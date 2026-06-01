"""Resolve boilerplate Global macro targets in Ableton live sets."""

from __future__ import annotations

import dataclasses
import re
import xml.etree.ElementTree as ET

from ableton_utilities import live_set
from ableton_utilities.hardware_xml import TrackBlock, parse_tracks


@dataclasses.dataclass(frozen=True)
class MacroTargetSpec:
    name: str
    target: str
    slot_object: str
    macro_index: int
    resolver: str


@dataclasses.dataclass(frozen=True)
class ResolvedMacroTarget:
    name: str
    target: str
    slot_object: str
    macro_index: int
    lom_id: str


BOILERPLATE_MACRO_TARGETS = (
    MacroTargetSpec("RollVol", "ControllerUtils > VSDC_IN > MidiVelocity > MaxOut/Out Hi", "obj-16", 0, "roll"),
    MacroTargetSpec("DrumMorph", "Micro > DrumGroupDevice > MacroControls.0/Morph", "obj-5", 1, "morph"),
    MacroTargetSpec("PercRoll", "ArpPerc > InstrumentGroupDevice > MacroControls.0", "obj-10", 2, "perc"),
    MacroTargetSpec("DrumFilter", "AllDrum > CrushFilter > MacroControls.0/Sample Rate", "obj-11", 3, "filter"),
    MacroTargetSpec("DrumVerb", "AllDrum > Mixer > Sends.1/B-BigVerb", "obj-12", 4, "verb"),
)


def ensure_boilerplate_macro_targets(xml: str) -> tuple[str, list[ResolvedMacroTarget], list[str]]:
    resolved: list[ResolvedMacroTarget] = []
    warnings: list[str] = []
    resolvers = {
        "roll": _ensure_roll_volume_target,
        "morph": _ensure_drum_morph_target,
        "perc": _ensure_perc_roll_target,
        "filter": _ensure_drum_filter_target,
        "verb": _ensure_drum_verb_target,
    }

    for spec in BOILERPLATE_MACRO_TARGETS:
        xml, lom_id, target_warnings = resolvers[spec.resolver](xml)
        warnings.extend(target_warnings)
        if lom_id is not None:
            resolved.append(ResolvedMacroTarget(spec.name, spec.target, spec.slot_object, spec.macro_index, lom_id))
    return xml, resolved, warnings


def _ensure_roll_volume_target(xml: str) -> tuple[str, str | None, list[str]]:
    tracks = parse_tracks(xml)
    controller = _find_track(tracks, "ControllerUtils")
    target_track = _find_track(tracks, "VSDC_IN", group_id=controller.track_id if controller else None)
    if target_track is None:
        return xml, None, ["No ControllerUtils > VSDC_IN track was found for RollVol mapping."]

    block, lom_id = _ensure_nested_parameter_lom(target_track.block, ("MidiVelocity", "MaxOut"), _next_lom_id(xml))
    if lom_id is None:
        return xml, None, ["VSDC_IN had no MidiVelocity MaxOut/Out Hi parameter for RollVol mapping."]
    return _replace_track_if_changed(xml, target_track, block), lom_id, []


def _ensure_drum_morph_target(xml: str) -> tuple[str, str | None, list[str]]:
    return _ensure_device_macro_lom(
        xml,
        track_name="Micro",
        device_tag="DrumGroupDevice",
        macro_tag="MacroControls.0",
        warning_name="DrumMorph",
    )


def _ensure_perc_roll_target(xml: str) -> tuple[str, str | None, list[str]]:
    return _ensure_device_macro_lom(
        xml,
        track_name="ArpPerc",
        device_tag="InstrumentGroupDevice",
        macro_tag="MacroControls.0",
        warning_name="PercRoll",
    )


def _ensure_drum_filter_target(xml: str) -> tuple[str, str | None, list[str]]:
    tracks = parse_tracks(xml)
    track = _find_track(tracks, "AllDrum")
    if track is None:
        return xml, None, ["No AllDrum track was found for DrumFilter mapping."]

    for device_range in live_set.tag_ranges(track.block, {"AudioEffectGroupDevice"}):
        device = track.block[device_range[0] : device_range[1]]
        if _xml_value(device, "./UserName") != "CrushFilter":
            continue
        block, lom_id = _ensure_nested_parameter_lom(device, ("MacroControls.0",), _next_lom_id(xml))
        if lom_id is None:
            return xml, None, ["AllDrum CrushFilter had no MacroControls.0 for DrumFilter mapping."]
        device = block
        track_block = live_set.replace_range(track.block, device_range, device)
        return _replace_track_if_changed(xml, track, track_block), lom_id, []
    return xml, None, ["No AllDrum CrushFilter rack was found for DrumFilter mapping."]


def _ensure_drum_verb_target(xml: str) -> tuple[str, str | None, list[str]]:
    tracks = parse_tracks(xml)
    track = _find_track(tracks, "AllDrum")
    if track is None:
        return xml, None, ["No AllDrum track was found for DrumVerb mapping."]

    for holder_range in live_set.tag_ranges(track.block, {"TrackSendHolder"}):
        holder = track.block[holder_range[0] : holder_range[1]]
        if not re.match(r'\s*<TrackSendHolder\b[^>]*\bId="1"', holder):
            continue
        block, lom_id = _ensure_nested_parameter_lom(holder, ("Send",), _next_lom_id(xml))
        if lom_id is None:
            return xml, None, ["AllDrum send 1 had no Send parameter for DrumVerb mapping."]
        track_block = live_set.replace_range(track.block, holder_range, block)
        return _replace_track_if_changed(xml, track, track_block), lom_id, []
    return xml, None, ["No AllDrum send 1/B-BigVerb slot was found for DrumVerb mapping."]


def _ensure_device_macro_lom(
    xml: str,
    track_name: str,
    device_tag: str,
    macro_tag: str,
    warning_name: str,
) -> tuple[str, str | None, list[str]]:
    track = _find_track(parse_tracks(xml), track_name)
    if track is None:
        return xml, None, [f"No {track_name} track was found for {warning_name} mapping."]

    block, lom_id = _ensure_device_parameter_lom(track.block, device_tag, macro_tag, _next_lom_id(xml))
    if lom_id is None:
        return xml, None, [f"No {track_name} {device_tag} {macro_tag} was found for {warning_name} mapping."]
    return _replace_track_if_changed(xml, track, block), lom_id, []


def _ensure_nested_parameter_lom(xml: str, tags: tuple[str, ...], new_lom_id: str) -> tuple[str, str | None]:
    target_range = _nested_tag_range(xml, tags)
    if target_range is None:
        return xml, None

    target = xml[target_range[0] : target_range[1]]
    current = _lom_id(target)
    if current and current != "0":
        return xml, current

    target, count = re.subn(r'(<LomId\b[^>]*\bValue=")\d+(" />)', rf"\g<1>{new_lom_id}\2", target, count=1)
    if count != 1:
        return xml, None
    return live_set.replace_range(xml, target_range, target), new_lom_id


def _nested_tag_range(xml: str, tags: tuple[str, ...]) -> tuple[int, int] | None:
    offset = 0
    current = xml
    for tag in tags:
        item_range = live_set.first_tag_range(current, tag)
        if item_range is None:
            return None
        offset += item_range[0]
        current = current[item_range[0] : item_range[1]]
    return offset, offset + len(current)


def _ensure_device_parameter_lom(
    track_block: str,
    device_tag: str,
    parameter_tag: str,
    new_lom_id: str,
) -> tuple[str, str | None]:
    parameter_ranges = _parameter_ranges_in_device(track_block, device_tag, parameter_tag)
    if not parameter_ranges:
        return track_block, None

    automation_ids = set(re.findall(r'<PointeeId\b[^>]*\bValue="(\d+)"', track_block))
    automated = [
        item_range
        for item_range in parameter_ranges
        if _automation_target_id(track_block[item_range[0] : item_range[1]]) in automation_ids
    ]
    target_range = automated[0] if automated else parameter_ranges[0]
    target = track_block[target_range[0] : target_range[1]]
    current = _lom_id(target)
    if current and current != "0":
        return track_block, current
    target, count = re.subn(r'(<LomId\b[^>]*\bValue=")\d+(" />)', rf"\g<1>{new_lom_id}\2", target, count=1)
    if count != 1:
        return track_block, None
    return live_set.replace_range(track_block, target_range, target), new_lom_id


def _parameter_ranges_in_device(track_block: str, device_tag: str, parameter_tag: str) -> list[tuple[int, int]]:
    device_ranges = live_set.tag_ranges(track_block, {device_tag})
    parameter_ranges = live_set.tag_ranges(track_block, {parameter_tag})
    results: list[tuple[int, int]] = []
    for parameter_range in parameter_ranges:
        containing = [r for r in device_ranges if r[0] <= parameter_range[0] and parameter_range[1] <= r[1]]
        if containing:
            results.append(parameter_range)
    return results


def _automation_target_id(xml: str) -> str | None:
    match = re.search(r'<AutomationTarget\b[^>]*\bId="(\d+)"', xml)
    return None if match is None else match.group(1)


def _replace_track_if_changed(xml: str, track: TrackBlock, block: str) -> str:
    return xml if block == track.block else live_set.replace_range(xml, (track.start, track.end), block)


def _find_track(tracks: list[TrackBlock], name: str, group_id: int | None = None) -> TrackBlock | None:
    return next((track for track in tracks if track.name == name and (group_id is None or track.group_id == group_id)), None)


def _next_lom_id(xml: str) -> str:
    return str(max((int(value) for value in re.findall(r'<LomId\b[^>]*\bValue="(\d+)"', xml)), default=0) + 1)


def _lom_id(xml: str) -> str | None:
    try:
        return ET.fromstring(xml).find("./LomId").attrib.get("Value")
    except (AttributeError, ET.ParseError):
        return None


def _xml_value(xml: str, path: str) -> str | None:
    try:
        node = ET.fromstring(xml).find(path)
    except ET.ParseError:
        return None
    return None if node is None else node.attrib.get("Value")

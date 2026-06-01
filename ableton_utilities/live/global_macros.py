"""Global Map8 macro boilerplate for Ableton live sets."""

from __future__ import annotations

import dataclasses
import re
import xml.etree.ElementTree as ET

from ableton_utilities import live_set
from ableton_utilities.hardware_xml import TrackBlock, parse_tracks


ROLL_VOLUME_TARGET = "ControllerUtils > VSDC_IN > MidiVelocity > MaxOut/Out Hi"
ROLL_VOLUME_SLOT_OBJECT = "obj-16"


@dataclasses.dataclass(frozen=True)
class GlobalMacroReport:
    name: str
    target: str
    lom_id: str


def apply_boilerplate_global_macros(xml: str) -> tuple[str, list[GlobalMacroReport], list[str]]:
    xml, lom_id, target_warnings = _ensure_roll_volume_target(xml)
    if lom_id is None:
        return xml, [], target_warnings

    tracks = parse_tracks(xml)
    global_track = _find_track(tracks, "Global")
    if global_track is None:
        return xml, [], [*target_warnings, "No Global track was found for RollVol Map8 mapping."]
    if "Map8.amxd" not in global_track.block:
        return xml, [], [*target_warnings, "Global track had no Map8.amxd device for RollVol mapping."]

    patched_global = _map_map8_slot(global_track.block, ROLL_VOLUME_SLOT_OBJECT, "RollVol", lom_id)
    xml = live_set.replace_range(xml, (global_track.start, global_track.end), patched_global)
    report = GlobalMacroReport("RollVol", ROLL_VOLUME_TARGET, lom_id)
    return xml, [report], target_warnings


def _ensure_roll_volume_target(xml: str) -> tuple[str, str | None, list[str]]:
    tracks = parse_tracks(xml)
    controller = _find_track(tracks, "ControllerUtils")
    target_track = _find_track(tracks, "VSDC_IN", group_id=controller.track_id if controller else None)
    if target_track is None:
        return xml, None, ["No ControllerUtils > VSDC_IN track was found for RollVol mapping."]

    block, lom_id = _ensure_velocity_maxout_lom(target_track.block, _next_lom_id(xml))
    if lom_id is None:
        return xml, None, ["VSDC_IN had no MidiVelocity MaxOut/Out Hi parameter for RollVol mapping."]
    if block != target_track.block:
        xml = live_set.replace_range(xml, (target_track.start, target_track.end), block)
    return xml, lom_id, []


def _ensure_velocity_maxout_lom(track_block: str, new_lom_id: str) -> tuple[str, str | None]:
    velocity_range = live_set.first_tag_range(track_block, "MidiVelocity")
    if velocity_range is None:
        return track_block, None
    velocity = track_block[velocity_range[0] : velocity_range[1]]
    maxout_range = live_set.first_tag_range(velocity, "MaxOut")
    if maxout_range is None:
        return track_block, None

    maxout = velocity[maxout_range[0] : maxout_range[1]]
    current = _lom_id(maxout)
    if current and current != "0":
        return track_block, current

    maxout, count = re.subn(
        r'(<LomId\b[^>]*\bValue=")\d+(" />)',
        rf"\g<1>{new_lom_id}\2",
        maxout,
        count=1,
    )
    if count != 1:
        return track_block, None
    velocity = live_set.replace_range(velocity, maxout_range, maxout)
    return live_set.replace_range(track_block, velocity_range, velocity), new_lom_id


def _map_map8_slot(global_block: str, slot_object: str, macro_name: str, lom_id: str) -> str:
    block, count = re.subn(
        r'(<MacroDisplayNames\.0\b[^>]*\bValue=")[^"]*(" />)',
        rf"\g<1>{live_set.escape_attr(macro_name)}\2",
        global_block,
        count=1,
    )
    if count != 1:
        raise ValueError("Could not rename Global macro display 0.")
    block = _upsert_idref(block, f"{slot_object}::obj-29::obj-18", lom_id, "id")
    block = _upsert_idref(block, f"{slot_object}::obj-28::obj-33", lom_id, "")
    return _enable_first_map8_toggle(block)


def _upsert_idref(block: str, name: str, lom_id: str, property_value: str) -> str:
    if f'<Name Value="{name}" />' in block:
        return _patch_idref_lom(block, name, lom_id)
    idref_range = _populated_idref_list_range(block)
    if idref_range is None:
        raise ValueError("Global Map8 had no populated IdRefList.")

    start, end = idref_range
    idref_block = block[start:end]
    next_id = max((int(match.group(1)) for match in re.finditer(r'<MxDIdRef Id="(\d+)"', idref_block)), default=-1) + 1
    line_sep = "\r\n" if "\r\n" in idref_block else "\n"
    indent_match = re.search(r"(\r?\n[\t ]*)<MxDIdRef Id=\"\d+\">", idref_block)
    if indent_match is None:
        raise ValueError("Could not infer IdRefList indentation.")
    indent = indent_match.group(1)[len(line_sep) :]
    child_indent = indent + "\t"
    entry = (
        f'{indent}<MxDIdRef Id="{next_id}">{line_sep}'
        f'{child_indent}<Name Value="{name}" />{line_sep}'
        f'{child_indent}<LomId Value="{lom_id}" />{line_sep}'
        f'{child_indent}<Property Value="{property_value}" />{line_sep}'
        f"{indent}</MxDIdRef>{line_sep}"
    )
    close = idref_block.rfind("</IdRefList>")
    return live_set.replace_range(block, idref_range, idref_block[:close] + entry + idref_block[close:])


def _patch_idref_lom(block: str, name: str, lom_id: str) -> str:
    pattern = re.compile(
        r'(<MxDIdRef\b[^>]*>\s*<Name Value="' + re.escape(name) + r'" />\s*<LomId Value=")([^"]*)(" />)',
        re.DOTALL,
    )
    block, count = pattern.subn(rf"\g<1>{lom_id}\3", block, count=1)
    if count != 1:
        raise ValueError(f"Could not patch existing MxDIdRef {name}.")
    return block


def _enable_first_map8_toggle(block: str) -> str:
    pattern = re.compile(r"(<Blob>\s*)([0-9A-Fa-f\s]+)(\s*</Blob>)")
    match = pattern.search(block)
    if match is None:
        raise ValueError("Global Map8 had no Blob payload.")
    decoded = bytes.fromhex("".join(match.group(2).split())).decode("utf-8")
    decoded = re.sub(r'("live\.toggle"\s*:\s*\[\s*)0(?:\.0)?(\s*\])', r"\g<1>1.0\2", decoded, count=1)
    encoded = decoded.encode("utf-8").hex().upper()
    line_sep = "\r\n" if "\r\n" in match.group(0) else "\n"
    leading = match.group(1)[len("<Blob>") :]
    indent = leading.split(line_sep)[-1] if line_sep in leading else ""
    chunks = [encoded[index : index + 80] for index in range(0, len(encoded), 80)]
    replacement = match.group(1) + (line_sep + indent).join(chunks) + match.group(3)
    return block[: match.start()] + replacement + block[match.end() :]


def _populated_idref_list_range(block: str) -> tuple[int, int] | None:
    return next((r for r in live_set.tag_ranges(block, {"IdRefList"}) if "<MxDIdRef " in block[r[0] : r[1]]), None)


def _find_track(tracks: list[TrackBlock], name: str, group_id: int | None = None) -> TrackBlock | None:
    return next((track for track in tracks if track.name == name and (group_id is None or track.group_id == group_id)), None)


def _next_lom_id(xml: str) -> str:
    return str(max((int(value) for value in re.findall(r'<LomId\b[^>]*\bValue="(\d+)"', xml)), default=0) + 1)


def _lom_id(xml: str) -> str | None:
    try:
        return ET.fromstring(xml).find("./LomId").attrib.get("Value")
    except (AttributeError, ET.ParseError):
        return None

"""XML block helpers for hardware-track conversion."""

from __future__ import annotations

import dataclasses
import re
import xml.etree.ElementTree as ET

from ableton_utilities import live_set
from ableton_utilities.hardware.automation import copy_mapped_automation_envelopes
from ableton_utilities.hardware.program_clips import apply_program_selection
from ableton_utilities.hardware.programs import ProgramSelection


TRACK_TAGS = {"AudioTrack", "GroupTrack", "MidiTrack"}


@dataclasses.dataclass(frozen=True)
class TrackBlock:
    index: int
    start: int
    end: int
    tag: str
    track_id: int
    group_id: int
    name: str
    block: str


def parse_tracks(xml: str) -> list[TrackBlock]:
    tracks: list[TrackBlock] = []
    for index, (start, end) in enumerate(live_set.tag_ranges(xml, TRACK_TAGS)):
        block = xml[start:end]
        try:
            element = ET.fromstring(block)
        except ET.ParseError:
            continue
        track_id = int(element.attrib.get("Id", "-1"))
        group_id = int(value(element, "./TrackGroupId") or "-1")
        tracks.append(TrackBlock(index, start, end, element.tag, track_id, group_id, track_name(element), block))
    return tracks


def track_name(element: ET.Element) -> str:
    return value(element, "./Name/EffectiveName") or value(element, "./Name/UserName") or ""


def value(element: ET.Element, path: str) -> str:
    node = element.find(path)
    return "" if node is None else node.attrib.get("Value", "")


def external_instrument_templates(xml: str) -> dict[str, str]:
    templates: dict[str, str] = {}
    for track in parse_tracks(xml):
        proxy = first_device_block(track.block, "ProxyInstrumentDevice")
        if not proxy:
            continue
        name = track.name.lower()
        if "tetra" in name and "tetra" not in templates:
            templates["tetra"] = proxy
        if "moog" in name and "moog" not in templates:
            templates["moog"] = proxy
    return templates


def first_device_block(track_block: str, tag: str) -> str | None:
    item_range = live_set.first_tag_range(track_block, tag)
    return None if item_range is None else track_block[item_range[0] : item_range[1]]


def find_group(tracks: list[TrackBlock], name: str) -> TrackBlock | None:
    target = normalize(name)
    return next((track for track in tracks if track.tag == "GroupTrack" and normalize(track.name) == target), None)


def find_child(children: list[TrackBlock], tag: str, hint: str) -> TrackBlock | None:
    normalized_hint = normalize(hint)
    matches = [track for track in children if track.tag == tag]
    return next((track for track in matches if normalized_hint in normalize(track.name)), matches[0] if matches else None)


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def build_live_track(
    group: TrackBlock,
    out_track: TrackBlock,
    proxy_template: str,
    config,
    track_id: int,
    first_global_id: int,
    mute_new_track: bool,
    program_selection: ProgramSelection | None = None,
) -> tuple[str, int]:
    block = out_track.block
    block = re.sub(r'(<MidiTrack\b[^>]*\bId=")(\d+)(")', rf"\g<1>{track_id}\3", block, count=1)
    block = set_track_name(block, config.new_track_name)
    block = re.sub(r'(<TrackGroupId\b[^>]*\bValue=")(-?\d+)(")', r"\g<1>-1\3", block, count=1)
    block = copy_first_tag(group.block, block, "AudioOutputRouting")
    block = copy_first_tag(group.block, block, "Mixer")
    proxy = patch_proxy(proxy_template, config)
    devices = [proxy, *direct_device_blocks(group.block)]
    block = replace_direct_devices(block, assign_device_ids(devices))
    if program_selection is not None:
        block = apply_program_selection(block, program_selection)
    if mute_new_track:
        block = set_speaker(block, "false")
    block, next_global_id, id_map = live_set.remap_global_ids_with_map(block, first_global_id)
    if config.key == "tetra":
        block = copy_mapped_automation_envelopes(group.block, block, id_map)
    return block, next_global_id


def copy_first_tag(source: str, target: str, tag: str) -> str:
    item_range = live_set.first_tag_range(source, tag)
    if item_range is None:
        return target
    return live_set.replace_first_tag(target, tag, source[item_range[0] : item_range[1]])


def direct_device_blocks(track_block: str) -> list[str]:
    inner_range = live_set.tag_inner_range(track_block, "Devices")
    if inner_range is None:
        return []
    return live_set.direct_child_blocks(track_block[inner_range[0] : inner_range[1]])


def replace_direct_devices(track_block: str, devices: list[str]) -> str:
    inner_range = live_set.tag_inner_range(track_block, "Devices")
    if inner_range is None:
        raise ValueError("Track direct <Devices> list was self-closing.")
    return live_set.replace_range(track_block, inner_range, "\n" + "\n".join(devices) + "\n")


def assign_device_ids(devices: list[str]) -> list[str]:
    return [live_set.set_root_id(block, index) for index, block in enumerate(devices)]


def set_track_name(block: str, name: str) -> str:
    name_range = live_set.first_tag_range(block, "Name")
    if name_range is None:
        raise ValueError("Track had no top-level <Name> block.")
    name_block = block[name_range[0] : name_range[1]]
    escaped = live_set.escape_attr(name)
    for tag in ("EffectiveName", "UserName"):
        name_block = re.sub(rf'(<{tag}\b[^>]*\bValue=")[^"]*(")', rf"\g<1>{escaped}\2", name_block, count=1)
    return live_set.replace_range(block, name_range, name_block)


def set_speaker(block: str, enabled: str) -> str:
    mixer_range = live_set.first_tag_range(block, "Mixer")
    if mixer_range is None:
        return block
    mixer = block[mixer_range[0] : mixer_range[1]]
    mixer = re.sub(
        r'(<Speaker>\s*<LomId\b[^>]*/>\s*<Manual\b[^>]*\bValue=")[^"]*(")',
        rf"\g<1>{enabled}\2",
        mixer,
        count=1,
    )
    return live_set.replace_range(block, mixer_range, mixer)


def patch_proxy(block: str, config) -> str:
    block = re.sub(r'(<UserName\b[^>]*\bValue=")[^"]*(")', rf"\g<1>{config.proxy_name}\2", block, count=1)
    block = patch_routable(block, "OutputHelper", config.midi_target, config.midi_upper, config.midi_lower)
    block = patch_routable(block, "InputHelper", config.audio_target, config.audio_upper, config.audio_lower)
    block = re.sub(
        r'(<InputHelper>.*?<Volume>.*?<Manual\b[^>]*\bValue=")[^"]*(")',
        rf"\g<1>{config.fallback_volume}\2",
        block,
        count=1,
        flags=re.DOTALL,
    )
    return block


def patch_routable(block: str, helper: str, target: str, upper: str, lower: str) -> str:
    helper_range = live_set.first_tag_range(block, helper)
    if helper_range is None:
        raise ValueError(f"External Instrument template had no {helper}.")
    helper_block = block[helper_range[0] : helper_range[1]]
    for tag, value_text in (("Target", target), ("UpperDisplayString", upper), ("LowerDisplayString", lower)):
        helper_block = re.sub(
            rf'(<{tag}\b[^>]*\bValue=")[^"]*(")',
            rf"\g<1>{live_set.escape_attr(value_text)}\2",
            helper_block,
            count=1,
        )
    return live_set.replace_range(block, helper_range, helper_block)

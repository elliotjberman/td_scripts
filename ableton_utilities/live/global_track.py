"""Create Global track boilerplate from a template Ableton set."""

from __future__ import annotations

import dataclasses
import re

from ableton_utilities import live_set
from ableton_utilities.hardware_xml import parse_tracks

SETLIST_DEVICE_MARKER = "setlist-device.amxd"


@dataclasses.dataclass(frozen=True)
class GlobalTrackResult:
    xml: str
    next_track_id: int
    next_global_id: int
    added: bool
    warnings: list[str]


def ensure_global_track(
    xml: str,
    template_xml: str,
    next_track_id: int,
    next_global_id: int,
) -> GlobalTrackResult:
    tracks = parse_tracks(xml)
    existing = next((track for track in tracks if track.name == "Global"), None)
    if existing is not None:
        block, next_global_id, warnings = _normalize_global_track(existing.block, template_xml, xml, next_global_id)
        if block != existing.block:
            xml = live_set.replace_range(xml, (existing.start, existing.end), block)
        return GlobalTrackResult(xml, next_track_id, next_global_id, False, warnings)

    template_global = next((track for track in parse_tracks(template_xml) if track.name == "Global"), None)
    if template_global is None:
        return GlobalTrackResult(xml, next_track_id, next_global_id, False, ["No Global track was found."])

    block = _set_track_id(template_global.block, next_track_id)
    block = _set_track_group_id(block, -1)
    block, next_global_id, _ = live_set.remap_global_ids_with_map(block, next_global_id)
    block = live_set.remap_nonzero_lom_ids(block, live_set.next_lom_id(xml))
    block = _clear_map8_targets(block)
    block, next_global_id, warnings = _normalize_global_track(block, template_xml, xml, next_global_id)
    insert_at = max((track.end for track in tracks), default=len(xml))
    xml = f"{xml[:insert_at]}\n{block}{xml[insert_at:]}"
    return GlobalTrackResult(xml, next_track_id + 1, next_global_id, True, warnings)


def _set_track_id(block: str, track_id: int) -> str:
    block, count = re.subn(
        r'(<(?:AudioTrack|MidiTrack|GroupTrack)\b[^>]*\bId=")\d+(")',
        rf"\g<1>{track_id}\2",
        block,
        count=1,
    )
    if count != 1:
        raise ValueError("Could not set cloned Global track id.")
    return block


def _set_track_group_id(block: str, group_id: int) -> str:
    return re.sub(
        r'(<TrackGroupId\b[^>]*\bValue=")-?\d+(")',
        rf"\g<1>{group_id}\2",
        block,
        count=1,
    )


def _normalize_global_track(
    block: str,
    template_xml: str,
    full_xml: str,
    next_global_id: int,
) -> tuple[str, int, list[str]]:
    warnings: list[str] = []
    block = _ensure_midi_track_tag(block)
    block = _ensure_midi_track_tail(block)
    if SETLIST_DEVICE_MARKER in block:
        return block, next_global_id, warnings
    setlist = _template_setlist_device(template_xml)
    if setlist is None:
        return block, next_global_id, ["No template setlist-device.amxd was found for Global."]
    setlist, next_global_id, _ = live_set.remap_global_ids_with_map(setlist, next_global_id)
    setlist = live_set.remap_nonzero_lom_ids(setlist, live_set.next_lom_id(f"{full_xml}{block}"))
    try:
        block = _insert_before_map8(block, setlist)
    except ValueError as exc:
        warnings.append(str(exc))
    return block, next_global_id, warnings


def _ensure_midi_track_tag(block: str) -> str:
    block = re.sub(r"^<AudioTrack\b", "<MidiTrack", block, count=1)
    return re.sub(r"</AudioTrack>\s*$", "</MidiTrack>", block, count=1)


def _ensure_midi_track_tail(block: str) -> str:
    if "<ReWireSlaveMidiTargetId " in block and "<PitchbendRange " in block:
        return block
    insert_at = block.rfind("</MidiTrack>")
    if insert_at < 0:
        return block
    line_sep = "\r\n" if "\r\n" in block else "\n"
    indent = live_set.line_indent(block, insert_at)
    tail = ""
    if "<ReWireSlaveMidiTargetId " not in block:
        tail += f'{indent}<ReWireSlaveMidiTargetId Value="3" />{line_sep}'
    if "<PitchbendRange " not in block:
        tail += f'{indent}<PitchbendRange Value="96" />{line_sep}'
    return f"{block[:insert_at]}{tail}{block[insert_at:]}"


def _template_setlist_device(xml: str) -> str | None:
    tracks = parse_tracks(xml)
    global_track = next((track for track in tracks if track.name == "Global" and SETLIST_DEVICE_MARKER in track.block), None)
    search = global_track.block if global_track else xml
    marker = search.find(SETLIST_DEVICE_MARKER)
    if marker < 0:
        return None
    ranges = live_set.tag_ranges(search, {"MxDeviceMidiEffect"})
    containing = [item_range for item_range in ranges if item_range[0] <= marker < item_range[1]]
    if not containing:
        return None
    start, end = min(containing, key=lambda item_range: item_range[1] - item_range[0])
    return search[start:end]


def _insert_before_map8(block: str, device: str) -> str:
    devices_range = _global_devices_range(block)
    devices = block[devices_range[0] : devices_range[1]]
    children = live_set.direct_child_blocks(live_set.tag_contents(devices))
    map8_child = next(
        (child for child in children if child.lstrip().startswith("<AudioEffectGroupDevice") and "Map8.amxd" in child),
        None,
    )
    if map8_child is None:
        raise ValueError("Global track had no direct Live_Macro/Map8 rack for setlist-device insertion.")
    device = live_set.set_root_id(device, live_set.next_root_id(children))
    insert_at = devices.find(map8_child)
    line_sep = "\r\n" if "\r\n" in devices else "\n"
    patched = f"{devices[:insert_at]}{device}{line_sep}{devices[insert_at:]}"
    return live_set.replace_range(block, devices_range, patched)


def _global_devices_range(block: str) -> tuple[int, int]:
    for devices_range in live_set.tag_ranges(block, {"Devices"}):
        devices = block[devices_range[0] : devices_range[1]]
        children = live_set.direct_child_blocks(live_set.tag_contents(devices))
        if any(child.lstrip().startswith("<AudioEffectGroupDevice") and "Map8.amxd" in child for child in children):
            return devices_range
    raise ValueError("Global track had no direct Devices list containing Live_Macro/Map8.")


def _clear_map8_targets(block: str) -> str:
    block = re.sub(
        r'(<MxDIdRef\b[^>]*>\s*<Name Value="[^"]+::obj-29::obj-18" />\s*<LomId Value=")\d+(" />)',
        r"\g<1>0\2",
        block,
        flags=re.DOTALL,
    )
    block = re.sub(
        r'\r?\n[\t ]*<MxDIdRef\b[^>]*>\s*<Name Value="[^"]+::obj-28::obj-33" />\s*'
        r'<LomId Value="\d+" />\s*<Property Value="[^"]*" />\s*</MxDIdRef>',
        "",
        block,
        flags=re.DOTALL,
    )
    return _clear_map8_blob_toggles(block)


def _clear_map8_blob_toggles(block: str) -> str:
    pattern = re.compile(r"(<Blob>\s*)([0-9A-Fa-f\s]+)(\s*</Blob>)")
    match = pattern.search(block)
    if match is None:
        return block
    decoded = bytes.fromhex("".join(match.group(2).split())).decode("utf-8")
    decoded = re.sub(r'("live\.toggle(?:\[\d+\])?"\s*:\s*\[\s*)[^]]+?(\s*\])', r"\g<1>0\2", decoded)
    encoded = decoded.encode("utf-8").hex().upper()
    line_sep = "\r\n" if "\r\n" in match.group(0) else "\n"
    leading = match.group(1)[len("<Blob>") :]
    indent = leading.split(line_sep)[-1] if line_sep in leading else ""
    chunks = [encoded[index : index + 80] for index in range(0, len(encoded), 80)]
    replacement = match.group(1) + (line_sep + indent).join(chunks) + match.group(3)
    return block[: match.start()] + replacement + block[match.end() :]

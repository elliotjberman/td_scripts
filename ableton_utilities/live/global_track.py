"""Create Global track boilerplate from a template Ableton set."""

from __future__ import annotations

import dataclasses
import re

from ableton_utilities import live_set
from ableton_utilities.hardware_xml import parse_tracks


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
    if any(track.name == "Global" for track in tracks):
        return GlobalTrackResult(xml, next_track_id, next_global_id, False, [])

    template_global = next((track for track in parse_tracks(template_xml) if track.name == "Global"), None)
    if template_global is None:
        return GlobalTrackResult(xml, next_track_id, next_global_id, False, ["No Global track was found."])

    block = _set_track_id(template_global.block, next_track_id)
    block = _set_track_group_id(block, -1)
    block, next_global_id, _ = live_set.remap_global_ids_with_map(block, next_global_id)
    block = _remap_nonzero_lom_ids(block, _next_lom_id(xml))
    block = _clear_map8_targets(block)
    insert_at = max((track.end for track in tracks), default=len(xml))
    xml = f"{xml[:insert_at]}\n{block}{xml[insert_at:]}"
    return GlobalTrackResult(xml, next_track_id + 1, next_global_id, True, [])


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


def _remap_nonzero_lom_ids(block: str, first_lom_id: int) -> str:
    next_lom_id = first_lom_id
    lomid_map: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        nonlocal next_lom_id
        old_id = match.group(2)
        if old_id == "0":
            return match.group(0)
        if old_id not in lomid_map:
            lomid_map[old_id] = str(next_lom_id)
            next_lom_id += 1
        return f"{match.group(1)}{lomid_map[old_id]}{match.group(3)}"

    return re.sub(r'(<LomId\b[^>]*\bValue=")(\d+)(")', replace, block)


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


def _next_lom_id(xml: str) -> int:
    return max((int(value) for value in re.findall(r'<LomId\b[^>]*\bValue="(\d+)"', xml)), default=0) + 1

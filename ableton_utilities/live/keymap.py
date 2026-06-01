"""Keyboard mapping helpers for Ableton live-set boilerplate."""

from __future__ import annotations

import re

from ableton_utilities import live_set
from ableton_utilities.hardware_xml import parse_tracks


GLOBAL_FOCUS_TARGET = "Global > Live_Macro/Map8 RemoteSelectionKeyMidi"


def apply_global_focus_key(xml: str, key: str = "/") -> tuple[str, bool, list[str]]:
    tracks = parse_tracks(xml)
    global_track = next((track for track in tracks if track.name == "Global"), None)
    if global_track is None:
        return xml, False, ["No Global track was found for focus key mapping."]

    device_range = _global_macro_device_range(global_track.block)
    if device_range is None:
        return xml, False, ["Global track had no Map8 rack for focus key mapping."]

    device = global_track.block[device_range[0] : device_range[1]]
    patched_device = _set_remote_selection_key(device, key)
    if patched_device == device:
        return xml, _has_remote_selection_key(device, key), []

    patched_track = live_set.replace_range(global_track.block, device_range, patched_device)
    xml = live_set.replace_range(xml, (global_track.start, global_track.end), patched_track)
    return xml, True, []


def _global_macro_device_range(track_block: str) -> tuple[int, int] | None:
    for device_range in live_set.tag_ranges(track_block, {"AudioEffectGroupDevice"}):
        device = track_block[device_range[0] : device_range[1]]
        if "Map8.amxd" in device:
            return device_range
    return None


def _set_remote_selection_key(device: str, key: str) -> str:
    key_range = live_set.first_tag_range(device, "RemoteSelectionKeyMidi")
    if key_range is not None:
        key_block = device[key_range[0] : key_range[1]]
        patched = _patch_key_block(key_block, key)
        return live_set.replace_range(device, key_range, patched)

    insert_at = device.find("<SourceContext>")
    if insert_at < 0:
        return device
    return f"{device[:insert_at]}{_remote_selection_key_block(device, insert_at, key)}{device[insert_at:]}"


def _has_remote_selection_key(device: str, key: str) -> bool:
    key_range = live_set.first_tag_range(device, "RemoteSelectionKeyMidi")
    if key_range is None:
        return False
    key_block = device[key_range[0] : key_range[1]]
    return f'<PersistentKeyString Value="{live_set.escape_attr(key)}" />' in key_block


def _patch_key_block(block: str, key: str) -> str:
    block = re.sub(r'(<PersistentKeyString\b[^>]*\bValue=")[^"]*(" />)', rf"\g<1>{key}\2", block, count=1)
    for tag in ("Channel", "NoteOrController", "LowerRangeNote", "UpperRangeNote"):
        block = re.sub(rf"(<{tag}\b[^>]*\bValue=\")-?\d+(\" />)", r"\g<1>-1\2", block, count=1)
    block = re.sub(r'(<IsNote\b[^>]*\bValue=")[^"]*(" />)', r"\g<1>false\2", block, count=1)
    block = re.sub(r'(<ControllerMapMode\b[^>]*\bValue=")\d+(" />)', r"\g<1>0\2", block, count=1)
    return block


def _remote_selection_key_block(device: str, insert_at: int, key: str) -> str:
    line_sep = "\r\n" if "\r\n" in device else "\n"
    indent = _line_indent(device, insert_at)
    child_indent = indent + "\t"
    return (
        f"{indent}<RemoteSelectionKeyMidi>{line_sep}"
        f'{child_indent}<PersistentKeyString Value="{live_set.escape_attr(key)}" />{line_sep}'
        f'{child_indent}<IsNote Value="false" />{line_sep}'
        f'{child_indent}<Channel Value="-1" />{line_sep}'
        f'{child_indent}<NoteOrController Value="-1" />{line_sep}'
        f'{child_indent}<LowerRangeNote Value="-1" />{line_sep}'
        f'{child_indent}<UpperRangeNote Value="-1" />{line_sep}'
        f'{child_indent}<ControllerMapMode Value="0" />{line_sep}'
        f"{indent}</RemoteSelectionKeyMidi>{line_sep}"
    )


def _line_indent(text: str, index: int) -> str:
    line_start = text.rfind("\n", 0, index)
    if line_start < 0:
        return ""
    return re.match(r"[\t ]*", text[line_start + 1 : index]).group(0)

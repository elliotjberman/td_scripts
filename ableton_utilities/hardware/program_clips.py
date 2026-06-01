"""Write MIDI program selections into Ableton Session clips."""

from __future__ import annotations

import re

from ableton_utilities import live_set
from ableton_utilities.hardware.programs import MidiProgramValues, ProgramSelection


VALUE_TAGS = ("BankSelectCoarse", "BankSelectFine", "ProgramChange")


def apply_program_selection(track_block: str, selection: ProgramSelection) -> str:
    values = selection.clip_values()
    slot_range = _session_slot_list_range(track_block)
    if slot_range is None:
        return track_block

    slot_list = track_block[slot_range[0] : slot_range[1]]
    slot_list = _prepare_first_scene(slot_list, _first_midi_clip(track_block), selection)
    slot_list = _patch_unprogrammed_session_clips(slot_list, values)
    return live_set.replace_range(track_block, slot_range, slot_list)


def _session_slot_list_range(track_block: str) -> tuple[int, int] | None:
    main_range = live_set.first_tag_range(track_block, "MainSequencer")
    if main_range is None:
        return None
    main = track_block[main_range[0] : main_range[1]]
    slot_range = live_set.first_tag_range(main, "ClipSlotList")
    if slot_range is None:
        return None
    return main_range[0] + slot_range[0], main_range[0] + slot_range[1]


def _prepare_first_scene(slot_list: str, template: str | None, selection: ProgramSelection) -> str:
    inner_range = live_set.tag_inner_range(slot_list, "ClipSlotList")
    if inner_range is None:
        return slot_list
    inner = slot_list[inner_range[0] : inner_range[1]]
    child_ranges = live_set.direct_child_ranges(inner)
    if not child_ranges:
        return slot_list

    first_start, first_end = child_ranges[0]
    first_slot = inner[first_start:first_end]
    clip_range = live_set.first_tag_range(first_slot, "MidiClip")
    if clip_range is not None:
        first_slot = _name_or_program_first_dummy(first_slot, clip_range, selection)
        absolute = (inner_range[0] + first_start, inner_range[0] + first_end)
        return live_set.replace_range(slot_list, absolute, first_slot)

    if template is None:
        return slot_list

    filled = _fill_empty_clip_slot(first_slot, _make_dummy_clip(template, selection))
    absolute = (inner_range[0] + first_start, inner_range[0] + first_end)
    return live_set.replace_range(slot_list, absolute, filled)


def _name_or_program_first_dummy(
    slot_block: str, clip_range: tuple[int, int], selection: ProgramSelection
) -> str:
    clip = slot_block[clip_range[0] : clip_range[1]]
    if _first_midi_note(clip) is not None:
        return slot_block

    values = selection.clip_values()
    if not _has_program_data(clip):
        clip = _set_clip_program(clip, values)
    if _clip_program_matches(clip, values) and not _clip_name(clip):
        clip = _set_clip_name(clip, selection.dummy_clip_name())
    return live_set.replace_range(slot_block, clip_range, clip)


def _patch_unprogrammed_session_clips(slot_list: str, values: MidiProgramValues) -> str:
    replacements: list[tuple[int, int, str]] = []
    for start, end in live_set.tag_ranges(slot_list, {"MidiClip"}):
        clip = slot_list[start:end]
        if _has_program_data(clip):
            continue
        replacements.append((start, end, _set_clip_program(clip, values)))
    for start, end, replacement in reversed(replacements):
        slot_list = live_set.replace_range(slot_list, (start, end), replacement)
    return slot_list


def _first_midi_clip(xml: str) -> str | None:
    clip_range = live_set.first_tag_range(xml, "MidiClip")
    return None if clip_range is None else xml[clip_range[0] : clip_range[1]]


def _make_dummy_clip(template: str, selection: ProgramSelection) -> str:
    values = selection.clip_values()
    clip = _clear_midi_notes(template)
    clip = _set_clip_name(clip, selection.dummy_clip_name())
    clip = _set_clip_time(clip, "0")
    for tag, value in (
        ("CurrentStart", "0"),
        ("CurrentEnd", "4"),
        ("LoopStart", "0"),
        ("LoopEnd", "4"),
        ("HiddenLoopStart", "0"),
        ("HiddenLoopEnd", "4"),
    ):
        clip = _set_value_tag(clip, tag, value)
    return _set_clip_program(clip, values)


def _clear_midi_notes(clip: str) -> str:
    for note_range in reversed(live_set.tag_ranges(clip, {"MidiNoteEvent"})):
        clip = live_set.replace_range(clip, note_range, "")
    return clip


def _first_midi_note(clip: str) -> tuple[int, int] | None:
    return live_set.first_tag_range(clip, "MidiNoteEvent")


def _set_clip_name(clip: str, name: str) -> str:
    escaped = live_set.escape_attr(name)
    name_range = live_set.first_tag_range(clip, "Name")
    if name_range is None:
        pattern = re.compile(r'(<Name\b[^>]*\bValue=")[^"]*(")')
        return pattern.sub(rf"\g<1>{escaped}\2", clip, count=1)
    block = clip[name_range[0] : name_range[1]]
    for tag in ("EffectiveName", "UserName"):
        block = re.sub(rf'(<{tag}\b[^>]*\bValue=")[^"]*(")', rf"\g<1>{escaped}\2", block, count=1)
    return live_set.replace_range(clip, name_range, block)


def _set_clip_time(clip: str, value: str) -> str:
    return re.sub(r'(<MidiClip\b[^>]*\bTime=")[^"]*(")', rf"\g<1>{value}\2", clip, count=1)


def _set_clip_program(clip: str, values: MidiProgramValues) -> str:
    for tag, value in (
        ("BankSelectCoarse", values.bank_select_coarse),
        ("BankSelectFine", values.bank_select_fine),
        ("ProgramChange", values.program_change),
    ):
        clip = _set_value_tag(clip, tag, str(value))
    return clip


def _has_program_data(clip: str) -> bool:
    return any((_value_tag(clip, tag) or "-1") != "-1" for tag in VALUE_TAGS)


def _clip_program_matches(clip: str, values: MidiProgramValues) -> bool:
    return (
        (_value_tag(clip, "BankSelectCoarse") or "-1") == str(values.bank_select_coarse)
        and (_value_tag(clip, "BankSelectFine") or "-1") == str(values.bank_select_fine)
        and (_value_tag(clip, "ProgramChange") or "-1") == str(values.program_change)
    )


def _clip_name(clip: str) -> str:
    return _value_tag(clip, "UserName") or _value_tag(clip, "EffectiveName") or ""


def _value_tag(xml: str, tag: str) -> str | None:
    match = re.search(rf'<{tag}\b[^>]*\bValue="([^"]*)"', xml)
    return None if match is None else match.group(1)


def _set_value_tag(xml: str, tag: str, value: str) -> str:
    return re.sub(rf'(<{tag}\b[^>]*\bValue=")[^"]*(")', rf"\g<1>{value}\2", xml, count=1)


def _fill_empty_clip_slot(slot_block: str, clip: str) -> str:
    pattern = re.compile(r"(<ClipSlot>\s*)<Value\s*/>(\s*</ClipSlot>)", re.DOTALL)
    return pattern.sub(lambda match: f"{match.group(1)}<Value>\n{clip}\n</Value>{match.group(2)}", slot_block, count=1)

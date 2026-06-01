"""Parse hardware patch hints and write MIDI program changes into clips."""

from __future__ import annotations

import dataclasses
import re

from ableton_utilities import live_set


PAIR_RE = re.compile(r"(?<!\d)(\d{1,3})\s*-\s*(\d{1,3})(?!\d)")
MOOG_PROGRAM_RE = re.compile(r"\bmoog(?:live|out|trig)?[\s_-]*\(?(\d{1,3})\)?\s*$", re.IGNORECASE)
TETRA_BANKS = {1, 2}
VALUE_TAGS = ("BankSelectCoarse", "BankSelectFine", "ProgramChange")


@dataclasses.dataclass(frozen=True)
class MidiProgramValues:
    bank_select_coarse: int
    bank_select_fine: int
    program_change: int


@dataclasses.dataclass(frozen=True)
class ProgramSelection:
    synth_key: str
    program: int
    bank: int | None
    source_name: str
    source_order: str

    def clip_values(self) -> MidiProgramValues:
        if self.synth_key == "tetra":
            bank = -1 if self.bank is None else self.bank - 1
            return MidiProgramValues(-1, bank, self.program - 1)
        return MidiProgramValues(-1, -1, self.program - 1)

    def dummy_clip_name(self) -> str:
        if self.bank is None:
            return f"PC {self.program}"
        return f"PC {self.bank}-{self.program}"


def parse_track_program(name: str, synth_key: str) -> ProgramSelection | None:
    if synth_key == "tetra":
        return _parse_tetra_program(name)
    if synth_key == "moog":
        return _parse_moog_program(name)
    return None


def apply_program_selection(track_block: str, selection: ProgramSelection) -> str:
    values = selection.clip_values()
    slot_range = _session_slot_list_range(track_block)
    if slot_range is None:
        return track_block

    slot_list = track_block[slot_range[0] : slot_range[1]]
    slot_list = _prepare_first_scene(slot_list, _first_midi_clip(track_block), selection)
    slot_list = _patch_unprogrammed_session_clips(slot_list, values)
    return live_set.replace_range(track_block, slot_range, slot_list)


def _parse_tetra_program(name: str) -> ProgramSelection | None:
    if "tetra" not in name.lower():
        return None
    matches = PAIR_RE.findall(name)
    if not matches:
        return None

    first, second = (int(part) for part in matches[-1])
    if first in TETRA_BANKS:
        bank, program, order = first, second, "bank-program"
    elif second in TETRA_BANKS:
        program, bank, order = first, second, "program-bank"
    else:
        return None
    if not _valid_program(program):
        return None
    return ProgramSelection("tetra", program, bank, name, order)


def _parse_moog_program(name: str) -> ProgramSelection | None:
    match = MOOG_PROGRAM_RE.search(name)
    if not match:
        return None
    program = int(match.group(1))
    if not _valid_program(program):
        return None
    return ProgramSelection("moog", program, None, name, "program")


def _valid_program(program: int) -> bool:
    return 1 <= program <= 128


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
    inner_range = _tag_inner_range(slot_list, "ClipSlotList")
    if inner_range is None:
        return slot_list
    inner = slot_list[inner_range[0] : inner_range[1]]
    child_ranges = _direct_child_ranges(inner)
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


def _tag_inner_range(xml: str, tag: str) -> tuple[int, int] | None:
    tag_range = live_set.first_tag_range(xml, tag)
    if tag_range is None:
        return None
    open_end = xml.find(">", tag_range[0]) + 1
    close_start = xml.rfind(f"</{tag}>", tag_range[0], tag_range[1])
    if close_start < open_end:
        return None
    return open_end, close_start


def _direct_child_ranges(xml: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    stack: list[str] = []
    start: int | None = None
    for match in live_set.XML_TAG_RE.finditer(xml):
        closing, tag, _attrs, self_closing = match.groups()
        if closing:
            if stack and stack[-1] == tag:
                stack.pop()
                if not stack and start is not None:
                    ranges.append((start, match.end()))
                    start = None
            continue
        if not stack:
            start = match.start()
        if not self_closing:
            stack.append(tag)
        elif not stack and start is not None:
            ranges.append((start, match.end()))
            start = None
    return ranges

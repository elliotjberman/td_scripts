"""Parse hardware patch hints from track names."""

from __future__ import annotations

import re

from ableton_utilities.hardware.program_clips import apply_program_selection
from ableton_utilities.hardware.program_types import MidiProgramValues, ProgramSelection


PAIR_RE = re.compile(r"(?<!\d)(\d{1,3})\s*-\s*(\d{1,3})(?!\d)")
MOOG_PROGRAM_RE = re.compile(r"\bmoog(?:live|out|trig)?[\s_-]*\(?(\d{1,3})\)?\s*$", re.IGNORECASE)
TETRA_BANKS = {1, 2}


def parse_track_program(name: str, synth_key: str) -> ProgramSelection | None:
    if synth_key == "tetra":
        return _parse_tetra_program(name)
    if synth_key == "moog":
        return _parse_moog_program(name)
    return None


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

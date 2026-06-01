"""Parse hardware patch hints from track names."""

from __future__ import annotations

import dataclasses
import re


PAIR_RE = re.compile(r"(?<!\d)(\d{1,3})\s*-\s*(\d{1,3})(?!\d)")
MOOG_PROGRAM_RE = re.compile(r"\bmoog(?:live|out|trig)?[\s_-]*\(?(\d{1,3})\)?\s*$", re.IGNORECASE)
TETRA_BANKS = {1, 2}


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

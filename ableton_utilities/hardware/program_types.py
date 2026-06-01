"""Shared MIDI program-selection value objects."""

from __future__ import annotations

import dataclasses


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

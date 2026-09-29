from typing import List, Tuple


class TriggerExt:
    """Route notes to triggers inside the configured target component."""

    WILDCARD = "_"

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp

    def NoteTableNameForTrack(self, track_name: str) -> str:
        return track_name.removesuffix('_midi') + '_note_mappings'

    def TableHeaders(self) -> Tuple[str, str]:
        return 'note_number', 'trigger_name'

    def TargetRoot(self):
        return self.ownerComp.opex(str(self.ownerComp.par.Targetroot))

    def HandleNote(self, track_name: str, note_number: int, velocity: int) -> None:
        self.set_pitch(track_name, note_number)
        target_root = self.TargetRoot()
        failures = []
        for name in self.get_target_operator_names_for_track(track_name, note_number):
            try:
                target = target_root.opex(str(name))
                if isinstance(target, triggerCHOP):
                    target.par.triggerpulse.pulse()
                elif isinstance(target, baseCOMP):
                    target.store('velocity', velocity)
                    target.par.Trigger.pulse()
                else:
                    raise TypeError('Unsupported MIDI target: ' + target.path)
            except Exception as error:
                failures.append(f'{target_root.path}/{name}: {error}')
        if failures:
            raise RuntimeError('MIDI routing failed:\n' + '\n'.join(failures))

    def set_pitch(self, track_name: str, note_number: int) -> None:
        self.ownerComp.opex('last_note_' + track_name).par.value0 = note_number

    def get_target_operator_names_for_track(self, track_name: str, note_number: int) -> List[str]:
        table = self.ownerComp.opex(self.NoteTableNameForTrack(track_name))
        return (table.cells(str(note_number), 'trigger_name')
                + table.cells(self.WILDCARD, 'trigger_name'))

from typing import List, Tuple

import TDFunctions as TDF

class TriggerExt:
	"""
	TriggerExt description
	"""

	WILDCARD = "_"

	def __init__(self, ownerComp):
		# The component to which this extension is attached
		self.ownerComp = ownerComp

	# Can't do statics in TriggerExt's otherwise I would
	def NoteTableNameForTrack(self, track_name: str) -> str:
		return track_name.replace("_midi", "_note_mappings")

	def TableHeaders(self) -> Tuple[str, str]:
		return 'note_number', 'trigger_name'

	def HandleNote(self, track_name: str, note_number: int, velocity: int) -> None:
		self.set_pitch(track_name, note_number)
		trigger_names = self.get_target_operator_names_for_track(track_name, note_number)

		for trigger_name in trigger_names:
			operator = op(f'/*/{trigger_name}')
			if operator is None:
				continue
			if type(operator) == triggerCHOP:
				operator.par.triggerpulse.pulse()
			if type(operator) == baseCOMP:
				operator.store("velocity", velocity)
				operator.par.Trigger.pulse()

	def set_pitch(self, track_name: str, note_number: int) -> None:
		op(f'last_note_{track_name}').par.value0 = note_number

	def get_target_operator_names_for_track(self, track_name: str, note_number: int) -> List[str]:
		table_name = self.NoteTableNameForTrack(track_name)
		note_table = op(table_name)
		_, trigger_name_column = self.TableHeaders()
		numbered_cells = note_table.cells(str(note_number), trigger_name_column)
		wildcard_cells = note_table.cells(TriggerExt.WILDCARD, trigger_name_column)
		return numbered_cells + wildcard_cells

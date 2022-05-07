SPACING = 200

def onFindOPGetInclude(dat, curOp, row):
	return True

def onOPFound(dat, curOp, row, results):
	midi_table = create_or_get_midi_table(curOp)
	midi_table.nodeX = SPACING * (row - 1)

	return

def create_or_get_midi_table(midi_operator: op) -> op:
	table_operator_name = parent().NoteTableNameForTrack(midi_operator.name)
	note_table = op(table_operator_name)
	if note_table is None:
		note_table = create_new_midi_table(table_operator_name)

	return note_table

def create_new_midi_table(table_operator_name) -> op:
	new_table = parent().create(tableDAT, table_operator_name)
	new_table.par.file = f"{table_operator_name}.tsv"
	new_table.par.syncfile = True
	new_table.par.edit.pulse()
	new_table.insertRow(parent().TableHeaders())
	return new_table

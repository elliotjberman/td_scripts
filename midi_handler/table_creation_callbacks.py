def onFindOPGetInclude(dat, curOp, row):
	return True


# Provide an extensive dictionary of what was matched for each operator.
# Multiple matching tags, parameters and cells will be included.
# For each match, a corresponding key is included in the dictionary:
#
#  results:
#
#  'name': curOp.name
#  'type': curOp.OPType
#  'path': curOp.path
#  'parent' : curOp.parent()
#  'comment': curOp.comment
#  'tags' : [list of strings] or empty list
#  'text' : [list of Cells] or empty list
#  'par': dictionary of matching parameter attributes.
#    example entries:
#        tx : { 'name': True, 'value':True , 'expression':True } # Parameter tx matched on name, value, expression
#        ty : { 'value' : True } # Parameter ty matched on value
#

SPACING = 200

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
	new_table.insertRow(parent().TableHeaders())
	return new_table

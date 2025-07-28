# This is this bullshit script you need because when you accidentally open the wrong Ableton file with a given TDAbleton Setup
# it will mess around with all of the assignments of tracks/chains based on some kind of index system.

# This goes through and hardcodes the indices of all the tracks/chains so even if you open the wrong Ableton set, the TDAbleton COMPs
# should not get altered.

# Use in a DAT-Execute with an OPFind input looking for "Other COMPs".

DONT_ALTER = (
	"Autosync",
	"Valuesend",
	"Mapfromlive",
)

MIDI_PARAMS = (
	"Track",
	"Device",
)

ABLETON_PARAMETER = "Ableton Parameter"
ABLETON_MIDI = "Ableton MIDI"

def onTableChange(dat):
	for row in dat.rows():
		comp = op(row[0].val)
		if comp is None:
			continue
	
		# Because TD doesn't have COMP type info
		if ABLETON_PARAMETER in comp.customPages:
			handle_ableton_parameter(comp)
			continue

		if ABLETON_MIDI in comp.customPages:
			handle_ableton_midi(comp)


def handle_ableton_parameter(comp):
	for parameter in comp.customPages[ABLETON_PARAMETER].pars:
		if parameter.hidden or parameter.val is None or parameter.name in DONT_ALTER:
			continue

		freeze_parameter(parameter)

def handle_ableton_midi(comp):
	for parameter in comp.customPages["Ableton MIDI"].pars:
		if parameter.hidden or parameter.val is None or parameter.name not in MIDI_PARAMS:
			continue

		freeze_parameter(parameter)


def freeze_parameter(parameter):
	value = parameter.menuIndex
	if value is None:
		return

	parameter.expr = f"{value} + 0"
	parameter.mode = ParMode.EXPRESSION

def onRowChange(dat, rows):
	return

def onColChange(dat, cols):
	return

def onCellChange(dat, cells, prev):
	return

def onSizeChange(dat):
	return
	
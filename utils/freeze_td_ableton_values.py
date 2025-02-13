# This is this bullshit script you need because when you accidentally open the wrong Ableton file with a given TDAbleton Setup
# it will mess around with all of the assignments of tracks/chains based on some kind of index system.

# This goes through and hardcodes the indices of all the tracks/chains so even if you open the wrong Ableton set, the TDAbleton COMPs
# should not get altered.

DONT_ALTER = (
	"Autosync",
	"Valuesend",
	"Mapfromlive",
)

def onTableChange(dat):
	for row in dat.rows():
		comp = op(row[0].val)
		if comp is None:
			continue
	
		for parameter in comp.customPages["Ableton Parameter"].pars:
			if parameter.hidden or parameter.val is None or parameter.name in DONT_ALTER:
				continue

			value = parameter.menuIndex
			if value is None:
				continue

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
	
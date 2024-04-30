# Point the parameters at the parent's
inherited_params = [
	"Home",
	"Resolutionw",
	"Resolutionh"
]

def onTableChange(dat):
	for row in dat.rows()[1:]:
		name = row[0]
		for param in inherited_params:
			op(name).par[param].expr = f'parent().par.{param}'

	return
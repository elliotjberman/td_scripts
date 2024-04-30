default_expressions = {
	"home": "parent().par.Home",
	"resolution": {
		"width": "parent().par.Resolutionw",
		"height": "parent().par.Resolutionh",
	}
}

def onTableChange(dat):
	for row in dat.rows()[1:]:
		name = row[0]
		op(name).par.Resolutionw.expr = default_expressions['resolution']['width']
		op(name).par.Resolutionh.expr = default_expressions['resolution']['height']
		op(name).par.Home.expr = default_expressions['home']

	return
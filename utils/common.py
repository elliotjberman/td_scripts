# Point the parameters at the parent's
inherited_params = [
	"Home",
	"Resolutionw",
	"Resolutionh"
]

def disable_all_visuals(dat):
    operators = [op(name) for name, in dat.rows()[1:]]

    for operator in operators:
         operator.allowCooking = False

def reset_all_visuals(dat):
    # Exclude header row, fetch all operators by name
	operators = [op(name) for name, in dat.rows()[1:]] 	

	# Go top to bottom visually
	operators.sort(key=lambda operator: operator.nodeCenterY, reverse=True)

	for operator in operators:
		mod.common.reset_visual(operator)

	return

def reset_visual(operator):
    # Set params uniformly to point to parents
    for param in inherited_params:
        operator.par[param].expr = f'parent().par.{param}'

    # Protect against double-connecting
    for connector in operator.outputConnectors:
        connector.disconnect()

    operator.outputConnectors[0].connect(op('ableton_switcher'))

    # Set viewer to be on
    operator.viewer = True
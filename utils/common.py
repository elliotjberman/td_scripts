# Point the parameters at the parent's
inherited_params = [
	"Home",
	"Resolutionw",
	"Resolutionh"
]

def disable_all_visuals(dat):
    operators = [op(name) for name, in dat.rows()[1:]]

    for operator in operators:
        disable_visual(operator)

def enable_visual(operator):
    if operator.par['Disable'] is not None:
        operator.par.Disable = False
        return
    operator.allowCooking = True

def disable_visual(operator):
    if operator.par['Disable'] is not None:
        operator.par.Disable = True
        return
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

    # Set viewer to be off - otherwise it may request data from its network
    operator.viewer = False
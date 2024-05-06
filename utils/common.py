# Point the parameters at the parent's
inherited_params = [
	"Home",
	"Resolutionw",
	"Resolutionh"
]

def reset_visual(operator):
    # Set params uniformly to point to parents
    for param in inherited_params:
        operator.par[param].expr = f'parent().par.{param}'

    # Protect against double-connecting
    for connector in operator.outputConnectors:
        connector.disconnect()

    operator.outputConnectors[0].connect(op('ableton_switcher'))
def onOffToOn(channel, sampleIndex, val, prev):
	for operator in get_ableton_operators():
		operator.allowCooking = False

def whileOn(channel, sampleIndex, val, prev):
	return

def onOnToOff(channel, sampleIndex, val, prev):
	for operator in get_ableton_operators():
		operator.allowCooking = True

def whileOff(channel, sampleIndex, val, prev):
	return

def onValueChange(channel, sampleIndex, val, prev):
	return

def get_ableton_operators():
	# Exclude header row
	paths = []
	for operator_path, in op("ableton_operators").rows()[1:]:
		paths.append(op(operator_path))

	return paths
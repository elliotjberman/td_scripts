def onTableChange(dat):
	# Exclude header row, fetch all operators by name
	operators = [op(name) for name, in dat.rows()[1:]] 	

	# Go top to bottom visually
	operators.sort(key=lambda operator: operator.nodeCenterY, reverse=True)

	for operator in operators:
		mod.common.reset_visual(operator)

	return
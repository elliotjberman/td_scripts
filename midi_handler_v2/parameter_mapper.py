import time

import td


WIDTH = 760
HEIGHT = 340
INFO_H = 86
ROW_H = 30
ROUTE_TARGET_TAG = "midi-route-target"
ENVELOPE_TAG = "scaled-envelope"
IGNORED_PARAMETER_NAMES = {
	"pageindex",
}


def ensure_parameter_mapper(manager):
	_tracker_execute(manager)
	_tracker_callbacks(manager)
	panel = _panel(manager)
	_rows(panel, "parameter_bind_info_rows", ("Field", "Value"))
	_rows(panel, "parameter_bind_output_rows", ("Envelope Output", "Path", "expr_path"))
	_info_list(panel)
	_output_list(panel)
	_window(manager, panel)
	return panel


def open_parameter_mapper(manager):
	panel = ensure_parameter_mapper(manager)
	update_parameter_tracker(manager)
	_build_info_rows(manager, panel.op("parameter_bind_info_rows"))
	_build_output_rows(manager, panel.op("parameter_bind_output_rows"))
	_reset(panel, "parameter_bind_info_list")
	_reset(panel, "parameter_bind_output_list")
	window = manager.ownerComp.op("parameter_bind_window")
	window.par.winopen.pulse()
	return last_parameter(manager)


def update_parameter_tracker(manager):
	target = _selected_operator(manager) or _tracked_operator(manager)
	callbacks = _tracker_callbacks(manager)
	if target is None:
		return None
	if callbacks.fetch("target_path", "") == target.path:
		callbacks.par.active = True
		_poll_parameter_snapshot(manager, target)
		return target
	callbacks.par.active = False
	callbacks.par.pars = "*"
	callbacks.par.fromop = target.path
	callbacks.par.op = target.path
	callbacks.par.active = True
	callbacks.store("target_path", target.path)
	_store_parameter_snapshot(manager, target)
	return target


def record_parameter_change(manager, par, prev):
	if not _is_trackable_parameter(manager, par):
		return None
	info = {
		"owner": par.owner.path,
		"owner_name": par.owner.name,
		"name": par.name,
		"label": getattr(par, "label", par.name),
		"page": getattr(getattr(par, "page", None), "name", ""),
		"value": _safe_eval(par),
		"prev": str(prev),
		"time": time.time(),
	}
	manager.ownerComp.store("last_parameter_target", info)
	return info


def last_parameter(manager):
	return dict(manager.ownerComp.fetch("last_parameter_target", {}))


def apply_binding(manager, output_path):
	info = last_parameter(manager)
	owner = _op(manager, info.get("owner", ""))
	if owner is None:
		return False
	par = owner.par[info.get("name", "")]
	if par is None:
		return False
	output_path = str(output_path or "")
	if not output_path:
		return False
	expr = "op({!r})[0]".format(output_path)
	par.expr = expr
	_set_expression_mode(manager, par)
	manager.ownerComp.store("last_parameter_binding", {
		"owner": owner.path,
		"parameter": par.name,
		"output": output_path,
		"expr": expr,
		"time": time.time(),
	})
	_close_window(manager)
	return True


def discover_outputs(manager):
	root = manager.ownerComp.parent()
	items = []
	for child in root.children:
		for output, envelope_path in _candidate_outputs(child):
			items.append(_output_item(root, output))
	by_path = {}
	for item in items:
		path = item["path"]
		current = by_path.get(path)
		if current is not None and current["priority"] <= item["priority"]:
			continue
		by_path[path] = item
	outputs = [{"label": item["label"], "path": item["path"]} for item in by_path.values()]
	outputs.sort(key=lambda item: item["label"].lower())
	return outputs


def _candidate_outputs(operator):
	outputs = []
	if _is_chop(operator) and ROUTE_TARGET_TAG in operator.tags:
		for terminal in _terminal_output_chops(operator):
			outputs.append((terminal, _source_envelope_path(operator)))
	if ENVELOPE_TAG in operator.tags:
		chop = _envelope_output_chop(operator)
		if chop is not None:
			for terminal in _terminal_output_chops(chop):
				outputs.append((terminal, operator.path))
	return outputs


def _terminal_output_chops(chop):
	terminals = []
	stack = [(chop, 0)]
	seen = set()
	while stack:
		current, depth = stack.pop()
		if current is None or current.path in seen:
			continue
		seen.add(current.path)
		outputs = [
			out for out in getattr(current, "outputs", [])
			if _is_chop(out) and _same_chain_scope(chop, out)
		]
		if not outputs or depth >= 12:
			terminals.append(current)
			continue
		for output in reversed(outputs):
			stack.append((output, depth + 1))
	return terminals


def _same_chain_scope(start, candidate):
	try:
		return candidate.parent() in (start.parent(), start.parent().parent())
	except Exception:
		return False


def _envelope_output_chop(envelope):
	for name in ("value", "out1", "final_value", "envelope_scale", "trigger_out"):
		chop = envelope.op(name)
		if chop is not None and _is_chop(chop):
			return chop
	for child in envelope.children:
		if _is_chop(child) and str(child.OPType).lower() == "outchop":
			return child
	return None


def _source_envelope_path(output):
	source = output.fetch("source_envelope", "")
	if source:
		return str(source)
	if ENVELOPE_TAG in output.tags:
		return output.path
	parent_op = output.parent()
	if parent_op is not None and ENVELOPE_TAG in parent_op.tags:
		return parent_op.path
	return ""


def _output_priority(output):
	if output.fetch("source_envelope", ""):
		return 0
	if ROUTE_TARGET_TAG in output.tags:
		return 1
	return 2


def _output_item(root, output):
	return {
		"label": _terminal_label(root, output),
		"path": output.path,
		"priority": _output_priority(output),
	}


def _terminal_label(root, output):
	try:
		if output.parent() == root:
			return output.name
		parent_op = output.parent()
		if parent_op is not None:
			return "{}/{}".format(parent_op.name, output.name)
	except Exception:
		pass
	return output.name


def _build_info_rows(manager, rows):
	info = last_parameter(manager)
	rows.clear()
	rows.appendRow(("Field", "Value"))
	if not info:
		rows.appendRow(("Target", "No changed parameter captured yet"))
		tracked = _tracked_operator(manager)
		if tracked is not None:
			rows.appendRow(("Tracking", tracked.path))
		return
	rows.appendRow(("Target", "{}.par.{}".format(info.get("owner", ""), info.get("name", ""))))
	rows.appendRow(("Label", info.get("label", "")))
	rows.appendRow(("Current", str(info.get("value", ""))))


def _build_output_rows(manager, rows):
	rows.clear()
	rows.appendRow(("Envelope Output", "expr_path"))
	for output in discover_outputs(manager):
		rows.appendRow((output["label"], output["path"]))


def _is_trackable_parameter(manager, par):
	try:
		if par.name in IGNORED_PARAMETER_NAMES:
			return False
		if not getattr(par, "label", ""):
			return False
		if par.owner.path.startswith(manager.ownerComp.path):
			return False
		if str(par.mode).lower().find("constant") == -1:
			return False
		value = par.eval()
		if isinstance(value, bool) or isinstance(value, str):
			return False
		float(value)
		return True
	except Exception:
		return False


def _selected_operator(manager):
	root = manager.ownerComp.parent()
	selected = []
	for child in root.children:
		try:
			if child != manager.ownerComp and child.selected:
				selected.append(child)
		except Exception:
			pass
	return selected[-1] if selected else None


def _tracked_operator(manager):
	callbacks = manager.ownerComp.op("parameter_tracker_callbacks")
	if callbacks is None:
		return None
	path = callbacks.fetch("target_path", "")
	if not path:
		try:
			operator = callbacks.par.fromop.eval()
			path = operator.path if operator is not None else ""
		except Exception:
			path = ""
	return _op(manager, path) if path else None


def _poll_parameter_snapshot(manager, target):
	current = _numeric_parameter_values(manager, target)
	previous = dict(manager.ownerComp.fetch("parameter_tracker_snapshot", {}))
	if previous.get("target") == target.path:
		old_values = previous.get("values", {})
		for name, value in current.items():
			if name in old_values and old_values[name] != value:
				par = target.par[name]
				if par is not None:
					record_parameter_change(manager, par, old_values[name])
	_store_snapshot_values(manager, target, current)


def _store_parameter_snapshot(manager, target):
	_store_snapshot_values(manager, target, _numeric_parameter_values(manager, target))


def _store_snapshot_values(manager, target, values):
	manager.ownerComp.store("parameter_tracker_snapshot", {
		"target": target.path,
		"values": values,
		"time": time.time(),
	})


def _numeric_parameter_values(manager, target):
	values = {}
	for par in target.pars():
		if _is_trackable_parameter(manager, par):
			try:
				values[par.name] = float(par.eval())
			except Exception:
				pass
	return values


def _set_expression_mode(manager, par):
	try:
		par.mode = manager._td_environment()["ParMode"].EXPRESSION
		return
	except Exception:
		pass
	try:
		par.mode = "EXPRESSION"
	except Exception:
		pass


def _tracker_execute(manager):
	dat = manager.ownerComp.op("parameter_tracker_update")
	if dat is None:
		dat = manager.ownerComp.create(td.executeDAT, "parameter_tracker_update")
	dat.par.active = True
	dat.par.framestart = True
	dat.par.language = "python"
	dat.text = (
		"def onFrameStart(frame):\n"
		"\tif frame % 10 == 0:\n"
		"\t\tparent().ext.AbletonHookupManagerExt.UpdateParameterTracker()\n"
		"\treturn\n"
	)
	return dat


def _tracker_callbacks(manager):
	dat = manager.ownerComp.op("parameter_tracker_callbacks")
	if dat is None:
		dat = manager.ownerComp.create(td.parameterexecuteDAT, "parameter_tracker_callbacks")
	for name, value in (
		("valuechange", True),
		("valueschanged", False),
		("onpulse", False),
		("expressionchange", False),
		("modechange", False),
		("custom", True),
		("builtin", True),
	):
		try:
			dat.par[name] = value
		except Exception:
			pass
	dat.par.language = "python"
	dat.text = (
		"def onValueChange(par, prev):\n"
		"\tparent().ext.AbletonHookupManagerExt.RecordParameterChange(par, prev)\n"
		"\treturn\n"
	)
	return dat


def _panel(manager):
	panel = manager.ownerComp.op("parameter_bind_panel")
	if panel is None:
		panel = manager.ownerComp.create(td.containerCOMP, "parameter_bind_panel")
	panel.store("manager_path", manager.ownerComp.path)
	panel.par.w = WIDTH
	panel.par.h = HEIGHT
	return panel


def _rows(panel, name, header):
	rows = panel.op(name)
	if rows is None:
		rows = panel.create(td.tableDAT, name)
	if rows.numRows == 0:
		rows.appendRow(header)
	return rows


def _info_list(panel):
	return _list(panel, "parameter_bind_info_list", "parameter_bind_info_rows", 0, INFO_H, 2, _info_callbacks())


def _output_list(panel):
	return _list(panel, "parameter_bind_output_list", "parameter_bind_output_rows", INFO_H, HEIGHT - INFO_H, 2, _output_callbacks())


def _list(panel, name, rows_name, y, height, cols, callbacks_text):
	list_comp = panel.op(name)
	if list_comp is None:
		list_comp = panel.create(td.listCOMP, name)
	list_comp.par.x = 0
	list_comp.par.y = y
	list_comp.par.w = WIDTH
	list_comp.par.h = height
	list_comp.par.rows = max(1, height // ROW_H)
	list_comp.par.cols = cols
	callbacks = panel.op(name + "_callbacks")
	if callbacks is None:
		callbacks = panel.create(td.textDAT, name + "_callbacks")
	callbacks.par.language = "python"
	callbacks.text = callbacks_text
	list_comp.par.callbacks = callbacks.path
	list_comp.store("rows_name", rows_name)
	return list_comp


def _window(manager, panel):
	window = manager.ownerComp.op("parameter_bind_window")
	if window is None:
		window = manager.ownerComp.create(td.windowCOMP, "parameter_bind_window")
	_set(window, "winop", panel.path)
	_set(window, "title", "Bind Parameter")
	_set(window, "size", "custom")
	_set(window, "winw", WIDTH)
	_set(window, "winh", HEIGHT)
	_set(window, "borders", True)
	_set(window, "alwaysontop", True)
	_set(window, "closeescape", True)
	_set(window, "interact", True)
	_set(window, "justifyh", "center")
	_set(window, "justifyv", "center")
	_set(window, "includedialog", False)
	return window


def _set(operator, name, value):
	par = operator.par[name]
	if par is None:
		return False
	try:
		par.val = value
		return True
	except Exception:
		pass
	for values in (getattr(par, "menuNames", None) or [], getattr(par, "menuLabels", None) or []):
		for index, item in enumerate(values):
			if str(item).lower() == str(value).lower():
				try:
					par.menuIndex = index
					return True
				except Exception:
					pass
	return False


def _reset(panel, name):
	list_comp = panel.op(name)
	if list_comp is not None:
		try:
			list_comp.par.reset.pulse()
		except Exception:
			pass


def _close_window(manager):
	window = manager.ownerComp.op("parameter_bind_window")
	if window is not None:
		try:
			window.par.winclose.pulse()
		except Exception:
			pass


def _op(manager, path):
	try:
		return manager._td_environment()["op"](str(path))
	except Exception:
		return None


def _is_chop(operator):
	try:
		return operator.isCHOP
	except Exception:
		return False


def _safe_eval(par):
	try:
		return par.eval()
	except Exception:
		return ""


def _tail(path):
	return str(path).rstrip("/").split("/")[-1]


def _info_callbacks():
	return r'''
def onInitCell(comp, row, col, attribs):
	dat = parent().op(comp.fetch('rows_name', ''))
	text = dat[row, col].val if dat and row < dat.numRows and col < dat.numCols else ''
	attribs.text = text
	attribs.rowHeight = 28
	attribs.colWidth = 130 if col == 0 else 620
	attribs.textOffsetX = 10
	attribs.textJustify = JustifyType.CENTERLEFT
	if row == 0:
		attribs.fontBold = True
		attribs.bgColor = (0.11, 0.12, 0.15, 1)
	else:
		attribs.bgColor = (0.16, 0.17, 0.20, 1)
	attribs.textColor = (0.86, 0.88, 0.92, 1)
	return
'''


def _output_callbacks():
	return r'''
def onInitCell(comp, row, col, attribs):
	dat = parent().op(comp.fetch('rows_name', ''))
	text = dat[row, col].val if dat and row < dat.numRows and col < dat.numCols else ''
	attribs.text = text
	attribs.rowHeight = 30
	attribs.colWidth = 760 if col == 0 else 0
	attribs.textOffsetX = 10
	attribs.textJustify = JustifyType.CENTERLEFT
	if row == 0:
		attribs.fontBold = True
		attribs.bgColor = (0.11, 0.12, 0.15, 1)
	else:
		attribs.bgColor = (0.18, 0.19, 0.22, 1)
	attribs.textColor = (0.88, 0.90, 0.94, 1)
	return


def onSelect(comp, startRow, startCol, startCoords, endRow, endCol, endCoords, start, end):
	if not end or endRow < 1:
		return
	dat = parent().op(comp.fetch('rows_name', ''))
	if not dat or endRow >= dat.numRows or dat.numCols < 2:
		return
	path = dat[endRow, 1].val if dat[endRow, 1] is not None else ''
	manager = op(parent().fetch('manager_path', ''))
	if manager and path:
		manager.ext.AbletonHookupManagerExt.ApplyParameterBinding(path)
	return
'''

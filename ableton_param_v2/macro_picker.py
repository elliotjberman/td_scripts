import td


TRACK_NAME = "Global"
DEVICE_NAME = "Live_Macro"
MANUAL_KEY = "__manual__"
ROW_HEIGHT = 34
MIN_ROWS = 3
MAX_ROWS = 14
WIDTH = 520


def ensure_picker(manager):
	panel = _panel(manager)
	_rows_dat(panel)
	_list(panel)
	_window(manager, panel)
	return panel


def open_picker(manager):
	panel = ensure_picker(manager)
	rows = _rows_dat(panel)
	rows.clear()
	rows.appendRow(("Parameter", "Source"))
	for row in _macro_rows(manager):
		rows.appendRow(row)
	rows.appendRow(("Empty / manual binding", MANUAL_KEY))
	row_count = min(MAX_ROWS, max(MIN_ROWS, rows.numRows))
	height = 58 + row_count * ROW_HEIGHT
	panel.par.w = WIDTH
	panel.par.h = height
	list_comp = panel.op("ableton_param_list")
	list_comp.par.rows = row_count
	list_comp.par.cols = 2
	list_comp.par.w = WIDTH
	list_comp.par.h = height
	try:
		list_comp.par.reset.pulse()
	except Exception:
		pass
	window = manager.ownerComp.op("ableton_param_picker_window")
	window.par.winw = WIDTH
	window.par.winh = height
	window.par.winopen.pulse()
	return panel


def close_picker(manager):
	window = manager.ownerComp.op("ableton_param_picker_window")
	if window is not None:
		window.par.winclose.pulse()


def select_parameter(manager, parameter_name):
	if parameter_name == MANUAL_KEY:
		source = manager.CreateAbletonParamSource("", "", "")
	else:
		source = manager.CreateAbletonParamSource(TRACK_NAME, DEVICE_NAME, parameter_name)
	close_picker(manager)
	return source


def picker_info(manager):
	parameters = global_macro_parameters(manager)
	return {
		"track_name": TRACK_NAME,
		"device_name": DEVICE_NAME,
		"parameters": parameters,
		"source_label": "{}/{}".format(TRACK_NAME, DEVICE_NAME),
		"manual_key": MANUAL_KEY,
	}


def global_macro_parameters(manager):
	td_ableton = op("/project1/tdAbleton")
	if td_ableton is None:
		return []
	try:
		song_info = td_ableton.ext.TDAbletonExt.SongInfo
	except Exception:
		return []
	global_track = None
	for key, data in song_info.get("tracks", {}).items():
		if str(data.get("name") or key).lower() == TRACK_NAME.lower():
			global_track = data
			break
	if not global_track:
		return []
	device = (global_track.get("devices", {}) or {}).get(DEVICE_NAME)
	if not device:
		return []
	parameters = device.get("aPars", {}) or device.get("parameters", {}) or {}
	return [str(value.get("name") or key) for key, value in parameters.items() if _is_macro_parameter(key, value)]


def _macro_rows(manager):
	return [(name, "{}/{}".format(TRACK_NAME, DEVICE_NAME)) for name in global_macro_parameters(manager)]


def _is_macro_parameter(key, value):
	name = str(value.get("name") or key)
	if name in ("Device On", "Chain Selector"):
		return False
	return bool(name)


def _panel(manager):
	panel = manager.ownerComp.op("ableton_param_picker_panel")
	if panel is None:
		panel = manager.ownerComp.create(td.containerCOMP, "ableton_param_picker_panel")
	panel.store("manager_path", manager.ownerComp.path)
	panel.tags.add("ableton-hookup-modal")
	panel.par.w = WIDTH
	panel.par.h = 160
	return panel


def _rows_dat(panel):
	rows = panel.op("ableton_param_picker_rows")
	if rows is None:
		rows = panel.create(td.tableDAT, "ableton_param_picker_rows")
	if rows.numRows == 0:
		rows.appendRow(("Parameter", "Source"))
	return rows


def _list(panel):
	list_comp = panel.op("ableton_param_list")
	if list_comp is None:
		list_comp = panel.create(td.listCOMP, "ableton_param_list")
	list_comp.par.x = 0
	list_comp.par.y = 0
	list_comp.par.w = WIDTH
	list_comp.par.h = 160
	list_comp.par.rows = 4
	list_comp.par.cols = 2
	callbacks = panel.op("ableton_param_list_callbacks")
	if callbacks is None:
		callbacks = panel.create(td.textDAT, "ableton_param_list_callbacks")
	callbacks.par.language = "python"
	callbacks.text = _callbacks_text()
	list_comp.par.callbacks = callbacks.path
	return list_comp


def _window(manager, panel):
	window = manager.ownerComp.op("ableton_param_picker_window")
	if window is None:
		window = manager.ownerComp.create(td.windowCOMP, "ableton_param_picker_window")
	_set(window, "winop", panel.path)
	_set(window, "title", "Ableton Param Source")
	_set(window, "size", "custom")
	_set(window, "winw", WIDTH)
	_set(window, "winh", 160)
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
		return
	try:
		par.val = value
	except Exception:
		pass


def _callbacks_text():
	return (
		"def onInitCell(comp, row, col, attribs):\n"
		"\tdat = parent().op('ableton_param_picker_rows')\n"
		"\ttext = dat[row, col].val if dat and row < dat.numRows and col < dat.numCols else ''\n"
		"\tattribs.text = text if text != '__manual__' else 'manual'\n"
		"\tattribs.rowHeight = 34\n"
		"\tattribs.colWidth = 330 if col == 0 else 190\n"
		"\tattribs.textOffsetX = 12\n"
		"\tattribs.textJustify = JustifyType.CENTERLEFT\n"
		"\tif row == 0:\n"
		"\t\tattribs.fontBold = True\n"
		"\t\tattribs.bgColor = (0.12, 0.13, 0.16, 1)\n"
		"\telse:\n"
		"\t\tattribs.bgColor = (0.18, 0.19, 0.22, 1)\n"
		"\t\tattribs.textColor = (0.88, 0.90, 0.94, 1)\n"
		"\treturn\n\n"
		"def onSelect(comp, startRow, startCol, startCoords, endRow, endCol, endCoords, start, end):\n"
		"\tif not end or endRow < 1:\n"
		"\t\treturn\n"
		"\tdat = parent().op('ableton_param_picker_rows')\n"
		"\tif not dat or endRow >= dat.numRows:\n"
		"\t\treturn\n"
		"\tmanager = op(parent().fetch('manager_path', ''))\n"
		"\tif manager:\n"
		"\t\tmanager.ext.AbletonHookupManagerExt.SelectAbletonParam(dat[endRow, 0].val if dat[endRow, 1].val != '__manual__' else '__manual__')\n"
		"\treturn\n"
	)

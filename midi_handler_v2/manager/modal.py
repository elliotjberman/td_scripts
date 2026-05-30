import td


MIN_ROWS = 2
MAX_ROWS = 12
ROW_HEIGHT = 34
WIDTH = 420


def ensure_source_picker(manager):
	panel = _panel(manager)
	_rows_dat(panel)
	_remove_note_activity_ops(panel)
	_list(panel)
	_window(manager, panel)
	return panel


def open_source_picker(manager, info):
	panel = ensure_source_picker(manager)
	rows = _rows_dat(panel)
	rows.clear()
	rows.appendRow(("Track", "Status"))
	for track, status in _ordered_tracks(info):
		rows.appendRow((track, status))
	row_count = min(MAX_ROWS, max(MIN_ROWS, len(info["tracks"])))
	height = 58 + row_count * ROW_HEIGHT
	panel.par.w = WIDTH
	panel.par.h = height
	list_comp = panel.op("source_list")
	list_comp.par.rows = max(MIN_ROWS + 1, min(MAX_ROWS + 1, len(info["tracks"]) + 1))
	list_comp.par.cols = 2
	list_comp.par.w = WIDTH
	list_comp.par.h = height
	list_comp.par.x = 0
	list_comp.par.y = 0
	try:
		list_comp.par.reset.pulse()
	except Exception:
		pass
	window = manager.ownerComp.op("source_picker_window")
	window.par.winw = WIDTH
	window.par.winh = height
	window.par.winopen.pulse()
	return panel


def update_source_picker_activity(manager):
	return None


def close_source_picker(manager):
	window = manager.ownerComp.op("source_picker_window")
	if window is not None:
		window.par.winclose.pulse()


def _panel(manager):
	panel = manager.ownerComp.op("source_picker_panel")
	if panel is None:
		panel = manager.ownerComp.create(td.containerCOMP, "source_picker_panel")
	panel.store("manager_path", manager.ownerComp.path)
	panel.tags.add("ableton-hookup-modal")
	panel.par.w = WIDTH
	panel.par.h = 126
	return panel


def _rows_dat(panel):
	rows = panel.op("source_picker_rows")
	if rows is None:
		rows = panel.create(td.tableDAT, "source_picker_rows")
	if rows.numRows == 0:
		rows.appendRow(("Track", "Status"))
	return rows


def _list(panel):
	list_comp = panel.op("source_list")
	if list_comp is None:
		list_comp = panel.create(td.listCOMP, "source_list")
	list_comp.par.x = 0
	list_comp.par.y = 0
	list_comp.par.w = WIDTH
	list_comp.par.h = 126
	list_comp.par.rows = 3
	list_comp.par.cols = 2
	callbacks = panel.op("source_list_callbacks")
	if callbacks is None:
		callbacks = panel.create(td.textDAT, "source_list_callbacks")
	callbacks.par.language = "python"
	callbacks.text = _callbacks_text()
	list_comp.par.callbacks = callbacks.path
	return list_comp


def _window(manager, panel):
	window = manager.ownerComp.op("source_picker_window")
	if window is None:
		window = manager.ownerComp.create(td.windowCOMP, "source_picker_window")
	_set(window, "winop", panel.path)
	_set(window, "title", "Ableton MIDI Source")
	_set(window, "size", "custom")
	_set(window, "winw", WIDTH)
	_set(window, "winh", 126)
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
	for values in (getattr(par, "menuNames", []), getattr(par, "menuLabels", [])):
		for index, item in enumerate(values):
			if str(item).lower() == str(value).lower():
				par.menuIndex = index
				return True
	return False


def _ordered_tracks(info):
	selected = set(info["selected_tracks"])
	available = [(track, "available") for track in info["tracks"] if track not in selected]
	added = [(track, "added") for track in info["tracks"] if track in selected]
	return available + added


def _remove_note_activity_ops(panel):
	for name in (
		"note_activity_list",
		"note_activity_rows",
		"note_activity_execute",
		"note_activity_callbacks",
		"note_activity_list_callbacks",
	):
		child = panel.op(name)
		if child is not None:
			try:
				child.destroy()
			except Exception:
				pass


def _callbacks_text():
	return (
		"def onInitCell(comp, row, col, attribs):\n"
		"\tdat = parent().op('source_picker_rows')\n"
		"\ttext = dat[row, col].val if dat and row < dat.numRows and col < dat.numCols else ''\n"
		"\tattribs.text = text\n"
		"\tattribs.rowHeight = 34\n"
		"\tattribs.colWidth = 300 if col == 0 else 120\n"
		"\tattribs.textOffsetX = 12\n"
		"\tattribs.textJustify = JustifyType.CENTERLEFT\n"
		"\tif row == 0:\n"
		"\t\tattribs.fontBold = True\n"
		"\t\tattribs.bgColor = (0.12, 0.13, 0.16, 1)\n"
		"\telif dat and dat[row, 1].val == 'added':\n"
		"\t\tattribs.bgColor = (0.10, 0.10, 0.10, 1)\n"
		"\t\tattribs.textColor = (0.45, 0.45, 0.45, 1)\n"
		"\telse:\n"
		"\t\tattribs.bgColor = (0.18, 0.19, 0.22, 1)\n"
		"\t\tattribs.textColor = (0.88, 0.90, 0.94, 1)\n"
		"\treturn\n\n"
		"def onSelect(comp, startRow, startCol, startCoords, endRow, endCol, endCoords, start, end):\n"
		"\tif not end or endRow < 1:\n"
		"\t\treturn\n"
		"\tdat = parent().op('source_picker_rows')\n"
		"\tif not dat or endRow >= dat.numRows or dat[endRow, 1].val != 'available':\n"
		"\t\treturn\n"
		"\tmanager = op(parent().fetch('manager_path', ''))\n"
		"\tif manager:\n"
		"\t\tmanager.ext.AbletonHookupManagerExt.SelectSourceTrack(dat[endRow, 0].val)\n"
		"\treturn\n"
	)


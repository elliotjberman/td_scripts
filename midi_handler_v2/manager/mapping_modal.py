import time

import td


WIDTH = 820
HEIGHT = 430
NOTE_W = 300
TARGET_W = WIDTH - NOTE_W
ROW_H = 30
MAX_ROWS = 13
FLASH_SECONDS = 0.12
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
ABLETON_OCTAVE_OFFSET = -2


def ensure_mapping_editor(manager):
	panel = _panel(manager)
	_rows(panel, "mapping_note_rows", ("Note", "Vel", "Routes", "key", "last_seen"))
	_rows(panel, "mapping_target_rows", ("Envelope", "Mapped", "Go", "path"))
	_note_list(panel)
	_target_list(panel)
	_updater(panel)
	_window(manager, panel)
	return panel


def open_mapping_editor(manager, source=None):
	source = _resolve_source(manager, source)
	if source is None:
		return None
	panel = ensure_mapping_editor(manager)
	panel.store("source_path", source.path)
	panel.store("selected_note", panel.fetch("selected_note", "*") or "*")
	panel.store("targets_dirty", True)
	refresh_mapping_editor(manager)
	updater = panel.op("mapping_editor_update")
	if updater is not None:
		updater.par.active = True
	window = manager.ownerComp.op("mapping_editor_window")
	window.par.winopen.pulse()
	return source


def close_mapping_editor(manager):
	panel = manager.ownerComp.op("mapping_editor_panel")
	if panel is not None:
		updater = panel.op("mapping_editor_update")
		if updater is not None:
			updater.par.active = False
	window = manager.ownerComp.op("mapping_editor_window")
	if window is not None:
		window.par.winclose.pulse()


def select_note(manager, note_key):
	panel = ensure_mapping_editor(manager)
	panel.store("selected_note", str(note_key or "*"))
	panel.store("targets_dirty", True)
	refresh_mapping_editor(manager)


def toggle_target(manager, target_path):
	panel = ensure_mapping_editor(manager)
	source = _op(manager, panel.fetch("source_path", ""))
	target_path = str(target_path or "")
	if source is None or not target_path:
		return False
	note_key = str(panel.fetch("selected_note", "*") or "*")
	ext = source.ext.AbletonMidiSourceExt
	if _has_mapping(ext, note_key, target_path):
		ext.RemoveMapping(note_key, target_path)
	else:
		ext.AddMapping(note_key, target_path)
	panel.store("targets_dirty", True)
	refresh_mapping_editor(manager)
	return True


def go_to_target(manager, target_path):
	target = _op(manager, target_path)
	if target is None:
		return False
	try:
		for child in target.parent().children:
			child.selected = False
	except Exception:
		pass
	try:
		target.selected = True
		target.current = True
	except Exception:
		pass
	try:
		target.openParameters()
	except Exception:
		pass
	return True


def refresh_mapping_editor(manager):
	panel = manager.ownerComp.op("mapping_editor_panel")
	if panel is None:
		return
	source = _op(manager, panel.fetch("source_path", ""))
	if source is None:
		return
	note_rows = panel.op("mapping_note_rows")
	target_rows = panel.op("mapping_target_rows")
	_build_note_rows(source, note_rows, panel)
	_resize_lists(panel)
	_reset_list(panel, "mapping_note_list")
	if panel.fetch("targets_dirty", True):
		_build_target_rows(source, target_rows, panel)
		_resize_lists(panel)
		_reset_list(panel, "mapping_target_list")
		panel.store("targets_dirty", False)


def _reset_list(panel, name):
	list_comp = panel.op(name)
	if list_comp is not None:
		try:
			list_comp.par.reset.pulse()
		except Exception:
			pass


def _build_note_rows(source, rows, panel):
	activity = _activity(source)
	data = source.ext.AbletonMidiSourceExt.MappingData()
	mappings = data.get("mappings", {})
	keys = {"*"}
	keys.update(key for key, entries in mappings.items() if entries)
	keys.update(activity.keys())
	note_keys = sorted([key for key in keys if _is_int(key)], key=lambda item: int(item))
	ordered = ["*"] + note_keys + sorted(key for key in keys if key not in {"*"} and not _is_int(key))
	selected = str(panel.fetch("selected_note", "*") or "*")
	if selected not in ordered:
		selected = "*"
		panel.store("selected_note", selected)
		panel.store("targets_dirty", True)
	rows.clear()
	rows.appendRow(("Note", "Vel", "Routes", "key", "last_seen"))
	for key in ordered:
		vel, last_seen = activity.get(key, ("", "0"))
		count = len(mappings.get(key, []))
		label = "*" if key == "*" else _note_label(key)
		rows.appendRow((label, vel, str(count), key, last_seen))


def _build_target_rows(source, rows, panel):
	note_key = str(panel.fetch("selected_note", "*") or "*")
	mapped = _mapped_paths(source.ext.AbletonMidiSourceExt, note_key)
	targets = source.ext.AbletonMidiSourceExt.DiscoverTargets()
	targets.sort(key=lambda item: (item.get("path", "") not in mapped, item.get("label", "")))
	rows.clear()
	rows.appendRow(("Envelope", "Mapped", "Go", "path"))
	for target in targets:
		path = target.get("path", "")
		status = "yes" if path in mapped else "no"
		rows.appendRow((target.get("label", path), status, "go", path))


def _resize_lists(panel):
	note_rows = panel.op("mapping_note_rows")
	target_rows = panel.op("mapping_target_rows")
	note_count = note_rows.numRows if note_rows is not None else 1
	target_count = target_rows.numRows if target_rows is not None else 1
	content_rows = max(MAX_ROWS, note_count, target_count)
	content_height = max(HEIGHT, content_rows * ROW_H)
	panel.par.h = content_height
	_apply_list_size(panel.op("mapping_note_list"), NOTE_W, note_count, content_height)
	_apply_list_size(panel.op("mapping_target_list"), TARGET_W, target_count, content_height)


def _apply_list_size(list_comp, width, row_count, height):
	if list_comp is None:
		return
	list_comp.par.w = width
	list_comp.par.h = height
	list_comp.par.rows = max(1, row_count)


def _activity(source):
	table = source.op("note_activity")
	result = {}
	if table is None:
		return result
	for row in range(1, table.numRows):
		key = table[row, 0].val
		if key:
			result[str(key)] = (table[row, 1].val, table[row, 2].val)
	return result


def _has_mapping(ext, note_key, target_path):
	return target_path in _mapped_paths(ext, note_key)


def _mapped_paths(ext, note_key):
	entries = ext.MappingData().get("mappings", {}).get(str(note_key), [])
	return {entry.get("target", "") for entry in entries}


def _resolve_source(manager, source):
	if source is not None:
		if hasattr(source, "path"):
			return source
		found = _op(manager, str(source))
		if found is not None:
			return found
	root = manager.ownerComp.parent()
	sources = [child for child in root.children if _is_source(child)]
	for source in sources:
		try:
			if source.selected:
				return source
		except Exception:
			pass
	return sources[0] if sources else None


def _is_source(operator):
	try:
		return "ableton-midi-source-v2" in operator.tags or operator.op("abletonMIDI") is not None
	except Exception:
		return False


def _op(manager, path):
	try:
		return manager._td_environment()["op"](str(path))
	except Exception:
		return None


def _is_int(value):
	try:
		int(value)
		return True
	except Exception:
		return False


def _note_label(value):
	try:
		note = int(value)
	except Exception:
		return str(value)
	name = NOTE_NAMES[note % 12]
	octave = note // 12 + ABLETON_OCTAVE_OFFSET
	return "{}  {}".format(note, name + str(octave))


def _panel(manager):
	panel = manager.ownerComp.op("mapping_editor_panel")
	if panel is None:
		panel = manager.ownerComp.create(td.containerCOMP, "mapping_editor_panel")
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


def _note_list(panel):
	return _list(panel, "mapping_note_list", "mapping_note_rows", 0, NOTE_W, 3, _note_callbacks_text())


def _target_list(panel):
	return _list(panel, "mapping_target_list", "mapping_target_rows", NOTE_W, TARGET_W, 3, _target_callbacks_text())


def _list(panel, name, rows_name, x, width, cols, callbacks_text):
	list_comp = panel.op(name)
	if list_comp is None:
		list_comp = panel.create(td.listCOMP, name)
	list_comp.par.x = x
	list_comp.par.y = 0
	list_comp.par.w = width
	list_comp.par.h = HEIGHT
	list_comp.par.rows = MAX_ROWS
	list_comp.par.cols = cols
	callbacks = panel.op(name + "_callbacks")
	if callbacks is None:
		callbacks = panel.create(td.textDAT, name + "_callbacks")
	callbacks.par.language = "python"
	callbacks.text = callbacks_text
	list_comp.par.callbacks = callbacks.path
	list_comp.store("rows_name", rows_name)
	return list_comp


def _updater(panel):
	execute = panel.op("mapping_editor_update")
	if execute is None:
		execute = panel.create(td.executeDAT, "mapping_editor_update")
		execute.par.active = False
	execute.par.framestart = True
	execute.par.language = "python"
	execute.text = (
		"def onFrameStart(frame):\n"
		"\tmanager = op(parent().fetch('manager_path', ''))\n"
		"\twindow = manager.op('mapping_editor_window') if manager else None\n"
		"\tif window is not None and not window.isOpen:\n"
		"\t\tme.par.active = False\n"
		"\t\treturn\n"
		"\tif manager:\n"
		"\t\tmanager.ext.AbletonHookupManagerExt.RefreshMappingEditor()\n"
		"\treturn\n"
	)
	return execute


def _window(manager, panel):
	window = manager.ownerComp.op("mapping_editor_window")
	if window is None:
		window = manager.ownerComp.create(td.windowCOMP, "mapping_editor_window")
	_set(window, "winop", panel.path)
	_set(window, "title", "MIDI Note Mapping")
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


def _note_callbacks_text():
	return r'''
import time


def onInitCell(comp, row, col, attribs):
	dat = parent().op(comp.fetch('rows_name', ''))
	text = dat[row, col].val if dat and row < dat.numRows and col < dat.numCols else ''
	attribs.text = text
	attribs.rowHeight = 30
	attribs.colWidth = (105, 75, 90)[col] if col < 3 else 80
	attribs.textOffsetX = 10
	attribs.textJustify = JustifyType.CENTERLEFT
	if row == 0:
		attribs.fontBold = True
		attribs.bgColor = (0.11, 0.12, 0.15, 1)
		attribs.textColor = (0.86, 0.88, 0.92, 1)
		return
	key = dat[row, 3].val if dat and row < dat.numRows else ''
	selected = str(parent().fetch('selected_note', '*'))
	route_count = _int(dat[row, 2].val) if dat and row < dat.numRows else 0
	flash = _flash(dat[row, 4].val if dat and row < dat.numRows else '0')
	if key == selected:
		base = (0.24, 0.27, 0.34, 1)
	elif route_count:
		base = (0.15, 0.22, 0.18, 1)
	elif key == '*':
		base = (0.18, 0.17, 0.22, 1)
	else:
		base = (0.16, 0.17, 0.20, 1)
	if flash > 0:
		attribs.bgColor = _mix(base, (0.46, 0.92, 0.64, 1), flash)
		attribs.textColor = (0.04, 0.08, 0.05, 1)
	else:
		attribs.bgColor = base
		attribs.textColor = (0.88, 0.90, 0.94, 1)
	return


def onSelect(comp, startRow, startCol, startCoords, endRow, endCol, endCoords, start, end):
	if not end or endRow < 1:
		return
	dat = parent().op(comp.fetch('rows_name', ''))
	if not dat or endRow >= dat.numRows:
		return
	manager = op(parent().fetch('manager_path', ''))
	if manager:
		manager.ext.AbletonHookupManagerExt.SelectMappingNote(dat[endRow, 3].val)
	return


def _flash(value):
	try:
		age = time.time() - float(value)
	except Exception:
		return 0
	if age < 0 or age > 0.12:
		return 0
	return 1 - (age / 0.12)


def _mix(a, b, amount):
	return tuple(a[i] * (1 - amount) + b[i] * amount for i in range(4))


def _int(value):
	try:
		return int(value)
	except Exception:
		return 0
'''


def _target_callbacks_text():
	return r'''
def onInitCell(comp, row, col, attribs):
	dat = parent().op(comp.fetch('rows_name', ''))
	text = dat[row, col].val if dat and row < dat.numRows and col < dat.numCols else ''
	mapped = dat[row, 1].val if dat and row < dat.numRows and dat.numCols > 1 and dat[row, 1] is not None else ''
	attribs.text = text
	attribs.rowHeight = 30
	attribs.colWidth = (340, 90, 70)[col] if col < 3 else 70
	attribs.textOffsetX = 10
	attribs.textJustify = JustifyType.CENTERLEFT
	if row == 0:
		attribs.fontBold = True
		attribs.bgColor = (0.11, 0.12, 0.15, 1)
		attribs.textColor = (0.86, 0.88, 0.92, 1)
	elif mapped == 'yes':
		attribs.bgColor = (0.18, 0.30, 0.20, 1)
		attribs.textColor = (0.92, 0.98, 0.92, 1)
	else:
		attribs.bgColor = (0.16, 0.17, 0.20, 1)
		attribs.textColor = (0.84, 0.86, 0.90, 1)
	return


def onSelect(comp, startRow, startCol, startCoords, endRow, endCol, endCoords, start, end):
	if not end or endRow < 1:
		return
	dat = parent().op(comp.fetch('rows_name', ''))
	if not dat or endRow >= dat.numRows or dat.numCols < 4:
		return
	target_path = dat[endRow, 3].val if dat[endRow, 3] is not None else ''
	if not target_path:
		return
	manager = op(parent().fetch('manager_path', ''))
	if manager:
		if endCol == 2:
			manager.ext.AbletonHookupManagerExt.GoToMappingTarget(target_path)
		else:
			manager.ext.AbletonHookupManagerExt.ToggleMappingTarget(target_path)
	return
'''

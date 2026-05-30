import ctypes

import td


WIDTH = 420
HEIGHT = 86
ROW_H = 43
LABEL_W = 116
VALUE_W = WIDTH - LABEL_W
WINDOW_TITLE = "Scaled Envelope"


def ensure_envelope_name_prompt(manager):
	panel = _panel(manager)
	_remove_old_list_prompt(panel)
	_label(panel, "name_label", "Name", 0, ROW_H)
	_input(panel)
	_label(panel, "creates_label", "Creates", 0, 0)
	_preview(panel)
	_updater(panel)
	_window(manager, panel)
	return panel


def open_envelope_name_prompt(manager, default_name=""):
	panel = ensure_envelope_name_prompt(manager)
	panel.store("input_active", True)
	_input(panel).par.text = default_name or ""
	update_envelope_name_prompt(manager)
	window = manager.ownerComp.op("envelope_name_window")
	window.par.winw = WIDTH
	window.par.winh = HEIGHT
	window.par.winopen.pulse()
	focus_envelope_name_prompt(manager)
	try:
		manager._td_environment()["run"](
			"op('{}').ext.AbletonHookupManagerExt.FocusEnvelopeNamePrompt()".format(manager.ownerComp.path),
			delayFrames=2,
		)
	except Exception:
		pass
	return panel


def close_envelope_name_prompt(manager):
	panel = manager.ownerComp.op("envelope_name_panel")
	if panel is not None:
		panel.store("input_active", False)
	window = manager.ownerComp.op("envelope_name_window")
	if window is not None:
		window.par.winclose.pulse()


def focus_envelope_name_prompt(manager):
	panel = manager.ownerComp.op("envelope_name_panel")
	if panel is None or not panel.fetch("input_active", False):
		return False
	field = _input(panel)
	_activate_window(WINDOW_TITLE)
	try:
		field.setFocus()
	except Exception:
		pass
	try:
		field.setKeyboardFocus()
	except Exception:
		pass
	return True


def update_envelope_name_prompt(manager):
	panel = manager.ownerComp.op("envelope_name_panel")
	if panel is None:
		return
	value = _current_value(panel)
	panel.store("input_value", value)
	preview = "{}_envelope".format(_preview_name(value)) if value.strip() else "scaled envelope"
	_preview(panel).par.text = preview


def handle_key(manager, key, character, alt, ctrl, shift, state, cmd=False):
	panel = manager.ownerComp.op("envelope_name_panel")
	if panel is None or not panel.fetch("input_active", False) or not state:
		return False
	key_text = str(key or "").lower()
	if key_text in ("escape", "esc"):
		close_envelope_name_prompt(manager)
		return True
	if key_text in ("enter", "return"):
		value = _current_value(panel)
		close_envelope_name_prompt(manager)
		manager.CreateScaledEnvelopeFromName(value)
		return True
	return True


def _panel(manager):
	panel = manager.ownerComp.op("envelope_name_panel")
	if panel is None:
		panel = manager.ownerComp.create(td.containerCOMP, "envelope_name_panel")
	panel.store("manager_path", manager.ownerComp.path)
	panel.tags.add("ableton-hookup-modal")
	panel.par.w = WIDTH
	panel.par.h = HEIGHT
	return panel


def _label(panel, name, text, x, y):
	comp = panel.op(name)
	if comp is None:
		comp = panel.create(td.textCOMP, name)
	comp.par.x = x
	comp.par.y = y
	comp.par.w = LABEL_W
	comp.par.h = ROW_H
	comp.par.text = text
	_set(comp, "type", "string")
	_set(comp, "editmode", "locked")
	_style_text(comp, bg=(0.14, 0.15, 0.18, 1), fg=(0.82, 0.84, 0.88, 1))
	return comp


def _input(panel):
	comp = panel.op("name_input")
	if comp is None:
		comp = panel.create(td.textCOMP, "name_input")
	comp.par.x = LABEL_W
	comp.par.y = ROW_H
	comp.par.w = VALUE_W
	comp.par.h = ROW_H
	_set(comp, "type", "string")
	_set(comp, "editmode", "editablecontinuous")
	_set(comp, "allowuishortcuts", "off")
	if comp.par["fieldfocus"] is not None:
		comp.par.fieldfocus = 1
	if comp.par["placeholdertext"] is not None:
		comp.par.placeholdertext = "type name"
	_style_text(comp, bg=(0.20, 0.21, 0.24, 1), fg=(0.95, 0.96, 0.98, 1))
	return comp


def _preview(panel):
	comp = panel.op("creates_preview")
	if comp is None:
		comp = panel.create(td.textCOMP, "creates_preview")
	comp.par.x = LABEL_W
	comp.par.y = 0
	comp.par.w = VALUE_W
	comp.par.h = ROW_H
	_set(comp, "type", "string")
	_set(comp, "editmode", "locked")
	_style_text(comp, bg=(0.14, 0.15, 0.18, 1), fg=(0.82, 0.84, 0.88, 1))
	return comp


def _updater(panel):
	execute = panel.op("envelope_name_update")
	if execute is None:
		execute = panel.create(td.executeDAT, "envelope_name_update")
	execute.par.active = True
	execute.par.framestart = True
	execute.par.language = "python"
	execute.text = (
		"def onFrameStart(frame):\n"
		"\tmanager = op(parent().fetch('manager_path', ''))\n"
		"\tif manager and parent().fetch('input_active', False):\n"
		"\t\tmanager.ext.AbletonHookupManagerExt.UpdateEnvelopeNamePrompt()\n"
		"\treturn\n"
	)
	return execute


def _window(manager, panel):
	window = manager.ownerComp.op("envelope_name_window")
	if window is None:
		window = manager.ownerComp.create(td.windowCOMP, "envelope_name_window")
	_set(window, "winop", panel.path)
	_set(window, "title", WINDOW_TITLE)
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


def _activate_window(title):
	try:
		user32 = ctypes.windll.user32
		kernel32 = ctypes.windll.kernel32
	except Exception:
		return False
	hwnd = user32.FindWindowW(None, str(title))
	if not hwnd:
		return False
	current_thread = kernel32.GetCurrentThreadId()
	foreground = user32.GetForegroundWindow()
	threads = [
		user32.GetWindowThreadProcessId(hwnd, None),
		user32.GetWindowThreadProcessId(foreground, None) if foreground else 0,
	]
	attached = []
	for thread in threads:
		if thread and thread != current_thread:
			try:
				if user32.AttachThreadInput(current_thread, thread, True):
					attached.append(thread)
			except Exception:
				pass
	try:
		user32.ShowWindow(hwnd, 5)
		user32.BringWindowToTop(hwnd)
		user32.SetForegroundWindow(hwnd)
		user32.SetActiveWindow(hwnd)
		user32.SetFocus(hwnd)
		return True
	except Exception:
		return False
	finally:
		for thread in attached:
			try:
				user32.AttachThreadInput(current_thread, thread, False)
			except Exception:
				pass


def _style_text(comp, bg, fg):
	_set(comp, "alignx", "left")
	_set(comp, "aligny", "center")
	if comp.par["font"] is not None:
		_set(comp, "font", "Cascadia Mono")
	if comp.par["fontsize"] is not None:
		comp.par.fontsize = 15
	_set_color(comp, "bgcolor", bg)
	_set_color(comp, "fontcolor", fg)


def _set_color(comp, base, color):
	names = ("r", "g", "b", "a")
	for index, suffix in enumerate(names):
		par = comp.par[base + suffix]
		if par is not None:
			par.val = color[index]


def _set(operator, name, value):
	par = operator.par[name]
	if par is None:
		return False
	for values in (getattr(par, "menuNames", None) or [], getattr(par, "menuLabels", None) or []):
		for index, item in enumerate(values):
			if str(item).lower() == str(value).lower():
				try:
					par.menuIndex = index
					return True
				except Exception:
					pass
	if str(value).lower() in ("off", "false", "0"):
		value = False
	elif str(value).lower() in ("on", "true", "1"):
		value = True
	try:
		par.val = value
		return True
	except Exception:
		pass
	return False


def _current_value(panel):
	field = panel.op("name_input")
	if field is None:
		return ""
	try:
		return str(field.par.text.eval())
	except Exception:
		return ""


def _preview_name(value):
	name = "_".join(str(value).strip().split()).lower()
	return name.replace("-", "_").strip("_") or "scaled"


def _remove_old_list_prompt(panel):
	for name in ("envelope_name_list", "envelope_name_rows", "envelope_name_callbacks", "envelope_name_list_callbacks"):
		child = panel.op(name)
		if child is not None:
			try:
				child.destroy()
			except Exception:
				pass

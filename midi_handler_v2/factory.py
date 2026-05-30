from pathlib import Path
import os
import re
import td


ABLETON_MIDI_TOX_RELATIVE = (
	"Derivative",
	"TouchDesigner",
	"Samples",
	"Palette",
	"TDAbleton",
	"Live 11+",
	"abletonMIDI.tox",
)


def create_source(manager_comp, track_name, add_device=True):
	"""Create a v2 self-contained Ableton MIDI source wrapper."""
	parent_comp = manager_comp.parent()
	home = _home(manager_comp)
	source_name = _source_name(track_name)
	source_id = "ableton_midi:" + source_name
	wrapper_name = source_name + "_source"

	wrapper = parent_comp.op(wrapper_name)
	if wrapper is None:
		wrapper = parent_comp.create(td.baseCOMP, wrapper_name)
	wrapper.tags.add("ableton-midi-source-v2")
	wrapper.store("source_id", source_id)
	wrapper.store("track_name", track_name)
	wrapper.store("home", home)

	_setup_extension(wrapper, home)
	ableton_midi = _ensure_ableton_midi(wrapper, source_name)
	if ableton_midi is None:
		return wrapper

	_set_parameter_value(ableton_midi, "Connect", False)
	_configure_ableton_midi(wrapper, ableton_midi, track_name, home)
	wrapper.ext.AbletonMidiSourceExt.Setup()
	_layout_source_wrapper(wrapper)
	if add_device or _source_has_tda_midi_device(track_name):
		_ensure_tda_midi_device(ableton_midi, track_name, add_if_missing=add_device)
		_ensure_device_setup_poller(wrapper, add_device)
	return wrapper


def _setup_extension(wrapper, home):
	ext_dat = wrapper.op("AbletonMidiSourceExt")
	if ext_dat is None:
		ext_dat = wrapper.create(td.textDAT, "AbletonMidiSourceExt")
	ext_dat.par.file.expr = _home_expr(home, "source_extension.py")
	ext_dat.par.syncfile = True
	ext_dat.par.loadonstartpulse.pulse()
	ext_dat.par.language = "python"
	wrapper.par.ext0object = "op('./AbletonMidiSourceExt').module.AbletonMidiSourceExt(me)"
	wrapper.par.ext0name = ""
	wrapper.par.ext0promote = True
	wrapper.par.reinitextensions.pulse()


def _ensure_ableton_midi(wrapper, source_name):
	existing = wrapper.op("abletonMIDI")
	if existing is not None:
		if _has_ableton_midi_pars(existing):
			return existing
		nested = _resolve_ableton_midi_operator(existing)
		if nested is not None:
			return _flatten_ableton_midi(wrapper, existing, nested)

	tox_path = _ableton_midi_tox_path()
	if tox_path is None:
		return None

	loaded = wrapper.loadTox(str(tox_path), unwired=True)
	ableton_midi = _resolve_ableton_midi_operator(loaded or wrapper)
	if ableton_midi is None:
		return None
	if ableton_midi.parent() != wrapper:
		ableton_midi = _flatten_ableton_midi(wrapper, loaded, ableton_midi)
	try:
		if ableton_midi.parent() == wrapper:
			ableton_midi.name = "abletonMIDI"
	except Exception:
		pass
	ableton_midi.tags.add("ableton-midi-source-v2-inner")
	return ableton_midi


def _flatten_ableton_midi(wrapper, container, inner):
	flat = wrapper.copy(inner, name="_abletonMIDI_flat")
	if container is not None and container.valid:
		container.destroy()
	flat.name = "abletonMIDI"
	return flat


def _configure_ableton_midi(wrapper, ableton_midi, track_name, home):
	source_id = wrapper.fetch("source_id")
	for op_ in (wrapper, ableton_midi):
		op_.store("source_id", source_id)
		op_.store("track_name", track_name)
		op_.store("source_wrapper_path", wrapper.path)
		op_.store("ableton_midi_operator_path", ableton_midi.path)
		op_.store("home", home)
	wrapper.store("midi_v2_allow_autoconnect", False)

	callback = wrapper.op("source_callback")
	if callback is None:
		callback = wrapper.create(td.textDAT, "source_callback")
	callback.par.file.expr = _home_expr(home, "source_callback.py")
	callback.par.syncfile = True
	callback.par.loadonstartpulse.pulse()
	callback.par.language = "python"

	_set_menu_parameter(ableton_midi, "Device", "None")
	_refresh_lom(ableton_midi)
	_set_menu_parameter(ableton_midi, "Track", track_name)
	_set_parameter_value(ableton_midi, "Callbackdat", callback)
	_set_parameter_value(ableton_midi, "Enablecallbacks", True)
	_remove_unused_callback_dats(wrapper, callback)


def _remove_unused_callback_dats(wrapper, active_callback):
	for child in list(wrapper.children):
		if child == active_callback or not child.isDAT:
			continue
		if child.name.startswith("abletonMIDI") and child.name.endswith("_callbacks"):
			child.destroy()


def _layout_source_wrapper(wrapper):
	positions = {
		"abletonMIDI": (0, 120),
		"last_note": (260, 120),
		"out1": (450, 120),
		"AbletonMidiSourceExt": (0, -60),
		"source_callback": (210, -60),
		"source_par_callbacks": (420, -60),
		"mappings_json": (0, -210),
		"recent_notes": (210, -210),
		"note_activity": (420, -210),
	}
	for name, position in positions.items():
		operator = wrapper.op(name)
		if operator is not None:
			operator.nodeX, operator.nodeY = position


def _ensure_tda_midi_device(ableton_midi, track_name, add_if_missing=True):
	if _source_has_tda_midi_device(track_name):
		_refresh_lom(ableton_midi)
		return _select_tda_midi_device(ableton_midi, track_name)
	if not add_if_missing:
		return False
	pulse = ableton_midi.par["Adddevice"]
	if pulse is not None:
		pulse.pulse()
	return False


def _ensure_device_setup_poller(wrapper, add_if_missing=True):
	poller = wrapper.op("device_setup")
	if poller is None:
		poller = wrapper.create(td.executeDAT, "device_setup")
	poller.par.active = True
	poller.par.framestart = True
	poller.par.language = "python"
	poller.text = _device_setup_poller_text()
	wrapper.store("tda_midi_setup_attempts", 0)
	wrapper.store("tda_midi_add_if_missing", bool(add_if_missing))
	wrapper.store("tda_midi_ready", False)


def _device_setup_poller_text():
	return r'''
def onFrameStart(frame):
	if frame % 10:
		return
	wrapper = parent()
	midi = wrapper.op('abletonMIDI')
	if midi is None:
		return
	attempts = wrapper.fetch('tda_midi_setup_attempts', 0) + 1
	wrapper.store('tda_midi_setup_attempts', attempts)
	track_name = wrapper.fetch('track_name', '')
	_set_bool(midi, 'Connect', False)
	_refresh_lom(midi, track_name)
	_set_menu(midi, 'Track', track_name)
	_refresh_lom(midi, track_name)
	if _set_menu(midi, 'Device', 'TdaMIDI'):
		_set_bool(midi, 'Enablecallbacks', True)
		_clear_errors(midi)
		try:
			midi.par.reinitextensions.pulse()
		except Exception:
			pass
		path = repr(midi.path)
		run("target = op({})\nif target:\n\ttarget.par.Connect = True".format(path), delayFrames=2)
		run("target = op({})\nif target:\n\ttarget.clearScriptErrors()".format(path), delayFrames=3)
		wrapper.store('tda_midi_ready', True)
		me.par.active = False
		return
	if wrapper.fetch('tda_midi_add_if_missing', True) and not wrapper.fetch('tda_midi_add_requested', False):
		pulse = midi.par['Adddevice']
		if pulse is not None:
			pulse.pulse()
		wrapper.store('tda_midi_add_requested', True)
	if attempts >= 120:
		wrapper.store('tda_midi_ready', False)
		me.par.active = False
	return


def _refresh_lom(midi, track_name):
	td_ableton = op('/project1/tdAbleton')
	try:
		td_ableton.ext.TDAbletonExt.Update()
	except Exception:
		pass
	try:
		ext = midi.ext.TDAbletonCompBaseExt
		ext.setTDAbletonComp()
		ext.onAbletonNotify({'notificationType': 'songInfo'})
		ext.updateLOMPars(setupListeners=False)
	except Exception:
		pass


def _set_menu(operator, name, label):
	par = operator.par[name]
	if par is None:
		return False
	labels = list(par.menuLabels or [])
	names = list(par.menuNames or [])
	for values in (labels, names):
		for index, value in enumerate(values):
			if str(value) == str(label):
				par.menuIndex = index
				return True
	return False


def _set_bool(operator, name, value):
	par = operator.par[name]
	if par is not None:
		par.val = bool(value)


def _clear_errors(operator):
	try:
		operator.clearScriptErrors()
	except Exception:
		pass
'''


def _select_tda_midi_device(ableton_midi, track_name):
	for device in _walk_track_devices(track_name):
		if "ID_TDA_MIDI" in device.get("aPars", {}):
			for value in (device.get("name"), device.get("ptr")):
				if value is not None and _set_menu_parameter(ableton_midi, "Device", str(value)):
					_refresh_lom(ableton_midi)
					return True
	return False


def _source_has_tda_midi_device(track_name):
	return any("ID_TDA_MIDI" in device.get("aPars", {}) for device in _walk_track_devices(track_name))


def _walk_track_devices(track_name):
	td_ableton = op("/project1/tdAbleton")
	if td_ableton is None:
		return []
	try:
		tracks = td_ableton.ext.TDAbletonExt.SongInfo.get("tracks", {})
	except Exception:
		return []
	track = tracks.get(track_name)
	if not track:
		for item in tracks.values():
			if str(item.get("name", "")).lower() == track_name.lower():
				track = item
				break
	return _walk_devices((track or {}).get("devices", {}))


def _walk_devices(devices):
	found = []
	for device in getattr(devices, "values", lambda: [])():
		found.append(device)
		for chain in device.get("chains", {}).values():
			found.extend(_walk_devices(chain.get("devices", {})))
	return found


def _resolve_ableton_midi_operator(operator):
	if operator is None:
		return None
	if _has_ableton_midi_pars(operator):
		return operator
	for path in ("abletonMIDI", "abletonMIDI/abletonMIDI"):
		try:
			child = operator.op(path)
		except Exception:
			child = None
		if child is not None and _has_ableton_midi_pars(child):
			return child
	for child in operator.findChildren(depth=5):
		if _has_ableton_midi_pars(child):
			return child
	return None


def _has_ableton_midi_pars(operator):
	try:
		return operator.par["Track"] is not None and operator.par["Callbackdat"] is not None
	except Exception:
		return False


def _refresh_lom(ableton_midi):
	try:
		ext = ableton_midi.ext.TDAbletonCompBaseExt
		ext.setTDAbletonComp()
		ext.onAbletonNotify({"notificationType": "songInfo"})
		ext.updateLOMPars(setupListeners=False)
	except Exception:
		pass


def _set_menu_parameter(operator, name, label):
	par = operator.par[name]
	if par is None:
		return False
	menu_labels = list(par.menuLabels or [])
	menu_names = list(par.menuNames or [])
	for values in (menu_labels, menu_names):
		for index, value in enumerate(values):
			if str(value) == str(label):
				par.menuIndex = index
				return True
	if menu_labels or menu_names:
		return False
	try:
		par.val = label
		return True
	except Exception:
		return False


def _set_parameter_value(operator, name, value):
	par = operator.par[name]
	if par is None:
		return False
	par.val = value
	return True


def _source_name(track_name):
	slug = re.sub(r"[^0-9A-Za-z_]+", "_", track_name.strip()).strip("_").lower()
	if not slug:
		slug = "ableton"
	if slug[0].isdigit():
		slug = "track_" + slug
	return slug


def _home(manager_comp):
	for candidate in (manager_comp, manager_comp.parent()):
		par = candidate.par["Home"]
		if par is not None and par.eval():
			return str(par.eval())
	return str(Path.home())


def _home_expr(home, file_name):
	escaped = home.replace("\\", "\\\\").replace('"', '\\"')
	return f'"{escaped}/td_scripts/midi_handler_v2/{file_name}"'


def _ableton_midi_tox_path():
	candidates = []
	try:
		candidates.append(Path(app.installFolder) / "Samples" / "Palette" / "TDAbleton" / "Live 11+" / "abletonMIDI.tox")
	except Exception:
		pass
	program_files = os.environ.get("PROGRAMFILES") if "os" in globals() else None
	if program_files:
		candidates.append(Path(program_files).joinpath(*ABLETON_MIDI_TOX_RELATIVE))
	for candidate in candidates:
		if candidate.exists():
			return candidate
	return None

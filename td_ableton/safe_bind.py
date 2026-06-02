DEFAULT_TD_ABLETON = "/project1/tdAbleton"

STATUS_READY = "ready"
STATUS_NO_ABLETON = "no_ableton"
STATUS_WRONG_SET = "wrong_set"
STATUS_INVALID_SPEC = "invalid_spec"


def guard_status(required_tracks=(), td_ableton_path=DEFAULT_TD_ABLETON):
	info = song_info(td_ableton_path)
	tracks = _tracks(info)
	if not tracks:
		return _result(False, STATUS_NO_ABLETON, "No Ableton song info available")

	missing_tracks = [name for name in required_tracks if not track_data(info, name)]
	if missing_tracks:
		return _result(
			False,
			STATUS_WRONG_SET,
			"Missing tracks: {}".format(", ".join(missing_tracks)),
		)

	return _result(True, STATUS_READY, "Ableton set looks valid")


def bind_midi(operator, track_name, device_name="TdaMIDI", connect=True, require_device=True):
	disarm(operator)
	if operator is None:
		return _result(False, STATUS_INVALID_SPEC, "Missing abletonMIDI operator")
	if not track_name:
		return _store_result(operator, _result(False, STATUS_INVALID_SPEC, "Missing track name"))

	info = song_info()
	if not _tracks(info):
		return _store_result(operator, _result(False, STATUS_NO_ABLETON, "No Ableton song info available"))
	if not track_data(info, track_name):
		return _store_result(operator, _result(False, STATUS_WRONG_SET, "Missing track: {}".format(track_name)))

	refresh_lom(operator)
	if not set_menu_parameter(operator, "Track", track_name):
		return _store_result(operator, _result(False, STATUS_WRONG_SET, "Track menu missing: {}".format(track_name)))

	refresh_lom(operator)
	if device_name:
		if not set_menu_parameter(operator, "Device", device_name):
			status = STATUS_WRONG_SET if require_device else STATUS_INVALID_SPEC
			return _store_result(operator, _result(False, status, "Device menu missing: {}".format(device_name)))
		refresh_lom(operator)

	_set_parameter_value(operator, "Enablecallbacks", True)
	if connect:
		_set_parameter_value(operator, "Connect", True)
	_clear_errors(operator)
	return _store_result(operator, _result(True, STATUS_READY, "Bound {} / {}".format(track_name, device_name or "")))


def bind_parameter(operator, track_name, device_name, parameter_name, connect=True, autosync=True):
	disarm(operator)
	if operator is None:
		return _result(False, STATUS_INVALID_SPEC, "Missing abletonParameter operator")
	if not track_name or not device_name or not parameter_name:
		return _store_result(operator, _result(False, STATUS_INVALID_SPEC, "Missing track/device/parameter"))

	info = song_info()
	if not _tracks(info):
		return _store_result(operator, _result(False, STATUS_NO_ABLETON, "No Ableton song info available"))
	if not track_data(info, track_name):
		return _store_result(operator, _result(False, STATUS_WRONG_SET, "Missing track: {}".format(track_name)))

	refresh_lom(operator)
	for par_name, label in (("Track", track_name), ("Device", device_name), ("Parameter", parameter_name)):
		if not set_menu_parameter(operator, par_name, label):
			return _store_result(operator, _result(False, STATUS_WRONG_SET, "{} menu missing: {}".format(par_name, label)))
		refresh_lom(operator)

	_set_parameter_value(operator, "Autosync", bool(autosync))
	if connect:
		_set_parameter_value(operator, "Connect", True)
	_clear_errors(operator)
	return _store_result(
		operator,
		_result(True, STATUS_READY, "Bound {} / {} / {}".format(track_name, device_name, parameter_name)),
	)


def disarm(operator):
	if operator is None:
		return False
	_set_parameter_value(operator, "Connect", False)
	return True


def song_info(td_ableton_path=DEFAULT_TD_ABLETON):
	td_ableton = _op(td_ableton_path)
	if td_ableton is None:
		return {}
	try:
		ext = td_ableton.ext.TDAbletonExt
		update = getattr(ext, "Update", None) or getattr(ext, "UpdateAbletonComps", None)
		if update:
			update()
	except Exception:
		pass
	try:
		return dict(td_ableton.ext.TDAbletonExt.SongInfo or {})
	except Exception:
		return {}


def refresh_lom(operator):
	try:
		ext = operator.ext.TDAbletonCompBaseExt
		ext.setTDAbletonComp()
		ext.onAbletonNotify({"notificationType": "songInfo"})
		ext.updateLOMPars(setupListeners=False)
		return True
	except Exception:
		return False


def set_menu_parameter(operator, name, label):
	par = operator.par[name]
	if par is None:
		return False
	for values in (list(par.menuLabels or []), list(par.menuNames or [])):
		for index, value in enumerate(values):
			if str(value) == str(label):
				par.menuIndex = index
				return True
	return False


def selected_menu_text(operator, name):
	par = operator.par[name]
	if par is None:
		return ""
	try:
		index = int(par.menuIndex)
	except Exception:
		return str(par.eval())
	for values in (list(par.menuLabels or []), list(par.menuNames or [])):
		if 0 <= index < len(values):
			return str(values[index])
	return str(par.eval())


def track_data(info, track_name):
	target = _norm(track_name)
	for key, data in _tracks(info).items():
		name = str(data.get("name") or key)
		if _norm(name) == target or _norm(key) == target:
			return data
	return None


def device_data(track, device_name):
	target = _norm(device_name)
	for device in _walk_devices((track or {}).get("devices", {})):
		name = str(device.get("name") or device.get("original_name") or device.get("ptr") or "")
		if _norm(name) == target:
			return device
	return None


def parameter_data(device, parameter_name):
	target = _norm(parameter_name)
	parameters = (device or {}).get("aPars", {}) or (device or {}).get("parameters", {}) or {}
	for key, data in parameters.items():
		name = str(data.get("name") or key)
		if _norm(name) == target or _norm(key) == target:
			return data
	return None


def required_tracks_from_sources(root):
	tracks = []
	for source in _find_children(root):
		tags = _tags(source)
		if not tags.intersection(("ableton-midi-source-v2", "ableton-param-source-v2")):
			continue
		name = source.fetch("track_name", "")
		if name and name not in tracks:
			tracks.append(str(name))
	return tracks


def disarm_v2_sources(root):
	count = 0
	for operator in _v2_ableton_operators(root):
		if disarm(operator):
			count += 1
	return count


def arm_v2_sources(root):
	results = []
	for source in _find_children(root):
		tags = _tags(source)
		if "ableton-midi-source-v2" in tags:
			midi = source.op("abletonMIDI")
			results.append(bind_midi(midi, source.fetch("track_name", ""), "TdaMIDI", connect=True))
		elif "ableton-param-source-v2" in tags:
			param = source.op("abletonParameter")
			results.append(bind_parameter(
				param,
				source.fetch("track_name", ""),
				source.fetch("device_name", ""),
				source.fetch("parameter_name", ""),
				connect=True,
			))
	return results


def _v2_ableton_operators(root):
	for source in _find_children(root):
		tags = _tags(source)
		if "ableton-midi-source-v2" in tags:
			midi = source.op("abletonMIDI")
			if midi is not None:
				yield midi
		elif "ableton-param-source-v2" in tags:
			param = source.op("abletonParameter")
			if param is not None:
				yield param


def _find_children(root):
	if root is None:
		return []
	result = []
	stack = list(getattr(root, "children", []) or [])
	while stack:
		operator = stack.pop(0)
		result.append(operator)
		stack.extend(list(getattr(operator, "children", []) or []))
	return result


def _walk_devices(devices):
	found = []
	for device in getattr(devices, "values", lambda: [])():
		found.append(device)
		for chain in device.get("chains", {}).values():
			found.extend(_walk_devices(chain.get("devices", {})))
	return found


def _tracks(info):
	return (info or {}).get("tracks", {}) or {}


def _tags(operator):
	try:
		return set(operator.tags)
	except Exception:
		return set()


def _set_parameter_value(operator, name, value):
	if operator is None:
		return False
	par = operator.par[name]
	if par is None:
		return False
	par.val = value
	return True


def _store_result(operator, result):
	if operator is not None:
		try:
			operator.store("safe_bind_result", result)
		except Exception:
			pass
	return result


def _clear_errors(operator):
	try:
		operator.clearScriptErrors()
	except Exception:
		pass


def _op(path):
	try:
		return op(str(path))
	except Exception:
		return None


def _norm(value):
	return str(value or "").strip().lower()


def _result(ok, status, message):
	return {"ok": bool(ok), "status": status, "message": message}

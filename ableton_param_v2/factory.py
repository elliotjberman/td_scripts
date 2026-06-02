from pathlib import Path
import importlib.util
import os
import re
import sys
import td


ABLETON_PARAMETER_TOX_RELATIVE = (
	"Derivative",
	"TouchDesigner",
	"Samples",
	"Palette",
	"TDAbleton",
	"Live 11+",
	"abletonParameter.tox",
)


def create_param_source(manager_comp, track_name="", device_name="", parameter_name="", name=None):
	parent_comp = manager_comp.parent()
	source_name = name or _source_name(parameter_name or device_name or "ableton_param")
	wrapper = parent_comp.op(source_name)
	if wrapper is None:
		wrapper = parent_comp.create(td.baseCOMP, source_name)
	wrapper.tags.add("ableton-param-source-v2")
	wrapper.store("track_name", track_name)
	wrapper.store("device_name", device_name)
	wrapper.store("parameter_name", parameter_name)

	_ensure_custom_parameters(wrapper, track_name, device_name, parameter_name)
	ableton_parameter = _ensure_ableton_parameter(wrapper)
	default_value = _ensure_default_value(wrapper)
	_build_processing_chain(wrapper, ableton_parameter, default_value)
	_configure_ableton_parameter(ableton_parameter, track_name, device_name, parameter_name)
	_layout(wrapper)
	return wrapper


def _ensure_custom_parameters(wrapper, track_name, device_name, parameter_name):
	page = _page(wrapper, "Ableton Param")
	for name, label, value in (
		("Trackname", "Track Name", track_name),
		("Devicename", "Device Name", device_name),
		("Parametername", "Parameter Name", parameter_name),
		("Outputname", "Output Name", "value"),
	):
		if wrapper.par[name] is None:
			page.appendStr(name, label=label)
		wrapper.par[name] = value
	for name, label, value in (
		("Defaultvalue", "Default Value", 0.0),
		("Frommin", "From Min", 0.0),
		("Frommax", "From Max", 127.0),
		("Tomin", "To Min", 0.0),
		("Tomax", "To Max", 1.0),
	):
		if wrapper.par[name] is None:
			page.appendFloat(name, label=label)
		wrapper.par[name] = value


def _ensure_ableton_parameter(wrapper):
	existing = wrapper.op("abletonParameter")
	if existing is not None and existing.par["Track"] is not None:
		return existing
	tox_path = _ableton_parameter_tox_path()
	if tox_path is None:
		return None
	loaded = wrapper.loadTox(str(tox_path), unwired=True)
	inner = loaded.op("abletonParameter") if loaded is not None else None
	if inner is None:
		inner = loaded
	if inner is not None and inner.parent() != wrapper:
		inner = wrapper.copy(inner, name="_abletonParameter_flat")
	if loaded is not None and loaded.valid and loaded != inner:
		loaded.destroy()
	if inner is not None:
		inner.name = "abletonParameter"
		inner.tags.add("ableton-param-source-v2-inner")
	return inner


def _ensure_default_value(wrapper):
	existing = wrapper.op("DefaultValue")
	if existing is not None:
		return existing
	tox_path = Path.home() / "td_scripts" / "utils" / "DefaultValue.tox"
	if tox_path.exists():
		loaded = wrapper.loadTox(str(tox_path), unwired=True)
		if loaded is not None:
			loaded.name = "DefaultValue"
			return loaded
	default_value = wrapper.create(td.constantCHOP, "DefaultValue")
	default_value.par.name0 = "value"
	default_value.par.value0 = 0
	return default_value


def _build_processing_chain(wrapper, ableton_parameter, default_value):
	fallback = _op(wrapper, "fallback_switch", td.switchCHOP)
	scale = _op(wrapper, "scale", td.mathCHOP)
	rename = _op(wrapper, "rename", td.selectCHOP)
	out = _op(wrapper, "out1", td.outCHOP)

	_connect(fallback, 0, _output(default_value))
	if ableton_parameter is not None:
		_connect(fallback, 1, _output(ableton_parameter))
		fallback.par.index.expr = "1 if op('abletonParameter/out1') and op('abletonParameter/out1').numChans else 0"
	else:
		fallback.par.index = 0
	_connect(scale, 0, fallback)
	_connect(rename, 0, scale)
	_connect(out, 0, rename)

	if default_value.par["Value"] is not None:
		default_value.par.Value.expr = "parent().par.Defaultvalue"
	if default_value.par["Channelname"] is not None:
		default_value.par.Channelname.expr = "parent().par.Outputname"
	scale.par.fromrange1.expr = "parent().par.Frommin"
	scale.par.fromrange2.expr = "parent().par.Frommax"
	scale.par.torange1.expr = "parent().par.Tomin"
	scale.par.torange2.expr = "parent().par.Tomax"
	rename.par.channames = "*"
	rename.par.renamefrom = "*"
	rename.par.renameto.expr = "parent().par.Outputname"


def _configure_ableton_parameter(ableton_parameter, track_name, device_name, parameter_name):
	if ableton_parameter is None:
		return False
	result = _safe_bind_module().bind_parameter(
		ableton_parameter,
		track_name,
		device_name,
		parameter_name,
		connect=True,
		autosync=True,
	)
	return result.get("ok", False)


def _layout(wrapper):
	positions = {
		"abletonParameter": (0, 160),
		"DefaultValue": (0, 0),
		"fallback_switch": (230, 80),
		"scale": (430, 80),
		"rename": (630, 80),
		"out1": (820, 80),
	}
	for name, (x, y) in positions.items():
		operator = wrapper.op(name)
		if operator is not None:
			operator.nodeX = x
			operator.nodeY = y


def _source_name(text):
	slug = re.sub(r"[^0-9A-Za-z_]+", "_", str(text).strip()).strip("_").lower()
	if not slug:
		slug = "ableton_param"
	if slug[0].isdigit():
		slug = "param_" + slug
	return slug + "_param"


def _op(parent, name, op_type):
	operator = parent.op(name)
	if operator is None:
		operator = parent.create(op_type, name)
	return operator


def _output(operator):
	if operator is None:
		return None
	return operator.op("out1") or operator


def _connect(target, index, source):
	if target is None or source is None:
		return
	target.inputConnectors[index].connect(source)


def _ableton_parameter_tox_path():
	candidates = []
	try:
		candidates.append(Path(app.installFolder) / "Samples" / "Palette" / "TDAbleton" / "Live 11+" / "abletonParameter.tox")
	except Exception:
		pass
	program_files = os.environ.get("PROGRAMFILES")
	if program_files:
		candidates.append(Path(program_files).joinpath(*ABLETON_PARAMETER_TOX_RELATIVE))
	for candidate in candidates:
		if candidate.exists():
			return candidate
	return None


_SAFE_BIND = None


def _safe_bind_module():
	global _SAFE_BIND
	if _SAFE_BIND is not None:
		return _SAFE_BIND
	candidates = []
	try:
		candidates.append(Path(__file__).resolve().parent.parent / "td_ableton" / "safe_bind.py")
	except Exception:
		pass
	candidates.append(Path.home() / "td_scripts" / "td_ableton" / "safe_bind.py")
	for path in candidates:
		if path.exists():
			spec = importlib.util.spec_from_file_location("td_ableton_safe_bind", str(path))
			module = importlib.util.module_from_spec(spec)
			module.__dict__.update({"op": op})
			sys.modules["td_ableton_safe_bind"] = module
			spec.loader.exec_module(module)
			_SAFE_BIND = module
			return module
	raise RuntimeError("td_ableton/safe_bind.py not found")


def _page(operator, name):
	for page in operator.customPages:
		if page.name == name:
			return page
	return operator.appendCustomPage(name)

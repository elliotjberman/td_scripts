from pathlib import Path
import os

import td


DEBUGGER_NAME = "CodexDebugger"
DEBUGGER_TAG = "codex-debugger"


def create_debugger(parent_comp=None, name=DEBUGGER_NAME):
	if parent_comp is None:
		parent_comp = _default_parent()
	if parent_comp is None:
		raise RuntimeError("No parent component found for CodexDebugger")

	debugger = parent_comp.op(name)
	if debugger is None:
		debugger = parent_comp.create(td.baseCOMP, name)
		_place_debugger(parent_comp, debugger)

	debugger_root = _debugger_root(parent_comp)
	debugger.tags.add(DEBUGGER_TAG)
	debugger.store("debugger_root", str(debugger_root))
	_ensure_parameters(debugger, debugger_root)
	_setup_extension(debugger, debugger_root)
	try:
		debugger.ext.CodexDebuggerExt.Setup()
	except Exception:
		_print_extension_diagnostics(debugger)
		raise
	return debugger


def _default_parent():
	for path in ("/project1", "/"):
		parent_comp = op(path)
		if parent_comp is not None:
			return parent_comp
	return None


def _ensure_parameters(debugger, debugger_root):
	page = _page(debugger, "Codex Debugger")
	if debugger.par["Enabled"] is None:
		page.appendToggle("Enabled", label="Enabled")
	if debugger.par["Pollframes"] is None:
		page.appendInt("Pollframes", label="Poll Frames")
	if debugger.par["Maxperpoll"] is None:
		page.appendInt("Maxperpoll", label="Max Per Poll")
	if debugger.par["Queuedir"] is None:
		page.appendStr("Queuedir", label="Queue Dir")
	if debugger.par["Runpending"] is None:
		page.appendPulse("Runpending", label="Run Pending")

	debugger.par.Enabled = True
	debugger.par.Pollframes = 10
	debugger.par.Maxperpoll = 1
	debugger.par.Queuedir = str(Path(debugger_root) / "queue")


def _setup_extension(debugger, debugger_root):
	ext_dat = debugger.op("CodexDebuggerExt")
	if ext_dat is None:
		ext_dat = debugger.create(td.textDAT, "CodexDebuggerExt")
	ext_dat.par.file.expr = _file_expr(debugger_root, "extension.py")
	ext_dat.par.syncfile = True
	ext_dat.par.loadonstartpulse.pulse()
	ext_dat.par.language = "python"
	debugger.par.ext0object = "op('./CodexDebuggerExt').module.CodexDebuggerExt(me)"
	debugger.par.ext0name = ""
	debugger.par.ext0promote = True
	debugger.par.reinitextensions.pulse()


def _place_debugger(parent_comp, debugger):
	try:
		debugger.nodeX = -500
		debugger.nodeY = 300
		for child in parent_comp.children:
			child.current = False
		debugger.current = True
		debugger.selected = True
	except Exception:
		pass


def _debugger_root(parent_comp):
	env_root = os.environ.get("CODEX_DEBUGGER_ROOT", "")
	if env_root and (Path(env_root) / "extension.py").exists():
		return Path(env_root)
	user_root = Path.home() / "td_scripts" / "debug" / "codex_debugger"
	if (user_root / "extension.py").exists():
		return user_root
	for candidate in (parent_comp, parent_comp.parent()):
		if candidate is None:
			continue
		par = candidate.par["Home"]
		if par is not None and par.eval():
			root = Path(str(par.eval())) / "td_scripts" / "debug" / "codex_debugger"
			if (root / "extension.py").exists():
				return root
	return user_root


def _file_expr(debugger_root, file_name):
	path = str(Path(debugger_root) / file_name)
	escaped = path.replace("\\", "\\\\").replace('"', '\\"')
	return f'"{escaped}"'


def _page(comp, name):
	for page in comp.customPages:
		if page.name == name:
			return page
	return comp.appendCustomPage(name)


def _print_extension_diagnostics(debugger):
	ext_dat = debugger.op("CodexDebuggerExt")
	if ext_dat is None:
		print("CodexDebuggerExt DAT is missing")
		return
	for attr in ("errors", "warnings"):
		try:
			value = getattr(ext_dat, attr)()
			if value:
				print("CodexDebuggerExt {}: {}".format(attr, value))
		except Exception:
			pass


try:
	debugger = create_debugger()
	print("codex_debugger:", debugger.path)
except NameError:
	pass
except Exception as exc:
	print("codex_debugger bootstrap failed:", exc)

from pathlib import Path
import td


MANAGER_NAME = "AbletonHookupManager"
MANAGER_TAG = "ableton-hookup-manager-v2"


def create_manager(parent_comp=None, name=MANAGER_NAME):
	if parent_comp is None:
		parent_comp = _default_parent()
	if parent_comp is None:
		raise RuntimeError("No parent component found for AbletonHookupManager")

	manager = parent_comp.op(name)
	if manager is None:
		manager = parent_comp.create(td.baseCOMP, name)
	_place_manager(parent_comp, manager)
	manager.tags.add(MANAGER_TAG)
	home = _home(parent_comp)
	manager.store("home", home)
	_setup_extension(manager, home)
	manager.ext.AbletonHookupManagerExt.Setup()
	return manager


def _default_parent():
	for path in ("/project1/visuals_container/visual", "/project1"):
		parent_comp = op(path)
		if parent_comp is not None:
			return parent_comp
	return None


def _setup_extension(manager, home):
	ext_dat = manager.op("AbletonHookupManagerExt")
	if ext_dat is None:
		ext_dat = manager.create(td.textDAT, "AbletonHookupManagerExt")
	ext_dat.par.file.expr = _home_expr(home, "manager_extension.py")
	ext_dat.par.syncfile = True
	ext_dat.par.loadonstartpulse.pulse()
	ext_dat.par.language = "python"
	manager.par.ext0object = "op('./AbletonHookupManagerExt').module.AbletonHookupManagerExt(me)"
	manager.par.ext0name = ""
	manager.par.ext0promote = True
	manager.par.reinitextensions.pulse()


def _place_manager(parent_comp, manager):
	try:
		manager.nodeX = 0
		manager.nodeY = 220
		for child in parent_comp.children:
			child.current = False
		manager.current = True
		manager.selected = True
	except Exception:
		pass


def _home(parent_comp):
	for candidate in (parent_comp, parent_comp.parent()):
		if candidate is None:
			continue
		par = candidate.par["Home"]
		if par is not None and par.eval():
			return str(par.eval())
	return str(Path.home())


def _home_expr(home, file_name):
	escaped = home.replace("\\", "\\\\").replace('"', '\\"')
	return f'"{escaped}/td_scripts/midi_handler_v2/{file_name}"'


try:
	manager = create_manager()
	print("midi_handler_v2 manager:", manager.path)
except NameError:
	pass
except Exception as exc:
	print("midi_handler_v2 bootstrap failed:", exc)

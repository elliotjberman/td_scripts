from pathlib import Path
import importlib.util
import sys
import td


GUARD_NAME = "AbletonGuard"
GUARD_TAG = "ableton-guard-v1"


def ensure_guard(parent_comp, home=None, name=GUARD_NAME):
	guard = parent_comp.op(name)
	if guard is None:
		guard = parent_comp.create(td.baseCOMP, name)
		guard.nodeX = 0
		guard.nodeY = 420
	guard.tags.add(GUARD_TAG)
	if home:
		guard.store("home", home)
	_setup_extension(guard, home or _home(parent_comp))
	guard.ext.AbletonGuardExt.Setup()
	return guard


class AbletonGuardExt:
	def __init__(self, ownerComp):
		self.ownerComp = ownerComp
		self._safe_bind = None

	def Setup(self):
		self.ownerComp.tags.add(GUARD_TAG)
		self._ensure_parameters()
		self._ensure_required_tracks()
		self._ensure_callbacks()
		self.Refresh()

	def Refresh(self):
		safe_bind = self.SafeBind()
		result = safe_bind.guard_status(
			self.RequiredTracks(),
			self.ownerComp.par.Tdabletonpath.eval(),
		)
		if result.get("status") != safe_bind.STATUS_READY and self._auto_disarm():
			safe_bind.disarm_v2_sources(self.ownerComp.parent())
		self._set_status(result)
		return result

	def IsReady(self):
		return self.Refresh().get("status") == self.SafeBind().STATUS_READY

	def Arm(self):
		safe_bind = self.SafeBind()
		safe_bind.disarm_v2_sources(self.ownerComp.parent())
		result = self.Refresh()
		if result.get("status") != safe_bind.STATUS_READY:
			return result
		results = safe_bind.arm_v2_sources(self.ownerComp.parent())
		failed = [item for item in results if not item.get("ok")]
		if failed:
			message = "; ".join(item.get("message", "") for item in failed)
			result = {"ok": False, "status": safe_bind.STATUS_WRONG_SET, "message": message}
		else:
			result = {"ok": True, "status": safe_bind.STATUS_READY, "message": "Armed {} sources".format(len(results))}
		self._set_status(result)
		return result

	def Disarm(self):
		count = self.SafeBind().disarm_v2_sources(self.ownerComp.parent())
		result = {"ok": True, "status": "disarmed", "message": "Disarmed {} sources".format(count)}
		self._set_status(result)
		return result

	def RequiredTracks(self):
		rows = self.ownerComp.op("required_tracks")
		tracks = []
		if rows is not None:
			for row in rows.rows()[1:]:
				name = row[0].val.strip()
				if name and name not in tracks:
					tracks.append(name)
		for name in self.SafeBind().required_tracks_from_sources(self.ownerComp.parent()):
			if name not in tracks:
				tracks.append(name)
		return tracks

	def HandleParPulse(self, par):
		actions = {
			"Refresh": self.Refresh,
			"Arm": self.Arm,
			"Disarm": self.Disarm,
		}
		action = actions.get(getattr(par, "name", ""))
		if action:
			action()

	def SafeBind(self):
		if self._safe_bind is None:
			self._safe_bind = _load_safe_bind(_home(self.ownerComp))
		return self._safe_bind

	def _ensure_parameters(self):
		page = _page(self.ownerComp, "Ableton Guard")
		if self.ownerComp.par["Home"] is None:
			page.appendStr("Home", label="Home")
		if not self.ownerComp.par.Home.eval():
			self.ownerComp.par.Home = _home(self.ownerComp)
		if self.ownerComp.par["Tdabletonpath"] is None:
			page.appendStr("Tdabletonpath", label="TDAbleton Path")
			self.ownerComp.par.Tdabletonpath = "/project1/tdAbleton"
		if self.ownerComp.par["Status"] is None:
			page.appendStr("Status", label="Status")
		if self.ownerComp.par["Message"] is None:
			page.appendStr("Message", label="Message")
		if self.ownerComp.par["Autodisarm"] is None:
			page.appendToggle("Autodisarm", label="Auto Disarm")
			self.ownerComp.par.Autodisarm = True
		for name in ("Refresh", "Arm", "Disarm"):
			if self.ownerComp.par[name] is None:
				page.appendPulse(name)

	def _ensure_required_tracks(self):
		rows = self.ownerComp.op("required_tracks")
		if rows is None:
			rows = self.ownerComp.create(td.tableDAT, "required_tracks")
		if rows.numRows == 0:
			rows.appendRow(("track_name",))
		return rows

	def _ensure_callbacks(self):
		callbacks = self.ownerComp.op("guard_par_callbacks")
		if callbacks is None:
			callbacks = self.ownerComp.create(td.parameterexecuteDAT, "guard_par_callbacks")
		callbacks.par.pars = "Refresh Arm Disarm"
		callbacks.par.fromop = self.ownerComp.path
		callbacks.par.op = self.ownerComp.path
		callbacks.par.onpulse = True
		callbacks.par.custom = True
		callbacks.par.builtin = False
		callbacks.par.language = "python"
		callbacks.text = (
			"def onValueChange(par, prev):\n\treturn\n\n"
			"def onPulse(par):\n\tparent().ext.AbletonGuardExt.HandleParPulse(par)\n\treturn\n"
		)

	def _set_status(self, result):
		self.ownerComp.store("ableton_guard_result", result)
		self.ownerComp.par.Status = result.get("status", "")
		self.ownerComp.par.Message = result.get("message", "")

	def _auto_disarm(self):
		par = self.ownerComp.par["Autodisarm"]
		return bool(par.eval()) if par is not None else True


def _setup_extension(guard, home):
	ext_dat = guard.op("AbletonGuardExt")
	if ext_dat is None:
		ext_dat = guard.create(td.textDAT, "AbletonGuardExt")
	ext_dat.par.file.expr = _home_expr(home, "ableton_guard.py")
	ext_dat.par.syncfile = True
	ext_dat.par.loadonstartpulse.pulse()
	ext_dat.par.language = "python"
	guard.par.ext0object = "op('./AbletonGuardExt').module.AbletonGuardExt(me)"
	guard.par.ext0name = ""
	guard.par.ext0promote = True
	guard.par.reinitextensions.pulse()


def _load_safe_bind(home):
	path = Path(home) / "td_scripts" / "td_ableton" / "safe_bind.py"
	if not path.exists():
		path = Path(__file__).resolve().parent / "safe_bind.py"
	spec = importlib.util.spec_from_file_location("td_ableton_safe_bind", str(path))
	module = importlib.util.module_from_spec(spec)
	module.__dict__.update({"op": op})
	sys.modules["td_ableton_safe_bind"] = module
	spec.loader.exec_module(module)
	return module


def _home(operator):
	for candidate in (operator, operator.parent() if operator else None):
		if candidate is None:
			continue
		value = candidate.fetch("home", "")
		if value:
			return str(value)
		par = candidate.par["Home"]
		if par is not None and par.eval():
			return str(par.eval())
	return str(Path.home())


def _home_expr(home, file_name):
	escaped = str(home).replace("\\", "\\\\").replace('"', '\\"')
	return f'"{escaped}/td_scripts/td_ableton/{file_name}"'


def _page(operator, name):
	for page in operator.customPages:
		if page.name == name:
			return page
	return operator.appendCustomPage(name)

from datetime import datetime
from pathlib import Path
import importlib.util
import json
import time
import td


class AbletonMidiSourceExt:
	"""Self-contained Ableton MIDI source wrapper."""

	SOURCE_TAG = "ableton-midi-source-v2"
	TARGET_TAGS = ("scaled-envelope", "midi-route-target")

	def __init__(self, ownerComp):
		self.ownerComp = ownerComp

	def Setup(self):
		self.ownerComp.tags.add(self.SOURCE_TAG)
		self._migrate_source_metadata()
		self._remove_old_source_pars()
		self._ensure_parameters()
		self._ensure_parameter_callbacks()
		self._ensure_mappings_dat()
		self._ensure_recent_notes()
		self._ensure_note_activity()
		self._ensure_last_note()
		self._ensure_output_chop()

	def OnMidiEvent(self, info):
		event_type = str(info.get("eventType", ""))
		number = self._safe_int(info.get("eventTypeNumber"))
		value = self._safe_int(info.get("eventValue"))
		self._record_event(event_type, number, value)
		if event_type != "note" or number is None or value is None:
			return
		last_note = self._ensure_last_note()
		self._set_constant_channel(last_note, 0, "note", number)
		self._set_constant_channel(last_note, 1, "velocity", value)
		self._set_constant_channel(last_note, 2, "gate", 1 if value > 0 else 0)
		if value <= 0:
			return
		self._record_note_activity(number, value)
		self.RouteNote(number, value)

	def RouteNote(self, note, velocity=127):
		targets = self.MappedTargets(note)
		for target in targets:
			self._pulse_target(target, velocity, note)
		return [target.path for target in targets]

	def MappedTargets(self, note):
		data = self.MappingData()
		entries = []
		for key in (str(note), "*", "_"):
			entries.extend(data.get("mappings", {}).get(key, []))
		targets = []
		for entry in entries:
			target = self._op(entry.get("target", ""))
			if target is not None:
				targets.append(target)
		return targets

	def AddMapping(self, note, target_path, action="pulse"):
		data = self.MappingData()
		key = str(note)
		data.setdefault("mappings", {}).setdefault(key, [])
		entry = {"target": target_path, "action": action}
		if entry not in data["mappings"][key]:
			data["mappings"][key].append(entry)
		self.SaveMappingData(data)

	def RemoveMapping(self, note, target_path):
		data = self.MappingData()
		key = str(note)
		rows = data.setdefault("mappings", {}).get(key, [])
		data["mappings"][key] = [row for row in rows if row.get("target") != target_path]
		self.SaveMappingData(data)

	def MappingData(self):
		mappings = self._ensure_mappings_dat()
		try:
			data = json.loads(mappings.text or "{}")
		except Exception:
			data = {}
		data.setdefault("version", 1)
		data.setdefault("source_id", self.SourceId())
		data.setdefault("track_name", self.TrackName())
		data.setdefault("mappings", {})
		return data

	def SaveMappingData(self, data):
		data["source_id"] = self.SourceId()
		data["track_name"] = self.TrackName()
		self._ensure_mappings_dat().text = json.dumps(data, indent=2, sort_keys=True)

	def DiscoverTargets(self):
		root = self.ownerComp.parent()
		targets = []
		candidates = list(root.children) + list(root.findChildren(depth=4))
		seen = set()
		for candidate in candidates:
			if candidate.id in seen:
				continue
			seen.add(candidate.id)
			if candidate == self.ownerComp or not candidate.isCOMP:
				continue
			if self._is_route_target(candidate):
				targets.append({"label": self._target_label(candidate), "path": candidate.path})
		return targets

	def SourceId(self):
		return self._metadata_value("source_id", "Sourceid")

	def TrackName(self):
		return self._metadata_value("track_name", "Trackname")

	def OpenMapper(self):
		manager = self._manager()
		if manager is None:
			raise RuntimeError("AbletonHookupManager could not be created")
		return manager.ext.AbletonHookupManagerExt.OpenMappingEditor(self.ownerComp.path)

	def HandleParPulse(self, par):
		if getattr(par, "name", "") == "Openmapper":
			self.OpenMapper()

	def _is_route_target(self, candidate):
		tags = set(candidate.tags)
		if tags.intersection(self.TARGET_TAGS):
			return True
		return candidate.par["Trigger"] is not None or candidate.par["triggerpulse"] is not None

	def _target_label(self, target):
		try:
			label = target.par.Targetlabel.eval()
			if label:
				return str(label)
		except Exception:
			pass
		return target.name

	def _pulse_target(self, target, velocity, note):
		target.store("midi_velocity", velocity)
		target.store("midi_note", note)
		for par_name in ("Trigger", "triggerpulse", "Pulse"):
			par = target.par[par_name]
			if par is not None:
				par.pulse()
				return True
		return False

	def _migrate_source_metadata(self):
		for store_key, par_name in (("source_id", "Sourceid"), ("track_name", "Trackname")):
			if self.ownerComp.fetch(store_key, ""):
				continue
			par = self.ownerComp.par[par_name]
			if par is not None and par.eval():
				self.ownerComp.store(store_key, str(par.eval()))

	def _metadata_value(self, store_key, par_name):
		value = self.ownerComp.fetch(store_key, "")
		if value:
			return str(value)
		par = self.ownerComp.par[par_name]
		if par is not None and par.eval():
			return str(par.eval())
		return ""

	def _remove_old_source_pars(self):
		for name in ("Sourceid", "Trackname", "Mappingdat", "Lastnotechop", "Refreshtargets"):
			par = self.ownerComp.par[name]
			if par is None:
				continue
			try:
				par.destroy()
				continue
			except Exception:
				pass
			try:
				par.hidden = True
			except Exception:
				pass

	def _ensure_parameters(self):
		page = self._page("Ableton Source")
		if self.ownerComp.par["Openmapper"] is None:
			page.appendPulse("Openmapper", label="Open Mapper")

	def _ensure_parameter_callbacks(self):
		callbacks = self.ownerComp.op("source_par_callbacks")
		if callbacks is None:
			callbacks = self.ownerComp.create(td.parameterexecuteDAT, "source_par_callbacks")
		callbacks.par.pars = "Openmapper"
		callbacks.par.fromop = self.ownerComp.path
		callbacks.par.op = self.ownerComp.path
		callbacks.par.onpulse = True
		callbacks.par.custom = True
		callbacks.par.builtin = False
		callbacks.par.language = "python"
		callbacks.text = (
			"def onValueChange(par, prev):\n\treturn\n\n"
			"def onPulse(par):\n"
			"\tparent().ext.AbletonMidiSourceExt.HandleParPulse(par)\n"
			"\treturn\n"
		)

	def _ensure_mappings_dat(self):
		mappings = self.ownerComp.op("mappings_json")
		if mappings is None:
			mappings = self.ownerComp.create(td.textDAT, "mappings_json")
		if not (mappings.text or "").strip():
			data = {
				"version": 1,
				"source_id": self.SourceId(),
				"track_name": self.TrackName(),
				"mappings": {},
			}
			mappings.text = json.dumps(data, indent=2, sort_keys=True)
		return mappings

	def _ensure_recent_notes(self):
		table = self.ownerComp.op("recent_notes")
		if table is None:
			table = self.ownerComp.create(td.tableDAT, "recent_notes")
		if table.numRows == 0 or not any(cell.val for cell in table.row(0)):
			table.clear()
			table.appendRow(("time", "event_type", "number", "value"))
		return table

	def _ensure_note_activity(self):
		table = self.ownerComp.op("note_activity")
		if table is None:
			table = self.ownerComp.create(td.tableDAT, "note_activity")
		if table.numRows == 0 or not any(cell.val for cell in table.row(0)):
			table.clear()
			table.appendRow(("note", "velocity", "last_seen", "count"))
		return table

	def _ensure_last_note(self):
		chop = self.ownerComp.op("last_note")
		if chop is None:
			chop = self.ownerComp.create(td.constantCHOP, "last_note")
		self._set_constant_channel(chop, 0, "note", 0)
		self._set_constant_channel(chop, 1, "velocity", 0)
		self._set_constant_channel(chop, 2, "gate", 0)
		return chop

	def _ensure_output_chop(self):
		last_note = self._ensure_last_note()
		out = self.ownerComp.op("out1")
		if out is None:
			out = self.ownerComp.create(td.outCHOP, "out1")
		self._connect_first_input(out, last_note)
		out.nodeX = last_note.nodeX + 180
		out.nodeY = last_note.nodeY
		for operator in (last_note, out):
			try:
				operator.display = True
				operator.viewer = True
			except Exception:
				pass
		return out

	def _set_constant_channel(self, chop, index, name, value):
		name_par = chop.par["name{}".format(index)]
		value_par = chop.par["value{}".format(index)]
		if name_par is not None:
			name_par.val = name
		if value_par is not None:
			value_par.val = value

	def _connect_first_input(self, target, source):
		try:
			if target.inputs and target.inputs[0] == source:
				return
		except Exception:
			pass
		try:
			target.inputConnectors[0].connect(source)
			return
		except Exception:
			pass
		try:
			target.setInput(0, source)
		except Exception:
			pass

	def _op(self, path):
		path = str(path or "")
		if not path:
			return None
		try:
			found = self.ownerComp.op(path)
			if found is not None:
				return found
		except Exception:
			pass
		try:
			return self.ownerComp.evalExpression("op({!r})".format(path))
		except Exception:
			return None

	def _manager(self):
		root = self.ownerComp.parent()
		for child in root.children:
			if child.name == "AbletonHookupManager" or "ableton-hookup-manager-v2" in child.tags:
				return child
		return self._create_manager(root)

	def _create_manager(self, root):
		path = self._script_root() / "manager" / "bootstrap.py"
		if not path.exists():
			return None
		spec = importlib.util.spec_from_file_location("midi_handler_v2_manager_bootstrap", str(path))
		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)
		return module.create_manager(root)

	def _script_root(self):
		home = self.ownerComp.fetch("home", "")
		if home:
			return Path(str(home)) / "td_scripts" / "midi_handler_v2"
		try:
			return Path(__file__).resolve().parent
		except Exception:
			return Path.home() / "td_scripts" / "midi_handler_v2"

	def _page(self, name):
		for page in self.ownerComp.customPages:
			if page.name == name:
				return page
		return self.ownerComp.appendCustomPage(name)

	def _record_event(self, event_type, number, value):
		table = self._ensure_recent_notes()
		table.appendRow((datetime.now().isoformat(timespec="seconds"), event_type, str(number), str(value)))
		while table.numRows > 65:
			table.deleteRow(1)

	def _record_note_activity(self, note, velocity):
		table = self._ensure_note_activity()
		note_text = str(note)
		for row in range(1, table.numRows):
			if table[row, 0].val == note_text:
				table[row, 1] = str(velocity)
				table[row, 2] = "{:.6f}".format(time.time())
				table[row, 3] = str((self._safe_int(table[row, 3].val) or 0) + 1)
				return
		table.appendRow((note_text, str(velocity), "{:.6f}".format(time.time()), "1"))

	def _safe_int(self, value):
		try:
			return int(value)
		except Exception:
			return None

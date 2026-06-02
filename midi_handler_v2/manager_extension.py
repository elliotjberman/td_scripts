from pathlib import Path
import importlib.util
import json
import sys


class AbletonHookupManagerExt:
	SOURCE_TAG = "ableton-midi-source-v2"
	MANAGER_TAG = "ableton-hookup-manager-v2"

	def __init__(self, ownerComp):
		self.ownerComp = ownerComp
		self._module_cache = {}
		self._clear_legacy_storage()

	def Setup(self):
		self.ownerComp.tags.add(self.MANAGER_TAG)
		self._clear_legacy_storage()
		self._ensure_parameters()
		self._remove_deprecated_parameters()
		self._remove_bridge_artifacts()
		self._ensure_parameter_callbacks()
		self._ensure_hotkey()
		self._modal_module().ensure_source_picker(self)
		self._name_prompt_module().ensure_envelope_name_prompt(self)
		self._mapping_modal_module().ensure_mapping_editor(self)
		self._parameter_mapper_module().ensure_parameter_mapper(self)
		self._ableton_param_picker_module().ensure_picker(self)
		self.AbletonGuard()

	def OpenSourcePicker(self):
		info = self.SourcePickerInfo()
		self._modal_module().open_source_picker(self, info)
		return info["available_tracks"]

	def CloseSourcePicker(self):
		self._modal_module().close_source_picker(self)

	def OpenMappingEditor(self, source_path=None):
		return self._mapping_modal_module().open_mapping_editor(self, source_path)

	def RefreshMappingEditor(self):
		return self._mapping_modal_module().refresh_mapping_editor(self)

	def SelectMappingNote(self, note_key):
		return self._mapping_modal_module().select_note(self, note_key)

	def ToggleMappingTarget(self, target_path):
		return self._mapping_modal_module().toggle_target(self, target_path)

	def GoToMappingTarget(self, target_path):
		return self._mapping_modal_module().go_to_target(self, target_path)

	def UpdateSourcePickerActivity(self):
		self._modal_module().update_source_picker_activity(self)

	def SelectSourceTrack(self, track_name):
		if track_name in self.ExistingSourceTracks():
			return None
		source = self.CreateSource(track_name)
		self.CloseSourcePicker()
		return source

	def SourcePickerInfo(self):
		tracks = self.AbletonTrackNames()
		selected = set(self.ExistingSourceTracks())
		available = [track for track in tracks if track not in selected]
		return {
			"tracks": tracks,
			"selected_tracks": sorted(selected),
			"available_tracks": available,
		}

	def AbletonTrackNames(self):
		td_ableton = op("/project1/tdAbleton")
		if td_ableton is None:
			return []
		try:
			td_ableton.ext.TDAbletonExt.Update()
		except Exception:
			pass
		try:
			tracks = td_ableton.ext.TDAbletonExt.SongInfo.get("tracks", {})
		except Exception:
			return []
		names = []
		for key, data in tracks.items():
			name = str(data.get("name") or key)
			if self._is_selectable_ableton_track(name):
				names.append(name)
		return names

	def _is_selectable_ableton_track(self, name):
		text = str(name or "").strip()
		lower = text.lower()
		return bool(text) and not lower.startswith("return:") and "master" not in lower

	def ExistingSourceTracks(self):
		root = self.ownerComp.parent()
		selected = set()
		candidates = [root] + list(root.children) + list(root.findChildren(depth=4))
		for candidate in candidates:
			try:
				if self._is_source_candidate(candidate):
					track = self._source_track_name(candidate)
					if track:
						selected.add(str(track))
			except Exception:
				pass
		return sorted(selected)

	def _is_source_candidate(self, candidate):
		if self.SOURCE_TAG in candidate.tags:
			return True
		if str(candidate.name).endswith("_source") and candidate.op("abletonMIDI") is not None:
			return True
		return False

	def _source_track_name(self, source):
		for value in (
			source.fetch("track_name", ""),
			self._par_value(source, "Trackname"),
			self._mapping_track_name(source),
		):
			if value:
				return value
		ableton_midi = source.op("abletonMIDI")
		if ableton_midi is not None:
			return ableton_midi.fetch("track_name", "") or self._par_value(ableton_midi, "Track")
		return ""

	def _mapping_track_name(self, source):
		mappings = source.op("mappings_json")
		if mappings is None:
			return ""
		try:
			return str(json.loads(mappings.text or "{}").get("track_name", ""))
		except Exception:
			return ""

	def _par_value(self, operator, name):
		par = operator.par[name]
		if par is None:
			return ""
		try:
			return str(par.eval())
		except Exception:
			return ""

	def CreateSource(self, track_name, add_device=True):
		factory = self._factory_module()
		factory.op = op
		return factory.create_source(self.ownerComp, track_name, add_device=add_device)

	def CreateScaledEnvelope(self, name=None):
		if name is None:
			return self._name_prompt_module().open_envelope_name_prompt(self)
		return self.CreateScaledEnvelopeFromName(name)

	def CreateScaledEnvelopeFromName(self, name):
		return self._envelopes_module().create_scaled_envelope(self, name)

	def FocusEnvelopeNamePrompt(self):
		return self._name_prompt_module().focus_envelope_name_prompt(self)

	def UpdateEnvelopeNamePrompt(self):
		return self._name_prompt_module().update_envelope_name_prompt(self)

	def OpenParameterMapper(self):
		return self._parameter_mapper_module().open_parameter_mapper(self)

	def OpenAbletonParamPicker(self):
		return self._ableton_param_picker_module().open_picker(self)

	def SelectAbletonParam(self, parameter_name):
		return self._ableton_param_picker_module().select_parameter(self, parameter_name)

	def AbletonGlobalMacroParameters(self):
		return self._ableton_param_picker_module().global_macro_parameters(self)

	def AbletonParamPickerInfo(self):
		return self._ableton_param_picker_module().picker_info(self)

	def AbletonGuard(self):
		module = self._ableton_guard_module()
		return module.ensure_guard(self.ownerComp.parent(), self._home())

	def RefreshAbletonGuard(self):
		return self.AbletonGuard().ext.AbletonGuardExt.Refresh()

	def ArmAbleton(self):
		return self.AbletonGuard().ext.AbletonGuardExt.Arm()

	def DisarmAbleton(self):
		return self.AbletonGuard().ext.AbletonGuardExt.Disarm()

	def CreateAbletonParamSource(self, track_name="", device_name="", parameter_name="", name=None):
		factory = self._ableton_param_factory_module()
		factory.op = op
		return factory.create_param_source(self.ownerComp, track_name, device_name, parameter_name, name=name)

	def CreateAndConnectAbletonParam(self, track_name, device_name, parameter_name, target_path, input_index=0, name=None, output_name=""):
		source = self.CreateAbletonParamSource(track_name, device_name, parameter_name, name=name)
		if output_name and source.par["Outputname"] is not None:
			source.par.Outputname = output_name
		target = target_path if hasattr(target_path, "inputConnectors") else op(str(target_path))
		if target is None:
			raise RuntimeError("Target operator not found: {}".format(target_path))
		output = source.op("out1") or source
		target.inputConnectors[int(input_index)].connect(output)
		return source

	def ApplyParameterBinding(self, output_path):
		return self._parameter_mapper_module().apply_binding(self, output_path)

	def RecordParameterChange(self, par, prev):
		return self._parameter_mapper_module().record_parameter_change(self, par, prev)

	def UpdateParameterTracker(self):
		return self._parameter_mapper_module().update_parameter_tracker(self)

	def HandleParPulse(self, par):
		actions = {
			"Addsource": self.OpenSourcePicker,
			"Addenvelope": self.CreateScaledEnvelope,
			"Refreshtracks": self.AbletonTrackNames,
			"Bindparam": self.OpenParameterMapper,
			"Addparam": self.OpenAbletonParamPicker,
			"Refreshguard": self.RefreshAbletonGuard,
			"Armableton": self.ArmAbleton,
			"Disarmableton": self.DisarmAbleton,
		}
		action = actions.get(getattr(par, "name", ""))
		if action:
			action()

	def HandleShortcut(self, shortcut_name):
		self._run_hotkey_action(self._hotkeys_module().resolve_shortcut(shortcut_name))

	def HandleKey(self, key, character, alt, ctrl, shift, state, cmd=False):
		if self._name_prompt_module().handle_key(self, key, character, alt, ctrl, shift, state, cmd):
			return
		action = self._hotkeys_module().resolve_key(key, character, alt, ctrl, shift, state, cmd)
		self._run_hotkey_action(action)

	def _run_hotkey_action(self, action):
		hotkeys = self._hotkeys_module()
		if action == hotkeys.ACTION_OPEN_SOURCE_PICKER:
			self.OpenSourcePicker()
		elif action == hotkeys.ACTION_CREATE_SCALED_ENVELOPE:
			self.CreateScaledEnvelope()
		elif action == hotkeys.ACTION_BIND_PARAMETER:
			self.OpenParameterMapper()
		elif action == hotkeys.ACTION_OPEN_ABLETON_PARAM_PICKER:
			self.OpenAbletonParamPicker()

	def _ensure_parameters(self):
		page = self._page("Ableton Hookup")
		for name, label in (
			("Addsource", "Add Source..."),
			("Addenvelope", "Add Scaled Envelope"),
			("Refreshtracks", "Refresh Tracks"),
			("Bindparam", "Bind Parameter..."),
			("Addparam", "Add Ableton Param..."),
			("Refreshguard", "Refresh Guard"),
			("Armableton", "Arm Ableton"),
			("Disarmableton", "Disarm Ableton"),
		):
			if self.ownerComp.par[name] is None:
				page.appendPulse(name, label=label)

	def _remove_deprecated_parameters(self):
		for name in ("Editmappings", "Startbridge"):
			par = self.ownerComp.par[name]
			if par is None:
				continue
			try:
				par.destroy()
			except Exception:
				try:
					par.hidden = True
				except Exception:
					pass

	def _ensure_parameter_callbacks(self):
		callbacks = self.ownerComp.op("manager_par_callbacks")
		if callbacks is None:
			callbacks = self.ownerComp.create(parameterexecuteDAT, "manager_par_callbacks")
		callbacks.par.pars = "Addsource Addenvelope Refreshtracks Bindparam Addparam Refreshguard Armableton Disarmableton"
		callbacks.par.fromop = self.ownerComp.path
		callbacks.par.op = self.ownerComp.path
		callbacks.par.onpulse = True
		callbacks.par.custom = True
		callbacks.par.builtin = False
		callbacks.par.language = "python"
		callbacks.text = (
			"def onValueChange(par, prev):\n\treturn\n\n"
			"def onPulse(par):\n\tparent().ext.AbletonHookupManagerExt.HandleParPulse(par)\n\treturn\n"
		)

	def _ensure_hotkey(self):
		self._remove_stale_hotkey_callbacks()
		callbacks = self.ownerComp.op("manager_hotkey_callbacks")
		if callbacks is None:
			callbacks = self.ownerComp.create(textDAT, "manager_hotkey_callbacks")
		keyboard = self.ownerComp.op("manager_hotkeys")
		if keyboard is None:
			keyboard = self.ownerComp.create(keyboardinDAT, "manager_hotkeys")
		callbacks.par.language = "python"
		callbacks.text = (
			"def onKey(dat, key, character, alt, lAlt, rAlt, ctrl, lCtrl, rCtrl, shift, lShift, rShift, state, time, *extra):\n"
			"\tcmd = any(bool(value) for value in extra)\n"
			"\tparent().ext.AbletonHookupManagerExt.HandleKey(key, character, bool(alt), bool(ctrl), bool(shift), bool(state), cmd)\n"
			"\treturn\n\n"
			"def onShortcut(dat, shortcutName, time):\n"
			"\tparent().ext.AbletonHookupManagerExt.HandleShortcut(shortcutName)\n"
			"\treturn\n"
		)
		keyboard.par.active = True
		keyboard.par.shortcuts = " ".join(self._hotkeys_module().shortcuts())
		keyboard.par.callbacks = callbacks.path
		keyboard.par.executeloc = "callbacks"

	def _remove_stale_hotkey_callbacks(self):
		stale = self.ownerComp.op("manager_hotkeys_callbacks")
		if stale is not None:
			try:
				stale.destroy()
			except Exception:
				pass

	def _remove_bridge_artifacts(self):
		try:
			self.ownerComp.unstore("td_bridge_state")
		except Exception:
			pass
		keeper = self.ownerComp.op("bridge_keepalive")
		if keeper is not None:
			try:
				keeper.destroy()
			except Exception:
				pass

	def _clear_legacy_storage(self):
		for key in ("midi_v2_module_cache", "td_bridge_state"):
			try:
				self.ownerComp.unstore(key)
			except Exception:
				pass

	def _factory_module(self):
		return self._module("midi_handler_v2_factory", "factory.py")

	def _modal_module(self):
		return self._module("midi_handler_v2_modal", "manager", "modal.py")

	def _name_prompt_module(self):
		return self._module("midi_handler_v2_name_prompt", "manager", "name_prompt.py")

	def _mapping_modal_module(self):
		return self._module("midi_handler_v2_mapping_modal", "manager", "mapping_modal.py")

	def _hotkeys_module(self):
		return self._module("midi_handler_v2_hotkeys", "manager", "hotkeys.py")

	def _envelopes_module(self):
		return self._module("midi_handler_v2_envelopes", "manager", "envelopes.py")

	def _parameter_mapper_module(self):
		return self._module("midi_handler_v2_parameter_mapper", "parameter_mapper.py")

	def _ableton_param_factory_module(self):
		return self._root_module("ableton_param_v2_factory", "ableton_param_v2", "factory.py")

	def _ableton_param_picker_module(self):
		return self._root_module("ableton_param_v2_macro_picker", "ableton_param_v2", "macro_picker.py")

	def _ableton_guard_module(self):
		return self._root_module("td_ableton_ableton_guard", "td_ableton", "ableton_guard.py")

	def _module(self, module_name, *parts):
		path = self._script_root().joinpath(*parts)
		return self._load_module(module_name, path)

	def _root_module(self, module_name, *parts):
		path = self._script_root().parent.joinpath(*parts)
		return self._load_module(module_name, path)

	def _load_module(self, module_name, path):
		mtime = path.stat().st_mtime if path.exists() else 0
		cache_key = (module_name, str(path), mtime)
		cached = self._module_cache.get(module_name)
		if cached and cached.get("key") == cache_key:
			return cached["module"]
		spec = importlib.util.spec_from_file_location(module_name, str(path))
		module = importlib.util.module_from_spec(spec)
		module.__dict__.update(self._td_environment())
		sys.modules[module_name] = module
		spec.loader.exec_module(module)
		self._module_cache[module_name] = {"key": cache_key, "module": module}
		self.ownerComp.unstore("midi_v2_module_cache")
		return module

	def _script_root(self):
		candidates = []
		home = self.ownerComp.fetch("home", "")
		if home:
			candidates.append(Path(str(home)) / "td_scripts" / "midi_handler_v2")
		try:
			candidates.append(Path(__file__).resolve().parent)
		except Exception:
			pass
		candidates.append(Path.home() / "td_scripts" / "midi_handler_v2")
		for candidate in candidates:
			if (candidate / "factory.py").exists():
				return candidate
		return candidates[0]

	def _home(self):
		value = self.ownerComp.fetch("home", "")
		if value:
			return str(value)
		return str(Path.home())

	def _td_environment(self):
		return {"op": op, "parent": parent, "me": me, "mod": mod, "project": project, "ui": ui, "run": run, "absTime": absTime, "ParMode": ParMode, "app": app}

	def _page(self, name):
		for page in self.ownerComp.customPages:
			if page.name == name:
				return page
		return self.ownerComp.appendCustomPage(name)

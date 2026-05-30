from pathlib import Path
import contextlib
import io
import json
import time
import traceback


class CodexDebuggerExt:
	TAG = "codex-debugger"
	MAX_WALK_NODES = 500
	MAX_WALK_DEPTH = 6

	def __init__(self, ownerComp):
		self.ownerComp = ownerComp
	def Setup(self):
		self.ownerComp.tags.add(self.TAG)
		self._ensure_dirs()
		self._ensure_poll_dat()
		self._ensure_par_callbacks()
	def Poll(self):
		if not self._enabled():
			return []
		return self.RunPending()
	def RunPending(self):
		paths = self._queue_paths()
		requests = sorted(paths["requests"].glob("*.json"))
		limit = max(1, self._int_par("Maxperpoll", 1))
		results = []
		for request_path in requests[:limit]:
			results.append(self.ExecuteRequestFile(request_path))
		return results
	def ExecuteRequestFile(self, request_path):
		paths = self._queue_paths()
		request_path = Path(str(request_path))
		running_path = request_path.with_suffix(".running")
		try:
			request_path.rename(running_path)
		except Exception:
			return None

		request_id = running_path.stem
		try:
			request = json.loads(running_path.read_text(encoding="utf-8"))
			request_id = str(request.get("id") or request_id)
			response = self.Execute(request.get("code", ""), request.get("mode", "exec"))
		except Exception:
			response = self._error_response(traceback.format_exc())
		response["id"] = request_id
		response["request_path"] = str(running_path)

		response_path = paths["responses"] / "{}.json".format(request_id)
		response_path.write_text(json.dumps(response, indent=2), encoding="utf-8")
		archive_path = paths["archive"] / "{}.json".format(request_id)
		try:
			running_path.replace(archive_path)
		except Exception:
			pass
		return response
	def Execute(self, code, mode="exec"):
		stdout = io.StringIO()
		stderr = io.StringIO()
		reply_box = {"set": False, "value": None}
		start = time.time()

		def reply(value=None):
			reply_box["set"] = True
			reply_box["value"] = value
			return value

		env = self._exec_env(reply)
		try:
			with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
				if str(mode).lower() == "eval":
					result = eval(str(code), env, env)
				else:
					exec(compile(str(code), "<codex_debugger>", "exec"), env, env)
					result = reply_box["value"] if reply_box["set"] else env.get("_result")
			return {
				"ok": True,
				"result": self._jsonable(result),
				"stdout": stdout.getvalue(),
				"stderr": stderr.getvalue(),
				"elapsed": round(time.time() - start, 6),
			}
		except Exception:
			return {
				"ok": False,
				"error": traceback.format_exc(),
				"stdout": stdout.getvalue(),
				"stderr": stderr.getvalue(),
				"elapsed": round(time.time() - start, 6),
			}

	def Describe(self, target="/project1", depth=1):
		operator = self._op(target)
		if operator is None:
			return None
		return self._describe_op(operator, depth)

	def Selected(self, root="/project1", depth=6):
		root_op = self._op(root)
		if root_op is None:
			return []
		items = self._walk(root_op, depth)
		return [self._describe_op(item, 0) for item in items if self._selected(item)]

	def FindByTag(self, tag, root="/project1", depth=6):
		root_op = self._op(root)
		if root_op is None:
			return []
		items = self._walk(root_op, depth)
		return [self._describe_op(item, 0) for item in items if str(tag) in self._tags(item)]

	def HandleParPulse(self, par):
		if getattr(par, "name", "") == "Runpending":
			self.RunPending()

	def _exec_env(self, reply):
		env = {
			"op": op,
			"parent": parent,
			"me": me,
			"mod": mod,
			"ui": ui,
			"project": project,
			"run": run,
			"absTime": absTime,
			"debugger": self,
			"owner": self.ownerComp,
			"reply": reply,
			"describe": self.Describe,
			"selected": self.Selected,
			"find_by_tag": self.FindByTag,
		}
		try:
			env["td"] = __import__("td")
		except Exception:
			pass
		return env

	def _describe_op(self, operator, depth):
		data = {
			"path": operator.path,
			"name": operator.name,
			"type": self._op_type(operator),
			"tags": sorted(self._tags(operator)),
			"selected": self._selected(operator),
			"children": len(self._children(operator)),
			"storage_keys": self._storage_keys(operator),
		}
		if depth > 0:
			data["child_ops"] = [self._describe_op(child, depth - 1) for child in self._children(operator)]
		return data

	def _walk(self, root, depth):
		max_depth = min(max(0, int(depth or 0)), self.MAX_WALK_DEPTH)
		result = []
		stack = [(root, 0)]
		seen = set()
		while stack and len(result) < self.MAX_WALK_NODES:
			operator, level = stack.pop()
			key = getattr(operator, "path", repr(operator))
			if key in seen:
				continue
			seen.add(key)
			result.append(operator)
			if level >= max_depth:
				continue
			children = self._children(operator)
			for child in reversed(children):
				stack.append((child, level + 1))
		return result

	def _children(self, operator):
		try:
			return list(operator.children)
		except Exception:
			return []

	def _tags(self, operator):
		try:
			return [str(tag) for tag in operator.tags]
		except Exception:
			return []

	def _op_type(self, operator):
		try:
			return str(operator.OPType)
		except Exception:
			return type(operator).__name__

	def _storage_keys(self, operator):
		try:
			return sorted([str(key) for key in operator.storage.keys()])
		except Exception:
			return []

	def _jsonable(self, value, depth=4):
		if value is None or isinstance(value, (bool, int, float, str)):
			return value
		if hasattr(value, "path") and hasattr(value, "OPType"):
			return self._describe_op(value, 0)
		if isinstance(value, dict):
			return {str(key): self._jsonable(item, depth - 1) for key, item in value.items()}
		if isinstance(value, (list, tuple, set)):
			return [self._jsonable(item, depth - 1) for item in list(value)]
		if depth <= 0:
			return repr(value)
		return {"type": type(value).__name__, "repr": repr(value)}

	def _op(self, target):
		if hasattr(target, "path"):
			return target
		try:
			return op(str(target))
		except Exception:
			return None

	def _selected(self, operator):
		try:
			return bool(operator.selected)
		except Exception:
			return False

	def _enabled(self):
		par = self.ownerComp.par["Enabled"]
		return bool(par.eval()) if par is not None else True

	def _int_par(self, name, default):
		par = self.ownerComp.par[name]
		if par is None:
			return default
		try:
			return int(par.eval())
		except Exception:
			return default

	def _queue_paths(self):
		root = self._queue_root()
		paths = {
			"root": root,
			"requests": root / "requests",
			"responses": root / "responses",
			"archive": root / "archive",
		}
		for path in paths.values():
			path.mkdir(parents=True, exist_ok=True)
		return paths

	def _queue_root(self):
		par = self.ownerComp.par["Queuedir"]
		if par is not None and par.eval():
			return Path(str(par.eval()))
		home = self.ownerComp.fetch("home", str(Path.home()))
		return Path(str(home)) / "td_scripts" / "debug" / "codex_debugger" / "queue"

	def _ensure_dirs(self):
		self._queue_paths()

	def _ensure_poll_dat(self):
		dat = self.ownerComp.op("codex_debugger_poll")
		if dat is None:
			dat = self.ownerComp.create(executeDAT, "codex_debugger_poll")
		dat.par.active = True
		dat.par.framestart = True
		dat.par.language = "python"
		dat.text = (
			"def onFrameStart(frame):\n"
			"\tcomp = parent()\n"
			"\tif not comp.par.Enabled.eval():\n"
			"\t\treturn\n"
			"\tframes = max(1, int(comp.par.Pollframes.eval() or 1))\n"
			"\tif frame % frames == 0:\n"
			"\t\tcomp.ext.CodexDebuggerExt.Poll()\n"
			"\treturn\n"
		)

	def _ensure_par_callbacks(self):
		dat = self.ownerComp.op("codex_debugger_par_callbacks")
		if dat is None:
			dat = self.ownerComp.create(parameterexecuteDAT, "codex_debugger_par_callbacks")
		dat.par.pars = "Runpending"
		dat.par.fromop = self.ownerComp.path
		dat.par.op = self.ownerComp.path
		dat.par.onpulse = True
		dat.par.language = "python"
		dat.text = (
			"def onValueChange(par, prev):\n\treturn\n\n"
			"def onPulse(par):\n"
			"\tparent().ext.CodexDebuggerExt.HandleParPulse(par)\n"
			"\treturn\n"
		)

	def _error_response(self, error):
		return {"ok": False, "error": error, "stdout": "", "stderr": "", "elapsed": 0}

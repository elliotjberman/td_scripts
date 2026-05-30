ACTION_OPEN_SOURCE_PICKER = "open_source_picker"
ACTION_CREATE_SCALED_ENVELOPE = "create_scaled_envelope"
ACTION_BIND_PARAMETER = "bind_parameter"

DEBUG_KEYS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0")

_ACTION_CANDIDATES = (
	(ACTION_OPEN_SOURCE_PICKER, ("ctrl.shift.m", "ctrl.alt.m", "cmd.alt.m", "ctrl.cmd.m", "cmd.m")),
	(ACTION_CREATE_SCALED_ENVELOPE, ("ctrl.e", "ctrl.shift.e")),
	(ACTION_BIND_PARAMETER, ("ctrl.shift.p",)),
)


def action_shortcuts():
	used = set()
	resolved = {}
	for action, candidates in _ACTION_CANDIDATES:
		resolved[action] = []
		for shortcut in candidates:
			if shortcut in used:
				continue
			resolved[action].append(shortcut)
			used.add(shortcut)
	return resolved


def shortcuts():
	values = []
	for action_values in action_shortcuts().values():
		values.extend(action_values)
	return tuple(values)


def resolve_shortcut(shortcut_name):
	for action, values in action_shortcuts().items():
		if shortcut_name in values:
			return action
	return None


def resolve_key(key, character, alt, ctrl, shift, state, cmd=False):
	if not state:
		return None
	key_text = str(character or key or "").lower()
	shortcut = _shortcut_name(key_text, alt, ctrl, shift, cmd)
	return resolve_shortcut(shortcut)


def next_debug_key(used_keys):
	used = {str(value).lower() for value in used_keys if value is not None}
	for key in DEBUG_KEYS:
		if key not in used:
			return key
	return ""


def _shortcut_name(key_text, alt, ctrl, shift, cmd):
	parts = []
	if ctrl:
		parts.append("ctrl")
	if shift:
		parts.append("shift")
	if alt:
		parts.append("alt")
	if cmd:
		parts.append("cmd")
	parts.append(key_text)
	return ".".join(parts)

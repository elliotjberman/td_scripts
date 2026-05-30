from pathlib import Path
import re
import td


ENVELOPE_TAG = "scaled-envelope"
ROUTE_TARGET_TAG = "midi-route-target"
MANAGER_TAG = "ableton-hookup-manager-v2"
REF_OFFSET_X = 210
REF_OFFSET_Y = 35
LEFT_PADDING_X = 130
STACK_SPACING_Y = 170


def create_scaled_envelope(manager, envelope_name=None):
	root = manager.ownerComp.parent()
	debug_key = next_envelope_debug_key(root, manager)
	base_name = _base_name(envelope_name, "scaled_{}".format(debug_key or "x"))
	name = _unique_name(root, "{}_envelope".format(base_name))
	envelope = _load_scaled_envelope(root, name) or root.create(td.baseCOMP, name)
	envelope.tags.add(ENVELOPE_TAG)
	envelope.tags.add(ROUTE_TARGET_TAG)
	envelope.store("envelope_name", base_name)
	envelope.store("debug_key", debug_key)
	envelope.store("test_key", debug_key)
	reference = _ensure_reference_null(root, envelope, base_name)
	_set_debug_key(envelope, debug_key)
	_place_envelope(envelope, reference, manager.ownerComp)
	return envelope


def next_envelope_debug_key(root, manager):
	hotkeys = manager._hotkeys_module()
	return hotkeys.next_debug_key(_used_debug_keys(root))


def _used_debug_keys(root):
	keys = []
	for candidate in list(root.children) + list(root.findChildren(depth=4)):
		try:
			if ENVELOPE_TAG not in candidate.tags:
				continue
			keys.append(candidate.fetch("debug_key", None))
			keys.append(candidate.fetch("test_key", None))
			for name in ("Debugkey", "Testkey", "Hotkey", "Key"):
				par = candidate.par[name]
				if par is not None:
					keys.append(par.eval())
		except Exception:
			pass
	return keys


def _load_scaled_envelope(root, name):
	tox = _scaled_envelope_tox_path()
	if tox is None:
		return None
	try:
		loaded = root.loadTox(str(tox), unwired=True)
		loaded.name = name
		return loaded
	except Exception:
		return None


def _scaled_envelope_tox_path():
	for candidate in (
		Path.home() / "td_scripts" / "midi_handler_v2" / "ScaledEnvelope.tox",
		Path.home() / "td_scripts" / "midi_handler" / "ScaledEnvelope.tox",
	):
		if candidate.exists():
			return candidate
	return None


def _set_debug_key(envelope, debug_key):
	for name in ("Debugkey", "Testkey", "Hotkey", "Key", "Debughotkey", "Testhotkey"):
		par = envelope.par[name]
		if par is not None:
			par.val = debug_key
			return
	page = _page(envelope, "Debug")
	par = envelope.par["Debugkey"]
	if par is None:
		page.appendStr("Debugkey", label="Debug Key")
	envelope.par.Debugkey = debug_key


def _ensure_reference_null(root, envelope, base_name):
	name = _unique_name(root, base_name)
	reference = root.create(td.nullCHOP, name)
	reference.tags.add(ROUTE_TARGET_TAG)
	reference.store("source_envelope", envelope.path)
	source = _envelope_output_chop(envelope)
	try:
		reference.inputConnectors[0].connect(source or envelope)
	except Exception:
		try:
			reference.setInput(0, source or envelope)
		except Exception:
			pass
	return reference


def _envelope_output_chop(envelope):
	for name in ("value", "out1", "final_value", "envelope_scale", "trigger_out"):
		chop = envelope.op(name)
		if chop is not None and _is_chop(chop):
			return chop
	for child in envelope.children:
		if _is_chop(child) and str(child.OPType).lower() == "outchop":
			return child
	return None


def _is_chop(operator):
	try:
		return operator.isCHOP
	except Exception:
		return False


def _place_envelope(envelope, reference, manager_comp):
	x, y = _next_envelope_position(manager_comp.parent(), envelope, reference)
	envelope.nodeX = x
	envelope.nodeY = y
	reference.nodeX = x + REF_OFFSET_X
	reference.nodeY = y + REF_OFFSET_Y


def _next_envelope_position(root, envelope, reference):
	existing = _existing_envelopes(root, envelope)
	if existing:
		x = min(item.nodeX for item in existing)
		y = min(item.nodeY for item in existing) - STACK_SPACING_Y
	else:
		left_edge = _network_left_edge(root, envelope, reference)
		x = left_edge - REF_OFFSET_X - LEFT_PADDING_X
		y = _left_edge_node_y(root, left_edge, envelope, reference)
	return x, y


def _network_left_edge(root, envelope, reference):
	nodes = _layout_anchor_nodes(root, envelope, reference)
	if not nodes:
		return 0
	return min(node.nodeX for node in nodes)


def _left_edge_node_y(root, left_edge, envelope, reference):
	nodes = [node for node in _layout_anchor_nodes(root, envelope, reference) if node.nodeX == left_edge]
	if nodes:
		return min(node.nodeY for node in nodes)
	return 0


def _layout_anchor_nodes(root, envelope, reference):
	nodes = []
	for child in root.children:
		if child in (envelope, reference):
			continue
		if _is_managed_envelope_node(child):
			continue
		if _is_manager_or_helper(child):
			continue
		nodes.append(child)
	return nodes


def _existing_envelopes(root, envelope):
	return [
		child for child in root.children
		if child != envelope and ENVELOPE_TAG in child.tags
	]


def _is_managed_envelope_node(operator):
	if ENVELOPE_TAG in operator.tags:
		return True
	if operator.fetch("source_envelope", None):
		return True
	return False


def _is_manager_or_helper(operator):
	if MANAGER_TAG in operator.tags:
		return True
	if operator.name.startswith("AbletonHookupManager"):
		return True
	return False


def _base_name(value, fallback):
	name = re.sub(r"[^0-9A-Za-z_]+", "_", str(value or "").strip()).strip("_").lower()
	if name.endswith("_envelope"):
		name = name[:-9].rstrip("_")
	name = name or fallback
	if name[0].isdigit():
		name = "env_" + name
	return name


def _unique_name(root, base):
	base = re.sub(r"[^0-9A-Za-z_]+", "_", base).strip("_") or "scaled_envelope"
	if root.op(base) is None:
		return base
	index = 2
	while root.op("{}_{}".format(base, index)) is not None:
		index += 1
	return "{}_{}".format(base, index)


def _page(comp, name):
	for page in comp.customPages:
		if page.name == name:
			return page
	return comp.appendCustomPage(name)

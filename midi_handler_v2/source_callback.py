def _source_wrapper():
	try:
		wrapper = me.parent()
	except Exception:
		return None
	return wrapper if _is_source_wrapper(wrapper) else None


def onMIDIEvent(info):
	wrapper = _source_wrapper()
	if wrapper is None:
		print("AbletonMidiSource callback DAT is not inside a MIDI source wrapper")
		return
	wrapper.ext.AbletonMidiSourceExt.OnMidiEvent(info)


def _is_source_wrapper(candidate):
	if candidate is None:
		return False
	try:
		return getattr(candidate.ext, "AbletonMidiSourceExt", None) is not None
	except Exception:
		return False

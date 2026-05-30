def _source_wrapper():
	for candidate in (parent(), parent().parent() if parent() else None):
		if candidate is None:
			continue
		try:
			wrapper_path = candidate.fetch("source_wrapper_path", "")
		except Exception:
			wrapper_path = ""
		wrapper = op(wrapper_path) if wrapper_path else candidate
		if wrapper is not None and getattr(wrapper.ext, "AbletonMidiSourceExt", None) is not None:
			return wrapper
	return None


def onMIDIEvent(info):
	wrapper = _source_wrapper()
	if wrapper is None:
		print("AbletonMidiSource callback could not resolve wrapper")
		return
	wrapper.ext.AbletonMidiSourceExt.OnMidiEvent(info)

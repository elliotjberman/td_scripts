"""Pulse an explicit public action when the reference track changes rows.

This observes a cue track, not a global scene-launch event. The first observed
row establishes a baseline; empty/stopped rows do not trigger or reset it.
"""

_last_index = None


def reset():
    global _last_index
    _last_index = None


def onPlayingClipChanged(info):
    global _last_index
    source = info['ownerComp']
    if str(source.par.Track) != str(source.par.Expectedtrack):
        reset()
        return
    index = int(info['index'])
    if index < 0:
        return
    previous = _last_index
    _last_index = index
    if previous is not None and index != previous:
        target = source.opex(str(source.par.Eventtarget))
        target.par[str(source.par.Eventpulse)].pulse()


def onQueuedClipChanged(info):
    pass


def onClipsStopped(info):
    pass

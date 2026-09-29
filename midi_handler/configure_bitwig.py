"""One-time authoring helpers. Run in TD; exported receivers embed the callbacks.

These configure an existing official receiver without changing its connection,
track selection, pin state, or Bitwig. Inspect and pin the intended track first.
"""

from pathlib import Path
from td import textDAT, parameterexecuteDAT

SOURCE_DIR = Path(__file__).resolve().parent


def _parameter(page, style, name, value, help_text):
    parameter = getattr(page.owner.par, name, None)
    if parameter is None:
        parameter = getattr(page, 'append' + style)(name)[0]
    parameter.default = value
    parameter.val = value
    parameter.help = help_text
    return parameter


def _callback(source, filename):
    callback = source.op('routing_callback')
    if callback is None:
        callback = source.create(textDAT, 'routing_callback')
    callback.par.syncfile = False
    callback.par.loadonstart = False
    callback.par.file = ''
    callback.text = (SOURCE_DIR / filename).read_text()
    callback.nodeX = 100
    peers = [child for child in source.children if child != callback]
    callback.nodeY = min((child.nodeY - child.nodeHeight for child in peers), default=0) - 30
    source.par.Callbackdat = source.relativePath(callback)
    return callback


def configure_note(source, handler, expected_track):
    if not source.name.endswith('_midi') or source.parent() != handler.parent():
        raise ValueError('Use a sibling *_midi receiver beside MidiHandler.')
    page = source.appendCustomPage('MIDI Routing')
    _parameter(page, 'Str', 'Expectedtrack', expected_track,
               'Exact pinned track name; other tracks are ignored.')
    _parameter(page, 'COMP', 'Midihandler', source.relativePath(handler),
               'MIDIHandler that owns this source\'s note mapping table.')
    return _callback(source, 'bitwig_note_callback.py')


def configure_scene(source, target, pulse_name, expected_track):
    if target.par[pulse_name] is None or not target.par[pulse_name].isPulse:
        raise ValueError('Choose an existing public Pulse parameter.')
    page = source.appendCustomPage('Cue Routing')
    _parameter(page, 'Str', 'Expectedtrack', expected_track,
               'Exact pinned cue-track name; other tracks are ignored.')
    _parameter(page, 'COMP', 'Eventtarget', source.relativePath(target),
               'Component that owns the action fired on a cue-row change.')
    _parameter(page, 'Str', 'Eventpulse', pulse_name,
               'Public Pulse parameter on Event Target.')
    _parameter(page, 'Pulse', 'Resetbaseline', 0,
               'Forget the last row, for example after switching projects or reconnecting.')
    callback = _callback(source, 'bitwig_scene_callback.py')
    reset = source.op('routing_reset')
    if reset is None:
        reset = source.create(parameterexecuteDAT, 'routing_reset')
    reset.par.op = '..'
    reset.par.pars = 'Track Expectedtrack Connect Resetbaseline'
    reset.par.valuechange = True
    reset.par.onpulse = True
    reset.text = (SOURCE_DIR / 'bitwig_scene_reset.py').read_text()
    reset.nodeX, reset.nodeY = callback.nodeX + callback.nodeWidth + 30, callback.nodeY
    return callback

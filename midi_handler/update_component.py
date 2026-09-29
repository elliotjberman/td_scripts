"""Embed this folder's sources into an existing MidiHandler COMP, then save a TOX.

One-time TD authoring helper; does not save the project or change mapping rows.
"""
from pathlib import Path
from td import DAT

SOURCE_DIR = Path(__file__).resolve().parent


def update(handler):
    if getattr(handler.par, 'Targetroot', None) is None:
        p = handler.appendCustomPage('Routing').appendCOMP('Targetroot', label='Target Visual')[0]
        p.defaultExpr = 'me.parent()'
        p.expr = 'me.parent()'
        p.help = 'Component containing the triggered envelopes; mapping paths are relative to it.'
    for dat in handler.findChildren(type=DAT):
        if getattr(dat.par, 'file', None) is not None:
            dat.par.syncfile = False
            dat.par.loadonstart = False
            dat.par.write = False
            dat.par.file = ''
    handler.op('TriggerExt').text = (SOURCE_DIR / 'extension.py').read_text()
    handler.op('opfind2_callbacks').text = (SOURCE_DIR / 'table_creation_callbacks.py').read_text()
    handler.par.reinitextensions.pulse()
    for name in ['all_triggers', 'all_envelopes']:
        handler.op(name).par.component.expr = 'parent().TargetRoot()'
    handler.op('all_tracks_callback').par.component.expr = 'parent(2)'
    handler.op('OutputReplicator/all_tracks').par.component.expr = 'parent(3)'
    handler.op('OutputReplicator/replicator1').par.recreateall.expr = ''

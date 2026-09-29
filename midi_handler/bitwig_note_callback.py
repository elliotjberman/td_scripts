"""Embed in an official bitwigNote receiver; see configure_bitwig.py."""


def onNoteEvent(info):
    velocity = int(info['velocity'])
    if velocity <= 0:
        return
    source = parent()
    if str(source.par.Track) != str(source.par.Expectedtrack):
        return
    handler = source.opex(str(source.par.Midihandler))
    handler.HandleNote(source.name, int(info['pitch']), velocity)

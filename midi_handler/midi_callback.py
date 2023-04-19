def onMIDIEvent(info):
    if info['eventType'] != 'note':
        return

    note = int(info['eventTypeNumber'])
    velocity = int(info['eventValue'])

    if velocity == 0:
        return

    name = str(info['ownerComp']).split("/")[-1]
    op('MidiHandler').HandleNote(name, note, velocity)

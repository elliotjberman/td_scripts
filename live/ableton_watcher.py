# me - this DAT
#
# channel - the Channel object which has changed
# sampleIndex - the index of the changed sample
# val - the numeric value of the changed sample
# prev - the previous sample value
#
# Make sure the corresponding toggle is enabled in the CHOP Execute DAT.

def onOffToOn(channel, sampleIndex, val, prev):
    return

def whileOn(channel, sampleIndex, val, prev):
    return

def onOnToOff(channel, sampleIndex, val, prev):
    return

def whileOff(channel, sampleIndex, val, prev):
    return

def onValueChange(channel, sampleIndex, val, prev):
    on = bool(channel)
    if on:
        track_name = get_name_of_track()
        turn_on_visual(track_name)
    else:
        turn_on_placeholder()
    return

def turn_on_visual(name: str) -> None:
    ableton_switcher = op("ableton_switcher")
    visual_name = f"{name}_visual"
    for index, connector in enumerate(ableton_switcher.inputs):
        operator = connector.parent()
        if operator.name == visual_name:
            operator.allowCooking = True
            ableton_switcher.par.index = index
        else:
            operator.allowCooking = False

    toggle_placeholder(True)

def turn_on_placeholder() -> None:
    op('placeholder').allowCooking = True
    toggle_placeholder(False)

def get_name_of_track() -> str:
    song_id = int(op("song_id")[0])
    # print(song_id)
    track_name = op("songs").cell(str(song_id), "song_name")
    # print(track_name)
    return track_name

def toggle_placeholder(is_on: bool) -> None:
    parent().par.Index = int(is_on)

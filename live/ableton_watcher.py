def onValueChange(channel, sampleIndex, val, prev):
    on = channel > 0
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

    toggle_visual(True)

def turn_on_placeholder() -> None:
    op('placeholder').allowCooking = True
    ableton_switcher = op("ableton_switcher")
    for connector in ableton_switcher.inputs:
        operator = connector.parent()
        operator.allowCooking = False
    toggle_visual(False)

def get_name_of_track() -> str:
    song_id = int(op("song_id")[0])
    # print(song_id)
    track_name = op("songs").cell(str(song_id), "song_name")
    # print(track_name)
    return track_name

def toggle_visual(is_on: bool) -> None:
    parent().par.Index = int(is_on)

def onOffToOn(channel, sampleIndex, val, prev):
    return

def whileOn(channel, sampleIndex, val, prev):
    return

def onOnToOff(channel, sampleIndex, val, prev):
    return

def whileOff(channel, sampleIndex, val, prev):
    return

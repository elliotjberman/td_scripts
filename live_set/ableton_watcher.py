DELAY_SECONDS = op('lag1').par.lag1
DISCONNECTED_VALUE = 0
TEMP_DISCONNECT_VALUE = -1
FPS = 60

def onValueChange(channelValue, sampleIndex, val, prev):
    if channelValue == TEMP_DISCONNECT_VALUE:
        return

    on = channelValue > DISCONNECTED_VALUE
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

    # Allows you to run things after a sleep period
    # in TD - sleep() will block
    run(op('toggle_visual').text, True, delayFrames = FPS * DELAY_SECONDS)

def turn_on_placeholder() -> None:
    op('placeholder').allowCooking = True
    ableton_switcher = op("ableton_switcher")
    for connector in ableton_switcher.inputs:
        visual_operator = connector.parent()
        run(op('turn_off_cook').text, visual_operator, delayFrames = FPS * DELAY_SECONDS)
    run(op('toggle_visual').text, False, delayFrames = 0)

def get_name_of_track() -> str:
    song_id = int(op("song_id")[0])
    track_name = op("songs").cell(str(song_id), "song_name")
    return track_name

def onOffToOn(channel, sampleIndex, val, prev):
    return

def whileOn(channel, sampleIndex, val, prev):
    return

def onOnToOff(channel, sampleIndex, val, prev):
    return

def whileOff(channel, sampleIndex, val, prev):
    return

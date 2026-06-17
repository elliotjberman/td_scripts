DELAY_SECONDS = op('lag1').par.lag1
DISCONNECTED_VALUE = 0
TEMP_DISCONNECT_VALUE = -1
FPS = 60
SONG_SLUG_PAR = "Songslug"
SONG_SLUG_SOURCE = "song_slug"


def onValueChange(channelValue, sampleIndex, val, prev):
    # Ableton can temporarily set the old numeric ID to -1; don't switch visuals
    # while that disconnect blip is in flight.
    if channelValue == TEMP_DISCONNECT_VALUE:
        return

    ableton_connected = channelValue > DISCONNECTED_VALUE or bool(get_current_song_slug())
    if ableton_connected:
        update_from_song_slug()
    else:
        turn_on_placeholder()

    return


def update_from_song_slug() -> None:
    song_slug = get_current_song_slug()
    if song_slug:
        turn_on_visual(song_slug)
    else:
        turn_on_placeholder()

    return


def turn_on_visual(song_slug: str) -> None:
    ableton_switcher = op("ableton_switcher")
    match = find_visual_for_song(song_slug)
    if match is None:
        print("No visual found for Songslug {!r}".format(song_slug))
        turn_on_placeholder()
        return

    match_index, match_operator = match
    for index, connector in enumerate(ableton_switcher.inputs):
        operator = connector.parent()
        if operator == match_operator:
            mod.common.enable_visual(operator)
            ableton_switcher.par.index = match_index
        else:
            mod.common.disable_visual(operator)

    # Allows you to run things after a sleep period
    # in TD - sleep() will block
    run(op('toggle_visual').text, True, delayFrames = FPS * DELAY_SECONDS)

    return

def turn_on_placeholder() -> None:
    op('placeholder').allowCooking = True
    ableton_switcher = op("ableton_switcher")
    for connector in ableton_switcher.inputs:
        visual_operator = connector.parent()
        run(op('disable_operator').text, visual_operator, delayFrames = FPS * DELAY_SECONDS)
    run(op('toggle_visual').text, False, delayFrames = 0)

    return


def find_visual_for_song(song_slug: str):
    target_slug = normalize_song_slug(song_slug)
    matches = []
    ableton_switcher = op("ableton_switcher")
    for index, connector in enumerate(ableton_switcher.inputs):
        operator = connector.parent()
        operator_slug = song_slug_for_visual(operator)
        if operator_slug == target_slug:
            matches.append((index, operator))

    if len(matches) > 1:
        print("Multiple visuals have Songslug {!r}; using {}".format(target_slug, matches[0][1].path))
    return matches[0] if matches else None


def song_slug_for_visual(operator) -> str:
    parameter = operator.par[SONG_SLUG_PAR]
    if parameter is not None and parameter.eval():
        return normalize_song_slug(parameter.eval())
    return infer_song_slug_from_name(operator.name)


def get_current_song_slug() -> str:
    slug = read_song_slug_source()
    if slug:
        return slug
    return get_legacy_song_slug()


def read_song_slug_source() -> str:
    source = op(SONG_SLUG_SOURCE)
    if source is None:
        return ""

    for reader in (_read_text_dat, _read_table_cell, _read_first_value):
        value = reader(source)
        if value:
            return parse_song_slug(value)
    return ""


def _read_text_dat(operator) -> str:
    try:
        return str(operator.text).strip()
    except Exception:
        return ""


def _read_table_cell(operator) -> str:
    try:
        return str(operator[0, 0]).strip()
    except Exception:
        return ""


def _read_first_value(operator) -> str:
    try:
        return str(operator[0]).strip()
    except Exception:
        return ""


def get_legacy_song_slug() -> str:
    song_id_operator = op("song_id")
    songs = op("songs")
    if song_id_operator is None or songs is None:
        return ""
    try:
        song_id = int(song_id_operator[0])
        track_name = songs.cell(str(song_id), "song_name")
    except Exception:
        return ""
    if track_name is None:
        return ""
    return parse_song_slug(track_name)


def parse_song_slug(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    marker = "[td:"
    marker_start = text.find(marker)
    if marker_start >= 0:
        marker_end = text.find("]", marker_start)
        if marker_end >= 0:
            return normalize_song_slug(text[marker_start + len(marker):marker_end])
    if text.startswith("td:"):
        return normalize_song_slug(text[3:])
    return normalize_song_slug(text)


def normalize_song_slug(value) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return "_".join(text.split())


def infer_song_slug_from_name(name: str) -> str:
    slug = str(name)
    for suffix in ("_visual_v2", "_visual", "_live_v2", "_live"):
        if slug.endswith(suffix):
            slug = slug[:-len(suffix)]
            break
    return normalize_song_slug(slug)


def onOffToOn(channel, sampleIndex, val, prev):
    return

def whileOn(channel, sampleIndex, val, prev):
    return

def onOnToOff(channel, sampleIndex, val, prev):
    return

def whileOff(channel, sampleIndex, val, prev):
    return

import random

def onStart():
    return

def iterate_string(input_string, reset_char, randomize):
    if len(input_string) == 0:
        return input_string

    i = random.randint(0, len(input_string)-1)
    original_string = op('original_string').text
    original_length = min(len(input_string), len(original_string))
    if original_length == 0:
        reset_char = False
        j = 0
    else:
        j = random.randint(0, original_length-1)

    rand_char = chr(random.randint(65,123))
    chars = [char for char in input_string]

    if randomize:
        chars[i] = rand_char
    if reset_char:
        chars[j] = original_string[j]

    return "".join(chars)

def onCreate():
    return

def onExit():
    return

def onFrameStart(frame):
    input_op = op('current_string')

    if op('cooldown')[0] > 0:
        new_string = iterate_string(input_op.text, True, False)
        input_op.text = new_string
        return

    random_frames = int(parent().par.Randomframes)
    reset_frames = int(parent().par.Resetframes)
    if random_frames <= 0:
        return

    if frame % random_frames != 0:
        return

    reset_char = reset_frames > 0 and frame % reset_frames == 0
    new_string = iterate_string(input_op.text, reset_char, True)
    input_op.text = new_string
    return

def onFrameEnd(frame):
    return

def onPlayStateChange(state):
    return

def onDeviceChange():
    return

def onProjectPreSave():
    return

def onProjectPostSave():
    return


import random

def onStart():
    return

def iterate_string(input_string, reset_char, randomize):
    i = random.randint(0, len(input_string)-1)
    j = random.randint(0, len(input_string)-1)

    rand_char = chr(random.randint(65,123))
    original_char = op('original_string').text[j]
    chars = [char for char in input_string]

    if randomize:
        chars[i] = rand_char
    if reset_char:
        chars[j] = original_char

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

    if frame % parent().par.Randomframes != 0:
        return
    
    reset_char = frame % parent().par.Resetframes == 0
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


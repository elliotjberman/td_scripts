# me - this DAT
#
# frame - the current frame
# state - True if the timeline is paused
#
# Make sure the corresponding toggle is enabled in the Execute DAT.

import socket

LOCALHOST = "127.0.0.1"


def onStart():
    try:
        ip = socket.gethostbyname('elliot-macbook.local')
        op('ip').text = ip
    except socket.gaierror as e:
        print(e)
        op('ip').text = LOCALHOST


def onCreate():
    return


def onExit():
    return


def onFrameStart(frame):
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

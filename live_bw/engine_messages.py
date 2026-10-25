"""Receive one atomic project/engine observation from Bitwig."""


def onReceiveOSC(dat, rowIndex, message, bytes, timeStamp, address, args, peer):
    if address != '/live/engine/state' or len(args) != 2:
        raise ValueError('Unexpected audio-engine observation')
    parent.LiveMaster.ext.Router.EngineState(*args)

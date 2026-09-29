"""Rebaseline cue events when their source changes or Reset Baseline is pulsed."""


def onValueChange(par, prev):
    parent().op('routing_callback').module.reset()


def onPulse(par):
    parent().op('routing_callback').module.reset()

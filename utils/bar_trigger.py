"""Embedded CHOP Execute DAT in BarTrigger.tox; input is quarter-note time."""

import math


class Downbeats:
    def __init__(self):
        self.previous = None

    def step(self, position, playing, numerator, denominator, every, offset):
        if numerator <= 0 or denominator <= 0 or every < 1:
            raise ValueError('Time signature and Every Bars must be positive.')
        signature = (numerator, denominator)
        length = numerator * 4 / denominator
        bar = math.floor(position / length)
        previous = self.previous
        self.previous = (bar, playing, signature)
        if previous is None or not playing or position < 0 or signature != previous[2]:
            return None
        entered = bar != previous[0] or not previous[1]
        # Accept the first clock packet near the downbeat, never a mid-bar seek.
        near_start = position - bar * length < min(0.25, length / 4)
        if entered and near_start and bar % every == offset % every:
            return bar + 1
        return None


_downbeats = Downbeats()


def reset():
    _downbeats.previous = None


def onValueChange(channel, sampleIndex, val, prev):
    comp = parent()
    clock = comp.op('in1')
    if not comp.par.Enabled or not clock['connected'][sampleIndex]:
        reset()
        return
    bar = _downbeats.step(
        clock['position'][sampleIndex], bool(clock['playing'][sampleIndex]),
        clock['numerator'][sampleIndex], clock['denominator'][sampleIndex],
        int(comp.par.Everybars), int(comp.par.Baroffset))
    if bar is not None:
        comp.op('pulse').par.triggerpulse.pulse()

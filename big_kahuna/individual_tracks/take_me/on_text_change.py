# me - this DAT
#
# channel - the Channel object which has changed
# sampleIndex - the index of the changed sample
# val - the numeric value of the changed sample
# prev - the previous sample value
#
# Make sure the corresponding toggle is enabled in the CHOP Execute DAT.

import random

def onOffToOn(channel, sampleIndex, val, prev):
	phrases = [row[0] for row in op('phrases').rows()]
	low, high = parent().par.Minimum, parent().par.Maximum
	op('phrase').text = random.choice(phrases[low:high+1])
	return

def whileOn(channel, sampleIndex, val, prev):
	return

def onOnToOff(channel, sampleIndex, val, prev):
	return

def whileOff(channel, sampleIndex, val, prev):
	return

def onValueChange(channel, sampleIndex, val, prev):
	return

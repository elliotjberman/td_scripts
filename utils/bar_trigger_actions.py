"""Public actions and configuration reset for BarTrigger."""


def onPulse(par):
    if par.name == 'Trigger':
        parent().op('pulse').par.triggerpulse.pulse()
    elif par.name == 'Reset':
        parent().op('clock_events').module.reset()


def onValueChange(par, prev):
    parent().op('clock_events').module.reset()

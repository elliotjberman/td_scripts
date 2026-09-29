"""TD authoring recipe for the checked-in BarTrigger and ControlMap TOXs.

Call build(parent_comp) from TD Python with this module loaded from disk.
It creates two new COMPs; it does not save the project or connect a DAW.
"""
from pathlib import Path
from td import (baseCOMP, inCHOP, chopexecuteDAT, triggerCHOP, outCHOP,
                parameterexecuteDAT, mathCHOP, limitCHOP, lagCHOP, selectCHOP)

SOURCE_DIR = Path(__file__).resolve().parent


def parameter(page, style, name, value, help_text, minimum=None, maximum=None):
    p = getattr(page, 'append' + style)(name)[0]
    p.default = value
    p.val = value
    p.help = help_text
    if minimum is not None:
        p.min = p.normMin = minimum
        p.clampMin = True
    if maximum is not None:
        p.normMax = maximum
    return p


def node(comp, kind, name, x, y=100):
    op = comp.create(kind, name)
    op.nodeX, op.nodeY = x, y
    return op


def build(parent_comp):
    bar = parent_comp.create(baseCOMP, 'BarTrigger')
    bar.nodeX, bar.nodeY = 400, 200
    page = bar.appendCustomPage('Clock')
    parameter(page, 'Toggle', 'Enabled', False, 'Listen to the connected clock input.')
    parameter(page, 'Int', 'Everybars', 2, 'Trigger every N bars, counted from song position zero.', 1, 16)
    parameter(page, 'Int', 'Baroffset', 0, 'Zero-based bar offset: 0 selects bars 1, 1+N, and so on.', 0, 15)
    p = parameter(page, 'Pulse', 'Trigger', 0, 'Fire the output pulse manually, even when the clock is disabled.')
    p.startSection = True
    parameter(page, 'Float', 'Pulsewidth', 0.05, 'Native Trigger CHOP pulse duration in seconds.', 0.02, 0.5)
    parameter(page, 'Pulse', 'Reset', 0, 'Forget the previous clock position; the next update only establishes a baseline.')
    clock = node(bar, inCHOP, 'in1', -300)
    events = node(bar, chopexecuteDAT, 'clock_events', -300, -40)
    events.text = (SOURCE_DIR / 'bar_trigger.py').read_text()
    events.par.chop = 'in1'
    events.par.channel = '*'
    events.par.offtoon = events.par.whileon = events.par.ontooff = events.par.whileoff = False
    events.par.valuechange = True
    pulse = node(bar, triggerCHOP, 'pulse', 0)
    pulse.par.channame = 'trigger'
    pulse.par.attack = pulse.par.decay = pulse.par.release = pulse.par.sustain = 0
    pulse.par.peaklenunit = 'seconds'
    pulse.par.peaklen.expr = 'parent().par.Pulsewidth'
    pulse.par.multitrigger = 'restart'
    pulse.par.specifyrate = True
    pulse.par.rate.expr = 'project.cookRate'
    out = node(bar, outCHOP, 'out1', 160)
    out.inputConnectors[0].connect(pulse)
    actions = node(bar, parameterexecuteDAT, 'actions', 0, -40)
    actions.text = (SOURCE_DIR / 'bar_trigger_actions.py').read_text()
    actions.par.op = '..'
    actions.par.pars = 'Enabled Everybars Baroffset Trigger Reset'
    actions.par.valuechange = True
    actions.par.onpulse = True

    control = parent_comp.create(baseCOMP, 'ControlMap')
    control.nodeX, control.nodeY = 600, 200
    page = control.appendCustomPage('Mapping')
    parameter(page, 'Toggle', 'Enabled', True, 'When disabled, omit output channels so local visual controls retain ownership.')
    p = parameter(page, 'Float', 'Inputmin', 0, 'Incoming value corresponding to Output Minimum.')
    p.startSection = True
    parameter(page, 'Float', 'Inputmax', 1, 'Incoming value corresponding to Output Maximum; must differ from Input Minimum.')
    parameter(page, 'Float', 'Outputmin', 0, 'Mapped output at Input Minimum.')
    parameter(page, 'Float', 'Outputmax', 1, 'Mapped output at Input Maximum. May be below Output Minimum to reverse the mapping.')
    p = parameter(page, 'Float', 'Lagup', 0, 'Native Lag CHOP rise time in seconds; zero responds immediately.', 0, 2)
    p.startSection = True
    parameter(page, 'Float', 'Lagdown', 0, 'Native Lag CHOP fall time in seconds; zero responds immediately.', 0, 2)
    incoming = node(control, inCHOP, 'in1', 0)
    normalize = node(control, mathCHOP, 'normalize', 160)
    normalize.inputConnectors[0].connect(incoming)
    normalize.par.fromrange1.expr = 'parent().par.Inputmin'
    normalize.par.fromrange2.expr = 'parent().par.Inputmax'
    clamp = node(control, limitCHOP, 'clamp', 320)
    clamp.inputConnectors[0].connect(normalize)
    clamp.par.type = 'clamp'
    clamp.par.min = 0
    clamp.par.max = 1
    scale = node(control, mathCHOP, 'scale', 480)
    scale.inputConnectors[0].connect(clamp)
    scale.par.torange1.expr = 'parent().par.Outputmin'
    scale.par.torange2.expr = 'parent().par.Outputmax'
    lag = node(control, lagCHOP, 'lag', 640)
    lag.inputConnectors[0].connect(scale)
    lag.par.lag1.expr = 'parent().par.Lagup'
    lag.par.lag2.expr = 'parent().par.Lagdown'
    selected = node(control, selectCHOP, 'enabled_channels', 800)
    selected.par.chop = 'lag'
    selected.par.channames.expr = "'*' if parent().par.Enabled else ''"
    out = node(control, outCHOP, 'out1', 960)
    out.inputConnectors[0].connect(selected)
    return bar, control

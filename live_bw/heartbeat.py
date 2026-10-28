"""Embedded Heartbeat/send DAT: one local OSC packet per native timer cycle."""
import os
import uuid

_session = uuid.uuid4().hex
_sequence = 0


def start():
    global _session, _sequence
    # Module/storage saved state must never identify a new TOE session.
    _session = uuid.uuid4().hex
    _sequence = 0
    timer = parent().op('timer')
    timer.par.initialize.pulse()
    timer.par.start.pulse()


def send():
    global _sequence
    component = parent()
    master = component.par.State.eval()
    output = passive(component.par.Output.eval())
    status = master.par.Status.eval()
    state = ('loading' if master.par.Loading.eval() else
             'ready' if master.par.Ready.eval() else 'error')
    if 'ERROR' in status:
        state = 'error'
    visual_name = master.par.Currentvisual.eval()
    visual = master.op('visuals/' + visual_name) if visual_name else None
    present = visual is not None and visual.allowCooking and visual.op('out1') is not None
    _sequence += 1
    component.op('osc_out').sendOSC('/vs_set/td/heartbeat', [
        1, os.path.join(project.folder, project.name), _session, os.getpid(), _sequence,
        state, int(master.par.Loadcount), int(master.par.Loadtotal),
        master.par.Loadvisual.eval(), master.par.Loadstatus.eval(),
        visual_name, master.par.Currentproject.eval(), status,
        int(output.totalCooks), int(output.cookAbsFrame), output.width, output.height,
        int(present), int(ui.performMode),
    ])

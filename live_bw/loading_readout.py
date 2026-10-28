"""Presentation of the public SetLoader state; no preparation or routing logic."""


def Caption(state, progress):
    count = int(state.par.Loadcount.eval())
    total = int(state.par.Loadtotal.eval())
    name = state.par.Loadvisual.eval()
    status = state.par.Loadstatus.eval()
    if not state.par.Loading.eval() and not state.par.Ready.eval():
        return 'UNABLE TO LOAD SET\n\n' + status
    if not total:
        return status.upper()
    current = min(count + bool(name), total)
    label = name if name else ('READY' if state.par.Ready.eval() else status)
    blocks = round(float(progress[0]) * 48)
    bar = '\u2588' * blocks + '\u2591' * (48 - blocks)
    return f'{label.upper()}   |   {current} OF {total}\n\n[{bar}]\n{count} / {total} PREPARED'

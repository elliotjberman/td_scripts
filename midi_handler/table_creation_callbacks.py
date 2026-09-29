"""Create embedded note tables when a sibling *_midi source is discovered."""


def onFindOPGetInclude(dat, curOp, row):
    return True


def onOPFound(dat, curOp, row, results):
    handler = dat.parent()
    name = handler.NoteTableNameForTrack(curOp.name)
    if handler.op(name) is not None:
        return
    table = handler.create(tableDAT, name)
    table.clear()
    table.appendRow(handler.TableHeaders())
    # Match each source table to its last-note row, with a small gutter.
    table.nodeX = -150
    table.nodeY = -120 - (row - 1) * (table.nodeHeight + 30)

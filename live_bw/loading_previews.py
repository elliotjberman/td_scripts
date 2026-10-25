"""Optional presentation metadata refreshed by the native setlist DAT event."""
import json
from pathlib import Path


def Refresh(view):
    catalog = json.loads(view.par.Catalog.eval().text)
    filename = Path(view.par.Catalogfile.eval())
    if not filename.is_absolute():
        filename = Path(project.folder) / filename
    table = view.op('preview_paths')
    table.clear()
    table.appendRow(['visual', 'file', 'status'])
    for spec in catalog['visuals'].values():
        relative = spec.get('preview')
        path = (filename.parent / relative).resolve() if isinstance(relative, str) and relative else None
        exists = path is not None and path.is_file()
        table.appendRow([spec['name'], str(path) if exists else '',
                         'available' if exists else 'missing' if path else 'not specified'])


def Filename(view):
    cell = view.op('preview_paths')[view.par.State.eval().par.Loadvisual.eval(), 'file']
    return cell.val if cell is not None else ''

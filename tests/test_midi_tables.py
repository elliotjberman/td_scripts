"""New mapping tables must have headers in row zero, not below TD's empty row."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location('tables', Path(__file__).parents[1] / 'midi_handler/table_creation_callbacks.py')
tables = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tables)


class MappingTableTests(unittest.TestCase):
    def test_new_table_replaces_initial_empty_row(self):
        rows = [['']]
        table = SimpleNamespace(nodeHeight=90, clear=rows.clear, appendRow=rows.append)
        handler = SimpleNamespace(
            NoteTableNameForTrack=lambda name: 'synth_note_mappings',
            TableHeaders=lambda: ('note_number', 'trigger_name'),
            op=lambda name: None,
            create=lambda kind, name: table)
        tables.tableDAT = object()
        tables.onOPFound(SimpleNamespace(parent=lambda: handler),
                         SimpleNamespace(name='synth_midi'), 1, {})
        self.assertEqual(rows, [('note_number', 'trigger_name')])


if __name__ == '__main__':
    unittest.main()

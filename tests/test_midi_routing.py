"""One stale route must not suppress valid exact-note or wildcard targets."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location('routing', Path(__file__).parents[1] / 'midi_handler/extension.py')
routing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(routing)


class Envelope:
    def __init__(self):
        self.pulses = 0
        self.par = SimpleNamespace(Trigger=SimpleNamespace(pulse=self.trigger))
        self.values = {}

    def trigger(self):
        self.pulses += 1

    def store(self, name, value):
        self.values[name] = value


class RoutingTests(unittest.TestCase):
    def test_broken_route_does_not_suppress_other_targets(self):
        exact, wildcard = Envelope(), Envelope()
        targets = {'exact': exact, 'wildcard': wildcard}

        def resolve(name):
            if name not in targets:
                raise RuntimeError('Target does not exist')
            return targets[name]

        root = SimpleNamespace(path='/visual', opex=resolve)
        table = SimpleNamespace(cells=lambda note, column: ['deleted', 'exact'] if note == '60' else ['wildcard'])
        last_note = SimpleNamespace(par=SimpleNamespace(value0=0))
        children = {'/visual': root, 'synth_note_mappings': table, 'last_note_synth_midi': last_note}
        owner = SimpleNamespace(par=SimpleNamespace(Targetroot='/visual'), opex=children.__getitem__)
        routing.baseCOMP = Envelope
        routing.triggerCHOP = type('Trigger', (), {})
        handler = routing.TriggerExt(owner)
        with self.assertRaisesRegex(RuntimeError, '/visual/deleted'):
            handler.HandleNote('synth_midi', 60, 100)
        self.assertEqual((exact.pulses, wildcard.pulses), (1, 1))
        self.assertEqual((exact.values['velocity'], wildcard.values['velocity']), (100, 100))
        self.assertEqual(last_note.par.value0, 60)


if __name__ == '__main__':
    unittest.main()

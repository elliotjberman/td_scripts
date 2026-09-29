"""Transport boundary regressions; native CHOP integration is verified in TD."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('bar_trigger', Path(__file__).parents[1] / 'utils/bar_trigger.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DownbeatTests(unittest.TestCase):
    def setUp(self):
        self.clock = module.Downbeats()

    def step(self, position, playing=True, numerator=4, denominator=4, every=2, offset=0):
        return self.clock.step(position, playing, numerator, denominator, every, offset)

    def test_every_other_bar_and_no_duplicate(self):
        self.assertIsNone(self.step(0, False))
        self.assertEqual(self.step(0), 1)
        self.assertIsNone(self.step(0.04))
        self.assertIsNone(self.step(4))
        self.assertEqual(self.step(8.04), 3)

    def test_connect_mid_song_is_silent(self):
        self.assertIsNone(self.step(8))
        self.assertIsNone(self.step(8.05))
        self.assertIsNone(self.step(17))  # Mid-bar seek does not catch up.
        self.assertIsNone(self.step(17.1))

    def test_loop_and_resume_at_downbeat(self):
        self.step(12)
        self.assertEqual(self.step(0), 1)
        self.assertIsNone(self.step(0, False))
        self.assertEqual(self.step(0), 1)
        self.step(2, False)
        self.assertIsNone(self.step(2))

    def test_compound_meter_and_offset(self):
        self.step(0, False, 6, 8, offset=1)
        self.assertIsNone(self.step(0, numerator=6, denominator=8, offset=1))
        self.assertEqual(self.step(3, numerator=6, denominator=8, offset=1), 2)
        self.assertEqual(self.step(9, numerator=6, denominator=8, offset=1), 4)

    def test_signature_change_rebaselines(self):
        self.step(0)
        self.assertIsNone(self.step(6, numerator=3))
        self.assertEqual(self.step(12, numerator=3), 5)

    def test_invalid_clock_is_visible(self):
        with self.assertRaises(ValueError):
            self.step(0, denominator=0)


if __name__ == '__main__':
    unittest.main()

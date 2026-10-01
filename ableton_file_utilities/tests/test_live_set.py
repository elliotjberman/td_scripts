from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ableton_file_utilities.core import live_set  # noqa: E402


class LiveSetTests(unittest.TestCase):
    def test_format_hex_like_existing_preserves_wrapped_line_indent(self) -> None:
        existing = "AABB\n\tCCDD"

        formatted = live_set.format_hex_like_existing(existing, bytes.fromhex("00010203"), width=4)

        self.assertEqual(formatted, "0001\n\t0203")

    def test_copy_global_target_ids_preserves_source_wiring(self) -> None:
        source = '<AutomationTarget Id="101" /><ModulationTarget Id="102" />'
        target = '<AutomationTarget Id="901" /><ModulationTarget Id="902" />'

        copied = live_set.copy_global_target_ids(source, target)

        self.assertEqual(copied, source)


if __name__ == "__main__":
    unittest.main()

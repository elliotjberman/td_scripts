from __future__ import annotations

import re
import unittest

from ableton_utilities.live.global_macros import MAP8_SLOT_OBJECTS, _set_map8_min_percent


def min_param(name: str) -> str:
    return (
        '<MxDIntParameter Id="0">'
        f'<Name Value="{name}" />'
        '<Timeable><Manual Value="0" /></Timeable>'
        "</MxDIntParameter>"
    )


def manual_value(block: str, name: str) -> str:
    match = re.search(
        r'<MxDIntParameter\b[^>]*>.*?<Name Value="'
        + re.escape(name)
        + r'" />.*?<Manual Value="([^"]*)"',
        block,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


class GlobalMacroTests(unittest.TestCase):
    def test_known_map8_row_object_order(self) -> None:
        self.assertEqual(MAP8_SLOT_OBJECTS[:6], ("obj-16", "obj-5", "obj-8", "obj-10", "obj-11", "obj-12"))

    def test_sets_roll_volume_minimum_on_first_map8_row(self) -> None:
        block = "".join(
            min_param(name)
            for name in ("Min[10]", "Min[11]", "Min[1]", "Min[2]", "Min[3]", "Min[4]", "Min[8]", "Min[9]")
        )

        patched = _set_map8_min_percent(block, 0, "1")

        self.assertEqual(manual_value(patched, "Min[8]"), "1")
        self.assertEqual(manual_value(patched, "Min[1]"), "0")

    def test_sets_second_map8_row_minimum(self) -> None:
        block = min_param("Min[8]") + min_param("Min[9]")

        patched = _set_map8_min_percent(block, 1, "40")

        self.assertEqual(manual_value(patched, "Min[8]"), "0")
        self.assertEqual(manual_value(patched, "Min[9]"), "40")


if __name__ == "__main__":
    unittest.main()

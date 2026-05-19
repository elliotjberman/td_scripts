from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ableton_utilities.saturn2 import cli, vst3  # noqa: E402


def make_processor(mode: str) -> bytes:
    processor = bytearray(vst3.PROCESSOR_LENGTH)
    processor[: len(vst3.PROCESSOR_HEADER)] = vst3.PROCESSOR_HEADER
    processor[-len(vst3.PROCESSOR_TAIL) :] = vst3.PROCESSOR_TAIL
    processor[vst3.QUALITY_OFFSET : vst3.QUALITY_OFFSET + 4] = vst3.QUALITY_BYTES[vst3.canonical_mode(mode)]
    return bytes(processor)


def make_block(mode: str = "normal", processor: bytes | None = None) -> str:
    processor = processor or make_processor(mode)
    return f"""
<PluginDevice Id="1">
  <SourceContext>
    <BrowserContentPath Value="query:Plugins#VST3:FabFilter:Saturn%202" />
  </SourceContext>
  <PluginDesc>
    <Vst3PluginInfo Id="0">
      <Preset>
        <Vst3Preset Id="1">
          <ProcessorState>
            {processor.hex().upper()}
          </ProcessorState>
          <ControllerState>
            46533261030000000F00000044656661756C742053657474696E67FFFFFFFF010000000C0000007A65726F206C6174656E63790100000043755356010000000000000046466564000000000000803F
          </ControllerState>
        </Vst3Preset>
      </Preset>
      <Name Value="Saturn 2" />
    </Vst3PluginInfo>
  </PluginDesc>
</PluginDevice>
"""


class SaturnQualityTests(unittest.TestCase):
    def test_switches_known_processor_state_to_super_high_quality(self) -> None:
        result = vst3.patch_block(make_block("normal"), "super-high-quality")

        self.assertIsNone(result.warning)
        self.assertTrue(result.changed)
        patched = vst3.HEX_STATE_RE.search(result.block)
        processor = bytes.fromhex("".join(patched.group(2).split()))
        self.assertEqual(vst3.quality_mode(processor), "super_high_quality")

    def test_accepts_highest_quality_alias(self) -> None:
        self.assertEqual(vst3.canonical_mode("highest-quality"), "super_high_quality")

    def test_does_not_change_already_matching_quality(self) -> None:
        result = vst3.patch_block(make_block("high-quality"), "high-quality")

        self.assertIsNone(result.warning)
        self.assertFalse(result.changed)

    def test_refuses_unknown_processor_length(self) -> None:
        result = vst3.patch_block(make_block(processor=make_processor("normal") + b"\x00"), "high-quality")

        self.assertFalse(result.changed)
        self.assertIn("expected 3828", result.warning)

    def test_refuses_unknown_quality_bytes(self) -> None:
        processor = bytearray(make_processor("normal"))
        processor[vst3.QUALITY_OFFSET : vst3.QUALITY_OFFSET + 4] = b"\x00\x00@@"
        result = vst3.patch_block(make_block(processor=bytes(processor)), "high-quality")

        self.assertFalse(result.changed)
        self.assertIn("Unknown Saturn 2 quality bytes", result.warning)

    def test_patches_ableton_xml(self) -> None:
        xml = f"<Ableton>{make_block('normal')}{make_block('high-quality')}</Ableton>"

        patched_xml, reports = cli.patch_xml(xml, "super-high-quality")

        self.assertEqual(len(reports), 2)
        self.assertEqual(sum(1 for report in reports if report.changed), 2)
        states = [bytes.fromhex("".join(match.group(2).split())) for match in vst3.HEX_STATE_RE.finditer(patched_xml)]
        self.assertEqual([vst3.quality_mode(state) for state in states], ["super_high_quality", "super_high_quality"])


if __name__ == "__main__":
    unittest.main()


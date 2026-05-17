from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ableton_utilities import cli, proq3_vst3  # noqa: E402


def make_processor(mode: str) -> bytes:
    processor = bytearray(proq3_vst3.PROCESSOR_LENGTH)
    processor[: len(proq3_vst3.PROCESSOR_HEADER)] = proq3_vst3.PROCESSOR_HEADER
    processor[-len(proq3_vst3.PROCESSOR_TAIL) :] = proq3_vst3.PROCESSOR_TAIL
    value = proq3_vst3.MODE_BYTES[mode]
    offset = proq3_vst3.MODE_OFFSET
    processor[offset : offset + len(value)] = value
    return bytes(processor)


def make_block(mode: str = "natural_phase", processor: bytes | None = None) -> str:
    processor = processor or make_processor(mode)
    return f"""
<PluginDevice Id="1">
  <SourceContext>
    <BrowserContentPath Value="query:Plugins#VST3:FabFilter:Pro-Q%203" />
  </SourceContext>
  <PluginDesc>
    <Vst3PluginInfo Id="0">
      <Preset>
        <Vst3Preset Id="1">
          <ProcessorState>
            {processor.hex().upper()}
          </ProcessorState>
          <ControllerState>
            46513370030000000F00000044656661756C742053657474696E67FFFFFFFF010000000C0000007A65726F206C6174656E63790100000043755356010000000000000046466564000000000000803F
          </ControllerState>
          <Name Value="" />
        </Vst3Preset>
      </Preset>
      <Name Value="Pro-Q 3" />
    </Vst3PluginInfo>
  </PluginDesc>
</PluginDevice>
"""


class FabFilterProQPhaseTests(unittest.TestCase):
    def test_switches_known_processor_state_to_zero_latency(self) -> None:
        result = proq3_vst3.patch_block(make_block("natural_phase"), "zero_latency")

        self.assertIsNone(result.warning)
        self.assertTrue(result.changed)
        patched = proq3_vst3.HEX_STATE_RE.search(result.block)
        processor = bytes.fromhex("".join(patched.group(2).split()))
        self.assertEqual(
            processor[proq3_vst3.MODE_OFFSET : proq3_vst3.MODE_OFFSET + 4],
            proq3_vst3.MODE_BYTES["zero_latency"],
        )

    def test_refuses_unknown_processor_length(self) -> None:
        bad_processor = make_processor("natural_phase") + b"\x00"
        result = proq3_vst3.patch_block(make_block(processor=bad_processor), "zero_latency")

        self.assertFalse(result.changed)
        self.assertIn("expected 1456", result.warning)

    def test_refuses_unknown_current_mode_bytes(self) -> None:
        processor = bytearray(make_processor("natural_phase"))
        processor[proq3_vst3.MODE_OFFSET : proq3_vst3.MODE_OFFSET + 4] = bytes.fromhex(
            "DEADBEEF"
        )
        result = proq3_vst3.patch_block(make_block(processor=bytes(processor)), "zero_latency")

        self.assertFalse(result.changed)
        self.assertIn("Unknown mode bytes", result.warning)

    def test_does_not_patch_controller_state_text(self) -> None:
        result = proq3_vst3.patch_block(make_block("natural_phase"), "zero_latency")

        self.assertIn("7A65726F206C6174656E6379", result.block)
        self.assertTrue(result.changed)

    def test_patches_ableton_xml_once(self) -> None:
        xml = f"<Ableton>{make_block('natural_phase')}</Ableton>"
        patched_xml, reports = cli.patch_xml(xml, "zero_latency")

        self.assertEqual(len(reports), 1)
        self.assertTrue(reports[0].changed)
        self.assertIn("00000000", patched_xml)


if __name__ == "__main__":
    unittest.main()

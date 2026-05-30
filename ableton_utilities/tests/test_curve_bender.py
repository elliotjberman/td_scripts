from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ableton_utilities import curve_bender, live_set  # noqa: E402
import write_curve_bender_to_proq  # noqa: E402


def param(name: str, value: float, parameter_id: int = 0) -> str:
    return f"""
<PluginFloatParameter Id="{parameter_id}">
  <ParameterName Value="{name}" />
  <ParameterId Value="{parameter_id}" />
  <ParameterValue>
    <Manual Value="{value}" />
  </ParameterValue>
</PluginFloatParameter>
"""


def block(params: list[str]) -> str:
    return f"""
<PluginDevice>
  <On><Manual Value="true" /></On>
  <IsOn Value="true" />
  <SourceContext>
    <BrowserContentPath Value="query:Plugins#VST3:Universal%20Audio:UAD%20Chandler%20Limited%20Curve%20Bender" />
  </SourceContext>
  <Name Value="UAD Chandler Limited Curve Bender" />
  <ParameterList>
    {"".join(params)}
  </ParameterList>
</PluginDevice>
"""


def proq_block() -> str:
    from test_fabfilter_proq_phase import make_block  # noqa: PLC0415

    return make_block("natural_phase")


class CurveBenderTests(unittest.TestCase):
    def test_builds_mid_side_plan_and_skips_zero_gain_bands(self) -> None:
        plan = curve_bender.plan_block(
            block(
                [
                    param("Link Channels", 0),
                    param("Mid/Side Processing", 1),
                    param("Left/Mid In", 1),
                    param("Right/Side In", 1),
                    param("L High Pass", 0),
                    param("L Low Pass", 1),
                    param("L Bass Peak/Shelf", 0),
                    param("L Bass Frequency", 0.571428597),
                    param("L Bass Gain", 0.6000000238),
                    param("L Bass Multiplier", 0),
                    param("R High Pass", 0.1000000015),
                    param("R Low Pass", 1),
                    param("R Bass Peak/Shelf", 1),
                    param("R Bass Frequency", 0.571428597),
                    param("R Bass Gain", 0.5),
                    param("R Bass Multiplier", 0),
                ]
            )
        )

        self.assertFalse(plan.linked)
        self.assertTrue(plan.mid_side)
        self.assertEqual(len(plan.bands), 2)
        self.assertEqual(plan.bands[0].channel, "mid")
        self.assertEqual(plan.bands[0].kind, "low_shelf")
        self.assertAlmostEqual(plan.bands[0].gain_db, 1.0)
        self.assertEqual(plan.bands[0].q, 0.2)
        self.assertEqual(plan.bands[1].channel, "side")
        self.assertEqual(plan.bands[1].kind, "high_pass")

    def test_linked_plan_uses_stereo_left_side(self) -> None:
        plan = curve_bender.plan_params(
            {
                "Link Channels": 1,
                "Mid/Side Processing": 0,
                "Left/Mid In": 1,
                "L Presence 1 Frequency": 0.625,
                "L Presence 1 Gain": 0.75,
                "L Presence 1 Multiplier": 1,
            }
        )

        self.assertEqual(len(plan.bands), 1)
        self.assertEqual(plan.bands[0].channel, "stereo")
        self.assertEqual(plan.bands[0].kind, "bell")
        self.assertAlmostEqual(plan.bands[0].gain_db, 3.75)
        self.assertEqual(plan.bands[0].q, 0.75)

    def test_curve_bender_conversion_uses_nearest_proq_in_same_chain(self) -> None:
        params = [
            param("Link Channels", 1),
            param("Left/Mid In", 1),
            param("L High Pass", 0),
            param("L Low Pass", 1),
            param("L Bass Frequency", 0.571428597),
            param("L Bass Gain", 0.6000000238),
        ]
        xml = f"""
<Ableton>
  <LiveSet><Tracks><AudioTrack Id="1"><DeviceChain><Devices>
    {proq_block()}
    {block(params)}
    {proq_block()}
  </Devices></DeviceChain></AudioTrack></Tracks>
  <EffectiveName Value="Pro-Q 3 | UAD Chandler Limited Curve Bender | Saturn 2" />
  </LiveSet>
</Ableton>
"""

        _xml, reports = write_curve_bender_to_proq.patch_xml(xml)

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].proq_index, 2)
        self.assertFalse(reports[0].created_proq)
        self.assertTrue(reports[0].curve_bender_removed)
        self.assertNotIn("Curve%20Bender", _xml)
        self.assertNotIn("UAD Chandler Limited Curve Bender", _xml)
        self.assertIn('EffectiveName Value="Pro-Q 3 | Saturn 2"', _xml)

    def test_curve_bender_conversion_can_clone_proq_template(self) -> None:
        params = [
            param("Link Channels", 1, 1),
            param("Left/Mid In", 1, 2),
            param("L High Pass", 0, 3),
            param("L Low Pass", 1, 4),
            param("L Bass Frequency", 0.571428597, 5),
            param("L Bass Gain", 0.6000000238, 6),
        ]
        xml = f"""
<Ableton>
  <LiveSet>
    <NextPointeeId Value="100" />
    <Tracks><AudioTrack Id="1"><DeviceChain><Devices>
      {block(params)}
    </Devices></DeviceChain></AudioTrack></Tracks>
  </LiveSet>
</Ableton>
"""

        patched, reports = write_curve_bender_to_proq.patch_xml(xml, proq_block())

        self.assertEqual(len(reports), 1)
        self.assertTrue(reports[0].created_proq)
        self.assertIn("Pro-Q%203", patched)
        self.assertNotIn("Curve%20Bender", patched)
        self.assertIn('<NextPointeeId Value="100"', patched)
        live_set.validate_xml(patched)


if __name__ == "__main__":
    unittest.main()

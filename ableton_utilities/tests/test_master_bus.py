from __future__ import annotations

import unittest

from ableton_utilities import live_set
from ableton_utilities.live.master_bus import TDA_MASTER_MARKER, ensure_tda_master


def live_xml(master_device: str, next_id: int = 100) -> str:
    return (
        "<Ableton><LiveSet><Tracks />"
        "<MasterTrack><DeviceChain><Mixer />"
        f"<DeviceChain><Devices>{master_device}</Devices><SignalModulations /></DeviceChain>"
        "</DeviceChain></MasterTrack>"
        f'<NextPointeeId Value="{next_id}" /></LiveSet></Ableton>'
    )


def tda_master_device() -> str:
    return (
        '<MxDeviceAudioEffect Id="7"><LomId Value="40" />'
        '<On><LomId Value="41" /><AutomationTarget Id="200" /></On>'
        '<Pointee Id="201" /><UserName Value="" />'
        '<SourceContext><Value><RelativePath Value="Remote Scripts/TouchDesigner/TDA_Master.amxd" />'
        "</Value></SourceContext></MxDeviceAudioEffect>"
    )


class MasterBusTests(unittest.TestCase):
    def test_appends_template_tda_master_to_master_bus(self) -> None:
        source = live_xml('<GlueCompressor Id="0"><LomId Value="0" /><Pointee Id="10" /></GlueCompressor>')
        template = live_xml(tda_master_device(), next_id=300)

        result = ensure_tda_master(source, template, 100)
        patched = live_set.set_next_pointee_id(result.xml, result.next_global_id)

        self.assertTrue(result.added)
        self.assertIn(TDA_MASTER_MARKER, patched)
        self.assertIn('<MxDeviceAudioEffect Id="1">', patched)
        self.assertIn('<AutomationTarget Id="100"', patched)
        self.assertIn('<Pointee Id="101"', patched)
        self.assertNotIn('<LomId Value="40"', patched)
        live_set.validate_xml(patched)

    def test_does_not_duplicate_existing_tda_master(self) -> None:
        source = live_xml(tda_master_device())

        result = ensure_tda_master(source, source, 100)

        self.assertFalse(result.added)
        self.assertEqual(result.xml.count(TDA_MASTER_MARKER), 1)


if __name__ == "__main__":
    unittest.main()

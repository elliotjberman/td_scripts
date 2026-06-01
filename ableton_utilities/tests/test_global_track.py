from __future__ import annotations

import unittest

from ableton_utilities import live_set
from ableton_utilities.hardware_xml import parse_tracks
from ableton_utilities.live.global_track import SETLIST_DEVICE_MARKER, ensure_global_track


def live_xml(track: str, next_id: int = 100) -> str:
    return f"<Ableton><LiveSet><Tracks>{track}</Tracks><NextPointeeId Value=\"{next_id}\" /></LiveSet></Ableton>"


def name_block(name: str = "Global") -> str:
    return f'<Name><EffectiveName Value="{name}" /><UserName Value="{name}" /></Name>'


def global_track(tag: str, devices: str) -> str:
    return (
        f'<{tag} Id="1"><LomId Value="0" />{name_block()}<TrackGroupId Value="-1" />'
        f"<DeviceChain><DeviceChain><Devices>{devices}</Devices><SignalModulations /></DeviceChain></DeviceChain>"
        f"</{tag}>"
    )


def setlist_device() -> str:
    return (
        '<MxDeviceMidiEffect Id="7"><LomId Value="40" /><On><LomId Value="41" />'
        '<AutomationTarget Id="200" /></On><Pointee Id="201" />'
        '<PatchSlot><Value><MxDPatchRef Id="0"><FileRef>'
        '<RelativePath Value="../../../../../setlist_manager/setlist-device.amxd" />'
        '<Path Value="C:/Users/Elliot/setlist_manager/setlist-device.amxd" />'
        "</FileRef></MxDPatchRef></Value></PatchSlot></MxDeviceMidiEffect>"
    )


def map8_rack() -> str:
    return (
        '<AudioEffectGroupDevice Id="0"><LomId Value="0" />'
        '<PatchSlot><Value><RelativePath Value="Max Audio Effect/Control Devices/Map8.amxd" /></Value></PatchSlot>'
        "</AudioEffectGroupDevice>"
    )


class GlobalTrackTests(unittest.TestCase):
    def test_existing_global_is_midi_track_with_setlist_before_map8(self) -> None:
        source = live_xml(global_track("AudioTrack", map8_rack()))
        template = live_xml(global_track("MidiTrack", setlist_device() + map8_rack()))

        result = ensure_global_track(source, template, 2, 100)
        patched = live_set.set_next_pointee_id(result.xml, result.next_global_id)
        global_track_block = next(track for track in parse_tracks(patched) if track.name == "Global").block

        self.assertFalse(result.added)
        self.assertEqual(parse_tracks(patched)[0].tag, "MidiTrack")
        self.assertIn(SETLIST_DEVICE_MARKER, global_track_block)
        self.assertLess(global_track_block.index(SETLIST_DEVICE_MARKER), global_track_block.index("Map8.amxd"))
        self.assertIn('<ReWireSlaveMidiTargetId Value="3" />', global_track_block)
        self.assertIn('<PitchbendRange Value="96" />', global_track_block)
        self.assertIn('<AutomationTarget Id="100"', global_track_block)
        self.assertIn('<Pointee Id="101"', global_track_block)
        live_set.validate_xml(patched)

    def test_missing_global_is_cloned_and_normalized(self) -> None:
        source = live_xml('<MidiTrack Id="1"><LomId Value="0" />' + name_block("Drums") + "</MidiTrack>")
        template = live_xml(global_track("AudioTrack", setlist_device() + map8_rack()))

        result = ensure_global_track(source, template, 2, 100)
        patched = live_set.set_next_pointee_id(result.xml, result.next_global_id)
        global_track_block = next(track for track in parse_tracks(patched) if track.name == "Global").block

        self.assertTrue(result.added)
        self.assertEqual(next(track for track in parse_tracks(patched) if track.name == "Global").tag, "MidiTrack")
        self.assertIn(SETLIST_DEVICE_MARKER, global_track_block)
        live_set.validate_xml(patched)


if __name__ == "__main__":
    unittest.main()

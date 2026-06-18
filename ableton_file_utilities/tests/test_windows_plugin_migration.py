from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ableton_file_utilities.plugins.migration import windows_plugins as migration  # noqa: E402


SCANNER = """
2026-06-16T23:13:55.960608: info: VST3: found: OTT
   vendor: Xfer Records
   device-class-id: device:vst3:audiofx:56535458-6654-546f-7474-000000000000?n=OTT
   path: "/Library/Audio/Plug-Ins/VST3/OTT.vst3"
2026-06-16T23:16:47.884597: info: VST2: found: OTT
   vendor: Xfer Records
   device-class-id: device:vst:audiofx:1483101268?n=OTT
   path: "/Library/Audio/Plug-Ins/VST/OTT.vst"
2026-06-17T18:00:00.000000: info: VST3: found: Permut8
   vendor: Sonic Charge
   device-class-id: device:vst3:audiofx:5653544e-7550-7270-6572-6d7574380000?n=Permut8
   path: "/Library/Audio/Plug-Ins/VST3/Sonic Charge/Permut8.vst3"
2026-06-17T18:00:01.000000: info: VST2: found: Permut8
   vendor: Sonic Charge
   device-class-id: device:vst:audiofx:1316311154?n=Permut8
   path: "/Library/Audio/Plug-Ins/VST/Sonic Charge/Permut8.vst"
2026-06-17T22:24:00.000000: info: VST3: found: Sie-Q
   vendor: Soundtoys
   device-class-id: device:vst3:audiofx:56535453-7453-7173-6965-710000000000?n=Sie-Q
   path: "/Library/Audio/Plug-Ins/VST3/Soundtoys/SieQ.vst3"
2026-06-17T22:24:01.000000: info: VST2: found: SieQ
   vendor: Soundtoys
   device-class-id: device:vst:audiofx:1400132465?n=SieQ
   path: "/Library/Audio/Plug-Ins/VST/Soundtoys/SieQ.vst"
2026-06-17T16:09:24.068263: info: VST3: found: elysia nvelope
   vendor: Plugin Alliance
   device-class-id: device:vst3:audiofx:5653546e-766c-7065-6c79-736961206e76?n=elysia%20nvelope
   path: "/Library/Audio/Plug-Ins/VST3/elysia nvelope.vst3"
"""


def vst2_block() -> str:
    return """
<PluginDevice Id="2">
  <SourceContext>
    <Value>
      <BranchSourceContext Id="0">
        <BrowserContentPath Value="query:Plugins#VST:Local:OTT" />
        <BranchDeviceId Value="device:vst:audiofx:1483101268?n=OTT" />
      </BranchSourceContext>
    </Value>
  </SourceContext>
  <PluginDesc>
    <VstPluginInfo Id="0">
      <Path Value="C:/Program Files/Common Files/VST2/OTT_x64.dll" />
      <PlugName Value="OTT_x64" />
      <UniqueId Value="1483101268" />
      <Preset>
        <VstPreset Id="1">
          <UniqueId Value="1483101268" />
        </VstPreset>
      </Preset>
    </VstPluginInfo>
  </PluginDesc>
  <ParameterList>
    <PluginFloatParameter Id="0">
      <ParameterName Value="Depth" />
      <ParameterId Value="0" />
      <ParameterValue><Manual Value="0.25" /></ParameterValue>
    </PluginFloatParameter>
  </ParameterList>
</PluginDevice>
"""


def vst3_block() -> str:
    return """
<PluginDevice Id="4">
  <SourceContext>
    <Value>
      <BranchSourceContext Id="0">
        <BrowserContentPath Value="query:Plugins#VST3:Plugin%20Alliance:elysia%20nvelope" />
        <BranchDeviceId Value="device:vst3:audiofx:18716bb8-a2cf-2142-b5a3-bbdf77e70160" />
      </BranchSourceContext>
    </Value>
  </SourceContext>
  <PluginDesc>
    <Vst3PluginInfo Id="0">
      <Preset>
        <Vst3Preset Id="50">
          <Uid>
            <Fields.0 Value="410086328" />
            <Fields.1 Value="-1563483838" />
            <Fields.2 Value="-1247560737" />
            <Fields.3 Value="2011627872" />
          </Uid>
          <ProcessorState>00</ProcessorState>
        </Vst3Preset>
      </Preset>
      <Name Value="elysia nvelope" />
      <Uid>
        <Fields.0 Value="410086328" />
        <Fields.1 Value="-1563483838" />
        <Fields.2 Value="-1247560737" />
        <Fields.3 Value="2011627872" />
      </Uid>
    </Vst3PluginInfo>
  </PluginDesc>
</PluginDevice>
"""


def ott_vst3_template_block() -> str:
    return """
<PluginDevice Id="99">
  <SourceContext>
    <Value>
      <BranchSourceContext Id="0">
        <BrowserContentPath Value="query:Plugins#VST3:Xfer%20Records:OTT" />
        <BranchDeviceId Value="device:vst3:audiofx:56535458-6654-546f-7474-000000000000" />
      </BranchSourceContext>
    </Value>
  </SourceContext>
  <PluginDesc>
    <Vst3PluginInfo Id="0">
      <Preset>
        <Vst3Preset Id="11">
          <ProcessorState>0000803F00000000</ProcessorState>
        </Vst3Preset>
      </Preset>
      <Name Value="OTT" />
      <Uid>
        <Fields.0 Value="1448301656" />
        <Fields.1 Value="1716794479" />
        <Fields.2 Value="1953787904" />
        <Fields.3 Value="0" />
      </Uid>
    </Vst3PluginInfo>
  </PluginDesc>
  <ParameterList>
    <PluginFloatParameter Id="0">
      <ParameterName Value="Depth" />
      <ParameterId Value="0" />
      <ParameterValue><Manual Value="0.1" /></ParameterValue>
    </PluginFloatParameter>
  </ParameterList>
</PluginDevice>
"""


def permut8_vst2_block() -> str:
    return """
<PluginDevice Id="3">
  <On>
    <Manual Value="false" />
    <AutomationTarget Id="77">
      <LockEnvelope Value="0" />
    </AutomationTarget>
  </On>
  <SourceContext>
    <Value>
      <BranchSourceContext Id="0">
        <BrowserContentPath Value="query:Plugins#VST:Local:Sonic%20Charge:Permut8" />
        <BranchDeviceId Value="device:vst:audiofx:1316311154?n=Permut8" />
      </BranchSourceContext>
    </Value>
  </SourceContext>
  <PluginDesc>
    <VstPluginInfo Id="0">
      <Path Value="C:/Program Files/Common Files/VST2/Sonic Charge/Permut8.dll" />
      <PlugName Value="Permut8" />
      <UniqueId Value="1316311154" />
      <Preset>
        <VstPreset Id="1">
          <ProgramNumber Value="7" />
          <Buffer>1D6A59F3FD0A0000789C</Buffer>
        </VstPreset>
      </Preset>
    </VstPluginInfo>
  </PluginDesc>
  <ParameterList>
    <PluginFloatParameter Id="0">
      <ParameterName Value="Input Level" />
      <ParameterId Value="3" />
      <ParameterValue><Manual Value="0.5" /></ParameterValue>
    </PluginFloatParameter>
  </ParameterList>
</PluginDevice>
"""


def permut8_vst3_template_block() -> str:
    state = _permut8_vst3_state(bytes.fromhex("1D6A59F3C70B0000789C"))
    return f"""
<PluginDevice Id="101">
  <On>
    <Manual Value="true" />
    <AutomationTarget Id="88">
      <LockEnvelope Value="0" />
    </AutomationTarget>
  </On>
  <SourceContext>
    <Value>
      <BranchSourceContext Id="0">
        <BrowserContentPath Value="query:Plugins#VST3:Sonic%20Charge:Permut8" />
        <BranchDeviceId Value="device:vst3:audiofx:5653544e-7550-7270-6572-6d7574380000" />
      </BranchSourceContext>
    </Value>
  </SourceContext>
  <PluginDesc>
    <Vst3PluginInfo Id="0">
      <Preset>
        <Vst3Preset Id="11">
          <ProcessorState>{state.hex().upper()}</ProcessorState>
        </Vst3Preset>
      </Preset>
      <Name Value="Permut8" />
    </Vst3PluginInfo>
  </PluginDesc>
  <ParameterList>
    <PluginFloatParameter Id="0">
      <ParameterName Value="Input Level" />
      <ParameterId Value="3" />
      <ParameterValue><Manual Value="0.25" /></ParameterValue>
    </PluginFloatParameter>
  </ParameterList>
</PluginDevice>
"""


def _permut8_vst3_state(buffer: bytes, program_number: int = 1) -> bytes:
    state = bytearray(170 + len(buffer))
    state[0:4] = b"\x59\xa2\xcd\x18"
    state[5] = program_number
    state[6:8] = (len(state) - 10).to_bytes(2, "little")
    state[10:14] = b"CcnK"
    state[14:18] = (len(state) - 18).to_bytes(4, "big")
    state[168:170] = len(buffer).to_bytes(2, "big")
    state[170:] = buffer
    return bytes(state)


def sieq_vst2_block() -> str:
    return """
<PluginDevice Id="4">
  <On>
    <Manual Value="true" />
  </On>
  <SourceContext>
    <Value>
      <BranchSourceContext Id="0">
        <BrowserContentPath Value="query:Plugins#VST:Local:Soundtoys:SieQ" />
        <BranchDeviceId Value="device:vst:audiofx:1400132465?n=SieQ" />
      </BranchSourceContext>
    </Value>
  </SourceContext>
  <PluginDesc>
    <VstPluginInfo Id="0">
      <Path Value="C:/Program Files/Common Files/VST2/Soundtoys/SieQ.dll" />
      <PlugName Value="SieQ" />
      <UniqueId Value="1400132465" />
      <Preset>
        <VstPreset Id="1">
          <Buffer>574944474554203D205369652D513B0D535243</Buffer>
        </VstPreset>
      </Preset>
    </VstPluginInfo>
  </PluginDesc>
  <ParameterList>
    <PluginFloatParameter Id="0">
      <ParameterName Value="Bypass" />
      <ParameterId Value="0" />
      <ParameterValue><Manual Value="0" /></ParameterValue>
    </PluginFloatParameter>
    <PluginFloatParameter Id="1">
      <ParameterName Value="Low Gain" />
      <ParameterId Value="1" />
      <ParameterValue><Manual Value="0.25" /></ParameterValue>
    </PluginFloatParameter>
    <PluginFloatParameter Id="2">
      <ParameterName Value="Mid Gain" />
      <ParameterId Value="2" />
      <ParameterValue><Manual Value="0.5" /></ParameterValue>
    </PluginFloatParameter>
    <PluginFloatParameter Id="3">
      <ParameterName Value="Mid Frequency" />
      <ParameterId Value="3" />
      <ParameterValue><Manual Value="0.75" /></ParameterValue>
    </PluginFloatParameter>
    <PluginFloatParameter Id="4">
      <ParameterName Value="High Gain" />
      <ParameterId Value="4" />
      <ParameterValue><Manual Value="0.875" /></ParameterValue>
    </PluginFloatParameter>
    <PluginFloatParameter Id="5">
      <ParameterName Value="Drive" />
      <ParameterId Value="5" />
      <ParameterValue><Manual Value="0.125" /></ParameterValue>
    </PluginFloatParameter>
  </ParameterList>
</PluginDevice>
"""


def sieq_vst3_template_block() -> str:
    state = _sieq_vst3_state(b"WIDGET = Sie-Q;\rTEMPLATE")
    return f"""
<PluginDevice Id="102">
  <On>
    <Manual Value="true" />
  </On>
  <SourceContext>
    <Value>
      <BranchSourceContext Id="0">
        <BrowserContentPath Value="query:Plugins#VST3:Soundtoys:Sie-Q" />
        <BranchDeviceId Value="device:vst3:audiofx:56535453-7453-7173-6965-710000000000" />
      </BranchSourceContext>
    </Value>
  </SourceContext>
  <PluginDesc>
    <Vst3PluginInfo Id="0">
      <Preset>
        <Vst3Preset Id="11">
          <ProcessorState>{state.hex().upper()}</ProcessorState>
        </Vst3Preset>
      </Preset>
      <Name Value="Sie-Q" />
    </Vst3PluginInfo>
  </PluginDesc>
  <ParameterList>
    <PluginFloatParameter Id="0">
      <ParameterName Value="Low Gain" />
      <ParameterId Value="1" />
      <ParameterValue><Manual Value="0.767123282" /></ParameterValue>
    </PluginFloatParameter>
    <PluginFloatParameter Id="1">
      <ParameterName Value="Mid Gain" />
      <ParameterId Value="2" />
      <ParameterValue><Manual Value="0.3000000119" /></ParameterValue>
    </PluginFloatParameter>
    <PluginFloatParameter Id="2">
      <ParameterName Value="Mid Frequency" />
      <ParameterId Value="3" />
      <ParameterValue><Manual Value="0.8000000119" /></ParameterValue>
    </PluginFloatParameter>
    <PluginFloatParameter Id="3">
      <ParameterName Value="High Gain" />
      <ParameterId Value="4" />
      <ParameterValue><Manual Value="0.4033333361" /></ParameterValue>
    </PluginFloatParameter>
    <PluginFloatParameter Id="4">
      <ParameterName Value="Drive" />
      <ParameterId Value="5" />
      <ParameterValue><Manual Value="0.6399999857" /></ParameterValue>
    </PluginFloatParameter>
  </ParameterList>
</PluginDevice>
"""


def _sieq_vst3_state(buffer: bytes) -> bytes:
    state = bytearray(176 + len(buffer))
    state[0:4] = b"VstW"
    state[7] = 8
    state[11] = 1
    state[16:20] = b"CcnK"
    state[24:28] = b"FBCh"
    state[31] = 2
    state[32:36] = b"StSq"
    state[39] = 1
    state[43] = 1
    state[172:176] = len(buffer).to_bytes(4, "big")
    state[176:] = buffer
    state[20:24] = (len(state) - 24).to_bytes(4, "big")
    return bytes(state)


def parameter_block(depth: str, out_gain: str = "0.5") -> str:
    return f"""
<PluginDevice>
  <ParameterList>
    <PluginFloatParameter Id="0">
      <ParameterName Value="Depth" />
      <ParameterId Value="0" />
      <ParameterValue>
        <Manual Value="{depth}" />
        <MidiControllerRange><Min Value="0" /><Max Value="1" /></MidiControllerRange>
      </ParameterValue>
    </PluginFloatParameter>
    <PluginFloatParameter Id="1">
      <ParameterName Value="Out Gain" />
      <ParameterId Value="1" />
      <ParameterValue>
        <Manual Value="{out_gain}" />
        <MidiControllerRange><Min Value="0" /><Max Value="1" /></MidiControllerRange>
      </ParameterValue>
    </PluginFloatParameter>
  </ParameterList>
</PluginDevice>
"""


class WindowsPluginMigrationTests(unittest.TestCase):
    def test_scanner_parser_collects_vst2_and_vst3_candidates(self) -> None:
        plugins = migration.parse_plugin_scanner(SCANNER)

        self.assertEqual(len(plugins), 7)
        self.assertEqual(plugins[1].format, "VST2")
        self.assertEqual(plugins[1].name, "OTT")
        self.assertEqual(plugins[1].path, "/Library/Audio/Plug-Ins/VST/OTT.vst")

    def test_vst2_windows_path_and_name_are_rewritten_to_scanned_mac_bundle(self) -> None:
        xml, reports = migration.patch_xml(f"<Ableton>{vst2_block()}</Ableton>", migration.parse_plugin_scanner(SCANNER))

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].classification, "windows-vst2-name-and-path-restore-failure")
        self.assertTrue(reports[0].changed)
        self.assertIn('/Library/Audio/Plug-Ins/VST/OTT.vst', xml)
        self.assertIn('<PlugName Value="OTT" />', xml)
        self.assertIn('<UniqueId Value="1483101268" />', xml)

    def test_plugin_filter_matches_windows_x64_suffix(self) -> None:
        xml, reports = migration.patch_xml(
            f"<Ableton>{vst2_block()}</Ableton>",
            migration.parse_plugin_scanner(SCANNER),
            plugin_names={"OTT"},
        )

        self.assertEqual(len(reports), 1)
        self.assertIn('<PlugName Value="OTT" />', xml)

    def test_vst3_class_id_and_uid_fields_are_rewritten_to_scanned_mac_class(self) -> None:
        xml, reports = migration.patch_xml(f"<Ableton>{vst3_block()}</Ableton>", migration.parse_plugin_scanner(SCANNER))

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].classification, "windows-vst3-class-id-mismatch")
        self.assertTrue(reports[0].changed)
        self.assertIn('BranchDeviceId Value="device:vst3:audiofx:5653546e-766c-7065-6c79-736961206e76"', xml)
        self.assertNotIn("BranchDeviceId Value=\"device:vst3:audiofx:5653546e-766c-7065-6c79-736961206e76?n=", xml)
        self.assertIn('<Fields.0 Value="1448301678" />', xml)
        self.assertIn('<Fields.1 Value="1986818149" />', xml)
        self.assertIn('<Fields.2 Value="1819898729" />', xml)
        self.assertIn('<Fields.3 Value="1629515382" />', xml)

    def test_parameter_mapper_copies_visible_values_by_normalized_name(self) -> None:
        result = migration.map_parameter_values(parameter_block("0.875", "0.25"), parameter_block("0.1", "0.5"))

        self.assertEqual(len(result.mappings), 2)
        self.assertEqual(result.mappings[0].confidence, "exact-name")
        self.assertIn('<Manual Value="0.875" />', result.block)
        self.assertIn('<Manual Value="0.25" />', result.block)

    def test_parameter_mapper_scales_to_target_manual_range(self) -> None:
        target = parameter_block("0.1").replace('<Max Value="1" />', '<Max Value="100" />', 1)

        result = migration.map_parameter_values(parameter_block("0.25"), target)

        self.assertIn('<Manual Value="25" />', result.block)
        self.assertEqual(result.mappings[0].target_new_value, "25")

    def test_parameter_mapper_ignores_blank_parameter_names(self) -> None:
        source = parameter_block("0.875") + """
<PluginFloatParameter Id="2">
  <ParameterName Value="" />
  <ParameterValue><Manual Value="0.33" /></ParameterValue>
</PluginFloatParameter>
"""
        target = parameter_block("0.1") + """
<PluginFloatParameter Id="2">
  <ParameterName Value="" />
  <ParameterValue><Manual Value="0.44" /></ParameterValue>
</PluginFloatParameter>
"""
        result = migration.map_parameter_values(source, target)

        self.assertEqual([item.target_name for item in result.mappings], ["Depth", "Out Gain"])
        self.assertIn('<Manual Value="0.44" />', result.block)

    def test_vst2_template_clone_uses_mac_block_and_maps_parameters(self) -> None:
        source = vst2_block()
        template = (
            vst2_block()
            .replace('PluginDevice Id="2"', 'PluginDevice Id="99"', 1)
            .replace("C:/Program Files/Common Files/VST2/OTT_x64.dll", "/Library/Audio/Plug-Ins/VST/OTT.vst")
            .replace('<PlugName Value="OTT_x64" />', '<PlugName Value="OTT" />')
            .replace('<Manual Value="0.25" />', '<Manual Value="0.1" />')
        )

        xml, reports = migration.patch_xml(
            f'<Ableton><LiveSet><NextPointeeId Value="100" />{source}</LiveSet></Ableton>',
            migration.parse_plugin_scanner(SCANNER),
            reference_xml=f"<Ableton>{template}</Ableton>",
        )

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].classification, "vst2-template-clone-with-parameter-map")
        self.assertEqual(reports[0].parameters_mapped, 1)
        self.assertIn('PluginDevice Id="2"', xml)
        self.assertIn('/Library/Audio/Plug-Ins/VST/OTT.vst', xml)
        self.assertIn('<PlugName Value="OTT" />', xml)
        self.assertIn('<Manual Value="0.25" />', xml)
        self.assertIn('<NextPointeeId Value="100" />', xml)

    def test_vst2_source_can_clone_vst3_template_when_requested(self) -> None:
        xml, reports = migration.patch_xml(
            f'<Ableton><LiveSet><NextPointeeId Value="100" />{vst2_block()}</LiveSet></Ableton>',
            migration.parse_plugin_scanner(SCANNER),
            reference_xml=f"<Ableton>{ott_vst3_template_block()}</Ableton>",
            target_format="VST3",
        )

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].classification, "vst3-template-clone-with-parameter-map")
        self.assertEqual(reports[0].parameters_mapped, 1)
        self.assertEqual(reports[0].new_class_id, "device:vst3:audiofx:56535458-6654-546f-7474-000000000000")
        self.assertIn('PluginDevice Id="2"', xml)
        self.assertIn('BranchDeviceId Value="device:vst3:audiofx:56535458-6654-546f-7474-000000000000"', xml)
        self.assertIn('<Manual Value="0.25" />', xml)
        self.assertIn("<ProcessorState>0000803E00000000</ProcessorState>", xml)

    def test_permut8_vst3_template_clone_transplants_source_bank_buffer(self) -> None:
        xml, reports = migration.patch_xml(
            f'<Ableton><LiveSet><NextPointeeId Value="100" />{permut8_vst2_block()}</LiveSet></Ableton>',
            migration.parse_plugin_scanner(SCANNER),
            reference_xml=f"<Ableton>{permut8_vst3_template_block()}</Ableton>",
            target_format="VST3",
        )

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].classification, "vst3-template-clone-with-parameter-map")
        state_hex = re.search(r"<ProcessorState>(.*?)</ProcessorState>", xml, re.S).group(1)
        state = bytes.fromhex("".join(state_hex.split()))
        self.assertEqual(state[5], 7)
        self.assertEqual(int.from_bytes(state[6:8], "little"), len(state) - 10)
        self.assertEqual(int.from_bytes(state[14:18], "big"), len(state) - 18)
        self.assertEqual(int.from_bytes(state[168:170], "big"), 10)
        self.assertEqual(state[170:], bytes.fromhex("1D6A59F3FD0A0000789C"))
        on_value = re.search(r"<On>\s*.*?<Manual Value=\"([^\"]+)\"", xml, re.S).group(1)
        self.assertEqual(on_value, "false")
        on_target = re.search(r"<On>\s*.*?<AutomationTarget Id=\"([^\"]+)\"", xml, re.S).group(1)
        self.assertEqual(on_target, "77")

    def test_sieq_vst3_template_clone_transplants_soundtoys_preset_buffer(self) -> None:
        xml, reports = migration.patch_xml(
            f'<Ableton><LiveSet><NextPointeeId Value="100" />{sieq_vst2_block()}</LiveSet></Ableton>',
            migration.parse_plugin_scanner(SCANNER),
            reference_xml=f"<Ableton>{sieq_vst3_template_block()}</Ableton>",
            target_format="VST3",
        )

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].classification, "vst3-template-clone-with-parameter-map")
        state_hex = re.search(r"<ProcessorState>(.*?)</ProcessorState>", xml, re.S).group(1)
        state = bytes.fromhex("".join(state_hex.split()))
        self.assertEqual(int.from_bytes(state[20:24], "big"), len(state) - 24)
        self.assertEqual(int.from_bytes(state[172:176], "big"), len(b"WIDGET = Sie-Q;\rSRC"))
        self.assertEqual(state[176:], b"WIDGET = Sie-Q;\rSRC")
        self.assertIn('<Manual Value="0.25" />', xml)
        self.assertIn('<Manual Value="0.875" />', xml)

    def test_uuid_word_round_trip_matches_ableton_signed_fields(self) -> None:
        uuid_text = migration.uuid_from_signed_words([410086328, -1563483838, -1247560737, 2011627872])

        self.assertEqual(uuid_text, "18716bb8-a2cf-2142-b5a3-bbdf77e70160")
        self.assertEqual(
            migration.signed_words_from_uuid("5653546e-766c-7065-6c79-736961206e76"),
            [1448301678, 1986818149, 1819898729, 1629515382],
        )


if __name__ == "__main__":
    unittest.main()

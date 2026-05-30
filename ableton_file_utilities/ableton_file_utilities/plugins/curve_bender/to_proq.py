"""Write a Curve Bender plan into an existing FabFilter Pro-Q instance."""

from __future__ import annotations

import argparse
import dataclasses
import re
import sys
from pathlib import Path

from ableton_file_utilities.core import live_set
from ableton_file_utilities.plugins.curve_bender import planner as curve_bender
from ableton_file_utilities.plugins.proq3 import vst3 as proq3_vst3


@dataclasses.dataclass(frozen=True)
class ConversionReport:
    curve_bender_index: int
    proq_index: int
    created_proq: bool
    bands_written: int
    curve_bender_removed: bool


def convert_file(
    input_path: Path,
    output_path: Path | None = None,
    proq_template_path: Path | None = None,
) -> Path:
    document = live_set.read(input_path)
    template_xml = live_set.read(proq_template_path).xml if proq_template_path else None
    xml, reports = patch_xml(document.xml, template_xml)
    if not reports:
        raise ValueError("No Curve Bender devices found.")

    output = output_path or input_path.with_name(f"{input_path.stem}_curve_bender_to_proq{input_path.suffix}")
    live_set.write(document, output, xml)
    return output


def patch_xml(xml: str, template_xml: str | None = None) -> tuple[str, list[ConversionReport]]:
    devices = _devices(xml)
    template = _proq_template_block(xml) or (template_xml and _proq_template_block(template_xml))
    reports: list[ConversionReport] = []
    replacements: list[tuple[int, int, str]] = []
    used_proqs: set[int] = set()
    next_plugin_ids: dict[tuple[int, int] | None, int] = {}
    next_id: int | None = None

    for curve_index, device in enumerate((item for item in devices if item.kind == "curve_bender"), start=1):
        plan = curve_bender.plan_block(xml[device.start : device.end])
        if plan.skipped:
            raise ValueError(f"Curve Bender {curve_index} has skipped values: " + "; ".join(plan.skipped))

        target = _nearest_proq_in_chain(device, devices, used_proqs)
        created_proq = target is None
        if created_proq:
            if template is None:
                raise ValueError(f"No Pro-Q 3 target or clone template found for Curve Bender {curve_index}.")
            if next_id is None:
                next_id = live_set.next_pointee_id(xml)
            plugin_id = next_plugin_ids.get(device.devices_list)
            if plugin_id is None:
                plugin_id = _next_plugin_device_id(xml, device.devices_list)
            next_plugin_ids[device.devices_list] = plugin_id + 1
            proq_block, next_id = live_set.remap_cloned_plugin_device(template, plugin_id, next_id)
            target_index = _next_proq_index(devices, reports)
            replace_start = replace_end = device.end
        else:
            used_proqs.add(target.device_index)
            proq_block = xml[target.start : target.end]
            target_index = target.plugin_type_index
            replace_start, replace_end = target.start, target.end

        result = proq3_vst3.patch_block_bands(proq_block, plan.bands, "zero_latency")
        if result.warning:
            raise ValueError(result.warning)

        replacements.append((replace_start, replace_end, result.block))
        replacements.append((device.start, device.end, ""))
        reports.append(
            ConversionReport(
                curve_bender_index=curve_index,
                proq_index=target_index,
                created_proq=created_proq,
                bands_written=len(plan.bands),
                curve_bender_removed=True,
            )
        )

    replacements.sort(key=lambda item: item[0])
    patched = live_set.replace_ranges(xml, replacements)
    patched = _remove_curve_bender_effective_names(patched)
    if next_id is not None and next_id != live_set.next_pointee_id(xml):
        patched = live_set.set_next_pointee_id(patched, next_id)
    return patched, reports


@dataclasses.dataclass(frozen=True)
class _Device:
    start: int
    end: int
    kind: str
    device_index: int
    plugin_type_index: int
    chain: tuple[int, int] | None
    container: tuple[int, int] | None
    devices_list: tuple[int, int] | None


def _devices(xml: str) -> list[_Device]:
    chains = live_set.tag_ranges(xml, {"DeviceChain"})
    containers = live_set.tag_ranges(xml, {"AudioTrack", "MidiTrack", "GroupTrack", "ReturnTrack", "MasterTrack"})
    device_lists = live_set.tag_ranges(xml, {"Devices"})
    counters = {"curve_bender": 0, "proq": 0}
    devices: list[_Device] = []

    for start, end in live_set.iter_plugin_device_ranges(xml):
        block = xml[start:end]
        kind = None
        if curve_bender.is_curve_bender_block(block):
            kind = "curve_bender"
        elif proq3_vst3.is_proq3_block(block):
            kind = "proq"
        if kind is None:
            continue

        counters[kind] += 1
        devices.append(
            _Device(
                start=start,
                end=end,
                kind=kind,
                device_index=len(devices),
                plugin_type_index=counters[kind],
                chain=live_set.smallest_containing_range(chains, start, end),
                container=live_set.smallest_containing_range(containers, start, end),
                devices_list=live_set.smallest_containing_range(device_lists, start, end),
            )
        )
    return devices


def _nearest_proq_in_chain(
    curve_device: _Device,
    devices: list[_Device],
    used_proqs: set[int],
) -> _Device | None:
    candidates = [
        device
        for device in devices
        if device.kind == "proq" and device.chain == curve_device.chain and device.device_index not in used_proqs
    ]
    if not candidates:
        candidates = [
            device
            for device in devices
            if device.kind == "proq"
            and device.container == curve_device.container
            and device.device_index not in used_proqs
        ]
    if not candidates:
        return None
    return min(candidates, key=lambda item: (abs(item.device_index - curve_device.device_index), item.device_index < curve_device.device_index))


def _proq_template_block(xml: str) -> str | None:
    for start, end in live_set.iter_plugin_device_ranges(xml):
        block = xml[start:end]
        if proq3_vst3.is_proq3_block(block):
            return block
    return None


def _next_plugin_device_id(xml: str, devices_list: tuple[int, int] | None) -> int:
    if devices_list is None:
        return live_set.next_pointee_id(xml)
    devices_xml = xml[devices_list[0] : devices_list[1]]
    ids = [int(value) for value in re.findall(r"<PluginDevice\b[^>]*\bId=\"(\d+)\"", devices_xml)]
    return max(ids, default=-1) + 1


def _next_proq_index(devices: list[_Device], reports: list[ConversionReport]) -> int:
    existing = [device.plugin_type_index for device in devices if device.kind == "proq"]
    created = [report.proq_index for report in reports if report.created_proq]
    return max([*existing, *created], default=0) + 1


def _remove_curve_bender_effective_names(xml: str) -> str:
    def replace(match: re.Match[str]) -> str:
        value = match.group(2)
        parts = [part.strip() for part in value.split("|")]
        kept = [part for part in parts if "curve bender" not in part.lower()]
        return f"{match.group(1)}{' | '.join(kept)}{match.group(3)}"

    pattern = re.compile(r'(<EffectiveName\b[^>]*\bValue=")([^"]*Curve Bender[^"]*)(")', re.I)
    return pattern.sub(replace, xml)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write Curve Bender plans into Pro-Q 3 instances in an Ableton set.")
    parser.add_argument("session", type=Path, help="Path to an Ableton .als file.")
    parser.add_argument("--output", type=Path, help="Output .als path. Defaults to *_curve_bender_to_proq.als.")
    parser.add_argument("--proq-template", type=Path, help="Ableton set to clone a Pro-Q 3 from when the input has none.")
    args = parser.parse_args(argv)

    try:
        output = convert_file(args.session, args.output, args.proq_template)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

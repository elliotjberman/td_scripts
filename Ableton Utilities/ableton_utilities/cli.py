"""CLI for switching FabFilter Pro-Q 3 VST3 phase modes in Ableton sets."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from . import live_set, proq3_vst3


@dataclasses.dataclass(frozen=True)
class DeviceReport:
    device_index: int
    plugin_name: str
    old_value: str | None
    new_value: str | None
    changed: bool
    warning: str | None


@dataclasses.dataclass(frozen=True)
class ChangeReport:
    input_path: str
    output_path: str | None
    target_mode: str
    target_label: str
    dry_run: bool
    devices_seen: int
    devices_changed: int
    reports: list[DeviceReport]


def change_file(
    input_path: Path,
    mode: str,
    output_path: Path | None = None,
    write: bool = False,
    make_backup: bool = True,
) -> ChangeReport:
    target_mode = proq3_vst3.canonical_mode(mode)
    document = live_set.read(input_path)
    new_xml, reports = patch_xml(document.xml, target_mode)

    dry_run = not write and output_path is None
    resolved_output = None
    if not dry_run:
        resolved_output = output_path or input_path
        if resolved_output == input_path and make_backup:
            live_set.backup(input_path)
        live_set.write(document, resolved_output, new_xml)

    return ChangeReport(
        input_path=str(input_path),
        output_path=str(resolved_output) if resolved_output else None,
        target_mode=target_mode,
        target_label=proq3_vst3.MODE_LABELS[target_mode],
        dry_run=dry_run,
        devices_seen=len(reports),
        devices_changed=sum(1 for report in reports if report.changed),
        reports=reports,
    )


def patch_xml(xml: str, target_mode: str) -> tuple[str, list[DeviceReport]]:
    replacements: list[tuple[int, int, str]] = []
    reports: list[DeviceReport] = []

    for start, end in live_set.iter_plugin_device_ranges(xml):
        block = xml[start:end]
        if not proq3_vst3.is_proq3_block(block):
            continue
        result = proq3_vst3.patch_block(block, target_mode)
        reports.append(
            DeviceReport(
                device_index=len(reports) + 1,
                plugin_name=result.plugin_name,
                old_value=result.old_value,
                new_value=result.new_value,
                changed=result.changed,
                warning=result.warning,
            )
        )
        replacements.append((start, end, result.block))

    return live_set.replace_ranges(xml, replacements), reports


def report_to_dict(report: ChangeReport) -> dict[str, object]:
    return {
        "input_path": report.input_path,
        "output_path": report.output_path,
        "target_mode": report.target_mode,
        "target_label": report.target_label,
        "dry_run": report.dry_run,
        "devices_seen": report.devices_seen,
        "devices_changed": report.devices_changed,
        "devices": [dataclasses.asdict(device) for device in report.reports],
    }


def format_report(report: ChangeReport) -> str:
    action = "Dry run" if report.dry_run else "Wrote"
    lines = [
        f"{action}: {report.input_path}",
        f"Target mode: {report.target_label}",
        f"FabFilter Pro-Q 3 devices found: {report.devices_seen}",
        f"Devices changed: {report.devices_changed}",
    ]
    if report.output_path:
        lines.append(f"Output: {report.output_path}")

    for device in report.reports:
        lines.extend(format_device(device))
    return "\n".join(lines)


def format_device(device: DeviceReport) -> list[str]:
    lines = ["", f"[{device.device_index}] {device.plugin_name}"]
    if device.warning:
        lines.append(f"  skipped: {device.warning}")
        return lines
    marker = "changed" if device.changed else "already"
    lines.append(f"  {marker}: ProcessorState@{proq3_vst3.MODE_OFFSET}: {device.old_value} -> {device.new_value}")
    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Switch FabFilter Pro-Q 3 VST3 phase mode in an Ableton .als file.")
    parser.add_argument("session", type=Path, help="Path to an Ableton .als file.")
    parser.add_argument("--mode", required=True, help="Target mode: zero-latency or natural-phase.")
    parser.add_argument("--write", action="store_true", help="Modify the input file in place.")
    parser.add_argument("--output", type=Path, help="Write a changed copy instead of editing in place.")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup creation when using --write.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.write and args.output:
        parser.error("Use either --write or --output, not both.")

    try:
        report = change_file(args.session, args.mode, args.output, args.write, not args.no_backup)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report_to_dict(report), indent=2) if args.json else format_report(report))
    return 2 if report.devices_seen == 0 else 0


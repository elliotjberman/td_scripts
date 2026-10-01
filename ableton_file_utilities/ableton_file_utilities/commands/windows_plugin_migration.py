"""Command-line workflow for Windows-to-Mac plugin migration."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from ableton_file_utilities.core import live_set
from ableton_file_utilities.plugins.migration import windows_plugins


@dataclasses.dataclass(frozen=True)
class MigrationReport:
    input_path: str
    output_path: str | None
    dry_run: bool
    devices_seen: int
    devices_changed: int
    reports: list[windows_plugins.DeviceReport]


def migrate_file(
    input_path: Path,
    scanner_path: Path | None = None,
    output_path: Path | None = None,
    plugin_names: set[str] | None = None,
    reference_path: Path | None = None,
    target_format: str | None = None,
) -> MigrationReport:
    if (reference_path is None) != (target_format is None):
        raise ValueError("--reference-set and --target-format must be provided together.")
    if reference_path and not plugin_names:
        raise ValueError("Template cloning requires at least one --plugin filter.")
    if output_path:
        if output_path.resolve() == input_path.resolve():
            raise ValueError("Output path must not overwrite the input set.")
        if output_path.exists():
            raise ValueError(f"Output path already exists: {output_path}")

    scanner = (
        windows_plugins.parse_plugin_scanner(scanner_path.read_text("utf-8", errors="replace"))
        if scanner_path
        else []
    )
    reference_xml = live_set.read(reference_path).xml if reference_path else None
    document = live_set.read(input_path)
    new_xml, reports = windows_plugins.patch_xml(
        document.xml,
        scanner,
        plugin_names,
        reference_xml,
        target_format,
    )

    if output_path:
        live_set.write(document, output_path, new_xml)

    return MigrationReport(
        input_path=str(input_path),
        output_path=str(output_path) if output_path else None,
        dry_run=output_path is None,
        devices_seen=len(reports),
        devices_changed=sum(1 for item in reports if item.changed),
        reports=reports,
    )


def report_to_dict(report: MigrationReport) -> dict[str, object]:
    return {
        "input_path": report.input_path,
        "output_path": report.output_path,
        "dry_run": report.dry_run,
        "devices_seen": report.devices_seen,
        "devices_changed": report.devices_changed,
        "devices": [dataclasses.asdict(item) for item in report.reports],
    }


def format_report(report: MigrationReport) -> str:
    action = "Dry run" if report.dry_run else "Patched copy for"
    lines = [
        f"{action}: {report.input_path}",
        f"Plugin devices inspected: {report.devices_seen}",
        f"Devices changed: {report.devices_changed}",
    ]
    if report.output_path:
        lines.append(f"Output: {report.output_path}")

    for item in report.reports:
        lines.extend(
            [
                "",
                f"[{item.device_index}] {item.plugin_name} ({item.format})",
                f"  classification: {item.classification}",
            ]
        )
        if item.saved_path:
            lines.append(f"  saved path: {item.saved_path}")
        if item.new_path:
            lines.append(f"  new path: {item.new_path}")
        if item.saved_plug_name and item.new_plug_name:
            lines.append(f"  plug name: {item.saved_plug_name} -> {item.new_plug_name}")
        if item.new_class_id:
            lines.append(f"  class id: {item.saved_class_id} -> {item.new_class_id}")
        if item.template_source:
            lines.extend(
                [
                    f"  template source: {item.template_source}",
                    f"  parameters mapped: {item.parameters_mapped}",
                ]
            )
        if item.skipped_parameters:
            lines.append("  skipped parameters: " + ", ".join(item.skipped_parameters[:12]))
        if item.warning:
            lines.append(f"  warning: {item.warning}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan or patch Windows-saved plugin references in an Ableton .als file."
    )
    parser.add_argument("session", type=Path, help="Path to an Ableton .als file.")
    parser.add_argument("--scanner", type=Path, help="Ableton PluginScanner.txt from the target Mac.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Write a new patched copy. Without this, the command is report-only.",
    )
    parser.add_argument(
        "--plugin",
        action="append",
        help="Only inspect or patch this plugin name. Repeat for multiple names.",
    )
    parser.add_argument(
        "--reference-set",
        type=Path,
        help="Ableton set containing known-good Mac plugin devices to clone.",
    )
    parser.add_argument(
        "--target-format",
        choices=("VST2", "VST3"),
        help="Clone reference devices in this plugin format. Requires --reference-set.",
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        report = migrate_file(
            args.session,
            args.scanner,
            args.output,
            set(args.plugin or []),
            args.reference_set,
            args.target_format,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report_to_dict(report), indent=2) if args.json else format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

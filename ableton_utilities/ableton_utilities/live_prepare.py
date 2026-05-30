"""One-shot live preparation pipeline for Ableton sets."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from ableton_utilities import cli as proq_cli
from ableton_utilities import live_set
from ableton_utilities.saturn2 import cli as saturn_cli
import write_curve_bender_to_proq


@dataclasses.dataclass(frozen=True)
class LivePrepareReport:
    input_path: str
    output_path: str
    proq_devices_seen: int
    proq_devices_changed: int
    saturn_devices_seen: int
    saturn_devices_changed: int
    curve_benders_converted: int
    curve_bender_proqs_created: int


def prepare_file(
    input_path: Path,
    output_path: Path,
    saturn_mode: str = "normal",
    proq_template_path: Path | None = None,
) -> LivePrepareReport:
    if output_path == input_path:
        raise ValueError("Output path must not overwrite the input set.")
    if output_path.exists():
        raise ValueError(f"Output path already exists: {output_path}")

    document = live_set.read(input_path)
    template_xml = live_set.read(proq_template_path).xml if proq_template_path else None
    xml = document.xml

    xml, proq_reports = proq_cli.patch_xml(xml, "zero-latency")
    xml, saturn_reports = saturn_cli.patch_xml(xml, saturn_mode)
    xml, curve_reports = write_curve_bender_to_proq.patch_xml(xml, template_xml)

    live_set.write(document, output_path, xml)
    return LivePrepareReport(
        input_path=str(input_path),
        output_path=str(output_path),
        proq_devices_seen=len(proq_reports),
        proq_devices_changed=sum(1 for report in proq_reports if report.changed),
        saturn_devices_seen=len(saturn_reports),
        saturn_devices_changed=sum(1 for report in saturn_reports if report.changed),
        curve_benders_converted=len(curve_reports),
        curve_bender_proqs_created=sum(1 for report in curve_reports if report.created_proq),
    )


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_live{input_path.suffix}")


def format_report(report: LivePrepareReport) -> str:
    return "\n".join(
        [
            f"Wrote: {report.output_path}",
            f"Input: {report.input_path}",
            f"Pro-Q devices: {report.proq_devices_seen} seen, {report.proq_devices_changed} changed",
            f"Saturn 2 devices: {report.saturn_devices_seen} seen, {report.saturn_devices_changed} changed",
            f"Curve Benders converted: {report.curve_benders_converted}",
            f"Pro-Q devices created for Curve Bender: {report.curve_bender_proqs_created}",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare an Ableton set for low-latency live use.")
    parser.add_argument("session", type=Path, help="Path to the source Ableton .als file.")
    parser.add_argument("--output", type=Path, help="Output .als path. Defaults to *_live.als.")
    parser.add_argument("--saturn-mode", default="normal", help="Saturn target mode.")
    parser.add_argument("--proq-template", type=Path, help="Ableton set to clone a Pro-Q from if this set has none.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output = args.output or default_output_path(args.session)

    try:
        report = prepare_file(args.session, output, args.saturn_mode, args.proq_template)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(dataclasses.asdict(report), indent=2) if args.json else format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Write a Curve Bender plan into an existing FabFilter Pro-Q instance."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ableton_utilities import curve_bender, live_set, proq3_vst3


def convert_file(input_path: Path, output_path: Path | None = None) -> Path:
    document = live_set.read(input_path)
    plans = _curve_bender_plans(document.xml)
    proq_ranges = _proq_ranges(document.xml)
    if not plans:
        raise ValueError("No Curve Bender devices found.")
    if len(proq_ranges) < len(plans):
        raise ValueError(f"Found {len(plans)} Curve Benders but only {len(proq_ranges)} Pro-Q 3 devices.")

    replacements: list[tuple[int, int, str]] = []
    for index, plan in enumerate(plans):
        if plan.skipped:
            raise ValueError(f"Curve Bender {index + 1} has skipped values: " + "; ".join(plan.skipped))
        start, end = proq_ranges[index]
        result = proq3_vst3.patch_block_bands(document.xml[start:end], plan.bands, "zero_latency")
        if result.warning:
            raise ValueError(result.warning)
        replacements.append((start, end, result.block))

    output = output_path or input_path.with_name(f"{input_path.stem}_curve_bender_to_proq{input_path.suffix}")
    xml = live_set.replace_ranges(document.xml, replacements)
    live_set.write(document, output, xml)
    return output


def _curve_bender_plans(xml: str) -> list[curve_bender.CurveBenderPlan]:
    plans: list[curve_bender.CurveBenderPlan] = []
    for start, end in live_set.iter_plugin_device_ranges(xml):
        block = xml[start:end]
        if curve_bender.is_curve_bender_block(block):
            plans.append(curve_bender.plan_block(block))
    return plans


def _proq_ranges(xml: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for start, end in live_set.iter_plugin_device_ranges(xml):
        if proq3_vst3.is_proq3_block(xml[start:end]):
            ranges.append((start, end))
    return ranges


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write Curve Bender plans into Pro-Q 3 instances in an Ableton set.")
    parser.add_argument("session", type=Path, help="Path to an Ableton .als file.")
    parser.add_argument("--output", type=Path, help="Output .als path. Defaults to *_curve_bender_to_proq.als.")
    args = parser.parse_args(argv)

    try:
        output = convert_file(args.session, args.output)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

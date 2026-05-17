"""Write a Curve Bender plan into an existing FabFilter Pro-Q instance."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ableton_utilities import curve_bender, live_set, proq3_vst3


def convert_file(input_path: Path, output_path: Path | None = None) -> Path:
    document = live_set.read(input_path)
    plan = _single_curve_bender_plan(document.xml)
    if plan.skipped:
        raise ValueError("Curve Bender plan has skipped values: " + "; ".join(plan.skipped))

    proq_range = _first_proq_range(document.xml)
    start, end = proq_range
    block = document.xml[start:end]
    result = proq3_vst3.patch_block_bands(block, plan.bands, "zero_latency")
    if result.warning:
        raise ValueError(result.warning)

    output = output_path or input_path.with_name(f"{input_path.stem}_curve_bender_to_proq{input_path.suffix}")
    xml = live_set.replace_ranges(document.xml, [(start, end, result.block)])
    live_set.write(document, output, xml)
    return output


def _single_curve_bender_plan(xml: str) -> curve_bender.CurveBenderPlan:
    plans: list[curve_bender.CurveBenderPlan] = []
    for start, end in live_set.iter_plugin_device_ranges(xml):
        block = xml[start:end]
        if curve_bender.is_curve_bender_block(block):
            plans.append(curve_bender.plan_block(block))
    if len(plans) != 1:
        raise ValueError(f"Expected exactly one Curve Bender device; found {len(plans)}.")
    return plans[0]


def _first_proq_range(xml: str) -> tuple[int, int]:
    for start, end in live_set.iter_plugin_device_ranges(xml):
        if proq3_vst3.is_proq3_block(xml[start:end]):
            return start, end
    raise ValueError("No FabFilter Pro-Q 3 device found.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write one Curve Bender plan into the first Pro-Q 3 in an Ableton set.")
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

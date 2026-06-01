"""Add live External Instrument tracks next to old Expert Sleepers groups."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from ableton_utilities import live_set
from ableton_utilities.hardware.programs import parse_track_program
from ableton_utilities.live.global_macros import apply_boilerplate_global_macros
from ableton_utilities.live.global_track import ensure_global_track
from ableton_utilities.live.keymap import GLOBAL_FOCUS_TARGET, apply_global_focus_key
from ableton_utilities.hardware_xml import (
    build_live_track,
    external_instrument_templates,
    find_child,
    find_group,
    parse_tracks,
)


@dataclasses.dataclass(frozen=True)
class HardwareConfig:
    key: str
    group_name: str
    out_hint: str
    in_hint: str
    new_track_name: str
    proxy_name: str
    midi_target: str
    midi_upper: str
    midi_lower: str
    audio_target: str
    audio_upper: str
    audio_lower: str
    fallback_volume: str


CONFIGS = {
    "tetra": HardwareConfig(
        key="tetra",
        group_name="Tetra",
        out_hint="tetraout",
        in_hint="tetrain",
        new_track_name="TetraLive",
        proxy_name="TetraLive",
        midi_target="MidiOut/External.Dev:Arturia KeyStep 32/1",
        midi_upper="Arturia KeyStep 32",
        midi_lower="Ch. 2",
        audio_target="AudioIn/External/M6",
        audio_upper="Ext. In",
        audio_lower="7",
        fallback_volume="5.62341309",
    ),
    "moog": HardwareConfig(
        key="moog",
        group_name="Moog",
        out_hint="moogout",
        in_hint="moogin",
        new_track_name="MoogLive",
        proxy_name="MoogLive",
        midi_target="MidiOut/External.Dev:Arturia KeyStep 32/0",
        midi_upper="Arturia KeyStep 32",
        midi_lower="Ch. 1",
        audio_target="AudioIn/External/M7",
        audio_upper="Ext. In",
        audio_lower="8",
        fallback_volume="2.81838274",
    ),
}


@dataclasses.dataclass(frozen=True)
class ConversionReport:
    input_path: str
    output_path: str
    added_tracks: list[str]
    boilerplate_tracks: list[str]
    global_macros: list[str]
    key_mappings: list[str]
    warnings: list[str]
    muted_new_tracks: bool


def convert_file(
    input_path: Path,
    output_path: Path,
    template_path: Path | None = None,
    instruments: tuple[str, ...] = ("tetra", "moog"),
    mute_new_tracks: bool = True,
) -> ConversionReport:
    if output_path == input_path:
        raise ValueError("Output path must not overwrite the input set.")
    if output_path.exists():
        raise ValueError(f"Output path already exists: {output_path}")

    document = live_set.read(input_path)
    template_xml = live_set.read(template_path).xml if template_path else document.xml
    xml, added, boilerplate_tracks, global_macros, key_mappings, warnings = convert_xml(
        document.xml, template_xml, instruments, mute_new_tracks
    )
    live_set.write(document, output_path, xml)
    return ConversionReport(
        input_path=str(input_path),
        output_path=str(output_path),
        added_tracks=added,
        boilerplate_tracks=boilerplate_tracks,
        global_macros=global_macros,
        key_mappings=key_mappings,
        warnings=warnings,
        muted_new_tracks=mute_new_tracks,
    )


def convert_xml(
    xml: str,
    template_xml: str,
    instruments: tuple[str, ...],
    mute_new_tracks: bool = True,
) -> tuple[str, list[str], list[str], list[str], list[str], list[str]]:
    tracks = parse_tracks(xml)
    templates = external_instrument_templates(template_xml)
    fallback_template = next(iter(templates.values()), None)
    next_track_id = max((track.track_id for track in tracks), default=0) + 1
    next_global_id = live_set.next_pointee_id(xml)
    insertions: list[tuple[int, str]] = []
    added: list[str] = []
    boilerplate_tracks: list[str] = []
    key_mappings: list[str] = []
    warnings: list[str] = []

    for instrument in instruments:
        config = CONFIGS[instrument]
        group = find_group(tracks, config.group_name)
        if group is None:
            warnings.append(f"No {config.group_name} group was found.")
            continue
        children = [track for track in tracks if track.group_id == group.track_id]
        out_track = find_child(children, "MidiTrack", config.out_hint)
        in_track = find_child(children, "AudioTrack", config.in_hint)
        if out_track is None or in_track is None:
            warnings.append(f"{config.group_name} did not have the expected Out/In child tracks.")
            continue
        proxy = templates.get(config.key) or fallback_template
        if proxy is None:
            raise ValueError("No ProxyInstrumentDevice was found; pass --template-live-set.")
        program_selection = parse_track_program(out_track.name, config.key) or parse_track_program(
            group.name, config.key
        )
        new_track, next_global_id = build_live_track(
            group,
            out_track,
            proxy,
            config,
            next_track_id,
            next_global_id,
            mute_new_tracks,
            program_selection,
        )
        next_track_id += 1
        insertions.append((max(track.end for track in [group, *children]), new_track))
        added.append(config.new_track_name)

    for at, block in sorted(insertions, reverse=True):
        xml = f"{xml[:at]}\n{block}{xml[at:]}"
    result = ensure_global_track(xml, template_xml, next_track_id, next_global_id)
    xml, next_track_id, next_global_id = result.xml, result.next_track_id, result.next_global_id
    if result.added:
        boilerplate_tracks.append("Global")
    warnings.extend(result.warnings)
    xml = live_set.set_next_pointee_id(xml, next_global_id)
    xml, global_reports, global_warnings = apply_boilerplate_global_macros(xml)
    warnings.extend(global_warnings)
    xml, focus_mapped, focus_warnings = apply_global_focus_key(xml)
    if focus_mapped:
        key_mappings.append(f"/ -> {GLOBAL_FOCUS_TARGET}")
    warnings.extend(focus_warnings)
    live_set.validate_xml(xml)
    global_macros = [f"{report.name} -> {report.target} (LomId {report.lom_id})" for report in global_reports]
    return xml, added, boilerplate_tracks, global_macros, key_mappings, warnings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add live External Instrument tracks for Tetra and Moog.")
    parser.add_argument("session", type=Path, help="Source Ableton .als file.")
    parser.add_argument("--output", type=Path, required=True, help="Output .als path.")
    parser.add_argument("--template-live-set", type=Path, help="Set containing Tetra/Moog External Instrument tracks.")
    parser.add_argument("--instrument", choices=sorted(CONFIGS), action="append", help="Limit to one instrument.")
    parser.add_argument("--activate-new", action="store_true", help="Leave new tracks active instead of muted.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    instruments = tuple(args.instrument) if args.instrument else ("tetra", "moog")
    try:
        report = convert_file(args.session, args.output, args.template_live_set, instruments, not args.activate_new)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(dataclasses.asdict(report), indent=2) if args.json else format_report(report))
    return 0


def format_report(report: ConversionReport) -> str:
    lines = [f"Wrote: {report.output_path}", f"Input: {report.input_path}"]
    lines.append("New tracks: " + (", ".join(report.added_tracks) if report.added_tracks else "none"))
    lines.append(
        "Boilerplate tracks: " + (", ".join(report.boilerplate_tracks) if report.boilerplate_tracks else "none")
    )
    lines.append("Global macros: " + (", ".join(report.global_macros) if report.global_macros else "none"))
    lines.append("Key mappings: " + (", ".join(report.key_mappings) if report.key_mappings else "none"))
    lines.append(f"New tracks muted: {report.muted_new_tracks}")
    lines.extend(f"Warning: {warning}" for warning in report.warnings)
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

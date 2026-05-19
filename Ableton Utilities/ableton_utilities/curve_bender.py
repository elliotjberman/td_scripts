"""UAD Chandler Curve Bender parameter planning."""

from __future__ import annotations

import dataclasses
import hashlib
import re


CURVE_BENDER_RE = re.compile(r"(Curve%20Bender|Curve Bender)", re.I)
PARAM_RE = re.compile(r"<PluginFloatParameter\b[^>]*>(.*?)</PluginFloatParameter>", re.S)
PROCESSOR_STATE_RE = re.compile(r"<ProcessorState>\s*([0-9A-Fa-f\s]+?)\s*</ProcessorState>", re.I | re.S)

GAIN_DB_RANGE = 10.0
HIGH_Q_GAIN_MULTIPLIER = 1.5
NORMAL_BELL_Q = 0.50
HIGH_BELL_Q = 0.75
FILTER_SLOPE_DB_OCT = 6

HIGH_PASS_FREQS = {
    0.0: None,
    0.1000000015: 30.0,
}
LOW_PASS_FREQS = {
    1.0: None,
}
EQ_FREQS = {
    "Bass": {0.571428597: 150.0},
    "Presence 2": {0.625: 1200.0},
    "Presence 1": {0.625: 4200.0},
    "Treble": {0.625: 10000.0},
}


@dataclasses.dataclass(frozen=True)
class PlannedBand:
    channel: str
    source: str
    kind: str
    frequency_hz: float
    gain_db: float | None = None
    q: float | None = None
    slope_db_oct: int | None = None


@dataclasses.dataclass(frozen=True)
class CurveBenderPlan:
    plugin_name: str
    linked: bool
    mid_side: bool
    bands: list[PlannedBand]
    skipped: list[str]


def is_curve_bender_block(block: str) -> bool:
    return CURVE_BENDER_RE.search(block) is not None


def plan_block(block: str) -> CurveBenderPlan:
    params = extract_params(block)
    return plan_params(params, detect_plugin_name(block))


def processor_state_fingerprint(block: str) -> str | None:
    match = PROCESSOR_STATE_RE.search(block)
    if not match:
        return None
    state = "".join(match.group(1).split())
    return hashlib.sha256(state.encode()).hexdigest()


def plan_signature(plan: CurveBenderPlan) -> tuple[object, ...]:
    return (
        plan.linked,
        plan.mid_side,
        tuple(
            (
                band.channel,
                band.kind,
                round(band.frequency_hz, 3),
                round(band.gain_db or 0.0, 3),
                band.q,
                band.slope_db_oct,
            )
            for band in plan.bands
        ),
    )


def extract_params(block: str) -> dict[str, float]:
    params: dict[str, float] = {}
    for match in PARAM_RE.finditer(block):
        chunk = match.group(1)
        name = _tag_value(chunk, "ParameterName")
        value = _tag_value(chunk, "Manual")
        parameter_id = _tag_value(chunk, "ParameterId")
        if name and value and parameter_id != "-1":
            params[name] = float(value)
    return params


def plan_params(params: dict[str, float], plugin_name: str = "UAD Chandler Limited Curve Bender") -> CurveBenderPlan:
    linked = _on(params.get("Link Channels", 0.0))
    mid_side = _on(params.get("Mid/Side Processing", 0.0))
    bands: list[PlannedBand] = []
    skipped: list[str] = []

    for prefix, channel in _targets(linked, mid_side):
        if not _on(params.get(f"{prefix}_input", params.get(_input_name(prefix), 1.0))):
            skipped.append(f"{prefix}: input disabled")
            continue
        _add_filters(params, prefix, channel, bands, skipped)
        _add_eq_bands(params, prefix, channel, bands, skipped)

    return CurveBenderPlan(plugin_name, linked, mid_side, bands, skipped)


def _targets(linked: bool, mid_side: bool) -> list[tuple[str, str]]:
    if linked:
        return [("L", "stereo")]
    if mid_side:
        return [("L", "mid"), ("R", "side")]
    return [("L", "mid"), ("R", "side")]


def _add_filters(
    params: dict[str, float],
    prefix: str,
    channel: str,
    bands: list[PlannedBand],
    skipped: list[str],
) -> None:
    for label, kind, frequencies in (
        ("High Pass", "high_pass", HIGH_PASS_FREQS),
        ("Low Pass", "low_pass", LOW_PASS_FREQS),
    ):
        name = f"{prefix} {label}"
        frequency = _lookup_frequency(frequencies, params.get(name), name, skipped)
        if frequency is not None:
            bands.append(PlannedBand(channel, name, kind, frequency, slope_db_oct=FILTER_SLOPE_DB_OCT))


def _add_eq_bands(
    params: dict[str, float],
    prefix: str,
    channel: str,
    bands: list[PlannedBand],
    skipped: list[str],
) -> None:
    for band_name in ("Bass", "Presence 2", "Presence 1", "Treble"):
        gain = _gain_db(params.get(f"{prefix} {band_name} Gain", 0.5))
        high_q = _on(params.get(f"{prefix} {band_name} Multiplier", 0.0))
        if high_q:
            gain *= HIGH_Q_GAIN_MULTIPLIER
        if abs(gain) < 0.01:
            continue

        frequency = _lookup_frequency(EQ_FREQS[band_name], params.get(f"{prefix} {band_name} Frequency"), f"{prefix} {band_name} Frequency", skipped)
        if frequency is None:
            continue

        kind = _eq_kind(params, prefix, band_name)
        q = HIGH_BELL_Q if high_q else NORMAL_BELL_Q
        bands.append(PlannedBand(channel, f"{prefix} {band_name}", kind, frequency, round(gain, 3), q))


def _eq_kind(params: dict[str, float], prefix: str, band_name: str) -> str:
    if band_name == "Bass":
        return "bell" if _on(params.get(f"{prefix} Bass Peak/Shelf", 0.0)) else "low_shelf"
    if band_name == "Treble":
        return "bell" if _on(params.get(f"{prefix} Treble Peak/Shelf", 0.0)) else "high_shelf"
    return "bell"


def _lookup_frequency(
    frequencies: dict[float, float | None],
    value: float | None,
    name: str,
    skipped: list[str],
) -> float | None:
    if value is None:
        skipped.append(f"{name}: missing parameter")
        return None
    for raw, frequency in frequencies.items():
        if abs(value - raw) < 0.00001:
            return frequency
    skipped.append(f"{name}: unknown stepped value {value:g}")
    return None


def _gain_db(value: float) -> float:
    return (value - 0.5) * GAIN_DB_RANGE


def _input_name(prefix: str) -> str:
    return "Left/Mid In" if prefix == "L" else "Right/Side In"


def _on(value: float | None) -> bool:
    return bool(value is not None and value >= 0.5)


def _tag_value(chunk: str, tag: str) -> str | None:
    match = re.search(rf"<{tag}\b[^>]*\bValue=\"([^\"]*)\"", chunk)
    return match.group(1) if match else None


def detect_plugin_name(block: str) -> str:
    match = re.search(r"<Name\b[^>]*\bValue=\"([^\"]*Curve Bender[^\"]*)\"", block, re.I)
    return match.group(1) if match else "UAD Chandler Limited Curve Bender"

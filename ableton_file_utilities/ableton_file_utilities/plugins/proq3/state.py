"""FabFilter Pro-Q 3 ProcessorState model."""

from __future__ import annotations

import dataclasses
import math
import struct


MODE_BYTES = {
    "zero_latency": bytes.fromhex("00000000"),
    "natural_phase": bytes.fromhex("0000803F"),
}
MODE_LABELS = {
    "zero_latency": "Zero Latency",
    "natural_phase": "Natural Phase",
}

PROCESSOR_LENGTH = 1456
PROCESSOR_HEADER = bytes.fromhex("464642530100000066010000")
PROCESSOR_TAIL = bytes.fromhex("464670720100000000000000")
MODE_OFFSET = 1260
BAND_START = 12
BAND_COUNT = 24
BAND_SIZE = 52
BAND_END = BAND_START + BAND_COUNT * BAND_SIZE

BAND_TYPE_CODES = {
    "bell": 0.0,
    "low_shelf": 1.0,
    "high_pass": 2.0,
    "high_shelf": 3.0,
    "low_pass": 4.0,
}
CHANNEL_CODES = {
    "stereo": 2.0,
    "mid": 3.0,
    "side": 4.0,
}
SLOPE_CODES = {
    6: 0.0,
    12: 1.0,
    18: 2.0,
    24: 3.0,
    30: 4.0,
    36: 5.0,
    48: 6.0,
    72: 7.0,
    96: 8.0,
}


@dataclasses.dataclass(frozen=True)
class ProQ3Band:
    channel: str
    kind: str
    frequency_hz: float
    gain_db: float = 0.0
    q: float = 0.5
    slope_db_oct: int | None = None


class ProQ3State:
    def __init__(self, processor: bytes):
        warning = validate_processor(processor)
        if warning:
            raise ValueError(warning)
        self._processor = bytearray(processor)

    def to_bytes(self) -> bytes:
        return bytes(self._processor)

    def mode(self) -> str:
        current = bytes(self._processor[MODE_OFFSET : MODE_OFFSET + 4])
        for mode, value in MODE_BYTES.items():
            if current == value:
                return mode
        raise ValueError(f"Unknown mode bytes at ProcessorState@{MODE_OFFSET}.")

    def set_mode(self, mode: str) -> None:
        self.mode()
        self._processor[MODE_OFFSET : MODE_OFFSET + 4] = MODE_BYTES[canonical_mode(mode)]

    def list_bands(self) -> list[ProQ3Band]:
        bands: list[ProQ3Band] = []
        for values in self._band_values():
            if values[0] >= 0.5:
                bands.append(_values_to_band(values))
        return bands

    def replace_bands(self, bands: list[object]) -> None:
        if len(bands) > BAND_COUNT:
            raise ValueError(f"Pro-Q supports {BAND_COUNT} serialized bands; got {len(bands)}.")
        slots = [_band_slot(band) for band in bands]
        slots.extend(_empty_band_slot() for _ in range(BAND_COUNT - len(bands)))
        self._processor[BAND_START:BAND_END] = b"".join(slots)

    def add_band(self, band: object) -> None:
        self.replace_bands([*self.list_bands(), band])

    def update_band(self, index: int, band: object) -> None:
        bands = self.list_bands()
        _require_band_index(index, bands)
        bands[index] = _coerce_band(band)
        self.replace_bands(bands)

    def delete_band(self, index: int) -> None:
        bands = self.list_bands()
        _require_band_index(index, bands)
        del bands[index]
        self.replace_bands(bands)

    def _band_values(self) -> list[list[float]]:
        return [
            _unpack_floats(bytes(self._processor[offset : offset + BAND_SIZE]))
            for offset in range(BAND_START, BAND_END, BAND_SIZE)
        ]


def canonical_mode(mode: str) -> str:
    key = mode.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "zero": "zero_latency",
        "zero_latency": "zero_latency",
        "natural": "natural_phase",
        "natural_phase": "natural_phase",
    }
    if key not in aliases:
        raise ValueError("Mode must be zero-latency or natural-phase.")
    return aliases[key]


def validate_processor(processor: bytes) -> str | None:
    if len(processor) != PROCESSOR_LENGTH:
        return f"ProcessorState length was {len(processor)} bytes; expected {PROCESSOR_LENGTH}."
    if not processor.startswith(PROCESSOR_HEADER):
        return "ProcessorState header did not match the known Pro-Q 3 VST3 shape."
    if not processor.endswith(PROCESSOR_TAIL):
        return "ProcessorState tail did not match the known Pro-Q 3 VST3 shape."
    return None


def write_bands(processor: bytes, bands: list[object], target_mode: str = "zero_latency") -> bytes:
    state = ProQ3State(processor)
    state.replace_bands(bands)
    state.set_mode(target_mode)
    return state.to_bytes()


def _band_slot(band: object) -> bytes:
    parsed = _coerce_band(band)
    values = _base_band_values()
    values[0] = 1.0
    values[2] = math.log2(parsed.frequency_hz)
    values[3] = parsed.gain_db
    values[7] = parsed.q
    values[8] = _lookup(BAND_TYPE_CODES, parsed.kind, "band type")
    values[9] = _slope_code(parsed.kind, parsed.slope_db_oct)
    values[10] = _lookup(CHANNEL_CODES, parsed.channel, "channel")
    return _pack_floats(values)


def _empty_band_slot() -> bytes:
    values = _base_band_values()
    values[0] = 0.0
    return _pack_floats(values)


def _base_band_values() -> list[float]:
    return [0.0, 1.0, math.log2(1000.0), 0.0, 0.0, 1.0, 1.0, 0.5, 0.0, 1.0, 2.0, 1.0, 0.0]


def _values_to_band(values: list[float]) -> ProQ3Band:
    kind = _reverse_lookup(BAND_TYPE_CODES, values[8], "band type")
    slope = _reverse_lookup(SLOPE_CODES, values[9], "filter slope") if kind in ("high_pass", "low_pass") else None
    return ProQ3Band(
        channel=_reverse_lookup(CHANNEL_CODES, values[10], "channel"),
        kind=kind,
        frequency_hz=2**values[2],
        gain_db=values[3],
        q=values[7],
        slope_db_oct=slope,
    )


def _slope_code(kind: str, slope: int | None) -> float:
    if kind not in ("high_pass", "low_pass"):
        return 1.0
    return _lookup(SLOPE_CODES, slope or 6, "filter slope")


def _lookup(values: dict[object, float], key: object, label: str) -> float:
    if key not in values:
        raise ValueError(f"Unsupported Pro-Q {label}: {key}.")
    return values[key]


def _reverse_lookup(values: dict[object, float], code: float, label: str) -> object:
    for key, value in values.items():
        if abs(code - value) < 0.001:
            return key
    raise ValueError(f"Unsupported Pro-Q {label} code: {code:g}.")


def _coerce_band(band: object) -> ProQ3Band:
    if isinstance(band, ProQ3Band):
        return band
    return ProQ3Band(
        channel=getattr(band, "channel"),
        kind=getattr(band, "kind"),
        frequency_hz=float(getattr(band, "frequency_hz")),
        gain_db=float(getattr(band, "gain_db", 0.0) or 0.0),
        q=float(getattr(band, "q", 0.5) or 0.5),
        slope_db_oct=getattr(band, "slope_db_oct", None),
    )


def _require_band_index(index: int, bands: list[ProQ3Band]) -> None:
    if index < 0 or index >= len(bands):
        raise IndexError(f"Band index {index} out of range.")


def _pack_floats(values: list[float]) -> bytes:
    return b"".join(struct.pack("<f", value) for value in values)


def _unpack_floats(slot: bytes) -> list[float]:
    return [struct.unpack("<f", slot[index : index + 4])[0] for index in range(0, BAND_SIZE, 4)]

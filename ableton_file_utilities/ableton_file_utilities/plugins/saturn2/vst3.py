"""FabFilter Saturn 2 VST3 Ableton XML adapter."""

from __future__ import annotations

import dataclasses
import re
import struct
import urllib.parse

from ableton_file_utilities.core import live_set


SATURN_2_RE = re.compile(r"Saturn(?:\s|%20)*2", re.IGNORECASE)
HEX_STATE_RE = live_set.HEX_STATE_RE

PROCESSOR_LENGTH = 3828
PROCESSOR_HEADER = bytes.fromhex("4646425301000000B7030000")
PROCESSOR_TAIL = bytes.fromhex("464670720100000000000000")
QUALITY_OFFSET = 2804

QUALITY_VALUES = {
    "normal": 0.0,
    "high_quality": 1.0,
    "super_high_quality": 2.0,
}
QUALITY_LABELS = {
    "normal": "Normal",
    "high_quality": "High Quality",
    "super_high_quality": "Super High Quality",
}
QUALITY_BYTES = {mode: struct.pack("<f", value) for mode, value in QUALITY_VALUES.items()}


@dataclasses.dataclass(frozen=True)
class PatchResult:
    block: str
    plugin_name: str
    old_value: str | None
    new_value: str | None
    changed: bool
    warning: str | None = None


def canonical_mode(mode: str) -> str:
    key = mode.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "normal": "normal",
        "standard": "normal",
        "high": "high_quality",
        "hq": "high_quality",
        "high_quality": "high_quality",
        "highest": "super_high_quality",
        "highest_quality": "super_high_quality",
        "super": "super_high_quality",
        "super_high": "super_high_quality",
        "super_high_quality": "super_high_quality",
    }
    if key not in aliases:
        raise ValueError("Mode must be normal, high-quality, or super-high-quality.")
    return aliases[key]


def is_saturn2_block(block: str) -> bool:
    return "fabfilter" in block.lower() and SATURN_2_RE.search(block) is not None


def patch_block(block: str, target_mode: str) -> PatchResult:
    plugin_name = detect_plugin_name(block)
    state_match = HEX_STATE_RE.search(block)
    if not state_match:
        return PatchResult(block, plugin_name, None, None, False, "No ProcessorState blob found.")

    try:
        target = canonical_mode(target_mode)
        processor = bytearray(live_set.bytes_from_hex_match(state_match))
        old_mode = quality_mode(processor)
    except ValueError as exc:
        return PatchResult(block, plugin_name, None, None, False, str(exc))

    old = QUALITY_BYTES[old_mode].hex().upper()
    new = QUALITY_BYTES[target].hex().upper()
    if old == new:
        return PatchResult(block, plugin_name, old, new, False)

    processor[QUALITY_OFFSET : QUALITY_OFFSET + 4] = QUALITY_BYTES[target]
    new_block = live_set.replace_processor_state(block, state_match, bytes(processor))
    return PatchResult(new_block, plugin_name, old, new, True)


def quality_mode(processor: bytes | bytearray) -> str:
    warning = validate_processor(bytes(processor))
    if warning:
        raise ValueError(warning)

    current = bytes(processor[QUALITY_OFFSET : QUALITY_OFFSET + 4])
    for mode, value in QUALITY_BYTES.items():
        if current == value:
            return mode
    raise ValueError(f"Unknown Saturn 2 quality bytes at ProcessorState@{QUALITY_OFFSET}.")


def validate_processor(processor: bytes) -> str | None:
    if len(processor) != PROCESSOR_LENGTH:
        return f"ProcessorState length was {len(processor)} bytes; expected {PROCESSOR_LENGTH}."
    if not processor.startswith(PROCESSOR_HEADER):
        return "ProcessorState header did not match the known Saturn 2 VST3 shape."
    if not processor.endswith(PROCESSOR_TAIL):
        return "ProcessorState tail did not match the known Saturn 2 VST3 shape."
    if len(processor) < QUALITY_OFFSET + 4:
        return "ProcessorState was shorter than the known Saturn 2 quality offset."
    return None


def detect_plugin_name(block: str) -> str:
    patterns = (
        r"<Name\b[^>]*\bValue=\"([^\"]*Saturn[^\"]*)\"",
        r"<BrowserContentPath\b[^>]*\bValue=\"[^\"]*FabFilter:([^\"]*)\"",
    )
    for pattern in patterns:
        match = re.search(pattern, block, re.I)
        if match:
            return urllib.parse.unquote(match.group(1))
    return "FabFilter Saturn 2"

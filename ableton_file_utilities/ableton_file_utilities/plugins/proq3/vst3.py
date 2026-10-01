"""FabFilter Pro-Q 3 VST3 Ableton XML adapter."""

from __future__ import annotations

import dataclasses
import re
import urllib.parse

from ableton_file_utilities.core import live_set

from .state import (
    MODE_BYTES,
    MODE_LABELS,
    MODE_OFFSET,
    PROCESSOR_HEADER,
    PROCESSOR_LENGTH,
    PROCESSOR_TAIL,
    ProQ3Band,
    ProQ3State,
    canonical_mode,
    validate_processor,
    write_bands,
)


PRO_Q_RE = re.compile(r"Pro-?Q(?:\s*(?:%20)?3)?", re.IGNORECASE)
HEX_STATE_RE = live_set.HEX_STATE_RE


@dataclasses.dataclass(frozen=True)
class PatchResult:
    block: str
    plugin_name: str
    old_value: str | None
    new_value: str | None
    changed: bool
    warning: str | None = None


def is_proq3_block(block: str) -> bool:
    return "fabfilter" in block.lower() and PRO_Q_RE.search(block) is not None


def state_from_block(block: str) -> ProQ3State:
    state_match = HEX_STATE_RE.search(block)
    if not state_match:
        raise ValueError("No ProcessorState blob found.")
    return ProQ3State(live_set.bytes_from_hex_match(state_match))


def patch_block(block: str, target_mode: str) -> PatchResult:
    plugin_name = detect_plugin_name(block)
    state_match = HEX_STATE_RE.search(block)
    if not state_match:
        return PatchResult(block, plugin_name, None, None, False, "No ProcessorState blob found.")

    try:
        state = ProQ3State(live_set.bytes_from_hex_match(state_match))
        old_mode = state.mode()
        state.set_mode(target_mode)
    except ValueError as exc:
        return PatchResult(block, plugin_name, None, None, False, str(exc))

    old = MODE_BYTES[old_mode].hex().upper()
    new = MODE_BYTES[canonical_mode(target_mode)].hex().upper()
    if old == new:
        return PatchResult(block, plugin_name, old, new, False)
    new_block = live_set.replace_processor_state(block, state_match, state.to_bytes())
    return PatchResult(new_block, plugin_name, old, new, True)


def patch_block_bands(block: str, bands: list[object], target_mode: str = "zero_latency") -> PatchResult:
    plugin_name = detect_plugin_name(block)
    state_match = HEX_STATE_RE.search(block)
    if not state_match:
        return PatchResult(block, plugin_name, None, None, False, "No ProcessorState blob found.")

    try:
        state = ProQ3State(live_set.bytes_from_hex_match(state_match))
        before = state.to_bytes()
        state.replace_bands(bands)
        state.set_mode(target_mode)
    except ValueError as exc:
        return PatchResult(block, plugin_name, None, None, False, str(exc))

    new_block = live_set.replace_processor_state(block, state_match, state.to_bytes())
    return PatchResult(new_block, plugin_name, None, None, state.to_bytes() != before)


def detect_plugin_name(block: str) -> str:
    patterns = (
        r"<Name\b[^>]*\bValue=\"([^\"]*Pro-Q[^\"]*)\"",
        r"<BrowserContentPath\b[^>]*\bValue=\"[^\"]*FabFilter:([^\"]*)\"",
    )
    for pattern in patterns:
        match = re.search(pattern, block, re.I)
        if match:
            return urllib.parse.unquote(match.group(1))
    return "FabFilter Pro-Q 3"

"""FabFilter Pro-Q 3 VST3 ProcessorState patching."""

from __future__ import annotations

import dataclasses
import re
import urllib.parse


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

PRO_Q_RE = re.compile(r"Pro-?Q(?:\s*(?:%20)?3)?", re.IGNORECASE)
HEX_STATE_RE = re.compile(r"(<ProcessorState>\s*)([0-9A-Fa-f\s]+?)(\s*</ProcessorState>)", re.I | re.S)


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
        "zero": "zero_latency",
        "zero_latency": "zero_latency",
        "natural": "natural_phase",
        "natural_phase": "natural_phase",
    }
    if key not in aliases:
        raise ValueError("Mode must be zero-latency or natural-phase.")
    return aliases[key]


def is_proq3_block(block: str) -> bool:
    return "fabfilter" in block.lower() and PRO_Q_RE.search(block) is not None


def patch_block(block: str, target_mode: str) -> PatchResult:
    plugin_name = detect_plugin_name(block)
    state_match = HEX_STATE_RE.search(block)
    if not state_match:
        return PatchResult(block, plugin_name, None, None, False, "No ProcessorState blob found.")

    processor = bytes.fromhex("".join(state_match.group(2).split()))
    warning = validate_processor(processor)
    if warning:
        return PatchResult(block, plugin_name, None, None, False, warning)

    target = MODE_BYTES[target_mode]
    old = processor[MODE_OFFSET : MODE_OFFSET + 4]
    if old not in MODE_BYTES.values():
        return PatchResult(
            block,
            plugin_name,
            old.hex().upper(),
            target.hex().upper(),
            False,
            f"Unknown mode bytes at ProcessorState@{MODE_OFFSET}.",
        )

    if old == target:
        return PatchResult(block, plugin_name, old.hex().upper(), target.hex().upper(), False)

    patched = processor[:MODE_OFFSET] + target + processor[MODE_OFFSET + 4 :]
    new_block = replace_processor_state(block, state_match, patched)
    return PatchResult(new_block, plugin_name, old.hex().upper(), target.hex().upper(), True)


def validate_processor(processor: bytes) -> str | None:
    if len(processor) != PROCESSOR_LENGTH:
        return f"ProcessorState length was {len(processor)} bytes; expected {PROCESSOR_LENGTH}."
    if not processor.startswith(PROCESSOR_HEADER):
        return "ProcessorState header did not match the known Pro-Q 3 VST3 shape."
    if not processor.endswith(PROCESSOR_TAIL):
        return "ProcessorState tail did not match the known Pro-Q 3 VST3 shape."
    return None


def replace_processor_state(block: str, match: re.Match[str], processor: bytes) -> str:
    formatted = format_hex_like_existing(match.group(2), processor)
    return f"{block[:match.start(2)]}{formatted}{block[match.end(2):]}"


def format_hex_like_existing(existing: str, data: bytes) -> str:
    newline = "\r\n" if "\r\n" in existing else "\n"
    indent = next((line[: len(line) - len(line.lstrip())] for line in existing.splitlines() if line.strip()), "")
    hex_text = data.hex().upper()
    chunks = [hex_text[index : index + 80] for index in range(0, len(hex_text), 80)]
    if not indent:
        return newline.join(chunks)
    return chunks[0] + "".join(f"{newline}{indent}{chunk}" for chunk in chunks[1:])


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


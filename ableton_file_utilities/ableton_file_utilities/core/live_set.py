"""Read, write, and traverse Ableton Live set XML."""

from __future__ import annotations

import dataclasses
import datetime as dt
import gzip
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable


XML_TAG_RE = re.compile(r"<(/?)([A-Za-z_][\w:.-]*)([^<>]*?)(/?)>")
TAG_VALUE_TEMPLATE = r"<{tag}\b[^>]*\bValue=\"([^\"]*)\""
HEX_STATE_RE = re.compile(r"(<ProcessorState>\s*)([0-9A-Fa-f\s]+?)(\s*</ProcessorState>)", re.I | re.S)
GLOBAL_ID_RE = re.compile(r'(<(?:Pointee|AutomationTarget|ModulationTarget)\b[^>]*\bId=")(\d+)(")')
DEVICE_ON_BLOCK_RE = re.compile(r"<On>\s*.*?</On>", re.S)
DEVICE_ON_MANUAL_RE = re.compile(r'(<On>\s*.*?<Manual\b[^>]*\bValue=")([^"]*)(")', re.S)
AUTOMATION_TARGET_ID_RE = re.compile(r'(<AutomationTarget\b[^>]*\bId=")(\d+)(")')


@dataclasses.dataclass(frozen=True)
class LiveSetDocument:
    path: Path
    xml: str
    was_gzip: bool


def read(path: Path) -> LiveSetDocument:
    raw = path.read_bytes()
    was_gzip = raw.startswith(b"\x1f\x8b")
    if was_gzip:
        raw = gzip.decompress(raw)
    return LiveSetDocument(path=path, xml=raw.decode("utf-8"), was_gzip=was_gzip)


def write(document: LiveSetDocument, output_path: Path, xml: str) -> None:
    validate_xml(xml)
    raw = xml.encode("utf-8")
    if document.was_gzip:
        raw = gzip.compress(raw)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "wb", delete=False, dir=str(output_path.parent), prefix=output_path.name, suffix=".tmp"
    ) as handle:
        tmp_path = Path(handle.name)
        handle.write(raw)

    tmp_path.replace(output_path)


def validate_xml(xml: str) -> None:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError(f"Ableton XML is not well-formed: {exc}") from exc
    duplicate = _first_duplicate_child_id(root)
    if duplicate:
        parent, child_id = duplicate
        raise ValueError(f"Ableton XML has duplicate child Id {child_id!r} under <{parent}>.")
    pointee_error = _next_pointee_error(root)
    if pointee_error:
        next_id, max_id = pointee_error
        raise ValueError(f"NextPointeeId is too low: {next_id} must be bigger than {max_id}.")


def _first_duplicate_child_id(root: ET.Element) -> tuple[str, str] | None:
    for parent in root.iter():
        seen: set[str] = set()
        for child in list(parent):
            child_id = child.attrib.get("Id")
            if child_id is None:
                continue
            if child_id in seen:
                return parent.tag, child_id
            seen.add(child_id)
    return None


def _next_pointee_error(root: ET.Element) -> tuple[int, int] | None:
    next_node = root.find(".//NextPointeeId")
    if next_node is None:
        return None
    value = next_node.attrib.get("Value")
    if value is None:
        return None
    next_id = int(value)
    max_id = max(_numeric_ids(root), default=-1)
    return (next_id, max_id) if next_id <= max_id else None


def _numeric_ids(root: ET.Element) -> Iterable[int]:
    for node in root.iter():
        value = node.attrib.get("Id")
        if value and value.isdigit():
            yield int(value)


def backup(path: Path) -> Path:
    backup_path = path.with_name(f"{path.name}.bak-{dt.datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(path, backup_path)
    return backup_path


def iter_plugin_device_ranges(xml: str) -> Iterable[tuple[int, int]]:
    stack: list[tuple[str, int]] = []
    for match in XML_TAG_RE.finditer(xml):
        closing, tag, attrs, self_closing = match.groups()
        if attrs.lstrip().startswith(("?", "!")):
            continue
        if closing:
            yield from _close_tag_ranges(stack, tag, match.end())
        elif not self_closing:
            stack.append((tag, match.start()))


def _close_tag_ranges(stack: list[tuple[str, int]], tag: str, end: int) -> Iterable[tuple[int, int]]:
    for index in range(len(stack) - 1, -1, -1):
        open_tag, start = stack[index]
        if open_tag != tag:
            continue
        del stack[index:]
        if tag.lower().endswith("plugindevice"):
            yield start, end
        return


def replace_ranges(xml: str, replacements: Iterable[tuple[int, int, str]]) -> str:
    parts: list[str] = []
    cursor = 0
    for start, end, replacement in replacements:
        parts.append(xml[cursor:start])
        parts.append(replacement)
        cursor = end
    parts.append(xml[cursor:])
    return "".join(parts)


def tag_ranges(xml: str, tags: set[str]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    stack: list[tuple[str, int]] = []
    for match in XML_TAG_RE.finditer(xml):
        closing, tag, _attrs, self_closing = match.groups()
        if closing:
            for index in range(len(stack) - 1, -1, -1):
                open_tag, start = stack[index]
                if open_tag != tag:
                    continue
                del stack[index:]
                if tag in tags:
                    ranges.append((start, match.end()))
                break
        elif not self_closing:
            stack.append((tag, match.start()))
    return ranges


def smallest_containing_range(
    ranges: list[tuple[int, int]],
    start: int,
    end: int,
) -> tuple[int, int] | None:
    containing = [item for item in ranges if item[0] <= start and end <= item[1]]
    if not containing:
        return None
    return min(containing, key=lambda item: item[1] - item[0])


def next_pointee_id(xml: str) -> int:
    match = re.search(r'<NextPointeeId\b[^>]*\bValue="(\d+)"', xml)
    if not match:
        raise ValueError("No NextPointeeId was found.")
    return int(match.group(1))


def set_next_pointee_id(xml: str, next_id: int) -> str:
    pattern = re.compile(r'(<NextPointeeId\b[^>]*\bValue=")(\d+)(")')
    if not pattern.search(xml):
        raise ValueError("No NextPointeeId was found.")
    return pattern.sub(rf"\g<1>{next_id}\3", xml, count=1)


def tag_value(text: str, tag: str) -> str | None:
    match = re.search(TAG_VALUE_TEMPLATE.format(tag=re.escape(tag)), text)
    return match.group(1) if match else None


def tag_values(text: str, tag: str) -> list[str]:
    return re.findall(TAG_VALUE_TEMPLATE.format(tag=re.escape(tag)), text)


def replace_tag_value(text: str, tag: str, value: str, count: int = 0) -> str:
    pattern = re.compile(rf"(<{re.escape(tag)}\b[^>]*\bValue=\")([^\"]*)(\")")
    return pattern.sub(lambda match: f"{match.group(1)}{value}{match.group(3)}", text, count=count)


def hex_text_to_bytes(text: str) -> bytes:
    return bytes.fromhex("".join(text.split()))


def bytes_from_hex_match(match: re.Match[str], group: int = 2) -> bytes:
    return hex_text_to_bytes(match.group(group))


def replace_processor_state(block: str, match: re.Match[str], processor: bytes, width: int = 80) -> str:
    formatted = format_hex_like_existing(match.group(2), processor, width)
    return f"{block[:match.start(2)]}{formatted}{block[match.end(2):]}"


def format_hex_like_existing(existing: str, data: bytes, width: int = 80) -> str:
    newline = "\r\n" if "\r\n" in existing else "\n"
    indent = next((line[: len(line) - len(line.lstrip())] for line in existing.splitlines() if line.strip()), "")
    hex_text = data.hex().upper()
    chunks = [hex_text[index : index + width] for index in range(0, len(hex_text), width)]
    if not indent:
        return newline.join(chunks)
    return chunks[0] + "".join(f"{newline}{indent}{chunk}" for chunk in chunks[1:])


def copy_device_on_state(source_block: str, target_block: str) -> str:
    source_match = DEVICE_ON_MANUAL_RE.search(source_block)
    if source_match:
        target_block = DEVICE_ON_MANUAL_RE.sub(
            lambda match: f"{match.group(1)}{source_match.group(2)}{match.group(3)}",
            target_block,
            count=1,
        )

    source_on = DEVICE_ON_BLOCK_RE.search(source_block)
    source_target = AUTOMATION_TARGET_ID_RE.search(source_on.group(0)) if source_on else None
    if not source_target:
        return target_block

    def replace_on_target(match: re.Match[str]) -> str:
        return AUTOMATION_TARGET_ID_RE.sub(
            lambda target: f"{target.group(1)}{source_target.group(2)}{target.group(3)}",
            match.group(0),
            count=1,
        )

    return DEVICE_ON_BLOCK_RE.sub(replace_on_target, target_block, count=1)


def remap_cloned_plugin_device(block: str, plugin_device_id: int, first_global_id: int) -> tuple[str, int]:
    next_id = first_global_id
    block = re.sub(r'(<PluginDevice\b[^>]*\bId=")(\d+)(")', rf"\g<1>{plugin_device_id}\3", block, count=1)
    if plugin_device_id >= next_id:
        next_id = plugin_device_id + 1

    id_map: dict[str, int] = {}

    def replace_global_id(match: re.Match[str]) -> str:
        nonlocal next_id
        old_id = match.group(2)
        if old_id not in id_map:
            id_map[old_id] = next_id
            next_id += 1
        return f'{match.group(1)}{id_map[old_id]}{match.group(3)}'

    return GLOBAL_ID_RE.sub(replace_global_id, block), next_id

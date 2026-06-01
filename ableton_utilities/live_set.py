"""Read, write, validate, and patch Ableton Live set XML."""

from __future__ import annotations

import dataclasses
import gzip
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable


XML_TAG_RE = re.compile(r"<(/?)([A-Za-z_][\w:.-]*)([^<>]*?)(/?)>")
GLOBAL_TARGET_RE = re.compile(
    r'(<(?:Pointee|(?:[A-Za-z_][\w:.-]*)?AutomationTarget|(?:[A-Za-z_][\w:.-]*)?ModulationTarget|'
    r'ControllerTargets\.\d+)\b[^>]*\bId=")(\d+)(")'
)
LOM_ID_RE = re.compile(r'(<LomId\b[^>]*\bValue=")(\d+)(")')
ROOT_ID_RE = re.compile(r'(<[A-Za-z_][\w:.-]*\b[^>]*\bId=")(\d+)(")')


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
    duplicate_target = _first_duplicate_global_target_id(root)
    if duplicate_target:
        tag, target_id = duplicate_target
        raise ValueError(f"Ableton XML has duplicate global target Id {target_id!r} on <{tag}>.")
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


def _first_duplicate_global_target_id(root: ET.Element) -> tuple[str, str] | None:
    seen: set[str] = set()
    for node in root.iter():
        if not _is_global_target_tag(node.tag):
            continue
        target_id = node.attrib.get("Id")
        if target_id is None:
            continue
        if target_id in seen:
            return node.tag, target_id
        seen.add(target_id)
    return None


def _is_global_target_tag(tag: str) -> bool:
    return (
        tag == "Pointee"
        or tag.endswith("AutomationTarget")
        or tag.endswith("ModulationTarget")
        or tag.startswith("ControllerTargets.")
    )


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


def first_tag_range(xml: str, tag: str) -> tuple[int, int] | None:
    ranges = tag_ranges(xml, {tag})
    return ranges[0] if ranges else None


def replace_range(xml: str, item_range: tuple[int, int], replacement: str) -> str:
    start, end = item_range
    return f"{xml[:start]}{replacement}{xml[end:]}"


def replace_first_tag(xml: str, tag: str, replacement: str) -> str:
    item_range = first_tag_range(xml, tag)
    if item_range is None:
        raise ValueError(f"No <{tag}> block was found.")
    return replace_range(xml, item_range, replacement)


def tag_inner_range(xml: str, tag: str) -> tuple[int, int] | None:
    item_range = first_tag_range(xml, tag)
    if item_range is None:
        return None
    open_end = xml.find(">", item_range[0]) + 1
    close_start = xml.rfind(f"</{tag}>", item_range[0], item_range[1])
    if close_start < open_end:
        return None
    return open_end, close_start


def tag_contents(block: str) -> str:
    open_end = block.find(">") + 1
    close_start = block.rfind("</")
    if open_end <= 0 or close_start < open_end:
        return ""
    return block[open_end:close_start]


def direct_child_blocks(xml: str) -> list[str]:
    return [xml[start:end] for start, end in direct_child_ranges(xml)]


def direct_child_ranges(xml: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    stack: list[str] = []
    start: int | None = None
    for match in XML_TAG_RE.finditer(xml):
        closing, tag, _attrs, self_closing = match.groups()
        if closing:
            if stack and stack[-1] == tag:
                stack.pop()
                if not stack and start is not None:
                    ranges.append((start, match.end()))
                    start = None
            continue
        if not stack:
            start = match.start()
        if not self_closing:
            stack.append(tag)
        elif not stack and start is not None:
            ranges.append((start, match.end()))
            start = None
    return ranges


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


def remap_global_ids(xml: str, first_id: int) -> tuple[str, int]:
    xml, next_id, _id_map = remap_global_ids_with_map(xml, first_id)
    return xml, next_id


def remap_global_ids_with_map(xml: str, first_id: int) -> tuple[str, int, dict[str, str]]:
    next_id = first_id
    id_map: dict[str, str] = {}

    def replace_global_id(match: re.Match[str]) -> str:
        nonlocal next_id
        old_id = match.group(2)
        if old_id not in id_map:
            id_map[old_id] = str(next_id)
            next_id += 1
        return f"{match.group(1)}{id_map[old_id]}{match.group(3)}"

    return GLOBAL_TARGET_RE.sub(replace_global_id, xml), next_id, id_map


def next_lom_id(xml: str) -> int:
    return max((int(value) for value in re.findall(r'<LomId\b[^>]*\bValue="(\d+)"', xml)), default=0) + 1


def remap_nonzero_lom_ids(block: str, first_lom_id: int) -> str:
    next_id = first_lom_id
    id_map: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        nonlocal next_id
        old_id = match.group(2)
        if old_id == "0":
            return match.group(0)
        if old_id not in id_map:
            id_map[old_id] = str(next_id)
            next_id += 1
        return f"{match.group(1)}{id_map[old_id]}{match.group(3)}"

    return LOM_ID_RE.sub(replace, block)


def next_root_id(blocks: list[str]) -> int:
    ids = [int(match.group(2)) for block in blocks if (match := ROOT_ID_RE.match(block))]
    return max(ids, default=-1) + 1


def set_root_id(block: str, item_id: int) -> str:
    patched, count = ROOT_ID_RE.subn(rf"\g<1>{item_id}\3", block, count=1)
    if count != 1:
        raise ValueError("Could not set root Id.")
    return patched


def line_indent(text: str, index: int) -> str:
    line_start = text.rfind("\n", 0, index)
    if line_start < 0:
        return ""
    match = re.match(r"[\t ]*", text[line_start + 1 : index])
    return "" if match is None else match.group(0)


def escape_attr(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")

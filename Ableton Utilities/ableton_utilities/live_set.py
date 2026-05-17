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
        ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError(f"Ableton XML is not well-formed: {exc}") from exc


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

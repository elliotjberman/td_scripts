"""Global Map8 macro boilerplate for Ableton live sets."""

from __future__ import annotations

import dataclasses
import re

from ableton_utilities import live_set
from ableton_utilities.hardware_xml import parse_tracks
from ableton_utilities.live.macro_targets import ensure_boilerplate_macro_targets


@dataclasses.dataclass(frozen=True)
class GlobalMacroReport:
    name: str
    target: str
    lom_id: str


def apply_boilerplate_global_macros(xml: str) -> tuple[str, list[GlobalMacroReport], list[str]]:
    reports: list[GlobalMacroReport] = []

    tracks = parse_tracks(xml)
    global_track = next((track for track in tracks if track.name == "Global"), None)
    if global_track is None:
        return xml, [], ["No Global track was found for global Map8 mappings."]
    if "Map8.amxd" not in global_track.block:
        return xml, [], ["Global track had no Map8.amxd device for global mappings."]

    xml, macro_targets, warnings = ensure_boilerplate_macro_targets(xml)

    global_track = next((track for track in parse_tracks(xml) if track.name == "Global"), None)
    if global_track is None:
        return xml, reports, [*warnings, "No Global track was found after target setup."]

    patched_global = global_track.block
    for target in macro_targets:
        patched_global = _map_map8_slot(
            patched_global,
            target.slot_object,
            target.macro_index,
            target.name,
            target.lom_id,
        )
        reports.append(GlobalMacroReport(target.name, target.target, target.lom_id))

    xml = live_set.replace_range(xml, (global_track.start, global_track.end), patched_global)
    return xml, reports, warnings


def _map_map8_slot(global_block: str, slot_object: str, macro_index: int, macro_name: str, lom_id: str) -> str:
    block, count = re.subn(
        rf'(<MacroDisplayNames\.{macro_index}\b[^>]*\bValue=")[^"]*(" />)',
        rf"\g<1>{live_set.escape_attr(macro_name)}\2",
        global_block,
        count=1,
    )
    if count != 1:
        raise ValueError(f"Could not rename Global macro display {macro_index}.")
    block = _upsert_idref(block, f"{slot_object}::obj-29::obj-18", lom_id, "id")
    block = _upsert_idref(block, f"{slot_object}::obj-28::obj-33", lom_id, "")
    return _enable_map8_toggle(block, macro_index)


def _upsert_idref(block: str, name: str, lom_id: str, property_value: str) -> str:
    if f'<Name Value="{name}" />' in block:
        return _patch_idref_lom(block, name, lom_id)
    idref_range = _populated_idref_list_range(block)
    if idref_range is None:
        raise ValueError("Global Map8 had no populated IdRefList.")

    start, end = idref_range
    idref_block = block[start:end]
    next_id = max((int(match.group(1)) for match in re.finditer(r'<MxDIdRef Id="(\d+)"', idref_block)), default=-1) + 1
    line_sep = "\r\n" if "\r\n" in idref_block else "\n"
    indent_match = re.search(r"(\r?\n[\t ]*)<MxDIdRef Id=\"\d+\">", idref_block)
    if indent_match is None:
        raise ValueError("Could not infer IdRefList indentation.")
    indent = indent_match.group(1)[len(line_sep) :]
    child_indent = indent + "\t"
    entry = (
        f'{indent}<MxDIdRef Id="{next_id}">{line_sep}'
        f'{child_indent}<Name Value="{name}" />{line_sep}'
        f'{child_indent}<LomId Value="{lom_id}" />{line_sep}'
        f'{child_indent}<Property Value="{property_value}" />{line_sep}'
        f"{indent}</MxDIdRef>{line_sep}"
    )
    close = idref_block.rfind("</IdRefList>")
    return live_set.replace_range(block, idref_range, idref_block[:close] + entry + idref_block[close:])


def _patch_idref_lom(block: str, name: str, lom_id: str) -> str:
    pattern = re.compile(
        r'(<MxDIdRef\b[^>]*>\s*<Name Value="' + re.escape(name) + r'" />\s*<LomId Value=")([^"]*)(" />)',
        re.DOTALL,
    )
    block, count = pattern.subn(rf"\g<1>{lom_id}\3", block, count=1)
    if count != 1:
        raise ValueError(f"Could not patch existing MxDIdRef {name}.")
    return block


def _enable_map8_toggle(block: str, macro_index: int) -> str:
    pattern = re.compile(r"(<Blob>\s*)([0-9A-Fa-f\s]+)(\s*</Blob>)")
    match = pattern.search(block)
    if match is None:
        raise ValueError("Global Map8 had no Blob payload.")
    decoded = bytes.fromhex("".join(match.group(2).split())).decode("utf-8")
    key = "live.toggle" if macro_index == 0 else f"live.toggle[{macro_index}]"
    decoded, count = re.subn(
        rf'("{re.escape(key)}"\s*:\s*\[\s*)[^]]+?(\s*\])',
        r"\g<1>1.0\2",
        decoded,
        count=1,
    )
    if count != 1:
        raise ValueError(f"Could not enable Map8 toggle {macro_index}.")
    encoded = decoded.encode("utf-8").hex().upper()
    line_sep = "\r\n" if "\r\n" in match.group(0) else "\n"
    leading = match.group(1)[len("<Blob>") :]
    indent = leading.split(line_sep)[-1] if line_sep in leading else ""
    chunks = [encoded[index : index + 80] for index in range(0, len(encoded), 80)]
    replacement = match.group(1) + (line_sep + indent).join(chunks) + match.group(3)
    return block[: match.start()] + replacement + block[match.end() :]


def _populated_idref_list_range(block: str) -> tuple[int, int] | None:
    return next((r for r in live_set.tag_ranges(block, {"IdRefList"}) if "<MxDIdRef " in block[r[0] : r[1]]), None)

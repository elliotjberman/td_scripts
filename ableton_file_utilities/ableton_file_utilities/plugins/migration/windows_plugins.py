"""Plan and patch Windows-saved plugin references in Ableton sets.

This module is intentionally migration-oriented. It does not try to understand
vendor blobs unless a plugin-specific migration has been calibrated from
known-good Windows and Mac fixtures.
"""

from __future__ import annotations

import dataclasses
import re
import struct
import urllib.parse
from collections.abc import Callable, Iterator

from ableton_file_utilities.core import live_set


WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")
PLUGIN_FLOAT_RE = re.compile(r"<PluginFloatParameter\b[^>]*>(.*?)</PluginFloatParameter>", re.S)
MANUAL_VALUE_RE = re.compile(r'(<Manual\b[^>]*\bValue=")([^"]*)(")')
BUFFER_RE = re.compile(r"<Buffer>\s*(.*?)\s*</Buffer>", re.S)
UID_BLOCK_RE = re.compile(r"<Uid>\s*(.*?)\s*</Uid>", re.S)
FIELD_RE = re.compile(r'(<Fields\.([0-3])\b[^>]*\bValue=")(-?\d+)(")')
SCANNER_FOUND_RE = re.compile(r"VST([23]): found: (.+)$")
SCANNER_FIELD_RE = re.compile(r"\s*(vendor|device-class-id|path):\s*(.+?)\s*$")
VST3_UUID_RE = re.compile(
    r":([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})(?:\?|$)"
)
MIDI_CONTROLLER_RANGE_RE = re.compile(
    r'<MidiControllerRange>\s*<Min\b[^>]*\bValue="([^"]*)"\s*/>\s*<Max\b[^>]*\bValue="([^"]*)"',
    re.S,
)


@dataclasses.dataclass(frozen=True)
class ScannedPlugin:
    format: str
    name: str
    vendor: str | None
    class_id: str | None
    path: str | None


@dataclasses.dataclass(frozen=True)
class PluginParameter:
    name: str
    parameter_id: str | None
    manual: str
    minimum: str | None = None
    maximum: str | None = None


@dataclasses.dataclass(frozen=True)
class ParameterMapping:
    source_name: str
    target_name: str
    source_value: str
    target_old_value: str
    target_new_value: str
    confidence: str


@dataclasses.dataclass(frozen=True)
class ParameterMapResult:
    block: str
    mappings: list[ParameterMapping]
    skipped_targets: list[str]


@dataclasses.dataclass(frozen=True)
class DeviceReport:
    device_index: int
    format: str
    plugin_name: str
    classification: str
    changed: bool
    saved_path: str | None = None
    new_path: str | None = None
    saved_plug_name: str | None = None
    new_plug_name: str | None = None
    saved_class_id: str | None = None
    new_class_id: str | None = None
    warning: str | None = None
    template_source: str | None = None
    parameters_mapped: int = 0
    skipped_parameters: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class _PluginDevice:
    block: str
    format: str
    plugin_name: str
    vendor: str | None
    branch_device_id: str | None
    browser_content_path: str | None
    path: str | None
    plug_name: str | None
    unique_id: str | None
    vst3_uids: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class _TemplateDevice:
    block: str
    device: _PluginDevice


def patch_xml(
    xml: str,
    scanner: list[ScannedPlugin],
    plugin_names: set[str] | None = None,
    reference_xml: str | None = None,
    target_format: str | None = None,
) -> tuple[str, list[DeviceReport]]:
    replacements: list[tuple[int, int, str]] = []
    reports: list[DeviceReport] = []
    normalized_targets = {_plugin_key(name) for name in plugin_names} if plugin_names else None
    templates = _template_devices(reference_xml) if reference_xml and target_format else []
    next_id: int | None = None

    for start, end in live_set.iter_plugin_device_ranges(xml):
        block = xml[start:end]
        device = parse_plugin_device(block)
        if device is None:
            continue
        if normalized_targets and _plugin_key(device.plugin_name) not in normalized_targets:
            continue
        candidate = find_candidate(device, scanner)
        template = (
            find_template_device(device, candidate, templates, target_format)
            if device.format == "VST2" and templates and target_format
            else None
        )
        if template:
            if next_id is None:
                next_id = live_set.next_pointee_id(xml)
            new_block, next_id, report = clone_template_block(device, template, next_id, len(reports) + 1)
        else:
            new_block, report = patch_block(device, candidate, len(reports) + 1)
        reports.append(report)
        if new_block != block:
            replacements.append((start, end, new_block))

    patched = live_set.replace_ranges(xml, replacements)
    if next_id is not None and next_id != live_set.next_pointee_id(xml):
        patched = live_set.set_next_pointee_id(patched, next_id)
    return patched, reports


def parse_plugin_scanner(text: str) -> list[ScannedPlugin]:
    plugins: list[ScannedPlugin] = []
    current: dict[str, str] | None = None

    for line in text.splitlines():
        found = SCANNER_FOUND_RE.search(line)
        if found:
            if current:
                plugins.append(_scanner_plugin(current))
            current = {"format": f"VST{found.group(1)}", "name": found.group(2).strip()}
            continue
        if current is None:
            continue
        field = SCANNER_FIELD_RE.match(line)
        if field:
            current[field.group(1)] = _unquote_scanner_value(field.group(2))

    if current:
        plugins.append(_scanner_plugin(current))
    return plugins


def _scanner_plugin(values: dict[str, str]) -> ScannedPlugin:
    return ScannedPlugin(
        format=values["format"],
        name=values["name"],
        vendor=values.get("vendor"),
        class_id=values.get("device-class-id"),
        path=values.get("path"),
    )


def _unquote_scanner_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def parse_plugin_device(block: str) -> _PluginDevice | None:
    if "<Vst3PluginInfo" in block:
        return _parse_vst3_device(block)
    if "<VstPluginInfo" in block:
        return _parse_vst2_device(block)
    return None


def _template_devices(xml: str | None) -> list[_TemplateDevice]:
    if not xml:
        return []
    templates: list[_TemplateDevice] = []
    for start, end in live_set.iter_plugin_device_ranges(xml):
        block = xml[start:end]
        device = parse_plugin_device(block)
        if device is not None:
            templates.append(_TemplateDevice(block, device))
    return templates


def find_template_device(
    source: _PluginDevice,
    candidate: ScannedPlugin | None,
    templates: list[_TemplateDevice],
    target_format: str,
) -> _TemplateDevice | None:
    if source.format != "VST2":
        return None
    for template in templates:
        if template.device.format != target_format:
            continue
        if target_format == "VST2" and source.unique_id and template.device.unique_id == source.unique_id:
            return template
        if candidate and _plugin_key(template.device.plugin_name) == _plugin_key(candidate.name):
            return template
        if _plugin_key(template.device.plugin_name) == _plugin_key(source.plugin_name):
            return template
    return None


def clone_template_block(
    source: _PluginDevice,
    template: _TemplateDevice,
    next_id: int,
    device_index: int,
) -> tuple[str, int, DeviceReport]:
    plugin_id = _plugin_device_id(source.block)
    if plugin_id is None:
        return (
            source.block,
            next_id,
            _report(
                source,
                device_index,
                "vst2-template-clone-skipped",
                False,
                warning="Source PluginDevice has no Id.",
            ),
        )
    cloned, next_id = live_set.remap_cloned_plugin_device(template.block, plugin_id, next_id)
    cloned = live_set.copy_device_on_state(source.block, cloned)
    mapped = map_parameter_values(source.block, cloned)
    mapped_block = mapped.block
    if template.device.format == "VST3":
        mapper = VST3_PROCESSOR_STATE_MAPPERS.get(_plugin_key(source.plugin_name))
        if mapper:
            mapped_block = mapper(source.block, mapped_block)
    changed = mapped_block != source.block
    return (
        mapped_block,
        next_id,
        _report(
            source,
            device_index,
            f"{template.device.format.lower()}-template-clone-with-parameter-map",
            changed,
            new_path=template.device.path,
            new_plug_name=template.device.plug_name,
            new_class_id=template.device.branch_device_id,
            template_source=template.device.plugin_name,
            parameters_mapped=len(mapped.mappings),
            skipped_parameters=tuple(mapped.skipped_targets),
        ),
    )


def _plugin_device_id(block: str) -> int | None:
    match = re.search(r'<PluginDevice\b[^>]*\bId="(\d+)"', block)
    return int(match.group(1)) if match else None


def _parse_vst2_device(block: str) -> _PluginDevice:
    browser = live_set.tag_value(block, "BrowserContentPath")
    branch = live_set.tag_value(block, "BranchDeviceId")
    path = live_set.tag_value(block, "Path")
    plug_name = live_set.tag_value(block, "PlugName")
    unique_id = live_set.tag_value(block, "UniqueId")
    name = plug_name or _query_name(branch) or _query_name(browser) or "Unknown VST2"
    return _PluginDevice(
        block=block,
        format="VST2",
        plugin_name=name,
        vendor=_vendor_from_browser_path(browser),
        branch_device_id=branch,
        browser_content_path=browser,
        path=path,
        plug_name=plug_name,
        unique_id=unique_id,
        vst3_uids=(),
    )


def _parse_vst3_device(block: str) -> _PluginDevice:
    browser = live_set.tag_value(block, "BrowserContentPath")
    branch = live_set.tag_value(block, "BranchDeviceId")
    name = _vst3_name(block) or _query_name(branch) or _query_name(browser) or "Unknown VST3"
    return _PluginDevice(
        block=block,
        format="VST3",
        plugin_name=name,
        vendor=_vendor_from_browser_path(browser),
        branch_device_id=branch,
        browser_content_path=browser,
        path=None,
        plug_name=None,
        unique_id=None,
        vst3_uids=_vst3_uids_from_block(block),
    )


def _vst3_name(block: str) -> str | None:
    match = re.search(r"<Vst3PluginInfo\b.*?</Vst3PluginInfo>", block, re.S)
    if not match:
        return None
    names = live_set.tag_values(match.group(0), "Name")
    named = [name for name in names if name]
    return named[-1] if named else None


def _vst3_uids_from_block(block: str) -> tuple[str, ...]:
    uids: list[str] = []
    for match in UID_BLOCK_RE.finditer(block):
        fields = {int(field.group(2)): int(field.group(3)) for field in FIELD_RE.finditer(match.group(1))}
        if set(fields) == {0, 1, 2, 3}:
            uids.append(uuid_from_signed_words([fields[index] for index in range(4)]))
    return tuple(uids)


def _query_name(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"[?&]n=([^&]+)", value)
    if match:
        return urllib.parse.unquote(match.group(1))
    if _class_id_uuid(value):
        return None
    if ":" in value:
        return urllib.parse.unquote(value.rsplit(":", 1)[-1])
    return None


def _vendor_from_browser_path(value: str | None) -> str | None:
    if not value or "#" not in value:
        return None
    parts = value.split("#", 1)[1].split(":")
    if len(parts) < 3:
        return None
    if parts[0] == "VST3":
        return urllib.parse.unquote(parts[1])
    if parts[0] == "VST" and len(parts) >= 4:
        return urllib.parse.unquote(parts[2])
    return None


def find_candidate(device: _PluginDevice, scanner: list[ScannedPlugin]) -> ScannedPlugin | None:
    if device.format == "VST2":
        for plugin in scanner:
            if plugin.format == "VST2" and _same_class_id(plugin.class_id, device.branch_device_id):
                return plugin
        if device.unique_id:
            for plugin in scanner:
                if plugin.format == "VST2" and plugin.class_id and f":{device.unique_id}?n=" in plugin.class_id:
                    return plugin
        return _name_candidate(device, scanner, "VST2")

    if device.format == "VST3":
        exact = [
            plugin
            for plugin in scanner
            if plugin.format == "VST3" and _same_class_id(plugin.class_id, device.branch_device_id)
        ]
        if exact:
            return exact[0]
        return _name_candidate(device, scanner, "VST3")

    return None


def _name_candidate(device: _PluginDevice, scanner: list[ScannedPlugin], plugin_format: str) -> ScannedPlugin | None:
    matches = [
        plugin
        for plugin in scanner
        if plugin.format == plugin_format
        and _norm(plugin.name) == _norm(device.plugin_name)
        and (not device.vendor or not plugin.vendor or _norm(plugin.vendor) == _norm(device.vendor))
    ]
    return matches[0] if matches else None


def patch_block(
    device: _PluginDevice,
    candidate: ScannedPlugin | None,
    device_index: int,
) -> tuple[str, DeviceReport]:
    if candidate is None:
        return device.block, _report(
            device,
            device_index,
            "missing-install",
            False,
            warning="No scanned plugin candidate found.",
        )

    if device.format == "VST2":
        return _patch_vst2_block(device, candidate, device_index)
    if device.format == "VST3":
        return _patch_vst3_block(device, candidate, device_index)
    return device.block, _report(device, device_index, "unsupported-format", False)


def _patch_vst2_block(
    device: _PluginDevice,
    candidate: ScannedPlugin,
    device_index: int,
) -> tuple[str, DeviceReport]:
    path_changed = bool(candidate.path and device.path and candidate.path != device.path)
    name_changed = bool(candidate.name and device.plug_name and candidate.name != device.plug_name)
    windows_path = bool(device.path and WINDOWS_PATH_RE.match(device.path))

    if name_changed and windows_path:
        classification = "windows-vst2-name-and-path-restore-failure"
    elif windows_path:
        classification = "windows-vst2-path-restore-failure"
    elif name_changed:
        classification = "vst2-name-mismatch"
    else:
        classification = "installed-vst2-id-match"

    block = device.block
    if path_changed and candidate.path:
        block = live_set.replace_tag_value(block, "Path", candidate.path, count=1)
    if name_changed:
        block = live_set.replace_tag_value(block, "PlugName", candidate.name, count=1)

    changed = block != device.block
    return block, _report(
        device,
        device_index,
        classification,
        changed,
        new_path=candidate.path if path_changed else None,
        new_plug_name=candidate.name if name_changed else None,
    )


def _patch_vst3_block(
    device: _PluginDevice,
    candidate: ScannedPlugin,
    device_index: int,
) -> tuple[str, DeviceReport]:
    candidate_uid = _class_id_uuid(candidate.class_id)
    branch_uid = _class_id_uuid(device.branch_device_id)
    candidate_device_id = _class_id_without_query(candidate.class_id)
    if not candidate_uid:
        return device.block, _report(
            device,
            device_index,
            "missing-vst3-class-id",
            False,
            warning="Candidate has no VST3 class ID.",
        )
    branch_matches = not device.branch_device_id or branch_uid == candidate_uid
    preset_matches = all(uid == candidate_uid for uid in device.vst3_uids)
    if branch_matches and preset_matches:
        return device.block, _report(device, device_index, "installed-vst3-id-match", False)

    block = device.block
    if device.branch_device_id and candidate_device_id:
        block = live_set.replace_tag_value(block, "BranchDeviceId", candidate_device_id, count=1)
    block = _replace_vst3_uid_fields(block, signed_words_from_uuid(candidate_uid))
    changed = block != device.block
    return block, _report(
        device,
        device_index,
        "windows-vst3-class-id-mismatch",
        changed,
        new_class_id=candidate_device_id,
    )


def _report(
    device: _PluginDevice,
    device_index: int,
    classification: str,
    changed: bool,
    new_path: str | None = None,
    new_plug_name: str | None = None,
    new_class_id: str | None = None,
    warning: str | None = None,
    template_source: str | None = None,
    parameters_mapped: int = 0,
    skipped_parameters: tuple[str, ...] = (),
) -> DeviceReport:
    return DeviceReport(
        device_index=device_index,
        format=device.format,
        plugin_name=device.plugin_name,
        classification=classification,
        changed=changed,
        saved_path=device.path,
        new_path=new_path,
        saved_plug_name=device.plug_name,
        new_plug_name=new_plug_name,
        saved_class_id=device.branch_device_id,
        new_class_id=new_class_id,
        warning=warning,
        template_source=template_source,
        parameters_mapped=parameters_mapped,
        skipped_parameters=skipped_parameters,
    )


def _replace_vst3_uid_fields(block: str, words: list[int]) -> str:
    def replace_uid(match: re.Match[str]) -> str:
        def replace_field(field_match: re.Match[str]) -> str:
            index = int(field_match.group(2))
            return f"{field_match.group(1)}{words[index]}{field_match.group(4)}"

        return f"<Uid>{FIELD_RE.sub(replace_field, match.group(1))}</Uid>"

    return UID_BLOCK_RE.sub(replace_uid, block)


def _class_id_uuid(class_id: str | None) -> str | None:
    if not class_id:
        return None
    match = VST3_UUID_RE.search(class_id)
    return match.group(1).lower() if match else None


def _class_id_without_query(class_id: str | None) -> str | None:
    if not class_id:
        return None
    return class_id.split("?", 1)[0]


def _same_class_id(left: str | None, right: str | None) -> bool:
    return bool(left and right and _class_id_without_query(left) == _class_id_without_query(right))


def signed_words_from_uuid(uuid_text: str) -> list[int]:
    raw = uuid_text.replace("-", "")
    if len(raw) != 32:
        raise ValueError(f"Expected 32 hex digits in VST3 UUID, got {uuid_text!r}.")
    words = []
    for index in range(0, 32, 8):
        value = int(raw[index : index + 8], 16)
        words.append(value if value < 2**31 else value - 2**32)
    return words


def uuid_from_signed_words(words: list[int]) -> str:
    if len(words) != 4:
        raise ValueError("VST3 UID needs exactly four 32-bit fields.")
    hex_words = [f"{word & 0xFFFFFFFF:08x}" for word in words]
    raw = "".join(hex_words)
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


def extract_parameters(block: str) -> list[PluginParameter]:
    return [parameter for parameter, _chunk in _iter_parameter_chunks(block)]


def _iter_parameter_chunks(block: str) -> Iterator[tuple[PluginParameter, str]]:
    for match in PLUGIN_FLOAT_RE.finditer(block):
        chunk = match.group(1)
        parameter = _parameter_from_chunk(chunk)
        if parameter:
            yield parameter, chunk


def map_parameter_values(source_block: str, target_block: str) -> ParameterMapResult:
    source = {_norm(parameter.name): (parameter, chunk) for parameter, chunk in _iter_parameter_chunks(source_block)}
    mappings: list[ParameterMapping] = []
    skipped: list[str] = []
    pieces: list[str] = []
    cursor = 0

    for match in PLUGIN_FLOAT_RE.finditer(target_block):
        pieces.append(target_block[cursor : match.start()])
        target_chunk = match.group(1)
        target_param = _parameter_from_chunk(target_chunk)
        replacement = match.group(0)

        if target_param:
            source_entry = source.get(_norm(target_param.name))
            if source_entry:
                source_param, source_chunk = source_entry
                target_value = _target_manual_value(source_param.manual, target_param.minimum, target_param.maximum)
                new_chunk = _replace_manual_value(target_chunk, target_value)
                new_chunk = live_set.copy_global_target_ids(source_chunk, new_chunk)
                confidence = "exact-name" if source_param.name == target_param.name else "normalized-name"
                mappings.append(
                    ParameterMapping(
                        source_name=source_param.name,
                        target_name=target_param.name,
                        source_value=source_param.manual,
                        target_old_value=target_param.manual,
                        target_new_value=target_value,
                        confidence=confidence,
                    )
                )
                if new_chunk != target_chunk:
                    replacement = replacement.replace(target_chunk, new_chunk, 1)
            else:
                skipped.append(target_param.name)

        pieces.append(replacement)
        cursor = match.end()

    pieces.append(target_block[cursor:])
    return ParameterMapResult("".join(pieces), mappings, skipped)


def map_ott_vst3_processor_state(source_block: str, target_block: str) -> str:
    source_values = _normalized_parameter_values_by_id(source_block)
    if not source_values:
        return target_block
    parameter_ids = sorted(source_values)
    if parameter_ids != list(range(len(parameter_ids))):
        return target_block
    values = [source_values[parameter_id] for parameter_id in parameter_ids]
    return _replace_processor_state_floats(target_block, values)


def map_permut8_vst3_processor_state(source_block: str, target_block: str) -> str:
    source_buffer = _hex_tag_bytes(source_block, BUFFER_RE)
    if not source_buffer:
        return target_block
    try:
        program_number = int(live_set.tag_value(source_block, "ProgramNumber") or "0")
    except ValueError:
        program_number = 0
    return _replace_permut8_processor_state_buffer(target_block, source_buffer, program_number)


def map_sieq_vst3_processor_state(source_block: str, target_block: str) -> str:
    source_buffer = _hex_tag_bytes(source_block, BUFFER_RE)
    if not source_buffer:
        return target_block
    return _replace_sieq_processor_state_buffer(target_block, source_buffer)


VST3_PROCESSOR_STATE_MAPPERS: dict[str, Callable[[str, str], str]] = {
    "ott": map_ott_vst3_processor_state,
    "permut8": map_permut8_vst3_processor_state,
    "sieq": map_sieq_vst3_processor_state,
}


def _parameter_from_chunk(chunk: str) -> PluginParameter | None:
    name = live_set.tag_value(chunk, "ParameterName")
    manual = live_set.tag_value(chunk, "Manual")
    if not name or manual is None:
        return None
    minimum, maximum = _manual_ranges(chunk)
    return PluginParameter(
        name=name,
        parameter_id=live_set.tag_value(chunk, "ParameterId"),
        manual=manual,
        minimum=minimum,
        maximum=maximum,
    )


def _normalized_parameter_values_by_id(block: str) -> dict[int, float]:
    values: dict[int, float] = {}
    for param in extract_parameters(block):
        if param.parameter_id is None:
            continue
        try:
            parameter_id = int(param.parameter_id)
            if parameter_id < 0:
                continue
            values[parameter_id] = float(param.manual)
        except ValueError:
            continue
    return values


def _replace_processor_state_floats(block: str, values: list[float]) -> str:
    match = live_set.HEX_STATE_RE.search(block)
    if not match:
        return block

    hex_state = "".join(match.group(2).split())
    if not hex_state or len(hex_state) % 8:
        return block
    existing = bytes.fromhex(hex_state)
    float_count = len(existing) // 4
    if len(values) > float_count:
        return block

    patched = b"".join(struct.pack("<f", value) for value in values) + existing[len(values) * 4 :]
    return live_set.replace_processor_state(block, match, patched, width=96)


def _replace_permut8_processor_state_buffer(block: str, source_buffer: bytes, program_number: int) -> str:
    match = live_set.HEX_STATE_RE.search(block)
    if not match:
        return block

    state = live_set.bytes_from_hex_match(match)
    if len(state) < 178 or state[10:14] != b"CcnK":
        return block

    patched = bytearray(state[:170] + source_buffer)
    patched[4] = 0
    patched[5] = max(0, min(program_number, 255))
    _write_u16_le(patched, 6, len(patched) - 10)
    _write_u32_be(patched, 14, len(patched) - 18)
    _write_u16_be(patched, 168, len(source_buffer))

    return live_set.replace_processor_state(block, match, bytes(patched), width=96)


def _replace_sieq_processor_state_buffer(block: str, source_buffer: bytes) -> str:
    match = live_set.HEX_STATE_RE.search(block)
    if not match:
        return block

    state = live_set.bytes_from_hex_match(match)
    body_start = state.find(b"WIDGET = Sie-Q;")
    if body_start < 4 or state[16:20] != b"CcnK":
        return block

    patched = bytearray(state[:body_start] + source_buffer)
    _write_u32_be(patched, 20, len(patched) - 24)
    _write_u32_be(patched, body_start - 4, len(source_buffer))

    return live_set.replace_processor_state(block, match, bytes(patched), width=96)


def _hex_tag_bytes(block: str, pattern: re.Pattern[str]) -> bytes | None:
    match = pattern.search(block)
    if not match:
        return None
    try:
        return live_set.hex_text_to_bytes(match.group(1))
    except ValueError:
        return None


def _write_u16_le(buffer: bytearray, offset: int, value: int) -> None:
    buffer[offset : offset + 2] = value.to_bytes(2, "little")


def _write_u16_be(buffer: bytearray, offset: int, value: int) -> None:
    buffer[offset : offset + 2] = value.to_bytes(2, "big")


def _write_u32_be(buffer: bytearray, offset: int, value: int) -> None:
    buffer[offset : offset + 4] = value.to_bytes(4, "big")


def _manual_ranges(chunk: str) -> tuple[str | None, str | None]:
    range_match = MIDI_CONTROLLER_RANGE_RE.search(chunk)
    if not range_match:
        return None, None
    return range_match.group(1), range_match.group(2)


def _target_manual_value(source_value: str, target_minimum: str | None, target_maximum: str | None) -> str:
    if target_minimum is None or target_maximum is None:
        return source_value
    try:
        normalized = float(source_value)
        minimum = float(target_minimum)
        maximum = float(target_maximum)
    except ValueError:
        return source_value
    if minimum == 0.0 and maximum == 1.0:
        return source_value
    return _format_float(minimum + normalized * (maximum - minimum))


def _format_float(value: float) -> str:
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def _replace_manual_value(chunk: str, value: str) -> str:
    return MANUAL_VALUE_RE.sub(lambda match: f"{match.group(1)}{value}{match.group(3)}", chunk, count=1)


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", urllib.parse.unquote(value).lower())


def _plugin_key(value: str) -> str:
    normalized = _norm(value)
    if normalized.endswith("x64"):
        normalized = normalized[:-3]
    return normalized

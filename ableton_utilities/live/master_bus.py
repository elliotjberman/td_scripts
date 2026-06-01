"""Master bus boilerplate helpers for Ableton live sets."""

from __future__ import annotations

import dataclasses
import re

from ableton_utilities import live_set


TDA_MASTER_MARKER = "TDA_Master.amxd"
TDA_MASTER_REPORT = "TDAMaster -> Master"
DEVICE_ID_RE = re.compile(r'(<[A-Za-z_][\w:.-]*\b[^>]*\bId=")(\d+)(")')


@dataclasses.dataclass(frozen=True)
class MasterBusResult:
    xml: str
    next_global_id: int
    added: bool
    warnings: list[str]


def ensure_tda_master(xml: str, template_xml: str, next_global_id: int) -> MasterBusResult:
    master_range = live_set.first_tag_range(xml, "MasterTrack")
    if master_range is None:
        return MasterBusResult(xml, next_global_id, False, ["No MasterTrack was found for TDAMaster."])
    master = xml[master_range[0] : master_range[1]]
    if TDA_MASTER_MARKER in master:
        return MasterBusResult(xml, next_global_id, False, [])

    template_device = _template_tda_master_device(template_xml)
    if template_device is None:
        return MasterBusResult(xml, next_global_id, False, ["No template TDAMaster device was found."])

    device, next_global_id, _ = live_set.remap_global_ids_with_map(template_device, next_global_id)
    device = _remap_nonzero_lom_ids(device, _next_lom_id(xml))
    patched_master = _append_master_device(master, device)
    xml = live_set.replace_range(xml, master_range, patched_master)
    return MasterBusResult(xml, next_global_id, True, [])


def _template_tda_master_device(xml: str) -> str | None:
    master_range = live_set.first_tag_range(xml, "MasterTrack")
    if master_range is None:
        return None
    master = xml[master_range[0] : master_range[1]]
    marker = master.find(TDA_MASTER_MARKER)
    if marker < 0:
        return None
    device_ranges = live_set.tag_ranges(master, {"MxDeviceAudioEffect"})
    containing = [item_range for item_range in device_ranges if item_range[0] <= marker < item_range[1]]
    if not containing:
        return None
    start, end = min(containing, key=lambda item_range: item_range[1] - item_range[0])
    return master[start:end]


def _append_master_device(master: str, device: str) -> str:
    devices_range = _master_devices_range(master)
    devices = master[devices_range[0] : devices_range[1]]
    children = _direct_children(devices)
    device = _set_root_device_id(device, _next_device_id(children))
    close = devices.rfind("</Devices>")
    line_sep = "\r\n" if "\r\n" in devices else "\n"
    patched_devices = f"{devices[:close]}{line_sep}{device}{line_sep}{devices[close:]}"
    return live_set.replace_range(master, devices_range, patched_devices)


def _master_devices_range(master: str) -> tuple[int, int]:
    outer = _direct_child_range(master, (0, len(master)), "DeviceChain")
    if outer is None:
        raise ValueError("MasterTrack had no DeviceChain.")
    inner = _direct_child_range(master, outer, "DeviceChain")
    if inner is None:
        raise ValueError("MasterTrack had no inner DeviceChain.")
    devices = _direct_child_range(master, inner, "Devices")
    if devices is None:
        raise ValueError("MasterTrack had no direct Devices list.")
    return devices


def _direct_child_range(xml: str, parent_range: tuple[int, int], tag: str) -> tuple[int, int] | None:
    start, end = parent_range
    open_end = xml.find(">", start, end) + 1
    depth = 0
    for match in live_set.XML_TAG_RE.finditer(xml, open_end, end):
        closing, name, _attrs, self_closing = match.groups()
        if closing:
            if depth == 0:
                return None
            depth -= 1
            continue
        if depth == 0 and name == tag:
            return (match.start(), match.end()) if self_closing else _tag_range_from_open(xml, match.start(), end)
        if not self_closing:
            depth += 1
    return None


def _tag_range_from_open(xml: str, start: int, end: int) -> tuple[int, int]:
    tag = live_set.XML_TAG_RE.match(xml, start).group(2)
    depth = 0
    for match in live_set.XML_TAG_RE.finditer(xml, start, end):
        closing, name, _attrs, self_closing = match.groups()
        if name != tag:
            continue
        if closing:
            depth -= 1
            if depth == 0:
                return start, match.end()
        elif not self_closing:
            depth += 1
    raise ValueError(f"No matching close tag for <{tag}>.")


def _direct_children(block: str) -> list[str]:
    open_end = block.find(">") + 1
    close = block.rfind("</")
    return live_set.direct_child_blocks(block[open_end:close])


def _next_device_id(devices: list[str]) -> int:
    ids = []
    for device in devices:
        match = re.match(r'<[A-Za-z_][\w:.-]*\b[^>]*\bId="(\d+)"', device)
        if match:
            ids.append(int(match.group(1)))
    return max(ids, default=-1) + 1


def _set_root_device_id(device: str, device_id: int) -> str:
    return DEVICE_ID_RE.sub(rf"\g<1>{device_id}\3", device, count=1)


def _remap_nonzero_lom_ids(block: str, first_lom_id: int) -> str:
    next_lom_id = first_lom_id
    lomid_map: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        nonlocal next_lom_id
        old_id = match.group(2)
        if old_id == "0":
            return match.group(0)
        if old_id not in lomid_map:
            lomid_map[old_id] = str(next_lom_id)
            next_lom_id += 1
        return f"{match.group(1)}{lomid_map[old_id]}{match.group(3)}"

    return re.sub(r'(<LomId\b[^>]*\bValue=")(\d+)(")', replace, block)


def _next_lom_id(xml: str) -> int:
    return max((int(value) for value in re.findall(r'<LomId\b[^>]*\bValue="(\d+)"', xml)), default=0) + 1

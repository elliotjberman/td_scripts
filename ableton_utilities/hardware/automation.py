"""Copy group automation envelopes onto generated hardware-live tracks."""

from __future__ import annotations

import re

from ableton_utilities import live_set


POINTEE_ID_RE = re.compile(r'(<PointeeId\b[^>]*\bValue=")(\d+)(")')


def copy_mapped_automation_envelopes(source_track: str, target_track: str, id_map: dict[str, str]) -> str:
    source_envelopes = _mapped_source_envelopes(source_track, id_map)
    if not source_envelopes:
        return target_track

    automation_range = live_set.first_tag_range(target_track, "AutomationEnvelopes")
    if automation_range is None:
        return target_track

    target_ids = _global_target_ids(target_track)
    existing = _valid_existing_envelopes(target_track[automation_range[0] : automation_range[1]], target_ids)
    envelopes = _renumber_envelopes([*existing, *source_envelopes])
    return live_set.replace_range(target_track, automation_range, _automation_block(envelopes))


def missing_automation_targets(track_block: str) -> set[str]:
    target_ids = _global_target_ids(track_block)
    missing: set[str] = set()
    for envelope in _automation_envelopes(track_block):
        missing.update(target_id for target_id in _pointee_ids(envelope) if target_id not in target_ids)
    return missing


def _mapped_source_envelopes(source_track: str, id_map: dict[str, str]) -> list[str]:
    envelopes = []
    for envelope in _automation_envelopes(source_track):
        source_ids = _pointee_ids(envelope)
        if not source_ids or any(target_id not in id_map for target_id in source_ids):
            continue
        envelopes.append(_rewrite_pointee_ids(envelope, id_map))
    return envelopes


def _valid_existing_envelopes(automation_block: str, target_ids: set[str]) -> list[str]:
    return [
        envelope
        for envelope in _automation_envelopes(automation_block)
        if all(target_id in target_ids for target_id in _pointee_ids(envelope))
    ]


def _automation_envelopes(xml: str) -> list[str]:
    envelopes = []
    for start, end in live_set.tag_ranges(xml, {"AutomationEnvelope"}):
        block = xml[start:end]
        if block.lstrip().startswith("<AutomationEnvelopes"):
            continue
        envelopes.append(block)
    return envelopes


def _rewrite_pointee_ids(envelope: str, id_map: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        return f"{match.group(1)}{id_map[match.group(2)]}{match.group(3)}"

    return POINTEE_ID_RE.sub(replace, envelope)


def _pointee_ids(envelope: str) -> list[str]:
    return [match.group(2) for match in POINTEE_ID_RE.finditer(envelope)]


def _global_target_ids(track_block: str) -> set[str]:
    return {match.group(2) for match in live_set.GLOBAL_TARGET_RE.finditer(track_block)}


def _renumber_envelopes(envelopes: list[str]) -> list[str]:
    return [_set_envelope_id(envelope, index) for index, envelope in enumerate(envelopes)]


def _set_envelope_id(envelope: str, envelope_id: int) -> str:
    return re.sub(
        r'(<AutomationEnvelope\b[^>]*\bId=")\d+(")',
        rf"\g<1>{envelope_id}\2",
        envelope,
        count=1,
    )


def _automation_block(envelopes: list[str]) -> str:
    if not envelopes:
        return "<AutomationEnvelopes>\n\t\t\t\t\t<Envelopes />\n\t\t\t\t</AutomationEnvelopes>"
    body = "\n".join(envelopes)
    return f"<AutomationEnvelopes>\n\t\t\t\t\t<Envelopes>\n{body}\n\t\t\t\t\t</Envelopes>\n\t\t\t\t</AutomationEnvelopes>"

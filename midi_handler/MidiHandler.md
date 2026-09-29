# MidiHandler

Routes incoming note events to existing triggers and ScaledEnvelopes. Keep the
handler and song-specific MIDI sources outside the reusable visual; the envelopes
and their animation/effect chains remain inside it.

In Teachers Pet the handler lives at `/project1/MappedVisual/MidiHandler`,
beside the song receivers and nested reusable `visual`. **Target Visual**
(`Targetroot`) points to that sibling visual. Envelope discovery and routing both use that target.
Source discovery searches the handler's parent for `*_midi` operators, so song
sources can live alongside it without being included in a visual export.

Mappings retain the existing per-source tables: `drums_midi` uses
`drums_note_mappings`, with `note_number` and `trigger_name` columns. Target names
are paths relative to Target Visual, such as `PlaneNoiseEnvelope`; `_` is the
wildcard note, and a note may have multiple target rows. The handler retains
per-source last-note CHOPs and stores velocity on the triggered envelope.
See the shared [ScaledEnvelope guide](../midi_handler_v2/ScaledEnvelope.md).

The repository [MidiHandler.tox](MidiHandler.tox) now includes this routing
interface. **Target Visual** defaults to the handler's parent for the original
sibling-envelope layout; select the nested visual for a mapped wrapper.
Missing targets raise visible errors instead of silently skipping a mapping.
Tables and callbacks are embedded, with no loose TSV/Python file dependency.

External TSVs are still useful as authoring data or for version-controlled song
mappings. Import their contents into the Table DAT before exporting a performance
TOX; do not leave Sync to File enabled unless that external dependency is intentional.
Embedded tables improve deployment portability, not the quality of the mapping data.

[extension.py](extension.py) and [table_creation_callbacks.py](table_creation_callbacks.py)
are the reviewable sources. Run `update_component.update(handler)` in TD to embed
source changes into an existing handler without altering its mapping rows, then
save its TOX. This is an authoring action, not performance-time file loading.

The note-routing entrypoint remains
`HandleNote(source_name, note_number, velocity)`; the source must provide its
mapping table and last-note CHOP. Teachers Pet uses the official TDBitwig OSC
receiver outside the visual; see [Bitwig](Bitwig.md) for the drum-note setup.

## SimpleRayTK verification — 2026-09-20

The old handler inside the visual and the unused top-level `tdAbleton` were
removed. All seven envelopes remain inside the visual and are discovered through
Target Visual. A temporary note-60 route triggered `PlaneNoiseEnvelope`: its
output and the plane-noise amplitude both reached 0.2 and returned to zero.
The temporary mapping and last-note CHOP were removed after this check. This
verified the relocated routing entrypoint, not a live Bitwig connection.

## Reusable export verification — 2026-09-28

Loaded the saved component in a separate TD 2025.33070 test network. Synthetic
notes verified exact-note plus wildcard routing, velocity storage, last-note
output, note-off/source filtering, and visible missing-target errors. The exported
TOX was reloaded under a renamed container and routed independently there.
This check did not operate Bitwig or replace the performance patch.

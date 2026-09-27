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

This guide describes the embedded Teachers Pet variant. The repository
[extension.py](extension.py) predates its Target Visual support; updating that
source is separate implementation work. In the embedded variant, Target Visual is required;
missing targets raise visible errors instead of silently skipping a mapping.
The mapping tables are embedded, not synchronized to loose TSV files.
The moved live instance embeds its extension and callback text, so routing does
not depend on a local checkout being available during a show.

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

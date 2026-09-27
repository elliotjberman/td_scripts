# PlaneNoiseEnvelope

A local ScaledEnvelope drives the amplitude of `plane_noise`:

```text
5 key / Trigger → PlaneNoiseEnvelope → plane_noise_amount → plane_noise.Amplitude
```

- **Debug key:** `5`, checked against all loaded envelope assignments when created.
- **Output minimum:** `0`.
- **Output maximum:** `0.2` (the nominal single-trigger maximum).
- **Layout:** below the key-4 `BloomEnvelope`, preserving ascending debug-key order.
- **Timing:** adjust Attack and Release on this envelope to shape the bump.

The amplitude expression is `parent().op('plane_noise_amount')[0]`. The envelope,
reference Null CHOP, and target live inside the visual export boundary. The
visual parent needs no additional parameters.

The copied Trigger CHOP currently uses additive retriggering with Clamp Peak
off, so overlapping triggers can exceed the nominal maximum. This existing
retrigger behavior is preserved.

## Minilogue note route

The external `/project1/MappedVisual/minilogue_midi` receiver routes positive-velocity notes
from **`(Mini_trig)`** through `MidiHandler/minilogue_note_mappings` to this
envelope. Note-offs are ignored. The Required Source Track guard prevents notes
from another selected track from firing it. For initial setup, select
`(Mini_trig)` in Bitwig once; `pin_source` then pins the receiver and disables
itself. The existing debug key, timing, range, and retrigger behavior stay intact.

A synthetic handler event verified matching envelope output and plane-noise
amplitude at 0.2, returning to zero. This checks the TD route; it does not claim
a live Minilogue note was received.

Verified live on 2026-09-19 after reopening revision 31: at rest, both output and
amplitude were zero. A Trigger pulse produced a sampled output of 0.179292;
the reference Null and plane-noise amplitude matched exactly, and all returned
to zero after release. The rendered output remained visible with no visual
component errors. Debug key 5 remained assigned to the keyboard input.

See [ScaledEnvelope](../midi_handler_v2/ScaledEnvelope.md) for the shared component
guide and naming, debug-key allocation, and layout rules.

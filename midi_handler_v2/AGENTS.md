# MIDI Handler V2

Read [README.md](README.md) for setup, manager entrypoints, and the portable path
contract. Read [ScaledEnvelope.md](ScaledEnvelope.md) before creating, wiring,
or modifying a ScaledEnvelope, including when using it in another folder's visual.

## Authoring and routing

- ScaledEnvelope is a primary animation building block for this user, usually
  triggered by MIDI notes. Preserve its adjustable output range and number-key
  debugging workflow.
- Creation helpers live in `manager/envelopes.py`. Preserve the `scaled-envelope`
  and `midi-route-target` tags, named reference Null CHOP, and debug/test key.
- Inspect the loaded component's parameters and output before wiring it. The
  creator can fall back to an empty Base COMP if loading fails; creation alone
  does not prove a working envelope.
- Keep mappings in each source wrapper's `mappings_json`, with target paths
  relative to that wrapper. Allow multiple targets per note and wildcard routes.
- The current router pulses targets on positive-velocity note events. It stores
  note and velocity on targets, but that alone does not prove velocity scales
  the envelope or that note-off controls release. Verify these details in TD.
- Keep discovery and mapping UI separate from performance callbacks. The current
  source wrappers are TDAbleton-specific; defer Bitwig migration until requested.

## Component documentation

- [ScaledEnvelope](ScaledEnvelope.md): ADSR animation, output min/max, MIDI
  triggering, and keyboard debugging.
- Add further component guides alongside their files and link them here.

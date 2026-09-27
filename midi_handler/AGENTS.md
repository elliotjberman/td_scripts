# MIDI Handler

This folder contains the older MIDI handler workflow and a copy of
`ScaledEnvelope.tox`.

See [MidiHandler](MidiHandler.md) for placement outside a visual, its Target
Visual reference, and the existing per-source note-routing contract.
See [Bitwig](Bitwig.md) for the official TDBitwig OSC connection and note callback.

Before using or modifying ScaledEnvelope, read the shared
[ScaledEnvelope component guide](../midi_handler_v2/ScaledEnvelope.md). Preserve
its role as a MIDI-triggered ADSR animation source with adjustable output
minimum/maximum and configurable number-key debugging.

Keep component usage documentation in the shared guide. Inspect the loaded
component before assuming this copy and the v2 copy have identical internals.
For v2 source wrappers and mapping behavior, see
[the v2 README](../midi_handler_v2/README.md).

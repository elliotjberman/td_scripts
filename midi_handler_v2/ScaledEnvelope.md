# ScaledEnvelope

ScaledEnvelope is an ADSR (attack, decay, sustain, release) envelope with an
adjustable minimum and maximum output value. The envelope is scaled into that
range, which is why it is called ScaledEnvelope. This description of its intended
behavior and use comes from the user.

It is one of the user's main building blocks for animating visuals in
TouchDesigner. They almost always hook it up to MIDI notes: the note triggers
the envelope, and its output animates a visual parameter.

## Controls and usage

- **Naming:** name envelope COMPs in PascalCase as `<Purpose>Envelope`, such as
  `SpeedEnvelope`, `NoiseOffsetEnvelope`, and `ShakeEnvelope`. Use a clear purpose
  rather than numbered names. Keep reference Null CHOP names descriptive and
  update their source references and routing metadata whenever an envelope is
  renamed.
- **Layout:** always arrange envelope rows from top to bottom in debug-key
  order (`1`–`9`, then `0`). Keep each reference Null and its short control chain
  on the corresponding row. When adding or reassigning an envelope, reflow
  the existing block in place: keep all envelope rows together, put
  standalone parameter/control components below them, and leave only small
  gutters between nodes and rows.
- **ADSR:** shapes the animation over time.
- **Output minimum and maximum:** set the range of values sent to the visual
  parameter. Choose the range on the envelope to suit the animation.
- **Debug key:** a configurable number key (`0` through `9`) for manually
  triggering and previewing the envelope without needing incoming MIDI notes.
  This keyboard testing workflow is an important part of authoring animations.
  Every newly created envelope must receive a key that is not already assigned
  to another envelope in the loaded project. Inspect live debug/test parameters
  and stored assignments before choosing the next free key (`1`–`9`, then `0`);
  do not keep the TOX's default key when it is taken. Keep the component's key
  parameter and its `debug_key`/`test_key` storage consistent. If all ten keys
  are occupied, leave the new key unassigned and report that no free key remains
  rather than introducing a duplicate.

The usual flow is:

```text
MIDI note → ScaledEnvelope → reference/output CHOP → visual parameter
                 ↑
         number-key debug trigger
```

For example, use the envelope to drive ScreenShake's `Amount`, adjusting the
envelope's `Outputminimum` and `Outputmaximum` to control the effect's range.
Keep ScreenShake's `Triangleamp` and `Noiseamp` as fixed relative mix controls.

## Files and authoring helpers

- `ScaledEnvelope.tox` in this folder is the component used by the v2 creator.
- `../midi_handler/ScaledEnvelope.tox` is the older workflow's copy. This guide
  describes the shared user workflow; inspect a loaded copy before assuming
  that its implementation matches another copy.
- `manager/envelopes.py` loads the component, creates its named reference Null
  CHOP, adds routing tags, and assigns a debug/test key.
- `manager/hotkeys.py` allocates unused debug keys in the order `1`–`9`, then `0`.
  It returns an empty assignment if all ten keys are already used.

## Details to inspect in TouchDesigner

The intended workflow above is documented from the user's description. Exact
ADSR parameter names, retrigger behavior, MIDI note-off/release behavior, and
velocity response have not been verified in the live component in this task.
Inspect them before making changes that depend on those details. In particular,
the v2 MIDI router's positive-velocity trigger pulse does not by itself establish
held-note sustain or velocity-sensitive output scaling.

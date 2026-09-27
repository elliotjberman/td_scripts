# LiveControls

Song receivers and input conditioning inside `MappedVisual`, alongside `visual`.
The shell keeps only the shared `bitwigMain` connection. Continuous controls
use native CHOP chains and the visual's named CHOP input. MIDI notes still
use MIDIHandler; discrete triggers retain their existing callbacks.

## Current routes

| Source | Conditioning / final CHOP | Public destination |
| --- | --- | --- |
| CTRL / Chain / Perform: Color, `par1/modVal` | Select → Limit → `color_live` Hold | ColorLookup.Palette |
| CTRL / Chain / Perform: Camera, `par2/modVal` | Select → Math × preset count → Limit (floor, 0…count−1) → `camera_live` Hold | CameraMoves.Preset |
| Project Perform: DrumWarp, `par7/modVal` | `drumwarp_live` Hold; `edge_amount` Math inverts | EdgeMix.Rawopacity; EdgeMix.Edgeopacity |
| Project Perform: DrumVerb, `par0/modVal` | `drumverb_live` Hold | NoiseAmplitude.Amount |
| Project Perform: PermFilter, `par6/modVal` | `permfilter_live` Hold | NoiseScale.Amount |
| Project Perform: FastArp, `par2/modVal` | BloomTiming/rippler_value → live_input Hold → to_bloom | BloomTiming.Rippler |
| Perm audio envelope | AudioSlice: Math → Limit → Lag → Logic/Math gate → Hold → to_slice | SliceControl.Amount |
| PermFilter audio envelope | AudioNoise: Math → Limit → Lag → Hold → to_noise | NoiseOffsetEnvelope.Externallevel |
| Drum Machine (Pitch), note 36 | MIDIHandler | ShakeEnvelope.Trigger |
| MC202 post-arpeggiator notes | MIDIHandler | BloomEnvelope.Trigger |
| Master playing Scene Cue changes | Existing scene callback | AutofocusEnvelope.Trigger |
| Global clock, beat 1 of every other bar | SpeedClock | SpeedEnvelope.Trigger |

Project macros share the official receiver at `BloomTiming/rippler_state`.
Both official remote receivers must Read Modulated Values. The unmodulated
`val` channels do not represent all modulation/automation.

The visual still owns its existing ranges and processing: camera poses/spring,
color crossfade, edge fade, noise maps, envelope shapes, and local bloom timing.
NoiseDrift was deliberately removed and has no remaining live route.

## Enable, disconnect, and manual operation

`LiveControls/out1` is wired to `visual`'s CHOP input. Each `send_*` Select
publishes its named channel only while that source is enabled and ready;
`^*` selects no channels for a deliberately inactive source. No zero substitutes
are sent on disconnect. The existing Holds and source calibration remain native.

LiveControls.Active gates continuous song routes. Followremotes also gates
Color, Camera, DrumWarp, DrumVerb, and PermFilter; Followpermfilter is an
additional gate. AudioNoise, AudioSlice, and song BloomTiming retain independent
Enabled controls. Readiness checks connection and expected track/page/slot
identity, with Color and Camera checked independently. MIDIHandler and SpeedClock
have their own event paths.

Inside the visual, `ControlInputs/current` is a native **Bind CHOP**, matched by
channel name with pickup off. Public parameters use short Python bind expressions,
for example `op('ControlInputs/current')['noise_amplitude']`. Local edits and
Next/Toggle actions keep Bind mode intact. A later changed song value takes
control of that channel again. Other channels are unaffected. Repeating an
identical value, including after reconnect, is not a new change; move the control
or let automation change it to reclaim it. No mode switching is required.

NoiseOffsetEnvelope Auto uses the shared `noise_offset` channel, which also
receives its local ADSR. Envelope and Manual remain explicit local options.
BloomTiming's release/mask Holds remain downstream visual behavior controls.

All official receivers reference the wrapper's public **Bridge** parameter via
`parent.MappedVisual.par.Bridge`. MidiHandler.Targetroot and
LiveControls.Targetvisual reference the sibling `visual`. No input mapping in
the reusable visual reaches outward to Bitwig or LiveControls. See
the [channel contract](PerformanceControls.md#continuous-input-contract).

## Runtime implementation

There are no authored CHOP exports, continuous-value callbacks, Script CHOP
slider mapping, or export-restoration callbacks in these routes. Signal math
and state are visible in CHOPs. `control_events` only contains source-identity
checks and public pulse actions; its source is
`live_controls_callbacks.py`, embedded in the live component and not included
in this documentation change.

Avoid expressions that read their own parameter's `.val` as a local branch.
During verification that pattern updated the displayed value while downstream
CHOPs stayed stale. Direct references plus native Holds passed the same sweep.

## Verification — 2026-09-22

Controlled TD source inputs 0, 0.34, 0.67, and 1 reached all four camera poses
and the three palette selections, and propagated through the downstream native
chains. NoiseAmplitude reached 0.3–0.7; current NoiseScale bounds reached
0.4–1.15; edge/raw weights stayed complementary; audio normalization/gating
responded; bloom release switched 1.0/0.08 and its mask followed.

Disabling held the output while the source changed, and re-enabling applied
the new value. Actual Bitwig receiver disconnect/reconnect restored all ready
states and received values. The native transport API started/stopped playback
and the received song clock advanced; both audio meters were zero during that
brief check, so their source movement was not verified. All temporary test inputs were removed. No route
or callback errors remained. The repair removed authored exports and shared
continuous-update callbacks so one failed mapping cannot stop unrelated routes.

The locked macOS session prevented UI knob tests. The official controller
answered a ping, but outgoing remote-value requests did not produce changed
incoming values. The controlled TD sweep is not a verified Bitwig knob sweep. A later actual
received Camera change from 0.78 to 0.62 did propagate through the native chain
to Texture (index 2), with the rendered view changing accordingly.

Saved as `teachers_pet_live_demo.11.toe` in Documents/touchdesigner/2026/raytk1.
Measured 60 fps after restoration. These are historical observations, not
fresh runtime tests performed while publishing this guide.

## Packaging verification — 2026-09-26

Moved all song receivers, MidiHandler, and LiveControls into MappedVisual.
The shell retains bitwigMain, RayTK, Embody, output, and host settings.
Nine input channels passed a controlled TD sweep; local edits, later incoming
changes, and independent channel ownership worked without changing parameter
modes. Palette/camera Next and slice Toggle passed. MIDIHandler routed the
three note sources to their existing envelopes without callback errors.

Loaded the visual under a differently named parent with no input and inherited
640×360 resolution; local controls and render worked. Loaded a renamed mapped
wrapper, rebound its host/Bridge references, and verified its receiver and target
paths. Removed two baked absolute RayTK library paths and embedded the MIDI
table previously linked to a TSV. Bitwig was disconnected during this pass;
this was not a live DAW knob/playback test.

Exports in Documents/touchdesigner/2026/raytk1:
`teachers_pet_visual.tox` and `teachers_pet_mapped.tox`.
Saved project: `teachers_pet_live_demo.16.toe`; pre-change checkpoint: `.15.toe`.

# Performing the visual without a song

All artistic controls live inside the visual. Its parent keeps only inherited
resolution and Home. The mapped wrapper supplies named CHOP values and public trigger events.
The same behavior parameters remain editable for local performance.

| Component | Public controls | Local key |
| --- | --- | --- |
| ColorLookup | Palette 0–1: Black, Warm, Green; Next; Crossfade Seconds | `'` |
| CameraMoves | Preset; Next; FOV Multiplier; Spring section; Top-view backstop enable/Y | `\` |
| EdgeMix | Independent Edge/Raw Opacity; Toggle; fade time, thickness, strength, black level | `;` |
| SliceControl | Amount; Toggle; amount range, thickness endpoints, Lag | `]` |
| NoiseScale | Amount; minimum/maximum multiplier for animated Wombat X/Y; smoothing | — |
| NoiseAmplitude | Amount; output minimum/maximum (0.3–0.7) | — |
| NoiseOffsetEnvelope | Auto / Envelope / Manual input; manual amount; ADSR and output range | `2` |
| BloomTiming | Rippler Active; normal/rippler release; independent release/mask following | — |
| BloomCalibration | Black/Warm/Green base and peak levels for edge/raw; Gain, Ceiling, Preview Peak | — |
| PostProcessing | Focus distance/falloff, blur radius, noise, bloom threshold/fill/radii/preconditioning | — |
| PostProcessing/BloomMask | Enabled; Advance; Reset; start/end/step and rectangle shape | BloomEnvelope trigger |
| Scanner | Enabled, appearance, Progress, timing/opacity/shape controls | `6` |

Envelope rows are in debug-key order: **1 Shake, 2 NoiseOffset, 3 Speed,
4 Bloom, 5 PlaneNoise, 6 Scanner, 7 Autofocus**. Each exposes Trigger,
ADSR/shape, and output range. Trigger them locally without MIDI. Standalone
control COMPs sit below the envelope group, with compact gutters.

## Continuous input contract

`visual/controls_in` is the optional CHOP input. Channels match by name, so a
wrapper may supply only the controls it uses. `ControlInputs` combines saved
starting values, the local noise-offset ADSR, and the external input with one
native Bind CHOP. Public parameters bind to its channels; their internal
processing keeps ordinary short parameter/CHOP references.

| Channel | Units | Owning public parameter |
| --- | --- | --- |
| palette | 0–1: Black, Warm, Green | ColorLookup.Palette |
| camera | Zero-based integer preset index: Side, Angled, Texture, Top | CameraMoves.Preset |
| edge | Opacity 0–1 | EdgeMix.Edgeopacity |
| raw | Opacity 0–1 | EdgeMix.Rawopacity |
| noise_amplitude | Normalized 0–1 | NoiseAmplitude.Amount |
| noise_scale | Normalized 0–1 | NoiseScale.Amount |
| slice | Normalized 0–1 | SliceControl.Amount |
| rippler | 0/1 | BloomTiming.Rippler |
| noise_offset | Normalized 0–1 before the artistic range | NoiseOffsetEnvelope.Externallevel |

The camera adapter converts the song's normalized knob to an integer using the
public preset menu count. Pose data and the shared spring remain in the visual.

## Local and external ownership

Edit the existing public parameter or use its local Next/Toggle action. It stays
in **Bind** mode: there is no Expression/Constant restoration step. The most
recent changed value wins independently for each channel. Moving automation
can immediately override local debugging; an unchanged incoming value cannot.
Inactive source channels are omitted, leaving local controls usable.

The mapped wrapper owns source selection/calibration and event routing. The
visual owns ranges, release pairs, palette ordering, and effect behavior.
NoiseOffsetEnvelope retains explicit Envelope/Manual modes as well as Auto.
The seven local envelope keys remain available without MIDI.

The shell supplies shared services, the mapped wrapper owns song routing, and
the nested visual owns these controls. See [LiveControls](LiveControls.md) for
source routes. Both visual and mapped wrapper
exports live beside the current TOE as `teachers_pet_visual.tox` and
`teachers_pet_mapped.tox`. RayTK is supplied by the shell.

## Verification, 2026-09-21

Verified with Bitwig disconnected in `teachers_pet_live_demo`: public palette
Next/wrap, camera Next, edge Toggle, slice Toggle (0.17 / 0.07), noise amplitude
0.3 / 0.7, rippler releases 0.75 / 0.08, and mask enable/advance/disable.
Restored Black, Angled, full edges, slice 0, and normal timing. The rendered
output was inspected; modified components reported no errors. Project sampled
at approximately 60 fps. Connected Bitwig automation was not exercised during
this pass, and Bitwig was not operated.

The pre-interface project checkpoint is `teachers_pet_live_demo.1.toe`.
The 2026-09-22 routing repair replaced the legacy mapping nodes. A subsequent
cleanup removed the unused slice/palette counters, edge-opacity Constant,
historical bloom table, and empty MIDI callback template. NoiseDrift had already
been removed by the user. The deliberately parked CellBoxes experiment remains.

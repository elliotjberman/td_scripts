# BloomCalibration

Located inside the reusable visual, below its envelope/control block. Owns the
relationship between palette, edge/raw treatment, and bloom envelope. It adds
no renderer and no image-processing pass.

Open the **Black**, **Warm**, and **Green** parameter pages on BloomCalibration
to tune these values:

| Palette | Edge base | Edge peak | Raw base | Raw peak |
| --- | ---: | ---: | ---: | ---: |
| Warm | 0 | 0.18 | 0 | 0.07 |
| Black | 0 | 0.35 | 0 | 0.12 |
| Green | 0 | 0.16 | 0 | 0.06 |

Calibration associates the named public parameters with ColorLookup's physical
ramp order (Warm, Black, Green). Public palette selection starts with Black.
The superseded levels DAT was removed on 2026-09-22. The public parameters
are the source of calibration values.

The envelope row is `BloomEnvelope → bloom_edge_scale (Math) → bloom_amount`.
The Math CHOP multiplies by **0.3 with edges on** and **1 with edges off**. It
uses the existing smoothed EdgeMix edge weight, interpolating the multiplier
during the edge/raw fade. References remain inside the visual.

`bloom_amount` directly supplies the 0–1 blend between the palette's base and
peak. BloomEnvelope's Output Maximum still controls pulse strength: 0.5
produces 0.15 at full edges or 0.5 with edges off. Output Minimum sets the
resting level before the same multiplier. Values outside 0–1 are clamped. Do not normalize this
signal by the envelope's own min/max: that cancels the scaled envelope controls
and was the reason lowering Output Maximum previously had no effect. Calibration
blends using the **actual two ramp slots and crossfade amount** and the
**smoothed EdgeMix edge/raw weights**. Direct Green → Black transitions
therefore do not pass through Warm or jump between calibration values.

`Calibration Gain` scales the result. `Maximum Bloom Intensity`, initially 0.5,
caps it. `Preview Full Bloom` holds the mapping at its peak for tuning without
changing the envelope's ADSR; leave it off for performance. The final channel
feeds PostProcessing.Bloomintensity. Threshold, radius, fill, and resolution
retain their existing settings. Bloom threshold, fill, radii, and preconditioning
are now public on PostProcessing’s Bloom page.

## Native processing

All calculation now lives in native CHOPs inside BloomCalibration:

```text
warm / black / green → current_palette / target_palette → palette_mix
                                                             ↓
                                                   base_levels / peak_levels
                                                             ↓
bloom_amount → envelope_input → pulse_range ──────────→ envelope_mix
                                                             ↓
EdgeMix/opacity_lag → opacity_input → opacity_range ───→ weighted_levels
                                                             ↓
                                                    bloom_gain → bloom_limit → out1
```

Each palette Constant reads its four public base/peak parameters. The two
Switch CHOPs select the image's actual current and target palette slots;
`palette_mix` is a Cross CHOP using the image's crossfade amount. Another
Cross CHOP blends the resulting base/peak levels using the clamped envelope.
Preview Full Bloom raises that clamp's minimum to 1. The two-channel Math
multiplies by the smoothed edge/raw weights; the next Math sums and applies
Gain. The final Limit clamps to 0–Ceiling. `out1['bloom']` and all public
parameters keep their existing names and ranges.

The old `calibration` Python DAT and expression-driven `intensity` Constant
were removed. Parameter expressions only reference values; no Python mixing
function, callbacks, or CHOP exports are involved. No changes to the external
song routes or manual-control behavior are part of this cleanup.

Verified on 2026-09-22 against the previous calculation: base and peak levels,
partial envelope strength, mixed edge/raw weights, palette crossfade midpoints,
Green-to-Black wrapping, preview, gain, and ceiling. Maximum difference across
12 cases was less than 0.00000001 (CHOP float precision). Test inputs and
temporary calibration values were removed/restored before saving.
Preview changes also propagated through PostProcessing without forced cooking;
the restored visual reported no operator or script errors and ran at 60 fps.
Saved in `teachers_pet_live_demo.13.toe`.

## Earlier verification

These are artistic starting values, not automatic exposure. All six peak
values were verified live. Black and Warm edge renders and the Green raw render
were inspected at peak bloom. Output remained valid with no calibration errors.
Real MC202 arpeggiator playback also verified continuous envelope-to-intensity
updates; Black edge bloom stayed capped at 0.35 when retriggers caused a small
envelope overshoot. No force-cook or frame callback is needed.
The component has no runtime disk dependency.

The scaled-envelope fix was verified in `SimpleRayTK.65.toe`: with Green edges,
envelope values 0.05 and 0.5 produced intensities 0.008 and 0.08. Live envelope
output 0.02065 produced intensity 0.003304. MC202 remains routed to
BloomEnvelope, with the existing 0.75/0.08-second release selection.

The edge attenuation was added in `SimpleRayTK.67.toe`. With full edges, a
live envelope value of 0.388662 produced 0.116599 after the Math CHOP (×0.3).

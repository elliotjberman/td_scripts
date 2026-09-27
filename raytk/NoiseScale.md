# NoiseScale

`visual/NoiseScale` maps one normalized performance input to a shared multiplier
for **wombat_noise.Scale1 (X)** and **Scale2 (Y)**. Existing `noise_scale_x` and
`noise_scale_y` LFO animation stays intact. Z stays at its existing setting.

| Public parameter | Starting value | Meaning |
| --- | ---: | --- |
| Amount | 1 locally | Input 0–1, editable without a song. |
| Minimum Scale Multiplier | 0.75 | Multiplier when Amount is 0. |
| Maximum Scale Multiplier | 1 | Multiplier when Amount is 1. |
| Smoothing Seconds | 0.1 | Shared rising/falling Lag time. Set 0 for immediate response. |
| Current Scale Multiplier | Read-only | Actual smoothed output. |

```text
Amount → amount (Parameter) → scale_range (Math) → smooth (Lag) → out1
                                                                  │
noise_scale_x (existing LFO) ───────────────────────────────────── × → Wombat X
noise_scale_y (existing LFO) ───────────────────────────────────── × → Wombat Y
```

The mapped target is `minimum + Amount * (maximum - minimum)`.
Amount 0 / 0.5 / 1 produces multiplier **0.75 / 0.875 / 1**. At zero, both
animated scales are 25% lower; at full, their original animated values pass
through. Bounds stay positive to avoid singular noise scales. The visual owns
these limits and smoothing. No envelope, debug key, or parent parameter is added.

## External input

`LiveControls/permfilter_value` selects effective **Project Perform → PermFilter**,
slot **7**, zero-based channel **par6/modVal**, from the existing
`BloomTiming/rippler_state` receiver. This is the project macro, independent of
the PermFilter track's audio-meter mapping to NoiseOffsetEnvelope.

`permfilter_live` is a native Hold gated by Active, Followremotes,
Followpermfilter, and source readiness. The wrapper publishes its ready
`noise_scale` channel to the visual's CHOP input. NoiseScale.Amount binds to
ControlInputs, so local edits and incoming changes share one value without
mode switching or an update callback.

Current live tuning is Minimum 0.4, Maximum 1.15, and Lag 0.021 seconds.
The 2026-09-22 input sweep verified these endpoints and intermediate values
through the actual output. NoiseDrift was removed by the user; this knob has
no remaining drift route. See [LiveControls](LiveControls.md).

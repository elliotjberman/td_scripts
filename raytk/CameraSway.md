# CameraSway

Continuous, subtle X/Y camera rotation inside the visual. This local variant of
[ScreenShake](../utils/ScreenShake.md) mixes slow sine waves with smooth noise.
It runs on its own, alongside the existing envelope-driven shake.

Each [CameraMoves](CameraMoves.md) preset has a `sway_percent` table column:
Angled (the diagonal view) starts at 100; Side, Texture, and Top start at 0. Set 50 for
half strength or 100 for the full Amount configured here. The percentage passes
through CameraMoves' shared Spring CHOP and scales this component's contribution
at the camera, allowing smooth fades between views without changing the global
Amount or affecting reactive screen shake.

| Control | Starting value | Meaning |
| --- | --- | --- |
| `Amount` | 0.25° | Overall motion scale, with a slider and hard maximum of 5°. Set to zero to disable sway. |
| `Lfoamp` — LFO Amount | 0.6 | Relative contribution of the sine waves. |
| `Noiseamp` — Noise Amount | 0.4 | Relative contribution of smooth noise. |
| `Cadence` — Cadence (seconds) | 12 | X cycle and noise period. Higher values move more slowly. |

The Y cycle lasts 1.25 times the cadence: 15 seconds at the starting setting,
with a quarter-cycle phase offset. Different cycles and separate noise channels
keep the two axes from following the same motion. LFO and noise amounts add;
they are independent weights, not a normalized crossfade. Amount is an overall
scale, not a hard angular limit.

Both sources use the same amplitude convention: their normalized signal stays
within -1 to +1, multiplied by its source Amount and then the master Amount in
degrees. For example, master Amount 2 and either source Amount 0.5 bounds that
source's contribution to ±1°. Hermite noise generally occupies less of its
permitted range than a sine wave; equal bounds do not imply equal measured peaks
or RMS strength. Preserve this mathematical scaling without empirical gain
compensation or automatic normalization. The two contributions still add.

The component reuses ScreenShake's five-CHOP structure: two LFOs, two-channel
Hermite noise, a Math CHOP that combines and scales them, and `out1`. Noise uses
a single sample with Time Slice off and Translate X set to
`absTime.seconds * me.par.rate`; translation is in sample units, while Period
remains linked to Cadence in seconds. This explicitly advances through noise
space without restarting when the project timeline loops. The sibling
Null `camera_sway` supplies channels `x` and `y`. The camera's X/Y rotation
expressions multiply these by `CameraMoves/pose['sway_scale']`, then add the
matching `camera_shake` channels. The motion itself bypasses the camera-preset
Spring CHOP. The existing local rotation after look-at keeps the
motion relative to the screen axes. The camera clamps the spring's sway scale to
0–1 to keep overshoot from reversing or exaggerating sway. Setting sway Amount to zero leaves reactive
shake active.

Keep CameraSway below the complete envelope group with the other local controls.
Its controls and processing stay inside the visual's export boundary, using
relative references. It adds no render pass or visual-parent parameters.

Verified live on 2026-09-19: both channels varied over time, the camera matched
the sum of sway and shake, zero Amount disabled only sway, and doubling cadence
halved both LFO frequencies while doubling the noise period. The visual reported
no errors and maintained 60 fps before and after the addition. A follow-up found
that the copied noise's time-sliced output stayed constant despite cooking;
the original motion check had only established that the combined output moved.
Explicit noise translation fixes that: verify the noise branch separately from
the LFOs when checking continuous motion.

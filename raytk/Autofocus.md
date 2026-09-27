# Autofocus

Envelope-driven focus hunting with a small correlated zoom, like a lens
recalibrating. `AutofocusEnvelope` is a copy of the visual's working
ScaledEnvelope. Its debug key is **7**, checked against the loaded project's
other envelopes (keys 1–6) when created. `Testkey`, `debug_key`, and `test_key`
all agree. It retains the `scaled-envelope` and `midi-route-target` tags.

```text
AutofocusEnvelope → autofocus_amount → Autofocus (Amount)
                                          ├─ focus_offset → PostProcessing.Focusdistance
                                          └─ zoom → camera.Camfov

Inside Autofocus:
noise → noise_lag ··· signals → out1
```

The dotted link is a relative CHOP expression reference. Runtime processing
uses four CHOPs; there are no frame callbacks or agent calls.

## Controls

Set overall strength and timing on **AutofocusEnvelope**:

- Output Minimum **0**, Maximum **2** initially. This scales bipolar noise,
  so the focus offset can move in both directions, approximately ±2 scene
  units before smoothing. These are strength limits, not fixed endpoints of
  the focus plane. Keep Minimum at zero for an unchanged resting view.
- Attack **0.12 s**, Release **1.6 s** initially; Decay 0, Sustain 1.
- Debug key **7** or the envelope's Trigger pulse starts the effect. Existing
  ScaledEnvelope event routing can target it. The current wrapper supplies
  Master Scene Cue changes; see [LiveControls](LiveControls.md).

The **Autofocus** component exposes:

| Control | Initial | Effect |
| --- | --- | --- |
| Amount | Envelope output | Overall focus offset strength; normally leave its expression connected. |
| Noise Speed | 2.5 Hz | Higher values make focus search faster; internally sets Noise Period to `1 / speed`. |
| Roughness | 0.35 | Higher values emphasize fast, irregular details. |
| Harmonics | 2 | Number of additional faster noise layers. |
| Smoothing | 0.06 s | Lag before envelope scaling; larger values soften the motion. |
| Seed | 17 | Changes the noise pattern. |
| Zoom Amount | 0.02 | Fractional zoom per scene unit of focus offset. Zero disables zoom. |

For a more frantic look, raise Noise Speed and Roughness or reduce Smoothing.
For stronger focus travel, raise the envelope Maximum. Zoom Amount of 0.02
means a +2-unit focus offset produces a zoom factor of 1.04 (about 4% zoom in).

## Mapping and behavior

Sparse Noise is time sliced at the visual's frame rate. Its phase runs
continuously; the envelope reveals a burst of motion instead of restarting
the same noise sequence on each trigger. Noise is smoothed before scaling so
an envelope output of zero gives exactly zero offset and unity zoom.

```text
focus_offset = smoothed_noise * envelope
zoom = max(0.1, 1 + focus_offset * zoom_amount)
focus_plane = existing_camera_relative_focus_plane + focus_offset
tan(new_FOV / 2) = tan(existing_FOV / 2) / zoom
```

Only lens FOV receives this zoom factor. Camera position and the existing
framing-preserving FOV Multiplier retain their behavior. This lets autofocus
produce visible lens breathing without camera-distance compensation cancelling
it. Focus falloff and maximum blur radius remain unchanged.

`PostProcessing/focus_mask` now blurs on both sides of the focus plane. This
same `focus_offset` signal moves the sharp plane through the scene: foreground
can go out of focus while farther surfaces sharpen, and vice versa. The mask
uses the live, breathing-adjusted camera FOV to convert ray distance to planar
camera depth. No new autofocus envelope, noise source, or timing stage is needed.

All references are relative inside the visual export boundary. Reusing
Autofocus alone requires supplying its Amount source and wiring its two output
channels to the receiving focus and camera controls. The original focus and
FOV expressions are retained as string metadata on Autofocus for reference.

The envelope group is ordered 1–7, with short chains on the same rows and
standalone controls below it. Autofocus follows its envelope's reference Null.

## Verification and exports

At rest, the new wiring matched original focus, FOV, and rendered pixels
exactly. A Trigger pulse produced positive and negative focus offsets with
correlated FOV changes, then returned to zero offset and unity zoom by the
120-frame sample. The active rendered frame was inspected, and the four-CHOP
motion component reported about 0.036 ms child CPU cook time in one sample.
These measurements are snapshots, not a guaranteed frame rate.

The current components are embedded at `/project1/MappedVisual/visual` in the
Teachers Pet project. Export the live visual or components when needed; older
standalone snapshots are not included in this documentation change.

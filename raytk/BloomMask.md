# BloomMask

`visual/PostProcessing/BloomMask` owns the stepping rectangle that masks bloom.
It takes one TOP input (the bloomed image) and returns that image through the
rectangle mask. The existing Over composite places it over the original image.

## Public controls and API

```python
mask.par.Enabled = True      # use the rectangle mask
mask.par.Advance.pulse()     # move to the next band position
mask.par.Reset.pulse()       # arm the next advance at the top
mask.par.Enabled = False     # unmasked, full-frame input image
```

- **Start Y / End Y / Step Size:** `0.4 / -0.4 / 0.1` by default.
- **Current Y:** read-only position feedback.
- **Shape → Width / Height / Edge Softness:** the existing rectangle settings,
  initially `1.2 / 0.25 / 0.1`.

The first Advance after reset or enable uses **0.4**, followed by **0.3, 0.2,
0.1, 0, −0.1, −0.2, −0.3, −0.4**, then snaps to **0.4**. Integer step indexing
avoids accumulated floating-point drift. Advance is ignored while disabled.
Enabling/disabling resets the sequence; the next active note starts at the top.

Disabled mode bypasses the Rectangle TOP itself. There is no Switch TOP,
extra render, or larger replacement rectangle. The TOP input passes through
unchanged, preserving normal bloom outside rippler sections. Resolution follows
the input image. Parameter callbacks run only on changes/pulses, without a
frame polling DAT or runtime disk dependency.

## This visual's routing

`PostProcessing/bloom_mask_events` watches the rising edge of
`BloomEnvelope/trigger_out` and pulses Advance. This is the envelope's raw
trigger output, before ADSR shaping, output scaling, and bloom calibration.
It therefore includes MIDI and debug key **4**, and doesn't wait for the
envelope tail to reach zero before the next step. No new envelope/key is used.

The visual's BloomTiming.Rippler drives Enabled through its native `mask_live`
Hold and a short parameter reference. LiveControls/BloomTiming supplies the
normalized `rippler` input; missing input leaves the visual's current value
available for local edits. Turn off BloomTiming's
Apply Rippler to Bloom Mask to operate Enabled independently.

For another visual, route triggers to Advance and on/off state to Enabled.
BloomMask contains no Bitwig, MIDI-track, visual-parent, or envelope paths.
The current envelope hook and local timing relationship live beside it inside
the visual; source discovery and DAW receivers remain outside.

Implementation: `bloom_mask.py` and `bloom_mask_trigger.py`, embedded in their
callback DATs. Those source files are not included in this documentation change.

## Verification — 2026-09-21

With rippler off, the component's output matched its full-frame bloom input
pixel for pixel (maximum difference 0), at the inherited 1920×1080 resolution.
Real rippler playback enabled the mask and advanced its position; Elliot
confirmed the visual result. The isolated public-API check exercised the
stepping controls without substituting any live input. The temporary copy was
removed afterward. PostProcessing reported no errors or warnings.

## Public interface update — 2026-09-21

The visual’s BloomTiming owns the local Rippler-to-Enabled relationship.
The external song adapter targets BloomTiming.Rippler. Disable BloomTiming’s
Apply Rippler to Bloom Mask to adjust Enabled independently. State/position
helpers now live in a Text DAT, `mask_logic`; the Parameter Execute DAT only
forwards events. This avoids a dependency loop from Centery evaluating the
same Execute DAT that watches Enabled. Enable changes defer bypass updates
one frame; Advance still synchronizes immediately, preserving enable-and-step
in the same event.

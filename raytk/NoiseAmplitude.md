# NoiseAmplitude

`visual/NoiseAmplitude` owns the range mapping for `wombat_noise.Amplitude`.
It lives below the existing envelope/control group, with no new envelope or
debug key and no parameters added to the visual parent.

| Control | Purpose |
| --- | --- |
| Amount | Normalized 0–1 input; local default 0. |
| Output Minimum | Amplitude at Amount 0; default **0.3**. |
| Output Maximum | Amplitude at Amount 1; default **0.7**. |
| Current Amplitude | Read-only mapped output. |

```text
Amount → amount (Parameter CHOP) → scale_range (Math) → out1['amplitude']
                                                        ↓
                                            wombat_noise.Amplitude
```

The mapping is linear: `minimum + Amount × (maximum − minimum)`, so Amount
0 / 0.5 / 1 gives amplitude **0.3 / 0.5 / 0.7**. Native wired CHOPs keep changes
reactive without Python callbacks, frame polling, or extra smoothing.

Outside the visual, `LiveControls/drumverb_value` reads **Project Perform →
DrumVerb**, the first remote (`par0/modVal`), through the existing project
receiver. `drumverb_live` holds the last value while disabled/disconnected;
the ready `noise_amplitude` channel crosses the visual CHOP input and binds to
NoiseAmplitude.Amount through ControlInputs. The existing visual
Math owns the 0.3–0.7 range. No continuous Python callback or export is used.

See [LiveControls](LiveControls.md#enable-disconnect-and-manual-operation) for
source enables and local/incoming last-change-wins control.

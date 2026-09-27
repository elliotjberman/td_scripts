# AudioSlice

External song input conditioner at `LiveControls/AudioSlice`. An official
bitwigTrack receiver pinned to **Perm** reads the track's audio envelope,
a normalized RMS meter rather than dB or a full-rate waveform.

```text
source_audio → source_level → level_range → limit_range → smooth_level
                                                            ↓
                                                       output_gate
                                                            ↓
                                                        to_slice
                                                            ↓
                                               SliceControl:Amount
```

Public input controls are Enabled, Input Low/High (0 / 0.6), Rise/Fall Time
(both 0), Output Gate Threshold (0.3), the required track, receiver, and source
status. Read-only meters show input and conditioned output. Values below the
gate become zero; values at or above it pass unchanged. The gate is in normalized
output units: with input 0–0.6, meter 0.18 reaches the 0.3 boundary.

The Math maps input levels to 0–1, Limit clamps, and Lag conditions the source.
The visual's **SliceControl** owns artistic amount limits, thickness endpoints,
and any effect smoothing. The retained song-side minimum/maximum displays
are read-only mirrors, not a second mapping. `LiveControls.Slice` is also only
a display. The wrapper publishes `slice` through the visual's CHOP input;
SliceControl.Amount binds to that channel through ControlInputs.

`gate_open` is a Logic CHOP; `output_gate` is a Math CHOP multiplying the
level by that gate. `live_input` holds while Active, Enabled, or Ready is off.
The route uses no exports or continuous-update callbacks. The 2026-09-22
controlled TD sweep verified normalization, the gate, and enable/hold/resume.
See [LiveControls](LiveControls.md) for verification limits and manual modes.

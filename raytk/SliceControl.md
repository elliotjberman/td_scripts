# SliceControl

Owns slice thickness inside the visual. Its Amount is a local, editable public
parameter, shared by the Toggle pulse, `]` key, and optional external input.

| Parameter | Purpose |
| --- | --- |
| Amount | Normalized performance input, normally 0–1. |
| Toggle | Toggle Amount between 0 and 1; also used by `]`. |
| Lag | Existing smoothing time; currently 0 seconds. |
| Minimum / Maximum Amount | Artistic mapping of input 0/1; currently 0/1. |
| Thickness at Amount 0 / 1 | Geometry endpoints; currently 0.17 / 0.07. |

```text
Amount → constant_amount → math_thickness → lag_thickness → out1
```

The Math applies both ranges in one operation:
`mapped = minimum + (maximum - minimum) * Amount`, then
`thickness = thickness_at_0 + (thickness_at_1 - thickness_at_0) * mapped`.
No extra processing chain is needed. Reversed ranges are supported. The
`thickness` output drives the visual's `quadSdf1.Thickness`.

The keyboard calls the public Toggle pulse once per unmodified press. Amount
owns selection; the obsolete private Count was removed on 2026-09-22.
Internal processing references this public parameter.

External `LiveControls/AudioSlice` calibrates the Perm audio meter to 0–1,
applies source smoothing and a gate. Its ready `slice` channel enters the
visual CHOP input. **SliceControl:Amount** binds through ControlInputs; local
edits and Toggle keep the binding, and later input changes reclaim control. The song layer does not own
artistic slice limits. The earlier RePerm and intermediate LiveControls.Slice
routes are obsolete; the latter is only a read-only display now.

Verified public Toggle → Amount 1 → thickness 0.07, and local Amount 0 →
0.17, with no errors on 2026-09-21. The local `SliceControl.tox` snapshot
predates the unused-counter cleanup and is not included here; export the live
component when reusing it. See
[AudioSlice](AudioSlice.md) for input calibration.

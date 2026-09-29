# ControlMap

[ControlMap.tox](ControlMap.tox) maps continuous CHOP values with a visible native
chain:

```text
In → Math (normalize) → Limit (0–1) → Math (scale) → Lag → Select → Out
```

It preserves input channel names and applies the same range to every channel.
Use separate instances when signals need different ranges. There are no runtime
Python callbacks, Script CHOPs, or CHOP exports.

## Public controls

- **Inputmin / Inputmax**: measured source bounds; they must differ.
- **Outputmin / Outputmax**: destination bounds. Reverse them to invert a knob.
- **Lagup / Lagdown**: independent rise/fall times in seconds, both initially zero.
- **Enabled**: when off, output has **no channels**. It does not send zero as a
  competing control value.

For a normalized remote knob, leave input bounds at 0 and 1. For an audio meter,
watch the actual channel and set bounds around the useful quiet/loud values.
The component maps a control-rate audio envelope; it does not analyze an audio
waveform. Receiver/envelope smoothing before this component remains upstream,
even when both local lag controls are zero.

Place artistic output ranges in the visual, on the behavior that owns them.
The mapped wrapper selects, names, and validates the song's incoming signals.
Use receiver connection and source identity to drive **Enabled** there; do not
replace a missing external input with zero. Follow
[Visual Structure](../VISUAL_STRUCTURE.md) for named CHOP inputs and native Bind
CHOPs, which let local debug controls and external signals share one value.

## Maintenance and verification

[build_control_components.py](build_control_components.py) constructs the native
network. The TOX has no file-sync dependencies. Verified in TD 2025.33070 at low,
mid, high and out-of-range inputs, reversed output bounds, zero lag, disabled
channel omission, and after reload into a renamed container.

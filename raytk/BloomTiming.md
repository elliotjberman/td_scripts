# BloomTiming

The **visual's BloomTiming** owns the two bloom release lengths and the local
Rippler state. The separate `LiveControls/BloomTiming` only receives Bitwig
state and routes it to this public interface.

| Visual parameter | Current value / behavior |
| --- | --- |
| Apply Release Timing | Enables the native release Hold. Disabled holds its last value; use Constant mode on BloomEnvelope.Release for manual tuning. |
| Rippler Active | Editable local toggle, or normalized external 0/1 state. |
| Normal Release Seconds | 1.0 |
| Rippler Release Seconds | 0.08 |
| Apply Rippler to Bloom Mask | When enabled, Rippler also drives BloomMask.Enabled. Disable to operate that mask independently. |

```text
Rippler → Parameter CHOP → release_time Math → BloomEnvelope.Release
                        └→ to_mask Select  → PostProcessing/BloomMask.Enabled
```

The local native chains include release_live and mask_live Hold CHOPs.
BloomEnvelope.Release and BloomMask.Enabled directly reference their outputs.
No continuous-update callbacks or CHOP exports are used. BloomEnvelope retains its
public output range, ADSR/shape, Trigger, and debug key **4**. Its raw trigger
locally advances BloomMask; timing state only enables the mask.

## External song adapter

The existing official `bitwigRemotesProject` receiver remains at
`LiveControls/BloomTiming/rippler_state`; other project macro routes reuse it.
It reads **Project Perform → FastArp**, slot 3 (`par2/modVal`). Read Modulated
Values must stay on: `par2/val` can remain zero while automation enables Fast.

`rippler_value → live_input Hold → to_bloom` supplies the visual's public
BloomTiming.Rippler through the visual's named `rippler` CHOP input and native
Bind CHOP. Active, Enabled, and Ready gate the source. Inactive routes omit the
channel; local edits remain usable. A later changed input reclaims control. Source-name/page checks remain explicit. Obsolete song-side
release and mask nodes and all export-switch callbacks were removed. See
[LiveControls](LiveControls.md#enable-disconnect-and-manual-operation) for modes.

MC202 notes still trigger BloomEnvelope through the MIDI mapping outside the
visual. Local Rippler on/off verified 0.08/0.75 seconds and mask enable/disable on
2026-09-21. See [BloomMask](BloomMask.md) and
[PerformanceControls](PerformanceControls.md).

Later on 2026-09-21, Normal Release was increased from 0.75 to 1.0 second
for the longer MC202 notes. Rippler Release remains 0.08 seconds.

# CHOP export inventory — 2026-09-22

Inspected live through the existing Embody/Envoy API in:
`/Users/elliot/Documents/touchdesigner/2026/raytk1/teachers_pet_live_demo.10.toe`.

This is a historical incident record, not a layout or routing recipe. Current
interfaces are documented in [LiveControls](LiveControls.md).

This section records the initial inventory, before the repair below. No routing, parameter values, callbacks,
or export flags were edited, and the project was not saved. Bitwig was closed;
TD's `bitwigMain/out1/connected` was 0. Disconnected exports being off during
this audit is expected and does not reproduce the reported live-demo failure.

The user reported that camera/color stopped following incoming Bitwig values,
while `BloomTiming/to_envelope` worked. Do not describe all exports as failed.

## Scope and totals

Read CHOP export flags/configuration throughout `/project1` and all other
user networks at `/`. Excluded TD's `/ui`, `/sys`, and `/local` infrastructure.
The scan covered 12,176 CHOPs, using export metadata rather than evaluating
every parameter in the RayTK network. Read configured export tables, channel
destinations, relevant public parameter modes, and the live mapping callbacks.

- **8 performance-routing export operators**, with 10 intended destinations.
- **3 disabled legacy export configurations** on still-present operators.
- **14 bundled utility export operators:** 9 in RayTK tools and 5 in TDBitwig.
- **25 configured export operators total; 16 green flags were on.** Those 16
  were the two local bloom exports and the 14 utility operators. A green flag
  alone does not establish a working route: the five TDBitwig utility sources
  had no channels while disconnected.
- No configured exports were found outside `/project1`, and no configured
  export-table paths failed to resolve.

Below, `LC` means `/project1/LiveControls` and `V` means
`/project1/visuals_container/visual`.

## Performance routes

All eight use channel names as export destinations (`autoname`).

| Export CHOP | Input / purpose | Intended parameter destination | Flag during audit / enable condition |
| --- | --- | --- | --- |
| `LC/to_controls` | `ctrl_device/out1` → `remote_values`; device remotes `par1/modVal` Color and `par2/modVal` Camera | `LC.Color`, `LC.Camera` | Off. Requires `Active`, `Followremotes`, `Remotesready`. |
| `LC/to_visual` | `slider_parameters` → `slider_values` Script CHOP → `palette_camera` | `V/ColorLookup.Palette`, `V/CameraMoves.Preset` | Off. Same readiness gate as `to_controls`. |
| `LC/drumverb_value` | Project remote `par0/modVal`, DrumVerb | `V/NoiseAmplitude.Amount` | Off. Requires `Active`, `Followremotes`, `Drumverbready`. |
| `LC/AudioNoise/to_noise` | PermFilter `track/audioEnvelope` → Math → Limit → Lag | `V/NoiseOffsetEnvelope.Externallevel` | Off. Requires this component's `Enabled` and `Ready`; its callback does not also check `LC.Active`. |
| `LC/AudioSlice/to_slice` | Perm `track/audioEnvelope` → Math → Limit → Lag → output gate | `V/SliceControl.Amount` | Off. Requires `LC.Active`, this component's `Enabled` and `Ready`. |
| `LC/BloomTiming/to_bloom` | Project remote `par2/modVal`, FastArp → `rippler_value` | `V/BloomTiming.Rippler` | Off. Requires this component's `Enabled` and `Ready`. |
| `V/BloomTiming/to_envelope` | Local `Rippler` Parameter CHOP → `release_time` Math | `V/BloomEnvelope.Release` | **On, bound in EXPORT mode, value 1.0.** Controlled by local `Enabled`. User reported this worked. |
| `V/BloomTiming/to_mask` | Local `Rippler` Parameter CHOP → Select | `V/PostProcessing/BloomMask.Enabled` | **On, bound in EXPORT mode, value 0.** Controlled by local `Maskfollow`. |

`LC/AudioNoise` still expects the **PermFilter** track. `LC/AudioSlice` expects
**Perm**. These are different source routes, not two names for one route.

## Camera and color: two export boundaries

```text
ctrl_device/out1  [Color / Camera effective remote values]
  → remote_values
  → to_controls                 GREEN EXPORT #1
  → LiveControls.Color / Camera
  → slider_parameters           Parameter CHOP
  → slider_values               Script CHOP: clamp / camera quantization
  → palette_camera              Select CHOP
  → to_visual                   GREEN EXPORT #2
  → ColorLookup.Palette / CameraMoves.Preset
```

The readiness check requires a connected receiver for track `CTRL`, device
`Chain`, page suffix `Perform`, and matching slot names `Color` and `Camera`.

`LC/visual_control_events` listens to the intermediate `slider_parameters`
channels. It calls `restore_export()` to put the final public parameter back
in EXPORT mode; it does **not** assign the changed value. `restore_export()`
only acts if an export source already exists, is enabled, and is `to_visual`.
It neither supplies the value nor repairs a missing first-stage route. If the
first export stops updating the sliders, this downstream listener may not see
the source movement at all.

At inspection, `LC.Color`, `LC.Camera`, `ColorLookup.Palette`, and
`CameraMoves.Preset` were all in CONSTANT mode. The two source CHOPs had their
flags off because Bitwig was disconnected. This snapshot cannot establish
which boundary failed during the demo.

The local bloom route is shorter and independent of these readiness callbacks:
its Parameter CHOP and Math CHOP feed one export, enabled by the visual's own
toggle. Its current source/destination agree. That is a verified structural
difference, not proof of why one export worked and another failed.

## Disabled leftovers

| Operator | Configured destination | Current role |
| --- | --- | --- |
| `LC/drumwarp_value` | `LC.Edgeon` | Export off. Still supplies the DrumWarp signal to the Math CHOP. |
| `LC/edge_amount` | `LC.Edgeon` | Export off, explicitly enforced by `control_events`. Its processed signal now drives `EdgeMix` through a Python callback. |
| `LC/BloomTiming/mask_enable` | `V/PostProcessing/BloomMask.Enabled` | Export off. Superseded by the visual's `BloomTiming/to_mask`. |

`LC/BloomTiming/release_time` is another leftover Math CHOP with no downstream
wired consumers, but is **not** an additional configured export.
`LC/to_edges` is absent. The Script CHOP still produces old edge opacity
channels, but `palette_camera` excludes them from `to_visual`.

## Bundled utility exports

These are separate from the authored performance mappings. They remain part of
the complete inventory; none were changed or identified as demo failures.
Paths below are relative to `/project1`.

| Export CHOP | Configured destinations (relative to its containing network) |
| --- | --- |
| `raytk/tools/inspector/bufferInspector/checker/null1` | `transform4.sx`, `transform4.sy` |
| `raytk/tools/inspector/selectedOp_dropmenu/menu/selectedCell` | `selectedRowSelect.rowindexstart`, `.rowindexend` |
| `raytk/tools/inspector/selectedOp_dropmenu/dropmenu0/popMenu/selectedCell` | `selectedRowSelect.rowindexstart`, `.rowindexend` |
| `raytk/tools/inspector/camera_type_dropmenu/menu/selectedCell` | `selectedRowSelect.rowindexstart`, `.rowindexend` |
| `raytk/tools/inspector/camera_type_dropmenu/dropmenu0/popMenu/selectedCell` | `selectedRowSelect.rowindexstart`, `.rowindexend` |
| `raytk/tools/editorTools/exposeParamDialog/pageDropDownField/menu/selectedCell` | `selectedRowSelect.rowindexstart`, `.rowindexend` |
| `raytk/tools/editorTools/exposeParamDialog/pageDropDownField/stringMenu0/popMenu/selectedCell` | `selectedRowSelect.rowindexstart`, `.rowindexend` |
| `raytk/tools/editorTools/exposeParamDialog/structureDropDownMenu/menu/selectedCell` | `selectedRowSelect.rowindexstart`, `.rowindexend` |
| `raytk/tools/editorTools/exposeParamDialog/structureDropDownMenu/dropmenu0/popMenu/selectedCell` | `selectedRowSelect.rowindexstart`, `.rowindexend` |
| `LiveControls/SpeedClock/song/calcBeat/timeSigInfo` | `quarterNoteRatio.gain`, `math3.gain`, `div_numerator1.gain`, `dev_denom1.gain` |
| `LiveControls/SpeedClock/song/beatFormat/lengths` | `barRamp.length`, `beatRamp.length` |
| `LiveControls/SpeedClock/song/beatFormat/selectPlayState` | `barRamp.play`, `beatRamp.play` |
| `LiveControls/SpeedClock/song/beatFormat/selectTransport` | `math2.gain` |
| `scene_events/formatClipSlotStatus/clipIndex` | `selectPlaying.rowindexstart`, `.rowindexend`; `selectQueued.rowindexstart`, `.rowindexend` |

The checker uses a `datname` export table; the other 13 use `datindex` tables.
The checker table also contains ten **disabled rows** for `transform4`
resolution width/height, `color1` RGB/alpha, and `color2` RGB/alpha.

## Risks and migration dependencies

1. **Missing target can interrupt the shared routing callback.** In this
   revision `V/NoiseDrift` is absent, but `LC/control_events.apply_permfilter()`
   still assigns its `Amount`. When PermFilter is ready, that access will
   fail. `onValueChange()` calls it before updating `AudioSlice/to_slice`,
   `to_controls`, and `drumverb_value` export flags and before restoring the
   visual exports. This can interrupt reconnection setup for unrelated routes.
   Local bloom uses a separate callback. This is a concrete broken reference;
   attributing the demo's camera/color failure to it remains an inference.
   The callback was not triggered for this audit.
2. **Noise input selection depends on parameter mode.**
   `NoiseOffsetEnvelope/input_select` in Auto mode chooses external input only
   when `Externallevel` is in EXPRESSION/BIND mode or has a live EXPORT source.
   Direct Python assignment makes it CONSTANT, so replacing the export alone
   would leave the envelope using its other input. Migration needs an explicit
   public external-input selection, with documented disconnect behavior.
3. **Some signal processing is hidden in Python.** `LC/slider_values` clamps
   color/camera/edge, quantizes the four camera presets, and calculates an edge
   complement in a Script CHOP. `apply_permfilter()` also clamps in Python,
   and `apply_edge_amount()` computes the complementary opacity there. Native
   Math/Limit/Select operations should own this processing; short parameter
   references should connect continuous values. Reserve callbacks for events.
4. **Some missing-route states are silently skipped.**
   `restore_visual_exports()`, `onPulse()`, and `visual_control_events` quietly
   return/skip when `Targetvisual` is missing. Audio readiness/display
   expressions also turn some missing-source/channel cases into false/zero.
   A deliberate disconnect must be distinguishable from invalid configuration.
5. **Gate behavior differs between routes.** AudioNoise and external BloomTiming
   only gate on their own Enabled/Ready; they do not include `LC.Active` in their
   export-state callbacks. Preserve or explicitly clarify enable semantics
   during migration rather than assuming one global switch currently controls
   every route.

No stored errors or warnings were reported by the inspected live-control,
audio, bloom, or clock networks while disconnected. No Bitwig controls were
operated, no input sweep was performed, and no fixes were applied in this pass.

Future changes follow [the routing rules](../TOUCHDESIGNER_DEV_NOTES.md#control-routing-defaults):
native CHOPs for signal processing, explicit Python for parameter routing, no
new green-flag exports, no eval-based mappings or hidden failures, and live
verification of source → public destination → visible behavior.


## Repair outcome — 2026-09-22

With Bitwig connected, `control_events.scriptErrors()` reproduced the missing
NoiseDrift exception. It interrupted export enable updates: camera/color input
and DrumVerb exports stayed off while the upstream native receiver values were
present. Ordinary component errors did not reveal this callback exception.

The authored export routes and dormant export configurations were removed.
Continuous routes now use native CHOP processing and direct parameter references;
Hold CHOPs implement enable/disconnect state. The Script CHOP slider mapper,
shared update callback, and export-restoration callbacks were removed.
Local bloom/mask exports were replaced too. Bundled RayTK/TDBitwig utility
internals were preserved. See [LiveControls](LiveControls.md) for the actual
verification scope and manual-mode behavior.

## Later packaging — 2026-09-26

The native processing remains. Continuous values now cross the reusable visual
boundary as named CHOP inputs, with a native Bind CHOP sharing public controls
between local edits and later changed inputs. No Expression/Constant mode
switch is required. Song nodes moved into MappedVisual; the paths above describe
the earlier audited revision, not the current project layout. See
[Visual Structure](../VISUAL_STRUCTURE.md) for the current boundary.

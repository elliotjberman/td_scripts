# TouchDesigner Development Notes

These are durable notes for future work on this repo.

## Runtime Safety

- Do not auto-start bridge polling or network calls from TouchDesigner's main thread on project load.
- Keep bridge/server integration explicit. Start it only from a user action, and keep HTTP timeouts short.
- Execute DATs should be active only when supporting required UI or performance behavior. Continuous control routing should use parameter references; callbacks are for events, not per-frame polling.
- If TD freezes after adding a manager/component, first suspect an always-on Execute DAT or blocking Python call.
- Use Embody/Envoy for live agent inspection and authoring. Do not install or recreate the removed CodexDebugger file-backed execution bridge when that connection is unavailable.
- Keep agent execution out of live-performance workflow components and the Ableton hookup manager.
- Do not blindly trust a project's `Home` parameter for tooling. Old `.toe` files can carry another machine/user path; verify the current project's paths before use.
- Scope live reference audits to the component being changed and its known
  consumers. Avoid project-wide parameter-value scans through RayTK and agent
  internals; a broad `findChildren(parValue=...)` audit froze this project. Read
  specific parameter names or shallow networks, and expand only as needed.

## TDAbleton / AbletonMIDI

- Treat `abletonMIDI.par.Adddevice.pulse()` as asynchronous.
- Do not set raw menu labels into TDAbleton menu parameters before the menu contains the label.
- For TDA_MIDI creation, keep `Connect` off, pulse `Adddevice`, wait until `TdaMIDI` exists in the Device menu, select it, clear stale script errors, reinit if needed, then turn `Connect` back on.
- The red X can be caused by TDAbleton's first LOM/menu pass racing device creation; disable/re-enable works because it forces a later pass.

## Importlib Modules

- Keep TD runtime imports constrained and explicit. Avoid defensive lazy-import patterns that hide runtime state or load broad module graphs from hot UI paths.
- Python files loaded with `importlib.util.spec_from_file_location()` do not automatically have TD globals like `op`.
- Pass TD globals through the manager/source environment, or call through an object that can provide `op`.
- In callbacks stored as DAT text inside TD, `op()` is available. In external modules, assume it is not.
- Never store live module objects in operator storage. TD pickles storage on save, and module objects cannot be pickled.

## UI / Workflow Shape

- Mapping data is per MIDI source wrapper. The user-facing entrypoint should be on the source wrapper, not only on a global manager.
- The global manager can host shared modal UI, but it should edit a specific source's `mappings_json`.
- Source wrappers should expose an `Open Mapper` pulse.
- Keep setup/authoring behavior separate from performance runtime behavior.
- Setup/authoring can discover Ableton tracks, create wrappers, add `TdaMIDI`, build UI, create envelopes, and bind parameters.
- Performance runtime should only handle callbacks, maintain local note state, read existing mappings, and pulse mapped targets.
- Do not run broad Ableton discovery, UI scans, or debug bridge behavior during performance unless explicitly enabled.
- Note mapping UI should be sparse: show `*`, mapped notes, and notes that have actually fired. Do not show all 0-127 notes by default.
- Incoming notes need immediate visual feedback: insert the note if missing, show velocity, and flash/fade the row quickly.
- Multiple envelopes/route targets can map to the same note.
- "Go to envelope" style actions should select the target OP, make it current, and open its parameters. Keep this explicit in UI rather than overloading every row click.

## Visual Control Idioms

- For `ScreenShake.tox`, use envelope output range to control effect strength.
- Keep `Triangleamp` and `Noiseamp` as fixed relative mix controls. Do not put envelope expressions directly on them.
- Drive `screen_shake.par.Amount` from the envelope/null output, then tune intensity with the envelope's `Outputminimum`/`Outputmaximum`.

## Parameter Ownership

Think in terms of OOP: a component owns a cohesive behavior, its state, and the
parameters that control it. An isolated chain involving controls can be
consolidated into such a component, with those controls exposed as parameters.
Keep the interface scoped to that behavior instead of collecting unrelated
controls on the visual parent. Err on the side of less consolidation and a
smaller interface; the user can always ask to consolidate more later.

### Public Interface Shape

A behavior's owning component inside the visual is its public control surface.
Its parameter pane should make the current setting visible and expose the
controls someone needs to operate and tune it. Keep the visual parent thin by
placing these parameters on the relevant child component. Expose an existing
component's useful controls before considering another wrapper or consolidation.

- **Values and actions:** expose selections, amounts, enables, and relevant
  trigger/advance/reset pulses. A color component should expose its palette
  selection and transition time; opening an internal crossfade to find the
  current index is an interface gap. Detailed ramp editing can stay inside.
- **Ownership:** keep palette ordering/selection semantics, output min/max,
  and artistic timing in the visual. The external song layer selects sources,
  calibrates incoming audio/MIDI when needed, and supplies values or events to
  the public interface. It must not be the only place a visual can be tuned.
- **One source of truth:** local controls, keyboard actions, and external
  routing should operate the same public state. Internal operators reference
  or bind to it. Avoid a public display disconnected from the actual editable
  control, or independent copies of the same value in song and visual controls.
- **Stable boundary:** external continuous mappings supply named CHOP inputs;
  event mappings target the owning component's public actions. Document input
  units, ranges, and local operation. Do not route into private implementation nodes.
  The visual must remain usable when exported without its song connections.

For example, a song supplies a normalized noise amount while the visual owns
its output range. A palette selector exposes selection and transition time on
the palette component. See [the visual's control guide](raytk/PerformanceControls.md)
for a concrete implementation.

Before completing a new hookup, check that someone can find its current value
and artistic controls inside the visual, and that the external route uses the
public interface without needing to know internal node names.

## Control Routing Defaults

Agreed 2026-09-22 after diagnosing failed live mappings:

- **Visible signal processing:** use native CHOPs for selection, scaling,
  clamping, smoothing, envelopes, counting, and integration. Keep the processing
  inspectable in the network instead of hiding it in Python or Script CHOPs.
- **Simple continuous connections:** reference the final channel in a parameter,
  for example `op('amount')['value']`. Do not use CHOP exports (the green flag)
  or callbacks that continually copy values between parameters. For public
  controls that must remain editable, use a Python bind expression to a native
  Bind CHOP; local and incoming changes then share the same state.
- **Minimal event Python:** reuse MIDIHandler for notes and existing component
  actions for triggers. Add a small callback only when an event needs one; use
  native operators when they already perform the behavior.
- **Independent mappings:** avoid putting unrelated updates into one execution
  path where one failure prevents the others from updating. Give continuous
  controls their own CHOP paths and references; keep an event callback focused
  on its action; remove a deleted component's own routing without disrupting
  other controls. For example, removing a noise effect must not stop a palette
  input; a failed MIDI target must not gate an unrelated audio-level chain.
  Shared inputs and reusable components are fine.
- **Visible failures, focused verification:** no `eval()` in mapping Python or
  silent fallbacks for missing paths, channels, or targets. Distinguish an
  intentional disabled/disconnected input from a broken reference. Remove stale
  references when deleting components. Verify the changed route from actual
  input to visible output; inspect `scriptErrors()` for callbacks as well as
  ordinary operator errors. Check reconnect behavior when connection logic
  changes. Avoid broad project scans or a large testing framework for a hookup.

The confirmed failure was a shared callback referring to the deleted NoiseDrift
component. Its exception prevented later export-enable updates for unrelated
controls. This does not establish that TouchDesigner's export engine itself
failed. See the [audit](raytk/ChopExportInventory.md) and
[current routes](raytk/LiveControls.md).

Visual component structure is documented separately in
[Visual Structure](VISUAL_STRUCTURE.md), alongside the
[parameter ownership](#parameter-ownership) guidance.

## TD Window/Text Focus

- For text entry modals, use `setFocus()` plus `setKeyboardFocus()`.
- Set `allowuishortcuts` off on editable text fields so TD network hotkeys do not leak while typing.
- Avoid synthetic mouse/focus tricks unless absolutely necessary; they have caused instability.
- TD `Par` truthiness can reflect its value; a parameter at `0` can behave falsey. Check `par is not None` when testing existence.
- Parameter Execute DAT uses the `valuechange` toggle for `onValueChange`, not `onvaluechange`.
- Use native Bind CHOP for last-change-wins performance controls; do not poll
  parameter snapshots each frame to implement takeover.

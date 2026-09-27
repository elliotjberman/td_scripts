# TouchDesigner workflow

Read `TOUCHDESIGNER_DEV_NOTES.md` before changing TouchDesigner runtime,
MIDI mapping, component authoring, or agent bridge code. Read
`midi_handler_v2/README.md` for the current source-wrapper and mapping workflow.

## User priorities

- Audio- and MIDI-reactive visuals are a core use case.
- ScaledEnvelope is central to the user's workflow. Reuse and inspect the existing
  component rather than substituting a generic envelope by default.
- Connect continuous CHOP values with short Python parameter references. For an
  editable public control, use a Python bind expression to a native Bind CHOP.
  Do not create CHOP exports (the green flag) or callbacks that continually copy values.
- Do not use `eval()` in mapping Python or fallbacks that conceal missing paths,
  channels, or targets. Mapping failures must be visible and verifiable.
- Use native CHOPs whenever they can perform the signal processing: math,
  ranges, clamping, selection, envelopes, lag, spring, and integration. Keep
  Python to simple references and necessary event callbacks. Reuse MIDIHandler
  for notes. Keep unrelated mappings independent; avoid shared update callbacks
  where one failure prevents other mappings from updating. Avoid frame-by-frame
  polling. See
  [control routing defaults](TOUCHDESIGNER_DEV_NOTES.md#control-routing-defaults).
- The user is moving from Ableton to Bitwig. Defer DAW migration unless requested;
  do not assume the existing TDAbleton source wrappers already support Bitwig.
- For Bitwig, inspect the existing Derivative TouchDesigner controller first.
  It communicates over OSC, so MIDI-port discovery alone cannot determine
  whether it is enabled. See [Bitwig note input](midi_handler/Bitwig.md).

## Documentation layout

- Keep repository-wide priorities and instructions here. Put folder-specific
  instructions in that folder's `AGENTS.md`, with links to component documents.
- Use a named Markdown file per component for its purpose, controls, and usage.
  Keep a single shared description when multiple folders contain the component.
- Before using ScaledEnvelope in any visual, read
  [its component guide](midi_handler_v2/ScaledEnvelope.md).
- MIDI v2 authoring and routing instructions live in
  [midi_handler_v2/AGENTS.md](midi_handler_v2/AGENTS.md).
- Reusable utility component guides are indexed in
  [utils/AGENTS.md](utils/AGENTS.md), including ScreenShake, TopVignette,
  DefaultValue, and MovieRecorder. Read the relevant guide wherever a component
  is used, even if the visual lives in another folder.
- Keep setup/discovery/UI work separate from the performance runtime. Audio,
  MIDI, and envelope evaluation must continue inside TD without agent tool calls.

## Visual component boundaries

- Use three layers: shell/shared DAW bridge, mapped visual with song routing,
  and nested reusable visual. Continuous values cross the visual boundary through
  named CHOP inputs; events use public actions/MIDIHandler. See
  [Visual Structure](VISUAL_STRUCTURE.md) for ownership, local controls, and reuse.
- Keep visual parents thin. Retain the template's shared contract, such as
  inherited resolution and Home, rather than adding every effect parameter to
  the parent interface.
- Think in terms of OOP: an isolated chain with a cohesive behavior can become
  a component that owns that behavior and exposes its controls as parameters.
  Err on the side of less consolidation; the user can always ask for more. See
  [parameter ownership guidance](TOUCHDESIGNER_DEV_NOTES.md#parameter-ownership).
- Give each visual behavior a usable public interface on its owning component
  inside the visual: current selection/value, relevant ranges and timing, and
  actions such as Advance or Reset. Routine tuning must be possible from that
  component's parameter pane without entering its implementation network.
- External song/track routing must target that public interface. Keep visual
  choices, artistic ranges, and behavior controls inside the visual; do not
  bury them solely in external track controls or target private nested operators.
  Keep one authoritative control shared by local and external operation. See
  [public interface shape](TOUCHDESIGNER_DEV_NOTES.md#public-interface-shape).
- Author visual containers for eventual export as external `.tox` components in
  live setups. Keep their processing, animation CHOPs, and local controls inside
  the export boundary, with relative references that survive renaming or moving
  the visual. Keep Embody/Envoy outside that performance component.
- Keep the shared DAW bridge in the shell and song-specific receivers/mappings
  in the mapped wrapper, alongside its nested visual. The visual owns its
  ScaledEnvelopes and effect behavior. Changing songs changes the wrapper,
  without rebuilding the visual or adding DAW controls to its parent interface.

## Network layout

- Always arrange envelopes as one contiguous group, top to bottom in debug-key
  order (`1`–`9`, then `0`). Keep each envelope's reference Null and short
  processing chain on its row, flowing left to right.
- Place standalone parameter/control components below the last envelope row.
  For example, `SliceControl` belongs below `PlaneNoiseEnvelope` when that is
  the last envelope, rather than between envelope rows.
- Pack operators and rows tightly, with only a small, consistent gutter between
  their visible bounds and labels. Use the tallest operator in each row to size
  its vertical spacing. This compact layout takes precedence over generic
  tooling guidance that imposes large grid steps or minimum gaps.
- When adding or reassigning an envelope, or when asked to tidy this layout,
  reflow the existing envelope/control block in place using these rules. Move
  existing controls below the complete envelope group and close oversized gaps;
  preserve operator names, wiring, parameter values, and behavior.
- Verify the resulting node positions and inspect the actual network layout
  before reporting a layout change complete. A request solely to document this
  guidance remains a documentation-only change.

## Agent connection and verification

- Use the user's Embody/Envoy integration for live TD inspection and authoring.
  Confirm available tools and the connected project before modifying operators.
- As of the 2026-09-13 inspection, `/Users/elliot/embody_demo/.codex/config.toml`
  configures Envoy at `http://127.0.0.1:9870/mcp`. This `td_scripts` checkout has
  no project MCP configuration. Recheck current state rather than assuming a
  connection in another project is available here.
- CodexDebugger has been removed. Do not use or recreate the file-backed Python
  execution bridge. If Embody/Envoy is unavailable, diagnose its connection and
  report any unresolved blocker instead of installing a substitute bridge.
- Do not embed arbitrary agent execution or bridge polling into performance
  components.
- Distinguish files found on disk from live verification. Before declaring a
  reactive patch ready, verify its input signal, envelope/output response,
  parameter mapping, visible result, errors, and performance in TouchDesigner.

## Worktree durability

- Never place an active or uncommitted worktree under `/tmp`, `/private/tmp`, or
  another restart-ephemeral directory. Use a persistent workspace path.
- Before requesting a computer, TouchDesigner, Bitwig, or other development-host
  restart, create a recoverable Git checkpoint and verify the worktree survives.
  A generated artifact or automatic Codex turn-diff is not the primary backup.

## GitHub publishing

- A failed `gh auth status` is not itself a publishing blocker when the connected
  GitHub app is available. Use the configured Git remote (including SSH) for
  fetch/push and the connected GitHub app for pull requests.
- Request `gh` reauthentication only for a genuinely gh-only operation after
  testing available connected-app, Git, and other API paths.

# TouchDesigner workflow

Read `TOUCHDESIGNER_DEV_NOTES.md` before changing TouchDesigner runtime,
MIDI mapping, component authoring, or agent bridge code. Read
`midi_handler_v2/README.md` for the current source-wrapper and mapping workflow.

## User priorities

- Audio- and MIDI-reactive visuals are a core use case.
- ScaledEnvelope is central to the user's workflow. Reuse and inspect the existing
  component rather than substituting a generic envelope by default.
- The user is moving from Ableton to Bitwig. Defer DAW migration unless requested;
  do not assume the existing TDAbleton source wrappers already support Bitwig.

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

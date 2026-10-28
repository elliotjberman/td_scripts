# Bitwig live master

Read [README.md](README.md), [Visual Structure](../VISUAL_STRUCTURE.md) and
[TouchDesigner Development Notes](../TOUCHDESIGNER_DEV_NOTES.md) before changing
the master. Read [Setlist.md](Setlist.md) before changing startup preparation or
loading presentation. Use Embody/Envoy through `dev/live_bw/envoy_live_bw.toe` for live
authoring; keep its integration and `.venv` outside the clean runtime TOE.

- Keep official `bitwigMain`/`bitwigSong`, resolution and constant Home in the
  shell. Keep song routing/MIDIHandler in mapped wrappers and artistic controls,
  envelopes and rendering in their nested visuals. Read the
  [track export guide](tracks/README.md)
  and [Connection Screen guide](ConnectionScreen.md) before changing those components.
- The production master requires matching selected-project identities from the
  official bridge and the read-only Audio Engine Handoff controller, with that
  project's engine active. Tab selection alone holds the accepted visual;
  dropping MIDI/control input during that interval is intentional. Do not add
  input caching, time-based switch delays, or polling. See [controller setup](bitwig/README.md).
  The master has no Mock source selector or automatic test cycle. Preserve the four real
  project names in README.md. Coordinate shared DAW use before live checks;
  connecting observers does not authorize UI changes or playback control.
- Gate every song receiver by its wrapper's project identity while preserving
  its individual enable choice. Keep deliberately unused receivers disabled.
  Resignation has real LiveControls and a PercRate clock: preserve them when
  refreshing its mapped TOX, and gate the discrete clock callback by song too.
  Never run the earlier mock-only LiveControls deletion on a live wrapper.
- Song exports are external dependencies, registered in `setlist.json`. Read
  [Refresh.md](Refresh.md) and the v1 host contract in Visual Structure. Startup
  and explicit Load Set reread the file and components, then warm selected ones.
  Never reload files during a cue or add a watcher. Source updates require no
  master rebuild. The standalone source shell must supply the same contract.
- The JSON `visuals` registry is authoritative. `song_map` and the embedded
  `setlist` are generated inspection data. Names match exactly; duplicates,
  missing files and invalid contracts fail visibly. The host supplies project
  identity/readiness before import; the loader must not edit source internals.
- Use native project/connection events. The shared `connections['ready']` gate
  combines main connected, Song Connect and Song Connected. Enable only the
  connection DAT's implemented off/on edges; do not add polling.
- Preserve the shared bridge's cursor-reuse compatibility patch: exported cursor
  indices identify per-project Bitwig pins. Exclusive song wrappers reuse them;
  simultaneous enabled owners must fail visibly. See [bridge notes](bitwig/README.md).
- Keep visuals resident with Allow Cooking on. `SetLoader` prepares only the
  external setlist's selected song wrappers, sequentially,
  behind the output gate. Declare gated branches in the nested visual's optional
  `warmup_tops` table. Do not change cooking flags or force rendering in the
  project-switch handler. Unlisted components can still occupy resident memory.
- Keep loading state independent of its skin: publish Ready, Loading,
  Loadcount, Loadtotal, Loadvisual and Loadstatus on the master. `loading_view`
  reads that contract through its State OP parameter; the loader must not access
  presentation nodes. `output_gate` alone selects loading or show output using
  Ready. Future asynchronous resources need an explicit readiness check; elapsed
  warm frames are not a universal guarantee.
- The current startup presentation is documented in [Programme Startup](ProgrammeStartup.md):
  visual preload, connection test, stop the Rust test, then Bitwig. Keep the title,
  footer and layout shared between the two views. `visuals/screensaver` now hosts
  the connection screen; the noise artwork is embedded inside that component.
  Save a fresh-start export with native Reset Test applied. Preserve the latch
  during the session, and keep hidden RGBA-delay caches off Always Cook.
- Only the setlist's project selection is required. Personal title metadata
  must not affect validation, warmup or loading presentation.
- Queue only the latest request until set readiness. Unavailable startup
  selects the screensaver after preparation; connected startup queries the
  engine observer and accepts only an engine-qualified identity. A mapped visual
  outside the warmed set remains selectable as a potentially slower fallback;
  log each accepted fallback transition persistently. The setlist selects warmup,
  not permission to switch. Keep missing/broken visual errors visible.
  Reset during loading lets preparation finish but keeps show output black until
  a new request. A loader failure keeps Ready off; Load Setlist retries.
- Preserve native two-slot Timer/Cross fades, default two seconds, with explicit
  host resolution/aspect. Never rewire a visible slot during a fade. Retire the
  outgoing Select to black one frame after completion, checking owner validity,
  extension identity and generation before acting. Dispatch pending work only
  after retirement; keep only the latest request. Empty strings are valid
  screensaver requests; `None` means no pending request.
- Empty/all-whitespace requests select the screensaver; unknown nonempty names
  select black. Disconnection holds the accepted visual and cancels pending work.
  Mapping errors cancel pending work and remain visible after a current fade
  finishes. Do not infer no-project state from disconnection.
- Keep Embody, agent startup helper DATs, hardware-audio
  lifecycle, IP discovery, recorder and Ableton reload/reset machinery out of
  the runtime TOE. Preserve the original noise artwork inside the programme screens.
- Keep finite checks, fixtures and reports in [dev/live_bw](../dev/live_bw/AGENTS.md).
  Verify full-image endpoints with passive snapshots after one master demand,
  hidden TOP cook deltas, queued requests, stale retirement callbacks, runtime
  errors and save/reopen. Report finite benchmark results with their scope;
  distinguish isolated checks from actual Bitwig integration.

Add a future visual End action or extension-resource destructor only when its
shared contract or real resources require it.

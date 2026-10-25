# Audio Engine Handoff

`Live Visual Handoff.control.js` reads Bitwig's `Application.projectName()` and
`Application.hasActiveEngine()`. It sends one coherent state packet after a
change, using Bitwig's native controller flush. Explicit state queries request
the same flush, including when transport is stopped. The query method uses a
wildcard type-tag matcher so TD's OSC payload is dispatched. It has no MIDI ports, DAW writes,
timer, or playback loop. Keep the official Derivative TouchDesigner controller
enabled for notes, controls and transport.

Copy the script to `~/Documents/Bitwig Studio/Controller Scripts/`, then add
**Live Visuals → Audio Engine Handoff** in Bitwig Settings → Controllers. One
instance is sufficient for every song tab. No per-song controller is needed.

- Bitwig sends `/live/engine/state` (project string, active boolean) to local
  UDP port **9100**. The master's `engine_state` DAT receives it.
- The master queries `/live/engine/get` with integer `1` on local UDP port **9101** when the
  bridge connects, the selected project changes, or set preparation finishes.
  This also handles opening TD after Bitwig. There is no heartbeat or polling.
- The existing official bridge remains on **8088 / 9099**.

The master holds its accepted visual while an inactive tab is selected, while
disconnected, or while project identities disagree. Activating the selected
tab's engine commits the cue and starts the normal crossfade. MIDI and control
input may drop while browsing; there is no input cache. Visual/source TOX files
do not need a new interface for this handoff.

Only one TD master should own these receiver ports in a live setup. A missing
observer leaves a visible WAITING status instead of treating a tab click as a
performance cue.

## Shared native bridge compatibility

The shell's TDBitwig 1.2.4 `BitwigMainExt` preserves each imported receiver's
saved cursor index. These indices refer to track/device pins stored by Bitwig
for each project. Allocating fresh indices on import silently selected other
tracks. Inactive song wrappers may reuse an index; two enabled owners produce
a visible collision error. Removing an old receiver releases a slot only if it
still owns it. Connection scans include enabled receivers only.

When another Song receiver joins, the bridge briefly resubscribes the shared
transport listener so the official controller flushes constants such as tempo.
This changes subscriptions, not Bitwig's playback or engine state.

The cursor-reuse compatibility patch is embedded in the saved shell and
preserved in Git history. It does not rewrite imported song mappings. Recheck
this behavior when upgrading TDBitwig.

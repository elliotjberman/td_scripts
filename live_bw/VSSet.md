# vs_set

This launcher is delivered after the standalone connection utility. Its full
visual → MIDI → Bitwig flow also requires the separately delivered
`live_bw.toe`, its embedded heartbeat, and the TOX/preview files referenced by
`setlist.json`. Those binary assets are not part of the launcher PR. `bwset`
works independently with a local setlist and Bitwig projects.

Run `vs_set` from any directory. It is a prebuilt Rust CLI in
`../live_connection_util/target/release/vs_set`; both launchers and the MIDI test
run locally with no Python, Cargo, Envoy, agent or internet dependency at showtime.

1. `vs_set` listens for the master heartbeat, reuses the matching running
   `live_bw.toe`, or opens it if TouchDesigner is absent. It waits for confirmed
   visual readiness before offering the MIDI test. A new master starts in Perform Mode, with 1920×1080
   rendering scaled to fill the external monitor/projector. The first display
   not named Built-in/Color LCD is selected, so the studio LG can be exchanged
   for the gig projector. Escape returns to the editor.
   The borderless window uses Custom sizing with expressions for that display's
   native width and height, avoiding the startup flash from Fill Location.
2. Wait for Visual Loading to finish (four song visuals), then press **Enter**
   in the terminal. The native MIDI test starts at 65 BPM, with OSC on localhost
   port 9012. Its meters appear on the TouchDesigner connection screen.
3. Press **Enter** again. The launcher sends SIGINT to its test child and waits
   for successful process exit, including note releases and audio-stream closure.
   Only then does it open the Bitwig projects in the external setlist's order.

**Ctrl-C** cancels without advancing. During the test it also stops the owned
MIDI child. A test error or shutdown timeout prevents Bitwig from opening.
TouchDesigner and already-opened Bitwig projects are left running on cancellation.
The launcher rejects a second simultaneous launcher session, a missing external
display, or Bitwig already running before the audio test. A different TD project
is left untouched. An existing TD process without a matching heartbeat is given
startup grace; it is never treated as permission to open a second copy.

The `bwset` alias runs `vs_set bwset`: just the native Bitwig-opening stage.
It uses the same local JSON and recursively finds exact `.bwproject` filenames,
rejecting missing or duplicate matches before opening anything. Like the former
Python command, it waits for Bitwig's application-startup completion, then allows
five seconds between open requests. Start with no song tabs open for a fresh tab
order; it does not close or reorder existing tabs and does not press Play.

```sh
vs_set --dry-run                 # verify local paths/order; no app or device opens
vs_set visuals                   # open/reuse only TD; also works while Bitwig runs
vs_set td-status                 # two-second read-only heartbeat snapshot
bwset --dry-run
bwset --delay 8                  # optional longer interval between project opens
connect_test                    # standalone TUI test; Ctrl-C stops it
```

To install the aliases, add the following to `~/.zshrc`, using the path where
you built the binaries, then run `source ~/.zshrc`:

```sh
alias vs_set='/path/to/td_scripts/live_connection_util/target/release/vs_set'
alias bwset='/path/to/td_scripts/live_connection_util/target/release/vs_set bwset'
alias connect_test='/path/to/td_scripts/live_connection_util/target/release/live-connection-util --osc 127.0.0.1:9012'
```

The launcher currently embeds its source checkout's location at compile time;
rebuild after moving the checkout.
All three aliases point directly to binaries, not `run.command`. Keep the
repository, compiled binaries, registered TOXs/previews and Bitwig projects on
this machine. The MIDI score is embedded. Local OSC works with Wi-Fi off.
TouchDesigner/Bitwig/plugin offline licensing must already be available; an
actual Wi-Fi-off hardware rehearsal has not been performed by these checks.

Build/update before the gig, separately from launching:

```sh
cd /path/to/td_scripts/live_connection_util
./cargo-local build --offline --locked --release --bins
```

`run.command` remains a development convenience that builds before running.
The gig commands never fetch or build; a missing installed binary fails visibly.
The `bwset` alias uses the Rust launcher; Python is not needed at showtime.

Validation covers exact project ordering, missing/ambiguous projects, failed-test
handoff refusal, and clean SIGINT shutdown of the simulated MIDI child (no
hardware streams). Native master save/reopen checks are separate from real
Bitwig playback and hardware-audio rehearsal.

## TouchDesigner health

The embedded master `Heartbeat` component sends one OSC/UDP packet every 0.5s
to `127.0.0.1:9013`. Its native Timer triggers a short send callback on TD's
normal processing thread: a frozen main thread cannot keep sending from a
background thread. There is no HTTP server, agent bridge, response, file write
or hardware dependency. The OSC Out DAT uses loopback for both addresses.
The component owns Enable, Port, State and Output controls. Both master TOEs
embed its code; `heartbeat.py` is its editable source, not a runtime file read.

Each `/vs_set/td/heartbeat` message has these ordered OSC arguments:

| Fields | Types |
| --- | --- |
| Schema version (1), actual TOE path, fresh session UUID, PID, increasing sequence | int, string, string, int, int |
| State (`loading`/`ready`/`error`), loaded count, total, loading visual, load status | string, int, int, string, string |
| Current visual, Bitwig project, router status | string, string, string |
| Final TOP total cooks, last absolute cook frame, width, height | int × 4 |
| Selected visual exists/enabled, Perform Mode | int × 2 (0/1) |

Output inspection is passive; it does not demand an extra render or cook hidden
visuals. These counters describe TD's output, not physical projector health.
A static picture may legitimately stop cooking, so unchanged counters alone
are not considered a crash. Readiness requires the master's completed preload,
a present selected visual and a final output that has cooked with valid size.
Existing loader/router errors are reported without scanning all song internals
twice per second.

Rust binds the port exclusively, gathers two seconds of discovery, checks the
actual TOE identity and confirms advancing sequence numbers. It rejects duplicate
master sessions and does not refresh liveness from replayed/out-of-order packets.
AppKit process IDs are only the final guard against duplicate app launches;
they do not establish visual readiness. Initial imports/compilation get up to
180 seconds, including temporary heartbeat gaps. Once ready, three seconds
without a fresh heartbeat stops the launcher. During the MIDI test this also
stops its owned child and prevents Bitwig handoff. A changed session or lost
readiness likewise requires a new launcher run.
Health checks continue while the MIDI child exits. Any failure is retained even
if TD recovers before that exit: MIDI cleanup finishes, then startup stops
without opening Bitwig.

`vs_set visuals` can be used to restore TD independently after a crash, including
while Bitwig is running. It leaves a healthy matching master in place. Frozen
or wrong-project instances are not killed or overwritten. `td-status` prints
the received state; its exclusive listener cannot run alongside `vs_set`.

The CLI checks TD through the MIDI-test handoff, then exits after opening the
Bitwig set. This is startup/restart protection, not a persistent show supervisor.
Bitwig crash recovery and per-project loading acknowledgments remain separate.

## Validation

Build both release binaries before the launcher's child-process integration test:

```sh
cd /path/to/td_scripts/live_connection_util
./cargo-local build --locked --release --bins
./cargo-local test --locked --bin vs_set
./cargo-local clippy --locked --all-targets -- -D warnings
./cargo-local fmt --check
```

The default tests cover project resolution/order, failed-child handoff refusal,
clean simulated-child shutdown, heartbeat parsing, stale/replayed packets and
duplicate sessions. A delayed-child regression covers heartbeat loss and recovery
during shutdown, verifying cleanup completes while the handoff stays blocked.
They open no physical MIDI/audio hardware or DAW apps.
The ignored `native_master_lifecycle` test operates on a real TouchDesigner
master: it may open TD, and `VS_TD_FREEZE_CHECK` briefly suspends/resumes its
identified process. Run it only during an explicit, checkpointed lifecycle test.
Full startup/display rehearsal uses the separately delivered TD assets; earlier
local testing included a cold reopen to 4/4 Ready, reuse of a matching running
master, and heartbeat loss/recovery without opening a duplicate. Bitwig crash
recovery remains outside this launcher.

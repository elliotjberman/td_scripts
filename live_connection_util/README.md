# Live Connection Util

Rust terminal test for Elliot's live hardware chain. It loops the bundled
**Invention_Berman_separate_staves.mid** through the **KeyStep**, with an
independent input meter per synth. The first note track (upper staff) goes to
Tetra/channel 2; the second (lower staff) goes to Moog/channel 1.

| Synth | MIDI | Analog Four return |
| --- | --- | --- |
| Moog | Channel 1 | Input 8 / Input R / Ext 2 |
| Tetra | Channel 2 | Input 7 / Input L / Ext 1 |

The default score plays at **65 BPM** and loops every **81.23 seconds**, preserving
its pitches, velocities, note lengths and opening rests. The source file encodes
120 BPM; `--bpm 120` plays that tempo. The MIDI is kept in `midi/` and embedded in
the binary so `connect_test` works from any directory. `--bpm` overrides the
playback tempo. `--midi-file path.mid` selects another file containing two note
tracks in upper/lower order and uses that file's tempo unless overridden.
File program changes, controllers, pitch bends and SysEx are ignored. Before
playback, the utility sends **neutral pitch bend** to both synths: MIDI value
8192 (bytes `E0 00 40` and `E1 00 40`), equivalent to a centered bend value of 0.
Startup also selects Tetra bank 1/program 78 and the College Town Moog/Sirin
patch (raw program 24); see Program changes below.

After input/output callbacks confirm the interface is working, the utility
publishes its first healthy telemetry frame and waits **one second** before
checking **MIDI Routing**. If KeyStep is missing, the test stays running and
retries every half second; plug it in to continue automatically. Only a uniquely
matched, successfully opened output passes this check. Ambiguous names and
connection errors remain visible and retry without selecting another device.
Metering, monitoring, OSC and stop controls remain active while waiting.
After routing succeeds, it waits **one more second** before the normal bend/patch
setup and 150 ms settling delay that precede playback. Waiting never consumes
opening notes or rests.
Demo mode uses the same stages;
`--midi-only` skips the first pause because no audio-interface check is performed;
the one-second pause after routing still applies.

`--quarter-notes` retains the original 160 BPM, MIDI 60 (C3), velocity 96,
150 ms gate test. `--note`, `--velocity` and `--gate` apply to that mode.
MIDI note number is authoritative; octave labels differ between applications.

## Run

Build once before a show, then run the native binary. Development builds need
Rust/Cargo and macOS Command Line Tools; the built utility has no Python,
TouchDesigner, Bitwig, or internet dependency. Hardware validation is on macOS
with CoreAudio/CoreMIDI.

```sh
cd /path/to/td_scripts/live_connection_util
./cargo-local build --locked --release
```

For `connect_test` from any directory, add this to `~/.zshrc`, using your actual
checkout path, then run `source ~/.zshrc`:

```sh
alias connect_test='/path/to/td_scripts/live_connection_util/target/release/live-connection-util --osc 127.0.0.1:9012'
```

`run.command` builds before running; the alias uses the prebuilt binary.

```sh
cd /path/to/td_scripts/live_connection_util
./run.command --list
./run.command --demo                  # visual preview, no hardware opened
./run.command --seconds 15            # bounded hardware test
./run.command                         # loop the Invention until Ctrl-C
./run.command --quarter-notes         # original steady pulse test
connect_test                          # loop with OSC to TouchDesigner on 9012
```

Space pauses/resumes MIDI at the current score position while input metering continues.
Pause releases held notes; playback resumes with the next scheduled attack. Ctrl-C exits.
Ctrl-C, SIGTERM, device errors and normal timed completion release this app's active
notes on both channels. Forced process kill or unplugged hardware cannot
guarantee a delivered note-off. No clock, transport, sustain or all-channel reset messages are sent.
The only bank-select message is the configured Tetra CC32 before its program. Keep other sequencers from sending the
same note/channel during the test, since MIDI cannot distinguish note owners.

The app reads CoreAudio independently of Bitwig. For this rig, finish the test
and release its audio streams before opening Bitwig.
The `Alien Live Cut` investigation documented
distorted audio when a separate reader shared the experimental Overbridge HAL
with Bitwig. Concurrent operation on that driver remains unverified; finish
active recordings before testing coexistence. The app does not stop Bitwig or
change the audio driver. `--midi-only` opens no audio stream and explicitly
labels both returns `UNMEASURED`; it still sends MIDI.

`--list` only enumerates ports/configurations. Names must match exactly or have
a unique case-insensitive substring. Missing audio devices still stop the test;
missing or ambiguous MIDI outputs wait and retry. There is never a fallback to
a microphone or another MIDI output. The TUI shows the routing detail; headless operation prints each routing-state
change to stderr. `--seconds` includes
time spent waiting, and Ctrl-C works even if KeyStep never appears.

```sh
./run.command --midi-port 'KeyStep' --audio-device 'Analog Four' \
  --moog-input 8 --tetra-input 7 --quarter-notes --bpm 160 --note 60
```

Inputs are one-based. The app checks channel count and waits for audio callbacks
before sending MIDI. The CoreAudio float32 input configuration is used; the two return inputs are mixed to this same interface's main output pair. Terminal input access may require macOS
microphone permission. Missing callbacks or a failed stream stop the test.

## Main L/R monitoring

By default the existing input callback mixes **Moog input 8 + Tetra input 7** at
**unity gain per synth**, sends the same mix to **Analog Four outputs 1/2
(Main L/R)**, and leaves outputs 3–6 silent. The separate meters and latency
readings still measure each original input. No second input reader is opened.
CoreAudio channel names were inspected on the connected Analog Four to confirm
that outputs 1/2 are Main L/R. These are also the documented main output pair in
[Elektron's channel table](https://elektron.se/wp-content/uploads/2024/10/overbridge_user_manual_2.0_241016.pdf).

`--no-monitor` keeps metering and MIDI but disables audio output.
`--monitor-gain 0.5` optionally reduces each synth by about 6 dB; the default
is `1.0`, with no attenuation. The summed digital signal is clamped to ±1.
`--monitor-buffer-ms 20` sets the queue target; at least two output blocks are
buffered before playback. Input/output use the same device and sample rate.

A bounded, allocation-free SPSC ring buffer connects the two audio callbacks.
Empty buffers produce silence; after a stall the consumer discards excess queued
audio to recover the target delay. The TUI's OUT row shows queue occupancy and
underruns. Queue milliseconds are measured after the output callback, **not**
total monitoring latency. JSON telemetry includes a `monitor` object with output
and mixed frame counts, underruns, dropped frames, queue milliseconds, and maximum
output peak; it is null when monitoring is disabled or hardware is not opened.
The existing latency estimate still ends at input capture, before monitoring.

The 15-second hardware check at 95 BPM and the initial 0.5 gain sent 720,896 mixed
frames to Main L/R with **zero underruns and zero dropped frames**. Queue
occupancy was 10.67 ms at exit and the peak mix was -16.60 dBFS. Its generated evidence remains local under ignored `runs/`. The subsequent user
settings are 65 BPM and unity gain. Pitch-bend reset bytes were verified through
a virtual MIDI port; continuous hardware playback is left for `connect_test`.

## Read the display

- Cyan `████` flashes while this app's note is on. Dim `░░░░` means note off.
- The outlined return bar measures peak level in the selected input, with a
  short hold and decay so short notes remain readable.
- Red `NO SIGNAL`: below -60 dBFS. Orange `LOW`: -60 to -36 dBFS.
- Green `GOOD`: -36 to -1 dBFS. Red `CLIP`: -1 dBFS or higher.
- The whole synth row takes its return-status color; bar fill shows amplitude.

These are starting thresholds, configurable using `--silence-db` and `--good-db`.
A green meter means sufficient input level, not proof that each MIDI note caused
that audio. Existing audio, noise, patch attack, release, and filtering affect
the result. The maximum peak remains in telemetry and the stop summary. Demo mode
is labeled everywhere and cycles Tetra through silence / low / good examples.

Each synth also shows **rolling latency in milliseconds**, the arithmetic mean
of its last eight detected attacks (or however many have arrived so far), plus
the latest single measurement. Timing is captured in the MIDI worker and audio
callback, independently of the terminal refresh. It measures from just before
the MIDI send call until delivery of the first buffer containing a new attack.
It includes MIDI transport, synth attack, and audio input buffering; it is an
approximate response measurement, not isolated driver latency or sample-accurate
round-trip latency. Buffer delivery quantizes the result.

A fresh attack must exceed `--latency-threshold-db` (default -48 dBFS) and be at
least twice the peak of the preceding audio buffer (about 6 dB higher). The
detector waits up to 250 ms, or 90% of a beat if shorter. A sustained/ringing
signal with no identifiable rise shows `no fresh attack` instead of a new
latency value. Slow attacks and unrelated transients can affect measurements.
Closely spaced score notes can replace a pending attack before a new rise is
detected, so legato passages can yield fewer latency samples.
The average retains eight accepted samples; missed detections don't count as
zero. Demo and MIDI-only modes report latency as unmeasured.

## Program changes

Every new run sends these once, before the first notes:

| Synth | Selection | MIDI bytes |
| --- | --- | --- |
| Moog/Sirin, channel 1 | College Town source patch: raw program 24; bank unchanged | `C0 18` |
| Tetra, channel 2 | Display bank 1, program 78 | `B1 20 00`, then `C1 4D` |

After the one-second interface lead-in, successful routing, and another
one-second pause, the neutral pitch-bend messages precede
these commands. The normal 150 ms settling delay follows patch selection, then
the score's opening rests. The
messages are not repeated on every loop or pause/resume. Restarting the utility
resends them directly, even if the selected values haven't changed.

Tetra uses CC32 values 0–3 for display banks 1–4, and MIDI programs 0–127 for
display programs 1–128 ([official manual, page 48](https://sequential.com/downloads/tetra/doc/Tetra_Manual_v.1.3.pdf)).
Its bank-1/program-78 bytes also match the earlier hardware-confirmed Alien setup.
The Moog setting comes from College Town's source initialization and successful
hardware program tests. That project's October 24 audit found native Bitwig
startup delivery still absent; this utility sends the intended selection itself.
Neither Moog bank byte nor Tetra CC0 is invented. Provenance is retained in
[startup_patches.json](startup_patches.json).

```sh
connect_test                           # requested default patches
connect_test --keep-programs           # retain current patches; still center bend
connect_test --moog-program 24 --tetra-bank 1 --tetra-program 77
```

`--moog-program` and `--tetra-program` accept **raw MIDI values 0–127**.
`--tetra-bank` accepts the **display bank 1–4** and subtracts one for CC32.
`--keep-programs` suppresses both bank and program commands.

## TouchDesigner output: OSC at approximately 30 Hz

Use the native OSC feed for the visual:

```sh
cd /path/to/td_scripts/live_connection_util
./run.command --osc 127.0.0.1:9012
```

Add `--demo` to preview without opening hardware. This still shows the TUI;
Space pauses/resumes notes and Ctrl-C exits. One immediate OSC bundle contains
the entire current state. Addresses and the encoding buffer are reused, and
OSC-only operation does not serialize JSON on each update. Network sends are
nonblocking and run outside the audio callback and MIDI worker. An absent or
restarting receiver does not stop the utility or create a backlog of old state.

In TouchDesigner, use a native
[OSC In CHOP](https://derivative.ca/UserGuide/OSC_In_CHOP):

- Protocol: Messaging (UDP), Local Address: `127.0.0.1`, Network Port: `9012`.
- Active: On, Queued: Off. These are current state snapshots.
- Strip Prefix Segments: `1` removes `lcu`; for example `/lcu/moog/send`
  becomes `moog/send` in the installed TD build. Inspect channel names before mapping.

This uses TD's native numeric receiver without a Python JSON parser, custom
socket receiver, or shared-memory synchronization. TD consumes the measured
levels from Rust and does not need a second audio reader. A TouchDesigner receiver/presentation and the full-set launcher are separate
follow-up changes; neither is required to run this utility.

All values are OSC float32. Global addresses are:

| Address | Meaning |
| --- | --- |
| `/lcu/version` | OSC schema version, currently 1 |
| `/lcu/heartbeat` | Counter incremented each update, including while paused |
| `/lcu/running` | 1 while active, 0 at clean shutdown |
| `/lcu/paused` | 1 when MIDI is paused; return meters continue |
| `/lcu/demo` | 1 for simulated data |
| `/lcu/bpm` | Current playback tempo |
| `/lcu/note`, `/lcu/velocity` | Legacy quarter-note settings; use per-voice values for the score |
| `/lcu/loops_completed` | Completed score loops, modulo 16,777,216 |
| `/lcu/midi_routing` | 0 pending interface lead-in; 1 missing port; 2 output opened; 3 discovery/open error |

Each synth has the following addresses under `/lcu/moog/` and `/lcu/tetra/`:

| Suffix | Meaning |
| --- | --- |
| `send` | Current note gate: 1 on, 0 off |
| `notes_sent` | Note-on counter; identifies notes missed between snapshots |
| `note`, `velocity` | Last sent pitch and attack velocity for this synth |
| `level`, `level_db` | Peak since the previous snapshot, linear and dBFS |
| `meter_db` | Held/decaying display level in dBFS |
| `level_valid` | 1 when measured or simulated; 0 in MIDI-only mode |
| `status` | 0 unmeasured, 1 no signal, 2 low, 3 good, 4 clip; uses held level |
| `latency_ms`, `latency_last_ms` | Rolling average and last accepted attack; -1 when invalid |
| `latency_valid` | 1 if an accepted reading is available and no missed onset is reported |
| `latency_state` | 0 unmeasured, 1 waiting, 2 detected, 3 no onset |
| `latency_samples` | Accepted samples retained in the rolling window, 0–8 |
| `midi_channel`, `input_channel` | One-based routing: Moog 1/8, Tetra 2/7 |

Unmeasured levels use 0 linear / -120 dBFS with `level_valid=0`. During a new
pending attack, latency can still show the preceding accepted reading; inspect
`latency_state` if that distinction matters. Both counters wrap at 16,777,216
to preserve exact integers in CHOP floats and reset when the utility restarts.
Rebase any derived event counts after reconnecting or a counter reset.

Treat a heartbeat unchanged for 0.5 seconds as disconnected and clear the send
lamps; also gate them with `running`. Build this watchdog and level processing
with native CHOPs. Use named CHOP inputs across the visual boundary and short
parameter references or Bind CHOPs for controls. No CHOP exports or Python
polling are required. UDP is best effort: a later snapshot restores current
state, but counters cannot reconstruct the exact timing of missed events.

### Optional JSON output

```sh
mkdir -p runs
./run.command --seconds 15 --jsonl runs/test.jsonl --udp 127.0.0.1:9010
./run.command --headless --seconds 15 --jsonl runs/headless.jsonl
```

JSONL files and `--udp` datagrams share JSON schema version 1 at approximately
30 Hz. `--udp` is loopback-only; each datagram contains one UTF-8 JSON object.
Keep it on a different port from `--osc`. Files contain levels/events only,
no recorded audio. JSONL is flushed on clean exit; the final
frame has `running: false` and both `note_on` fields false. UDP is best effort;
receivers should treat old frames as stale if the process crashes.

Each frame includes `mode` (`hardware`, `demo`, or `midi_only`), `elapsed_seconds`,
`unix_ms`, `running`, `paused`, `bpm`, `note`, `velocity`, `skipped_beats`,
`loops_completed`,
`audio_frames`, and two `voices`. A voice contains `name`, `midi_channel`,
`input_channel`, `note_on`, `note`, `velocity`, `notes_sent`, `peak` (linear), `peak_dbfs` (instant),
`held_dbfs` (display), `max_dbfs`, and `status`. Silence is floored at -120 dBFS;
unmeasured levels are JSON null. Demo counts are simulated; no hardware is opened.
`midi_routing` contains a `status` (`pending`, `waiting`, `ready`, or `error`)
and a human-readable `message` with the selected output or discovery detail.
Each voice also has `latency`: `average_ms`, `last_ms`, `samples` (0–8), and
`state` (`unmeasured`, `waiting`, `detected`, `no_onset`). Before the first
measurement, both numbers are null. When `state` is `no_onset`, any saved numbers
are historical accepted measurements, not a response to the latest note.
Use `--jsonl runs/test.jsonl` to record the rolling readings alongside levels.

## Build and verify

`cargo-local` uses the ignored project-local Rust toolchain when present, or
your installed `cargo` otherwise. `run.command` builds a locked release binary
before launching. `Cargo.lock` pins dependency versions. Source parses files once with [midly](https://docs.rs/midly/0.5.3/midly/) and uses
[midir](https://docs.rs/midir/0.11.1/midir/) for MIDI,
[CPAL](https://docs.rs/cpal/0.18.2/cpal/) for audio,
[rosc](https://docs.rs/rosc/0.11.4/rosc/) for OSC and crossterm for the terminal.

```sh
./cargo-local test --locked
./cargo-local clippy --locked --all-targets -- -D warnings
./cargo-local fmt --check
./cargo-local build --locked --release
./cargo-local test --locked --test virtual_midi -- --ignored --nocapture
python3 tests/check_runtime.py
python3 tests/check_osc.py
```

The opt-in virtual MIDI test needs macOS CoreMIDI access. It creates its own
software destination, verifies actual neutral-pitch-bend/channel/program/note bytes and 375 ms
intervals, and checks note-offs after timed completion and SIGTERM. It never
connects to the KeyStep. The Python runtime check launches the built release
binary in demo mode, exercises a real pseudoterminal (pause/resume/quit and
terminal restoration), and verifies JSONL against localhost UDP telemetry.
The OSC check independently decodes binary packets, verifies native numeric
channels and note gates, and closes/reopens its receiver while the sender runs.
The additional virtual-port score test verifies staff remapping, chord releases,
velocity preservation, ignored file program changes, and repeated loop timing.
These checks open no audio hardware. Their generated evidence goes in ignored
`runs/`.

The original October 24 OSC test received 36 numeric channels in **1,208-byte bundles**
at 27.94 Hz on this machine (the nominal 30 Hz loop is subject to OS scheduling).
It passed startup with no listener, receiver restart, and clean final note-off
state using an independent Python decoder. This verifies the sender and local
UDP behavior; the receiving TD component is delivered separately.

The current feed includes MIDI routing (42 numeric channels, 1,396-byte bundles); existing channel
names remain compatible. The MIDI worker owns the output connection and uses
monotonic deadlines. Attacks more than 50 ms late are skipped instead of replayed
in a burst. Each loop releases any remaining owned notes before wrapping. Audio callbacks only
compute peaks and update atomics; file writes and terminal rendering happen
outside the callback. The UI needs at least 65 columns by 15 rows.

## Hardware validation — October 24, 2026

Ran the TUI for 12.02 seconds with Bitwig closed, the real `Arturia KeyStep 32`
output and `Analog Four` float32 input at 48 kHz / 8 channels. No program changes.
32 note-60 pulses per synth at 160 BPM; zero skipped beats; normal exit with
both note states off. Each of the 32 pulse windows had an input peak above
the -36 dBFS good threshold on both returns.

| Return | Maximum peak | Range of per-pulse-window peaks |
| --- | --- | --- |
| Moog / input 8 | -13.72 dBFS | -15.23 to -13.72 dBFS |
| Tetra / input 7 | -19.11 dBFS | -25.96 to -19.11 dBFS |

Raw level/event telemetry: `runs/hardware-20261024.jsonl`; compact analysis:
`runs/hardware-20261024-summary.json`. These generated files are ignored by Git.
This verifies MIDI transmission and healthy direct input levels during the
bounded test, not Bitwig coexistence, audible fidelity, or long-run stability.

The subsequent eight-second latency test sent 21 notes per synth, with zero
skipped beats. At exit, the rolling eight-attack averages were **13.52 ms Moog**
and **32.04 ms Tetra** (latest individual readings 14.61 and 25.29 ms). These
are callback-delivery response estimates for the current patches. Timing data
are in `runs/latency-hardware-20261024.jsonl` and its `-summary.json` companion.
Four Tetra note windows did not meet the fresh-attack rule and were excluded
from the average; all 21 Moog windows produced estimates.

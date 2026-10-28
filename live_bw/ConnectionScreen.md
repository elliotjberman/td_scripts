# Connection Screen

Author in `../dev/live_bw/envoy_live_bw.toe` at
`/project1/live_bw/visuals/screensaver`. The production master is `live_bw.toe`;
`vs_set` opens it. The canonical screen export is `connection_screen.tox`.

The title uses **Helvetica Bold**, bitmap rendering, 60-pixel type and -4.8-pixel
tracking: **VS Electronic Music** / **Audivisualisation** / **Programme 3**.
Helvetica headings introduce Audio Interface, MIDI Routing, Tetra, then Moog. Menlo readouts show the MIDI gate,
channel, note, outlined return meter, level, rolling latency, and latest latency,
in 18-pixel type.
Each section follows the utility's live red / orange classification until it
first passes. A passed section stays green for the session with a **PASSED** label, even
after the sender stops or its level falls. Live meters and MIDI lamps continue
to show current telemetry; the passed state records the completed check.
The background is blue (`#0000AA`). The exact four-line funding/copyright credit
is editable through `Layout.Footer` and renders in white 16-pixel Menlo at bottom left.
White FCC, CE, UL, and crossed-out-bin marks occupy the right side of this footer
row, separated from its 401-pixel text area by the same 64-pixel gutter. Original
and white SVGs are retained under `assets/footer_marks`; their
[sources and adaptations](assets/footer_marks/SOURCES.md) are recorded there.
The small rendered strip is embedded in a locked TOP, so exported components
need no external files, web renderer, or deprecated SVG TOP at runtime.

The design occupies a centered **1440 × 1080 (4:3)** area inside the 1920 × 1080
output. The left/right gutters are 240 pixels; content has a further 72-pixel
inset. Other output sizes fit this same composition without stretching it.

Within that inset, the status rectangles are 760 pixels wide, with 16-pixel
text padding. The interface and routing rectangles are 50 pixels tall and each synth rectangle
is 100 pixels tall. A 64-pixel gutter separates them from one continuous
472 × 952 noise panel with matching 64-pixel top and bottom margins.
`Layout.Leftshare` and `Layout.Gutter` control the split and spacing.
Headings are 50 pixels tall, with 24-pixel section gaps.
Box padding, heights, and section gaps are also editable on `Layout`; later
sections follow those controls. The noise panel and footer follow the gutter
for their top/bottom spacing.

`NoisePanel` reuses the original placeholder's native noise, harmonics, animated
pixelation, edge treatment, palette, and drift. Its old title layer is removed.
It is embedded locally with no runtime dependency on `live_bw`. Translation
velocity is multiplied by the fraction of green boxes: 0, 1/4, 1/2, 3/4, or 1. The
multiplier is applied before the native Speed CHOPs. Passed checks retain their
share of motion after the sender stops; resetting with no active inputs freezes
the current position instead of jumping to another offset. The original
harmonic/pixelation changes remain autonomous. Palette Index, Speed X/Y/Z, and
Detail controls remain available on the component.

The original five palettes cycle every five seconds through native LFO/Count
CHOPs. On `NoisePanel`'s **Palette** page, **Cycle Colors** pauses/resumes cycling
and **Seconds per Color** changes the interval. **Palette Index** remains editable
through a native Bind CHOP; turn cycling off to hold a manually selected color.

`NoisePanel` receives the named `translation_speed` CHOP input. Its public
Translation Speed control shares that input through a native Bind CHOP, with
pickup disabled. An unconnected component defaults to zero translation.

When all four checks have passed, both outer side gutters fill with repeated
20-pixel green Menlo text on almost-black (`#0C100C`) boxes:
`SET CAN NOW HAPPEN `. Python generates the repeated text
once during authoring; native Text TOPs wrap it to fill the columns. At 1920 ×
1080, each column is 184 × 952 pixels, with 64-pixel outer/top/bottom margins
and 64 pixels to the central content. They sit before the existing post-processing.
Each box has 12 pixels of internal padding. `Layout.Readytextsize` (20) and
`Layout.Readypadding` (12) tune the repeated text and its inset.
They hide when the test is reset, and when the output has no room for side gutters.

## Run

Open `live_bw.toe`, wait for visual preparation, then run:

```sh
cd /Users/elliot/td_scripts/live_connection_util
./run.command --osc 127.0.0.1:9012
```

The default test loops the bundled Invention at 65 BPM: upper staff
to Tetra/channel 2, lower staff to Moog/channel 1. `connect_test` starts it with
OSC enabled; `connect_test --quarter-notes` runs the original pulse test. Each
readout displays its own current/last MIDI pitch from `tetra/note` or `moog/note`.
Space pauses/resumes the MIDI test; Ctrl-C stops it. Add `--demo` for simulated
meters without opening hardware. Demo input is explicitly labeled on screen.
Startup selects Tetra bank 1/program 78 and the College Town Moog/Sirin patch
(raw MIDI program 24, no bank change). `--keep-programs` retains current patches.

TouchDesigner reads OSC only. Rust owns the KeyStep output and Analog Four audio
input, and mixes those returns to Main L/R; this project opens no additional audio reader or MIDI output. The first
section reports active return capture from the utility, not a separate hardware
enumeration. MIDI-only operation is labeled AUDIO INPUT DISABLED.

Rust checks the audio callbacks first, publishes them, waits one second, then
checks MIDI Routing. A missing KeyStep displays **PLUG IN CONTROLLER** and retries
without restarting either app. Successful routing stays visible for another
second before Rust sends MIDI. Native OSC channel `midi_routing` is 0 pending,
1 missing, 2 output opened, or 3 discovery/open error. Routing success confirms
that the requested output is open; the synth return checks provide the separate
signal evidence. Synth checks cannot pass from pre-existing input noise before
routing and their first note. Headless errors/details appear in the `vs_set`
terminal. Demo routing is orange and labeled simulated, never a hardware pass.

## Edit

- Shell `/project1`: output resolution and the authoring-only Embody integration.
- `visuals/screensaver`: OSC port and connection timeout (default 0.5 seconds).
- `visuals/screensaver/visual/Layout`: title text, title size/tracking, section
  heading size, monospace size, and content inset.
- `visuals/screensaver/visual/Layout`: left column share, column gutter, box
  padding/heights, and section gap.
- `visuals/screensaver/visual/NoisePanel`: original placeholder palette and motion.
- `visuals/screensaver/visual/Readiness`: **Reset Test** clears the four completed
  checks. Sections currently receiving a good signal can immediately pass again.
  `passed` exposes the four latched channels; `all_passed` is their native minimum.
- `visuals/screensaver/visual/constant_palette`: editable RGB channels for each
  status: 0 unmeasured, 1 no signal, 2 low, 3 good, 4 clip.
- `visuals/screensaver/visual/ShakeEnvelope`: the shared rumble cadence and peak
  strength in design pixels; debug key **1** previews all four boxes.
- `visuals/screensaver/visual/ScaleEnvelope`: the shared pop cadence and added scale;
  `Outputmaximum = 0.025` means 2.5%; debug key **2** previews all four boxes.

## Ready motion

The first successful check starts a small rumble and centered scale-up
on that rectangle only. Later signal changes do not retrigger until Reset Test.
Both effects return
to neutral and can overlap across boxes without restarting another box.

There are exactly **two ScaledEnvelope components**, each carrying independent
`interface`, `routing`, `tetra`, and `moog` channels with one shared ADSR/range control set.
Their native Trigger/Math processing is preserved; only the input combiner and
channel naming are adapted for multiple channels. Their Trigger buttons and
number keys broadcast a manual preview; incoming status events stay independent.

The native ScreenShake components receive their own envelope channel through
`Amount`, retaining fixed triangle/noise mix values. Compositing applies the
motion and centered scale without cropping to the original rectangle bounds.
The composites use centered justification and pivots; their translation is
divided by the final scale because Composite TOP scales the translation offset.
This keeps each rectangle's center fixed and its shake amplitude independent of scale.
`live_status` contains the raw classifications. `Readiness` uses native Logic
and clamped Count CHOPs to hold each success; no polling or frame callbacks are
needed. `box_status` is the common latched source for color and transition detection. Its small
CHOP Execute callback only increments the corresponding event counter on a
qualifying change; native Logic produces the pulse. There are no frame callbacks
or scheduled pulse resets in the performance network.

`visuals/screensaver/visual` is the reusable visual. Its input is a named CHOP
containing the OSC schema plus `connected`; its output is `out1`. Internal
references are relative. The OSC receiver and heartbeat watchdog belong to the
outer `visuals/screensaver` component, outside the reusable visual boundary.
`connection_screen.tox` exports that receiver plus its nested visual and noise
panel. The host supplies Resolutionw and Resolutionh. There are no separate
visual/noise-panel exports to keep synchronized.

The native receiver keeps hierarchical channel names such as `tetra/send` and
`moog/meter_db` in this installed TD build. A Constant/Replace chain explicitly
defines the disconnected schema. Native Logic/Trigger CHOPs detect heartbeat
freshness, and native Math/Limit CHOPs scale the ASCII meters. A small embedded
DAT formats display strings only; there are no frame callbacks, CHOP exports,
network polling scripts, or external runtime Python files.

A missing/stalled sender clears MIDI lamps and latency. Unpassed sections show
OFFLINE/red; passed sections retain their green **PASSED** presentation.
A clean sender stop takes effect immediately. Reconnection uses the next full
state snapshot without clearing completed checks. The interface name and return labels reflect
the current Analog Four 7/8 rig.

## Validation

The screen has been checked with real hardware telemetry and isolated native
CHOP inputs. Checks covered missing MIDI routing, independent pass latches,
rumble/centered scale, noise speed, persistent passes after stopping the sender,
and Reset Test. Historical build recipes and captures remain recoverable in
Git; current edits use the Envoy master and the single canonical screen export.

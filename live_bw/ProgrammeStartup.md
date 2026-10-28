# Programme startup

[`vs_set`](VSSet.md) runs this sequence with two Enter presses. The manual steps are:

1. Open `live_bw.toe`. Visual Loading displays the actual `SetLoader` state while
   the four selected song visuals are prepared.
2. The loader makes a hard cut to the connection screen. Run
   `connect_test` in Terminal. It receives OSC on `127.0.0.1:9012`; TouchDesigner
   does not open the audio interface or send the test MIDI itself.
   Rust confirms audio callbacks, waits one second, then checks **MIDI Routing**.
   A missing KeyStep leaves that card red with **PLUG IN CONTROLLER** while Rust
   retries every half second. Once routing succeeds, another one-second pause
   precedes MIDI setup and playback. Connecting it continues automatically. Tetra and
   Moog can pass only after routing is open and their notes have started.
3. Stop the test with Ctrl-C. Passed checks and the outer readiness columns stay
   latched for the session. The visual preload remains valid.
4. Open the Bitwig set. The existing project/active-engine qualification and
   native crossfade select the song visual. No manual loading-screen dismissal
   or reload is required.

The Perform window uses **Custom** opening size, with width and height read
directly from the selected display. This keeps automatic monitor/projector
sizing while avoiding the white startup window seen with **Fill Location**
on macOS in TouchDesigner 2025.33070. Rendering remains 1920×1080; no new
startup callback or extra delay is involved. The first external display is
selected, with the built-in display as the TOE's fallback.

With the current registry, preparation is **4 items**: the four song visuals.
The built-in connection screen is shown afterward and is not a warmup item. The ordinal names the item being prepared; the bar and
`PREPARED` count show completed items. Progress measures work items, not time.
Errors remain visible on a red card and keep show output gated.

The two views share the fixed programme title, credit, white marks, centered
4:3 design area, blue background, and right noise panel. Layout scales with the
master's resolution, including the default 1920×1080 output. The loading panel
has the Helvetica heading **Visual Loading** and a Menlo name/count/bar card.
The right-hand rectangle shows the current visual's optional `preview` from
`setlist.json`, with **Crop to Fill** preserving its aspect ratio. **Preview Fit**
can switch to **Fit Whole Image**. Missing or unspecified images use the noise
panel and never block preparation. Preview metadata refreshes on native catalog
and loading-item changes, with no filesystem watcher or frame polling.
The noise fallback's translation follows completed progress. The connection screen keeps
the original two readiness envelopes, with independent channels for Audio
Interface, MIDI Routing, Tetra and Moog. Each passed check adds one quarter of
the noise translation speed; both outer columns require all four checks.

`loading_view.tox` reads only its **State** OP parameter, which points to a
publisher of the six public loading parameters documented in [Setlist](Setlist.md).
It has no MIDI/audio receiver. Its **Catalog** OP and **Catalog File** parameters
explicitly supply optional preview metadata and its path base; these do not
couple the loader to presentation operators. `connection_screen.tox` is the receiver plus
visual saved at `visuals/screensaver`, preserving the router's fallback path.
Both are embedded in the delivered TOE. Their TOX files are editable exports,
not extra external dependencies loaded during a cue.

Each screen's RGBA delay cache sizes itself from its active delay controls:
one current image plus the oldest requested frame. The saved RGB offsets
of -5, -3 and -1 therefore use six slots instead of thirty. The separate alpha
offset contributes only when **Alpha from All Delays** is off. This uses a
native Python parameter expression; hidden caches retain Always Cook off.

The shipped connection screen is saved with native **Reset Test** applied, so
opening it begins with unpassed checks. During a session, reset explicitly at
`visuals/screensaver/visual/Readiness` → **Reset Test**. Saving a TOE after checks
pass preserves that native latch state; reset before saving a fresh-start copy.
There is no added startup/frame callback. The original noise artwork is embedded
inside the programme screens; see [Connection Screen](ConnectionScreen.md).

Author both screens in `../dev/live_bw/envoy_live_bw.toe`, using its existing
Embody/Envoy integration. The loading screen is `project1/live_bw/loading_view`;
the connection screen is `project1/live_bw/visuals/screensaver`. Save their
components to `loading_view.tox` and `connection_screen.tox`. Standalone screen
projects and duplicate component exports have been retired.

Verification has covered the real 0→4 preparation sequence, loading/error
presentation, the hard cut to the connection screen, preview fallback, and
saved-master reopen. No hardware audio or Bitwig playback is triggered by
these checks. Historical captures remain recoverable in Git.

# Bitwig note input

Use Derivative's built-in **TouchDesigner** controller with the official TDBitwig
palette components. It communicates over OSC; the absence of a virtual MIDI port
does not indicate that this controller is disabled. Inspect the existing
controller/connection before proposing IAC buses or hardware MIDI routing.

## Authoring boundary

For the visual-control workflow, Elliot authors Bitwig's controls, remote pages,
and automation. The TD task reads those exposed controls through TDBitwig and
owns the external mapping into the visual. Do not operate Bitwig's UI, change
its parameters or routing, launch playback, or delegate its authoring unless
Elliot explicitly requests that again. An unavailable remote is a setup
limitation to report, not a reason to modify the controller or invent a bridge.

The reusable interface is a **named remote page backed by real parameters**.
An empty Chain with Macro-4 controls can expose them on a preset remote page
and travel as a Bitwig preset; TD reads it with bitwigRemotesDevice. Project
remotes use bitwigRemotesProject and need no track/device selection. Macros
hold the values; empty remote slots alone do not. Keep source discovery and
song-specific mapping outside the reusable visual.

The current visual-control example uses **CTRL → Chain → Perform** for
**Color / Camera** in remote slots 2–3. `LiveControls/ctrl_device`
reads these through bitwigRemotesDevice. **Edge On** reads **Project Perform
→ DrumWarp**, slot 8 (`par7/modVal`), through the existing
`LiveControls/BloomTiming/rippler_state` bitwigRemotesProject receiver.
The former device EdgeOn slot is disconnected. After a page is created, check TD's
selected page too: this receiver retained the stock Chain page (Wet Gain/Mix)
until Perform was selected. See [LiveControls](../raytk/LiveControls.md)
for the routing, public controls, and normalized selector values.

## Teachers Pet setup

The shared bitwigMain bridge lives in the shell. Song receivers and MidiHandler
live in MappedVisual, alongside its reusable visual. See the
[visual input contract](../raytk/PerformanceControls.md#continuous-input-contract).

```text
Bitwig: Drum Machine (Pitch)
    → bitwigMain (OSC connection)
    → drums_midi (official bitwigNote, pinned to the drum track)
    → MidiHandler/drums_note_mappings: 36 → ShakeEnvelope
    → MappedVisual/visual/ShakeEnvelope
    → shake_amount → ScreenShake.Amount
```

`bitwigMain` sends to Bitwig at `127.0.0.1:8088` and receives on port `9099` in
this setup. Both values must match the Bitwig controller's OSC settings. Its
`connected` output should be 1. These are the inspected session settings, not
requirements for every project.

`drums_midi` is the official `bitwigNote` component, with its Callback DAT
embedded as `note_callback`. The callback uses integer `pitch` (0–127) and
`velocity` (0–127) from `onNoteEvent`. Positive velocity routes through the
existing handler; velocity zero is ignored so note-off does not retrigger the
envelope. Its embedded implementation is `bitwig_note_callback.py` (not shipped in this
documentation change).
That source expects an `Expectedtrack` parameter and ignores events from a
different track. Older drum callbacks without this extra identity guard retain
their pinned receiver behavior.

The connection and callback references are relative. The mapping table retains
the existing handler's format and supports multiple targets and `_` wildcard
rows; see [MidiHandler](MidiHandler.md). Debug key **1** still triggers
`ShakeEnvelope` manually. Its output range and ADSR remain on the envelope.

## Track selection and reuse

Keep **Pin Track** enabled once the desired track is selected. An unpinned
receiver follows the Bitwig UI selection, which is unsuitable for a stable drum
route. `Prev Track` / `Next Track` navigate this receiver's cursor. Avoid the
separate `Select in Editor`, `Select in Mixer`, and visibility actions while
someone else is operating Bitwig.

Here, **cursor** means the controller API's track pointer, not mouse movement
or code editing. Selecting/pinning it uses the installed controller's built-in
behavior; it does not require modifying the controller extension.

For another song, select and pin that song's source track and edit the external
note mapping; the visual and its envelopes stay intact. Verify the displayed
Track name after changing projects or recreating a receiver.

The installed palette TOX files are wrappers containing the actual component
and help/icon resources. Place the inner `bitwigMain` and `bitwigNote` COMPs in
the working network. Keep one main connection per Bitwig session.

Official references: [TDBitwig](https://derivative.ca/UserGuide/TDBitwig),
[bitwigMain](https://derivative.ca/UserGuide/Palette:bitwigMain), and
[bitwigNote](https://derivative.ca/UserGuide/Palette:bitwigNote).

## Live verification — 2026-09-20

Connected to the existing Bitwig controller without UI or track-routing edits.
The pinned receiver reported `Drum Machine (Pitch)` and received live notes.
A real pitch-36 event at velocity 97 reached the callback; on the next TD frame,
both `shake_amount` and `ScreenShake.Amount` were 0.2. Temporary verification
instrumentation was removed. The receiver and handler had no errors or warnings.

## Additional live controls

See [LiveControls](../raytk/LiveControls.md) for external sliders, the MC202
receiver, audio-level mapping, and scene detection. Current audio routes use
Perm for slice and PermFilter for noise offset; the earlier PermRebounce route
is historical. MC202 is connected/pinned to `(202_postfx)`, receiving the **Fast**
device's output after the enabled **Notes** arpeggiator in `(202_trig)`.
Actual generated notes and calibrated bloom response were verified in playback.
Earlier Master scene-change, individual-fill, stop-row, and PermRebounce
post-fader meter tests passed. The exact original fader value was restored
afterward; that meter check does not verify the newer audio routes.

The native note receiver observes **track input before note effects**. For an
arpeggiator's output, subscribe to a separate instrument track whose note input
receives the desired final note-chain output. This requires Bitwig routing if
that receiving track does not already exist; do not silently substitute the
original sustained notes. [Derivative's example documentation](https://docs.derivative.ca/TDBitwig_Example_File#Managing_Note_Information)
describes this limitation and routing approach.

This differs from Ableton's TDA MIDI device, which can sit at the desired point
in a note-effects chain. For repeatable Bitwig setup, create a silent instrument
receiver with monitoring on, choose the exact desired device's note output as
its input, and pin `bitwigNote` to that receiver. Prove the tap with a sustained
source note and a known repeating note effect before wiring visual envelopes.
A track-output label or a device name such as “Arps” is not proof of processed
note delivery; some rhythmic instruments produce audio without emitting a
corresponding stream of MIDI notes.

`scene_events` uses bitwigClipSlot's `onPlayingClipChanged` pinned to **Master**,
with callbacks enabled after verification. The former drum-track source would
falsely trigger on fills. Master slot 0 → 1 fired autofocus; launching only an
individual drum fill left the Master slot unchanged and autofocus at zero.
Master `Scene Cue` clips occupy performance rows 1–16. Stop row 17 and independent
fill rows 18–21 remain empty on Master; launching the stop row did not trigger
autofocus. The installed TDBitwig scene-name bank
alone is not a scene-launch signal.
See [LiveControls](../raytk/LiveControls.md) for current status. The generic
row-change callback is embedded from `bitwig_scene_callback.py`; that source
is not shipped in this documentation change.
Its Required Source Track guard suppresses callbacks if the observer reconnects
to a different track; MC202 uses the same optional guard in its note callback.

## Effective device state through project remotes

The installed controller does not broadcast a device-enabled observer. To map
Fast arpeggiator state without modifying the controller, Project **Perform**
remote slot 3 (index 2), named **FastArp**, is bound directly to Fast **On/Off**.
The external [BloomTiming](../raytk/BloomTiming.md) component receives it through
the official bitwigRemotesProject and shortens the bloom envelope's release.

Enable **Read Modulated Values** and use `par2/modVal`. In actual Scene 10
playback the unmodulated `par2/val` stayed 0 while `par2/modVal` was 1 and Fast
was enabled by existing modulation. Do not infer effective state from the base
value or replace the existing musical modulation/automation with a new macro.

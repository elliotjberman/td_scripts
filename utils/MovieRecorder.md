# MovieRecorder

[MovieRecorder.tox](MovieRecorder.tox) records an incoming TOP image with audio.
It also outputs an image with a red recording indicator.

## User workflow

The user keeps MovieRecorder in their default TouchDesigner set so exporting
videos to post on Instagram is easy. It is an export/clip-making utility and
is never used for live sets. Preserve that separation when building templates
or performance networks.

Being present in the default set does not mean it should continuously record.
The historical TOX and the newer embedded Teachers Pet instance differ; the
sections below distinguish their settings.

## Repository TOX snapshot

- The `.` keyboard key feeds a Count CHOP configured to loop between 0 and 1.
  Its output, `record_on`, controls the Movie File Out TOP's record parameter.
- `in1` feeds `moviefileout1` directly. A separate branch feeds `recording_dot`
  and then `out1`, so the indicator is on the component's output image, outside
  the recorded image branch.
- The filename expression uses the project name with `.toe` removed, followed
  by `.mp4`.
- Saved recording settings include MPEG-4 video, ALAC audio, and 60 fps. These
  describe the file, not a tested or recommended configuration for this machine.

## Audio routing

The saved `monitor_outs` CHOP feeds the recorder's audio parameter. Its upstream
network contains audio-device inputs for Universal Audio monitor channels
`27:MON_L 28:MON_R` and Elektron Analog Four MKII `1:Main_L 2:Main_R`, routed
through a Math CHOP.

Those inputs are saved with ASIO settings. Verify the intended current audio
source, driver, channel routing, and output file location before recording on
another machine. Do not assume those historical device selections are current.

Evidence: user-confirmed export workflow and offline expansion of
`MovieRecorder.tox`. The `.` shortcut is established by the saved wiring rather
than a newly confirmed preference. No recording was started,
and device availability, codec support, and keyboard behavior were not live-tested.

## Teachers Pet: Apollo capture on macOS — 2026-09-26

The live project uses `apollo_monitor` (Audio Device In CHOP) → `monitor_outs`
→ Movie File Out TOP's Audio CHOP. Select **default / CoreAudio**, device
**Universal Audio Thunderbolt**, **By Index: 26 27**, and **Automatic** rate.
Those zero-based indices are **MON L / MON R** in the currently enumerated UAD
I/O map (channels 27/28 in one-based labels). Check the device's channel menu
if that map changes; historical ASIO channel strings are not portable to macOS.

This captures the Apollo monitor mix, including Bitwig when its output goes
there. It is not the TDBitwig audio-envelope meter, which carries control levels
rather than an audio waveform. The [UAD I/O Matrix](https://help.uaudio.com/hc/en-us/articles/25403673923220-I-O-Matrix-Settings-Panel)
defines which hardware/mix signals appear as driver inputs.

The old Math CHOP had Combine CHOPs off and the unavailable Elektron input
first. The live recorder bypassed that chain initially; the unused Elektron
input and Math CHOP were removed during the later consolidation.
Both monitor channels were verified with nonzero waveform samples (about 0.2
peak at inspection) at the final recorder audio input. Recording was left off;
no test movie was written and Bitwig was not operated. This updates the live TOE,
not the repository's historical MovieRecorder.tox snapshot.

### Matched audio/video buffering

The live recorder exposes **Recording → A/V Buffer Frames** (`Syncframes`),
initially **3 frames** (50 ms at 60 fps). This one parameter drives:

- `apollo_monitor` Buffer Length, in frames.
- `video_delay` Cache TOP Output Index as `-Syncframes`, using **Indices**.
- Cache Size as `Syncframes + 1`, including the current frame.

The recording branch is `in1` → `video_delay` → `moviefileout1`. The indicator
branch remains independent. Cache Step is 1, interpolation is off, and Always
Cook keeps the video history ready before recording. Movie File Out FPS follows
the component timeline rate so the frame units agree.

Use **Indices**, where 0 is the current image and -3 is three images earlier;
with Step 1 this is a three-frame delay. The Cache TOP's separate Frames unit
does not use the same zero-based indexing.

Change the public frame count to adjust both buffers together. This matches
their configured delay; hardware and DAW latency have not been measured with
a recorded sync test. The shared control was checked at 4 frames and restored
to 3; recording stayed off.

### MP4 audio compatibility

Use **AAC** audio for MP4 delivery. The actual `.19.mp4` recording contained
non-silent stereo MP3 audio, but Apple's AVFoundation reported no audio track.
The compressed H.264/AAC delivery copy retained all 2,023 video frames at 60 fps,
and AVFoundation recognized and decoded its audio. During the subsequent project
consolidation, the live recorder was switched to AAC and its unused Elektron
input and Math CHOP were removed. A silent player
alone therefore does not establish an input-routing failure: inspect the saved
file's streams and decoded signal before changing the CHOP route.

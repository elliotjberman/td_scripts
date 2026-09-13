# MovieRecorder

[MovieRecorder.tox](MovieRecorder.tox) records an incoming TOP image with audio.
It also outputs an image with a red recording indicator.

## User workflow

The user keeps MovieRecorder in their default TouchDesigner set so exporting
videos to post on Instagram is easy. It is an export/clip-making utility and
is never used for live sets. Preserve that separation when building templates
or performance networks.

Being present in the default set does not mean it should continuously record.
The user has not specified new export presets or audio routing in this discussion.

## Saved workflow

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

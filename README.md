# td_scripts
TouchDesigner scripts for VS Components

Component guides: [ScaledEnvelope](midi_handler_v2/ScaledEnvelope.md),
[ScreenShake](utils/ScreenShake.md), [TopVignette](utils/TopVignette.md),
[DefaultValue](utils/DefaultValue.md), and [MovieRecorder](utils/MovieRecorder.md).

See [TouchDesigner development notes](TOUCHDESIGNER_DEV_NOTES.md) before changing TD runtime, debug bridge, TDAbleton, or MIDI mapping workflow code.

`debug/codex_debugger/` is a separate TD debug bridge for executing short Codex-driven Python snippets; it is not part of the live Ableton hookup workflow.

See `ABLETON_LIVE_NOTES.md` for Ableton hardware/live-set conversion notes.
See `ABLETON_AUTOMATION_XML_NOTES.md` for the automation-copying handoff model.
See `live_set/README.md` for the setlist bridge and live-stack launcher.

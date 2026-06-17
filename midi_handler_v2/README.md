# MIDI Handler V2

Utilities for building Ableton MIDI source wrappers in TouchDesigner without the old TSV workflow.

## Install In A TD Project

Run this from the TouchDesigner Textport:

```python
exec(open(r"C:\Users\Elliot\td_scripts\midi_handler_v2\manager\bootstrap.py").read())
```

This creates or updates `AbletonHookupManager` in the current component. The manager is idempotent: rerunning bootstrap should update missing parameters/DATs without duplicating the main component.

## Main Workflow

- `Ctrl+Shift+M` opens the Ableton source picker.
- `Ctrl+E` opens the scaled-envelope creator.
- `Ctrl+Shift+P` opens the parameter binder for the last edited parameter.
- `Ctrl+Shift+K` opens the Ableton parameter source picker for `Global / Live_Macro`.
- Each source wrapper has an `Open Mapper` pulse for per-source note routing.

Mappings are stored on each source wrapper in `mappings_json`. Runtime routing should read that local mapping data instead of relying on external TSV files.

## Portable Path Contract

Visuals may be renamed or copied under a different parent, so MIDI v2 runtime paths must not assume `/project1`, `visuals_container`, or a component named `visual`.

- `source_callback` lives directly inside the MIDI source wrapper.
- `abletonMIDI.Callbackdat` should use `parent().op('source_callback').path`, so TDAbleton receives an absolute callback DAT path computed from the current wrapper location.
- Mapping targets in `mappings_json` are resolved from the source wrapper. A sibling envelope should be stored as `../BumpEnvelope`, not `BumpEnvelope` and not `/project1/...`.
- The runtime should not recursively search for mapping targets. If a stored relative path no longer resolves from the source wrapper, repair the mapping during setup/authoring.

## Direct Manager Calls

These are the agent-friendly entrypoints exposed by `AbletonHookupManagerExt`:

```python
manager.ext.AbletonHookupManagerExt.AbletonGlobalMacroParameters()
manager.ext.AbletonHookupManagerExt.AbletonParamPickerInfo()
manager.ext.AbletonHookupManagerExt.CreateAbletonParamSource("Global", "Live_Macro", "DrumVerb")
manager.ext.AbletonHookupManagerExt.CreateAndConnectAbletonParam("Global", "Live_Macro", "DrumVerb", op("math5"), output_name="chan1")
```

## Setup vs Performance

There are two different modes of concern:

- Setup/authoring: discover Ableton tracks, create source wrappers, add/select `TdaMIDI`, open mapping UI, create envelopes, and bind parameters.
- Performance runtime: receive MIDI callbacks, update `last_note` / `note_activity`, read existing `mappings_json`, and pulse mapped targets.

Keep live-performance work on the runtime path. Avoid broad Ableton discovery, UI scans, or debug bridges during performance unless explicitly enabled.

## Files

- `manager_extension.py`: TouchDesigner manager extension facade.
- `factory.py`: source wrapper creation and TDAbleton device setup.
- `source_extension.py`: source wrapper extension and MIDI routing entrypoint.
- `source_callback.py`: callback DAT loaded by `abletonMIDI`.
- `manager/`: source picker, mapping modal, hotkeys, name prompt, and envelope creation helpers.
- `ScaledEnvelope.tox`: vendored envelope component used by v2 creation.

## Debugging

The Codex debug bridge is intentionally outside this folder at `debug/codex_debugger/`. Do not add arbitrary Python execution or polling bridge behavior to the live Ableton hookup manager.

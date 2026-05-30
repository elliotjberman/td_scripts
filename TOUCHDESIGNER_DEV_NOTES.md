# TouchDesigner Development Notes

These are durable notes for future work on this repo.

## Runtime Safety

- Do not auto-start bridge polling or network calls from TouchDesigner's main thread on project load.
- Keep bridge/server integration explicit. Start it only from a user action, and keep HTTP timeouts short.
- Execute DATs should be inactive by default unless they are directly supporting an open UI.
- If TD freezes after adding a manager/component, first suspect an always-on Execute DAT or blocking Python call.
- Keep Codex-only debug execution separate from live-performance workflow components. Use `debug/codex_debugger/` for arbitrary Python probes, not the Ableton hookup manager.
- Do not blindly trust a project's `Home` parameter for debug tooling. Old `.toe` files can carry another machine/user path; prefer `Path.home()/td_scripts/debug/codex_debugger` or an explicit `CODEX_DEBUGGER_ROOT`.

## TDAbleton / AbletonMIDI

- Treat `abletonMIDI.par.Adddevice.pulse()` as asynchronous.
- Do not set raw menu labels into TDAbleton menu parameters before the menu contains the label.
- For TDA_MIDI creation, keep `Connect` off, pulse `Adddevice`, wait until `TdaMIDI` exists in the Device menu, select it, clear stale script errors, reinit if needed, then turn `Connect` back on.
- The red X can be caused by TDAbleton's first LOM/menu pass racing device creation; disable/re-enable works because it forces a later pass.

## Importlib Modules

- Keep TD runtime imports constrained and explicit. Avoid defensive lazy-import patterns that hide runtime state or load broad module graphs from hot UI paths.
- Python files loaded with `importlib.util.spec_from_file_location()` do not automatically have TD globals like `op`.
- Pass TD globals through the manager/source environment, or call through an object that can provide `op`.
- In callbacks stored as DAT text inside TD, `op()` is available. In external modules, assume it is not.
- Never store live module objects in operator storage. TD pickles storage on save, and module objects cannot be pickled.

## UI / Workflow Shape

- Mapping data is per MIDI source wrapper. The user-facing entrypoint should be on the source wrapper, not only on a global manager.
- The global manager can host shared modal UI, but it should edit a specific source's `mappings_json`.
- Source wrappers should expose an `Open Mapper` pulse.
- Keep setup/authoring behavior separate from performance runtime behavior.
- Setup/authoring can discover Ableton tracks, create wrappers, add `TdaMIDI`, build UI, create envelopes, and bind parameters.
- Performance runtime should only handle callbacks, maintain local note state, read existing mappings, and pulse mapped targets.
- Do not run broad Ableton discovery, UI scans, or debug bridge behavior during performance unless explicitly enabled.
- Note mapping UI should be sparse: show `*`, mapped notes, and notes that have actually fired. Do not show all 0-127 notes by default.
- Incoming notes need immediate visual feedback: insert the note if missing, show velocity, and flash/fade the row quickly.
- Multiple envelopes/route targets can map to the same note.
- "Go to envelope" style actions should select the target OP, make it current, and open its parameters. Keep this explicit in UI rather than overloading every row click.

## Visual Control Idioms

- For `ScreenShake.tox`, use envelope output range to control effect strength.
- Keep `Triangleamp` and `Noiseamp` as fixed relative mix controls. Do not put envelope expressions directly on them.
- Drive `screen_shake.par.Amount` from the envelope/null output, then tune intensity with the envelope's `Outputminimum`/`Outputmaximum`.

## TD Window/Text Focus

- For text entry modals, use `setFocus()` plus `setKeyboardFocus()`.
- Set `allowuishortcuts` off on editable text fields so TD network hotkeys do not leak while typing.
- Avoid synthetic mouse/focus tricks unless absolutely necessary; they have caused instability.
- TD `Par` truthiness can reflect its value; a parameter at `0` can behave falsey. Check `par is not None` when testing existence.
- Parameter Execute DAT uses the `valuechange` toggle for `onValueChange`, not `onvaluechange`.
- Parameter Execute DAT callbacks may not be enough for "last edited parameter" UX. Keep a small numeric-parameter snapshot for the tracked OP and diff it on frame updates.

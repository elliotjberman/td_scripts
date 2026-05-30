# Codex Debugger

Separate TouchDesigner debug bridge for Codex. This is intentionally not part of `midi_handler_v2` or the Ableton hookup manager.

## Install In TD

Run this once in the TouchDesigner Textport:

```python
exec(open(r"C:\Users\Elliot\td_scripts\debug\codex_debugger\bootstrap.py").read())
```

It creates `/project1/CodexDebugger`, resolves the debugger from `C:\Users\Elliot\td_scripts\debug\codex_debugger`, and uses a file-backed queue at:

```text
C:\Users\Elliot\td_scripts\debug\codex_debugger\queue
```

The component polls `queue/requests/*.json`, executes Python in TD, then writes `queue/responses/<id>.json`.

## Send Code From Codex

```powershell
python C:\Users\Elliot\td_scripts\debug\codex_debugger\client.py --eval "describe('/project1', 1)"
```

For statements, use `reply(...)` or assign `_result`:

```powershell
python C:\Users\Elliot\td_scripts\debug\codex_debugger\client.py --code "reply(selected('/project1'))"
```

Available TD-side helpers:

- `describe(path, depth=1)`
- `selected(root='/project1')`
- `find_by_tag(tag, root='/project1', depth=20)`
- `reply(value)`
- TD globals: `op`, `parent`, `me`, `ui`, `project`, `run`, `absTime`

## Safety

This executes arbitrary Python on TouchDesigner's main thread. Long-running or blocking code can freeze TD, so debug commands should be short and observational unless deliberately mutating the project.

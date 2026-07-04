# Live Set Launcher

The live-set bridge is now slug based. Ableton/the setlist server should publish
a stable string slug such as `bedroom`, `mixtape`, or `cities_box`, and each
TouchDesigner visual connected to `ableton_switcher` should have a custom string
parameter named `Songslug` with the same value.

`live_set/song_ids.tsv` is legacy transition data. The normal path no longer
depends on numeric song ids or TSV row order.

Run this once in the TouchDesigner Textport to add/migrate `Songslug` parameters
on the visuals already connected to `ableton_switcher`:

```python
exec(open("/Users/elliot/td_scripts/live_set/song_slug_params.py").read())
setup("/project1/ableton_switcher")
```

Existing values are kept. Missing values are inferred from operator names such as
`bedroom_visual_v2 -> bedroom`. If a visual is an external `.tox`, save the
external tox after confirming the parameter values so reloads keep them.

`live_set/ableton_watcher.py` looks for the current slug in an operator named
`song_slug`. A Text DAT containing `bedroom`, `td:bedroom`, or an Ableton scene
label like `[td:bedroom] Bedroom` will work. During migration only, it can still
fall back to the old `song_id` plus `songs` table if no slug source exists.

The Switch TOP index is derived at runtime from the actual connected input that
matches `Songslug`; no manual switch index or song number has to be maintained.

Use `launch_live_set.py` to bring up the live stack in show order:

1. start the setlist/server process;
2. open the master TouchDesigner project;
3. open Ableton.

Launch from the repo with the show dashboard:

```sh
./live_set/start_live_set.command
```

That opens the dashboard in your preferred terminal and runs
`live_set/live_set_dashboard.py`. The default terminal preference is `auto`,
which uses Ghostty when installed, then WezTerm when installed, and falls back to
macOS Terminal. Override it with `LIVE_SET_TERMINAL_APP`:

```sh
LIVE_SET_TERMINAL_APP=Terminal ./live_set/start_live_set.command
LIVE_SET_TERMINAL_APP=/Applications/Ghostty.app ./live_set/start_live_set.command
```

The launch wrapper runs the live set from the real `~/td_scripts` checkout by
default, even when the script was invoked from a Codex worktree. This keeps
TouchDesigner project-relative paths aligned with the machine setup. Override
that runtime checkout with `LIVE_SET_TD_SCRIPTS_ROOT`.

The dashboard launches the stack, shows server/TouchDesigner/Ableton heartbeats,
and renders the setlist with the current song highlighted when a current-song
source is configured. Startup leaves Ableton alone unless `LIVE_SET_ABLETON_SET`
or `--ableton-set` points at a specific `.als`. When TouchDesigner is down, `t`
relaunches the configured Big Kahuna TouchDesigner project. When Ableton is down,
`a` enters song selection mode; then use Up/Down to move the orange setlist
selection and Enter to launch that selected row. The
Ableton launch goes through the setlist server's `/load-set` endpoint when the
server is reachable, so the same process that opens the set also updates the
server-reported current row. Press `q` to close the dashboard without stopping
already-running apps. When Ableton is down, the server-reported song is shown as
the last-open song rather than the current song.

The wrapper auto-detects `~/setlist_manager` or a sibling `../setlist_manager`
repo. When that server exposes `GET /status`, the dashboard uses it for server
health and the actual `sets` order from `setlist.json`. If the server is alive
but the local `setlist.json` is missing or invalid, the server row shows that
configuration error directly. `serverPort` is optional for `setlist_manager`;
when it is omitted, the wrapper assumes the server's default `8000` port.

Use `LIVE_SET_STATUS_URL` to override the status endpoint, `LIVE_SET_SETLIST_URL`
for a separate setlist JSON endpoint, `LIVE_SET_SETLIST` for a JSON/TSV file, or
`LIVE_SET_CURRENT_SONG`, `LIVE_SET_CURRENT_SONG_FILE`, and
`LIVE_SET_CURRENT_SONG_URL` for temporary current-song overrides.

Check paths without starting the rig:

```sh
./live_set/check_live_set.command
```

For Spotlight/double-click launching, install
`live_set/macos/Start Live Set.app` into `~/Applications`. It runs
`~/td_scripts/live_set/start_live_set.command`, which opens Ghostty or falls back
to Terminal.

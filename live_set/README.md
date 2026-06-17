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

That opens Ghostty when it is installed and runs `live_set/live_set_dashboard.py`.
The dashboard launches the stack, shows server/TouchDesigner/Ableton heartbeats,
and renders the setlist with the current song highlighted when a current-song
source is configured. The Python setlist server's status JSON is the primary
source for both the actual setlist order and the current song:

```sh
export LIVE_SET_STATUS_URL=http://127.0.0.1:8000/status
```

If `LIVE_SET_STATUS_URL` is not set, the dashboard tries common local `/status`
ports and falls back to explicit overrides only. Use `LIVE_SET_SETLIST_URL` for a
separate setlist JSON endpoint, `LIVE_SET_SETLIST` for a JSON/TSV file, or
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

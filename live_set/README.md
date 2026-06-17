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

The launcher is intentionally hardcoded for the live rig:

- server directory: `~/setlist_manager`
- server command: `python3 server.py`
- TouchDesigner project: `big_kahuna/master_v2_no_tsv.toe`
- server log: `~/Library/Logs/td_scripts/live_set_server.log`

Launch from the repo with:

```sh
./live_set/start_live_set.command
```

Check paths without starting the rig:

```sh
./live_set/check_live_set.command
```

For Spotlight/double-click launching, install
`live_set/macos/Start Live Set.app` into `~/Applications`. It opens Terminal and
runs `~/td_scripts/live_set/start_live_set.command`, so failures stay visible.

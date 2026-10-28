# Bitwig live master

Open [live_bw.toe](live_bw.toe). The shell loads the mapped components in
[setlist.json](setlist.json), then warms all four selected visuals. The connection screen follows by a hard cut. Wait for **Set Ready** before performing.

Run **`vs_set`** from any directory: it opens this master fullscreen at 1080p on
the external display; **Enter** starts the audio/MIDI test; **Enter** stops it
cleanly and opens the Bitwig set in order. See [VS Set](VSSet.md) for offline
installation, controls and `--dry-run`. Passed checks stay green after the test stops. The warmed visuals
stay resident, and the existing engine-qualified Bitwig cue starts the show.
See [Programme Startup](ProgrammeStartup.md) for the two screens and controls.

| Exact Bitwig project name | Visual | Component |
| --- | --- | --- |
| `alien2_newsection_live` | Alien (RayTK) | `tracks/alien/mapped.tox` |
| `202arp3_newviz_live` | Teacher’s Pet | `tracks/teachers_pet/mapped.tox` |
| `resignation_live` | Resignation | `tracks/resignation/mapped.tox` |
| `college_town_live` | College Town | `tracks/college_town/mapped.tox` |

The shell contains the shared official Bitwig bridge, the
connection screen, loading display and native two-slot crossfade. Song components are
external dependencies. Keep them and the config available when moving the set.
The performance file contains no Embody, test loop or mock project selector.
Neither master embeds the main RayTK editor toolkit. Alien and College Town
carry their rendering operators, shader builders and controls inside their
mapped TOX files. Edit those scenes in their individual authoring projects,
where the RayTK palette and inspector remain available.

## Daily workflow

1. Edit the song’s standalone authoring project. Save that project, then **Save
   Component** on its mapped wrapper to the TOX listed above. Saving only the
   TOE does not update the exported TOX.
2. In the master, pulse **Load Set** on `project1/live_bw` → **Setlist**, or reopen
   the master. It rereads the config and components and repeats preparation.
3. To add a visual, export a mapped component following
   [the component contract](../VISUAL_STRUCTURE.md#mapped-component-contract-v1),
   register its project name, component name and path in `setlist.json`, and add
   its project name to `projects`. No song-specific master code is required.

Load Set interrupts show output with the loading view. Use it during preparation.
There is no file watcher or reload during a cue. Editing a TOX leaves the running
resident instance unchanged until the next Load Set or startup.

## Playing the set

Enable the shell’s `bitwigMain` and `bitwigSong` **Connect** controls, and install
the [Audio Engine Handoff controller](bitwig/README.md) alongside the official
TouchDesigner controller. Bitwig reports the selected tab's name even while
another tab is playing. The master therefore waits for the selected project's
audio engine to be active before accepting its visual cue.

Browsing an inactive tab holds the outgoing visual. Its MIDI and control input
may drop; this is a delay in visual switching, with no input cache. Activating
the new tab's engine starts the fade. The **Engine Handoff** page displays the
selected project, engine state, and whether the observer has replied.

The four visuals remain resident after startup. Changes use a two-second native
Timer/Cross fade, adjustable through **Crossfade Seconds**. Song receivers accept
input only when their host is ready and that exact song owns the audio engine.
Each receiver’s **Enable Receiver** retains its individual source enable choice.
Resignation’s PercRate clock is gated the same way. Artistic controls remain
inside the nested reusable visual.

The master displays **Current Project**, **Current Visual** and **Status**.
**Reset to Black** holds black until another request. Empty names select the
screensaver, unknown nonempty names select black, and disconnection holds the
accepted output. Only the latest queued request is retained during loading or
a fade. Duplicate names and broken components fail visibly.

`visuals` in the config registers available components; `projects` selects
proactive warmup. A registered visual omitted from `projects` can still play,
with possible first-use delay and an `unwarmed_fallback` log entry beside the TOE.
See [Setlist.md](Setlist.md) for readiness, errors and optional branch declarations.

## Authoring and validation

Open [envoy_live_bw.toe](../dev/live_bw/envoy_live_bw.toe) for master authoring
through its existing Embody/Envoy integration. Edit the loading and connection
screens there and save their canonical TOX exports beside this README.
The production `live_bw.toe` contains no agent integration.

All live song exports and their previews live under [tracks](tracks/README.md).
Continue editing individual visuals in their own scene authoring projects;
export each mapped wrapper directly to the path registered in `setlist.json`.

The four mapped exports render without the main RayTK editing toolkit. Both
master projects omit it. Window sizing reads the selected external display's
native dimensions, and the programme RGB delay uses only its required history.
Previous hardware/scene rehearsal and finite startup checks are recorded in
Git history. After a package/path change, check a fresh reopen reaches 4/4 Ready
and the expected output before a connected rehearsal.

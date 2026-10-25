# Live master development

Read [the runtime instructions](../../live_bw/AGENTS.md) before authoring.
`authoring/` contains finite builders/checks; `results/` preserves verification,
profiles, previews and review provenance. New experiments belong in `research/`.
The current editable master is `envoy_live_bw.toe`, with the existing
Embody/Envoy integration. The production master is `../../live_bw/live_bw.toe`.
Both screens are edited within this master and exported to the two canonical
TOXs in `live_bw/`. Individual tracks export directly to `live_bw/tracks/`.
Historical builders and fixtures are not release inputs. Do not recreate
standalone screen projects or duplicate component exports for routine edits.

- Keep benchmark fixtures, temporary DATs and frame callbacks out of the saved
  performance project. Clean them up and restore the canonical startup state.
- Follow current session authorization and the shared DAW lease for live Bitwig
  checks. Do not operate Bitwig's UI or playback merely to test a TD mapping.
  Keep local request tests and live engine-switch evidence clearly distinguished.
- Keep runtime inputs in `../../live_bw/`; write evidence here. Preserve earlier
  reports and label measurements by method/revision before replacing a baseline.
- Separate startup evidence from show performance: observe the loading/error
  view, declared branch warming, readiness, latest queued routing and save/reopen.
  Start measured crossfades only after Ready; do not expose warmup visuals or
  start a benchmark while preparation is running. Report startup cost separately.
- Check the loader/view boundary by replacing the view or its State reference
  without editing SetLoader. Loader failures must keep Ready off. A registered
  mapped project outside the warmed set remains selectable and logs its accepted
  fallback transition.
  Keep finite probes out of the production output network.
- `authoring/verify_reopen.py` checks an already reopened project. Its saved
  preference snapshot is provenance for the original run; capture the current
  save-prompt value before any new authoring run that changes it.

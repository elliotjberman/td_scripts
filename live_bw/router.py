"""Event routing; native CHOPs fade resident, demand-driven visual outputs."""

from datetime import datetime, timezone
import json
from pathlib import Path


class Router:
    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.generation = 0
        self.busy = False
        self.handoff = False
        self.current = None
        self.incoming = None
        self.pending = None
        self.active_slot = 0
        self.notice = None
        self.initialized = False
        self.event_log = Path(project.folder) / 'live_bw_events.jsonl'

    def onInitTD(self):
        # SetLoader owns finite startup work; routing stays gated until Loaded.
        self.ownerComp.par.Ready = False
        self.ownerComp.par.Loading = True
        self.ownerComp.par.Loadstatus = 'Reading setlist'
        self.ownerComp.par.Engineknown = False
        self.ownerComp.par.Engineactive = False
        self.ownerComp.par.Observedproject = ''
        self.Reset(initializing=True)
        self._status('LOADING: preparing setlist')

    def onDestroyTD(self):
        self.generation += 1

    def Loaded(self):
        project, self.pending = self.pending, None
        self.ownerComp.par.Pendingproject = ''
        if project is None and self.startup_cancelled:
            self._status('BLACK: set ready, waiting for a project')
            return
        if project is None:
            project = ''
        self.RequestProject(project, immediate=not project)
        self.ProjectChanged()

    def _status(self, text):
        self.ownerComp.par.Status = text

    def _hold(self, text):
        self.pending = None
        self.ownerComp.par.Pendingproject = ''
        self.notice = text
        self._status(text)

    def _visual(self, project):
        if not project:
            return self._mapped_visual('visuals/screensaver')
        table = self.ownerComp.op('song_map')
        if [cell.val for cell in table.row(0)] != ['project_name', 'visual']:
            raise ValueError('song_map requires project_name and visual headers')
        routes = {}
        for row in table.rows()[1:]:
            name, path = [cell.val for cell in row]
            if not name.strip() or not path.strip():
                raise ValueError('song_map rows require a project name and visual path')
            if name in routes:
                raise ValueError('Duplicate Bitwig project name in song_map: ' + name)
            routes[name] = self._mapped_visual(path)
        return routes.get(project)

    def _mapped_visual(self, path):
        visual = self.ownerComp.op(path)
        if visual is None or visual.parent() != self.ownerComp.op('visuals'):
            raise ValueError('Missing mapped visual in visuals: ' + path)
        if visual.op('out1') is None or visual.op('out1').family != 'TOP':
            raise ValueError('Mapped visual requires an out1 TOP: ' + path)
        return visual

    def Reset(self, initializing=False):
        self.generation += 1
        self.startup_cancelled = bool(self.ownerComp.par.Loading.eval()) and not initializing
        self.busy = self.handoff = False
        self.current = self.incoming = self.pending = None
        self.notice = None
        self.active_slot = 0
        self.ownerComp.op('slot_a').par.top = 'black'
        self.ownerComp.op('slot_b').par.top = 'black'
        self.ownerComp.op('timer').par.initialize.pulse()
        self.ownerComp.par.Destination = 1
        for name in ['Currentproject', 'Currentvisual', 'Requestedproject', 'Pendingproject']:
            self.ownerComp.par[name] = ''
        self._status('BLACK: waiting for a project')
        self.initialized = True

    def RequestProject(self, project, immediate=False):
        if not self.initialized:
            raise RuntimeError('Router is initializing; wait for its native reset')
        project = str(project)
        if not project.strip():
            project = ''
        self.ownerComp.par.Requestedproject = project
        if not bool(self.ownerComp.par.Ready.eval()):
            if not bool(self.ownerComp.par.Loading.eval()):
                raise RuntimeError('Set is not ready: ' + self.ownerComp.par.Loadstatus.eval())
            self.pending = project
            self.ownerComp.par.Pendingproject = project
            self._status('LOADING: queued ' + (project or 'screensaver'))
            return
        try:
            visual = self._visual(project)
        except Exception as error:
            self._hold('MAPPING ERROR: ' + str(error))
            raise
        self.notice = None
        if self.busy or self.handoff:
            self.pending = project
            self.ownerComp.par.Pendingproject = project
            return
        if visual == self.current:
            self.ownerComp.par.Currentproject = project
            self._settled_status(project, visual)
            return
        if visual is not None:
            nested = visual.op('content/visual') or visual.op('visual')
            if not visual.allowCooking or (nested is not None and not nested.allowCooking):
                self._hold('VISUAL ERROR: Allow Cooking is off: ' + visual.path)
                raise ValueError(self.notice)
            errors = visual.errors(recurse=True) or visual.scriptErrors(recurse=True)
            if errors:
                self._status('VISUAL ERROR: ' + errors)
                raise RuntimeError(errors)
        unwarmed = bool(project) and visual is not None and not any(
            visual == job[0] for job in self.ownerComp.ext.SetLoader.jobs)
        if unwarmed:
            self._record_unwarmed(project, visual)
        if immediate:
            # Startup's loading gate already hides both slots. Present the
            # connection screen immediately; song cues still fade.
            self.ownerComp.op('timer').par.initialize.pulse()
            self.ownerComp.op('slot_a').par.top = 'black' if visual is None else 'visuals/' + visual.name + '/out1'
            self.ownerComp.op('slot_b').par.top = 'black'
            self.ownerComp.par.Destination = 1
            self.active_slot = 0
            self.current = visual
            self.ownerComp.par.Currentproject = project
            self.ownerComp.par.Currentvisual = '' if visual is None else visual.name
            self._settled_status(project, visual)
            return
        self.incoming = visual
        self.incoming_project = project
        target_slot = 1 - self.active_slot
        selector = self.ownerComp.op('slot_b' if target_slot else 'slot_a')
        selector.par.top = 'black' if visual is None else 'visuals/' + visual.name + '/out1'
        self.ownerComp.op('timer').par.length = self.ownerComp.par.Crossfadesecs.eval()
        self.ownerComp.op('timer').par.initialize.pulse()
        self.ownerComp.par.Destination = target_slot
        self.busy = True
        status = 'FADING: ' + (project or 'screensaver (no project)')
        if visual is None:
            status += ' (unmapped → black)'
        elif unwarmed:
            status += ' (not preloaded)'
        self._status(status + ('; ' + self.notice if self.notice else ''))
        self.ownerComp.op('timer').par.start.pulse()

    def _record_unwarmed(self, project, visual):
        event = {'time_utc': datetime.now(timezone.utc).isoformat(),
                 'event': 'unwarmed_fallback', 'project': project,
                 'visual': visual.name}
        try:
            with self.event_log.open('a', encoding='utf-8') as log:
                log.write(json.dumps(event) + '\n')
        except OSError as error:
            # A logging failure must remain visible without dropping the cue.
            self.notice = 'EVENT LOG ERROR: ' + str(error)

    def _settled_status(self, project, visual):
        if not project:
            status = 'SCREENSAVER: no project'
        elif visual is None:
            status = 'UNMAPPED: ' + project + ' → black'
        else:
            status = 'READY: ' + project
        self._status(self.notice or status)

    def Finish(self):
        if not self.busy:
            return
        self.current = self.incoming
        self.active_slot = int(self.ownerComp.par.Destination.eval())
        self.busy = False
        self.ownerComp.par.Currentproject = self.incoming_project
        self.ownerComp.par.Currentvisual = '' if self.current is None else self.current.name
        self._settled_status(self.incoming_project, self.current)
        # Let the final Timer fraction reach the image before retiring its old input.
        self.handoff = True
        run('args[0].ApplyPending(args[1])', self, self.generation, delayFrames=1)

    def ApplyPending(self, generation):
        if not self.ownerComp.valid or self.ownerComp.ext.Router is not self or generation != self.generation:
            return
        self.ownerComp.op('slot_a' if self.active_slot else 'slot_b').par.top = 'black'
        self.handoff = False
        project, self.pending = self.pending, None
        self.ownerComp.par.Pendingproject = ''
        if project is not None:
            self.RequestProject(project)

    def ProjectChanged(self):
        if not self.initialized:
            return
        if not bool(self.ownerComp.op('connections')['ready']):
            self.ownerComp.par.Engineknown = False
            self.ownerComp.par.Engineactive = False
            self._hold('DISCONNECTED: holding current visual')
            return
        # Re-query on connection/tab changes, including when TD starts after Bitwig.
        self.ownerComp.op('engine_request').sendOSC('/live/engine/get', [1])
        self._route_engine()

    def EngineState(self, project, active):
        if not isinstance(project, str) or not isinstance(active, bool):
            raise ValueError('Engine state requires a project name and boolean')
        self.ownerComp.par.Observedproject = project
        self.ownerComp.par.Engineactive = active
        self.ownerComp.par.Engineknown = True
        self._route_engine()

    def _route_engine(self):
        owner = self.ownerComp
        if not self.initialized or not bool(owner.op('connections')['ready']):
            return
        if not owner.par.Engineknown.eval():
            self._hold('WAITING: audio engine observer')
        elif not owner.par.Engineactive.eval():
            self._hold('HOLD: selected project audio engine is inactive')
        elif owner.par.Observedproject.eval() != owner.parent().op('bitwigSong').par.Projectname.eval():
            self._hold('WAITING: project identity settling')
        else:
            self.RequestProject(owner.par.Observedproject.eval())

"""Finite set warmup and loading state; presentation observes the public parameters."""

import json
from pathlib import Path
import re


class SetLoader:
    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.generation = 0
        self.jobs = []
        self.index = 0
        self.branch = 0
        self.remaining = 0
        self.warmed = []

    def onInitTD(self):
        self.generation += 1
        run('args[0]._DeferredStart(args[1])', self, self.generation, delayFrames=3)

    def onDestroyTD(self):
        self.generation += 1

    def _active(self, generation):
        return (self.ownerComp.valid and self.ownerComp.ext.SetLoader is self
                and generation == self.generation)

    def _later(self, action, frames=1):
        run('getattr(args[0], args[1])(args[2])', self, action,
            self.generation, delayFrames=frames)

    def _DeferredStart(self, generation):
        if self._active(generation):
            self.Start()

    def Start(self):
        owner = self.ownerComp
        self.generation += 1
        owner.par.Ready = False
        owner.par.Loading = True
        owner.ext.Router.Reset(initializing=True)
        self.jobs = []
        self.index = self.branch = self.remaining = 0
        self.warmed = []
        owner.par.Loadcount = owner.par.Loadtotal = 0
        owner.par.Loadvisual = ''
        owner.par.Loadstatus = 'Reading setlist'
        # Give the loading frame a presentation opportunity before any warmup.
        self._later('_Prepare', frames=2)

    @staticmethod
    def _unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate set file key: ' + key)
            result[key] = value
        return result

    def _catalog(self):
        owner = self.ownerComp
        path = Path(owner.par.Setfile.eval())
        if not path.is_absolute():
            path = Path(project.folder) / path
        data = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=self._unique_object)
        if not isinstance(data, dict):
            raise ValueError('setlist must be a JSON object')
        registry = data.get('visuals')
        if not isinstance(registry, dict) or not registry:
            raise ValueError('setlist visuals must be a nonempty object')
        entries, names = [], set()
        for project_name, spec in registry.items():
            if not project_name.strip() or not isinstance(spec, dict):
                raise ValueError('Each visual requires a project name and component specification')
            name = spec.get('name', '')
            if (not isinstance(name, str) or not re.fullmatch('[a-z][a-z0-9_]*', name)
                    or name == 'screensaver' or name in names):
                raise ValueError('Invalid or duplicate visual name: ' + str(name))
            filename = spec.get('tox')
            if not isinstance(filename, str) or not filename.strip():
                raise ValueError('Missing tox file for ' + name)
            source = (path.parent / filename).resolve()
            if source.suffix != '.tox' or not source.is_file():
                raise ValueError('Missing TOX: ' + str(source))
            for library, version in spec.get('requires', {}).items():
                if library != 'raytk':
                    raise ValueError('Unknown shared library: ' + library)
                toolkit = owner.parent().op('raytk')
                if toolkit is None or toolkit.par.Raytkversion.eval() != version:
                    raise ValueError(name + ' requires RayTK ' + version)
            names.add(name)
            entries.append((project_name, name, source))
        projects = data.get('projects')
        if (not isinstance(projects, list) or not projects
                or any(not isinstance(name, str) or name not in registry for name in projects)):
            raise ValueError('projects must be a nonempty list of registered project names')
        if len(set(projects)) != len(projects):
            raise ValueError('setlist has duplicate project names')
        self.projects = projects
        self.imports = iter(entries)
        owner.op('setlist').text = json.dumps(data, indent=2)

    def _import(self, project_name, name, source):
        owner = self.ownerComp
        bank = owner.op('visuals')
        host = bank.create('baseCOMP', name)
        host.nodeX, host.nodeY = 0, -120 * (len(bank.children) - 1)
        page = host.appendCustomPage('Host')
        for kind, parameter in [('OP', 'Bridge'), ('Int', 'Resolutionw'),
                                ('Int', 'Resolutionh'), ('Str', 'Home'),
                                ('Str', 'Expectedproject'), ('Toggle', 'Projectactive')]:
            getattr(page, 'append' + kind)(parameter)
        host.par.Bridge.expr = "parent.LiveShell.op('bitwigMain')"
        for parameter in ('Resolutionw', 'Resolutionh', 'Home'):
            host.par[parameter].expr = 'parent().par.' + parameter
        host.par.Expectedproject = project_name
        host.par.Projectactive.expr = (
            "parent.LiveMaster.par.Ready.eval() and "
            "bool(parent.LiveMaster.op('connections')['ready']) and "
            "parent.LiveMaster.par.Engineknown.eval() and "
            "parent.LiveMaster.par.Engineactive.eval() and "
            "parent.LiveMaster.par.Observedproject.eval() == me.par.Expectedproject.eval() and "
            "parent.LiveShell.op('bitwigSong').par.Projectname.eval() == me.par.Expectedproject.eval()")
        try:
            content = host.loadTox(str(source))
            content.name = 'content'
            if content.par['Interfaceversion'] is None or content.par.Interfaceversion.eval() != 1:
                raise ValueError('Mapped component requires Interfaceversion 1: ' + str(source))
            for parameter in ('Bridge', 'Resolutionw', 'Resolutionh', 'Home', 'Expectedproject', 'Projectactive'):
                p = content.par[parameter]
                if (p is None or str(p.mode) != 'ParMode.EXPRESSION'
                        or p.expr != 'parent().par.' + parameter):
                    raise ValueError('Mapped component must inherit host ' + parameter + ': ' + str(source))
            if content.op('visual') is None or content.op('out1') is None or content.op('out1').family != 'TOP':
                raise ValueError('Mapped component requires visual and out1 TOP: ' + str(source))
            if not content.allowCooking or not content.op('visual').allowCooking:
                raise ValueError('Mapped component and visual must allow cooking: ' + str(source))
            content.nodeX = content.nodeY = 0
            output = host.create('outTOP', 'out1')
            output.nodeX, output.nodeY = 180, 0
            output.inputConnectors[0].connect(content.outputConnectors[0])
            self._check(host)
        except Exception:
            host.destroy()
            raise
        owner.op('song_map').appendRow([project_name, 'visuals/' + name])

    def _Import(self, generation):
        if not self._active(generation):
            return
        try:
            entry = next(self.imports, None)
            if entry is not None:
                self.ownerComp.par.Loadstatus = 'Loading ' + entry[1]
                self._import(*entry)
                self._later('_Import')
                return
            self._plan()
            self.ownerComp.par.Loadtotal = len(self.jobs)
            self._announce()
        except Exception as error:
            self.Fail(str(error))
            raise

    def _plan(self):
        owner = self.ownerComp
        wrappers = []
        for project in self.projects:
            wrapper = owner.ext.Router._visual(project)
            if wrapper is None:
                raise ValueError('Unmapped setlist project: ' + project)
            if wrapper not in wrappers:
                wrappers.append(wrapper)
        for wrapper in wrappers:
            visual = wrapper.op('content/visual') or wrapper.op('visual')
            if not wrapper.allowCooking or (visual is not None and not visual.allowCooking):
                raise ValueError('Allow Cooking must stay on: ' + wrapper.path)
            tops = []
            table = visual.op('warmup_tops') if visual is not None else None
            if table is not None:
                if table.type != 'table' or [cell.val for cell in table.row(0)] != ['top']:
                    raise ValueError('warmup_tops requires one top column: ' + table.path)
                for row in table.rows()[1:]:
                    path = row[0].val
                    top = visual.op(path) if path and not path.startswith('/') else None
                    if (top is None or top.family != 'TOP'
                            or not top.path.startswith(visual.path + '/')):
                        raise ValueError('Invalid relative warmup TOP: ' + visual.path + '/' + path)
                    if top not in tops:
                        tops.append(top)
            self.jobs.append((wrapper, tops + [wrapper.op('out1')]))

    def _Prepare(self, generation):
        if not self._active(generation):
            return
        try:
            self._catalog()
            for child in self.ownerComp.op('visuals').children:
                if child.name != 'screensaver':
                    child.destroy()
            table = self.ownerComp.op('song_map')
            table.clear()
            table.appendRow(['project_name', 'visual'])
            self._later('_Import')
        except Exception as error:
            self.Fail(str(error))
            raise

    def _announce(self):
        owner = self.ownerComp
        wrapper = self.jobs[self.index][0]
        owner.par.Loadvisual = wrapper.name
        owner.par.Loadstatus = 'Warming ' + wrapper.name
        self.branch = 0
        self.remaining = 60
        self._later('_Warm')

    @staticmethod
    def _check(wrapper):
        errors = [wrapper.errors(recurse=True), wrapper.scriptErrors(recurse=True)]
        errors = [str(error) for error in errors if error]
        if errors:
            raise RuntimeError(wrapper.path + ': ' + '; '.join(errors))

    def _Warm(self, generation):
        if not self._active(generation):
            return
        try:
            wrapper, tops = self.jobs[self.index]
            if self.branch < len(tops):
                top = tops[self.branch]
                top.cook(force=True)
                self.warmed.append(top.path)
                self.branch += 1
            else:
                wrapper.op('out1').cook(force=True)
                self.remaining -= 1
                if self.remaining == 0:
                    self._check(wrapper)
                    self.index += 1
                    self.ownerComp.par.Loadcount = self.index
                    if self.index < len(self.jobs):
                        self._announce()
                    else:
                        self.remaining = 10
                        self.ownerComp.par.Loadvisual = ''
                        self.ownerComp.par.Loadstatus = 'Settling'
                        self._later('_Settle')
                    return
            self._later('_Warm')
        except Exception as error:
            self.Fail(str(error))
            raise

    def _Settle(self, generation):
        if not self._active(generation):
            return
        try:
            self.remaining -= 1
            if self.remaining:
                self._later('_Settle')
                return
            for wrapper, _ in self.jobs:
                self._check(wrapper)
            owner = self.ownerComp
            owner.par.Loadstatus = 'Ready'
            owner.par.Loading = False
            owner.par.Ready = True
        except Exception as error:
            self.Fail(str(error))
            raise
        # A routing refusal must not invalidate a successfully prepared set.
        owner.ext.Router.Loaded()

    def Fail(self, message):
        self.generation += 1
        owner = self.ownerComp
        owner.par.Ready = owner.par.Loading = False
        owner.par.Loadstatus = 'ERROR: ' + message

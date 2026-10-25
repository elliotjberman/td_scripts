# Visual component structure

The reusable model agreed for Teachers Pet, 2026-09-26:

```text
Shell .toe — authoring template or master live set
├── Shared DAW bridge (bitwigMain / Ableton equivalent)
├── MappedVisual .tox
│   ├── Song receivers, source calibration, MIDIHandler
│   ├── LiveControls ── named CHOP channels ──┐
│   ├── visual .tox ◀───────────────────────┘
│   │   ├── ControlInputs: defaults + input + local ADSR → Bind CHOP
│   │   ├── Public behavior controls ↔ bound channels
│   │   ├── Envelopes ← public trigger events
│   │   └── Geometry, rendering, post-processing → out1
│   └── out1
└── Output, shared resolution/Home, authoring tools
```

The **shell** owns connection infrastructure. The **mapped wrapper** owns which
song sources control which visual inputs, including audio input calibration.
The **visual** owns artistic ranges, palettes, camera poses, smoothing, envelopes,
and rendering. Keep cohesive controls on their existing behavior components;
the visual parent retains only the template contract. This is a starting
structure, not a requirement to wrap every small chain in another component.

## Continuous values and local operation

Use named CHOP input channels with documented units. A native Bind CHOP matches
by name, with pickup off. Bind each editable public parameter using a short
Python bind expression such as `op('ControlInputs/current')['palette']`.
Editing that parameter or receiving a changed input updates the same state;
the binding stays intact. Native CHOPs downstream perform ranges and smoothing.
Keep callbacks for actions, not copying continuous values.

This is **last change wins**, independently per channel. Local controls are
debug tools for disconnected use; moving automation can immediately reclaim
control. No Local/Mapped mode switch or pickup framework is needed. A repeated
identical input value is not a new change. Publish only enabled, ready source
channels; a deliberately disconnected source is omitted, not replaced with zero.
The visual keeps its current value until a local or incoming change. A fresh
unconnected visual starts from its saved defaults. Missing paths or invalid
mapping references must still produce visible errors.

For menu parameters, event Python should assign `menuIndex`; the bound channel
is numeric. Keyboard Next/Toggle actions write the same public parameters.
Notes go through MIDIHandler to public Trigger pulses; other discrete actions
likewise target public interfaces.

## Portable exports

- The visual must not reach outward for song receivers or LiveControls. Keep
  its callback/shader/mapping text embedded and its internal references relative.
- Expose shared host dependencies on the wrapper. Teachers Pet has one **Bridge**
  OP parameter; all receivers use `parent.MappedVisual.par.Bridge`. That is a
  parent shortcut, so renamed and nested instances resolve their own wrapper.
- Carry mapping tables inside the mapped TOX. Do not require a checkout or
  loose TSV file for performance. Avoid global shortcuts on per-instance nodes.
- Before claiming reuse, load the visual under a renamed parent with no song
  input; check local controls and output. Load the mapped wrapper, set its host
  references, and check its targets. This is a focused boundary check, not a new
  testing framework.

Teachers Pet's channel contract and current files are in
[PerformanceControls](raytk/PerformanceControls.md) and
[LiveControls](raytk/LiveControls.md). Its host provides Resolutionw/Resolutionh
and Home to the visual. The mapped wrapper inherits the template's width/height
and Home; rebind these when loading into a differently shaped host. RayTK editing
tools belong in individual scene authoring shells. The current Alien and College
Town mapped exports render without the main RayTK toolkit, so neither live-set
master embeds it. Embody stays outside exports.

## Mapped component contract v1

New live-set visuals must be independently authorable and exported as mapped
TOX components. The master imports them from `live_bw/setlist.json` at startup
or explicit **Load Set**, then keeps them resident. Do not bake song copies or
per-song installation code into the master. There is no performance file watcher.

A mapped component contains its song receivers/mappings, a nested `visual`, and
an `out1` TOP. It has parent shortcut **MappedVisual**, integer
**Interfaceversion = 1**, and these host inputs:

| Parameter | Type | Meaning |
| --- | --- | --- |
| Bridge | OP | Shared official `bitwigMain` |
| Resolutionw / Resolutionh | Int or Float | Output pixels |
| Home | Str | Host home folder, for existing template utilities |
| Expectedproject | Str | Exact Bitwig project name |
| Projectactive | Toggle | Host is ready and this song owns the connected engine |

Each input uses the expression `parent().par.<Name>` in expression mode. The
master creates this host before importing the TOX. The standalone authoring
shell provides the same parameters; it owns the bridge and determines its active
project from the bridge’s live song identity. The master owns only host wiring
and the output connection, and does not rewrite component internals after import.

Receivers use `parent.MappedVisual.par.Bridge`, and Connect requires both the
receiver’s own enable choice and `parent.MappedVisual.par.Projectactive`.
Discrete transport clocks must also stop when Projectactive is false. Preserve
intentional disabled receivers. Never save synthetic note loops or mock input
controls in performance exports. Named CHOPs and public MIDIHandler actions
remain the reusable visual boundary; this contract does not relocate art controls.

Save the authoring TOE and export the mapped wrapper to its registered TOX after
editing. Keep mapping tables, scripts and shaders embedded in the component,
with relative references. Declare external assets and shared library versions;
The current RayTK 0.46 scenes carry their rendering dependencies in their mapped
exports; the main editor toolkit is not a live-master dependency. Embody remains outside the export.
Test imports under renamed/nested hosts with real controls, errors and output,
then verify Load Set consumes the changed export without changing the master.

## Resident visuals and idle processing

Preload components and warm their declared branches before performance. Keep
Allow Cooking enabled; let the master's connected outputs demand rendering.
Both outputs may cook during a crossfade. Once an output is retired, its TOP
and POP processing must become idle, including nested branches whose final
output is no longer cooking.

Use passive Info readers for dimensions and compile diagnostics. Leave Always
Cook off on image caches and POP histories when visible output demand can drive
them. Preserve their history length and artistic settings. An intentional
independent processor needs an explicit reason and an inactive-song policy;
do not add per-frame Python or a master-specific internal rewrite to stop it.
Discrete song clocks follow Projectactive. Continuous controls retain their
last valid values; local animation and envelope releases can continue while
the outgoing image remains visible.

Verify an all-family cook census after fade-out, allowing capture/UI demand to
settle. Check returning to each visual as well as leaving it. Static allocation
is not evidence of ongoing CPU/GPU work, and checking only final TOP cook
counters is insufficient.

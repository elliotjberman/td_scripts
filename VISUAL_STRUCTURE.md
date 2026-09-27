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
and Home; rebind these when loading into a differently shaped host. RayTK 0.45
remains a shared toolkit dependency in the shell; Embody stays outside exports.

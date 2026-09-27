# RayTK component guides

These guides describe the components embedded in the Teachers Pet visual and
its song wrapper. They document public controls, signal flow, dependencies,
and recorded verification. Values are examples from that patch, not universal
presets. No runtime code or new TOX assets are shipped with these guides.

The current local project is
`Documents/touchdesigner/2026/raytk1/teachers_pet_live_demo.toe`.
Its reusable visual is `/project1/MappedVisual/visual`; song receivers and
MidiHandler sit beside it in `MappedVisual`. The shell supplies RayTK 0.45 and
the shared Bitwig bridge. Resolution inherits from the host.

## Visual controls

Start with [PerformanceControls](PerformanceControls.md) for the public interface,
local keys, and named CHOP input contract. Public controls remain editable when
no song is connected; a later changed input takes control of that channel again.

| Area | Guides |
| --- | --- |
| Camera | [CameraMoves](CameraMoves.md), [CameraSway](CameraSway.md), [Autofocus](Autofocus.md) |
| Image and depth | [EdgeMix](EdgeTreatment.md), [PostProcessing](PostProcessing.md) |
| Palettes and bloom | [ColorLookup](ColorLookup.md), [BloomCalibration](BloomCalibration.md), [BloomTiming](BloomTiming.md), [BloomMask](BloomMask.md) |
| Geometry and noise | [SliceControl](SliceControl.md), [NoiseAmplitude](NoiseAmplitude.md), [NoiseScale](NoiseScale.md), [NoiseOffsetEnvelope](NoiseOffsetEnvelope.md), [PlaneNoiseEnvelope](PlaneNoiseEnvelope.md) |
| Surface overlay | [Scanner](Scanner.md) |

Use the shared [ScaledEnvelope guide](../midi_handler_v2/ScaledEnvelope.md) for
naming, unique debug keys, ADSR controls, and layout. [TopCrossfade](../utils/TopCrossfade.md)
describes the two-slot transition used by ColorLookup.

## Song adapters

[LiveControls](LiveControls.md) lists the current source routes and input readiness
behavior. [AudioSlice](AudioSlice.md) conditions an audio meter;
[SpeedClock](SpeedClock.md) converts song position into envelope triggers.
[MidiHandler](../midi_handler/MidiHandler.md) routes note events, and
[Bitwig input](../midi_handler/Bitwig.md) explains the official OSC receivers.

Track names and remote slots belong to this example wrapper. Reuse the visual by
supplying its named channels and public events from another wrapper.

## Availability and older experiments

Export the current live visual or mapped wrapper when reusing it. Their local
exports are `teachers_pet_visual.tox` and `teachers_pet_mapped.tox`, beside the
TOE. Embedded callback and shader filenames mentioned in the guides identify
implementation DATs; those sources are not included in this documentation PR.
Older individual TOX snapshots may predate the documented public interfaces.

[CellBoxes](CellBoxes.md) is a parked experiment, and
[NoiseDrift](NoiseDrift.md) is historical: it was removed from the live visual.
They are not required for the current control routes.

Use Embody/Envoy for live inspection and authoring, following the repository's
[connection guidance](../AGENTS.md#agent-connection-and-verification).

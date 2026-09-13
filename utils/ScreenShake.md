# ScreenShake

[ScreenShake.tox](ScreenShake.tox) generates CHOP channels named `x` and `y`
for shake motion. It supplies motion values; it does not take an image input
and apply a transform itself. Connect its channels to the intended visual's
position/translation controls.

## Controls

| Parameter | Role |
| --- | --- |
| `Amount` | Overall shake scaling; the usual envelope-driven control. |
| `Triangleamp` | Relative amplitude of the triangle-wave motion. |
| `Noiseamp` | Relative amplitude of the noise motion. |

The saved network adds two triangle LFOs and two-channel noise by channel name,
then applies the `Amount`-controlled range through a Math CHOP and outputs `out1`.
The saved LFO frequencies are 12, with the Y LFO phase set to 0.25.

## Established workflow

The user uses ScreenShake heavily. In 2D work it can drive image position; in
3D work it can drive camera position. Choose the target based on the visual
being built rather than assuming a single kind of position control.

The repository's [development notes](../TOUCHDESIGNER_DEV_NOTES.md) specify:

1. Drive `Amount` from a [ScaledEnvelope](../midi_handler_v2/ScaledEnvelope.md)
   or its reference Null CHOP.
2. Tune effect strength with the envelope's `Outputminimum`/`Outputmaximum`.
3. Keep `Triangleamp` and `Noiseamp` fixed as relative mix controls instead of
   putting envelope expressions on them.

The saved `Amount` expression references `op('shake_amount')[0]`. Point it at
the intended local envelope/output when reusing the component.

Evidence: user-confirmed usage, offline expansion of `ScreenShake.tox`, and
existing development notes. No preferred numeric starting strength was supplied;
no live motion or output range was tested in this documentation pass.

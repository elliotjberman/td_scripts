# TopVignette

[TopVignette.tox](TopVignette.tox) takes a TOP image, darkens its edges in a GLSL
pixel shader, and outputs the processed image. The saved chain is
`in1 → vignette → out1`. The shader preserves the input alpha.

## User workflow

The user sometimes uses this for a vignetting effect. It is a low-priority
utility, and the user is open to a better implementation in future. There is
no request to redesign it now or investigate its usage further.

## Controls

| Parameter | Role in the saved shader |
| --- | --- |
| `Strength` | Amount of darkening, clamped to 0–1 in the shader. Zero leaves RGB unchanged. |
| `Scale` | Shapes the falloff; negative values are treated as zero. |

The falloff follows the rectangular frame. A shader comment explicitly says this
avoids a visible circular spotlight in wide output. This describes the existing
implementation, not a user requirement for any future replacement.

The shader multiplies RGB by a factor between 0.55 and 1. At full strength the
outer edge retains 55% of its input brightness; increasing `Strength` above 1
does not make it darker. Increasing `Scale` reduces the darkening in the interior
while the outer edge remains affected. With `Scale` at zero, darkening is uniform.

Evidence: user-confirmed usage and offline expansion of `TopVignette.tox`,
including its pixel shader.
These are saved-code properties, not a live visual assessment or confirmed presets.

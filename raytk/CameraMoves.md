# CameraMoves

Local camera preset controller inside the visual. Edit the `poses` Table DAT:
each row stores a name, position (`tx`, `ty`, `tz`), look-at target
(`lookx`, `looky`, `lookz`), field of view (`fov`), focus offset and falloff,
`sway_percent`, and camera `roll` in degrees. Keep the header row and at least one pose.

| Preset | Position XYZ | Look-at target XYZ | FOV | Sway % | Roll |
| --- | --- | --- | --- | --- | --- |
| Side | 0, 0, 14.533632 | 0, 0, 0 | 40° | 0 | 0° |
| Angled | 5.253458, 4.946125, 5.253458 | 0, -0.2560749253012169, 0 | 80° | 100 | 180° |
| Texture | 0, 0, 2.7 | 0, 0, 0 | 110° | 0 | 0° |
| Top | 0, 14.514267, 0.75 | 0, 0, 0 | 40° | 0 | 0° |

`roll` turns the image around the camera's viewing axis. Angled is upside down;
the other presets stay upright. It is an eleventh channel in `target_pose`,
passes through the existing `pose` Spring CHOP, and drives `camera.Camrotz`.
Entering or leaving Angled therefore includes a visible half-turn with the
same spring tuning as camera movement. Roll interpolates directly in degrees
without angle wrapping; no additional CHOP or parent control is needed.

Edit `sway_percent` in the table to set continuous camera sway for each view:
0 disables it, 50 gives half strength, and 100 uses the full CameraSway Amount.
Values are clamped to 0–100 and converted to the `sway_scale` channel (0–1),
which passes through the shared Spring CHOP with the pose. Sway fades with camera
moves; envelope-triggered screen shake is unaffected. No extra CHOP is needed.

The angled orientation was recovered from `SimpleRayTK.18.toe`; Side originated
in revision 19. Texture is a close side view whose wide lens frames the slices
as an image-filling texture rather than a whole object.
The angled target preserves the old -35° pitch / 45° yaw exactly; aiming it
at the origin instead would slightly change the composition. On 2026-09-19,
Side and Angled changed from 20° to 40°. Their position offsets from the target
were scaled by `tan(10°) / tan(20°)`, about 0.4844544, to preserve framing at
the target plane. This keeps the subject approximately the same size while
changing perspective. Texture remains at Z 2.7 and 110°.

Later on 2026-09-19, only Angled's base FOV was doubled from 40° to 80°.
Its position offset from its look-at target was scaled by
`tan(20°) / tan(40°)`, about 0.4337628, to retain the same target-plane framing.
Side, Texture, the global FOV Multiplier, and per-pose focus controls were
unchanged.

On 2026-09-20, Top was appended as the fourth preset. It looks down from positive
Y at the center, about 3° off vertical. The small positive-Z offset avoids
aligning the view direction with the camera's fixed world-Y up vector and leaves
room for the spring's slight overshoot. Camera distance and FOV match Side for
similar framing; Top starts with Side's focus settings and no continuous sway.
The other preset rows and the user's spring tuning were preserved.

## Camera selection

Press `\` in TouchDesigner to cycle Side → Angled → Texture → Top → Side.
The **Camera View** menu (`Preset`) on CameraMoves is the shared destination
selector. Its choices come directly from the `poses` table. The Keyboard In DAT
advances that menu once per press, suppressing held-key repeats and modifier
combinations. Cycling starts from whichever view is selected and wraps using
the table's row count. Held-key state is local to the callback module and resets
when the project loads. The former `preset_index` Count CHOP is no longer needed.

The mapped wrapper supplies a zero-based integer through the visual's `camera`
CHOP input. Preset binds through ControlInputs. For a local menu change that
preserves Bind mode, use the parameter pane, Next, or:

```python
op('CameraMoves').par.Preset.menuIndex = 3  # Top, from the visual network
```

A later changed input reclaims selection; an unchanged input does not undo the
local edit. Bitwig receiver setup stays in the wrapper. Keep this selection discrete. Like
TopCrossfade, CameraMoves resolves the destination first and smooths the actual
values rather than sweeping a smoothed index through intermediate presets.
The native Spring CHOP keeps its current position and velocity if another view
is selected during a move; it is not reset to a previous settled pose.

A single Constant CHOP produces eleven channels; one Spring CHOP moves all eleven. The preset table
keeps FOV in degrees, but the Constant CHOP converts it to `frame_height` before
smoothing. The camera calculates its FOV from that height and its current
distance to the smoothed target.
The former `Lag Seconds` control has been replaced by native spring controls.

## Spring controls

The existing **Camera** parameter page has a labeled **Spring** section below
FOV Multiplier. It exposes every parameter from the native Spring CHOP's Spring
page through direct bindings, including Reset Pulse. No callback DAT is needed.

| Control | Initial value | Meaning |
| --- | --- | --- |
| Spring Constant | 1416.489 | Spring strength; higher values increase response speed. |
| Mass | 1 | Higher mass lowers oscillation frequency and resists changes. |
| Damping Constant | 60.218 | Resistance; lower values add bounce, higher values suppress it. |
| Input Effect | Position | Position follows preset values; Force interprets them as applied forces. |
| Initial Conditions from Channel | On | Starts each channel at its input value. |
| Initial Position | 0 | Used when initial conditions from the channel are disabled. |
| Initial Speed | 0 | Used when initial conditions from the channel are disabled. |
| Spring per Sample | Off | Direct access to the native Spring per Sample option. |
| Reset | Off | Hold on to reset the spring continuously. |
| Reset Pulse | Pulse | Reset once using the selected initial conditions. |

These are the native physical controls. The initial values preserve the user's
live tuning when the full interface was exposed.

For reference, natural frequency is `sqrt(Spring Constant / Mass) / (2*pi)`;
critical damping is `2*sqrt(Spring Constant * Mass)`. Damping just below that
critical value gives a small bounce. The native simulation's sampled response
also depends on its channel rate. `target_pose` supplies 240 samples per second
for finer integration, independently of the display frame rate. This remains
one Constant CHOP feeding one Spring CHOP, with no additional runtime operators.
Initial Position and Initial Speed are disabled in the interface while Initial
Conditions from Channel is enabled.

## Framing and aim

`FOV Multiplier` on CameraMoves defaults to 1. Drag above 1 for a wider lens
and a closer camera, or below 1 for a narrower lens and a farther camera.
Camera distance compensates automatically to preserve framing at the target
plane. This is a global live control; it does not rewrite the preset table or
add a CHOP. Its slider and hard limits both cover 0.05–4.

Position and target pass through the same Spring CHOP, and the camera calculates
its aim from those smoothed points on every render. This replaces independently
lagged Euler angles, which previously let the center drift out of frame between
presets. Increasing lag could only slow that incorrect path. The tiny per-pose
target offset preserves the approved diagonal composition during the move.

## Coordinated lens movement

Lagging FOV degrees directly made the lens widen before the camera got close,
briefly showing much more of the scene than either saved view. Instead, the
existing lens channel now carries the visible height at the target plane:

```text
target frame_height = target distance * tan(preset FOV / 2)
live FOV = 2 * atan(smoothed frame_height / current distance)
```

Distance is between camera position and look-at target. Convert degrees to
radians for `tan`, and back to degrees after `atan`. The formula follows this
RayTK camera's height-based projection. Position, target, framing and depth
controls retain one shared Spring CHOP. There are no additional runtime operators
or callbacks, and rapid preset changes continue from the current smoothed state.
The formulas preserve every preset's FOV at rest while coordinating zoom with
actual movement. This is a framing approximation for a 3D object, not a guarantee
that every depth layer keeps the same size.

For multiplier `m`, the actual camera position is
`target + (smoothed_position - target) / m`, and FOV becomes
`2 * atan(smoothed_frame_height * m / smoothed_distance)`.
The multiplier scales lens spread, `tan(FOV/2)`, rather than degrees; this avoids
clipping a wide-angle preset at 180°. For example, a 40° preset at multiplier
1.5 becomes about 57.3°, at two-thirds of its saved distance. Depth of field
uses the actual compensated camera position, so focus follows the adjustment.

## Local screen shake

The visual's `camera` is a RayTK 0.45 `lookAtCamera` with the local
`lookAtCamera.glsl` function template embedded in its `functionTemplate` DAT.
This documentation change does not include the shader source.
The stock shader rotates the world-space ray. This version rotates the
camera-space ray first, then transforms it by the look-at basis:
`world_ray = look_at_basis * local_shake * camera_ray`.
Thus shake is applied relative to the aimed camera's screen axes. The X/Y
rotation parameters add `camera_shake` and the continuous `camera_sway` channels
multiplied by `CameraMoves/pose['sway_scale']`. The motion signals themselves
bypass the Spring CHOP; only the preset's sway percentage follows the transition.
The camera clamps the resulting sway scale to 0–1 before applying it, so spring
overshoot cannot reverse sway or exceed the preset's full strength.
[CameraSway](CameraSway.md) owns the slow LFO/noise motion.
The signs and XYZ order match the previous basicCamera.

This is a local shader customization: RayTK's Update OP may replace it. Keep
a copy of the embedded DAT before updating, and reapply this template
after updating the operator. The visual needs no external source file to run.

## Depth of field per pose

| Column | Meaning | Side | Angled | Texture | Top |
| --- | --- | --- | --- | --- | --- |
| `focus_offset` | Sharp plane distance equals camera distance from the visual origin plus this offset, in scene units. | -2.1 | -2.15 | -2.1 | -2.1 |
| `blur_falloff` | Distance away from the sharp plane to full blur, on either side; smaller gives a shallower transition. | 2.0 | 2.6 | 7.8 | 2.0 |

Blur strength is shared: `PostProcessing/dof_blur` White Width stays at 35 for all views,
matching the approved diagonal view. Keep effect strength out of the camera
pose data; tune per-view depth of field with focus offset and falloff only.

These values travel through the same Spring CHOP as the camera.
`PostProcessing/focus_mask` computes blur on both sides of the sharp plane from
the actual camera position and smoothed focus controls; its output and Luma
Blur's black/white values remain normalized to 0–1. Focus follows camera distance
automatically when positions change.
The [PostProcessing component](PostProcessing.md) owns depth mapping, blur,
image noise, and bloom; its focus controls retain these camera references.
The [Autofocus component](Autofocus.md) adds a temporary focus-distance offset
and divides lens spread by its zoom factor. It leaves camera position and the
framing-preserving FOV Multiplier unchanged, returning to the normal pose when
AutofocusEnvelope (debug key 7) reaches zero.
At FOV Multiplier 1 and with autofocus idle, Side focuses at about `12.43`,
Angled at `6.78`, and Texture at `0.60`. On 2026-09-19 the one-sided blur ramp
was replaced by blur on both sides of this plane. Resting offsets were adjusted
around measured sharp-surface depths; existing falloffs and maximum blur were
preserved. Camera distance assumes the subject is near the local origin.

The normalized blur mask is
`clamp(abs(axial_depth - focus_distance) / blur_falloff, 0, 1)`.
The shader converts RayTK ray distance to axial depth using the live FOV, so
the sharp region stays planar during wide-angle views and autofocus breathing.
Camera distance is calculated, while focus offset and falloff remain artistic
controls. Widen falloff for a deeper sharp region, or move focus offset to choose
which layer is sharp; do not change blur strength per pose.

The camera references `CameraMoves/pose` and adds reactive shake and the
preset-scaled sway X/Y after smoothing. Everything uses local relative
references inside the visual's eventual `.tox` export boundary. No agent calls
or frame callbacks are needed during performance. Pitch and yaw still come
from look-at; only roll is stored as an angle in the table. There are no
pitch/yaw angle-wrap transitions; roll takes the direct path described above.
The look-at basis uses world Y as its up vector.

Verified live on 2026-09-14: actual slash presses selected Angled and wrapped
back to Side; sampled intermediate poses approached the target smoothly.
On 2026-09-17, the shortcut was changed to backslash only; forward slash no
longer advances the counter.
The look-at revision was checked against the previous camera's GPU ray
direction, and the existing envelope produced nonzero shake values matching
the camera's X/Y rotation during a live transition. Per-pose depth controls
remain coordinated with camera movement.
On 2026-09-19, sampled live transitions confirmed that visible height follows
the smoothed `frame_height` channel instead of overshooting as FOV changes.
Later that day, the Lag CHOP was replaced in place with a Spring CHOP, preserving
the `pose` path, all ten channel names, the preset table, and the backslash
shortcut. Live transition samples showed a small overshoot, positive frame
height and focus falloff, and correct settled poses. The rendered scene was
inspected, with no visual operator errors and a 60 fps performance snapshot.
Native spring controls, including the bound Reset Pulse, were verified before
saving. All temporary verification operators and stored samples were removed.

On 2026-09-20, direct selection was verified with Top → Angled → Side → Texture
→ Top. Each change immediately selected only its destination row, while the
smoothed pose remained continuous at the selection boundary. Retargeting during
spring overshoot preserved the in-flight pose. Keyboard callback checks cycled
all four views and suppressed repeated key-down events. The edge/render shortcut
is separate; see [Edge treatment](EdgeTreatment.md).

The public **Next** pulse advances Preset with wrap; the backslash keyboard
callback now calls that same action. Pose data and spring tuning are unchanged.

## Top-view raymarch backstop

**Rendering → Top View Backstop** enables an invisible world-space cutoff at
**Top Backstop Y**, initially **−6**. In Top, rays stop when they travel below
that plane. This removes distant background beyond the plane; it does not add
a shaded surface, a second renderer, or another per-step SDF evaluation.
Move Y farther negative if more distant geometry must remain visible.

The renderer's native limit box implements the cutoff. X/Z bounds and upper Y
are ±1,000,000; lower Y is the public cutoff only when Preset is Top and the
backstop is enabled, otherwise −1,000,000. The other faces are beyond the
100-unit Max Distance. Use Limit Box stays on so changing presets only updates
a uniform instead of compiling a different shader. Other camera presets retain
their existing ray-travel extent. This replaces inactive legacy bounds that
referenced CellBoxes; the CellBoxes component itself is unchanged.

Verified live on 2026-09-21: Top remained under its existing external selector,
the image rendered without errors, and the cutoff rejected distant rays.
Quiet four-second samples reached 60 fps both with the original limits and
with Y −6/−10, so those samples do **not** establish a measured FPS improvement
or fully explain the reported 40 fps during performance. Step-output diagnostics
were restored off. RayTK's early limit exit skips updating its step counter,
so zeroes in that diagnostic represent clipped rays, not zero computational work.
Max Steps 512, Max Distance 100, and Distance Factor 0.5 were preserved.

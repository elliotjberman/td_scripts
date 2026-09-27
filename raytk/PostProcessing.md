# PostProcessing

Owns the visual's existing depth-of-field, image noise, and bloom chain.
The visual parent retains its template interface.

```text
image_in ───────────────── dof_blur → noise1 → bloom1 → BloomMask ─┐
depth_in → focus_mask ─────┘             └──────────────── comp1 → out1
```

Input 0 is the processed color image from `null1`. Input 1 is scene depth from
the existing RayTK `render_depth` buffer extractor. No additional raymarch or
render is created. Output resolution follows the image input.

[BloomMask](BloomMask.md) steps the existing rectangle from Y 0.4 to −0.4 in
0.1 increments on BloomEnvelope triggers, wrapping to the top. The visual’s BloomTiming.Rippler state
enables it through a native Hold and short parameter reference; disabled mode bypasses the rectangle
and restores full-frame bloom. Advance/Enabled are public controls for reuse.

The **Bloom** page exposes Threshold, Fill, Minimum/Maximum Radius, Pre Gamma,
Pre Black Level, and Pre Brightness. Values are preserved from the original
bloom1 and referenced by that TOP. Envelope range lives on BloomEnvelope;
palette/treatment levels live on BloomCalibration.

## Controls

| Parameter | Purpose / current source |
| --- | --- |
| Focus Distance | Distance to the sharp plane, in scene units; camera distance plus `CameraMoves/pose['focus_offset']` and `Autofocus/out1['focus_offset']`. |
| Focus Falloff | Distance away from the sharp plane that reaches full blur, on either side; `CameraMoves/pose['blur_falloff']`, clamped to at least 0.001. |
| Blur Radius | Shared maximum Luma Blur width, preserved at 35. |
| Noise Amount | Existing Noise TOP amplitude, preserved at 0.1. |
| Bloom Intensity | `BloomCalibration/out1`, mapping `bloom_amount` through per-palette edge/raw levels. |

The depth mask is now
`clamp(abs(axial_depth - focus_distance) / focus_falloff, 0, 1)`.
Surfaces at the focus plane stay sharp; nearer and farther surfaces become
progressively blurry. Keep per-camera adjustments on focus distance/falloff,
preserving shared blur strength.

`focus_mask` replaces the former `depth_range` Math TOP with one GLSL TOP.
It first converts RayTK's distance along each ray to camera-axis depth, keeping
the focus surface planar even in the wide Texture view. It then takes the
absolute distance to the focus plane and normalizes that to 0–1. This replaces
one image pass with one image pass; it adds no renderer or depth buffer.

The shader follows this visual's actual `lookAtCamera` projection:

```text
slope = (uv - 0.5) * (aspect, 1) * tan(Camfov / 2)
axial_depth = ray_distance / sqrt(1 + dot(slope, slope))
```

Camfov is converted from degrees to radians. The half-sized UV interval matches
RayTK's `z = image_height / tan(Camfov/2)` camera template; do not substitute a
conventional full-FOV formula. The uniform uses the live camera FOV, including
camera transitions, FOV Multiplier, and autofocus breathing.

Implementation: `focus_mask.glsl`, embedded in `focus_mask_pixel` for
portable `.tox` export; the source file is not included here. The shader requires a RayTK ray-distance depth input and
references the sibling `camera` for its FOV. When reusing this component with a
different camera projection or an already axial depth buffer, adapt that conversion.
This remains a screen-space Luma Blur effect; it does not simulate aperture
shape or reveal occluded geometry through foreground blur.

Controls inside the component reference their owning parameters. The component's
camera/envelope expressions refer to siblings in the visual using relative
paths. Exporting the complete visual preserves these relationships; when reusing
PostProcessing alone, supply both TOP inputs and replace the camera/envelope
parameter expressions with the new host's sources or constant values.

Noise retains its small period and `absTime.seconds` translation; bloom retains
its existing threshold, radius, fill, and pre-black level, exposed through the
public Bloom page. Noise period and translation remain on its internal operator.

The component is embedded in the Teachers Pet visual. Export the current
live component when needed; no standalone TOX is included here.
The initial ownership refactor matched the original output pixel for pixel. A temporary bloom
intensity change visibly changed the result, and restoring the envelope expression
returned the exact original pixels. The visual had no operator errors; a subsequent
performance sample reported 60 fps. [Autofocus](Autofocus.md) subsequently added
an envelope-driven offset to Focus Distance and a correlated camera zoom;
The subsequent two-sided focus update preserves that focus/zoom motion, all
falloffs, and the shared blur radius. Resting pose offsets were tuned to Side
`-2.1`, Angled `-2.15`, and Texture `-2.1`, near the previously sharp surfaces.

GPU verification of the new mask matched the expected depth mapping within
`0.000009`. For the same surface sample, focus at its depth produced mask `0`;
moving the focus plane half a falloff in either direction produced `0.500008`
in both cases (16-bit normalized mask precision).
All three camera presets showed nonzero blur on both sides of the focus plane.
An AutofocusEnvelope trigger produced positive and negative focus offsets with
matching zoom changes and returned to zero offset/unity zoom. Rendered views
were inspected, the visual had no operator errors, and a live performance
snapshot reported approximately 60 fps. Existing RayTK icon-font warnings were
unchanged. These measurements are observations, not a performance guarantee.

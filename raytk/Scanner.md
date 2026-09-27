# Scanner

`Scanner` adds a scanning band to the existing visible RayTK surface, using
either a solid color or animated noise colored through a lookup ramp.
Everything stays inside the visual export boundary. The visual parent gains no
parameters; the box, intersection, mask renderer, and compositing belong to
`Scanner`. Its `ScannerEnvelope` remains with the other envelope rows.

## Trigger and travel

- **Debug key:** `6`, checked against the loaded project's assignments when
  created. The envelope's Test Key, keyboard input, and stored key agree.
- **Envelope:** the existing ScaledEnvelope component, named `ScannerEnvelope`,
  with output range `0–1` and a `scanner_progress` reference Null CHOP.
- **Travel Progress:** public `Scanner.par.Progress`, ranging from `0` to `1`.
  Its expression is `1.0 - float(parent().op('scanner_progress')[0])`, so the
  envelope release advances the scan. At rest it reads `1`.
- The box moves from positive Z to negative Z, centered on the sphere:
  `sphere.Translatez + Travel * (0.5 - Progress)`. This is the reversed direction
  requested during authoring.
- Adjust timing and curve on `ScannerEnvelope`. Retriggering restarts this
  envelope, with its peak clamped. Other envelopes retain their own behavior.
- To scrub or drive travel independently, put Travel Progress into Constant
  mode or replace its expression. The scanner is active strictly between `0`
  and `1`; both endpoints clear it. The normal envelope rests at `1`.
- **Fade In** and **Fade Out** are fractions of travel. Fade In is currently
  `0`; Fade Out is restored to `0.169`, fading over the last 16.9% of travel.
  The band disappears and the background finishes returning at Progress `1`.
  There is no additional tail or endpoint hold.
- Travel retains the ScaledEnvelope's `0.96`-second **Ease Out** release.
  Opacity ramps linearly against progress within the fade regions, so its
  time shape follows that existing travel curve. Retriggering restarts the sweep.

Follow [ScaledEnvelope](../midi_handler_v2/ScaledEnvelope.md) for naming and key
allocation. Keep the envelope rows in key order, with compact gutters, and put
standalone parameter/control components below the entire group.

## Controls and outputs

- **Appearance:** `Solid Color` or `Noise + Ramp` (internal values `solid` and
  `noise`). Solid Color keeps its gain at `3.9`; switching modes does not change it.
- **Edit the purple palette:** dive into `Scanner` and select `purple_ramp`
  (`/project1/MappedVisual/visual/Scanner/purple_ramp` in this project).
  Edit its normal Ramp TOP color stops; the docked `purple_ramp_keys` DAT stores
  them. The initial palette runs from dark violet through purple to lavender,
  with HDR values for bloom. This ramp only colors the scanner, independently
  of the three main palettes inside `ColorLookup`.
- **Edit the texture:** `Scanner/scan_noise` controls the texture scale,
  roughness, and movement. It starts with monochrome 3D Simplex noise, period
  `0.45`, amplitude `0.25`, offset `0.5`, and Translate Z advancing at
  `absTime.seconds * 0.12`. The texture is in image space; the scanning box and
  intersection remain in world space.
- **Box Width / Height:** full dimensions in world units. Initially follow the
  sphere's diameter with 10% margin. RayTK `boxSdf` takes half-extents, so the
  internal Scale XYZ expressions divide these dimensions by two.
- **Band Thickness:** full Z thickness in world units.
- **Travel Distance:** total distance between the two endpoints.
- **Fade In:** fraction of travel reserved for bringing the band in and dimming
  the background. Independent of Fade Out; set to zero for an immediate start.
- **Fade Out:** fraction of travel reserved for fading to transparent, ending
  exactly at Progress `1`. Set to zero for an immediate end. Internal parameter:
  `Fadeout`. The temporary extra-time tail has been removed.
- **Background Opacity:** normal-image opacity while the scanner is active.
  `0` shows only the scanner band; `1` preserves the full background.
  Intermediate values dim the background. Fade In dims it gradually as the band
  appears. During Fade Out, the background
  returns to full opacity as the band disappears. Idle and disabled states
  always preserve the normal image.
- **Edge Softness:** world-space blending distance. A small additional tolerance
  includes surface hits that land just outside the SDF zero crossing.
- **Solid Intensity / Solid Color:** affect Solid Color mode only. Noise mode's colors and
  brightness come from `purple_ramp`.
- **Enable:** turns the whole scanner effect on or off.
- `out1`: the incoming image with the scanner layer composited over it.
- `scan_out`: the separate transparent scanner layer.
- `intersection_out`: the RayTK SDF definition of the box/shape intersection.

## Rendering

```text
source_shape ─┐
             ├─ intersection ─ inside_intersection ─ surface_mask
scan_box ────┘                                      ↑
                         main renderer worldPosOut ─┘

scan_noise ──→ noise_lookup ← purple_ramp
                    ↓
solid_color → appearance_switch → appearance_fade ─┐
surface_mask → mask_transform ─────────────────────┼─ scan_layer → composite → out1
line_image ───────────────────────────────────────┘                ↑
                                             image_in → background_level

Travel Progress → shared scan/background opacity
```

The geometry uses native RayTK `boxSdf`, `combine` in `simpleIntersect` mode,
and `sdfField` in `inside` mode. RayTK `pointMapRender` evaluates that scalar
field at world positions already found by `raymarchRender3D`. It performs one
field evaluation per valid surface pixel, with no second raymarch and no
scanner-specific GLSL. This is a visible-surface highlight: it cannot reveal
hidden interior cuts.

The main renderer's **World Position Output** must stay enabled. `source_shape`
selects the visual's `base_shape`; keep that source consistent with the SDF
being rendered if the geometry chain changes. Resolution follows the existing
world-position buffer and the visual's inherited resolution.

The mask follows the existing `transform1` spatial controls, using a transparent
background. The scanner layer uses the white line image before palette lookup.
The current visual chain is `transform1 → ColorLookup → Scanner → null1`, then
the existing downstream effects. Thus the main palette cannot recolor the band.
Existing line blur is reused; the scanner mask's own edge is controlled by Edge
Softness. `scan_layer` combines the mask, line image, and selected appearance.

The Switch TOP selects either the `solid_color` Constant TOP or the Noise → Lookup TOP
branch. The shared `appearance_fade` Level TOP applies opacity after this
selection. Noise inherits the visual's resolution; the palette is a 512×1
lookup texture. No additional raymarch is needed for either appearance.

The shared opacity expression multiplies the clamped fade-in and fade-out
factors derived directly from Travel Progress. No separate timing CHOPs,
additional debug key, or second envelope are needed.

`background_level` uses
`1 - (1 - Backgroundopacity) * appearance_fade.opacity`, so the background
returns with the same fade that clears the band. Both Level TOPs scale RGB and
alpha together; leave their extra **Pre-Multiply RGB by Alpha** toggles off to
avoid applying the fade twice.

References to the source shape, renderer, sphere, envelope output, and line
image are relative within the visual. Export the whole visual to preserve
these dependencies; `Scanner` alone is not a standalone scene asset.

## Verification — 2026-09-19

Triggered the existing ScannerEnvelope and inspected rendered captures in both
appearance modes. Solid-color gain remains `3.9`; the purple texture changes color
within the same visible-surface band. Public Progress, box movement, opacity,
and background restoration were sampled during the sweep. The user's preferred
progress-based timing was restored after trying an additional release tail;
travel duration, travel curve, appearance controls, and palette were preserved.
Live samples at Progress `0.855`, `0.915`, and `0.972` produced opacity `0.857`,
`0.504`, and `0.168`. At Progress `1`, opacity was `0`, background opacity was
`1`, and the output matched the incoming image exactly in a pixel comparison.

The current visual had no operator errors and reported 60 fps at 1920×1080.
Existing RayTK icon font warnings remain unrelated to this effect. This is a
live-session observation, not an isolated GPU benchmark; the world-position
buffer and additional TOP passes still have a cost.

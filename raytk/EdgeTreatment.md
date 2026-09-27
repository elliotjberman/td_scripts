# Edge treatment

The current visual uses `raymarchRender3D → EdgeMix → transform1`.
`EdgeMix` wraps the existing Edge TOP and exposes two independent 0–1
controls on its Mix page: **Edge Opacity** and **Raw Opacity**. The visual parent
still only exposes its template contract.

| Treatment | Edge Opacity | Raw Opacity |
| --- | --- | --- |
| Edges only (default) | 1 | 0 |
| Original shaded image | 0 | 1 |

Use the public **Toggle** pulse or press `;` to toggle **render → edges only → render**. The keyboard
handler and smoothing are entirely inside EdgeMix. Each press sets the two
existing opacity controls to the opposite single-layer preset; holding the key does not
repeat, and modified presses are ignored. After a manual mix adjustment, the
next press advances from the closest preset. The combined render-plus-edges
destination has been removed from the switch. The independent opacity controls
remain available for manual adjustments and the existing transition fade.

Both opacity targets pass through one two-channel Lag CHOP with 0.1 seconds
for rising and falling changes. **Opacity Fade Seconds** on the Edges page
controls both directions. This smooths the actual layer weights, not a
preset index, so wrapping directly from edges-only to raw does not sweep
through another preset. The sliders remain independently editable and their
manual changes use the same lag. Lag time is approximately time to 90% of a
change, rather than a fixed-duration fade.

Intermediate values adjust either layer independently. Internally, `image_in`
feeds the original `edge1` and a raw branch; a Level TOP on each branch controls
opacity, and a Screen Composite TOP combines them into `out1`. Screen adds the
bright outlines without the edge image's black background obscuring the raw
image. It is a screen blend, not a linear crossfade. Both opacities at zero
produce transparent black. Resolution follows the input; all parameter
references are local to the component.

The **Edges** page exposes the preserved Thickness, Strength, and Black Level
settings; `EdgeMix/edge1` references those parameters. The component
adds no second scene render. Its active controls use one Parameter CHOP and one Lag
CHOP, plus a Keyboard In DAT and its local callback. The obsolete Constant
CHOP was removed on 2026-09-22.
Live verification matched both single-layer modes exactly to their inputs and
checked the combined output against the Screen formula.

The reusable component is embedded in the Teachers Pet visual. Export the
current live component when needed; no standalone TOX is included here.
The active Edge TOP is inside EdgeMix; no top-level backup remains.

## Consistent line thickness

`edge1` uses pixel units and equal X/Y sample steps. Its sample-step expression
is `parent().par.Thickness * me.inputs[0].height / 1920.0`, with Thickness 1.2: 1.2 pixels at 1080×1920, and 0.675
pixels at 1920×1080. This preserves the preferred portrait treatment relative
to image height. The public Thickness parameter is the artistic coefficient.
Input filtering remains Linear; output resolution uses the input.

RayTK's camera projection uses render height. At the same position and FOV,
a 1920-pixel-high image samples the subject 1920/1080 times more densely than
a 1080-pixel-high image, while cropping to a narrower horizontal field. A
fixed 1.2-pixel edge consequently looks thinner relative to the subject in
portrait. Scaling the sample step by height compensates for that thickness mismatch.
It cannot make different lenses, distances, or geometry produce identical
image detail.

## Previous antialiasing treatment

An earlier revision used `edge_antialias`, an Anti Alias TOP with High-quality
SMAA and luminance detection, after edge extraction and before depth blur.
Those stages were absent from the live edge chain when EdgeMix was added;
EdgeMix does not restore them. Edge's Strength remains 10 and Black Level
remains 0.048.

SMAA smooths the extracted lines at output resolution. It cannot recover scene
detail that the raymarcher did not sample. For higher-quality offline output,
rendering at a larger resolution and downsampling after edge extraction can
help. RayTK's Anti Alias setting of 2 traces a 2×2 grid (four rays per pixel),
so increasing it has a substantial cost; it remains 1 for this live setup.

Compare output at native pixel scale. A fitted portrait viewer usually applies
more downsampling than a landscape viewer at the same available height, which
can make its lines appear smoother even before changing the processing.

The earlier antialiasing setup was checked at 1920×1080 and 1080×1920, then
restored to inherited resolution. Camera position and field of view are
independent of this edge treatment.

References: [Edge TOP](https://derivative.ca/UserGuide/Edge_TOP) and
[Anti Alias TOP](https://derivative.ca/UserGuide/Anti_Alias_TOP).

## External DrumWarp routing — 2026-09-22

DrumWarp passes through `LiveControls/drumwarp_live` (Hold), then `edge_amount`
(Math) computes 1−input. The wrapper publishes `raw` and `edge` through the
visual CHOP input. EdgeMix.Rawopacity and Edgeopacity bind to these channels
through ControlInputs. DrumWarp 0% gives edges 1 / raw 0; 100% gives edges 0 / raw 1.
The existing local Parameter CHOP and 0.1-second Lag feed the Level TOPs.

Active, Followremotes, and Edgeready gate the Hold. There are no authored CHOP
exports or continuous-update callbacks. Local actions preserve Bind mode;
a later changed external value reclaims the corresponding channel. See
[LiveControls](LiveControls.md#enable-disconnect-and-manual-operation).

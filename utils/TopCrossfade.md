# TopCrossfade

Crossfade directly between any two TOP inputs without passing through the
intervening input indices. This is the user's existing two-slot component,
recovered from the embedded `TopCrossfade` in
`Documents/touchdesigner/2025/feedback2/resignation_live_phasing.toe.dir`.
The older visual referenced a missing Windows `utils/TopCrossfade.tox` file;
the recovered copy is embedded in the live visual. This guide does not add a
standalone TOX to the repository.

## Controls

- **Index:** zero-based destination input. The controller rounds and clamps
  it to the available inputs. The recovered snapshot read a private
  `palette_index` Count CHOP; current ColorLookup supplies its public Palette
  selection instead.
- **Crossfade Seconds:** transition duration, configured to **0.1 seconds**.
  This supplies the requested smoothing. Keep Index discrete: putting a Lag
  CHOP on a wrapped index would reintroduce transitions through other palettes.
- **Input Count / Rebuild Inputs:** manage the numbered external TOP inputs.
  Set the count before wiring the inputs, and verify their order after changes.
- **Apostrophe (`'`) in the recovered snapshot:** advance the Count CHOP, wrapping through `0` to
  `Inputcount - 1`. The Keyboard In DAT uses the physical `Quote` web code,
  ignores modifier combinations, and counts once per press rather than on
  held-key repeats. Disable the internal keyboard DAT when another instance
  should own this shortcut. In the current visual, ColorLookup owns the key
  and calls its public Next action; do not enable a second shortcut owner.

## How it works

Two Switch TOPs select the current and destination inputs with their own
blending disabled. A Cross TOP blends only those two selections. For a
three-input palette bank, `2 → 0` therefore mixes the last palette directly
with the first; input `1` never becomes an intermediate selection.

The recovered Execute DAT controller advances the blend from local TD frame
callbacks using `absTime`. Input configuration, keyboard handling, and playback
run inside TouchDesigner without Embody or agent calls. The component's input
operators have explicit connector order.

The original controller restarts a transition from the last settled input if
retargeted before the current fade finishes; it does not capture a new source
image from the partially blended output. At the configured 0.1-second duration,
ordinary individual key presses can finish their transition before the next.

## Current visual and verification

The RayTK visual packages this component, its three original ramps, and its
Lookup TOP inside [ColorLookup](../raytk/ColorLookup.md). Enter that component
to edit palettes. Selection and Crossfade Seconds are public on ColorLookup;
they are not exposed on the visual parent.

Verified live on 2026-09-19: native `Quote` keyboard events reached the callback,
the count cycled and wrapped, and the final palette was visible in the render.
At the midpoint of a `2 → 0` transition, only those two slots were selected.
The pixels matched their 50/50 mixture within 8-bit rounding error (maximum
error about `0.001961`). The visual had no operator errors.

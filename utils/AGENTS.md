# Reusable utilities

Read the relevant component guide before using or changing these components:

- [BarTrigger](BarTrigger.md): configurable every-N-bars pulses from a named clock CHOP.
- [ControlMap](ControlMap.md): native range/clamp/lag mapping and disabled-channel omission.
- [NoteLengths](NoteLengths.md): BPM to musical durations; reuse the existing DAW-agnostic TOX.
- [ScreenShake](ScreenShake.md): two-channel motion source; envelope-driven strength.
- [TopVignette](TopVignette.md): image edge darkening with a frame-shaped falloff.
- [DefaultValue](DefaultValue.md): a configured constant and incoming CHOP through
  an Override CHOP.
- [MovieRecorder](MovieRecorder.md): video/audio recording and a recording indicator.
- [TopCrossfade](TopCrossfade.md): direct transitions between TOP inputs, with
  palette cycling that does not sweep through intermediate colors on wraparound.

These guides distinguish saved implementation from user-confirmed workflow.
Do not infer how often the user uses a component from its presence in this folder.


## User priorities

- ScreenShake is heavily used: image position for 2D work or camera position
  for 3D work, depending on the visual.
- TopVignette is an occasional, low-priority effect. No redesign is requested.
- DefaultValue addresses a historical missing-output startup problem. Preserve
  the explanation without assuming the workaround is needed for Bitwig.
- MovieRecorder belongs in the user's default authoring set for easy video
  exports to Instagram. It is not used for live sets; inclusion in a template
  does not imply recording should be active.

## Inspection

- These `.tox` files can be inspected offline using TouchDesigner's bundled
  `toeexpand` utility. Expand a copy in a scratch directory, read its `.n`
  wiring, `.parm` values/expressions, `.cparm` custom controls, and DAT contents.
  Do not overwrite the source `.tox` to inspect it.
- Offline inspection establishes saved structure; use live TD inspection for
  current parameter modes, device availability, behavior, and visual results.
- Saved references such as `shake_amount` or `select1` are contextual wiring,
  not requirements to give every new project's operators those names.
- Keep ScreenShake's `Triangleamp` and `Noiseamp` as relative mix controls;
  drive `Amount` with the envelope/reference output.
- `common.py` contains both general helpers and project-specific reset logic.
  Do not treat its reset routine as a generic initializer for these components.

## Evidence

Component guides were written from offline expansions of the repository `.tox`
files on 2026-09-13, existing development notes, and the user's descriptions of
their workflow. They do not certify a live
TouchDesigner session. See Derivative's
[Toeexpand documentation](https://docs.derivative.ca/Toeexpand).

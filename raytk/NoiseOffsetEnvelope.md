# NoiseOffsetEnvelope

Inside `MappedVisual/visual`, this instance of
[ScaledEnvelope](../midi_handler_v2/ScaledEnvelope.md) owns the noise-offset
range and local debugging. Its debug key remains **2**.

Open its **Range** page:

- **Output Minimum / Maximum:** the visual's target range, currently 0.4–0.7.
- **Input Source — Auto:** use the shared bound level; local ADSR and incoming audio
  participate in last-change-wins control.
- **Input Source — Envelope / Key 2:** ignore the external level and use the
  existing ADSR, Trigger pulse, or key 2.
- **Input Source — Manual Level:** use the local 0–1 slider for range testing.
- **Level (Local / Input):** editable normalized level, bound to the visual
  input so a local edit does not disconnect incoming control.

```text
external 0–1 level ─┐
local ADSR / key 2 ─┼→ input_select → shared min/max → value
manual 0–1 level ───┘                                  │
                              spring1 ←────────────────┘
                                 ↓
                            noise_offset → wombat_noise.Offset
```

The existing `spring1` and `noise_offset` operators stay on this envelope's
row and process every input mode. The range is applied once, before the spring.
The spring's existing settings were preserved; its motion can overshoot the
target range. `wombat_noise.Offset` references only `noise_offset`, with no
external CHOP export directly overriding the effect.

The mapped wrapper's LiveControls/AudioNoise selects PermFilter and conditions
its meter into 0–1 through native Math/Limit/Lag/Hold operators. Its ready
`noise_offset` channel enters the visual's CHOP input. ControlInputs also receives
this envelope's raw Trigger CHOP signal, so key 2 works while disconnected.
Input Source is a local menu: Auto uses the resolved bound level; Envelope and
Manual select those signals explicitly. It no longer references external
readiness or parameter modes.

The local range and spring are unchanged. The shared ScaledEnvelope TOX files
are unchanged; no envelope or debug key was added. See
[LiveControls](LiveControls.md) for current routing and verification.

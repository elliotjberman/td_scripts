# NoiseDrift

Historical component guide: the user removed NoiseDrift from the current live
visual. The stale external route was removed in the 2026-09-22 routing repair.

`visual/NoiseDrift` converts a normalized Amount into a rate and integrates it
into **wombat_noise.Translate1 (X)**. It follows the visual's existing
`speed_amount → speed1 → elapsed` approach, with a separate native Speed CHOP
for X. The existing Z translation still uses its original elapsed channel.

| Public parameter | Starting value | Purpose |
| --- | ---: | --- |
| Amount | 0 locally | Normalized performance input; the song supplies PermFilter. |
| Minimum Speed | 0 | Rate at Amount 0, in noise-coordinate units per second. |
| Maximum Speed | 0.2 | Rate at Amount 1. |
| Current Speed | Read-only | Actual mapped rate. |
| Elapsed / Translation X | Read-only | Accumulated position driving the noise field. |
| Reset Position | 0 | Position used by Reset and on project start. |
| Reset Position Now | Pulse | Native binding to the Speed CHOP's Reset Pulse. |

```text
Amount → amount (Parameter) → speed_range (Math) → speed1 (Speed)
                                                       ↓
                                                 elapsed (Null) → out1
                                                       ↓
                                          public Elapsed → wombat_noise.Translate1
```

The speed target is `minimum + Amount * (maximum - minimum)`:
input 0 / 0.5 / 1 gives **0 / 0.1 / 0.2 units per second**. The Speed CHOP
integrates the rate, so changing the knob preserves accumulated position.
At zero speed X stops where it is, rather than jumping back to zero. Reset is
an explicit separate action. Negative speed bounds allow reverse travel.
No extra lag is applied to this rate; the scale component retains its own
independent smoothing.

All range controls and animation live inside this component. References are
relative, no envelope/debug key is added, and the visual parent remains thin.
Reset On Start follows the existing speed chain, so reopening the project
starts at Reset Position. There is no per-frame Python in the performance path.

## Historical external route (removed)

The former **Project Perform → PermFilter** route fed NoiseScale and NoiseDrift
through `permfilter_events.py`. That continuous callback was deleted during the
routing repair; it is not a pattern to reuse. A new drift component should take
a named continuous CHOP input with a public bound Amount, following the current
[LiveControls](LiveControls.md) contract. The native integration chain above
remains useful independently of that retired route.

## Verification — 2026-09-21

Isolated native checks measured about 0.0983 and 0.1983 units over one second
at inputs 0.5 and 1 (one sample of transition timing). Zero speed held position
after reset settled; Reset Position Now reached 0.125 exactly in the isolated
copy. Routing guards held local values while disabled/disconnected and applied
the current source to both components on reconnect. Test copies were removed.

Live PermFilter movement reached both public Amount values; input zero read
speed zero, and subsequent knob movement resumed X travel. The accumulated
Elapsed value matched the actual Wombat Translate X. The visual rendered and
the changed operators reported no errors. Existing NoiseScale range/smoothing
edits were retained.

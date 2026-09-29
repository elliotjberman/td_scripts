# BarTrigger

[BarTrigger.tox](BarTrigger.tox) turns a song clock into a short `trigger` CHOP
pulse every N bars. It has no DAW receiver, envelope target, or visual dependency.
Put the clock receiver in the mapped wrapper and wire its named channels into
this component.

## Input

One CHOP with these five channels:

| Channel | Meaning |
| --- | --- |
| `position` | Song position in quarter notes, starting at zero |
| `playing` | 1 while transport plays |
| `numerator` | Time-signature numerator |
| `denominator` | Time-signature denominator |
| `connected` | 1 when the source clock is available |

For official TDBitwig, Select/Rename these `bitwigSong` channels:
`transport/position`, `transport/playState`, `transport/signatureNumerator`,
`transport/signatureDenominator`. Merge the shared `bitwigMain` `connected`
channel. Do not infer connection from a frozen song position.

## Controls and output

- **Enabled**: listen to the clock; off by default while wiring the input.
- **Everybars**: interval, initially 2.
- **Baroffset**: zero-based phase. With interval 2, offset 0 selects bars
  1, 3, 5; offset 1 selects bars 2, 4, 6.
- **Trigger**: manually fire the output, including when clock listening is off.
- **Pulsewidth**: native Trigger CHOP peak duration, initially 0.05 seconds.
- **Reset**: forget clock history; the next update establishes a baseline.

Use a CHOP Execute DAT's **Off to On** event on the `trigger` output to pulse an
owning component's public action. Keep that one-line action in the wrapper.
The bar trigger does not know which envelope or behavior consumes it.

## Transport behavior

The initial clock update is silent, including connection midway through a song.
Starting from an already observed stopped downbeat fires normally. Stops and
mid-bar seeks do not fire. Loops and seeks landing near an eligible downbeat fire
once; skipped bars are not replayed. Disconnecting or changing Enabled/interval/
offset resets the baseline. A time-signature change also establishes a new
baseline; numbering uses the current signature from song position zero, not a
historical meter map.

A downbeat is accepted within the first quarter note (or quarter of a short bar),
to tolerate clock delivery between TD frames. This is a frame-driven visual
trigger, not a sample-accurate audio scheduler. Repeated packets do not retrigger.
Missing required channels and invalid time signatures remain visible errors.

## Maintenance and verification

The stateful event callback is [bar_trigger.py](bar_trigger.py); the output pulse
is a native Trigger CHOP. Public actions use
[bar_trigger_actions.py](bar_trigger_actions.py). All code is embedded in the TOX.
[build_control_components.py](build_control_components.py) rebuilds the component
inside a supplied authoring COMP without connecting a DAW or saving the project.

Verified in TD 2025.33070 with synthetic transport input, native output events,
manual pulses, and relocated TOX reloads. Clock regression cases cover alternating
bars, duplicate packets, stop/resume, loops, seeks, 6/8, offset, and meter changes.
No Bitwig playback was operated for this packaging verification.

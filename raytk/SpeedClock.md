# SpeedClock

`LiveControls/SpeedClock` pulses the existing visual's `SpeedEnvelope.Trigger`
on beat 1 of every other bar. It reads Bitwig's global song position through
the official `bitwigSong` receiver. It never starts/stops transport or writes
tempo, time signature, or other Bitwig parameters.

## Controls

- **Enable Speed Trigger:** enable/disable this clock route independently.
- **Every N Bars:** default 2.
- **Bar Offset:** default 0, giving bars **1, 3, 5, …**. Set to 1 for
  **2, 4, 6, …**. Offset wraps within Every N Bars.
- **Clock Connected:** valid connected timing feed and time signature.
- **Current Bar / Last Trigger Bar / Trigger Count:** read-only feedback.

SpeedEnvelope retains its own ADSR, output range, and debug key **3**. No new
envelope or debug key is created. Its existing `speed_amount → speed1 → elapsed`
chain still drives noise translation. The clock component stays outside the
exportable visual and uses `LiveControls.Targetvisual` to find its target.

## Timing

Bitwig's transport position is in quarter notes. One bar has
`numerator × 4 / denominator` quarter notes. The zero-based bar index is
`floor(position / barLength)`; selected bars satisfy
`barIndex % Everybars == Baroffset % Everybars`.

One CHOP Execute DAT watches native position/play-state changes. It pulses
once when entering a selected bar while playing, accepting the first timing
sample less than a quarter note after the downbeat. This allows normal OSC
delivery delay and prevents a seek into the middle of a bar from firing.
Initial connection arms a baseline without firing. Stop silences the route;
restart/loop at a selected downbeat can fire again. There is no free-running
TD clock, accumulated beat counter, per-frame polling DAT, or agent dependency.
Timing precision is limited by OSC delivery and TD frame rate; a stall that
skips the downbeat window skips that trigger instead of firing it late.

The official receiver owns the time channels; do not edit the controller or
inject temporary signals into live mappings to test them. Local timing logic
is embedded in `clock_events` from `speed_clock.py`; the source file is not
included in this documentation change.

## Verification — 2026-09-21

With user-started Bitwig playback at 140 BPM in 4/4, the clock triggered on
bar 41 and skipped bar 42. Captured SpeedEnvelope output rose above 1.5, decayed
to its 0.1 minimum, and accelerated the existing elapsed channel. The user's
1.4-second release and 0.1–2 output range were preserved. Stop produced no
additional clock triggers. Clock/envelope operators reported no errors.
Separate pure-Python checks covered alternating bars, duplicate suppression,
initial attachment, stop/restart, seek, loop wrap, and 3/4 and 7/8 signatures.

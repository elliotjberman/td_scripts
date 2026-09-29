# NoteLengths

Use the existing [NoteLengths.tox](../td_ableton/NoteLengths.tox). Despite its
historical folder and annotation, it already accepts an ordinary CHOP channel
named `bpm`; it does not require TDAbleton. The existing location is retained so
external component references do not break.

For Bitwig, select `transport/tempo` from `bitwigSong` and rename it to `bpm`.
Connect that CHOP to NoteLengths. BPM must be greater than zero.

| Output channel | Seconds at 120 BPM |
| --- | ---: |
| `1/1` | 2 |
| `1/2` | 1 |
| `1/4` | 0.5 |
| `1/8` | 0.25 |
| `1/16` | 0.125 |

These are musical **durations**, not trigger events or playback progress.
A whole note is four quarter notes, regardless of the time signature; it need
not equal a bar. Use [BarTrigger](BarTrigger.md) for transport-aligned events.

For example, an envelope's release time in seconds can reference
`op('NoteLengths')['1/16']`. The source BPM and duration calculation stay in
native CHOPs; an envelope still needs a separate note/event to trigger it.

The existing asset was loaded and verified live in TD 2025.33070 at both 120 and
60 BPM during reusable-component packaging. No replacement TOX was necessary.

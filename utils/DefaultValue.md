# DefaultValue

[DefaultValue.tox](DefaultValue.tox) combines a configurable Constant CHOP with
an incoming CHOP using an Override CHOP, then sends the result to `out1`.

## Original purpose

The user describes this as a workaround for startup/lifecycle issues with an
external parameter source: when TouchDesigner opened before Ableton was running,
the connected parameter CHOP could have no output. Downstream controls needed
a usable numeric value, such as zero, instead of missing data.

That is the reason for this component. The exact missing-data representation
(for example, no channel versus no samples) and reset behavior have not been
verified. Treat this as legacy context; do not assume Bitwig needs the same
workaround or expand the Ableton integration as part of current documentation.

## Controls and wiring

| Parameter | Connection |
| --- | --- |
| `Value` | Value of the internal constant's channel. |
| `Channelname` | Name of the internal constant's channel. |

```text
constant1 (Value, Channelname) → override1 input 0
in1                          → override1 input 1
override1                    → out1
```

Override CHOP uses changes in input channels to choose output values and starts
from its first input's values. It is stateful; this wiring should not be described
as simply replacing every zero input with a default. Matching and reset behavior
matter. See [Derivative's Override CHOP reference](https://docs.derivative.ca/Override_CHOP).

The saved `Channelname` parameter includes a reference to
`op('select1').par.renameto`. Inspect its current mode and set the intended channel
name/reference when using the component elsewhere.

Evidence: the user's description of the original problem, offline expansion of
`DefaultValue.tox`, and the operator reference. Live startup/reset behavior has
not been tested.

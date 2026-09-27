# CellBoxes

`visual/CellBoxes` parks the repeated-box SDF experiment in one Base COMP:

```text
cell_coordinates → cell_noise → boxSdf1 → repeat_boxes → transform2 → out1
```

It is retained for revisiting the experiment, not required by the current control
routes. It adds no controls to the visual parent; edit its original operators
inside the component. Verify the current consumer's enable/selection before
reconnecting it: the original parking revision disabled `visual/combine1`,
but that consumer can be repurposed as the surrounding scene changes.

Noise translation and repeat shifts retain relative references to the visual's
elapsed channel and sphere position. The renderer's former CellBoxes limit
references were replaced by the [CameraMoves backstop](CameraMoves.md#top-view-raymarch-backstop).
Exporting CellBoxes alone requires supplying its surrounding visual dependencies.

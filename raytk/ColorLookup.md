# ColorLookup

Owns the three ramps, direct crossfade, and Lookup TOP. All selection controls
are public on ColorLookup; the visual parent retains its template interface.

| Parameter | Purpose |
| --- | --- |
| Palette | Normalized 0–1 selector: Black `[0, 1/3)`, Warm `[1/3, 2/3)`, Green `[2/3, 1]`. Convenient values: 0, 0.5, 1. |
| Current Palette | Read-only selected name. |
| Next Palette | Advance with wrap; the `'` key pulses this same action. |
| Crossfade Seconds | Time between the two selected ramp images; default 0.1. |

```text
Palette / Next / ' → internal slot mapping → TopCrossfade
ramp1 Warm ─┐                                  │
ramp2 Black ┼──────────────────────────────────┘
ramp3 Green ┘                                  ↓
image_in ────────────────────────────────── lookup1 → out1
```

Palette semantics live here. External routing targets `ColorLookup:Palette`,
not `TopCrossfade:Index`. The physical ramp order remains Warm, Black, Green;
internal mapping preserves Black as the first public choice. Green → Black
blends directly between those images without sweeping through Warm. Held-key
repeats and modified presses are ignored.

Enter ColorLookup to edit the ramps and key tables. The obsolete internal
Count was removed on 2026-09-22; Palette owns selection.
See [TopCrossfade](../utils/TopCrossfade.md) for the two-slot transition behavior.

Resolution follows the incoming image. Internal references are relative and
callbacks are embedded. The live Palette parameter binds to the visual's `palette` input through
ControlInputs. Local edits and Next keep that binding; later input changes
reclaim control. The local `ColorLookup.tox` snapshot predates the 2026-09-22
unused-counter cleanup and is not included here; export the live component
when reusing it. Public Next, wrap, output, and error checks
were verified on 2026-09-21 with Bitwig disconnected.

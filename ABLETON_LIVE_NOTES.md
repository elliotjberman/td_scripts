# Ableton Live Setup Notes

## Studio Mix / Expert Sleepers Hardware Tracks

The mix-project hardware setup uses Expert Sleepers instead of Ableton's
External Instrument device.

For the Tetra and Moog, the pattern is:

- a group track named for the synth, for example `Tetra` or `Moog`;
- a child MIDI `Out` track, for example `TetraOut` or `MoogOut`, containing the
  Expert Sleepers `SW ES-5 Controller` device and the MIDI clips;
- a child audio `In` track, for example `TetraIn` or `MoogIn`, receiving the
  synth's audio from the interface;
- the meaningful audio effects usually live on the group track, after the audio
  comes back from the hardware.

The old setup should be kept when making validation copies. It gives a known
reference path and preserves the old audio tracks while the new live path is
checked.

## Live Hardware Tracks

The live setup does not use the Expert Sleepers path for Tetra and Moog. It uses
Ableton External Instrument devices on MIDI tracks. The External Instrument
handles both MIDI out and audio return, so the new live track does not need a
separate audio input track.

The channel convention found across existing live sets is:

- `TetraLive`: MIDI out `Arturia KeyStep 32` channel 2, audio input `Ext. In 7`
  (`AudioIn/External/M6`).
- `MoogLive`: MIDI out `Arturia KeyStep 32` channel 1, audio input `Ext. In 8`
  (`AudioIn/External/M7`).

When converting an old set, add new top-level External Instrument tracks and
leave the old Expert Sleepers groups untouched. The new tracks should copy the
old MIDI clips from the `Out` tracks and copy the group's audio effects after
the External Instrument device.

The converter defaults the new tracks to muted so the old and new paths do not
both drive the hardware at once. Use `--activate-new` only when the output set
should open with the new live tracks already enabled.

## MIDI Program / Bank Hints

Some hardware tracks encode the desired patch in the track name. The converter
uses these hints only when clips do not already contain explicit MIDI program
data.

Tetra has two banks. In Ableton XML these are stored as `BankSelectFine` values
`0` and `1`; `BankSelectCoarse` stays `-1`. Program numbers in track names are
one-based, while Ableton's `ProgramChange` value is zero-based.

The Tetra name parser accepts both historical forms:

- `TetraOut (15-1)` means program 15, bank 1, so `ProgramChange=14` and
  `BankSelectFine=0`.
- `TetraOut(2-39)` means bank 2, program 39, so `ProgramChange=38` and
  `BankSelectFine=1`.

If a Tetra pair is ambiguous, for example `1-1` or `2-1`, assume
bank-to-program order.

Moog uses program changes without bank selection. A name like `Moog25` means
`ProgramChange=24`, with both bank fields left at `-1`.

When a program hint is inferred, the converter works in Session view only: it
fills unprogrammed Session MIDI clips with the corresponding bank/program data
and adds a zero-note scene-0 dummy clip when the first Session slot is empty.
Existing explicit clip-level program data is preserved. Generated program-change
dummies are named in bank-to-program order, for example `PC 1-15` for Tetra
bank 1 program 15. Synths without bank selection use `PC 25`.

## Converter

Use `ableton_utilities/convert_hardware_tracks.py` for this pass:

```powershell
python "ableton_utilities\convert_hardware_tracks.py" `
  "C:\path\to\old_mix.als" `
  --template-live-set "C:\path\to\live_reference_with_external_instruments.als" `
  --output "C:\path\to\old_mix_hardware_live.als"
```

The template set is used only as a safe source for Ableton's
`ProxyInstrumentDevice` XML shape. The script patches the cloned External
Instrument routes to the fixed live Tetra/Moog channels above.

## Global Macro Boilerplate

The converter also seeds the live Global macro rack when the set has, or the
template can provide, the standard Global/ControllerUtils boilerplate.

The only Global macro seeded by the converter is:

```text
RollVol -> ControllerUtils > VSDC_IN > Velocity > Out Hi
```

In Ableton XML, `Out Hi` is the `MidiVelocity` device's `MaxOut` parameter. The
Map8 object used by the existing live sets for this first roll-volume mapping is
`obj-16`; do not infer it from display order or use `obj-5`.
RollVol's Map8 minimum is set to `1%`, not `0%`, so turning the macro fully down
does not stop the drum controller from firing during a live set.

Song-specific Global macros, such as DrumMorph, PercRoll, DrumFilter, or
DrumVerb, should be applied to validation copies of the target `.als` set rather
than added to the conversion boilerplate.

The Global macro rack should also have `/` mapped to its
`RemoteSelectionKeyMidi`, matching the reference sets' blue-hand/focus shortcut.

If the source has `ControllerUtils > VSDC_IN` but no `Global` track, and the
template set has a Global track, the converter clones a clean Global track from
the template, remaps its Live target ids and nonzero `LomId` values, clears any
template Map8 target mappings, then applies the RollVol mapping.

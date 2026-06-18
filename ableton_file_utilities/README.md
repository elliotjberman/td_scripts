# Ableton File Utilities

Small Python utilities for editing Ableton Live set files.

## FabFilter Pro-Q Phase / Latency Mode

`switch_fabfilter_proq_phase.py` scans an Ableton `.als` file for FabFilter
Pro-Q plugin devices and changes the processing mode.

Examples:

```powershell
python "ableton_file_utilities\switch_fabfilter_proq_phase.py" "C:\path\to\Song.als" --mode zero-latency
python "ableton_file_utilities\switch_fabfilter_proq_phase.py" "C:\path\to\Song.als" --mode natural-phase --write
python "ableton_file_utilities\switch_fabfilter_proq_phase.py" "C:\path\to\Song.als" --mode zero-latency --output "C:\path\to\Song - zero latency.als"
```

Without `--write` or `--output`, the script only reports what it would change.
When editing in place, it creates a timestamped backup next to the original set
unless you pass `--no-backup`.

Supported mode names:

- `zero-latency`
- `natural-phase`

Ableton Live sets are gzip-compressed XML. Live stores third-party plugin
identity in that XML, but the plugin's complete state can live inside an opaque
vendor preset blob.

For FabFilter Pro-Q 3 VST3, a cloned-EQ before/after fixture showed that Zero
Latency vs Natural Phase is stored in the `ProcessorState` hex blob:

- `ProcessorState`: a four-byte mode value at offset `1260`.
- Zero Latency: `00000000`.
- Natural Phase: `0000803F`.

The script now patches that blob field directly for `zero-latency` and
`natural-phase`, so you do not need to manually expose or map a Live plugin
parameter for each Pro-Q instance. It only writes when the Pro-Q blob matches
the known-safe VST3 shape: exact `ProcessorState` length, expected header,
expected tail, and one of the known old mode values at offset `1260`.

One thing the first fixture made tempting was patching `ControllerState`, too,
because that fixture happened to contain strings like `zero latency` and
`natrual phase`. A wider read-only scan showed that field commonly contains
other UI/device labels such as track or device names. The utility intentionally
does not edit `ControllerState`.

Read-only safety scan, May 16, 2026:

- 60 recent non-backup `.als` files scanned.
- 398 FabFilter Pro-Q devices found.
- Every scanned Pro-Q `ProcessorState` had the expected 1456-byte length.
- Every scanned Pro-Q `ProcessorState` matched the structural header/tail
  markers used by the script.
- The known mode offset contained only the two learned values:
  `00000000` or `0000803F`.
- No mismatched known blob shapes were found in that sample.

Linear-phase resolution modes are not implemented yet. They need additional
cloned fixtures, one per target mode, so we can identify the exact bytes without
guessing.

Code layout:

- `ableton_file_utilities/ableton_file_utilities/core/`: gzip/XML file handling and shared Ableton traversal.
- `ableton_file_utilities/ableton_file_utilities/plugins/`: plugin-specific adapters, one folder per plugin family.
- `ableton_file_utilities/ableton_file_utilities/plugins/proq3/`: FabFilter Pro-Q 3 state model, VST3 blob adapter, and phase command.
- `ableton_file_utilities/ableton_file_utilities/plugins/saturn2/`: FabFilter Saturn 2 VST3 blob adapter and quality command.
- `ableton_file_utilities/ableton_file_utilities/plugins/curve_bender/`: UAD Curve Bender planning and Pro-Q conversion command.
- `ableton_file_utilities/ableton_file_utilities/plugins/migration/`: one-time migration helpers for Windows-saved plugin devices.
- `ableton_file_utilities/ableton_file_utilities/commands/`: cross-plugin workflows such as one-shot live preparation.

## UAD Chandler Curve Bender Conversion

`write_curve_bender_to_proq.py` writes Curve Bender plans into Pro-Q 3 instances
as zero-latency bands. It first looks for the nearest unused Pro-Q in the same
device chain or track container. If there is no local Pro-Q, it clones a known
Pro-Q device block, remaps Ableton IDs, writes the translated bands into the
clone, and removes the original Curve Bender device.

```powershell
python "ableton_file_utilities\write_curve_bender_to_proq.py" "C:\path\to\Song.als"
python "ableton_file_utilities\write_curve_bender_to_proq.py" "C:\path\to\Song.als" --output "C:\path\to\Song - proq.als"
python "ableton_file_utilities\write_curve_bender_to_proq.py" "C:\path\to\Song.als" --proq-template "C:\path\to\TemplateWithProQ.als"
```

Current mapping rules:

- Linked Curve Bender channels become stereo Pro-Q target bands.
- Mid/side Curve Bender channels become Mid and Side target bands.
- Unlinked non-mid/side channels currently map left to Mid and right to Side,
  matching the low-latency live-set workflow.
- Curve Bender normalized gain values are doubled when written to Pro-Q, based
  on visual calibration against the plugin's response.
- Zero-gain EQ bands are skipped instead of creating disabled or phantom bands.
- Bell Q starts at `0.50`; high-Q / `x1.5` bell Q starts at `1.00`.
- Shelf Q starts at `0.20`.
- High-pass and low-pass filters are represented as `6 dB/oct` filters with
  Q `0.70`.

The Pro-Q writer is structured through `ProQ3State`, which owns the binary
`ProcessorState` and exposes band CRUD operations:

- `list_bands()`
- `replace_bands(...)`
- `add_band(...)`
- `update_band(...)`
- `delete_band(...)`

Unknown stepped Curve Bender knob positions are reported as skipped values
rather than guessed. Add paired fixture sets before expanding those maps.

## FabFilter Saturn 2 Quality Mode

`switch_fabfilter_saturn_quality.py` scans an Ableton `.als` file for FabFilter
Saturn 2 VST3 devices and changes the quality mode.

```powershell
python "ableton_file_utilities\switch_fabfilter_saturn_quality.py" "C:\path\to\Song.als" --mode high-quality
python "ableton_file_utilities\switch_fabfilter_saturn_quality.py" "C:\path\to\Song.als" --mode super-high-quality --write
python "ableton_file_utilities\switch_fabfilter_saturn_quality.py" "C:\path\to\Song.als" --mode normal --output "C:\path\to\Song - normal saturn.als"
```

Supported mode names:

- `normal`
- `high-quality`
- `super-high-quality` / `highest-quality`

A three-instance fixture in `codex_test.als` showed that Saturn 2 stores this
mode as a four-byte float in the `ProcessorState` blob:

- `ProcessorState`: quality float at offset `2804`.
- Normal: `00000000`.
- High Quality: `0000803F`.
- Super High Quality: `00000040`.

The script only writes when the Saturn 2 blob matches the known-safe VST3 shape:
exact `ProcessorState` length, expected header, expected tail, and one of the
known quality values at offset `2804`.

## One-Shot Live Preparation

`live_prepare.py` combines the low-latency live-set transforms:

- switches every FabFilter Pro-Q 3 VST3 device to zero latency;
- switches every FabFilter Saturn 2 VST3 device to the requested quality mode
  (`normal` by default for lowest latency);
- converts UAD Chandler Curve Benders into Pro-Q bands and removes the original
  Curve Bender devices.

It refuses to overwrite the source set or an existing output file.

```powershell
python "ableton_file_utilities\live_prepare.py" "C:\path\to\Song.als" --output "C:\path\to\Song_live.als"
python "ableton_file_utilities\live_prepare.py" "C:\path\to\Song.als" --saturn-mode super-high-quality --json
python "ableton_file_utilities\live_prepare.py" "C:\path\to\Song.als" --proq-template "C:\path\to\TemplateWithProQ.als"
```

## Plan for Vendor Blob Editing

This will probably matter for FabFilter, UA, Soundtoys, iZotope, and other
plugins where Live stores most of the meaningful settings inside the plugin's
private state blob.

The approach should be incremental:

1. Add a blob inventory step that extracts plugin blobs per device, records the
   plugin name, format, blob size, and whether the blob looks compressed,
   base64-like, hex-like, or raw binary embedded in XML.
2. For each plugin family, create paired before/after fixtures from a tiny set:
   one instance with only the target setting changed. Diff those decoded blobs
   to identify the smallest stable byte range or structured field.
3. Build vendor adapters that know how to decode, patch, re-encode, and validate
   exactly one plugin family/version. Keep these adapters separate from the
   Ableton XML traversal code.
4. Add guardrails before writing: verify the plugin identity, expected blob
   shape, expected old value, output size/checksum rules, and a successful
   decompress/reparse when applicable.
5. Keep every write reversible: dry run by default, timestamped backups for
   in-place writes, JSON reports, and eventually a fixture test per adapter.

In practice, the next useful command is probably an `inspect` mode that reports
all third-party plugins and exports their candidate state blobs to a folder.
That gives us the raw material to learn the FabFilter format without guessing.

## Windows Plugin Migration

`migrate_windows_plugins.py` plans or patches Ableton plugin references that
were saved on Windows and then opened on macOS. It was added for one-time
machine migration cleanup, so it is deliberately conservative: report-only by
default, patched-copy output only, and plugin-specific blob edits only where a
fixture-backed migration has been calibrated.

```powershell
python "ableton_file_utilities\migrate_windows_plugins.py" "C:\path\to\Song.als" --scanner "C:\path\to\PluginScanner.txt"
python "ableton_file_utilities\migrate_windows_plugins.py" "C:\path\to\Song.als" --scanner "C:\path\to\PluginScanner.txt" --output "C:\path\to\Song_mac_plugin_patch.als"
python "ableton_file_utilities\migrate_windows_plugins.py" "C:\path\to\Song.als" --scanner "C:\path\to\PluginScanner.txt" --json
python "ableton_file_utilities\migrate_windows_plugins.py" "C:\path\to\Song.als" --reference-set "C:\path\to\MacPluginTemplates.als" --target-format VST3 --plugin OTT --plugin Permut8 --plugin SieQ
```

Current classification and patch rules:

- `windows-vst2-path-restore-failure`: the saved device points at a Windows
  `.dll`, but Ableton has scanned a Mac VST2 with the same ID. The patch rewrites
  only `<Path>` to the scanned `.vst` bundle path and preserves the saved state.
- `windows-vst2-name-and-path-restore-failure`: same as above, plus a saved
  Windows-only plug name such as `OTT_x64`. The patch rewrites `<Path>` and
  `<PlugName>` while preserving the saved VST2 ID and state.
- `windows-vst3-class-id-mismatch`: Ableton has scanned a same-name/same-vendor
  Mac VST3, but the saved Windows-era VST3 class ID differs. The patch rewrites
  `BranchDeviceId` and the VST3 `Uid` fields while preserving
  `ProcessorState`, `ControllerState`, and the visible `ParameterList`.
- `vst3-template-clone-with-parameter-map`: a Windows VST2 device is replaced
  with a known-good Mac VST3 template device from `--reference-set`. Ableton IDs
  are remapped, the source device on/off state is preserved, and visible
  `PluginFloatParameter` values are copied by normalized parameter name.

Current fixture-backed VST2-to-VST3 state migrations:

- `elysia nvelope`: visible parameter mapping has been enough for the checked
  concrete_live instances.
- `OTT`: visible parameters are copied and the VST3 `ProcessorState` float list
  is rewritten so the plugin UI opens with the same values.
- `Permut8`: the source VST2 bank buffer and active program number are
  transplanted into the VST3 wrapper state.
- `Sie-Q`: the Soundtoys VST2 preset buffer is transplanted into the VST3
  wrapper state after cloning a known-good Sie-Q VST3 template.

Anything outside those calibrated paths should be treated as report data first,
then promoted only after paired Windows/Mac fixtures prove the mapping.

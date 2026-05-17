# Ableton Utilities

Small Python utilities for editing Ableton Live set files.

## FabFilter Pro-Q Phase / Latency Mode

`switch_fabfilter_proq_phase.py` scans an Ableton `.als` file for FabFilter
Pro-Q plugin devices and changes the processing mode.

Examples:

```powershell
python "Ableton Utilities\switch_fabfilter_proq_phase.py" "C:\path\to\Song.als" --mode zero-latency
python "Ableton Utilities\switch_fabfilter_proq_phase.py" "C:\path\to\Song.als" --mode natural-phase --write
python "Ableton Utilities\switch_fabfilter_proq_phase.py" "C:\path\to\Song.als" --mode zero-latency --output "C:\path\to\Song - zero latency.als"
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

- `ableton_utilities/live_set.py`: gzip/XML file handling and PluginDevice traversal.
- `ableton_utilities/proq3_vst3.py`: FabFilter Pro-Q 3 VST3 `ProcessorState` validation and byte patching.
- `ableton_utilities/proq3/state.py`: Pro-Q 3 state model with band list/replace/add/update/delete operations.
- `ableton_utilities/curve_bender.py`: UAD Curve Bender parameter parsing and conversion planning.
- `ableton_utilities/cli.py`: command-line reporting and write orchestration.

## UAD Chandler Curve Bender Inspection

`inspect_curve_bender.py` reads UAD Chandler Limited Curve Bender VST3
parameters that Ableton exposes in the XML and turns them into a normalized EQ
plan.

Example:

```powershell
python "Ableton Utilities\inspect_curve_bender.py" "C:\path\to\Song.als"
python "Ableton Utilities\inspect_curve_bender.py" "C:\path\to\Song.als" --json
```

`write_curve_bender_to_proq.py` is the first Pro-Q writer proof. It expects one
Curve Bender and at least one Pro-Q 3 in the set, then writes the Curve Bender
plan into the first Pro-Q 3 instance as zero-latency bands. It does not remove
or replace the original Curve Bender device yet.

```powershell
python "Ableton Utilities\write_curve_bender_to_proq.py" "C:\path\to\Song.als"
python "Ableton Utilities\write_curve_bender_to_proq.py" "C:\path\to\Song.als" --output "C:\path\to\Song - proq.als"
```

Current mapping rules:

- Linked Curve Bender channels become stereo Pro-Q target bands.
- Mid/side Curve Bender channels become Mid and Side target bands.
- Unlinked non-mid/side channels currently map left to Mid and right to Side,
  matching the low-latency live-set workflow.
- Zero-gain EQ bands are skipped instead of creating disabled or phantom bands.
- Normal bell/shelf Q starts at `0.50`; high-Q / `x1.5` starts at `0.75`.
- High-pass and low-pass filters are represented as `6 dB/oct` filters.

The Pro-Q writer is structured through `ProQ3State`, which owns the binary
`ProcessorState` and exposes band CRUD operations:

- `list_bands()`
- `replace_bands(...)`
- `add_band(...)`
- `update_band(...)`
- `delete_band(...)`

The frequency maps are intentionally narrow for now. Unknown stepped Curve
Bender knob positions are reported as skipped values rather than guessed. Add
paired fixture sets before expanding those maps.

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

# `.pwxf` (i1Profiler workflow) format — reverse-engineered mapping

This is the working reference for adding `.pwxf` export to ChromIQ (TI2 editor
"Save As → i1Profiler workflow"). It was derived from **14 genuine i1Profiler
1.1.0 exports** supplied by Nelson (the "ArgyllCMS … ti1-pxf-pwxf" set), all
verified as authentic, unmodified `X-Rite - Prism` CxF3 output. See
`workflow/i1profiler_export.py` for the existing `.pxf` writer this builds on.

## TL;DR

A `.pwxf` **is the same CxF3 file as our `.pxf`**, with two additions:

1. A **fuller `<xrp:CustomAttributes>`** element — adds page geometry, the
   patch grid (`NumberPatchColumns/Rows/Pages`), patch sizes, device, and
   measurement mode. Our `.pxf` only emits a ~12-attribute subset.
2. **Optional per-patch `<cc:TagCollection Name="Location">`** giving each
   patch a `Column`/`Row`/`Page` on the i1Profiler grid.

Everything else (root element, `FileInformation`, the `Object` list, the
`ColorSpecificationCollection`, and the `<ProfileSettings>` block) is byte-for-byte
the structure we already generate.

## What is verified vs. constant

### Patch data — fully verified, lossless
- Objects are emitted in **exact `.ti1` order**. All 9 "576-patch" `.pwxf`
  files and the `.pxf` reproduce the supplied `.ti1`'s 576 patches in order,
  identical RGB. i1Profiler preserves order on import/export.
- RGB conversion: `round(argyll_0..100 / 100 * 255)` → `<cc:R/G/B>` 0..255.
  (Same `_to_255_int` we already use.)

### Header / spec blocks — constant boilerplate (identical across all 14 files)
- `<cc:FileInformation>`: `Creator` = `X-Rite - Prism` (ours says `ChromIQ` —
  keep ChromIQ unless an import test shows i1Profiler rejects it),
  `Description` = `Prism CXF3 file`, plus two tags
  `PrismAppName="i1Profiler"` / `PrismAppVersion="1.1.0"`.
- `<cc:ColorSpecificationCollection>` → `Colorimetric_Reflectance` /
  `UnknownGeometry=Target`. Identical in every file; we already emit this in
  `_color_specification()`.
- `<ProfileSettings>` block — constant; identical to what `_profile_settings()`
  already produces.

## The layout knobs — `<xrp:CustomAttributes>`

Of ~71 attributes, **55 are constant** across all files and 16 vary. Only the
varying ones carry layout/device intent:

| Attribute | Meaning | Observed values | Source in ChromIQ |
|-----------|---------|-----------------|-------------------|
| `MeasurementDevice` | spectro, free string | `i1Pro 2`, `i1Pro 3`, `i1iO 2` | user picks (dropdown) |
| `MeasurementMode` | scan mode | `1` = single scan, `2` = dual scan | user picks |
| `PaperFormat` | page preset | `0` = Custom, `2` = A4 | from chosen paper |
| `PaperOrientation` | `Portrait` / `Landscape` | both seen | from layout |
| `PageWidth` / `PageHeight` | **imageable area, mm** (not always the physical sheet — see gotcha) | e.g. `296.93`×`210.06` (A4), `175`×`130` (custom) | layout / paper |
| `NumberPatchColumns` | grid columns | 12–39 | computed (see grid) |
| `NumberPatchRows` | grid rows | 11–24 | computed (see grid) |
| `NumberPatchPages` | sheets | 1–4 | computed |
| `PatchSizeWidthValue` / `PatchSizeHeightValue` | patch size, **mm** | 6.0–10.0 | layout |
| `PatchSizeWidthPercent` / `PatchSizeHeightPercent` | same as % of cell; **derived, sometimes `0`** | — | derive or 0 |
| `UseLegacyTestChart` | older chart engine | `True`/`False` | set `False` |
| `UsePatchSettingDefaults` | let i1Profiler auto-size patches | `True`/`False` | `True` is safest |
| `ProfileFilename` | output profile path | empty in all | leave empty |

Constant attributes worth knowing: `ColorSpace="RGB"`, `TestChartType="RGB Variable"`,
`ScramblePatches="False"`, `WriteProtected` / `LockWriteProtection` (we set
`WriteProtected="True"` in `.pxf` to stop i1Profiler re-generating patches — keep
that), `InkLimit="300"`, `WorkflowStep="TestChart"`,
`WorkflowType="PrinterProfilePro"`, `numberCorePatches=<N>`,
`TitleString` (free text, shown in i1Profiler).

> Note: our current `.pxf` writes `MeasurementScanningMode="Strip"`, which does
> **not** appear in any real file — i1Profiler uses the integer `MeasurementMode`.
> The `Strip` attribute is almost certainly ignored on import.

## The grid (`Location` tags)

When present, each Object gets:

```xml
<cc:TagCollection Name="Location">
  <cc:Tag Name="Column"     Value="0"/>
  <cc:Tag Name="Page"       Value="1"/>
  <cc:Tag Name="Row"        Value="0"/>
  <cc:Tag Name="SampleID"   Value="-1"/>
  <cc:Tag Name="SampleName" Value=""/>
</cc:TagCollection>
```

- **One grid, filled column-first, then cut into pages** (corrected 4.3.19,
  study of 2026-10-27). i1Profiler lays out ALL `N` Objects (= `.ti1` order)
  as ONE grid of `C = NumberPatchColumns` columns and `R = ceil(N / C)` rows,
  column-major: entry `i` is at column `i // R` and global row `i % R`. Only
  then are the rows cut into pages, shared out evenly with the larger shares
  first (`R` rows on `P` pages: `R // P` each, the first `R % P` pages one
  more). The tag's `Page` counts from 1, `Row` (on that page) and `Column`
  from 0. `NumberPatchRows` is the rows of the FIRST page, not `R`.
  Verified on every Target object of pharmacist's genuine i1Profiler 3.8.6
  files (648 patches, 27 × 24 on one page: 648/648; 702 patches, 18 columns,
  39 rows on 3 pages of 13: 702/702) and on X-Rite's own
  `RGB_default-i1Pro.mxf` (2033 patches, 30 columns, 68 rows on 3 pages of
  23 + 23 + 22: 2033/2033). For one page this is the same as the older
  reading, which is why the 29×20 (i1Pro3) and 39×15 (i1iO single) charts
  agreed with it.
  - **What this file said until 4.3.19 was wrong for more than one page**:
    "`Column = i // NumberPatchRows`, `Row = i % NumberPatchRows`, `Page`
    advances when a sheet fills", i.e. filled page by page. That rule puts
    only 26 of the 702 patches of pharmacist's 3-page file in i1Profiler's
    cell. `write_pwxf(emit_locations=True)` followed it and now follows the
    measured rule (`i1p_location`, `i1p_page_rows` in
    `workflow/i1profiler_export.py`;
    `tests/test_i1profiler_turned_grid_check.py::test_write_pwxf_puts_every_patch_where_i1profiler_put_it`
    checks it against pharmacist's files and X-Rite's own `.mxf` when they
    are on disk). Nothing in
    ChromIQ writes Location tags itself; the probe scripts do.
  - X-Rite's `RGB_default-i1iO.mxf` (the i1iO table, 4 pages) does NOT follow
    this rule: of its 2033 patches only 71 are where the rule puts them and
    1962 are elsewhere. The i1iO lays its pages out by its own rules, and
    nothing here is claimed for it.
- **How many columns i1Profiler makes, handheld i1Pro 2 / i1Pro 3** (3.8.8
  measured for the cap and the page; the balancing step agrees with every
  grid seen so far, 20 of 20 cases, among them three of pharmacist's
  screenshots). `NumberPatchColumns` in a file that is LOADED is ignored;
  i1Profiler works the grid out itself, with patch width `w` and page
  width `W` in mm:

  ```
  max_cols = floor(min(241.5, W - 31) / w)   # the row cap, and 15.5 mm of page each side
  rows     = ceil(N / max_cols)
  cols     = ceil(N / rows)                  # "balancing": the rows evened out
  ```

  So the grid is not simply `max_cols` wide: 648 patches at 8.4 mm on a
  296.7 mm page give `max_cols = 28`, 24 rows, and then **27** columns
  (pharmacist's screenshot). The cap lies between 241.5 and 242.4 mm
  (8.05 mm patches gave 30 per row, 8.08 mm gave 29); a 420 mm page changed
  nothing, so the ruler is the limit and not the page, until the page is
  narrower than the cap plus 31 mm.
- **ChromIQ checks this grid on the way back** (4.3.19, §I.14): an `.mxf`
  measurement of the turned chart carries `NumberPatchColumns/Rows/Pages`
  and every Target's Location, and ChromIQ refuses it when they are not the
  grid its order file names (`reference_convert.cxf_measurement_to_ti3`
  writes them into the converted `.ti3` as `CHROMIQ_I1P_GRID`;
  `i1profiler_turned.grid_mismatch` compares them).
- `SampleID = -1` and `SampleName = ""` for **every** patch — the layout is
  purely positional, not name-keyed. We don't need to invent IDs.

**Presence is inconsistent** across the sample set (see table below) — it tracks
how far the chart was taken in i1Profiler before saving, not a clean version
flag. The three newest files (laid-out charts) and the older 572-set all carry
Location tags; the May-1 576 files don't.

| File group | Location tags? | `UseLegacyTestChart` | `UsePatchSettingDefaults` |
|------------|----------------|----------------------|----------------------------|
| 572-patch (Apr 27) | yes (572) | mixed | False |
| 576-patch i1Pro1/2 (May 1) | **no** | mixed | False |
| 576-patch i1Pro3 / i1iO2 (May 28) | yes (576) | False | mostly True |

**Answered since (i1Profiler 3.8.x, 2026-10-27):** it recomputes the grid
from page and patch size on load and ignores both our `Column/Row/Page` and
`NumberPatchColumns`, so (A) below is what ChromIQ does. The question as it
was first asked (needs an i1Profiler round-trip test — only Nelson could run
it): does i1Profiler **recompute** the grid from page+patch size on load and
ignore our `Column/Row`, or does it honour what we write? This decides
whether we:
- (A) emit no Location tags + let i1Profiler auto-lay-out (simplest, matches the
  May-1 files which still printed fine), or
- (B) compute and emit the column-major grid ourselves.

Recommend shipping **(A)** first (omit Location tags, set
`UsePatchSettingDefaults="True"`), and only add (B) if a test shows i1Profiler
needs an explicit grid.

## Patch size & header length (the slider-percent encoding)

When `UsePatchSettingDefaults="False"`, i1Profiler **ignores** `PatchSize*Value`
and reads the size from the slider *percent*:

```
PatchSize*Percent = (mm - lo) / (hi - lo) * 100
```

`(lo, hi)` is the device's slider range — verified per device from workflow files
saved at each slider extreme (`_PWXF_DEVICES` in `ui/dialogs/tools_dialogs.py`):

| Device | W mm | H mm | Mode | Header length? |
|--------|------|------|------|----------------|
| i1Pro 2 | 7–25 | 8–12 | 1/2 | — |
| i1Pro 3 | 6–25 | 6–12 | 1/2 | — |
| i1Pro 3 PLUS | 16–40 | 16–20 | 1 | — |
| i1Pro 3 PLUS M3 | 16–40 | 16–20 | 6 | — |
| i1iO 2 / 3 | 6–20 | 7–20 | 1/2 | — |
| i1iO 3 PLUS | 16–40 | 16–40 | 1 | — |
| i1iO 3 PLUS M3 | 16–40 | 16–40 | 6 | — |
| i1iSis /2/XL/2 XL | 6–20 | 6–20 | 1 | **32–80 mm** |

- Writing `*Percent="0"` makes i1Profiler use the slider **minimum** (the old
  ChromIQ bug → 6 mm + "unscannable" warning). Always emit the real percent.
- **Scan minimum ≠ slider minimum.** i1Profiler warns below a device-specific
  scan minimum (i1Pro 3 = 7, i1iO 3 = 7.5, PLUS/M3 = 20 mm). Defaults sit at/above
  it (`_device_default_size`: 8×7, or 20×20 for PLUS/M3).
- **Measurement mode** is fixed for some devices (PLUS → 1, M3 → 6, i1iSis → 1);
  only i1Pro/i1iO offer the Single (1) / Dual (2) choice.
- **`HeaderEdgeSizePercent`** = the i1iSis "Vorlauf" / **header length** lead-in.
  Same percent encoding, reverse-engineered range **32–80 mm**
  (`(mm-32)/48*100`; verified 32→0, 56→50, 80→100). Non-i1iSis devices write the
  sentinel `-2147483648`. i1Profiler still computes the column/row grid itself
  either way.
  - **NOT user-controllable.** i1Profiler does not *persist* the lead-in: it
    resets to the 32 mm minimum on load regardless of the file's value —
    confirmed by re-saving i1Profiler's own 56 mm workflow and reopening it (also
    32 mm). So ChromIQ writes `0` (= 32 mm) for i1iSis and offers no UI for it.
    The range/formula above are kept only as documented knowledge.

## Gotchas

- **`PageWidth/Height` ≠ physical sheet.** The "A4" May-1 files are
  `296.9 × 240` mm (not 210×297) with `PaperFormat="0"` (Custom) — the user had
  set a custom imageable area. The true-A4 files use `296.93 × 210.06` with
  `PaperFormat="2"`. So width here is the long edge / imaging region; pin down
  exact semantics with an i1Profiler test before trusting it as the sheet size.
- **`*Percent` patch sizes are unreliable** (`0` in the i1iO single-scan file).
  Use the `*Value` (mm) fields; treat percent as derived/optional.
- **Filename ≠ internal device.** Nelson's `i1Pro1` and `i1Pro2` files all carry
  `MeasurementDevice="i1Pro 2"` (i1Profiler 1.1.0 only exposes "i1Pro 2"). Don't
  read the i1Pro generation from a filename; the device string is the truth.

## Implementation sketch

`write_pxf()` in `workflow/i1profiler_export.py` already produces the skeleton.
Add a `write_pwxf()` (or a `workflow=True` path) that:

1. Reuses `_pxf_open` / `_rgb_object` / `_color_specification` /
   `_profile_settings` unchanged.
2. Emits the **full** `<xrp:CustomAttributes>` with the 16 layout/device
   attributes above, fed from the TI2 editor's in-memory layout
   (paper, patch size, columns/rows/pages) + a device/mode dropdown.
3. Phase 1: omit `Location` tags, `UsePatchSettingDefaults="True"`,
   `UseLegacyTestChart="False"`. Phase 2 (if testing requires): emit the
   column-major grid.

Validate output with `xml.etree.ElementTree.parse()` (all 14 references are
well-formed) and diff RGB-in-order against the source `.ti1`.

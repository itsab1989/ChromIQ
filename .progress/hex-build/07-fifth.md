# Fifth adversarial review — #159 hexagon work

Reviewer: fifth round. Started 2026-09-09.
Target: commit `8c4c9b20` ("#159: the fourth review's five findings, including the sixth
self-validating test"), the fixes for the fourth round's H1-H5.
Bar: *would I sign this off to print on a paying customer's paper.*

Findings are numbered J1, J2, ... and appended as they are measured.
Everything below is written to disk as it happens; nothing is held in memory.

---

## J0 — setup and orientation (not a finding)

Tree state at start: `git status --porcelain` empty, HEAD =
`8c4c9b20b0617a78c290f714ca9d1b2e2315c97a`, branch `feature/nelson-photocard-presets`.
Verified with `git branch --show-current` and `git rev-parse HEAD`.

Read first: `06-fourth.md` (H1-H5), the full diff of `8c4c9b20`, the current
`workflow/layout_engine/geometry.py::patch_rects_px`, and the same function at
`964f0fd9` (the pre-lattice commit the H2 fix restores parity with).

Static observation, to be measured, not yet a finding: the H2 `else` branch is a
verbatim copy of the pre-lattice four lines (`_x0,_y0 = px(x_of(p)), px(y_of(j))
+ _stag; _x1 = px(x_of(p)+pwid); _y1 = px(y_of(j)+plen)+_stag`), so byte
identity for every non-hexagonal chart is *expected*. Measured below (J2).

## J1 — H2's fix VERIFIED, and far wider than the commit claimed. NOTHING FOUND

The commit says *"56 rectangular configurations are byte-identical to the
pre-lattice tree again"*. I did not take that number; I re-derived it.

Probe: `scratchpad/j2_rects.py`, run once against `/Users/Basti/develop/ChromIQ`
(HEAD `8c4c9b20`) and once against the existing worktree
`scratchpad/pre-lattice` (`964f0fd9`, the commit before the lattice). It calls
`geometry.patch_rects_px` directly — the function under review — and hashes
**all four fields** of every slot (`x,y,w,h`), not `y` alone (H3's blind spot).

Matrix: 8 instruments (i1, p3, CM, 41, 51, DTP20, SS, CR30) x spacers off/on x
ColorMunki row stagger off/on x `hflag` off/on x three chart sizes
(60 / 400 / 5000 patches, so **1 page and many pages**) x 13 papers (A4, A3,
Letter, all three landscape, Legal, Tabloid, 5x7, 4x6, 8x10, A5, 13x19) x 11
resolutions (72, 96, 150, 200, 240, 300, 360, 400, 600, 720, 1200).

```
configs 13728   slots 25,067,790   errors 0
differing configs: 1580   {SS: 786, CR30: 794}
classified by instruments.is_hexagonal(geom) — the branch condition itself:
  HEX configs total:      1716      differing & hex:   1580
  RECT configs total:    12012      differing & RECT:     0
```

**12,012 rectangular configurations and 0 disagreements, over 25 million slots.**
That includes the DTP41 Letter/Legal/Tabloid cases H2 named, multi-page charts
(5000 patches spills to 8+ pages), and the ColorMunki row stagger in both
states. The DTP41/Letter/300 dpi case H2 measured as 72 boxes wrong is now
hash-identical.

WHY IT MATTERS: this was H2's blocker and the commit's headline claim. It holds,
and it holds over 200x more ground than was claimed. Confidence: high.
Method note: the `else` branch is a verbatim copy of the pre-lattice four lines,
so identity is expected — the value of the measurement is that it proves no
*other* edit in the commit leaked into the rectangular path.

## J2 — the honeycomb path did not regress: the recorded box still frames the ink in BOTH orientations. NOTHING FOUND

`scratchpad/j3_ink.py` renders a real CR30 honeycomb (unique colour per patch,
`randomize=False`, coloured spacers), reads the TIFF, takes each patch's own
colour's exact bounding box and reports `(ink_left-box_left, ink_top-box_top,
ink_right-box_right, ink_bottom-box_bottom)` for every patch of page 1.

18 configurations: CR30 x {A4, A3, Letter} x {200, 300, 600} dpi x both
orientations. Method correction, recorded because it produced a false alarm
first: on a honeycomb the recorded box is the SLOT and the ink is a hexagon that
is inset by the spacer RING on its flat sides and OVERHANGS by a sixth of the
slot at its two apexes, so a zero delta is the wrong expectation. The right
question is whether the ink is CENTRED in the recorded box.

```
pointy (flat=0), A4 200 dpi:  (+5,-8,-4,+8) x165  (+5,-7,-4,+9) x135  (+5,-8,-4,+9) x89
turned (flat=1), A4 200 dpi:  (-7,+5,+9,-4) x154  (-8,+5,+8,-4) x153  (-8,+5,+9,-4) x66
pointy, A4 600 dpi:           (+15,-23,-14,+24) x89 … all four families within 1 px
turned, A4 600 dpi:           (-23,+15,+24,-15) x90 … all four families within 1 px
```

The turn flips the pattern exactly as it must: pointy insets left/right (ring)
and overhangs top/bottom (apexes); turned insets top/bottom and overhangs
left/right. Every family is symmetric to within 1 px (2 px in one 200 dpi
family, which is one `round()` on a half pixel at 0.127 mm). No patch is off by
a systematic amount and no patch is off by more than a pixel of its opposite
edge. Confidence: high.

Note on the seam figure my probe printed: it is NOT a seam count and I am not
reporting one from it. The trim it uses does not cope with a chart whose page 2
is nearly empty, so it counts real margin as "seam". A correct seam measurement
is J4.

## J3 — the honeycomb SHEET is bit-identical to the previous commit. NOTHING FOUND

`scratchpad/j4_seam.py` renders a full page-1 honeycomb and sha256s the TIFF, in
this tree and in a fresh worktree at `9db92b20` (the commit before the one under
review). CR30 x {A4, Letter} x 300 dpi x both orientations, coloured spacers:

```
ChromIQ    A4     flat=0  tif=3aacd2ebb6c7f59b     prev-9db9  A4     flat=0  tif=3aacd2ebb6c7f59b
ChromIQ    Letter flat=0  tif=f2f28834ad90a3df     prev-9db9  Letter flat=0  tif=f2f28834ad90a3df
ChromIQ    A4     flat=1  tif=3edcaaa941579b04     prev-9db9  A4     flat=1  tif=3edcaaa941579b04
ChromIQ    Letter flat=1  tif=74f730c64cb6104f     prev-9db9  Letter flat=1  tif=74f730c64cb6104f
```

4 of 4 identical. Expected from the diff (the `if _ss_hex:` block holds the same
four lines it had, and `raster.py` was not touched at all), and now measured.

## J4 — TRUE seam count on a FULL sheet: 0 over 24 configurations. NOTHING FOUND

Spacers **off**, so the hexagons abut and any bare paper inside the field is a
real gap; page 1 filled exactly to `layout.patches_per_page`; the field trimmed
1.5 patch widths/heights on each side to drop the legitimate zigzag border.
`scratchpad/j4_seam2.py`, CR30 x {A4, A3, Letter, A4 landscape} x
{150, 300, 600} dpi x both orientations:

```
24 configurations, 24 x SEAM=0.  Fields up to 5649x8595 px (A3 @ 600, 836 patches).
```

METHOD TRAP WORTH RECORDING, because I fell into it for twenty minutes: with
spacers ON, the coloured spacer palette **contains white**, so a
"all channels > 245 = bare paper" test reports 91,435 "seams" on a chart that is
perfectly tiled. I looked at the picture
(`10-fifth/J4-field-centre-pointy.png`, `-turned.png`) before believing the
number, and the pictures show a flawless honeycomb with white RING segments.
Any future seam probe must run with spacers off or exclude the palette.

The two pictures also settle the shape by eye: the pointy sheet has apexes up
and down with vertical flats; the turned sheet has flat top and bottom edges
with apexes left and right, and its columns run straight down. Both looked at.

## J5 — BLOCKER (paper): the changelog's DIRECTION is still wrong. A3 goes DOWN, and the sentence says it goes up

The commit dropped H1's four numbers and replaced them with a direction:

> *"which way depends on the paper: on A4 portrait it comes down by a few
> percent, and on A4 landscape, A3 and Letter it goes up."*

Driven on screen (`scratchpad/j5_drive.py`, sandboxed settings, real
`MainWindow`, Create Chart > Manual > CR30 > Hexagon, Expert Options expanded),
reading the layout information panel's ESTIMATE total with the turn off and on:

| paper | turn OFF | turn ON | direction | CHANGELOG says |
|---|---|---|---|---|
| A4 portrait | **390** | **374** | down 4.1 % | down — CORRECT |
| A3 portrait | **836** | **832** | **DOWN 0.5 %** | **up — WRONG** |
| Letter portrait | **360** | **378** | up 5.0 % | up — CORRECT |

(A4 landscape is item data `A4R`, not `A4_landscape`; measured separately, J5b.)

Cross-checked away from the GUI, at the library defaults
(`instruments.build("CR30", hflag=True, hex_flat_top=…)` + `geometry.compute`,
`scratchpad/j4_seam2.py` output): A4 390 -> 374, A3 836 -> 832, Letter
360 -> 378, A4 landscape 396 -> 390. **Both routes agree that A3 goes DOWN**,
and the fourth review's own on-screen table (H1) already recorded A3 836 -> 832
as well. Three independent measurements, one direction, and the changelog
states the opposite.

WHY IT MATTERS: this is the third wrong version of the same sentence, and the
fix that was supposed to make it unfalsifiable made a claim that is falsifiable
in one click. A user on A3 who reads "it goes up" and sees the number go down
learns that the release notes are not to be trusted. Severity: user-facing
documentation, no ink at risk. Confidence: high, measured twice by different
routes and agreeing with the previous reviewer's independent figure.

FIX: say "it can go either way by a few percent" and stop naming papers, or
name A4 portrait/A3 as down and Letter as up after re-measuring A4 landscape.

### J5, completed: TWO of the three papers named as "goes up" go DOWN, and the widget the sentence points at never moves at all

`scratchpad/j6_count.py`, same sandboxed real window, this time using the paper
combo's real item data (`A4R`, `LetterR`) and calling `tab._update_patch_count()`
explicitly after every change so no reading can be a stale widget:

```
  A4       estimate   390 ->   374 (DOWN -16)   CalculatedPatches '315!' -> '315!'
  A4R      estimate   396 ->   390 (DOWN  -6)   CalculatedPatches '315!' -> '315!'
  A3       estimate   836 ->   832 (DOWN  -4)   CalculatedPatches '315!' -> '315!'
  Letter   estimate   360 ->   378 (UP   +18)   CalculatedPatches '315!' -> '315!'
  LetterR  estimate   378 ->   360 (DOWN -18)   CalculatedPatches '315!' -> '315!'
```

The changelog names three papers as going UP: **A4 landscape, A3 and Letter**.
Measured, A4 landscape goes DOWN, A3 goes DOWN, and only Letter goes up. Two of
the three named directions are wrong, and A4 portrait (the one it calls down) is
the only other one it gets right. Confidence: high.

### J5b — SECOND HALF OF THE SAME BLOCKER: "Calculated Patches" is the wrong widget. It does not respond to the turn

The sentence ends *"read it off 'Calculated Patches' beside the preview rather
than from a number here"*. Measured above: **`_patch_count_lbl` reads `315` in
all ten states** — both orientations, all five papers.

Why, from the code (`ui/tabs/tab_chart.py:12645`): the big number is
`per_sheet * pages` where `per_sheet = self._engine_capacity(instr, paper, dd=…,
td=…, eff_lb=…, nsl=…, pscale=…, margin=…, guided=…)`. That builds a geom out of
the **printtarg/Guided widgets**, not the Manual layout recipe: no `hflag`
except via `dd`, no `hex_flat_top` at all, and the `paper` it reads is the
printtarg paper widget rather than the recipe panel's. The turn is a MANUAL-ONLY
control ("Create Chart, Manual, Expert Options" — the changelog's own words), so
the one number the release notes tell the user to watch is the one number in the
window that cannot see the setting.

The figure that DOES move is the "Chart layout information" panel's *Total
patches / estimate* column, which is a different box on the other side of the
window.

Picture: `10-fifth/J5-A-create-chart-counts.png` — looked at. The "Chart layout
information" panel is bottom right ("Total patches — 360"); "Calculated Patches"
is a separate group further down the left column.

WHY IT MATTERS: the H1 fix replaced four wrong numbers with a wrong direction
and a wrong pointer. A user following the instruction sees a number that never
changes and concludes the setting does nothing. Severity: user-facing
documentation. Confidence: high, driven on screen and traced to the code that
computes the label.

FIX: name the panel the number is actually in ("Chart layout information",
Total patches), and state the direction as "either way by a few percent" unless
someone is willing to re-measure and maintain a per-paper table.

## J6 — H5's fix WORKS on a real turned honeycomb, end to end in the real window. NOTHING FOUND

`scratchpad/j7_e2e.py`: sandboxed settings, real `MainWindow`, Create Chart >
Manual > CR30 > Hexagon, Expert Options expanded, "Straight strips (turn the
honeycomb 30°)" ticked, **Generate Chart pressed** (a real targen + engine
build, not a fabricated sidecar).

```
built ti2 : …/ChromIQ/HexFifth/runs/run1/HexFifth.ti2
sidecar recipe : {'instrument': 'CR30', 'hflag': True, 'hex_flat_top': True}
chart_is_flat_top(ti2) = True   chart_is_hexagonal = True
MEASURE  : pages 2, boxes 374, hex zigzag True, hex flat True
SCANNER  : grid rects 330, hexagonal True, hex_flat_top True, sample max 64 %
```

`10-fifth/J7-08-measure-preview.png` and the crop `J7-08b-…-zoom.png`, looked
at: the printed sheet is a flat-top honeycomb (flat horizontal top and bottom
edges, apexes left and right) whose columns run straight down the page, with
strip letters A..O across the top and rows 1..22 down the side. That is the
feature working.

The scanner window's sample-area cap reads **64 %** on the turned chart, which
is the number E4 says is right (the un-transposed pointy formula gives 63 %),
so `_clamp_sample_area` is getting the orientation too.

### J6b — the marquee's own cells, measured

`scratchpad/j8_mesh.py`, two real CR30 honeycombs, the chart's own page loaded
as the scan, reading `ScanGridMarquee._cell_uv()` back:

```
pointy : hexagonal True  hex_flat_top False  cell width/height = 0.8689   (sqrt(3)/2 = 0.8660)
turned : hexagonal True  hex_flat_top True   cell width/height = 1.1631   (2/sqrt(3) = 1.1547)
```

The two are reciprocals to within the ring inset. H5's fix is real.

### J6c — the attack cases the brief named

| case | hexagonal | hex_flat_top | verdict |
|---|---|---|---|
| honeycomb with **no recipe**, `create_chart_settings` says SS + `-h` | True | False | correct: a printtarg SS honeycomb is pointy, and `settings_are_hexagonal` is the only signal there is |
| recipe present, **`hex_flat_top` key missing** (a pre-#159 sidecar) | True | False | correct fail-closed: `recipe_is_flat_top` returns False and the chart keeps the behaviour it always had |
| **cached `_cell_uv` built before the orientation was known** | n/a | n/a | cannot happen: `ScanGridMarquee.set_grid` sets `self._cell_uv_cache = None` on every grid, and `set_sample_fraction` does the same |

Also checked: `GridSpec` has three other construction sites
(`GridSpec.from_cht`, `GridSpec([])` x3) and none of them can carry a
honeycomb — a captured `.cht` is never hexagonal by construction (printtarg
refuses to emit one for hexagons), so `hex_flat_top` defaulting to False there
is right. `ui/scan_grid_marquee.py` is the only non-engine module allowed to
hold the raw flag, and `test_no_reader_outside_the_engine_asks_the_flag_raw`
now lists it.

## J7 — BLOCKER (report): H4 IS NOT FIXED. The turned chart's COLUMN pitch is still printed under "Row pitch", one click after the build

The commit added `panel.set_pitch_axis(chart_is_flat_top(ti2))` to
`_update_layout_info` (the "on screen" column). That is half of what H4 asked
for, and the half that does not work, because **one row NAME serves both
columns** (`ui/chart_layout_info_panel.py:200`, `self._row_names["pitch"]`) and
the two callers race:

* `_update_layout_info` runs only when the PREVIEWED CHART changes
  (`_set_margin_chart`, `preview.page_changed`, line 18758);
* `_predict_layout_info` runs on every SETTINGS change, and in
  `_set_margin_chart` it is called *after* `_update_layout_info`
  (`tab_chart.py:17744-17750`), so the estimate's answer wins whenever the two
  disagree.

Driven on screen, `scratchpad/j9_pitch.py`. Real build through Generate Chart,
then **"Auto-update preview when a layout setting changes" switched OFF** —
which is the state the two-column panel exists for, and the state the fourth
review was in. (With auto-preview ON the chart silently rebuilds on every
change, so the two columns can never disagree and the fault is masked; that is
why my first pass did not see it.)

```
AFTER BUILD      name='Column pitch (mm)'  act_pitch=10.41  act_patch=13.89x12.02  chart_on_disk_is_flat_top=True
UNTICK THE TURN  name='Row pitch (mm)'     act_pitch=10.41  act_patch=13.89x12.02  chart_on_disk_is_flat_top=True
SWITCH TO i1     name='Row pitch (mm)'     act_pitch=10.41  act_patch=13.89x12.02  chart_on_disk_is_flat_top=True
```

PHOTOGRAPHED and looked at: `10-fifth/J9-2-after-untick-panel.png` shows, in the
"on screen" column, **"Patch size (mm) 13.89x12.02"** directly above
**"Row pitch (mm) 10.41"**. The sheet's rows are 12.02 mm apart. The same box
reports flat-top patch dimensions and a pointy-top pitch name at the same time.
`J9-3-i1-panel` is the same after switching the instrument to an i1.

This is G10's symptom, then H4's symptom, now for the third time, verbatim,
reachable in ONE click after building the feature's headline chart.

WHY IT MATTERS: it is report-only, no ink at risk, but it is a number Knut reads
off a screenshot (#B8-80 came in exactly that way) and it has now survived two
fixes. Confidence: high, driven and photographed, with the code path traced.

FIX (H4 already wrote it and only half was taken): give the two columns their
own name when they disagree, or name the axis in the VALUE rather than the row
(`_engine_info_line_from_recipe` already does exactly that: "patch 13.89x12.02
mm, column pitch 10.41 mm").

### J6d — the mesh ON THE INK, photographed, both orientations

`scratchpad/j10_overlay.py` takes `ScanGridMarquee._cell_uv()` out of the REAL
`ScannerProfileDialog` after `_set_chart` + `_load_page_grid` (no fabricated
GridSpec, no hand-passed flag) and draws those polygons on the chart's own
pixels at 3x.

* `10-fifth/J10-mesh-on-ink-pointy.png` — control: every yellow cell on its
  pointy hexagon, black sample rectangle inside.
* `10-fifth/J10-mesh-on-ink-turned.png` — the turned sheet: every yellow cell
  sits exactly on its FLAT-TOP hexagon, apexes left and right, no cell reaching
  into a neighbour.

LOOKED AT, both. This is the picture the fourth review photographed as wrong
(`08-fourth/D2`), and it is now right. H5: FIXED, confirmed by eye.

## J8 — reopening the project restores the turn and rebuilds the same SHEET. NOTHING FOUND (with one thing worth stating plainly)

`scratchpad/j11_reopen.py`: build a turned CR30 chart through Generate Chart,
close the window, open a FRESH `MainWindow`, load the project by its own
`project.json` through `TabChart.open_project_manifest`, and read the panel
back.

```
reopened: instrument CR30   mode hex   paper A4   TURN True   checkbox visible True
```

The stored recipes of the first build and the rebuild are **byte-identical,
all 100 fields, including `hex_flat_top: True`** (diffed programmatically:
`recipe differences: {}`).

The rendered TIFFs are NOT identical, and that is correct, not a defect: the
recipe carries `randomize: True, seed: None`, so each build draws a fresh
permutation. Measured separately to make sure the difference is only the
colour ORDER and not the layout — two builds of the same .ti1 with the same
recipe:

```
GEOMETRY (every patch x,y,w,h,loc, sha256) IDENTICAL: True
TIFF identical: False
```

So the sheet's geometry is reproducible and the pixels are not, by design.
Picture: `10-fifth/J11-reopened.png`.

## J9 — THE SEVENTH SELF-VALIDATING TEST: the test written for H5 asserts on SOURCE TEXT, and a mutation that restores H5 in full leaves it green

`tests/test_the_honeycomb_can_be_turned.py::test_the_scanner_mesh_is_told_the_
orientation_by_a_resolver` (new in `8c4c9b20`) is in three parts:

```python
assert "hex_flat_top" in {f.name for f in dataclasses.fields(GridSpec)}
src = inspect.getsource(scanin_dialog)
assert "flat_top=_flat" in src and "recipe_is_flat_top" in src   # <- the only link to the dialog
...
g = GridSpec.from_patches(pats, hexagonal=True, flat_top=flat)   # <- hand-built, flag passed by hand
assert out[True][0] > out[True][1]
```

The third part builds its own `GridSpec` and passes `flat_top=` by hand, so it
proves `GridSpec` + `_cell_uv` respond to the flag. It never runs
`_load_page_grid`, so **the only thing standing between a turned chart and a
pointy mesh is a substring search of the module's text** — and a substring
search cannot tell a live expression from a dead one.

MUTATION M1, PROVEN TO LAND. `ui/dialogs/scanin_dialog.py:4306`:

```
-            _flat = recipe_is_flat_top(self._layout.get("recipe"))
+            _flat = False   # MUTATION M1
```

Grepped back: the file still contains `recipe_is_flat_top` (1 occurrence, the
import) and `flat_top=_flat` (1 occurrence), so both substring assertions still
hold. `__pycache__` cleared across the tree.

PROVEN HARMFUL, on screen, before running the suite. `scratchpad/j10_overlay.py`
against the mutated tree, real `ScannerProfileDialog`, real turned CR30 chart:

```
turned: hexagonal=True  hex_flat_top=False   (was True)
```

and the picture `10-fifth/J12-MUTATION-M1-mesh-wrong.png` — **looked at** — is
H5 restored exactly: pointy cells 30 degrees off flat-top ink, apexes reaching
into the patches above and below. It is the fourth review's `08-fourth/D2`
again.

GATE RESULT WITH M1 IN PLACE: (recorded below when the run finishes.)

GATE RESULT WITH M1 IN PLACE — the FULL everyday tier, `-n auto`, on the
mutated tree with `__pycache__` cleared:

```
12475 passed, 310 skipped, 4 xfailed in 118.68s (0:01:58)
[exited with code 0]
```

**Green, exit 0, with the alignment mesh 30 degrees off the ink on every turned
honeycomb.** Nothing in 12,475 tests notices.

Why the neighbours miss it too, checked rather than assumed:

* `test_the_scanner_dialog_passes_the_orientation` (spacer-is-a-ring, line 650)
  is the same shape — `assert "flat_top=flat_top" in src` — and `_flat` is still
  handed to `_clamp_sample_area`, just always False;
* `test_the_sample_cap_is_the_same_number_on_a_turned_hexagon` calls
  `hex_max_sample_fraction` directly and never touches the dialog;
* `test_the_dialog_caps_the_spinbox_from_the_chart_it_loaded` DOES drive
  `_load_page_grid`, but only with **SpectroScan** charts (pointy), and its
  expected value re-implements the production call
  (`int(hex_max_sample_fraction(w, h) * 100)`) without `flat_top=`, so it would
  agree with the mutation even if it were given a turned chart. Its own sanity
  bound is `55 <= want <= 66`, and the mutation's answer is 63.

So the whole cluster is anchored on text, and no test anywhere loads a TURNED
chart into the dialog and asks what came out.

Severity: this is a TEST defect, not a shipped one — HEAD is correct (J6, J6d).
It matters because H5 was found by a reviewer with a camera, not by the suite,
and the test written to stop it happening again cannot. Confidence: high,
mutation proven to land, proven harmful on screen, and the full gate measured
green with it.

FIX: assert the OUTCOME, not the text. Build a turned honeycomb, run
`_load_page_grid`, and assert `d._marquee._grid.hex_flat_top is True` and
`d._sample_area.maximum() == 64` (the pointy formula gives 63, so the number
separates the two). Three lines, and it is red under M1.

### J9b — how narrow the H3 REPLACEMENT test is, measured

`test_the_lattice_change_moved_no_rectangular_chart` now pins all four fields,
which was H3's point and is a real improvement. What it inspects is
`rects[:steps * 2]` — **the first two strips of page 1**, on 5 instruments x
3 papers x 2 resolutions, at the default spacer state:

```
i1  A4      steps= 21 pages=1 rects= 378   test inspects  42 = 11.1 % of slots,  2/18 strips
p3  A4      steps= 10 pages=4 rects= 370   test inspects  20 =  5.4 % of slots,  2/11 strips
CM  A4      steps= 16 pages=4 rects= 368   test inspects  32 =  8.7 % of slots,  2/7  strips
41  A3      steps= 38 pages=1 rects= 380   test inspects  76 = 20.0 % of slots,  2/10 strips
51  Letter  steps= 18 pages=2 rects= 378   test inspects  36 =  9.5 % of slots,  2/14 strips
```

5.4 % to 20 % of the slots, always page 1, always strips 0 and 1. Two
consequences follow, and both are testable:

* **x is only ever checked on two strips.** Nothing pins strips 2..17.
* **the ColorMunki page parity is never exercised.** Production stages the row
  stagger on `((first // steps) + p) & 1`, the GLOBAL strip index — which is
  what `raster.py:1350` uses (`global_strip & 1`). On page 1 `first` is 0, so
  that expression collapses to `p & 1`, and `p & 1` is exactly what the test
  re-implements. A change from the global index to the local one is invisible
  to it, and it moves every odd page of a ColorMunki chart off the paint.

Two mutations, applied together, both grepped back
(`geometry.py:522 … if (p & 1) else 0)   # MUTATION M3`,
`geometry.py:587 _m2 = 1 if p >= 2 else 0   # MUTATION M2`), `__pycache__`
cleared:

* **M2** — every recorded box on strip 3 and beyond, on every rectangular chart
  in the app, moved one pixel right of its ink.
* **M3** — the ColorMunki row stagger indexed locally instead of globally, so
  every odd page's recorded boxes sit a stagger away from the paint.

GATE RESULT: (recorded below.)

GATE RESULT for M2 + M3 — **the suite CATCHES both, and this is a real and
welcome result.** Combined, the full everyday tier came out

```
2 failed, 12473 passed, 310 skipped, 4 xfailed in 116.30s
FAILED tests/test_layout_geometry.py::test_every_strip_rect_bounds_exactly_its_own_patches
FAILED tests/test_margin_check_knows_about_pixels.py::test_no_builtin_preset_breaks_its_own_declared_margins
```

Separated, one mutation at a time, `__pycache__` cleared between runs:

* **M2 alone** -> `test_no_builtin_preset_breaks_its_own_declared_margins` FAILED
  (`1 failed, 153 passed`).
* **M3 alone** -> `test_every_strip_rect_bounds_exactly_its_own_patches` FAILED
  (`1 failed, 157 passed`).

So although `test_the_lattice_change_moved_no_rectangular_chart` is blind to
both — it never fired in either run — the SUITE is not. The rect-geometry
neighbourhood is genuinely guarded; only the scanner-mesh neighbourhood (J9) is
not. I record the narrowness above as context for whoever widens that test, not
as a defect.

## J10 — nothing else found

Checked and clean, briefly:

* **The marquee has exactly one instance.** `ScanGridMarquee(self)` is
  constructed once (`scanin_dialog.py:2218`); "Pop out" reparents that same
  widget rather than making a second, so there is no second mesh to fall out of
  step. Its other `GridSpec` sources are `from_cht` (never hexagonal, by
  construction) and three empty `GridSpec([])`.
* **`hexagon.contains`'s flat-top branch** is the exact transpose of the pointy
  one (x and y exchanged, `t6 = w/6` instead of `ph/6`), and
  `TiffPreview._in_hexagon` passes `self._hex_flat_top` through. The Measure
  overlay reported `hex zigzag True, hex flat True` on the built turned chart
  (J6). Note for whoever next widens the tests:
  `test_the_hit_test_agrees_with_the_polygon_it_is_testing` only ever tests the
  POINTY orientation — it never passes `flat_top=True` — so the turned hit test
  has no ray-casting cross-check. Not a defect; a gap.
* **The owner's settings are untouched.** `defaults read com.chromiq.ChromIQ
  custom_output_path` -> the key does not exist, which is the user's own state
  (default `~/ChromIQ`); and `~/ChromIQ` contains nothing newer than 8 Sep, so
  none of the eight drivers wrote into it.
* **The tree.** HEAD moved during the review from `8c4c9b20` to `f45f5e17`
  ("write down the standing orders for the autonomous review loop"), which
  touches only `.progress/hex-build/*.md`. No source file changed, so
  everything above still describes the code under review. All three mutations
  reverted; `git diff HEAD --name-only` lists only this report.

  Cross-checked myself rather than left as a gap: ray-casting
  `hexagon.vertices(..., flat_top=True)` against
  `hexagon.contains(..., flat_top=True)` over six slot sizes and a 41x41 grid
  each, boundary ties skipped — **0 disagreements of 7,956 sampled points**. The
  turned hit test is correct; only its test is missing.

## J11 — the changelog's OTHER claims in that bullet, checked

Read the bullet line by line rather than only the sentence H1 was about.

| claim | verdict |
|---|---|
| *"Create Chart, Manual, Expert Options, Patches & spacers, and only while the instrument is a CR30 with Hexagon patches on"* | true: the checkbox reads "Straight strips (turn the honeycomb 30°)", `isVisible()` True on CR30+Hexagon (J6) |
| *"It is off unless you turn it on"* | true: a recipe with the key missing loads `hex_flat_top False` (J6c), and a fresh panel starts unticked |
| *"saved with the target ... like any other layout setting"* | true: reopened from `project.json`, the box comes back ticked and all 100 recipe fields round-trip (J8) |
| *"the same hexagon, the same size, stood on a flat side instead of a point, so nothing is stretched and each patch holds the same ink"* | true: the panel reports patch 12 x 13.86 mm pointy and 13.86 x 12 mm turned, an exact transpose; the built sheet reads 13.89 x 12.02 (pixel rounding) |
| *"every second patch in a strip no longer sits half a patch to the side, so a strip ... runs straight down the page"* | true, looked at: `10-fifth/J7-08b-measure-preview-zoom.png` |
| *"the number of patches on a sheet can move ... on A4 landscape, A3 and Letter it goes up"* | **FALSE for two of the three** (J5) |
| *"read it off 'Calculated Patches' beside the preview"* | **FALSE**: that widget never moves (J5b) |

So one bullet, five true statements and two false ones, and the two false ones
are the two the previous fix introduced.

### J5c — the two routes AGREE exactly, so the direction is not an artefact of the owner's saved defaults

A fair objection to J5 is that my sandbox copies the owner's real plist, so
"the app's own defaults" might not be the shipped defaults. Answered by a route
that touches no settings at all: `instruments.build(key, hflag=True,
hex_flat_top=…, spacer_on=False)` + `geometry.compute(g, w, h, 100000)`,
reading `layout.patches_per_page` (`scratchpad/j4_seam2.py`).

| paper | library route off -> on | app panel off -> on |
|---|---|---|
| A4 | 390 -> 374 | 390 -> 374 |
| A4 landscape | 396 -> 390 | 396 -> 390 |
| A3 | 836 -> 832 | 836 -> 832 |
| Letter | 360 -> 378 | 360 -> 378 |

**Identical on all four.** The direction is a property of the geometry, not of a
setting, and the changelog contradicts it on two papers either way.

(Worth noting against H1's own text, which said *"the three routes give three
different sets of numbers"*: these two do not — they agree exactly. Whatever
made the library figures differ in H1's measurement was in its kwargs, not in
the routes being incomparable. It does not change the finding.)

## J12 — the release gate, run once as asked

`source .venv/bin/activate; QT_QPA_PLATFORM=offscreen pytest --runslow -n auto -q`
on the reverted, clean tree (`git diff HEAD --name-only` = this report only):

```
12618 passed, 167 skipped, 4 xfailed in 219.79s (0:03:39)
[exited with code 0]
```

Exact tail. **No `[gwN] node down` banner, no `Fatal Python error`, no
`Timeout (0:0X:XX)!` dump.** 12,618 matches the count the commit message claims,
and 3:39 is inside the 3:15-3:59 band CLAUDE.md records for this host. The
167 skips are all in named buckets (141 "engine-built preset — printtarg not
used", 10 build-shape, 6 no ArgyllCMS, 4 uncategorised, 6 platform/helper/data).

## J13 — I chased a margin violation and it is NOT one. Recorded so nobody chases it again

The "would I print this on a customer's paper" bar says measure the INK against
the margin, so I did: `scratchpad/j12b.py` renders full CR30 honeycombs, finds
every non-white pixel and compares its bounding box against the 6 mm border, for
both orientations x {A4, A3, Letter, A4 landscape} x {200, 300, 600} dpi.

Every one of the 21 configurations reported ink **0.50-0.54 mm to the LEFT of
the border**, at every resolution, so not a rounding artefact.

Then I looked at it. `10-fifth/J13-left-edge.png`: it is the **row-number
labels**. "10" and "11" are two digits wide where the band was sized for the
patches beside it, so from row 10 down the numbers reach past the border.

Three things settle it as not a defect and not this branch's:

1. **The declared margin is to the first PATCH, not to any ink.** The app's own
   margin inspector on the very chart I built reads "Left (to first patch)
   13.5 mm, min 6.0" and prints **"Margins: OK"** in green
   (`10-fifth/J11-reopened.png`). Under the contract the app states, there is
   nothing over the line.
2. **It is not the turn.** Pointy and turned overflow by the same amount
   (-5.9 px at 300 dpi in both).
3. **It is not this branch.** The SpectroScan honeycomb — shipped long before
   #159 — overflows further, 0.75 mm, and is **byte-identical on master**
   (`master-tip` worktree at `7e500e59`: leftmost ink x=62 in both trees).
   Rectangular charts do not overflow at all (i1 and p3 clear the border by
   19.99 mm, the DTP41 by 0.01 mm).

My first pass at this probe also had its sign convention inverted on two of the
four edges and flagged the TOP, which is 22 px inside. Recorded because it is
exactly the "a probe that searches too wide finds its answer somewhere else"
failure, and the picture is what caught it.


---

# SUMMARY AND RELEASE VERDICT

## What was verified and is right (six "nothing found" results, stated plainly)

| | result |
|---|---|
| **H2, rectangular rects** | 12,012 rectangular configurations, **25,067,790 slots**, all four fields byte-identical to the pre-lattice tree `964f0fd9`. The DTP41 cases H2 named are hash-identical again. Fixed, and over 200x wider than claimed. |
| **The honeycomb sheet** | bit-identical (4/4 sha256) to the previous commit; **0 seams** on 24 full sheets; the recorded box frames the ink symmetrically to within 1 px in both orientations on 18 configurations. |
| **H5, the scanner mesh** | fixed. Photographed on real ink in both orientations from the real dialog. `hex_flat_top` reaches `GridSpec`, `_cell_uv` and the sample cap (64 % on a turned chart, where the pointy formula gives 63 %). The three attack cases (no recipe / missing key / stale cache) all fail closed correctly. |
| **The whole feature end to end** | built through Generate Chart, previewed, opened in Measure (374 boxes, hex flat True), opened in the Scanner window, project closed and reopened: the turn comes back ticked and the rebuild's recipe is byte-identical in all 100 fields. |
| **The turned hit test** | correct: 0 disagreements in 7,956 ray-cast samples (though it has no test of its own). |
| **Margins** | no violation. What looked like one is the row-number labels, is identical on master, and is outside the margin the app actually declares. |
| **The release gate** | `12618 passed, 167 skipped, 4 xfailed in 219.79s (0:03:39)`, exit 0, no worker-down banner, no timeout dump. |

## What is wrong

* **J5 — the CHANGELOG (blocker, paper).** The bullet names three papers as
  going up; **A4 landscape and A3 both go DOWN**, measured twice by independent
  routes that agree exactly. And it tells the user to read the change off
  "Calculated Patches", a widget that shows **315 in all ten states** because it
  is computed from the Guided/printtarg widgets and cannot see the Manual
  recipe. Third wrong version of the same sentence.
* **J7 — H4 is NOT fixed (blocker, report).** One row NAME serves both columns
  of the layout panel, and the estimate path runs last, so with "Auto-update
  preview" off the panel prints **"Patch size 13.89x12.02" above "Row pitch
  10.41"** for a flat-top chart whose rows are 12.02 mm apart. Photographed.
  G10, then H4, now again. The half of H4's own prescription that was skipped is
  the half that mattered.
* **J9 — THE SEVENTH SELF-VALIDATING TEST (blocker, test).** The test written
  for H5 links to the dialog only through `assert "flat_top=_flat" in src`.
  Changing that line's right-hand side to `False` restores H5 in full — proven
  on screen, photographed — and the **full everyday gate stays green: 12,475
  passed, exit 0**. Its neighbours miss it too, for reasons measured one by one.

Two things I checked and did NOT find: the H3 replacement test is narrow
(5.4-20 % of slots, page 1, strips 0-1 only) but the SUITE is not blind — two
mutations aimed at its blind spots were each caught by a different test.

## VERDICT: **HOLD.**

Not because anything prints wrong. Every measurement that touches paper, ink,
patch identity or the scanner's read area came out right, and the release gate
is green. If the only question were "would the sheet be correct on a paying
customer's paper", the answer is yes.

It is a hold because all three findings fall inside the standing orders'
own "fix without asking" list (`00-AUTONOMOUS-LOOP.md`): *anything in the
changelog that is untrue*; *anything that shows the user a number that
disagrees with the sheet in their hand*; *any test proved not to catch the
fault it exists for*. And by the loop's stopping rule, a round that returns
blockers is not a clean round.

All three are small and none needs new geometry:

1. one changelog sentence — say "either way by a few percent" and name the
   "Chart layout information" panel instead of "Calculated Patches";
2. give the pitch row its own name per column (or put the axis in the value, as
   `_engine_info_line_from_recipe` already does);
3. replace the substring assertion with three lines that load a turned chart
   through `_load_page_grid` and assert `hex_flat_top is True` and
   `_sample_area.maximum() == 64`. That is red under M1; the current test is not.

Fix those three, and on this evidence the next round should be the clean one.


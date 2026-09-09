# 04 — FINAL adversarial review before stable 4.2.1

Branch `feature/nelson-photocard-presets`, head `eab90e19`.
Started 2026-09-09. Findings appended as they are measured.

## F1 — P7 IS ONLY TWO-THIRDS FIXED: two readers still ask the recipe's `hex_flat_top` RAW, and both print a wrong patch size

`498f1698` created `hex_support.recipe_is_flat_top` ("the resolution now lives
once") and wired it into `tab_measure`, `scanin_dialog` and `margin_inspector`.
Grep of every `hex_flat_top` outside `instruments.py` / `presets.py` finds two
production readers it did not reach, both in `ui/tabs/tab_chart.py`:

* **`tab_chart.py:12551`**, `_engine_info_line_from_recipe` — the one-line
  summary of a saved layout preset:
  `if recipe_is_hexagonal(r) and getattr(r, "hex_flat_top", False):`
  `recipe_is_hexagonal` is True for the **SpectroScan** as well as the CR30, so
  the instrument gate the other three sites have is missing here.
* **`tab_chart.py:17935`**, `_chart_patch_size_mm` — the ACTUAL column of the
  Chart layout information panel, reading the built chart's sidecar:
  `bool((recipe or {}).get("hex_flat_top", False))` — completely raw, no gate at
  all.

Measured (`LayoutRecipe(instrument="SS", hflag=True, hex_flat_top=True,
patch_w_mm=8.0, patch_h_mm=6.93)`, which is exactly the state P7 describes: the
box is ticked on a CR30, the user switches to a SpectroScan, the control hides
and `_read_recipe` still stores `r.hex_flat_top = self.hex_flat_top_cb.isChecked()`):

```
recipe_is_flat_top(r)                 -> False     (builder truth: pointy)
tab_chart:12551 raw test               -> True      (wrong)
raw sidecar read (tab_chart:17935)     -> True      (wrong)
_panel_patch_size_mm(8.0, 6.93, True, True)  -> (10.67, 6.93, 8.00)  "column pitch"
_panel_patch_size_mm(8.0, 6.93, True, False) -> ( 8.00, 9.24, 6.93)  "row pitch"
```

So on a SpectroScan honeycomb carrying a stale tick, the panel and the preset
summary tell the user the patch is **10.67 x 6.93 mm with a column pitch of
8.00** when the ink on the paper is **8.00 x 9.24 mm with a row pitch of 6.93**.
Both numbers wrong, both axes wrong, and the LABEL wrong. This is precisely the
defect P7 named ("the margin inspector moved the apex allowance to the wrong
axis"), one level over.

Severity: reporting only, no ink moves. But it is a *number a user reads off the
screen to decide whether the chart fits his instrument*, and the fix is one
import in each of two lines. **Fix before stable.**
Confidence: high (measured on the shipped functions).

## Gate (priority 5) — GREEN

`QT_QPA_PLATFORM=offscreen pytest --runslow -n auto`, head `eab90e19`, clean tree:

```
========== 12562 passed, 167 skipped, 8 xfailed in 211.17s (0:03:31) ===========
EXIT=0
```

No `node down` banner, no `Fatal Python error`, no `Timeout (0:0X:XX)!` dump
anywhere in the log (grep count 0). Nothing found.

## F2 — the P6 fix HOLDS: 72 rendered configurations, no patch ink outside any margin

Sweep written for this review (patches rendered pure RED so patch ink can be
separated from text, the clip band and the ruler comb — no other test here does
that; every existing margin test measures "any pixel darker than 250"):

* instruments CR30 and SS x `hex_flat_top` False/True
* margins (20,20,20,20) and the asymmetric (8,30,25,12)
* patch sizes: auto, 12.12x14.0, 20.0x17.32, 8.0x8.0, 25.0x9.0 (deliberately
  stretched both ways)
* layout modes: patch_first, area_first/by_width, area_first/by_grid (8x12)
* papers A4, A3, Letter
* 300 dpi, all pages of each build measured, tolerance 0.12 mm

**72 of 72 OK.** Closest approach to a margin over the whole sweep was
`CR30-ft1-m1-areaW` at top 10.329 mm against an 8.0 mm margin, i.e. 2.3 mm
inside. The two SpectroScan halves (`SS-ft0` vs `SS-ft1`) produced
BYTE-EQUAL numbers on all 18 pairs, which independently re-proves the
instrument gate: the turn cannot reach a SpectroScan.
(Script: scratchpad/sweep_margin.py.)
Confidence: high.

## F3 — `hexagon.inset` INVERTS when the ring is wider than the patch's inradius, and the sheet then prints far outside the margin

The rewrite makes the ring exactly the width asked for on all six sides of any
convex hexagon (measured below, P5 is genuinely fixed) — but it has **no upper
bound**, and past the inradius the six moved edge-lines cross the centre and
the "inner" polygon comes back INSIDE-OUT and GROWING.

Pure-function measurement, pointy hexagon w=12.0, ph=10.392 (the CR30 default),
`inset(pts, d)` signed area:

```
d =   0.500  area  +104.786
d =   2.000  area   +55.423
d =   4.000  area   +13.855
d =   5.196  area    +2.239
d =   6.000  area    +0.000     <- inradius: collapsed to a point
d =  10.000  area   +55.428     <- growing again, point-reflected
d = 100.000  area +30608.859
```

The polygon stays *simple* (a hexagon is centrally symmetric, so the inversion
is a 180-degree rotation, not a bow-tie), which is why nothing downstream
notices.

**IT REACHES PAPER.** `_ring = pspa` and `d = _ring_px / 2`, and the Manual
"Spacer size" spin box is `sb.setRange(0, 300)`
(`layout_options_panel.py:444-446`) with no honeycomb-specific clamp anywhere
(`grep hex_ring_mm` finds exactly three lines, none of them a limit). Built
CR30 A4 honeycomb, all four margins 20.0 mm, spacers Coloured, 200 dpi,
patch ink rendered pure red so it can be isolated:

```
spacer size   red patch ink, distance to page edge (top/left/bottom/right, mm)
      1.3 mm   31.50 / 20.57 / 24.38 / 148.46      OK
      6.0 mm   34.16 / 22.99 / 27.05 / 150.75      OK
     12.0 mm   37.72 / 25.91 / 30.61 / 153.80      collapsed (115 red px left)
     14.0 mm   36.58 / 25.02 / 29.46 / 152.91      INVERTED, patch is a dot
     40.0 mm   21.46 / 11.94 / 14.35 / 139.83      *** 8.1 mm OUTSIDE the margin
    300.0 mm    0.00 /  0.00 /  0.00 /   9.91      *** floods the sheet edge to edge
```

Rotated is the same: `hex_flat_top=True`, spacer 40 mm -> left 10.67 mm against
a 20 mm margin, 9.3 mm outside.

**It is hexagon-specific.** The identical CR30 chart with `hflag=False` and the
same 40 mm and 300 mm spacers stays inside every margin (left 19.94 mm both
times) — a bar spacer grows the pitch and costs patches, which is safe; a ring
comes out of the patch and inverts.

Looked at the picture (scratchpad/ringbig/sw40.0.png): a single red blob roughly
50 x 210 mm covering the row numbers and running past the left margin, and
sw14.0.png is a solid cyan column with one red dot per patch. So a user who
typed 40 would see it. A user who typed 13 on a 12 mm patch would see a chart
that merely looks "very heavily spaced" and is in fact geometrically inverted.

This is the same class as P6 — *ink outside the user's margin* — from a value
the UI offers. It is not a regression introduced by `eab90e19`; the previous
centroid-scaling `inset` inverted at the same point. It is a hole in the ring
feature (`8d3c3806`) that the rewrite did not close.

Minimal fix: clamp `d` in `inset` (or `_ring_px` in `raster`) to just under the
polygon's min apothem, i.e. `min over edges of |(centroid - edge point) . n|`,
which `inset` already computes. Two lines.
**Blocks stable in my view** — anything that puts ink outside a margin the user
typed is the exact bar the last round set.
Confidence: high (rendered and looked at).

## F4 — the `inset` rewrite (P5) HOLDS on paper, and on a stretched hexagon

Ring width measured on the RENDERED sheet at 1200 dpi (1 device px = 0.0212 mm),
patches red, spacer cyan, walking outward along each of the six edge normals from
an interior patch of strip 1 and counting the spacer run. Spacer size 1.5 mm, so
each half-band is 0.75 mm.

```
config              slot mm            six ring widths (mm)                 spread
regular-pointy      20.003 x 17.314    .7514 .7303 .7514 .7514 .7514 .7514  0.0212
stretched-pointy    20.003 x 12.002    .7514 .7303 .7514 .7514 .7514 .7514  0.0212
squashed-pointy     12.002 x 20.003    .7514 .7514 .7514 .7197 .7303 .7197  0.0317
regular-flat        17.314 x 20.003    .7514 .7303 .7514 .7514 .7514 .7514  0.0212
stretched-flat      12.002 x 20.003    .7514 .7303 .7514 .7514 .7514 .7514  0.0212
```

Spread is 1 to 1.5 device pixels, i.e. rasteriser quantisation. The slot sizes
were read back from the sidecar to prove the stretch was actually built (a
20.0 x 12.0 mm slot is 39 % off the natural sqrt(3)/2 proportion). The pre-fix
scaling version was measured by the last round at 40 % out on two of six sides;
it is now within one pixel on all six, on both orientations. **Nothing found.**

Pure-function checks on `inset` that came back clean: a square insets exactly
(1,1)-(9,9) from (0,0)-(10,10); all-identical vertices return the input (the
`L == 0` guard); a `w=0` or `ph=0` hexagon does not raise. A NON-CONVEX input
(a dart) produces a wrong polygon, but the docstring says "convex polygon" and
no shipped caller passes anything else, so that is documentation, not a defect.

One genuine wart: **collinear consecutive edges abandon the whole polygon**, not
just that vertex — `abs(det) < 1e-12` returns `list(pts)`, so `inner == outer`,
the ring silently becomes zero-width and the spacer vanishes with no error. Not
reachable from `vertices()` at any non-degenerate slot size, so it is a latent
trap rather than a defect. Ship.

## F5 — the `_stag` row-label fix (P8) HOLDS, including the odd-strips-per-page case that E7 was about

Measured per ROW rather than by comparing the two orientations' centroids (the
shipped test's method cancels a common-mode error; this one cannot). For each
page the row-label band is thresholded, split into connected y-clusters, and
each cluster matched to the patch it names. 600 dpi.

```
config            page  rows  clusters  mean residual   max |residual|
cr30-pointy         0    26      26       +1.088 mm       1.143 mm
cr30-rotated        0    22      22       +0.943 mm       0.974 mm
ss-pointy           0    45      45       +0.619 mm       0.656 mm
cr30-rot-multi      0    22      22       +0.943 mm       0.974 mm
cr30-rot-multi      1    22      22       +0.943 mm       0.974 mm
cr30-rot-multi      2    22      22       +0.943 mm       0.974 mm
cr30-poi-multi    0/1/2  26      26       +1.088 mm       1.143 mm
```

Cluster count equals row count on every page, so no label is doubled or lost.
The residual is the digit-glyph baseline bias (a numeral's ink centroid is not
its box centre); pointy and rotated differ by **0.145 mm**, against the 3.006 mm
fault P8 named and a quarter-pitch of 3.0 mm.

**The multi-page case has teeth**: `cr30-rot-multi` lays 17 strips per page,
an ODD number, and the recorded strip-0 patch y is **401 px on page 0 and 543 px
on page 1** — a difference of 142 px, exactly `h/2` (h = 284). So page 1's first
strip really is staggered the opposite way, the E7 condition is live in this
build, and the labels tracked it: identical residual on all three pages.

The ColorMunki rig-stagger half of the brief **cannot be measured this way and
is not a gap**: the CM geometry has `rlwi = 0`, so a CM sheet has no row-label
band at all (measured: zero label clusters on `cm-stagger` and `cm-plain`, and
on `i1-plain`). `_stag` there only moves patches, and the patches are placed
from the same variable.
Nothing found.

## F6 — the sample-area cap (E4) SHIPS: verified on screen in the real dialog

`scripts`-style driver (scratchpad/drive_sample_cap.py): real `QApplication`,
Basti's preferences copied to a throwaway .ini, `custom_output_path` inside a
temp tree, `QDialog.exec` and the four `QMessageBox` statics patched, four real
charts built by the engine with their sidecars, then a real
`ScannerProfileDialog` shown and `_set_chart()` called on each. Read straight
off the widget:

```
chart                          Sample area maximum   tooltip
CR30 honeycomb, ROTATED               64             "Hexagonal patches: 64 % ..."
CR30 honeycomb, pointy                64             "Hexagonal patches: 64 % ..."
SpectroScan honeycomb, pointy         64             "Hexagonal patches: 64 % ..."
CR30 RECTANGULAR                      80             (none)
```

64 both ways up (which is the point of E4 — the pointy formula on the transposed
slot floors to 63) and 80 on a rectangular chart. Looked at the grabbed window;
the "Patch sample area" spin box shows 60 % with the cap above it.
Nothing found.

## F7 — REGRESSION: no rectangular chart moved by a single pixel

39 non-hexagonal configurations x 64 rendered pages, sha256 of every page TIFF
plus `strips.json` plus `.ti2`, at 150 dpi:
instruments i1, i1Pro3, ColorMunki, DTP41, SpectroScan, CR30, each in
plain-A4 / plain-A3 / coloured-spacer / asymmetric-margins / hand-set patch size
/ area-first, plus CM rig-stagger, CM double density and an i1 clip border.

Compared against **two** baselines:

* the worktree the brief named, `478c7396` — 0 page mismatches, 0 strips
  mismatches, 0 `.ti2` mismatches once the `CREATED` timestamp and the random
  `CHART_ID` are excluded (39/39);
* and, because `478c7396` turns out **not to be an ancestor of this branch**
  (it is the head of `feature/182-compliance-sets`; `git merge-base` is
  `7e500e59`), also against `e1aeaf2f`, the real parent of the first hexagon
  commit — again 0 mismatches over the same 39 cases and 64 pages.

Nothing found.

## F8 — the ring DOES change an existing CR30 honeycomb, and the SpectroScan honeycomb has never had a spacer at all

Two measured facts a release note has to carry, neither of them a defect:

1. `hex_capable("CR30")` is already True at `e1aeaf2f`, so CR30 honeycombs are
   not new in this branch. What changed is the spacer: at `e1aeaf2f`
   `build("CR30", hflag=True, spacer_on=True)` gives `pspa = 1.3` (a bar in the
   pitch); at HEAD it gives `pspa = 0.0, hex_ring_mm = 1.3` (a ring inside the
   patch). A CR30 honeycomb project rebuilt in 4.2.1 therefore does NOT come
   back byte-identical, and its patch count changes, because a ring costs no
   page. That is Basti's ruling of 2026-09-09, so it is intended.
2. **A SpectroScan honeycomb has no spacer at all, and never had.** Its
   `_build_base` branch hard-codes `pspa=0.0`, and `build()` only honours the
   Spacer size box when `geom.pspa > 0`. Measured: `build("SS", hflag=True,
   spacer_on=True, spacer_width=1.3)` -> `pspa 0.0, hex_ring_mm 0.0`, and four
   rendered SS honeycombs (spacers off / coloured / black-and-white / edge
   spacers on) produced **one single page hash between them**, identical before
   and after the branch. Pre-existing, not a regression, but it means every
   Spacers control is inert on a SpectroScan honeycomb — see F9.

## Priority 2 — the five findings that were NOT acted on. All five re-measured at `eab90e19`; all five still live.

### F9 — P1, "Inter-patch gap" is still a DEAD control on a honeycomb, and a duplicate of Spacer size when they are on. **WART, can ship, but grey it.**

Re-measured on HEAD (CR30 A4 honeycomb, 210 patches, 300 dpi, no randomise):

```
inter_patch  spacer mode   grid    geom.pspa  hex_ring_mm  page sha256
   0.0 mm      none        9x26      0.000      0.000      c16a002b5fb0e581
   2.0 mm      none        9x26      0.000      2.000      c16a002b5fb0e581
   8.0 mm      none        9x26      0.000      8.000      c16a002b5fb0e581
   0.0 mm      colored     9x26      0.000      1.300      fbcae56422a44f81
   2.0 mm      colored     9x26      0.000      3.300      2b224167bbfeb0bf
   8.0 mm      colored     9x26      0.000      9.300      3ea2a6efa3060ab2
```

Byte-identical sheets for 0, 2 and 8 mm with spacers off — which is the CR30's
shipped default (`presets.default_recipe` sets `spacer_mode="none"`). The
RECTANGULAR control responds properly (10x23 -> 11x20 at 2 mm), so this is
honeycomb-only. With spacers on it is not dead but it is no longer a *gap*: it
adds into the ring and so does exactly what Spacer size does.

**Verdict: a wart.** Nothing wrong reaches paper; the sheet is correct, the
control is a lie. But it is one `setVisible(False)`/`setEnabled(False)` in
`_sync_*_visibility` away from honest, it is the same defect class this branch
set out to fix one control to the left, and a customer who types 4 mm and prints
gets a sheet identical to the one he was trying to change. Fix it if the release
can carry a three-line UI change; do not hold the release for it.

### F10 — P2, the Margin Inspector is still 0.879 mm OPTIMISTIC with edge spacers on. **DEFECT, fix before stable.**

`margin_inspector.measure_from_engine` still widens the box by
`round(_g.pspa * dpi / 25.4)` and `_g.pspa` is 0.000 on every honeycomb
(`"_g.pspa * dpi" in source` -> True at HEAD). Re-measured, CR30 A4, spacers
Coloured, 300 dpi, edge spacers off then on:

```
                          top      left    bottom    right
pointy  real ink   off   7.874    5.503    8.805    82.211
        real ink   ON    7.874    5.503    7.281    80.857   (ink moved 1.524 / 1.355 mm out)
        REPORT     off  15.198   14.393    8.160    81.645
        REPORT     ON   15.198   14.393    8.160    81.645   (moved 0.000 mm)

rotated real ink   off   7.705    5.503   10.583    89.747
        real ink   ON    7.705    5.503    9.229    88.223   (ink moved 1.355 / 1.524 mm out)
        REPORT off/ON   16.933   13.504    9.980    89.054   (identical)
```

With edge spacers on the tool claims **8.160 mm** of bottom clearance where the
ink leaves **7.281 mm**. The one tool whose entire job is telling the user
whether the ink clears the paper edge is wrong in the unsafe direction, on a
honeycomb, by 0.879 mm. On `e1aeaf2f` the same recipe had `pspa = 1.3` and the
allowance was applied, so this IS a regression of the ring commit.
The right allowance is the apex displacement of the outward band (measured
1.524 mm for a 1.3 mm ring, not `ring/2 = 0.65`), and it is on the axis the
apexes point along, which the flat-top branch immediately below already knows
how to choose.

**Verdict: defect. Fix before stable.**

### F11 — P3, the scanner Sample-area cap still does not know the ring exists, and the honest cap is 51 %, not 64 %. **DEFECT, fix before stable (one line).**

`grep ring` over `ui/dialogs/scanin_dialog.py` and `workflow/scanin_runner.py`
finds nothing: the cap is still computed from the recorded SLOT
(`p["w"], p["h"]`), which is the hexagon BEFORE the ring is taken out of it.

Quantified at HEAD for the shipped CR30 honeycomb with the shipped 1.3 mm ring:

```
slot                       12.000 x 10.392 mm   cap 0.644338 -> UI 64 %
ink hexagon after the ring 10.700 wide, 12.355 tip to tip
   ... as an equivalent slot 10.700 x  9.266 mm
safe fraction OF THE SLOT the dialog measures         0.512293 -> UI 51 %
```

So the dialog offers, and defaults to, a read box **13 percentage points larger
than the ink can support**. The previous round integrated the contamination at
2.336 % of the read area at 64 % with a 1.3 mm ring, 5.8 % at 2 mm and 18.0 % at
3 mm, and in "Black & white" that contamination is solid black on every patch of
the sheet at once.

Mitigating: it needs spacers switched ON (off by default on the CR30) and the
scanner path, which is itself behind the Preferences -> Beta opt-in. Not
mitigating: the fix is to hand `hex_max_sample_fraction` the inset hexagon's
dimensions instead of the slot's, which is a handful of lines in
`_clamp_sample_area`, and the failure mode is silent bad colour data, not a
visible error.

**Verdict: defect. Fix before stable.**

### F12 — P9, the layout panel still calls the COLUMN pitch "Row pitch". **WART, but see F1 — fix them together.**

`ui/chart_layout_info_panel.py:86` still hard-codes
`("pitch", tr("Row pitch (mm)"))`, and `grep -rn "Column pitch"` over the tree
returns nothing. `_panel_patch_size_mm`'s own docstring hands the naming
obligation to the caller ("which is why the caller has to name it") and no
caller discharges it.

On its own: a wart. Taken with **F1**, the same panel tells a rotated or
stale-flag honeycomb user three wrong numbers (the patch width, the pitch value
and the pitch's name), and F1 is a defect. Fix the three together.

### F13 — P10, `contrast.ring_for_mode` is still dead, and the low-contrast guard still walks `zip(col, col[1:])`. **WART, can ship — but delete the dead function.**

`grep -rn ring_for_mode --include=*.py .` (excluding `.venv`) returns exactly one
line, `workflow/layout_engine/contrast.py:75`, its own `def`.
`min_boundary_contrast` (contrast.py:113) is unchanged: `for a, b in
zip(patch_rgbs, patch_rgbs[1:])`, i.e. consecutive patches within a pass only,
which was complete cover for a bar and is 35-36 % of the joins a ring paints.

No demonstrated miss (the previous round could not build a target that trips the
guard on a hidden join), so the coverage half is a latent gap, not a bug.
The dead half is worse than harmless: 33 lines with a four-paragraph docstring
explaining a mechanism the renderer does not use will be read as truth by the
next person.

**Verdict: wart. Ship. Delete `ring_for_mode` in the tidy-up commit.**

## Priority 3 — the whole feature end to end, on screen

Driver `scratchpad/drive_e2e.py`: real `QApplication` + `MainWindow`, settings
sandboxed to a throwaway `.ini` BEFORE any ChromIQ import, `custom_output_path`
inside the sandbox, `QDialog.exec` and the four `QMessageBox` statics patched,
Expert Options expanded explicitly before every grab.

```
1 Create Chart, Manual, CR30, Hexagonal
    "Straight strips (turn the honeycomb 30 deg)" visible (expert open): True
    on screen: CR30 / hex / flat_top True / spacer colored
    -> built 345 patches, 1 page, recipe hex_flat_top=True in the sidecar
2 Print tab renders the sheet
3 Measure: 1 page, 345 boxes, preview _hex_zigzag True, _hex_flat_top True
    hit test on 40 randomly chosen patches: 0 wrong
      (centre inside AND all four recorded-rect CORNERS outside, on every one)
    highlight on H12 sits on its hexagon (looked at 05_highlight_H12.png)
4 Close, reopen the project in a FRESH MainWindow via `open_project_manifest`
    reopened panel: instr CR30, shape hex, flat_top True, spacer colored,
    the turn checkbox visible again
```

The settings come back. **Nothing found in the feature itself.**

Two things seen while doing it, both traced OUT of this branch:

* **F14 (out of scope, pre-existing).** After reopening a project, "Auto"
  beside the patch count comes back UNTICKED with the count reading 0, and
  pressing Generate rebuilds a **16**-patch chart where the project holds 525,
  or **14** where it holds 351 — while the app's own log line says *"Restored
  the chart's own layout settings ... and patch count now show the values this
  chart was made with."* Reproduced on a RECTANGULAR i1 chart as well
  (525 -> 16), and reproduced **identically on the `e1aeaf2f` worktree**, i.e.
  before the first hexagon commit. Not this branch's, but somebody should own
  it: the message and the behaviour disagree, and the direction is destructive.
  Confidence: high that it reproduces; medium that it is a bug rather than an
  intended "start from a clean count", because the log line asserts otherwise.
* the honeycomb seams (bare paper at the three-way vertices) are visible by eye
  at the default 300 dpi. They are already carried as a **strict xfail** in
  `test_a_honeycomb_has_no_seams_between_its_patches` with a full account of
  three attempted fixes. Re-measured here on a 345-patch A4 with the tests' own
  no-white palette: pointy 432 px, rotated 244 px with spacers on
  (432 / 254 with them off), so the ring did not cause it and the numbers agree
  with the docstring's sweep. Honest, deferred, and it is a **named caveat for
  the release**, not a new finding.
  (My first count said 60,648 px: the DEFAULT spacer palette contains white, so
  legitimate white spacer bands read as bare paper. Corrected before reporting.)

## Priority 6 — mutation testing of what was just added

Twelve mutations, each proven to be a UNIQUE anchor, applied, re-read from disk
to prove the text landed, `__pycache__` cleared, then run against the eight test
files that cover this work (`test_the_honeycomb_can_be_turned`,
`test_the_honeycomb_spacer_is_a_ring`, `test_the_hexagon_is_drawn_from_one_place`,
`test_hex_scanner_support`, `test_cr30_registration`, `test_helper_markers`,
`test_a_hexagon_is_taller_than_its_row_pitch`, `test_layout_presets`;
baseline **735 passed, 4 xfailed in 17.3 s**).

CAUGHT (4): M2 `inset` grows instead of shrinking; M4 the resize block's
flat-top reserves swapped back; M6 `side_neighbours`' `up` parity flipped;
M8 `recipe_is_flat_top` drops its `recipe_is_hexagonal` clause;
M10 the ring drawn at `_ring_px/2.5`. (5, counting M10.)

DISCARDED as an EQUIVALENT mutant, honestly: **M3**, deleting the inward-normal
flip in `inset`. It changes no output at all on any shipped polygon — the
`(-ey/L, ex/L)` normal already points inward for the vertex order `vertices()`
produces. The guard is dead defensive code, not a hole in the tests.

SURVIVED (6), each proven below to change what the user gets:

### F15 — M9: flipping `hexagon.stagger_dy`'s SIGN makes half the shared spacers TWO-TONE and the whole suite stays green. **The fourth self-validating test.**

Mutation: `dy = -ph*0.25 if strip % 2 == 0 else ph*0.25` -> the two swapped.

Proven to land: the rotated page TIFF hash changes (`d0230287...` ->
`706ceca7...`), so does `strips.json`, and `stagger_dy(100, 0..3)` goes
`[-25, 25, -25, 25]` -> `[25, -25, 25, -25]`.

Proven to MATTER, measured on a rendered 600 dpi sheet with a no-white palette:
for every pair of patches closer than 1.15 pitch, sample the shared band 8 px
either side of the midpoint of the line joining their centres (the band is
30.7 px wide at 600 dpi, so both samples are inside it) and compare.

```
                      unmutated            with M9
pointy honeycomb    0 of 533 two-tone    0 of 533
ROTATED honeycomb   0 of 538 two-tone    268 of 537 two-tone
```

**Half of every diagonal spacer on a rotated sheet comes out in two different
colours**, which is precisely the failure `side_neighbours`' docstring and
`test_the_pair_rule_is_symmetric_so_the_two_halves_agree` exist to prevent
("the two halves read as ONE shared spacer, which is what Basti asked for").

Caught by: **nothing.** 735 passed on the eight hex files, and
**12,419 passed, 310 skipped, 8 xfailed** on the whole everyday tier.

WHY. `test_every_side_names_the_patch_it_actually_faces` is the test that owns
this, and it RE-IMPLEMENTS the stagger inside itself
(`tests/test_the_honeycomb_spacer_is_a_ring.py:250-255`):

```python
def centre(p, j):
    if flat_top:
        return (p * w + w / 2, j * ph + ph / 2
                + (-ph / 4 if p % 2 == 0 else ph / 4))
```

It never calls `hexagon.stagger_dy`. So the "geometry" it checks
`side_neighbours` against is a hand copy of the convention, and a change to the
shipped convention moves the renderer and leaves the test's idea of the lattice
where it was. Two halves of one contract, pinned to each other by nothing.
The fix is one line: build `centre()` from `hexagon.stagger_dy` /
`hexagon.stagger_dx`.

**This is the fourth self-validating test in this work**, after the three the
author found and rewrote. Confidence: high.

### F16 — M1: the sample-area cap's ONE production caller is unprotected, and the test that guards it greps source text

Mutation: in `scanin_dialog._load_page_grid`, replace
`recipe_is_flat_top(self._layout.get("recipe"))` with `False`.

Proven to matter ON SCREEN, same driver as F6:

```
                   unmutated   with M1
CR30 ROTATED          64          63     <- the exact defect E4 was written to fix
CR30 pointy           64          64
SpectroScan pointy    64          64
CR30 rectangular      80          80
```

Caught by: **nothing** (735 on the hex files, 12,419 on the everyday tier).
`test_the_scanner_dialog_passes_the_orientation` asserts
`"flat_top=flat_top" in inspect.getsource(_clamp_sample_area)` and that the
signature has the parameter. Both remain true: the mutation is one function up,
in the CALLER, and the argument it passes is what E4 was about. The commit
message says *"with the call site itself asserted, because a cap that is right
in the function and never asked for is not shipped"* — the call site is
asserted as TEXT, and the text is in the wrong function.
Fix: assert the cap on the widget, which F6 shows takes four lines.

### F17 — M5: the margin inspector's flat-top apex axis is unpinned

Mutation: `w_px = max(r["w"] ...)` -> `max(r["h"] ...)` in
`margin_inspector.measure_from_engine`'s flat-top branch — i.e. the branch
`498f1698` added to fix P7's second half.

Proven to land: reported margins on a rotated honeycomb move from
`left 13.6313, right 120.1263` to `left 13.3562, right 119.8512` (0.275 mm on
both edges, in the unsafe direction on the left).

Caught by: **nothing** (735 / 12,419). The new flat-top branch has a test for
which axis it expands but nothing that pins the magnitude to the right rect
dimension.

### F18 — M7: the cap can round UP, against its own comment, on 154 of 350 patch shapes

Mutation: `int(frac * 100.0)` -> `round(frac * 100.0)` in
`_clamp_sample_area`, on the line whose own comment reads
`# floor: never round UP`.

Proven to land: swept `hex_max_sample_fraction(12.0, h)` for h = 2.5 to 20.0 in
0.05 steps, `int()` and `round()` disagree on **154 of 350** shapes — e.g. a
12.00 x 4.55 mm slot gives 65.988 %, floored to 65 and rounded to **66**. One
point above the safe maximum, and the function's own docstring says the limit is
"not a rate but a switch: a box one percent too big samples the neighbour on
EVERY patch" (measured 0 of 150 at 60 %, 150 of 150 at 70 %).

Caught by: **nothing** (735 / 12,419). Reachable through the Manual patch-size
boxes on any honeycomb.

### F19 — M11: the rotated patch WIDTH shown in Chart layout information is unpinned (33 % error survives)

Mutation: `return (hex_patch_width_mm(w), h, w)` -> `return (w, h, w)` in
`tab_chart._panel_patch_size_mm`'s flat-top branch.

Proven to land: `_panel_patch_size_mm(10.392, 12.0, True, True)` reports the
patch width as **10.392 mm** instead of **13.856 mm** — the whole 4/3 correction
this branch added for the turn, gone.

Caught by: **nothing** (735 / 12,419). Same panel as F1 and F12.

### F20 — M12: the flat-top HIT TEST's slope is unpinned

Mutation: `left = x0 - t6 + dy * 2.0 * t6` -> `dy * 1.0 * t6` (and the mirror
for `right`) in `hexagon.contains`, i.e. the flat-top branch's edge slope.

Proven to land: over a 27 x 27 sample grid across the slot, points reported
inside a flat-top hexagon go from **253 to 294**, a 16 % larger click region
whose extra area is the slot's four corners — exactly the region `contains`
exists to exclude ("a click in a corner selected a patch whose ink is not
there, 7.2-7.7 % of the click area and 86-92 % of corner clicks").
The pointy branch is unchanged, so the pointy path is protected and the
rotated one is not.

Caught by: **nothing** (735 / 12,419).

## F21 — the v4.2.1 CHANGELOG says NOTHING about ten commits of user-visible hexagon work. **Blocks a stable tag.**

`core/version.py` is `APP_VERSION = "4.2.1"` and the `## v4.2.1` section of
`CHANGELOG.md` is 70 lines long. Grepped for `hex|honeycomb|CR30|spacer|ring`
inside that section: every hit is about the photo-card presets and the
instrument-memory fixes. Nothing about

* the CR30 honeycomb turned 30 degrees ("Straight strips"), a new control;
* the spacer becoming a RING around each patch instead of a bar between rows,
  which changes every existing CR30 honeycomb with spacers on and changes its
  patch COUNT (see F8);
* the ruler comb a honeycomb keeps changing from top/bottom to the sides;
* the scanner Sample-area cap now knowing the orientation.

`grep -in "straight strip\|turn the honeycomb"` over the whole file returns
nothing. Ten commits, `1f4ff390..eab90e19`, none of them in the release notes.
The project's own release process names the changelog as a required step.

## Settings hygiene — clean

Every driver in this review exported `CHROMIQ_SETTINGS_FILE` before any ChromIQ
import (the sandbox banner appears in each run's log), and `custom_output_path`
was pointed inside a temp tree in each sandbox.

```
$ defaults read com.chromiq.ChromIQ custom_output_path
                       (empty string — the user's own value, meaning "use ~/ChromIQ")
$ ls -l ~/Library/Preferences/com.chromiq.ChromIQ.plist
-rw------- 16900  9 Sep 05:22        (the session began at 07:40; not touched)
```

## Also seen, NOT this branch's

* The "Build profile with scanner or camera" push button in the scanner window
  clips its own label ("ild profile with scanner or came" in the grab). Measured
  in both trees at a 1300 px dialog: **button width 286 px, sizeHint 320 px**,
  so it is 34 px narrower than its own minimum. Byte-identical numbers on
  `e1aeaf2f`, so pre-existing and unrelated. Cosmetic.

### M9 also survives the FULL RELEASE GATE

```
QT_QPA_PLATFORM=offscreen pytest --runslow -n auto   (with M9 applied)
12562 passed, 167 skipped, 8 xfailed in 229.05s (0:03:49)
```

Byte-for-byte the same counts as the clean tree. So the two-tone-spacer
mutation is invisible to every test ChromIQ has, slow tier included.
Tree reverted and verified clean (`git status --porcelain` shows only this
report).

---

# RELEASE VERDICT

## DO NOT SHIP as a stable 4.2.1 — yet. Four items, none of them large.

The five fixes since the last round are real and I could not break any of them:

* **P6** — swept 72 rendered configurations (2 instruments x 2 orientations x
  2 margin sets x 6 patch-size/layout modes x 3 papers) and no patch ink leaves
  its margin anywhere. **F2.**
* **P8** — measured per row, per page, including a chart with an ODD 17 strips
  per page where the E7 fault is live: labels track their strips to 0.145 mm
  against a 3.0 mm fault. **F5.**
* **P5 / `inset`** — the ring is the width the user asked for on all six sides
  of a hexagon stretched 39 % out of proportion, to within one device pixel at
  1200 dpi. **F4.**
* **E4** — verified ON SCREEN in the real dialog: 64 % rotated, 64 % pointy,
  80 % rectangular. **F6.**
* **P7** — fixed in the three places `498f1698` touched.
* Rectangular charts are untouched: 39 configurations, 64 pages, sha256-identical
  against two baselines. **F7.**
* The gate is green: **12562 passed, 167 skipped, 8 xfailed, exit 0**, no
  worker-down banner, no timeout dumps.

### What blocks the tag

1. **F21 — the changelog.** Ten commits of user-visible change (a new control,
   a spacer that changes shape and changes patch counts on existing projects)
   and not one line in the `## v4.2.1` section. This is the cheapest of the
   four and the least defensible to ship without.
2. **F3 — `inset` inverts past the inradius and prints outside the margin.**
   The Spacer size box accepts 0-300 mm with no honeycomb clamp; at 40 mm on a
   CR30 A4 honeycomb the patch ink reaches 11.94 mm inside a 20 mm margin, and
   at 300 mm it floods the sheet edge to edge. Rectangular charts are immune.
   Two lines: clamp `d` to just under the polygon's min apothem.
3. **F1 (+ F12) — the layout panel lies about a honeycomb's patch size.** Two
   readers still take `hex_flat_top` raw, so a SpectroScan honeycomb carrying a
   stale tick is reported as 10.67 x 6.93 mm with a "column pitch" when it
   prints 8.00 x 9.24 mm with a row pitch — both numbers, both axes and the
   label all wrong. This is P7, one level over, in the panel P7's own commit
   message cites. Two imports.
4. **F10 + F11 — the two tools that are supposed to keep the user safe are
   both wrong in the unsafe direction on a honeycomb.** The margin inspector
   overstates the bottom clearance by 0.879 mm with edge spacers on (a
   regression of the ring commit), and the scanner Sample-area cap offers 64 %
   where the ink after a 1.3 mm ring supports 51 %. Both are small changes and
   both are exactly the class of finding this branch's own commit messages say
   they exist to prevent.

### Ship-with-caveat once those are in

* **F9** — the Inter-patch gap box is dead on a honeycomb with spacers off
  (byte-identical sheets at 0, 2 and 8 mm) and duplicates Spacer size with them
  on. Grey it when you can; it does not change what prints.
* **F13** — `contrast.ring_for_mode` is 33 lines of documented dead code;
  delete it. The low-contrast guard covers about a third of a ring's joins,
  with no demonstrated miss.
* **The 300 dpi honeycomb seams** — bare paper at the three-way vertices, 432
  px (pointy) and 244 px (rotated) on an A4 at the DEFAULT resolution. Already
  a strict xfail with an honest account of three attempted fixes. It is a known
  cosmetic defect a user meets; say so in the release notes.
* **F8** — a CR30 honeycomb rebuilt in 4.2.1 does not come back identical and
  its patch count changes, because the spacer became a ring. Intended, but it
  belongs in the notes.
* **F14** (pre-existing, not this branch): reopening any project unticks "Auto"
  on the patch count and a Generate then rebuilds 16 patches where the project
  held 525, while the log says the count was restored. Somebody should own it.

### The tests

The gate is green and the six mutations the last round found are genuinely
closed. But **six new mutations survive the entire release gate**, five of them
in code this branch added, and one of them (**F15**) turns half the diagonal
spacers on a rotated sheet into two-tone bands. Its cause is the same one that
has now bitten four times in this work: `test_every_side_names_the_patch_it
_actually_faces` re-implements the stagger inside itself instead of asking
`hexagon.stagger_dy`, so it moves with the bug. That is the fourth
self-validating test, exactly as predicted.

I would not sign this off to print on a customer's paper today. With the four
blocking items above — none of which is more than a few lines, and one of which
is a changelog entry — I would.

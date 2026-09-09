# Fourth adversarial review — hexagon lattice + five fixes

Tree: clean at `9db92b20` (verified `git status --porcelain` empty).
Branch: feature/nelson-photocard-presets. Bar: "sign this off to print on a paying customer's paper".

Findings are appended as they are measured, numbered H1, H2, ...

## H0 — the three lattice claims, verified independently

**Claim 1: "seams 0 across {SS pointy, CR30 pointy, CR30 turned} x {150,200,300,360,400,600,720} dpi".**
CONFIRMED, and wider than claimed. My own probe (`scratchpad/h_seam3.py` +
`run_seam2.py`) does not reuse the suite's helper: it fills the sheet to
`layout.patches_per_page` (the suite renders 210 patches on a sheet that holds
390-2535, so most of its field is empty), captures the geom and rects the chart
actually used by hooking `geometry.patch_rects_px`, and counts bare paper
(all channels > 245) inside the patch field.

One correction to method, worth recording because it produced a false alarm
first: the bounding box of the recorded rects is NOT the patch field. A
honeycomb's field edge is a zigzag (the stagger moves the outer patches +-w/4),
so the box legitimately contains paper along its border: measuring the raw box
reported 7,974 to 837,303 "seams" on charts that are in fact perfect. Trimming
1.5 patch widths/heights off each side removes exactly that boundary.

Result with the trim: **0 bare-paper pixels in every configuration measured** -
2 instruments x 4 papers (A4, A3, Letter, A4 landscape) x 8 resolutions
(72, 150, 200, 300, 360, 400, 600, 720) x 3 spacer states (none / coloured /
coloured+edge spacers), on FULL sheets. Includes 72 and 96 dpi, which the
commit did not test. Confidence: high.

(Also settled while doing it: `hex_flat_top` is inert on the SpectroScan -
`_build_base` honours it only in the CR30 branch, and `_sync_hex_flat_top_
visibility` hides the checkbox for anything else. That is Basti's ruling of
2026-09-09, not a defect. SS pointy and SS "turned" render byte-for-byte the
same page, which is what "inert" should look like.)

## H1 — BLOCKER (paper): every patch count in the changelog paragraph is still wrong

G3 "corrected" the four counts in the CHANGELOG's "Straight strips" bullet. The
new numbers were measured through `instruments.build("CR30", hflag=True,
hex_flat_top=…)` with the LIBRARY defaults, which is not a path the app takes.
The bullet ends *"Watch the count beside the preview"*, so the number the user
compares against is the one the Chart layout information panel prints.

**Driven on screen** (`scratchpad/drive4.py`, sandboxed settings, Create Chart >
Manual > CR30 > Hexagon, Expert Options expanded, reading
`_layout_info_panel._estimate_labels`):

| paper | app, pointy | app, turned | CHANGELOG says |
|---|---|---|---|
| A4 portrait | **390** | **374** | 416 -> 396 |
| A3 portrait | **836** | **832** | 874 -> 864 |
| Letter portrait | **360** | **378** | 384 -> 399 |

A third answer exists as well: through the app's own `presets.default_recipe`
(`geom_from_build_kwargs(default_recipe("CR30").build_kwargs())`) the counts are
A4 405 -> 391, A4 landscape 396 -> 416, A3 836 -> 858, Letter 375 -> 378. So the
three routes give three different sets of numbers, and the changelog quotes the
only one no user can reach.

The differences between the library `build()` and the recipe path are
`margin_l` 6.00 mm vs 14.43 mm (the row-label band is added to the left margin
under `use_instrument_margins`), `rlwi`, `margins_are_law`, `label_band_mm` and
`patch_area_align`.

WHY IT MATTERS: this is the same failure mode as G4 (a number measured in units
/ down a path the app never uses), in the one artefact a customer reads. A user
who ticks the turn on A3 is told to expect 874 -> 864 and sees 836 -> 832.
Severity: user-facing documentation, no ink at risk. Confidence: high, measured
on screen.

FIX: either re-measure the four numbers through the panel and quote those, or
drop the numbers and keep only "watch the count beside the preview".
Screenshots: `~/Desktop/ChromIQ-hex-proof/08-fourth/A1-layout-info-panel.png`,
`A2-layout-info-panel-close.png`.

## H2 — BLOCKER: the lattice change DID move rectangular charts. The recorded box now overshoots the ink by a pixel on 17 % of a DTP41 sheet

`bcb10e45` states, in capitals: *"RECTANGULAR CHARTS ARE UNTOUCHED: 66 pages
over seven instruments, three papers and two resolutions, sha256-identical to
the pre-lattice tree. With no hexagon the stagger is zero and `round(a + 0)` is
the old `round(a)`."*

The **pages** are indeed identical. The **recorded rects are not**, and the
reasoning is incomplete: the change is not only "+0 on the stagger", it also
replaced `round((y + plen) * S)` with `round(y*S + plen*S)`. Those are equal in
real arithmetic and NOT in floating point, and a chart whose pitch lands on a
rounding tie flips.

Measured. Same .ti1, same options, HEAD tree vs a worktree at `964f0fd9` (the
commit before the lattice), rendering every rectangular instrument x {A4, A3,
Letter} x {150,300,600} dpi and hashing pages + `strips.json`
(`scratchpad/rect_ident.py`): 233 of 234 hashes identical, one differs -
**DTP41 / Letter / 300 dpi / spacers on**, `strips.json` only, TIFF identical.
Diffing the rects: **72 of 414 recorded boxes are 1 px taller than before**
(h 87->88 and 86->87); `x`, `y`, `w` unchanged.

Which one is right? Measured against the INK, unique colour per patch, exact
bounding box of each patch's own colour (`scratchpad/one41b.py`):

```
tree           delta (left, top, right, bottom) -> count
HEAD           (0,0,0,0): 303   (0,0,0,-1): 64
pre-lattice    (0,0,0,0): 367
```

So at the branch point every recorded box described the ink exactly, and at HEAD
**64 of 368 measured boxes reach one pixel below the ink**. The renderer's
rectangular branch still draws `[x0, y0, xR-1, yB-1]` from `px(y_of(j))` and
`px(y_of(j) + plen)` - the OLD expression - so only `patch_rects_px` moved, and
it moved away from the paint.

WHY IT MATTERS: these rects are what the Measure overlay highlights, what
`scanin_target` writes as the scanner's patch boxes, and what the margin
inspector measures from. A box one pixel too tall on a DTP41 chart pulls a
sliver of the spacer into the scanner's sample on every fifth patch - the same
class of fault F11/G4 were raised for, in the instrument family the fix was not
looking at. It is small, but it is a REGRESSION in a path the commit claimed it
had left alone, and the claim was checked by a test that cannot see it (H3).

Severity: blocker for a stable tag as an unverified claim; the ink itself is
unmoved, so no printed chart is wrong. Confidence: high, both trees measured
side by side.

FIX: make `patch_rects_px` use the renderer's own expression on the
non-hexagonal path - `round((y_of(j) + plen) * S)` - and keep the single-round
lattice expression only where the renderer uses it (the hexagon branch). Then
re-assert equality against the pre-lattice tree rather than against a property.

## H3 — THE SIXTH SELF-VALIDATING TEST: `test_the_lattice_change_moved_no_rectangular_chart`

It is named for H2's claim and cannot detect H2. Its docstring says *"Asserted
structurally rather than against a stored hash, so it cannot go stale"*. What it
actually asserts, for i1/p3/CM/41/51 on A4 at 300 dpi only:

```python
for k, r in enumerate(rects[:steps * 3]):
    by_strip.setdefault(k // steps, []).append(r["y"])
...
gaps = {b - a for a, b in zip(ys, ys[1:])}
assert len(gaps) <= 2
```

It reads only `r["y"]`. It never looks at `w`, `h` or `x`; it never compares
against the earlier tree; it never reads a pixel. The lattice change did not
move any `y`, so the assertion is satisfied by construction. Measured, the sets
it inspects are i1 {129,130}, p3 {259,260}, CM {177,178}, 41 {111}, 51 {141} -
1 or 2 values, against a limit of 2.

MUTATION, PROVEN TO LAND. `geometry.patch_rects_px`, line 579:
`"w": max(1, _x1 - _x0), "h": max(1, _y1 - _y0)` ->
`"w": max(1, _x1 - _x0 + 3), "h": max(1, _y1 - _y0 + 3)`; grepped back
(`579: "w": max(1, _x1 - _x0 + 3), "h": max(1, _y1 - _y0 + 3),`), `__pycache__`
cleared. **Every recorded box on every chart in the app is now 3 px wider and
3 px taller than the ink, and the test passes: `1 passed in 0.34s`.** Mutation
reverted; `git status` clean again.

And the regression in H2 is itself a landed mutation: it is present at HEAD and
the gate is green.

FIX: assert what the commit measured - render the rectangular set from both
trees and compare page bytes AND the recorded rects - or, better, assert that
every recorded box equals the ink's bounding box, which is the property the
rects exist to have and which holds for hexagons too.

### H2, scope (measured arithmetically, `scratchpad/ulp_rect.py`)

Every rectangular slot of 7 instruments x {spacers off/on} x {CM stagger} x
11 papers x 11 resolutions (72...1200), comparing the renderer's edge
`round((v + size) * S)` against the new geometry's `round(v*S + size*S)`:

```
instr spacers cm_stag paper    dpi  slots  x-off y-off
41    False   False   Letter   150   480     0     80
41    False   False   LetterR  150   462     0     42
41    False   False   Legal    300   656     0    128
41    False   False   Tabloid  300  1071     0    126
41    True    False   Letter   300   368     0     64
41    True    False   LetterR  300   357     0     42
41    True    False   Legal    150   512     0     48
41    True    False   Tabloid  150   840     0     42
41    True    False   8x10     300   315     0     75
configs with a disagreement: 9
```

Only the **DTP41** is hit, and only on its height, because its patch length is
an inch value (0.29") that lands on exact rounding ties at those resolutions.
Worst case Legal at 300 dpi: 128 of 656 boxes, 19.5 %. Nothing else in the
supported set moves. 1 px at 300 dpi is 0.085 mm.

So the practical harm is small and confined to one instrument; what makes it a
blocker for a *stable* tag is that it falsifies a headline claim of the commit
and the test written to guard that claim is blind to it (H3). The fix is two
lines: on the non-hexagonal path, keep the renderer's own expression.

### ...and the hexagon lockstep itself survives the same hazard (nothing found)

The fix introduces the same association hazard inside the honeycomb path:
`geometry` rounds `(fx + fw) + dx` and `raster` rounds `(fx + dx) + fw` for the
same edge, and on a turned sheet `((y*S + stag) + fh) + dy` against
`((y*S + stag) + dy) + fh`. Swept over **1,252,728 slots** - 2 instruments x
both orientations x spacers on/off x edge spacers on/off x 8 papers x 12
resolutions (72, 96, 150, 200, 240, 300, 360, 400, 600, 720, 1200, 2400):
**0 x-disagreements, 0 y-disagreements** (`scratchpad/ulp.py`). The honeycomb
lockstep holds exactly. Confidence: high.

## H4 — G10 is only half fixed: the ACTUAL column still prints a turned chart's COLUMN pitch under "Row pitch", one click after the fix

`set_pitch_axis` is called from ONE place, `TabChart._update_layout_estimate`,
which drives the **estimate** column. The **actual** column is filled by
`_update_layout_info` -> `_chart_patch_size_mm` -> `_panel_patch_size_mm(...,
recipe_is_flat_top(recipe))`, which reads the BUILT chart's own recipe and never
touches the row name. One row name serves both columns, and it follows only the
estimate.

**Driven on screen** (`scratchpad/drive4b.py`), CR30 + Hexagon + turn ticked,
chart generated, then a single click:

```
AFTER BUILD:      pitch row name : Column pitch (mm)
                  ACTUAL pitch   : 10.41      ESTIMATE : 10.39     [correct]
UNTICK THE TURN:  pitch row name : Row pitch (mm)
                  ACTUAL pitch   : 10.41   <- the built TURNED chart's COLUMN
                                              pitch, now labelled "Row pitch"
SWITCH TO i1:     pitch row name : Row pitch (mm)
                  ACTUAL pitch   : 10.41
```

That last state is G10's original symptom verbatim: *"the panel printed a turned
chart's COLUMN pitch under Row pitch: 10.39 mm where the sheet's rows are 12.00
mm apart"*. The built sheet's rows are 12.02 mm apart (the panel says so itself,
two rows up: "Patch size (mm) 13.89x12.02").

Pictures, looked at:
`08-fourth/C2-panel-turned-built.png` (correct: "Column pitch (mm) 10.41"),
`08-fourth/C4-panel-after-untick.png` (wrong: "Row pitch (mm) 10.41" beside
"Patch size 13.89x12.02"), `C5-panel-instrument-i1.png`.

Severity: report-only, no ink at risk, but it is the SAME defect the commit
claims to have closed, reachable in one click, and it is the kind of number
Knut reads off a screenshot (#B8-80). Confidence: high, photographed.

FIX: either call `set_pitch_axis` from `_update_layout_info` too and give the
two columns their own name when they disagree, or name the axis in the VALUE
rather than the row (the recipe summary line already does).

## H5 — BLOCKER (visible): the scanner grid mesh does not follow the turn. It draws POINTY cells on a flat-top chart

`ui/scan_grid_marquee.py`, `ScanGridMarquee._cell_uv`:

```python
if hexed:
    pts += hexagon.vertices(u, v, w, hh)      # no flat_top=
```

`GridSpec` has no `flat_top` field at all (its comment still says *"True for a
SpectroScan hexagonal chart"*), and `scanin_dialog._load_page_grid` computes the
orientation for the sample cap on the very next statement and passes only
`hexagonal=` to `GridSpec.from_patches`. So the one of `hexagon.py`'s five
pooled sites that the module docstring names as site 5 is the one that lost the
second orientation - the exact failure the pooling was done to prevent
(*"a second ORIENTATION is being added, and five independent copies get five
independent chances to disagree about it"*).

**Measured and photographed** (`scratchpad/mesh.py`): a real CR30 A4 honeycomb
at 200 dpi, both orientations, with the marquee's OWN `_cell_uv()` polygons
mapped back onto the chart's own pixels.

* `08-fourth/D1-pointy-scanner-mesh-on-ink.png` - control: every yellow cell
  sits exactly on its hexagon.
* `08-fourth/D2-turned-scanner-mesh-on-ink.png` - the turned chart: every cell
  is drawn 30 degrees off, apexes up and down over ink whose apexes are left and
  right, each cell's points reaching into the patches above and below.

LOOKED AT, not inferred: the second picture is unmistakable.

What is NOT affected: the sampled rectangle (`sample_margin`) is symmetric and
still correct, and the .cht boxes come from `patch_rects_px`, so scanin reads
the right area. The damage is that the alignment guide - the thing the user
drags the quad against, and whose stated purpose is *"so the user can see the
mesh sitting on the hexagons"* - is visibly wrong on the new orientation, and a
user who lines the chart up to make it fit will mis-register the whole scan.

Severity: blocker for a stable tag of a feature whose headline is the turn.
Confidence: high, photographed against a control.

FIX: give `GridSpec` a `flat_top` field, set it in `_load_page_grid` from the
same `recipe_is_flat_top` call that is already made two lines below, and pass it
to `hexagon.vertices(..., flat_top=...)`.

## H6 — G2 re-measured: real, harmful, and PRE-EXISTING. It does not block this tag, and it should not stay open

`LayoutRecipe.build_kwargs()` returns
`"edge_spacers": self.edge_spacers or self.instrument in ("i1","p3","CM")`,
while `to_dict()` (and therefore the sidecar's `recipe` block) stores the raw
`edge_spacers: False`. Measured:

```
i1  recipe.edge_spacers False -> built with True
p3  recipe.edge_spacers False -> built with True
CM  recipe.edge_spacers False -> built with True
41  False -> False        SS  False -> False
```

Two shipped consumers gate on the RAW value before they build the geom:
`margin_inspector.measure_from_engine` (`if rec.get("edge_spacers")`) and
`tab_measure.edge_spacer_px_from_sidecar` (`if not recipe.get("edge_spacers"):
return 0`). Both therefore behave as if the chart had no edge spacers when it
has them.

Measured against the rendered ink, A4, 600 dpi, default recipe, indicators off
(`scratchpad/g2.py`):

```
tree     instr  inspector top/bottom   ink top/bottom    over-report
HEAD     i1      6.985 /  7.017        3.979 / 4.022     +3.006 / +2.995
HEAD     p3      8.001 /  9.006        3.979 / 4.022     +4.022 / +4.985
HEAD     CM      6.985 /  7.017        5.969 / 6.011     +1.016 / +1.005
base(e1aeaf2f) — identical to HEAD on all three
```

It over-reports clearance, which is the unsafe direction, and it is exactly the
fault the code's own comment credits to Knut (#18) and says it fixes. **It is
byte-identical at the branch point**, so this branch neither caused it nor made
it worse. Decision: NOT a blocker for 4.2.1; it is an open defect that predates
the release and should be filed and fixed next, because the same reasoning has
now bitten twice in this feature (G4's units, G3's build path): a value read one
way and applied another.

### ...and while measuring it: the DEFAULT i1 and p3 chart prints 2.0 mm outside its own margin

Same probe, all three trees including the branch point: margins asked
6.00/6.00 mm, ink top **3.979 mm**, bottom **4.022 mm**, on i1 and p3.
CM is clean (5.969/6.011). Identical at `e1aeaf2f`, so PRE-EXISTING and out of
this branch's scope - but worth noting beside G5, which treated exactly this
symptom on a honeycomb as a blocking regression. The rectangular strip-reader
case has been shipping.

## H7 — the lattice under stress: nothing found

`scratchpad/edge_cases.py`, CR30 A4 at 300 dpi, both orientations, seams counted
in the patch field (trimmed 1.5 patches at each edge) and every patch's recorded
box compared against the ink of its own unique colour:

* **multi-page and odd counts**: n = 1, 391, 401, 800, 1200 -> 1, 2, 2, 3, 4
  pages. Seams **0** on every page of every one.
* **area-first**: `by_width`, `by_grid 12x20`, `by_grid 7x31` (4 pages),
  `by_ratio 1.4`. Seams **0**.
* **patch size**: 1.0, 2.0, 3.0, 30.0, 60.0, 120.0 mm wide (1 to 8 pages).
  Seams **0**.

The only recorded-box deviation anywhere is one family, `(0, +1)`: the ink's far
edge on the flat-side axis is one pixel beyond the recorded box, on 3-15 % of
patches (and on essentially all of them at a 120 mm patch, where a hexagon spans
thousands of pixels). That is Pillow's polygon fill convention on the closing
edge, it is present identically at the branch point and at `964f0fd9`, and it is
not what this change touched. Confidence: high.

## H8 — G5 re-verified on the fourth side, and on a ring sweep: nothing found

The suite's `test_a_honeycomb_never_prints_outside_its_margins` checks top, left
and bottom, never RIGHT, at two ring values. Re-measured on all four sides,
CR30 A4, 600 dpi, 20 mm margins on every side, indicators off, varied colours
and a palette without white (`scratchpad/margins4.py`):

both orientations x edge spacers off/on x ring in
{0.65, 1.3, 2.0, 3.0, 4.157, 10.0, 40.0} = **28 configurations**. The worst
clearance anywhere is **19.981 mm** against a 20.000 mm margin - 0.019 mm, less
than half a pixel at 600 dpi, i.e. the ink sits ON the margin and never past it.
The clamp visibly takes over from ring 4.157 upward (the layout re-flows and the
clearance jumps back to 23-25 mm), so the 300 mm the spinbox accepts is safe.

The `2/sqrt(3)` apex factor is also right by construction, and I checked the
algebra rather than trusting the comment: growing every edge of a REGULAR
hexagon by `d` scales the inradius to `r+d`, so the circumradius grows by
`d * R/r = d / cos 30 = d * 2/sqrt(3)`. With `d = ring/2` that is `0.5774*ring`
at the apexes and `0.5*ring` at the flats, exactly as written; and it is applied
to `hxeh` (the y reserve) on a pointy sheet and to `hxew` (the x reserve) on a
turned one, which matches `_build_base`'s own table of which overhang is which.
Confidence: high.

Capacity cost of the reservation, measured on full sheets: only A4 landscape
pointy loses patches (396 -> 374 with edge spacers, 5.6 %); A4 portrait, A3 and
Letter are unchanged in both orientations. No chart is pushed onto another page
in the set I measured.

## H9 — the pre-existing "reopen unticks Auto" item, re-measured. It does NOT block this tag

Driven on screen (`scratchpad/reopen2.py`), three trees:

```
HEAD      [RectChart] built 525; reopened auto=False count=0; REGENERATED -> 16
HEAD      [HexChart]  built 351; reopened auto=False count=0; REGENERATED -> 14
e1aeaf2f  identical
master (7e500e59, the shipped 4.2.0 line)  identical
```

So it is reproducible, it is bad - reopening a project loses "Auto patches" and
the count reads 0, and Generate then lays out a 16-patch sheet where the project
held 525 - and it is **byte-identical on master**, i.e. already shipped.

One mitigation the earlier report did not record: it is not silent.
`_confirm_displacing_results` is called **twice** on that regenerate, so the user
is asked before the existing results are displaced (instrumented; the count is
printed by the probe). What the user is NOT told is that the chart collapsed
from 525 patches to 16, and the panel shows the count as 0 rather than as the
project's own number.

DECISION: not a blocker for 4.2.1 - it is not a regression, it predates the
branch, and there is a confirmation in the way. It is the highest-value open
defect I met all round and should be the next thing fixed.

## H10 — the gate

`QT_QPA_PLATFORM=offscreen pytest --runslow -n auto`, tree clean at `9db92b20`,
nothing else running:

```
========== 12617 passed, 167 skipped, 4 xfailed in 224.41s (0:03:44) ===========
```

No `[gwN] node down`, no `Fatal Python error`, no `Timeout (0:0X:XX)!` dump
(grepped). Green, and green for the right reason.

Note for the record: this green gate contains H2 (a live 1-px regression in
`patch_rects_px` on the DTP41) and H5 (a visibly wrong scanner mesh on every
turned honeycomb). Neither is caught by anything in it.

---

# RELEASE VERDICT — HOLD

Not because the lattice is wrong. **The lattice is the strongest thing in this
branch and I could not break it.** I attacked it with a probe that shares no
code with the suite's, on full sheets rather than a quarter-full one, and it
came back clean over 279 rendered configurations plus multi-page, area-first,
by_grid, and patch sizes from 1 mm to 120 mm; and the float-association hazard
the fix introduces into the honeycomb path does not fire once in 1,252,728
slots. Claim 2 (the recorded box in lockstep with the ink) is independently
confirmed as a real improvement: at 300 and 600 dpi the pre-lattice tree
scattered 629 of 900 SpectroScan boxes by +-1 px and HEAD holds 854 of 900
exactly.

HOLD is for the five things around it.

**Fix before tagging (all small):**

1. **H5** — the scanner grid mesh draws pointy cells on every turned honeycomb.
   Photographed against a control. A user aligning a scan by that guide will
   mis-register it. One field on `GridSpec` and one keyword.
2. **H2** — the lattice DID move rectangular charts. `patch_rects_px` now
   overshoots the ink by 1 px on up to 19.5 % of a DTP41 sheet, where the
   branch point was exact. Two lines: keep the renderer's own expression on the
   non-hexagonal path.
3. **H3** — the test named for H2's claim reads only `r["y"]`; with every
   recorded box 3 px too big in both axes it passes in 0.34 s. Replace it with
   the comparison the commit actually made.
4. **H4** — G10 is half fixed: the ACTUAL column prints a turned chart's column
   pitch under "Row pitch" one click after the fix, and again on any instrument
   change. Photographed.
5. **H1** — every patch count in the CHANGELOG bullet is wrong against the
   number the same bullet tells the user to watch. Re-measure through the panel,
   or drop the numbers.

**File and fix next, not blocking 4.2.1** (both measured byte-identical at the
branch point or on master, so neither is this branch's doing):

* **H6** — `build_kwargs()` forces `edge_spacers` on for i1/p3/CM while the
  sidecar stores the raw False, so the margin inspector over-reports clearance
  by 1.0-5.0 mm on those instruments, in the unsafe direction. (And, separately,
  the DEFAULT i1/p3 chart prints 2.0 mm outside its own margin, on master too.)
* **H9** — reopening a project unticks "Auto patches", shows the count as 0, and
  Generate then lays out 16 patches where the project held 525. Confirmed on
  master. There is a displacement confirmation in the way, which is why it is
  not a blocker.

**What "ship" would need:** items 1-5 above, then a fresh `--runslow`. The gate
at `9db92b20` is green (12617 passed, 3:44, no worker-down banner) and that green
contains both H2 and H5, so the gate is not the thing that decides this.

Would I sign this off to print on a paying customer's paper? The PRINTED SHEET,
yes - I could not find a hexagon page that is wrong, at any resolution, paper,
patch size or page count. What I would not sign off is the READING of it: a
scanner alignment guide that is visibly 30 degrees out on the feature's headline
orientation is exactly the kind of thing a customer discovers after the ink is
dry.

## Housekeeping

Two git worktrees were added for the before/after comparisons and left in place
for whoever fixes H2:
`scratchpad/pre-lattice` at `964f0fd9` (the commit before the lattice) and
`scratchpad/master-tip` at `7e500e59` (master). `git worktree remove` them when
done. The working tree is clean apart from this file; the one source mutation
made (H3) was reverted and `git status` verified clean afterwards.

**AND THE TREE DID NOT STAY STILL.** At 10:24, after my gate had finished
(10:17-10:21) and while I was writing this file, a new untracked file appeared
in the repository that is not mine: `scripts/drive_nelson_split_overlay.py`
(7,137 bytes, a driver for the expected-vs-measured split on Nelson Lau's
10x15 cm chart). Something else is writing into this checkout. No TRACKED file
changed (`git diff --stat` is empty), so every measurement above stands and the
gate ran on a tree that was clean apart from this report - but whoever
coordinates this should know, and should re-check `git status` before tagging.

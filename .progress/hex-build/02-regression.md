# Adversarial regression review — commits 1f4ff390 and c62a7eb0

Reviewer: adversarial pass, 2026-09-08. Branch `feature/182-compliance-sets`.
Base tree before the two commits: `478c7396`.

Findings are appended as they are confirmed, numbered R1, R2, ...

---

## R1 — SHIPPED DEFECT (commit 1f4ff390): the two axes are SWAPPED. The comb that was kept misses every patch by a quarter of a patch width; the comb that was dropped was exact.

**What I did.** `helper_marker_lines_mm` now sets `sides = False` on a honeycomb
and keeps `top_bottom`. I measured, for every hex-capable instrument (`SS`,
`CR30`) x every engine paper (15 codes) x spacer on/off x pscale 0.8/1.0/1.3 —
**348 configurations** — the distance from each patch centre recorded by
`geometry.patch_rects_px` (the app's own record of where the ink is, which
commit c62a7eb0 asserts matches the raster exactly) to the nearest dash of each
comb. To see the comb the commit dropped I stubbed `instruments.is_hexagonal`
to False for the `helper_marker_lines_mm` call only.

Probe: `scratchpad/probe_both.py`, `scratchpad/probe_sweep.py`.

**Numbers, default `per_patch=3`, 300 dpi, page 0:**

```
SS    A4  spacer=True  pwid= 7.000 | TOP/BOTTOM(x) err min=1.6827 max=1.7450 mean=1.7105 | SIDES(y) err min=0.0011 max=0.0242
SS    A4  spacer=False pwid= 7.000 | TOP/BOTTOM(x) err min=1.6827 max=1.7450 mean=1.7105 | SIDES(y) err min=0.0011 max=0.0242
SS    A3  spacer=True  pwid= 7.000 | TOP/BOTTOM(x) err min=1.6827 max=1.7450 mean=1.7077 | SIDES(y) err min=0.0027 max=0.0228
CR30  A4  spacer=True  pwid=12.000 | TOP/BOTTOM(x) err min=2.9213 max=2.9827 mean=2.9545 | SIDES(y) err min=0.0008 max=0.0308
CR30  A4  spacer=False pwid=12.000 | TOP/BOTTOM(x) err min=2.9213 max=2.9827 mean=2.9548 | SIDES(y) err min=0.0018 max=0.0309
CR30  A3  spacer=False pwid=12.000 | TOP/BOTTOM(x) err min=2.9213 max=2.9827 mean=2.9539 | SIDES(y) err min=0.0000 max=0.0312
```

Over all 348 configs at `per_patch` in {3, 5}: **worst SIDES(y) error 0.0389 mm**
(that is under half a pixel at 300 dpi — it is the px rounding in
`patch_rects_px`, nothing else). The TOP/BOTTOM(x) error at the shipped default
`per_patch=3` is **never better than 1.6827 mm on SS and 2.9213 mm on CR30**, and
those are exactly `pwid/4` (1.75 and 3.00) less the same px rounding.

**Why. The stagger is applied to X, indexed by the position DOWN the strip.**
`geometry.patch_rects_px` line 551: `_dx = hexagon.stagger_dx(_x1 - _x0, j)`
with `p, j = wp // steps, wp % steps` — `j` is the index down the pass, and the
offset lands on `_x0`/`_x1`. So going down a column the patches alternate
left/right by ±pwid/4, while `place.y_of(j)` carries no stagger at all.

* The **side** comb marks Y. Y is uniform, pitch `plen + pspa`. Every patch
  centre sits on a dash. It is EXACT.
* The **top/bottom** comb marks X. It is anchored on `place.x_of(0)`, i.e. the
  **slot** grid, which no hexagon occupies. Concretely, CR30 A4: dashes at
  x = 3, 9, 15, 21, 27 ... mm; patch centres at x = 6, 12, 18, 24 ... mm. The
  dash grid and the honeycomb-column grid are both 6 mm and are exactly 3 mm out
  of phase. **Every dash falls exactly midway between two columns of the
  honeycomb — it points at the gap.** That is precisely the failure the commit
  says it is avoiding, and it kept it.

**The commit's own measurement supports the opposite conclusion.** The message
says "measured on a real CR30 A4 sheet, dy = 0.0000 between strips at a
12.0000 mm pitch." `dy = 0` between strips is a statement that the Y positions
do not move — that is the argument FOR the side comb. It says nothing about the
patch positions within a strip, which are the ones that zigzag, and they zigzag
in **X**, which is the axis the kept comb marks.

**Curiosity, not a defence:** at `per_patch=5` the X step becomes `pitch/4`,
which coincidentally equals the stagger, so the X comb hits centres there
(x_err 0.005..0.067). At the shipped default of 3 it never does. At 4 it is off
by up to 1.08 mm.

**Impact.** A honeycomb printed with helper markers gets a top/bottom comb whose
every dash points between the patch columns, and is refused the one comb that is
correct to 0.03 mm. On the sheet the user lines a ruler up against, the offer is
inverted.

**Confidence: very high.** Measured from the app's own geometry, 348
configurations, no exceptions found. The fix is a one-line swap
(`top_bottom = False` / keep `sides`), but it is a behaviour change on a
specification-governed area and needs Basti's ruling, not a silent correction.

## C — whole-tree gate (run first, before any probing)

`QT_QPA_PLATFORM=offscreen pytest --runslow -n auto` on HEAD (c62a7eb0):

```
12 workers [12649 items]
========== 12478 passed, 167 skipped, 4 xfailed in 203.68s (0:03:23) ===========
EXIT=0
```

No `node down` banner, no `Fatal Python error`, no `Timeout (0:0X:XX)!` dump.
The gate is genuinely green. **Which is itself a finding: R1 is a defect the
whole suite is blind to.**

## R2 — DEFECT (commit 1f4ff390): on a honeycomb, "No dashes will be printed" cannot fire, and the contradiction it was written to catch is now reachable.

**What I did.** Drove a real `LayoutOptionsPanel` offscreen
(`scratchpad/probe_panel.py`), in the user's order: markers on, both edge boxes
ticked, `set_helper_markers_supported(False, one_axis_only=True)` (a honeycomb),
then unticked "top and bottom" — the only box that is still enabled.

```
honeycomb, both ticked                     tb(en/ck)=True /True  sides(en/ck)=False/True  flag=True
honeycomb, top/bottom unticked by the user tb(en/ck)=True /False sides(en/ck)=False/True  flag=True
   warning text: ''
   engine lines with top_bottom=False, sides=True on a honeycomb: 0
```

**Why it matters.** `_helper_marker_edge_warning_text` asks
`not (top_bottom.isChecked() or sides.isChecked())`. On a honeycomb `sides`
stays TICKED by the "disable, never untick" doctrine, so the `or` is satisfied
by a box the engine has already decided to ignore. The warning stays empty while
`helper_marker_lines_mm` returns **0 segments**. The panel therefore shows
"Print helper markers" ticked, an edge box ticked, three live distance spin
boxes, and no warning — and the sheet comes out with no dashes at all. The
docstring of that very method says it exists because *"'Print helper markers'
ticked with both edges unticked prints nothing, and every distance box stays
live and looks armed — a contradiction the user can only resolve by asking."*
The commit re-opened that contradiction through a new door.

Fix: the warning must ask for an edge that will actually be *drawn*, i.e. treat
`sides` as unticked when `_hm_one_axis_only` is set.

**Confidence: high.** Reproduced end to end, panel state and engine output in
the same run.

## Panel state machine — attacked, nothing else found

With the tab's connection in place (`_manual_layout_panel.changed` ->
`_refresh_helper_marker_support`, tab_chart.py:5024) I could not find an order
of actions that leaves the state stale (`scratchpad/probe_panel2.py`):

```
fresh panel with selectors     sides(en/ck)=True /True  flag=<unset> instr=i1   mode=clip
instrument -> CR30             sides(en/ck)=True /True  flag=False   instr=CR30 mode=flat
mode -> hex                    sides(en/ck)=False/True  flag=True    instr=CR30 mode=hex
master retoggled               sides(en/ck)=False/True  flag=True    instr=CR30 mode=hex
set_recipe(i1/strip)           sides(en/ck)=True /True  flag=False   instr=i1   mode=noclip
set_recipe(CR30/hex)           sides(en/ck)=False/True  flag=True    instr=CR30 mode=hex
master retoggled on hex recipe sides(en/ck)=False/True  flag=True    instr=CR30 mode=hex
```

`set_recipe` ends in `_emit()` with `_loading` cleared, so the tab re-evaluates
and the flag is never left stale there. **DISABLE-NEVER-UNTICK also holds**: set
sides=True on squares -> switch to hex -> `get_recipe()` still carries
`helper_markers_sides=True` -> reload into a fresh panel -> back to squares ->
still ticked and enabled. Nothing lost.

**Two scoped observations, both PRE-EXISTING rather than regressions:**

* `set_helper_markers_supported` is called from exactly one place
  (`tab_chart.py:18362`). The TI2 layout editor
  (`ti2_relayout_dialog.py:5163`) and Preferences -> Chart Layout
  (`settings_dialog.py:5195`) embed the same panel, with the same
  "Ruler helper markers" group, and never call it — so on a CR30/hex recipe
  there both edge boxes are live and unexplained. The greying is a property of
  one screen, not of the control.
* A bare `LayoutOptionsPanel` has no `_hm_one_axis_only` attribute at all
  (`hasattr` = False); every read is `getattr(..., False)`. That is defensive
  and works, but it means "no honeycomb" and "nobody asked" are the same state.

## B — commit c62a7eb0 (pooling the hexagon). Verified independently.

### B1. The "not one pixel moved" claim — VERIFIED, and the manifest is not blind

I did not trust the committed manifests. `git worktree add ... 478c7396`, copied
the manifest script into the old tree (it did not exist there), ran it on both:

```
old tree 478c7396 : 76 lines, 44 pages hashed
HEAD     c62a7eb0 : 76 lines, 44 pages hashed
diff -> IDENTICAL: not one pixel moved
```

**And the manifest can fail.** In a third worktree at HEAD I changed
`raster._hexagon_points` to `round_to_int=False` — the exact regression the
commit says is its whole risk. Mutation proven to land
(`grep`: `1081: return hexagon.vertices(x0 + dx, y0, w, ph, round_to_int=False)`),
`__pycache__` cleared:

```
manifest SAW it: 44 of 44 rows differ
```

So the proof is a real proof, not a tautology. Caveats measured, none fatal:

* 44 page rows, **36 distinct hashes**. The 8 duplicates are all SS: for SS hex
  `spacers-none` and `spacers-colored` render byte-identical pages (SS hex has
  `pspa = 0`, so there is no spacer to colour). One quarter of the SS matrix is
  a duplicate row, not extra coverage.
* **0 REFUSED lines** in either run, so nothing was silently skipped. (The
  committed `manifest-before.err` does contain a traceback — `paper_w_mm` /
  `'A4L'` — but that is from an earlier, broken revision of the script; the
  committed `manifest-before.txt` has all 44 rows.)
* The manifest is structurally blind to three of the five pooled sites: it
  renders pages only, so it cannot see `tiff_preview`'s two Qt paths, the hit
  test, or the marquee mesh. The commit says exactly this and adds a second
  proof for them. Fair.
* The commit message says "45 pages"; the manifest says 44. Cosmetic.

### B2. `hexagon.contains` vs the old `_in_hexagon` — measured, no reachable change

400,000 random (QRect, point) pairs including widths 0, negative, and 1..101:

```
contains vs old _in_hexagon: 400000 samples, 79049 differ
   (6594 of them width == 0, 72455 width < 0)
   differing cases with width > 0: []   <- none
```

**Every single difference is a degenerate rect.** For any width > 0 the two
agree exactly. And the degenerate ones are unreachable: the only producer of
these rects is `tab_measure.patch_boxes_from_sidecar`, fed from
`geometry.patch_rects_px`, which writes `"w": max(1, _x1 - _x0)`. If a
hand-edited or foreign sidecar ever did carry `w: 0`, the new behaviour (miss)
is the correct one and the old one (a hit at `dx = 1.0`) was the bug. Not a
defect.

`b.width()` vs `b.right() + 1 - b.left()` (the substitution made in
`_patch_hexagon` and `_strip_zigzag_path`): swept every `QRect(x, y, w, h)` and
`QRect(QPoint, QPoint)` for x in {-7,0,1,999}, w in -4..59, h in -4..19, plus
the null `QRect()` — **0 cases where they differ**. Qt defines width() as
right()-left()+1, so the rewrite is exact by construction.

### B3. `stagger_dx` and `raster._hexagon_points` — bit-for-bit identical

Old vs new `_hexagon_points`, exhaustive over w = -5..400, ph = -3..199 plus
{401, 1000, 4097}, step in {0,1,2,7}, x0 in {0,1,7,-13,2500,9999} (odd widths
included, where w/2 is a .5 and the two versions add the terms in a different
order):

```
compared 2007264 hexagons; mismatches: 0
```

`stagger_dx` vs the two old expressions `round(-w/4)` / `round(w/4)`:

```
integer w = 0..4000, both parities: 0 mismatches
400,000 random float widths in [-500, 500]: 0 mismatches
```

Banker's rounding is not a hazard here: `w/4` and `w * 0.25` are the same double
(division by a power of two is exact), so `round()` never sees a different
argument. The `geometry.patch_rects_px` substitution is therefore exact.

One real float difference exists and is harmless: the old code wrote
`t6 = ph / 6.0`, the new one `ph * (1/6)`, and those differ for **6,666 of the
20,001 integers 0..20000**, by at most `5.7e-14` (max over 200k random floats).
On the rounded renderer path it never crosses a rounding boundary (the 2.0M
sweep above). On the unrounded float paths it is 1e-14 on a coordinate, and in
the marquee's unit space `(hh - hh/6)` vs `5*(hh*(1/6))` differs by at most
`1.1e-16`. Matches the commit's own claim of 1e-14.

### B4. Import cost / circular import — nothing found

`ui/scan_grid_marquee.py` now does `from workflow.layout_engine import hexagon`.

```
import ui.scan_grid_marquee, cumulative us, 3 runs each
  OLD (478c7396): 92936, 78549, 79107
  NEW (c62a7eb0): 84564, 78899, 79354
  workflow.layout_engine       132 us self / 226 cumulative
  workflow.layout_engine.hexagon  94 us self
```

Indistinguishable from noise. `numpy` line count in the importtime trace is
**86 in both trees** and `PIL` is **0 in both** — the marquee already pulled
numpy in via its own imports, and `hexagon` adds nothing: importing it alone
loads exactly `workflow`, `workflow.layout_engine`, `workflow.layout_engine.hexagon`
and nothing else (the package `__init__` is a docstring). No import cycle in any
order (marquee-first, geometry-first, all four together).

## R3 — WEAK GUARD (commit c62a7eb0): `test_every_geometry_key_reaches_the_geometry` is blind to 9 of `build()`'s 29 arguments, and they are exactly the ones a new geometry option will look like.

**What I did.** The test generates its own mutations: for each `build()` keyword
it builds a Geom at the default and at a probe value, and requires any key that
moves the Geom to be in `GEOM_BUILD_KEYS`. But the probe table is keyed on
`type(default)`, and `PROBES.get(type(default))` returns None for a `None`
default, which `continue`s.

Measured on HEAD:

```
probed  20: pscale sscale hflag density spacer_on border offset_x offset_y
            nolpcbord nolimit clip_border_width clip_band edge_spacers
            patch_area_align clip_side cm_stagger text_edge_top text_edge_clip
            margins_are_law fill_beyond_ruler

SKIPPED  9 (default is None -> never tried):
    margins              in GEOM_BUILD_KEYS=True
    patch_w              in GEOM_BUILD_KEYS=True
    patch_h              in GEOM_BUILD_KEYS=True
    spacer_width         in GEOM_BUILD_KEYS=True
    inter_patch          in GEOM_BUILD_KEYS=True
    strip_gap            in GEOM_BUILD_KEYS=True
    max_strip            in GEOM_BUILD_KEYS=True
    strip_indicator_gap  in GEOM_BUILD_KEYS=True
    row_indicators       in GEOM_BUILD_KEYS=True
```

**Mutation, one entry at a time, each deletion grepped to prove it landed
(`grep -c` inside the tuple returned 0 every time), `__pycache__` cleared before
every run:**

```
dropped "border"          -> 4 failed, 3 passed     CAUGHT
dropped "pscale"          -> 4 failed, 3 passed     CAUGHT
dropped "spacer_on"       -> 3 failed, 4 passed     CAUGHT
dropped "patch_w"         -> 7 passed               SURVIVED
dropped "patch_h"         -> 7 passed               SURVIVED
dropped "spacer_width"    -> 7 passed               SURVIVED
dropped "strip_gap"       -> 7 passed               SURVIVED
dropped "max_strip"       -> 7 passed               SURVIVED
dropped "row_indicators"  -> 7 passed               SURVIVED
dropped "margins"         -> 7 passed               SURVIVED
```

**Why it matters.** The test's own docstring claims *"It cannot be forgotten,
because nobody has to remember to add a line: the moment someone gives `build()`
a new geometry argument and leaves the tuple alone, this goes red naming it."*
That is false for 9 of the 29 arguments — and the 9 are the patch-size and
spacing arguments, i.e. the shape of a new geometry option. This commit is
explicitly *"groundwork for the rotation option"*, and the house style in this
signature for an optional geometry knob is `X | None = None` (9 of them already
are). A rotation argument written that way lands straight in the blind spot the
test was written to close.

Fix is small: give `PROBES` a fallback for a `None` default (try a plausible
float, and a bool for `row_indicators`), or drive the probe from the annotation
rather than from `type(default)`.

**Confidence: very high.** Ten mutations, each proven to land, run in an
isolated worktree.

## R4 — VACUOUS TEST (commit c62a7eb0): the rewritten `test_the_drawn_cell_is_a_hexagon` no longer tests `ScanGridMarquee` at all, and the mesh is now unguarded.

**What I did.** The rewrite dropped `inspect.getsource` and with it the only
assertion that the mesh *asks* the patch shape
(`assert "self._grid.hexagonal" in src, "the mesh ignores the patch shape"`).
What is left of the ScanGridMarquee half is one line:

```python
marquee = ScanGridMarquee.__new__(ScanGridMarquee)
assert hasattr(marquee, "_cell_uv") or hasattr(ScanGridMarquee, "_cell_uv")
```

That asserts a method exists. It never calls it. Everything else in the test
exercises `hexagon.vertices` directly, which
`test_the_hexagon_is_drawn_from_one_place.py` already pins six ways.

**Mutation, proven to land.** In an isolated worktree I made `_cell_uv` emit
RECTANGLES for a hexagonal grid — the exact regression the test is named for:

```
803:  pts += [(u, v), (u + w, v), (u + w, v + hh), (u, v + hh)]  # MUTANT
      (the hexed branch is now byte-identical to the else branch)

tests/test_hex_scanner_support.py -> 11 passed
```

`__pycache__` cleared, mutation grepped in place. The whole file stays green
with the scanner mesh drawing squares over a honeycomb.

The old assertion was brittle for the reason the docstring gives (it went red
for the shape being MOVED), but the replacement threw away the guard instead of
re-expressing it. The honest rewrite calls `_cell_uv` on a hexagonal `GridSpec`
and counts 6 points per cell against 4 — the data is right there in the same
file (`test_the_mesh_cells_take_the_patch_shape` already builds one).

**Confidence: very high.**

## The other new tests — attacked, they are REAL guards

Mutations in an isolated worktree, each grepped in place, `__pycache__` cleared:

```
hexagon.contains slope 2.0 -> 1.8   ->  34 failed  (the hit-test test caught it)
APEX_FRACTION 1/6 -> 1/5            -> 170 failed  (commit claimed 169)
raster round_to_int True -> False   ->  44 of 44 manifest rows differ
```

**And the `near < 1.0` skip filter does NOT gut the hit-test sampling** — this
was my main suspicion and it is wrong. Measured over the 56 parametrised boxes:

```
56 boxes, 221 grid points each = 12376 total
kept 11726 (94.7%), min per box 165, mean 209.4   (the assert only demands > 40)
of the kept points, 6886 are inside the hexagon (58.7%)
```

Well sampled, and balanced inside/outside. One cosmetic flaw:
`test_the_hit_test_agrees_with_the_polygon_it_is_testing` is parametrised on
`step` and **never uses `step` in its body** — it runs every case twice for
identical coverage.

## R1 confirmed on a REAL rendered sheet (not just on the geometry)

I built an actual CR30/A4/hex chart through `chart.build_chart` with
`helper_markers=True, edge=2, len=4, per_patch=3` at 300 dpi and measured the
printed page.

Spy on the real call inside the renderer:

```
geom: pwid=12.0 rrsp=12.0 hexagonal=True  x0=17.4323  steps=23  ppp=345
marker xs (mm): 5.4323, 11.4323, 17.4323, 23.4323, 29.4323, ...  (35 dashes, pitch 6.0)
```

Dashes found in the printed ink at y = 2.5 / 3.5 / 5.0 mm, all three scanlines
agreeing: 35 runs, 0.169 mm wide, first at 5.461 mm, pitch 6.011 mm.

The chart's own `strips.json` patch centres:

```
row 0: 20.4047 32.4697 44.3653 56.388 68.4107 80.4757   (mod 6 = 2.4047)
row 1: 26.5007 38.3963 50.4613 62.484 74.5067 86.4023   (mod 6 = 2.5007)
dashes                                                   (mod 6 = 5.461)
```

Offset 3.0 mm = pwid/4, on both parities of row. **No printed dash coincides
with any patch centre anywhere on the sheet.**

Picture: `.progress/hex-build/R1-dashes-land-on-the-seams.png` — red = the
printed top-edge dash extended down the page, blue dots = recorded row-0 patch
centres, white dots = row-1. The blue and white dots sit in the middle of their
hexagons; every red line runs down the flat side where two columns meet.

**And on that same real sheet, the comb that was DROPPED would have been exact.**
23 rows, centres 23.4103, 35.0943, 46.7783, ... ; the side comb's dashes
11.6923, 17.5385, 23.3846, 29.2308, ... :

```
worst |row centre - nearest side dash| = 0.0308 mm   (mean 0.0140)
```

0.03 mm is a third of a pixel at 300 dpi. The engine refuses that comb and
prints the 3.0 mm one.

## R4 confirmed at whole-suite scale

The mesh mutation (`_cell_uv` emitting rectangles on a hexagonal grid) run
against the **entire everyday tier** in an isolated worktree, mutation grepped
in place, `__pycache__` cleared:

```
803:  pts += [(u, v), (u + w, v), (u + w, v + hh), (u, v + hh)]  # MUTANT
12322 passed, 323 skipped, 4 xfailed in 111.57s
```

**Nothing anywhere in the suite notices that the scanner mesh stopped drawing
hexagons.** Before this commit, `test_the_drawn_cell_is_a_hexagon` did.

## R3 severity, measured honestly

Dropping `patch_w` from `GEOM_BUILD_KEYS` and running the whole everyday tier:

```
88 failed, 12234 passed, 323 skipped, 4 xfailed
  e.g. test_the_layout_estimate_follows_the_chart_on_screen.py, test_layout_info_prediction.py
```

So the EXISTING None-default keys are covered by other tests, even though the
new guard misses them. What is not covered is a **new** one: a rotation argument
written as `rotate: float | None = None` would be invisible to the new test and
would have no legacy tests either. R3 is therefore a hole in a guard, not a live
defect. Downgraded accordingly.

## R5 — DEFECT (commit 1f4ff390): the app still tells the user, in two places, that helper markers are not drawn on a honeycomb.

**What I did.** `grep` for the claim the commit falsified.

```
ui/dialogs/layout_options_panel.py:241-245   (the "Patch shape" ⓘ, CR30)
    "Two costs, both real. The scanner and camera tools turn a honeycomb chart
     away unless you switch them on for it in Preferences → Beta; and the ruler
     helper markers are not drawn on a honeycomb, because it has no straight
     rows to line a ruler against. If you want either of those, stay on
     Rectangular."

ui/tabs/tab_chart.py:12881-12883   (the Hexagon-Patches details card, CR30)
    "...and the ruler helper markers are not drawn on a honeycomb, because it
     has no straight rows to line a ruler against."
```

Both are now false, and both are the exact text a user reads while deciding
whether to choose hexagons. One of them tells them to **stay on Rectangular**
for a cost that no longer exists — which is the opposite of what Basti asked
for ("they are optional anyway and benefitial here"). This is the same rule the
commit itself invokes for the engine: the premise is measurably false.

Related, smaller: the old refusal string

```
ui/dialogs/layout_options_panel.py:4331
  "This chart's patches are hexagons, which have no rows to lay a ruler
   against — so helper markers cannot be printed on it."
```

is now **unreachable** from the app. `set_helper_markers_supported` sets
`supported = bool(supported) or bool(one_axis_only)` before computing `tip`, and
the only production caller (`tab_chart.py:18362`) always passes the two as
complements — so `supported` is always True there and `tip` is always `""`.
The string, and its 13 translations, are dead weight; the `reason` parameter is
dead with it.

**Confidence: very high** for the two stale help texts (read them, they contradict
the shipped behaviour); **high** for the dead string (traced both call sites).

## R6 — the new user-facing tooltip states the inverted fact, and `geometry.py` already warned about exactly this mistake.

The greyed side switch now hovers with (added to 13 translation catalogues in
the same commit):

> "Not available on hexagonal patches. A honeycomb's patches sit in straight
> lines across the page but step sideways as they go down it, so dashes along
> the left and right edges would point at the gaps between patches rather than
> at the patches. The top and bottom dashes line up exactly and stay available."

The first clause is true, the conclusion is backwards. Left/right dashes mark a
**Y** coordinate, and on a honeycomb every row has one exact Y (0.03 mm,
measured above). Top/bottom dashes mark an **X**, which is the coordinate that
zigzags.

`helper_marker_lines_mm`'s own docstring, unchanged by this commit, states the
trap:

> "The names are the EDGE, never the axis: the top/bottom dashes are drawn as
> VERTICAL segments and the side ones as horizontal, **so anyone naming these
> after the segment gets them backwards.**"

That is the error. Verified reachable: on a honeycomb the group and master
tooltips are `''` and only the side switch carries this text.

Fixing R1 makes this string wrong in the other direction, so the 13 translations
added here will have to be redone.

## R1 — the axis-independent statement, and one honest caveat

The comparison above uses "distance to the nearest dash", which is the right
criterion only for an ODD `per_patch` (an even count deliberately has no dash at
the patch centre, Knut's rule). So here is the same thing without that
dependence. Over the full hex-capable matrix — 2 instruments x 15 papers x
spacer on/off x pscale {0.8, 1.0, 1.3} x offset_x {0, 3.7} x patch_w
{default, 9 mm} = **195,282 patches**, comparing each patch's centre with the
centre of the slot it belongs to:

```
|x offset from its slot centre| deviates from pwid/4 by at most 0.0800 mm
|y offset from its slot centre| is at most                      0.0389 mm
pwid/rrsp ratios seen across the whole matrix: [1.0]
```

**Every hexagon on every page is exactly a quarter of a patch width off its slot
in X and exactly on it in Y.** The comb is anchored on the SLOT lattice on both
axes. So the side comb is in phase with the patches on every configuration, and
the top/bottom comb is a quarter width out of phase on every configuration. No
paper, orientation, spacer setting, scale, offset or patch size changes this.

The caveat, stated because it is the only thing resembling a defence: at
`per_patch = 5` the X step becomes `pwid/4`, which coincides with the stagger,
so the X comb hits centres there (worst 0.08 mm over 696 configs). The shipped
default is 3, where the worst X error is 3.90 mm and the worst Y error is
0.0389 mm.

---

# VERDICT

**c62a7eb0 (pooling the hexagon) is safe to build on. 1f4ff390 (ruler markers on
a honeycomb) is not, and must not go into a beta as it stands.** The pooling
commit does what it says: I reproduced its "not one pixel moved" proof from a
clean worktree at 478c7396, showed the manifest actually fails when the renderer
stops rounding, and proved the two arithmetic substitutions bit-for-bit
identical over 2,007,264 hexagons and 400,000 stagger widths; the one behaviour
change (`contains` on a zero or negative width) is unreachable and is the safer
answer anyway; there is no import cycle and no measurable import cost. Its two
weaknesses are in the tests, not the code: the rewritten
`test_the_drawn_cell_is_a_hexagon` is vacuous — the whole 12,322-test everyday
tier stays green with the scanner mesh drawing squares over a honeycomb (R4) —
and the generated `GEOM_BUILD_KEYS` guard is blind to the nine `X | None = None`
arguments, which is exactly the shape the coming rotation option will take (R3).
The marker commit is a different matter: its central claim is inverted. The
stagger is applied to X and indexed by the position down the strip, so a
honeycomb's rows are exact in Y and zigzag in X — measured over 348
configurations, 195,282 patches, and on a real rendered CR30 sheet where every
printed dash lands on the seam between two hexagon columns, 3.0 mm from any
patch centre, while the comb it refuses to draw would have been correct to
0.03 mm (R1). The commit therefore ships the wrong comb, greys out the right
one, tells the user the opposite of the truth in the new tooltip (R6), leaves
two other help texts saying markers are not drawn on honeycombs at all (R5), and
reopens the "markers ticked, nothing prints" contradiction it inherited (R2).
The engine fix is a one-line swap of which flag is cleared, but it is a
behaviour change on ground Basti has just ruled on, so it needs his call rather
than a quiet correction. The whole-tree gate is green (12,478 passed, exit 0, no
worker-down banner, no timeout dump) — which is itself the finding that no test
in this suite can see R1.

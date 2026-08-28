STATUS: in-progress

# CR30 (#159) — final whole-feature critique

Agent: **CR30-FINAL-CRITIC**. Branch `feature/cr30-instrument-159`.
Mandate: break it. Report, do not fix. No production code or tests changed.

Sections are appended and committed as they are finished.

---

## Section 1 — ADDITION 1: the `area_first` + hexagons fix

Fix under review: commit **`bbb2105a`** ("cr30: area_first drew stretched
hexagons and lost patches doing it"), `workflow/layout_engine/area_fit.py`.
Two edits:

* `:97-98` — when `hflag` and `instruments.hex_capable(instrument)`, force
  `ratio = √3/2`, overriding whatever height-% the user set.
* `:283-285` — after every solver path, **snap** `ph = pw · √3/2`.

### 1.1 Is `plen = pwid · √3/2` the right constraint? — YES, derived not assumed

Taken from the renderer, not from the design doc.
`workflow/layout_engine/raster.py:928-946` (`_hexagon_points`) builds the
hexagon for a slot `w × ph` as:

```
top apex     (cx,      y0 −  ph/6)
upper-right  (x0+w,    y0 +  ph/6)
lower-right  (x0+w,    y0 + 5ph/6)
bottom apex  (cx,      y0 + ph + ph/6)
```

So the vertical side has length `5ph/6 − ph/6 = 2ph/3`, the across-flats width
is `w`, and total height is `4ph/3`. A **regular** hexagon with flat vertical
sides satisfies `w = √3 · s` with `s = 2ph/3`, hence

    ph = 3w / (2√3) = w · √3/2 .

`instruments.py:518-520` (SS) and `:658-660` (CR30) already build exactly that
in the *patch-first* base (`plen = pscale · √0.75 · 7.0` / `· 12.0`). **The
constraint is correct and it is the same one the rest of the engine uses.**

### 1.2 Should it constrain the SEARCH SPACE rather than be post-hoc? — the
### post-hoc snap is necessary, and the coordinator was right to add it

Forcing `ratio` alone is **not sufficient**, and I was about to report that as
the fix's hole before the snap landed. Reason, from the code: in this solver
`ratio` is only ever a **floor**. `area_fit.py:180-183` (`_floor_ph`) and the
comment at `:174-176` say so in as many words — *"The height-% is a MINIMUM"*.
`ph` is then produced by `_rows_filling_fit(_max_rows_at(h_min))`, which
**grows** the height to fill the page exactly, re-stretching the very
proportion the ratio was set to fix. Measured with the ratio-only version of
the fix in the tree (SS/A4/`by_width`): residual stretch **+1.00 %**, CR30
**+1.66 %** — better than +17 %/+20 %, not fixed.

And in `by_grid` with **both** dimensions pinned (`:232-235`) `ratio` is not
consulted at all, so a ratio-only fix would have left that path fully stretched.

The snap at `:283-285` is therefore load-bearing, not belt-and-braces.
**Verdict: the approach is right.** Constraining the search space instead would
mean rewriting `_rows_filling_fit`/`_max_rows_at` to solve on `pw` alone; the
snap reaches the same answer in three lines. See 1.5 for what it costs.

### 1.3 Rectangular layouts are unchanged — 5,040 combinations, byte-identical

Swept `7 instruments × 15 papers × 2 layout modes × 2 area methods × 3 grid
targets × 2 ratios × 2 borders = 5,040` recipes, recording
`(patches_per_page, columns, rows, pwid, plen, hxeh, hxew)` for each.

| | |
|---|---|
| pre-fix tree | isolated `git worktree` at `efaecdbd` (the fix's parent) |
| post-fix tree | working tree at `bbb2105a` |
| **rectangular combinations that differ** | **0 / 5040** |

**The mutation is proven to land** (my memory's rule: a probe whose two sides
agree is a broken probe until proved otherwise). Control case
`SS|hex|A4|area_first|by_width|border 6`:

```
before: [988, 26, 38, pwid 7.18, plen 7.25]     <- stretched, 988 patches
after : [1170, 26, 45, pwid 7.18, plen 6.22]    <- regular,  1170 patches
```

⚠ **Process note against myself.** My first attempt at this comparison used
`git stash` on the shared tree; the coordinator committed while it was stashed
and the "before" run silently measured the *fixed* code, producing `0 differ`
on the hexagon sweep too — a textbook false no-op. The worktree run above
replaces it. **Do not stash a tree another agent is editing.**

### 1.4 The bug was much larger than reported, and the fix much better

Stretch = `(plen/pwid)/(√3/2) − 1` over every hex-capable combination:

| | min | max | mean abs |
|---|---|---|---|
| before | **−75.21 %** | **+203.97 %** | **12.91 %** |
| after | −0.13 % | +0.11 % | **0.02 %** |

The +17 %/+20 % in the brief is only the A4 `by_width` case. The `by_grid`
paths were far worse — up to a hexagon drawn **three times too tall**, and
`SS|594x420|by_grid|20 cols` drew a 28.6 × 6.14 mm sliver (−75 %). The residual
±0.13 % is the `math.floor(·*100)/100` at `:288`, i.e. 0.01 mm quantisation.
**Nothing is left of the defect.**

### 1.5 SERIOUS — the snap costs up to 76 % of capacity, and only in `by_grid`

579 combinations gained patches; **111 lost them. Every single one is
`by_grid`; `by_width` loses none.** Worst cases:

| recipe | before | after | |
|---|---|---|---|
| `SS · A2 (594×420) · by_grid · 20 cols` | 1360 | **320** | **−76.5 %** |
| `SS · A3+ (483×329) · by_grid · 20 cols` | 1020 | **300** | −70.6 % |
| `SS · A2 · by_grid · 20 cols` | 1940 | **660** | −66.0 % |
| `CR30 · A2 · by_grid · 20 cols` | 800 | **320** | −60.0 % |
| `CR30 · A4 · by_grid · auto` | 405 | 390 | −3.7 % |

**The new numbers are the geometrically honest ones** — pinning 20 columns
across an A2 forces a 28.6 mm-wide hexagon, and a regular one that wide is
24.8 mm tall, so 16 rows is all that fits. The old 1360 came from drawing
28.6 × 6.14 mm slivers and calling them hexagons. So this is **not a
regression in correctness**.

It is a serious *user-facing* surprise: a SpectroScan user who pins columns on
a large sheet ticks "hexagon patches" and watches the chart fall from 1360
patches to 320 with no explanation. Ranked SERIOUS on that basis alone.
**CR30-specific? No — pre-existing SpectroScan behaviour, exposed by #159.**

### 1.6 SERIOUS — `by_grid`'s row pin is violated by hexagons (pre-existing,
### NOT caused by this fix)

Asking `by_grid` for exactly 10 columns × 10 rows:

| | 10×10 delivered exactly |
|---|---|
| rectangular | **406 / 420** |
| hexagonal, **before** the fix | 290 / 420 |
| hexagonal, **after** the fix | **290 / 420** |

Identical before and after, so **the fix neither causes nor worsens it** — but
a hexagonal `by_grid` chart honours an explicit row pin in 69 % of cases against
96 % rectangular. Observed deliveries for a 10×10 request include 10×8, 10×9
and 10×17. A honeycomb's aspect is fixed, so columns and rows are
**over-determined**: at most one may be pinned. The engine should say so rather
than quietly deliver a different grid.

### 1.7 `area_method` and `area_min_patch` — checked, both still mean what they say

* **`by_width`** — clean. `area_min_patch` is a *width* floor and the snap only
  touches the height, so the control is untouched. All 579 gains, 0 losses.
* **`by_grid`** — the two findings above.
* **`area_min_patch`** still means "minimum patch **width**". Confirmed by
  sweeping it at 0.0 / 8.0 mm: `pw` never falls below the typed value on any
  hex-capable combination.
* **`area_ratio` is now silently dead for a honeycomb.** `:97-98` overwrites
  it before any solver path reads it, and `:283-285` overwrites the result
  again. Proved: user ratios of 0.0 / 0.5 / 1.0 / 2.0 all produce byte-identical
  output on SS and CR30 with `hflag`. The reasoning is right (a hexagon's
  proportions are not the user's to choose) but the **panel still offers the
  control**, so it is a live widget that does nothing — see Section 7.

### 1.8 What "the area target can no longer be met exactly" actually costs

Because the snap replaces a height that filled the box, area-first no longer
fills the page vertically. Measured, `by_width`, 6 mm border:

| instrument | paper | rect fill | hex fill | worst unused |
|---|---|---|---|---|
| SS | A4 | 99.9 % | 98.9 % | 3.03 mm |
| SS | A3 | 99.9 % | 98.8 % | 4.69 mm |
| CR30 | A4 | 100.0 % | 98.3 % | 4.81 mm |
| CR30 | A3 | 100.0 % | 97.7 % | **9.28 mm** |

**The worst case (9.28 mm) is still less than one CR30 hex row (10.39 mm), so
no row is ever lost to it.** The width still fills exactly. This is the correct
trade and it is cheap. Not a finding — recorded so nobody "fixes" it later.

### 1.9 Verdict on ADDITION 1

The fix is **correct, complete and safe**. It removes a genuine defect that was
far larger than reported, changes no rectangular layout in 5,040 checked
recipes, and leaves ±0.01 mm of quantisation. Two SERIOUS items it exposes
(1.5, 1.6) are both in `by_grid`, both pre-existing SpectroScan behaviour, and
both are about *telling the user*, not about geometry.
---

## Section 2 — ADDITION 2: the three Measure-tab overlays, driven on screen

**Verdict: all three overlays land on the ink, in all four CR30 cases and in
`by_grid` too. 18/19 checks pass; the one failure is my own probe's integrity
guard firing correctly (§2.3).**

### 2.1 Method — pixels, not eyes

Driver: `scratchpad/drive_cr30_overlays.py`, adapted from the project's own
`scripts/drive_hex_overlay_matrix.py`. It builds a flat-grey chart with **one
magenta patch**, opens it in the **real Measure tab of the real MainWindow**,
asks the app to act on the patch *it* believes is the magenta one, then measures
the result in screen pixels. Settings are copied into a sandbox `.ini`
(`settings._qs = dst`) and the real plist was backed up first.

Cases: CR30 × {rectangular, hexagonal} × {`patch_first`, `area_first`}, plus
CR30 hex `area_first`+`by_grid`, plus SpectroScan hex `area_first` as a control.
120 patches, A4, 6 mm border, spacers off, no randomisation.

### 2.2 Results — every overlay, every case

| case | chart built | 1 highlighter offset | 2 split uncovered | 3 only-measured kept |
|---|---|---|---|---|
| CR30 rect `patch_first` | 12.06 × 12.06 mm | dx −0.5 dy −1.5 px | 0.0 % | 98.4 % |
| CR30 hex `patch_first` | 11.94 × 10.41 mm | dx +0.4 dy −0.3 px | 2.2 % | 96.7 % |
| CR30 rect `area_first` | 19.05 × 23.75 mm | dx +1.0 dy +0.5 px | 0.0 % | 100.0 % |
| CR30 hex `area_first` | 20.07 × 17.27 mm | dx −2.2 dy −1.2 px | 0.0 % | 99.5 % |
| CR30 hex `area_first`+`by_grid` | 15.24 × 13.21 mm | dx −2.1 dy −1.3 px | 0.0 % | 99.3 % |
| SS hex `area_first` (control) | 20.07 × 17.27 mm | dx −2.2 dy −1.2 px | 0.0 % | 99.5 % |

* **1 — the patch highlighter.** Every ring centre is within **2.2 px** of the
  magenta ink's centre at the on-screen scale. **No half-patch offset anywhere**
  — which is the specific failure the earlier stagger blocker warned about, and
  the reason this had to be driven rather than unit-tested.
* **2 — expected-vs-measured.** The diagonal split covers the patch completely.
  The 2.2 % residue on `CR30 hex patch_first` is the hexagon's **apex tips**,
  which the split's clip leaves a few pixels of — cosmetic, present on the
  SpectroScan too, not introduced by #159.
* **3 — only show measured patches.** Unread patches are blanked to **true
  hexagon outlines** (not rectangles) on hex charts and to rectangles on
  rectangular ones; the one read patch keeps its split, in the right shape, in
  the right place.

**I read the screenshots, I did not only read the numbers.** The contact sheet
shows square rings on square patches, hexagonal rings on hexagons, and the
only-measured view drawing a real honeycomb of empty cells. On the first run
the numbers said 15/15 PASS while the picture showed
`CR30 rect area_first` drawing **page-wide horizontal bars** — see §3.4. The
numbers alone would have shipped that.

### 2.3 My own probe caught itself — SS and CR30 really do converge

The integrity guard fingerprints each built chart and refuses to let two cases
be silently identical. It fired:

```
[FAIL] SS hex area_first :: PROBE INTEGRITY
       — identical chart to CR30 hex area_first
```

**This is a true property, not a broken probe.** In `area_first` the patch size
is *derived from the page and the patch count*, so the instrument's own cell
size never enters — a CR30 `area_first` chart is geometrically **identical** to
a SpectroScan one. Confirmed independently: both give 20.07 × 17.27 mm at 120
patches on A4, and both give the same grid across the whole `by_grid` sweep in
§1. Consequence for #159 in §3.5.

### 2.4 Proof saved to the Desktop

| file | what it shows |
|---|---|
| `~/Desktop/cr30-overlay-proof-matrix.png` | the contact sheet: 3 overlays × 6 cases, cropped on the magenta patch, with the measured offset on each |
| `~/Desktop/cr30-overlay-proof-1-highlighter-rectangular.png` | full Measure preview, CR30 square chart, ring on the patch |
| `~/Desktop/cr30-overlay-proof-1-highlighter-hexagonal.png` | same, honeycomb — hexagonal ring |
| `~/Desktop/cr30-overlay-proof-1-highlighter-hexagonal-area-first.png` | same, honeycomb sized by `area_first` |
| `~/Desktop/cr30-overlay-proof-2-expected-vs-measured-rectangular.png` | the split overlay across a whole square CR30 sheet |
| `~/Desktop/cr30-overlay-proof-2-expected-vs-measured-hexagonal.png` | the split drawn as hexagons, not squares |
| `~/Desktop/cr30-overlay-proof-2-expected-vs-measured-hexagonal-area-first.png` | same, `area_first` sizing |
| `~/Desktop/cr30-overlay-proof-3-only-measured-rectangular.png` | unread patches blanked, read patch kept |
| `~/Desktop/cr30-overlay-proof-3-only-measured-hexagonal.png` | **the clearest one** — a full honeycomb of empty cells with the single read hexagon at C10, matching the drawn column/row labels |
| `~/Desktop/cr30-overlay-proof-3-only-measured-hexagonal-area-first.png` | same, `area_first` sizing |

**Nothing in the hex/stagger work or the `area_first` fix has broken any of the
three overlays.** ADDITION 2 is clear.

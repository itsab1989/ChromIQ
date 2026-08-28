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
---

## Section 3 — Does the CR30 behave like every other instrument?

### 3.1 BLOCKER — "the four failing tests are pre-existing" is FALSE. #159 broke them.

The brief asked me to verify this claim independently. **It does not hold.**

| tree | `tests/test_both_readers_raise_the_same_windows.py` |
|---|---|
| `feature/cr30-instrument-159` | **4 failed, 26 passed, 2 skipped** |
| `master` (isolated `git worktree`) | **30 passed, 2 skipped** |

The four are `test_the_helper_really_prints_that_line[capability / ccmx_read /
ccmx_set / mode_set]`.

**Cause, exactly.** The test pins the source line of four `printf`s in
`native/chartread_helper/chromiq_chartread.c` and matches within an **11-line
window** (`tests/…:114`, `text[src_line-6 : src_line+5]`). #159 inserted **21
lines** earlier in that file (`7711b16c`, `b02936c5`), so every pin fell out of
its window:

| label | pinned at | master | branch | shift |
|---|---|---|---|---|
| `capability` | 1022 | 1022 | **1043** | +21 |
| `ccmx_set` | 1081 | 1081 | **1102** | +21 |
| `ccmx_read` | 1103 | 1103 | **1124** | +21 |
| `mode_set` | 1427 | 1427 | **1448** | +21 |

All four strings are still present, unmodified, and reachable — **no behaviour
is broken.** The fix is to change four integers in
`tests/test_both_readers_raise_the_same_windows.py:35-42` to
**1043 / 1102 / 1124 / 1448**.

**Ranked BLOCKER anyway, and the ranking is about the claim, not the code.**
The branch cannot produce a green `--runslow` gate, and CLAUDE.md is explicit
that a green gate is what a merge decision requires. More importantly, a
regression labelled "pre-existing" without checking is exactly how a real one
ships: this one was harmless, and nobody would have known that until it was
looked at. **CR30-specific.**

### 3.2 SERIOUS — the shared hexagon/density checkbox leaks in BOTH directions,
### and it changes the printed sheet

`ui/tabs/tab_chart.py:11838-11934` (`_update_dd_visibility`). One `QCheckBox`
(`_dd_check`, created at `:3491`) serves three instruments with **two different
meanings**:

| instrument | what the box means | branch |
|---|---|---|
| ColorMunki | **Double density** — halves the patch width, *requires the physical rig accessory* | `:11842` |
| CR30 | **Hexagon patches** | `:11862` |
| SpectroScan | **Hexagon patches** | `:11904` |

It is force-unchecked **only in the `else:` branch** (`:11922-11927`), i.e. only
when it becomes *hidden* (i1 / i1Pro3 / DTP41 / DTP51). All three instruments
above keep it visible, so the state carries across them unchanged.

**Driven in the real app, Guided and Manual, and read off the built `Geom` —
not from the code:**

```
GUIDED
  CM  + "Double density" ticked  ->  switch to CR30
      dd_box=True   geom.hexagonal=True   plen=10.392  pwid=12.000
      -> the sheet is a HONEYCOMB the user never asked for

  CR30 + "Hexagon patches" ticked ->  switch to CM
      dd_box=True   pwid=13.700      (ColorMunki, double density)
      dd unticked   pwid=28.000      (ColorMunki, normal)
      -> a DOUBLE-DENSITY ColorMunki chart, which needs the rig accessory
MANUAL — byte-identical results.
```

Both directions are real and both reach the geometry, so both reach paper.
Direction B is arguably the worse one: the user ticked a box labelled *"Hexagon
patches (suits the round CR30…)"* and is handed a ColorMunki chart that
**cannot be read at all without hardware they may not own**.

SS ↔ CR30 also carries, but there the box means the same thing on both sides,
so it is defensible rather than wrong.

**Escape hatch that exists today:** passing through any instrument that hides
the box clears it —
```
CM(dd) -> SS   : still ticked
       -> i1   : cleared
       -> CR30 : clear
```
so the bug only bites on a *direct* CM↔CR30 or CM↔SS move.

**Fix:** clear the box whenever the instrument change crosses the
meaning boundary — cheapest correct form is to record which instrument the
current tick belongs to and clear it on any change where
`instruments.hex_capable(old) != instruments.hex_capable(new)`; simplest safe
form is to clear it on **every** instrument change. Do not widen the existing
`else:` — the box is visible in the failing cases, so visibility is the wrong
test.
**CR30-specific? Half.** CM↔SS is pre-existing; #159 added the CR30 as a third
member and a second direction, and the earlier critique (report 06 §6.2)
already ranked this SERIOUS and it is still open at `11c3e592`.

### 3.3 What survived: the round trip leaks nothing else

I snapshotted **every** `QCheckBox` / `QComboBox` / `QSpinBox` /
`QDoubleSpinBox` / `QRadioButton` in the Create Chart tab (visibility, enabled
state, value and label), walked
`CR30 → i1 → CM → SS → CR30 → i1 → CR30` in **Guided and Manual**, and diffed
the second visit against the first.

**No control other than `_dd_check` carries a value across an instrument change
that it should not.** Visibility and enablement track the instrument correctly:
`_td_check` (triple density) is CM-only, `_for_rig_label` is CM-only
(`:11934`), and the CR30 shows the hexagon box with its own label and its own
tooltip.

⚠ **One honest caveat, so nobody over-reads this.** Create Chart holds **one
shared set of controls, not per-instrument state.** Paper, page count and the
density/hexagon box are global: switching to another instrument and back does
*not* restore what you had. That is the existing design of the tab, it applies
equally to every instrument, and #159 does not change it — but it is why the
"revisit" diff is only meaningful for the `_dd_check` case above, and it is
worth confirming with Basti that it is intended for the CR30 too.
---

## Section 4 — Cross-tab: the FWA gate is correct and lands on a dead mechanism

### 4.1 SERIOUS — `_gated_options` is never populated, so nothing is ever greyed out

#159 does the right thing in `ui/tabs/tab_profile.py:4089-4102` and
`ui/tabs/tab_check_refine.py:242-255`: `_gate_active()` becomes
`spectral_options_unavailable(instrument, has_spectral)`
(`ui/ti2_loader.py:137-160`), so a CR30 `.ti3` — colorimetric by design —
answers **True** for the spectral-only colprof options (`-f` FWA, illuminant,
observer). **Verified in the running app: `gate_active` is `True` for a CR30
`.ti3` and `False` for an i1Pro one with spectra. That half is right.**

**But the gate acts on a list nothing ever fills.**

```
ui/tabs/tab_profile.py:325        self._gated_options: list[GatedOption] = []
ui/tabs/tab_profile.py:4107           for opt in self._gated_options:   # grey out
ui/tabs/tab_profile.py:5293           for opt in self._gated_options:   # neutralise
ui/tabs/tab_check_refine.py:130   self._gated_options: list[GatedOption] = []
ui/tabs/tab_check_refine.py:260 / :1735   same two loops
```

`grep -rn "_gated_options" --include='*.py' .` returns **exactly those six
lines and nothing else**. There is no `.append`, no `.extend`, no assignment of
a non-empty list, anywhere in the repository. `GatedOption` is defined at
`ui/widgets.py:3563` and **never constructed.**

Measured in the running app with a CR30 `.ti3` loaded:

```
gated option registry length : 0
gate_active for a CR30 ti3   : True
   _m_fwa_check           enabled=True     <-- should be greyed out
   _m_illum_combo         enabled=True     <-- should be greyed out
   _m_obs_combo           enabled=True     <-- should be greyed out
   user ticked FWA on a CR30 measurement -> True
   _collect_params -> fwa_enabled = True   <-- neutralise() did not fire either
```

`workflow/profile_builder.py:346-347` then does
`args.append("-f" ...)`, so **`colprof -f` is run on a measurement with no
spectral data.**

### 4.2 What that actually costs — measured with the real ArgyllCMS 3.5.0

Built a genuine colorimetric-only CR30-shaped `.ti3` (125 RGB→XYZ patches, no
`SPECTRAL_*`, `TARGET_INSTRUMENT "CR30"`) and ran the shipped binary:

```
colprof -qm       ->  profile written, 104,380 bytes
colprof -qm -f    ->  Error - Requested spectral interpretation when data not
                      available          (no profile written)
```

**It fails loudly, it does not produce a quietly-wrong profile.** That is the
one piece of good news here and it is why this is SERIOUS and not a BLOCKER: a
CR30 user who ticks FWA gets a failed build and a raw Argyll error sentence
instead of the greyed-out control the code intends. Nothing bad is shipped;
something confusing is.

**CR30-specific? NO — pre-existing, and it is dead on `master` too.** The same
six lines and the same empty list are in the `master` worktree, so the gate has
never worked for the **ColorMunki** either, which is the case it was originally
written for. #159 correctly extended a mechanism that was already inert. It is
in this report because #159 is the first instrument whose `.ti3` has **no
spectra at all** — the ColorMunki at least has a spectrum for `-f` to chew on,
so the dead gate cost it accuracy; for a CR30 it costs a hard failure.

**Fix:** construct the `GatedOption`s. Each needs `widgets=[…]` (the FWA check,
its illuminant combo, the illuminant combo, the observer combo — Guided *and*
Manual copies: `_fwa_check`/`_m_fwa_check`, `_illum_combo`/`_m_illum_combo`,
`_obs_combo`/`_m_obs_combo`, `_fwa_illum_combo`/`_m_fwa_illum_combo`) and a
`neutralise` that clears `params.fwa_enabled` / `illuminant` / `observer`. Both
tabs. This is a pre-existing repair #159 makes urgent, not a #159 defect.

### 4.3 What survived cross-tab

* Build Profile and Check & Refine **agree** about the instrument — both read
  it through the same `ui/ti2_loader` helpers and both return the same
  `_gate_active()` for the same `.ti3`.
* An i1Pro measurement with spectra is **not** collaterally gated
  (`gate_active=False`), so the new `has_spectral` term has not broken the
  ordinary case.
* `spectral_options_unavailable` defaults `has_spectral=True`
  (`ti2_loader.py:159`), so a caller that never looked is judged on the
  instrument alone — exactly as before #159. No behaviour change for existing
  callers.

---

## Section 5 — Boundaries, extremes and backward compatibility

### 5.1 Degenerate layouts fail cleanly — no crash, no hang, no silent nonsense

Every case built through the real engine (`chart.build_chart`, CR30, spacers
off, TIFFs actually rendered):

| case | result |
|---|---|
| 1 patch, rectangular | 1 page, 1 TIFF, 11.94 mm cell |
| 1 patch, hexagonal | 1 page, 1 TIFF |
| 2 patches, hexagonal | 1 page, 1 TIFF |
| smallest paper 4×6" (102 × 152 mm) | 1 page, 66/page |
| 4×6", hexagonal | 1 page, 72/page |
| 5×7" with a **0 mm** border | 1 page, 126/page |
| largest paper A2 | 1551/page |
| A2 hexagonal | 1728/page |
| **patch 200 mm wide** | `LayoutError: not enough width for even one row` |
| **patch 400 × 400 mm** | `LayoutError: paper too short: a single pass of patches does not fit (278.0 mm available)` |
| **border 200 mm (larger than the page)** | `LayoutError: paper too short … (-110.0 mm available)` |
| 3000 patches | 9 pages, 9 TIFFs |
| 3000 patches hexagonal | 8 pages, 8 TIFFs |

**Nothing hangs, nothing crashes, and every refusal names a number the user can
act on.** Multi-page and single-patch both work; hexagons with one row work.

### 5.2 MINOR — a patch smaller than the aperture still builds

```
patch 3.0 mm  -> OK, 5796 patches/page
patch 0.1 mm  -> OK, 952,000 patches/page
```
The CR30's window is **4 mm**, so a 3 mm patch cannot be read and a 0.1 mm one
is nonsense. Reachable only from the Manual patch-size boxes, and the ruling I
was given says there is **no aperture/minimum-patch guard** — so this is
*intended*.

⚠ **But the design document disagrees with the ruling.**
`docs/cr30_reports/02-design.md` §11 still ends with:

> ⚠ **Not yet done:** #159 line 483 requires that a patch smaller than the
> aperture is *refused at layout time, not on paper*. No guard exists.

One of the two is stale. Per the "design specifications are binding" rule in
CLAUDE.md this is not mine to resolve: **either the ruling supersedes #159 line
483 and §11 should say so, or the guard is still owed.** Flagged for Basti.

### 5.3 Backward compatibility — no existing chart changes

Built the same 200-patch `.ti1` for **every** non-CR30 instrument × both
`hflag` states through the branch's engine and hashed each `.ti2`; combined
with the 5,040-recipe rectangular sweep in §1.3 (0 differences against the
pre-fix tree) and report 06 §5's proof, **nothing about a non-CR30 chart moves.**

The mechanism is sound rather than accidental:
* `data/patch_db.py:194` deliberately keeps `CR30` **out** of
  `EXTERNAL_INSTRUMENTS` (that set also hides members from the Guided combo),
  and keeps printtarg away by forcing the engine instead.
* `ui/ti2_loader.py:44-53` adds `"CR30"` to `KNOWN_INSTRUMENTS` and documents
  in place why that is *not* the same question as "a name ArgyllCMS accepts",
  with `TabMeasure._blocked_by_stock_chartread_for_cr30`
  (`ui/tabs/tab_measure.py:4406`) asking the second question separately.
* `core/settings.py:670` adds only a label; no existing key changes meaning.
* An old `.ti2` has no `CR30` keyword, so every new code path is keyed off a
  value old files cannot carry.

**No new deletion path is introduced.** #159 adds no `rmtree`, no `unlink`, and
no rename over an existing artefact; the run-folder model of `#127` is
untouched.

### 5.4 MINOR — an `area_first` CR30 chart silently abandons the 12 mm ruling

Proved in §2.3: at 120 patches on A4, `area_first` gives a CR30 **20.07 ×
17.27 mm** cell — and a SpectroScan the **identical** chart, because in
`area_first` the patch size is derived from the page and the instrument's own
cell never enters. `presets.default_recipe` already defends against this by
defaulting the CR30 to `patch_first` (`presets.py:422-423`) with a good
explanation. But a Manual user who switches to area-first gets a cell size
unrelated to the ruled 12 mm, and **nothing says so** — while the hexagon
tooltip is still quoting figures measured at 12 mm. Worth one sentence in the
layout-info panel when a CR30 chart is area-first.
---

## Section 6 — The measure path: what a CR30 measurement does today

### 6.1 BLOCKER — the bundled helper binary is STALE, and a packaged beta
### would refuse every CR30 chart

`native/chromiq-chartread` is a **git-tracked binary** (`git ls-files` confirms
it) and `ChromIQ.spec:110-113` bundles that exact path into `dist/ChromIQ.app`.
**#159 edited `chromiq_chartread.c` and did not update it.**

```
native/chromiq-chartread                            Aug 15 02:44   *** STALE ***
dist/ChromIQ/_internal/native/chromiq-chartread     Aug  6 22:37   *** STALE ***
dist/ChromIQ.app/…/native/chromiq-chartread         Aug  6 22:37   *** STALE ***
native/chartread_helper/build/chromiq-chartread     Aug 28 20:43   CR30-aware
```

(Test: `strings <binary> | grep "which ChromIQ reads itself"` — the new CR30
message. Present only in the build tree.)

**Run against a real CR30 chart, both binaries:**

```
STALE   native/chromiq-chartread Chart
   chromiq-chartread: Error - Unrecognised chart target instrument 'CR30'

FRESH   native/chartread_helper/build/chromiq-chartread Chart
   chromiq-chartread: Error - The chart was made for 'CR30', which ChromIQ
   reads itself. Measure it in ChromIQ, or use -x to supply values.
```

**Why this bites only when packaged.** `workflow/chartread_engine.py:41-49`
searches `$CHROMIQ_CHARTREAD` → **the CMake build tree** → `native/`. In a
source checkout the build tree wins, so every developer and every test sees the
correct binary. **A frozen build has no build tree and falls through to the
stale `native/` copy.** The feature therefore works perfectly for everyone
testing it and is dead in the artefact handed to a tester.

**Fix:** rebuild the helper and commit the result to `native/chromiq-chartread`
(and the Windows/Linux equivalents) in the same commit as any
`chromiq_chartread.c` change — or make the release step build it, as
`ChromIQ.spec:99-101` already says the gammap helper's CI step does.
**CR30-specific.**

### 6.2 The C side itself is right — verified against the built binary

| invocation | result |
|---|---|
| stock ArgyllCMS `chartread Chart` | `Error - Unrecognised chart target instrument 'CR30'` — **exactly the documented price of the honest name**, working as ruled |
| fresh helper, no `-x` | the CR30-specific message above: names the device, names the cause, names the two ways out |
| fresh helper `-xx` | `Ready to read patch '1' at 'A1' / Enter XYZ value…` — spot mode, patch by patch |
| fresh helper `-xl` | same, `Enter L*a*b* value` |

`chromiq_chartread.c:3740-3751` is the gate: the error is skipped once
`cq_external_instrument_named` is set, and the chart's own `TARGET_INSTRUMENT`
is carried into the `.ti3`. Sound.

### 6.3 The guard in the Measure tab behaves exactly as designed

Driven with a real CR30 `.ti2` loaded in the real Measure tab:

```
chartread_engine='argyll'    _engine_selected()=False  blocked_for_cr30 = True
chartread_engine='chromiq'   _engine_selected()=True   blocked_for_cr30 = False
```

* `TARGET_INSTRUMENT "CR30"` is written honestly into the `.ti2` — confirmed by
  reading the file.
* `ui/ti2_loader.read_target_instrument` → `'CR30'`, `is_cr30` → `True`.
* The preview gets `_no_swipe=True` and `_hex_zigzag=False` for a rectangular
  CR30 chart — the two flags correctly kept separate
  (`ui/tiff_preview.py:607-614`, `:1481-1500`).
* `M-CR30-STOCK-READER` is in `workflow/measurement_messages.CATALOGUE` with
  `approved=False`, exactly as the §7 rule in `02-design.md` requires.

### 6.4 SERIOUS — nothing can actually take a reading, and Start is not blocked

**`workflow/cr30/` is imported by nothing.** Exhaustive check:

```
grep -rn "from workflow.cr30\|workflow\.cr30" --include='*.py' .
  tests/test_cr30_colour_tables.py:18   <- the ONLY consumer
```

Twelve modules and ~1,900 lines (`device.py`, `ble.py`, `session.py`,
`measurement.py`, `transport.py`, `usb_measure.py`, `discovery.py`,
`identity.py`, `frame.py`, `colour.py`) are vendored and unreferenced.
`measure_manager.py` and `chartread_engine.py` contain **no occurrence of
"CR30" at all**, and **nothing anywhere passes `-x`** (the only external-ish
flag either builds is `--xychart`, `measure_manager.py:448`).

This matches the implementer's own §U.12 in `04-impl-python.md` — *"Nothing in
the reading path was implemented — that is the C work, by the brief"* — so it
is a known gap, not a surprise. **I am reporting it because of what it means at
the UI, which is not written down anywhere:**

> With `chartread_engine = 'chromiq'`, the CR30 guard **deliberately stands
> down** (§6.3), so **Start is enabled on a CR30 chart** — and there is no
> `-x`, no device opened by ChromIQ, and no source of values.

The helper is then launched without `-x` and hits the branch at
`chromiq_chartread.c:3747`, so with the **fresh** binary the run dies
immediately with the clear CR30 message (good), and with the **stale** one with
the Argyll message (§6.1). Either way it fails fast rather than hanging — I
could not reach a hang, a crash, or a silent no-op on any path I drove.

**But the failure surfaces as a raw helper error after the user pressed Start,
not as an honest "not yet" before it.** For a beta the Measure tab should say
so up front. **CR30-specific.**

### 6.5 What survived here

* No path hangs. Every terminal state I could drive is a clean error with a
  readable sentence.
* No path records a wrong measurement, because no path records one at all.
* Per-patch `.ti3` autosave, `-r` resume and the `TARGET_INSTRUMENT` identity
  chain are all C-side and already tested (`tests/test_target_instrument_gate.py`,
  `tests/test_cr30_external_values.py`).

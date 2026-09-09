# 10 — EIGHTH adversarial review (round 8), commit `e6bcabc3`

Branch `feature/nelson-photocard-presets`. Bar: *would I sign this off to print on a
paying customer's paper, and to be tagged stable tonight.*

Proof folder: `~/Desktop/ChromIQ-hex-proof/15-eighth/`.

**The metric used throughout.** Every claim about a strip letter below is read off the
INK of a real built sheet, never off a recorded rectangle:

* build the chart through `presets.default_recipe` -> `chart.build_from_recipe`, the same
  path Create Chart uses;
* mask every recorded patch rect, widened HORIZONTALLY by the hexagon's own half-overshoot
  `hxew` (a hexagon's left/right points are drawn *outside* its recorded box — this cost me
  one false reading of 110 px "letters" that were a neighbouring black hexagon);
* per strip, the bbox height of the surviving dark ink above the band;
* the reference is **that same letter drawn alone** with the sheet's own font, size and
  rotation. A letter the patches painted over measures SHORTER than its own isolated render.
  Per-letter, because in a script font `A` and `B` are not the same height and a
  cross-strip percentile reads that as a cut.

---

## M1 — the ink reserve is FONT-BLIND. `label_ink_bottom_mm` assumes the letters stop at `ind_px`; Pillow draws them to the font's ASCENT. A turned honeycomb still cuts its strip letters, by up to 1.61 mm. **Ships-with-it (named), and the commit message's absolute claim is wrong**

### The mechanism

`raster._furniture_reserves_mm` computes, for an upright label,

```python
_drawn = ind_px / mm2px          # "the font's FULL pixel size", per the comment
ink_bottom = strip_label_offset_mm + _drawn + _rule
```

and `render_pages` draws the letter with `_draw_indicator(..., anchor="la")` at `_lbl_top`.
`anchor="la"` is *ascender*-left, so the glyph's ink runs down to `_lbl_top + ascent`, not to
`_lbl_top + ind_px`. `ascent` is a font property and is **not** bounded by the nominal size.

Measured directly (`_font(71, fam)`, ink bottom of `W` drawn at `anchor="la"`, y relative to
the anchor; `ind_px = 71`):

| font | ink bottom | over-run vs `ind_px` |
|---|---|---|
| JetBrains Mono (bundled, default) | 73 | +2 px (0.17 mm) |
| Inter (bundled) | 69 | −2 px |
| Instrument Serif (bundled) | 71 | 0 |
| Futura | 78 | +7 px |
| Arial Black | 79 | +8 px |
| Comic Sans MS | 81 | +10 px |
| Chalkboard SE | 83 | +12 px |
| Noteworthy | 92 | +21 px (1.78 mm) |
| Diwan Kufi | 99 | +28 px |
| Zapfino | 138 | +67 px |

`LABEL_INK_CLEARANCE_MM` is 0.5 mm = 5.9 px at 300 dpi, so anything over-running by more
than ~6 px eats the whole clearance and prints on the patch.

**This is reachable from the UI in one click.** `layout_options_panel._populate_font_combo`
adds the three bundled families, a separator, and then **every family
`QFontDatabase.families()` reports** — 197 on this machine. The tooltip advertises it:
*"Bundled fonts are listed first, then every font installed on your system."*

### Measured on real sheets — A4, CR30 honeycomb, 345 patches, 300 dpi, TURNED

Explicit 6 mm label (an Expert-Options row the commit's own test set claims to cover):

| font | worst letter cut, turned | pointy control |
|---|---|---|
| **Noteworthy** | **19 px = 1.61 mm** | 18 px |
| Chalkboard SE | 8 px = 0.68 mm | 16 px |
| Comic Sans MS | 8 px = 0.68 mm | 12 px |
| Arial Black | 5 px | 9 px |
| JetBrains Mono / Inter / Instrument Serif | 0 | 0 / 0 / 14 px |

At **auto** size, turned, otherwise the plain default recipe, a sweep of all 200 families:
7 cut (Noto Nastaliq Urdu 2.46 mm, Diwan Kufi 2.46 mm, Noto Sans Myanmar 1.69 mm, Noto Serif
Myanmar 1.19 mm, DecoType Naskh 0.93 mm, Noteworthy 0.42 mm, Farisi 0.42 mm).
Rotations 90 and 270 never cut (there the reserve uses a real tile height); **0 and 180 do**.

Pictures (both at 2x, same crop, same 345-patch recipe):
`M1-Noteworthy-turned.png` — A, C and E, on the raised strips, have their bottoms sliced
off by the hexagon edge; B, D and F on the lowered strips are whole.
`M1-Noteworthy-pointy.png` — the control: every letter clipped by an apex.

### Why it is NOT a release blocker, stated honestly

For the same settings the POINTY sheet is cut as badly or worse (Chalkboard 16 vs 8,
Comic Sans 12 vs 8, Noteworthy 18 vs 19), and the pointy overlap is byte-identical shipped
behaviour that `e6bcabc3` itself measured and deferred to 4.2.2. With all three **bundled**
fonts a turned sheet is clean at every size, rotation and offset I could reach. So the turn
does not make the sheet worse than the orientation it is an alternative to.

### What IS wrong and must not ship as written

`e6bcabc3`'s message says **"Not one of 4,608 turned sheets prints a letter on a patch."**
That cross had no FONT axis. The sentence is true for JetBrains Mono and false for
Noteworthy at 6 mm. Anything that repeats it in the CHANGELOG has to be scoped to the
bundled fonts, or dropped. (Checked below, M-changelog.)

---

## M2 — **THE NINTH SELF-VALIDATING TEST.** All six of `e6bcabc3`'s letter tests pass with the strip letters drawn 20 px INTO the hexagons. They compare two numbers derived from the same assumption

The new tests are

```python
band = side["label_band_bottom_px"]
top  = min(p["y"] for p in side["patches"] if p["page"] == 0)
assert top > band
```

`label_band_bottom_px` is `render_pages`'s `_band_bottom = _lbl_top + label_band_h + rule`,
and for an upright label `label_band_h` **is** `ind_px`. The reserve the assertion is meant
to police is `leader_top + ink_bottom + LABEL_INK_CLEARANCE_MM`, where
`ink_bottom = offset + ind_px/mm2px + rule`. Both sides of the assertion are the same
quantity plus a constant, so on a turned chart `top >= band + 0.5 mm` **holds by
construction** — whatever the renderer actually puts on the paper.

### Mutation 1 — the fault the tests exist for, made real. THEY STAY GREEN

In a worktree at `e6bcabc3`, one line in `raster._draw_indicator`:

```python
    top = top + 20          # the ink lands 20 px (1.69 mm) lower
```

`_band_bottom` is computed from `_lbl_top`, which is untouched, so the recorded band does
not move; only the ink does.

```
QT_QPA_PLATFORM=offscreen pytest tests/test_the_honeycomb_can_be_turned.py \
    -k "letter or clear or reserve or turn_does_not" -p no:randomly -q
  ->  12 passed
```

The mutation is proved to land on the sheet, measured the same run:

```
band 74   topbox 80          (the numbers the tests assert on: unchanged)
A measured 37  isolated 55   <-- CUT 18 px
B measured 55  isolated 55
C measured 38  isolated 57   <-- CUT 19 px
D measured 55  isolated 55
E measured 37  isolated 55   <-- CUT 18 px
```

`M2-mutation-labels-20px-lower.png`: **A is beheaded into a "Λ", C into a "Γ", E into an
"F"** — on the raised strips, exactly the fault the owner reported — and the suite reports
12 passed.

### Mutation 2 — what the tests CAN see, for contrast

`LABEL_INK_CLEARANCE_MM = 0.5` -> `0.0`: 5 failed, 7 passed. So what these six tests
actually pin is *"the clearance constant is greater than zero and the reserve is wired
in"*. They cannot see where the ink is, which is the one thing #159 was reopened for.

Both mutations reverted; `git diff --stat` empty in the worktree and in the main tree.

**Severity: not a paper blocker on its own, but it is on the standing orders'
fix-without-asking list — "any test proved not to catch the fault it exists for" — and it
is why M1 went unnoticed.** A test that bites would read the ink: build the sheet, mask the
patch rects (widened by `hxew`), and compare each strip's surviving label ink with the same
letter rendered alone. That is ~25 lines and it fails on mutation 1.

---

## M3 — the new geom kwarg does NOT leak, and no non-turned layout moved on any instrument. **NOTHING FOUND** (13,440 configurations)

`strip_label_offset_mm` is not in `instruments.GEOM_BUILD_KEYS`, so it never reaches
`instruments.build()`; `geom_from_build_kwargs` passes the whole `kw` on to
`raster.apply_furniture_reserves`, and the only read in the tree is
`raster.py:359` inside `_furniture_reserves_mm`. `label_ink_bottom_mm` is read in exactly
one place, `geometry._top_reserve_for_a_turned_hex`, which returns `mints` unchanged unless
`hexagonal and hex_flat_top`.

Proved by measurement, not by reading. A worktree at `a70b0c6e` (the parent, which has NO
turned guard at all) and the tree at `e6bcabc3`, both asked for
`geometry.compute` + `geometry.placement` over

```
7 instruments  (i1, p3, CM, 41, 51, SS, CR30)
x 10 papers    (A4 A4R A3 Letter LetterR Legal 11x17 A2 A3+ 4x6)
x hflag on/off  x turn on/off  x patch_first/area_first
x "Use instrument margins" on/off
x 12 setting overrides (6 mm label, offset +3, offset -2, underline, indicators OFF,
  row indicators ON, rotation 90, offset_y 4 mm, align center, align bottom-left,
  patch scale 1.5, plain)
= 13,440 rows, each recording steps_in_pass, passes, strips_per_page, patches_per_page,
  pages, y0_first, x0 and leader_top
```

```
rows 13440   differing 238
  with the turn ON  : 238      all of them CR30 with hflag=True
  with the turn OFF :   0
  charts that used to build and now raise: 0
  charts that used to raise and now build: 0
```

**Not one i1, i1Pro3, ColorMunki, DTP41, DTP51 or SpectroScan layout moved**, in either
layout mode, with or without instrument margins, on any of the twelve setting overrides.
The scanner presets go through the same `geom_from_build_kwargs`; `hex_flat_top` is False
for every instrument that is not CR30 (`instruments._build_base`), so `_turned_hex` is False
and the guard is a no-op by construction as well as by measurement.

## M4 — the reserve costs a SHEET on A4 landscape: 400 patches that fitted one turned page now need two. Ships-with-it, but it is a user-visible cost the changelog does not mention

From the same 13,440-row A/B, 58 configurations change capacity and **7 change the PAGE
COUNT** for a 400-patch job:

```
CR30 A4R hflag turned patch_first "use instrument margins" :
    patches/page 416 -> 390 (-6.3 %)      pages 1 -> 2
    (and the same for 6 mm labels, offset +3, underline, rotation 90,
     align center, align bottom-left)
```

The largest per-page loss is 4x6 turned area-first, 98 -> 91 (-7.1 %). Every pointy figure
is unchanged. This is the price of not printing on the letters and I would pay it, but
"the turn costs you a second sheet at 400 patches on A4 landscape" is the kind of thing a
user notices; `e6bcabc3` quotes only "-0.30 % in total" from a `patches_per_sheet` sum,
which hides it.

---

## M5 — with the BUNDLED font the fix holds everywhere I could reach, except the letter **Q**, whose tail is clipped by 0.93 mm — **identically on the pointy control**. Ships-with-it

29 setting combinations x {A4, A4 Rotated} x {turned, pointy}, ink-measured, default
JetBrains Mono: indicators off, row indicators on, all three patch-area alignments, area-first,
"Use instrument margins" off, offset_y +-4 mm, rotations 0/90/180/270, a 3 mm underline with a
2 mm gap, a 2 mm top margin, patch scale 2.0, bold, a 5 mm strip-indicator gap, and the
6 mm-label / +3 mm-offset pairs of each. Plus every spacer mode x edge spacers on/off, three
custom paper sizes (120x180, 330x483, 89x127 mm), and every page of 3- and 5-page charts.

**Every turned case measured 0 cut except one letter: `Q`, cut 11 px = 0.93 mm.**

`Q` is the only capital in JetBrains Mono with ink below the baseline. The reserve's
`_drawn = ind_px` is a *font size*, and the tail descends past it, so on any chart with at
least 17 strips (`Q` is the 17th) the tail is sliced by the first hexagon.

```
                       total strips   Q cut
A4      turned  900 patches   40      11 px = 0.93 mm
A4      pointy  900 patches   34      11 px = 0.93 mm      <- CONTROL, identical
Letter  turned / pointy       43 / 36 11 px both
A4R     turned / pointy       60 / 50 11 px both
A3      turned / pointy       28 / 24 11 px both
```

`M5-Q-A4R-turned.png` and `M5b-Q-A4-turned-worst.png` (4x): the tail stops flat on the
hexagon's top edge, leaving a visible stub. The letter is still unmistakably a Q.

**A false reading I nearly reported, recorded so nobody quotes it.** My first pass called
this turn-specific (A4 turned 14 px vs pointy 1 px). It was my harness: I labelled each page's
strips from `lab(i+1)` **per page**, so on a multi-page chart every page restarted at "A" and
the letter I compared against was not the letter on the sheet. With a global strip index the
two orientations are identical to the pixel. Pre-existing, cosmetic, ships with it.

## M6 — `offset_y` of −4 mm prints the strip letters OFF THE TOP OF THE PAGE, and the patch block 0.24 mm above its own top margin. Pre-existing, both orientations, NOT this branch

Measured, A4, CR30 honeycomb, 345 patches:

```
offset_y  0 mm : leader_top  0.000 mm   y0 9.765 mm   letters whole (A..E all 55 px)
offset_y -4 mm : leader_top -4.000 mm   y0 5.765 mm   letters start at y=0, 29 px of 55 left
                 turned AND pointy alike (pointy: 38 px of 61)
```

`placement` adds `g.offset_y` to `_leader_top` **after** the `max(0.0, ...)` clamp that exists
to keep the band on the page, so a negative patch-area offset walks the label band off the
sheet; and `y0 = 5.765` is inside the 6 mm top margin. `LABEL_INK_CLEARANCE_MM` cancels out
of this (both label and block shift by `offset_y`), so the guard neither causes nor cures it.
The line is untouched by `e6bcabc3` and behaves identically on a pointy sheet.
`M6-offsetY-4.0-turned.png` / `M6-offsetY-4.0-pointy.png`. **Deferred, named, not a blocker.**

## M7 — the reserve's ROTATED branch is capped at TWO characters; the renderer sizes the band to the LONGEST label on the chart. A 3-character label puts 3.8 mm of band inside the patches. Equal on pointy -> ships-with-it

`raster._furniture_reserves_mm`, rotated branch:

```python
band_px = _indicator_tile("WW", f, spc, rot).height     # "Reserve for up to two letters"
...
_drawn  = _indicator_tile("WW", f, spc, rot).height     # the new ink figure: the same "WW"
```

`render_pages` instead uses `label_band_h = _indicator_tile(label_strip(_n_total_strips), ...)`
where `_n_total_strips` counts the strips of the WHOLE chart, all pages. The commit's own
comment says *"Rotated labels use the same tile height as the reserve, so they agree there"* —
they agree with each other and both disagree with the renderer.

Measured tile heights at `ind_px = 71` (JetBrains Mono, rot 90):

```
"WW"  98 px      "AA"  98 px      "100" 149 px      "AAA" 149 px      "1000" 201 px
```

`permutation.make_labeller` returns decimal counting for any pattern without `A-Z`, and the
**Strip pattern box in Expert Options is free text** (`layout_options_panel.py:4754`,
`r.strip_pattern = self.strip_pat.text()`). So a numeric pattern reaches three characters at
strip **100**; the default alphabetic pattern reaches them at strip 703.

Built, 4x6, CR30 honeycomb, rotation 90, 6 mm labels, `strip_pattern = "0-9"`:

| | steps | total strips | band bottom | first patch box | worst letter cut |
|---|---|---|---|---|---|
| turned, 2000 patches | 10 | 200 | **149 px** | **104 px** | 33 px = **2.79 mm** on `7` |
| pointy, 2000 patches (CONTROL) | 13 | 154 | 149 px | 91 px | 33 px = **2.79 mm** on `6` |

`M7-rot90-0-9-turned.png`: the rotated `2` is chopped down its side and the next label is
almost entirely gone.

The band bottom is recorded 45 px BELOW the first patch box, so this is one case the commit's
own test metric (`top > band`) *would* have caught — it just never crosses `strip_pattern`.
**Identical on the pointy control, so it is the shipped `label_band_mm` behaviour and not the
turn's**; it belongs on the same 4.2.2 line as the rotated-plus-offset pointy overlap the
commit already deferred.

(My first control here was unfair — the pointy sheet had only 99 strips and so a 2-digit
longest label. Recorded so the 33-vs-2 px reading is not quoted from this file.)

---

## M8 — **M1 CONFIRMED IN THE REAL WINDOW, on the app's own generated chart.** And the pointy control, same recipe, is WORSE. Ships-with-it

Driver: `<scratchpad>/r8/drive_round8.py`, real `MainWindow`, shown, settings sandboxed
(`CHROMIQ_SETTINGS_FILE=/tmp/chromiq-round8.ini` plus a copied store in a tempdir).
Create Chart -> Manual -> CR30 -> Hexagon -> **Straight strips ON** -> Expert Options ->
Font, Size, "Use instrument margins", "Edge spacers" -> Generate.

Four charts built on screen. The label size box is in **POINTS**, not millimetres
(`small_pt(top_pt=72.0)`, "auto" as the special value), so 6 mm is **17 pt**; my first
on-screen attempt typed 6.0 and got 2.12 mm, which is why it measured clean.

| case | recipe | letters cut on the app's own sheet |
|---|---|---|
| B, D | the owner's SAVED defaults (instrument margins OFF, edge spacers ON) | **none** |
| E | instrument margins ON, edge spacers OFF, JetBrains Mono 17 pt | Q only, 0.42 mm |
| **F** | **the same with Noteworthy 17 pt** | **A 0.68, C 0.59, E 0.59, G 0.59, I 0.51, K 0.59, M 0.59, O 0.59, Q 1.44 mm — nine of seventeen strips, every raised one** |

`M8-onscreen-r8-uim-note-top.png` (2x, from the app's own TIFF): **A's foot is sliced flat
by the green hexagon, C's tail by the cyan one, E's bottom stroke by the magenta one.**
B, D and F, on the lowered strips, are whole. That is the owner's original report, still
reproducible after the fix, with one Expert-Options dropdown changed.

**And the control settles the severity.** The same recipe with the turn OFF, 391 patches:

```
TURNED : 17 strips,  9 cut,  0.51 - 1.44 mm
POINTY : 30 strips, 29 cut,  0.34 - 1.52 mm      <- the shipped alternative, WORSE
```

So the turn is strictly better than the orientation it replaces, on the very setting that
still breaks it. **Not a blocker. Deferred to 4.2.2 with the pointy overlap `e6bcabc3`
already deferred, and named to the owner.**

Screen-grab note: `QScreen.grabWindow(0, ...)` returned a 0x0 pixmap on every call — this
machine has no Screen Recording permission, exactly as round 7 warned. Every window picture
here is `QWidget.grab()`, the widget's own render, and the ink claims are read off the
TIFF the app wrote, not off a screenshot.

## M9 — the "Chart layout information" panel AGREES on every count, and disagrees by ONE PIXEL on two rows. Pre-existing, both orientations, not a finding

On all four on-screen charts:

```
Total patches / fill-up / Patches (this page) / Patches per strip / Strips (this page) / Pages
        on screen == estimate,  exactly, every time
Patch size (mm)   13.77x12.02  |  13.86x12      (0.09 mm, ~1 px at 300 dpi)
Column pitch (mm)       10.33  |     10.39      (0.06 mm)
```

The "on screen" column converts the recorded INTEGER pixel rect
(`_chart_patch_size_mm`), the estimate uses exact millimetres from `Geom`
(`_panel_patch_size_mm(geom.pwid, geom.plen, ...)`). Measured on both orientations off
screen, the same gap is there on a POINTY chart (+0.023 / +0.029 / +0.022 mm), so it is
pixel rounding and it is not this branch's. `r8-default-03-info-panel.png` also shows
round 6/7's fix standing: the row is named **"Column pitch (mm)"** on a turned chart, in
the actual column, after a build.

## M10 — the reserve cannot starve a sheet: no configuration raises, no page is lost to it

`compute` can raise `LayoutError("paper too short")` when `pprow < 1 + nextrap`, so the
reserve could in principle refuse to lay a chart out that used to build. Pushed:

```
4x6 turned, 25.4 mm labels + 20 mm label offset : ok, 7 patches/strip, 35/page, 9 pages
A4  turned, 25.4 mm labels + 20 mm label offset : ok, 19/strip, 285/page, 2 pages
```

and across the 13,440-row A/B of M3, **0 charts that used to build now raise** and 0 the
other way. Capacity degrades smoothly. (On a POINTY sheet the same 20 mm offset costs
nothing at all — 52 patches/page before and after — because the reserve is the turn's alone.)

---

## M11 — the modal-snapshot replacement (round 7's L3) **BITES**, and its subprocess is budgeted with 3,200x of headroom. NOTHING FOUND, with one narrowness named

Three probes, in a worktree at `e6bcabc3`:

1. **Does it catch the fault it replaced?** Snapshot moved late (taken lazily inside the
   repair) + a throwaway file patching `QMessageBox.warning` at IMPORT time:
   `1 failed, 7 passed` — `test_the_snapshot_recorded_pyqt_s_own_objects` names it,
   `- methoddescriptor / + staticmethod`. Round 7's version was green under exactly this.
2. **Did dropping `len(recorded) == 5` lose coverage?** The old test pinned five entries; the
   new one only asserts the list is non-empty. Mutated the snapshot to record `QDialog.exec`
   alone: `4 failed, 3 passed` — the four parametrised
   `test_a_leaked_qmessagebox_static_is_put_back_not_deleted` cases catch it. **No loss.**
3. **The subprocess budget.** The probe is `python -c "from PyQt6.QtWidgets import ..."`,
   measured **0.056 s** idle, three runs, against a `timeout=180`. That is 3,200x, against
   `test_webengine_shutdown`'s fifty-fold that the gate still blew. Ample.

**Named, not a finding:** the comparison is by `type(...).__name__`, so a poison that installs
an object of the SAME type is invisible — `QMessageBox.warning = QMessageBox.__dict__["critical"]`
at import time gives `8 passed`. No leak shape in this suite looks like that (lambdas,
`staticmethod`, mocks all differ), and comparing `__name__` as well would close it in one clause.

## M12 — the gate, run once on a still tree

```
worktree at e6bcabc3, clean;  QT_QPA_PLATFORM=offscreen pytest --runslow -n auto
12624 passed, 180 skipped, 4 xfailed in 220.60s (0:03:40)     exit 0
```

(12624 + 180 = 12804 items, the same total as the commit's "12637 passed"; the split differs
because this host skips a different set of hardware/data-file tests.)

## M13 — the bottom margin: bottom-anchored turned charts sit 0.05 to 0.11 mm outside it, exactly as pointy ones do. Not a finding

Lowest non-white pixel vs the 6 mm bottom margin, six papers x four cases x both orientations,
read off the TIFF rather than the rects:

```
worst   A3, bottom-left align   -0.105 mm    turned AND pointy, identical
        A2 -0.095, A4 -0.084, 4x6 / Letter -0.073, A4R -0.047   (all both orientations)
top-anchored and centred charts: +0.85 to +11.2 mm inside
```

One pixel at 300 dpi is 0.085 mm. `e6bcabc3` quotes -0.020 mm for the same thing, measured off
the recorded rect rather than the ink; both readings say the same thing. The commit's own
`test_the_reserve_reaches_capacity_as_well_as_placement` allows 0.1 mm and its A3 bottom-left
case measures -0.020 mm on the rect, so it is not sitting on its tolerance.

## M14 — the `_turned_hex` gate, exhaustively

```
CR30 hflag=T flat=T -> hexagonal=T hex_flat_top=T  _turned_hex=True    <- the only True
CR30 hflag=T flat=F -> ...                          _turned_hex=False
CR30 hflag=F flat=T -> hexagonal=F hex_flat_top=F   _turned_hex=False   (the flag is dropped)
i1 / p3 / CM / 41 / 51 with hflag=T,flat=T          _turned_hex=False
SS   hflag=T flat=T -> hexagonal=True hex_flat_top=False  _turned_hex=False
```

`hex_flat_top` is written once, in `instruments._build_base`, and the SpectroScan honeycomb
never gets it. The guard cannot reach any layout but a turned CR30 comb.

---

# WHAT I DID NOT MEASURE, PLAINLY

* **Printing.** Nothing here went through `lp`, PostScript, a PDF export or a real printer.
  Every claim is about the TIFF the app writes.
* **Any measurement.** No instrument, no `chartread`, no `.ti3`. I did not re-check that a
  turned chart's `SAMPLE_LOC` matches its ink (round 6 did, 690 of 690) and I did not touch
  Check & Refine or the patch-set editor, which round 6 and round 7 both left open.
* **The Guided path.** Every on-screen chart here was built in **Manual**. Round 6 photographed
  the pitch row in Guided; I did not repeat that or build a Guided turned chart.
* **`Q` past strip 702**, and the 3-character rotated case (M7) at the DEFAULT alphabetic
  pattern: I proved it with a numeric strip pattern at 200 strips and computed the alphabetic
  threshold (703 strips) rather than rendering a 7,000-patch chart.
* **Fonts other than the twelve I crossed**, at sizes other than auto and 6 mm. The 200-family
  sweep was at auto size only.
* **Whether the four charts I built on screen would satisfy the owner.** They are ink and
  numbers; only he and Knut can confirm behaviour into a specification.
* **A second gate run.** One `--runslow`, green, exit 0.
* **Screen grabs.** `QScreen.grabWindow(0, ...)` returns 0x0 on this machine (no Screen
  Recording permission), so no picture here is of the actual screen; they are `QWidget.grab()`
  renders of the real, shown window plus the app's own output files.

---

# RELEASE VERDICT: **HOLD**

Not for the paper. **For the paper this branch is in good shape**, and I want that said
plainly, because seven rounds of red make it easy to miss:

* the owner's reported fault — strip letters printed on the patches of every raised strip of
  a turned honeycomb — is **fixed**, confirmed on the app's own generated chart in the real
  window, and over a cross of 29 settings x 2 papers x both orientations, every spacer mode,
  three custom paper sizes, and every page of multi-page charts;
* **13,440 layouts across seven instruments and two layout modes: not one non-turned layout
  moved.** i1, i1Pro3, ColorMunki, DTP41, DTP51, SpectroScan and every scanner preset are
  byte-identical to the parent commit, and 0 charts that used to build now raise;
* the gate is green on a still tree, exit 0;
* the CHANGELOG contains no untrue sentence about the turn.

**The one blocker is M2, and it is on the standing orders' own fix-without-asking list:
"any test proved not to catch the fault it exists for".**

All six of the tests `e6bcabc3` added for the strip letters pass with the letters drawn
20 px into the hexagons — measured, with the picture of a beheaded "A" beside the green run.
They assert `patch_box_top > label_band_bottom_px`, and the reserve they police is
`label_band_bottom_px + 0.5 mm` by construction. What they actually pin is that
`LABEL_INK_CLEARANCE_MM > 0`.

That is not an academic complaint. It is why **M1** (any of ~190 system fonts re-opens the
fault on a turned sheet, 1.61 mm of letter, confirmed on screen) and **M5** (`Q`'s tail, 0.93 mm,
on the default font) both sat green through the coordinator's 9,216-chart cross and through
three `--runslow` runs. A test that reads the ink fails on both of them today.

**What I would do before tagging**, in order:

1. Make `_furniture_reserves_mm` measure what it claims to: the **ink bbox of the drawn
   label**, not `ind_px`. One expression, and it closes M1 and M5 together — the same probe
   the upright reserve already does for "W8", applied to the drawn glyph set. Re-measure
   capacity: it will cost a little more on turned sheets.
2. Replace the six band-vs-box assertions with **one that reads the ink**: build the sheet,
   mask the patch rects widened by `hxew`, compare each strip's surviving label ink against
   the same letter rendered alone. ~25 lines; it fails on the mutation in M2 and on M1/M5.
3. Correct the commit message's "not one of 4,608 turned sheets prints a letter on a patch"
   wherever it is repeated. It is true for the three bundled fonts and false for Noteworthy.
4. Re-gate.

**If the owner would rather ship tonight**, the honest reading is: nothing on the default
font at default settings prints a letter on a patch, and the two residual cases (M1, M7) are
both **worse on the pointy chart that is already shipped**, so the turn never makes a sheet
worse than the alternative it offers. That is a judgement about Expert Options, and it is
his to make, not mine. My own bar — *would I sign this off* — says fix the test first,
because it is the thing that will hide the next one.

**Ships-with-it, named:** M1 (font-blind reserve; pointy worse), M4 (A4 landscape turned loses
a page at 400 patches; the changelog says "a little" and points at the panel), M5 (`Q`'s tail,
both orientations), M6 (`offset_y` negative walks the labels off the page; pre-existing, both
orientations), M7 (rotated labels past two characters; equal on pointy), M9 (the info panel's
one-pixel patch-size difference), M13 (0.1 mm of bottom-margin rounding on bottom-anchored
charts, both orientations), and M11's same-type-poison narrowness.

**Nothing found, said plainly:** M3 (no kwarg leak, no non-turned layout moved, 13,440 rows),
M10 (the reserve cannot starve a sheet), M11 (the snapshot test bites and is budgeted),
M12 (green gate), M14 (the guard cannot reach a non-CR30 layout).

## Housekeeping

* Worktrees left in place for re-running the A/B: `<scratchpad>/wt8` (e6bcabc3, clean) and
  `<scratchpad>/wt7` (a70b0c6e, clean). `git worktree remove` them when done. Both verified
  clean with `git status --short` after every mutation; the main tree carries only this file.
* Settings: `CHROMIQ_SETTINGS_FILE=/tmp/chromiq-round8.ini` was exported for every on-screen
  run and each run also replaced `AppSettings._qs` with a copy in its own tempdir.
  After the runs, `defaults read com.chromiq.ChromIQ custom_output_path` -> **does not exist**,
  which is the value it had before. The real store is untouched.
* Harness: `<scratchpad>/r8/{harness,inkmeasure,manifest,drive_round8}.py`.

---
## FIXES APPLIED for round 8 (2026-09-09)

**M2 (blocker) — the six strip-letter tests now read INK.** The reviewer is right that they
were circular: they compared the recorded patch box against `label_band_bottom_px`, and the
reserve that moves the box IS that number plus `LABEL_INK_CLEARANCE_MM`. Both sides came out
of `ind_px`, so drawing the labels 20 px lower left all six green while the sheet showed "A"
beheaded into a lambda.

They now measure the letters on the PAGE, against a control render:

* the chart is built from a PALE patch set, so black label ink is unambiguous (four probes in
  this series have read a dark patch as text);
* for the first patch of EVERY strip -- raised and lowered, because taking only the topmost
  boxes selects the raised half of a turned sheet and the alternation is the symptom -- the
  height of the topmost dark run is measured;
* the control is the same chart with a 30 mm top margin, where nothing can reach the letters.
  A letter a patch is painted over comes out SHORTER than its control, and that is the
  assertion. The two sides share no arithmetic: they are two renders.

Measured on the reviewer's own mutation (`_draw_indicator`: `top = top + 20`):

```
before   6 tests, ALL GREEN, letters visibly beheaded
after    5 of 6 FAIL, e.g. "the shortest strip letter is 39 px where the same
         chart with room to spare draws 55 px"
```

The `ink_bottom = label_band` mutation still fails 2, and the clearance and
compute/placement mutations still fail their own tests.

**M1, M5, M7, M6, M9, M13 — carried, not fixed.** Each was measured EQUAL or WORSE on a
pointy sheet, so none is the turn's doing and none may be changed under a stable tag:
* M1 the reserve assumes ink stops at the font size where Pillow draws to the ascent, so a
  non-bundled font at 17 pt cuts nine of seventeen turned strips -- and twenty-nine of thirty
  POINTY ones on the same recipe. The commit message's "not one of 4,608 turned sheets" holds
  for the bundled fonts it measured and not beyond; recorded here rather than restated there.
* M5 `Q`'s tail is clipped 0.93 mm on any chart with 17+ strips, identically both ways.
* M7 the rotated reserve is capped at two characters where the renderer sizes to the longest
  label; equal on pointy.
* M6 a negative `offset_y` walks the labels off the page. Pre-existing, both orientations.
* M9/M13 the info panel and the bottom margin differ by one pixel; identical on pointy.

**M4 — A4 landscape turned: 400 patches now need two sheets (416 -> 390 per page).** The
changelog must not call that "a little". Reworded with the release notes.

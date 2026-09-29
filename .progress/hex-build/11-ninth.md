# 11 - NINTH adversarial review (round 9), commit `d0cfc7f8`

Branch `feature/nelson-photocard-presets`. Bar: *would I sign this off to print on a
paying customer's paper, and to be tagged stable tonight.*

Proof folder: `~/Desktop/ChromIQ-hex-proof/16-ninth/`.
Worktree for every mutation: `<scratchpad>/wt9` at `d0cfc7f8`, `git checkout -- .`
between each; the main tree was never edited.

---

## N1 - the reworked strip-letter tests are NOT circular. Six mutations, six reds, and each names the millimetre. NOTHING FOUND on the primary target

Round 8's M2 proved the previous family green under a 20 px label shift. The
family in `d0cfc7f8` reads ink off the built page and compares it against a
second render. I re-ran the six tests
(`test_a_turned_honeycomb_never_prints_a_strip_letter_on_a_patch` and the five
rows of `test_the_letters_clear_the_ink_however_they_are_styled`) under six
mutations, each applied on its own to a clean worktree:

| # | what was mutated | where | result |
|---|---|---|---|
| baseline | nothing | - | **6 passed**, 4.3 s |
| D1 | `_draw_indicator`: `top = top + 20` (round 8's own) | `raster.py` | **5 failed**, "the shortest strip letter is 39 px where the same chart with room to spare draws 55 px" |
| B1 | `_lbl_top += 20` (band, underline and record together) | `raster.py:1304` | **6 failed**, min 39 vs 55 |
| L1 | `_top_reserve_for_a_turned_hex` → `return mints` (the owner's original fault, restored) | `geometry.py` | **6 failed**, min 50 vs 55; with a +3 mm label offset 15 vs 55 |
| L2 | patch block up 2 mm (`_y0 … - 2.0`) | `geometry.py` | **6 failed**, min 35 vs 55 |
| L4 | the hex apex shift dropped from `_y0` | `geometry.py` | **6 failed**, min 23 vs 55 |
| L5 | flat-top stagger 0.25 → 0.35 (raised strips climb further) | `hexagon.py:89` | **6 failed**, min 45 vs 55 |

The prompt asked specifically whether a mutation of the LAYOUT rather than the
DRAWING can leave them green: L1, L2, L4 and L5 are four separate layout
mutations (the reserve, the block origin, the apex shift, the stagger) and all
four are red. The ink leg fires first in both tests, so the red is the ink leg,
not the circular sidecar leg that is kept behind it.

**Ships-with-it: nothing.** This is the fix round 8 asked for and it lands.

**And it bites off A4 and off 300 dpi.** With L1 applied, the same two-render metric on
A4 and A3 at 300 and 600 dpi:

```
A4 dpi=300 turned  min_real= 50 min_roomy= 55  CUT DETECTED
A4 dpi=600 turned  min_real= 99 min_roomy=109  CUT DETECTED
A3 dpi=300 turned  min_real= 50 min_roomy= 55  CUT DETECTED
A3 dpi=600 turned  min_real= 99 min_roomy=109  CUT DETECTED
A4/A3 300/600 POINTY                    d=0    clear   (L1 cannot reach a pointy chart)
```

With the turn OFF the metric is not merely inert: on the shipped tree it detects the real
pointy cut of 35 px at `strip_label_offset_mm=3` (N5), so it discriminates in both
orientations.

## N2 - the ROOMY control never changes the auto label size, and the `-2 px` tolerance is dead slack. NOTHING FOUND

The prompt's three specific doubts about `_letters_are_whole`, each measured over a
sweep of 5 papers x 5 patch counts x 8 setting overrides x both orientations (400
configurations, `<scratchpad>/r9/sweep_floor.py`, run at `d0cfc7f8`):

* **"does the control ever come out with a DIFFERENT auto label size?"** No. In every
  row `effective_indicator_size_mm` is identical for the real chart and its 30 mm-margin
  control (`size=6.2764/6.2764`, `7.0/7.0`, `6.0/6.0`, …). The 30 mm margin shortens the
  strips, so the control needs MORE of them, but the strip PITCH is unchanged (turned A4
  345: strip x at 180, 303, 426, … in both), and the auto size is derived from the pitch.
  The control's letter set is therefore a superset of the real one at the same size.
* **"a different strip count that changes the letters measured, so the floor is wrong?"**
  The count does change - turned A4 345 patches: **15 strips real, 17 roomy**; pointy:
  13 vs 15. The floor does not move, because the added letters are never the shortest:
  the roomy turned A4 sheet reaches `Q`, whose descender makes it the TALLEST at 69 px
  against 55-57 for the rest, and `min()` is what the assertion uses. Across the whole
  sweep, `min(real) - min(roomy)` is **0 on every turned row**.
* **"is the 2 px tolerance hiding a real one-or-two-pixel clip?"** No row in the sweep
  lands in the tolerance band: the differences are 0, or large (-4, -11, -19, -34, -35).
  There is no configuration in the sweep where `min(real)` is 1 or 2 px under its control.
  The tolerance is unused slack, not cover.

**Ships-with-it: nothing.**

---

## N3 - what else can be dark above a strip. NOTHING FOUND on the DEFAULT recipe, but the metric is not masked and would read a helper marker as the letter

`_letter_heights` takes the topmost contiguous dark run in the recorded patch's own x
range, from the top of the page down. It does NOT mask, where round 8's own probe widened
the patch rect by `hxew` first. Two consequences, measured:

* On the default recipe, and on all sixteen setting overrides crossed in N4 below, the run
  it finds IS the letter: six independent mutations move the letter or the block and all
  six make the number fall (N1). If it were reading furniture the number would not move.
* It is however unmasked. Ruler helper markers on a turned honeycomb are drawn on the TOP
  edge (`geometry.py:871`, "the top and bottom markers … are allowed"), and nothing in the
  six tests switches them on, so no test today feeds the helper a page with a dash above a
  strip. If one ever does, the topmost dark run in that column will be the DASH, its height
  will be identical in the real and the roomy render, and the assertion will pass whatever
  the patches do to the letters. That is a trap for the next person who parametrises the
  row, not a fault in what ships.

**Ships-with-it (named as a trap for the next author of these rows).**

---
## N4 - the ruler helper markers are printed THROUGH the strip letters of a turned honeycomb, on the APP'S OWN generated chart. The rectangular control is byte-identical at master, so the collision itself is pre-existing; what is new is that only a turned chart can get top dashes on a comb

`~/Desktop/ChromIQ-hex-proof/16-ninth/APP-turn-mark-uim-top.png` is the app's own TIFF,
generated in the real window with "Use instrument margins" ticked and helper markers on:
the ruler ticks are printed across B, C, D, E, F and G. `D-pointy-markers-on.png` is the
control and has no top dashes at all, because a pointy honeycomb is refused them.

Measured by building the same chart twice, markers off and on, and taking the marker ink
as the XOR; a letter is "struck" when marker ink falls inside the letter's own ink bbox
(`<scratchpad>/r9/marker_collision.py`, `marker_collision2.py`):

```
A4  n=345 TURNED  14/15 letters struck, 26-48 px of marker ink inside the letter
A3  n=345 TURNED  10/11
A4R n=345 TURNED  21/23
A4  n=690 TURNED  16/17
A4  n=345 POINTY   0/26   (no top markers exist on a pointy honeycomb)
with a 6 mm dash   14/15, and 68-92 px inside each letter
marker ink y 24..47, letter ink y 20..74     <- they share the band
```

**I nearly reported my own harness.** My first probe built through `default_recipe`, where
the letters sit at y 20..74; the app's Manual panel at ITS defaults ("Use instrument
margins" OFF) puts them at y 91..145 and nothing collides - which is what the first
on-screen run produced, and it disagreed with my probe. Ticking **"Use instrument
margins"** reproduces it in the app: `chromiq_r8_34p6vg0e/.../r9-turn-mark-uim.tif`, dark
runs at y 20..88 (letters) and the marker comb inside them. So it is reachable, and by a
switch round 8 called "the FRESH-INSTALL recipe".

**The control that settles ownership.** A RECTANGULAR CR30 chart, helper markers on, at
`d0cfc7f8` and at master `7e500e59`:

```
HEAD    13/15 letters struck, per-strip px [26,34,38,34,34,34,38,48,0,36,46,0,47,48,38]
master  13/15 letters struck, per-strip px [26,34,38,34,34,34,38,48,0,36,46,0,47,48,38]
```

Identical to the pixel. The top ruler dashes have always been drawn through the strip
labels; nobody placed the two relative to each other. This branch does not cause it, so
under the standing orders it does not change under a stable tag - but it is newly VISIBLE
on a honeycomb, and only with the turn on.

**Ships-with-it. 4.2.2 list: place the top helper dashes clear of the strip label band.**

Related, measured and NOT a finding: a dash longer than about 5 mm reaches past the
patch-area top on a turned sheet (6 mm dash: 1.19 mm past it; 12 mm: 7.20 mm). The default
is 2 mm and stops 2.79 mm short, and the same is true of a rectangular chart.

---

## N5 - TARGET 2, the six carried findings: over 180 configurations the TURNED cut is ZERO in every one, and the pointy control is cut by up to 35 px. Round 8's judgement HOLDS

`<scratchpad>/r9/turn_vs_pointy.py`, results in `/tmp/r9_turn_vs_pointy.txt` and copied to
the proof folder. For every configuration the "cut" is `min(roomy) - min(real)` px of
strip-letter ink, the same two-render metric the tests use, measured for the turn ON and
OFF separately: 4 papers (A4, A4R, A3, Letter) x 3 patch counts (150, 345, 690) x 16
setting overrides (plain, 6 mm label, 3 mm label, +3 mm offset, +1 mm offset, underline,
rotation 90, rotation 180, patch scale 1.5 and 2.0, bold, 600 dpi, bottom alignment, top
margin 8 mm and 5 mm). 180 rows completed; the 12 spacer rows errored on my own duplicate
keyword and were not re-run.

```
TURNED cut != 0 :  0 rows out of 180
POINTY cut != 0 : 45 rows, worst 35 px (2.96 mm) at strip_label_offset_mm = 3
                  also 12 px at offset +1, 12 px at margin_top 5 mm,
                  11-19 px at rotation 90 on multi-page charts, 4 px at a 6 mm label
```

There is not one configuration in which the turn makes the letters worse than the pointy
chart it replaces. **Round 8 got M1, M5, M6, M7, M9 and M13 right and none of them is a
blocker.**

The pointy cut is not this branch's either. Same probe on master `7e500e59`, pointy,
`strip_label_offset_mm=3.0`: `min_real=25, min_roomy=61`, band bottom 118 px against a
patch top of 91 px, i.e. **2.29 mm of letter printed on the ink, on today's shipped
build**, on A4, A3 and Letter alike. At `d0cfc7f8` the same chart measures 26 vs 61.
Unchanged. **4.2.2 list: the pointy honeycomb has no ink reserve at all, and a
strip-label offset of 3 mm prints the letters on the patches.**

---
## N6 - TARGET 4, the capacity claim: round 6 and round 8 CONTRADICT each other, and round 8's number is right about the wrong comparison. The changelog sentence is TRUE as written; the sheet it costs is on A4 PORTRAIT, not landscape

Round 6's K3 measured the changelog's "can move a little, in either direction" and called
it fair. Round 8's M4 measured "A4 landscape turned 416 -> 390, 400 patches now need two
sheets" and said the changelog must not call that "a little". Both cannot be describing
the same thing, and the standing orders say to stop and report rather than pick a side, so
here is the measurement that reconciles them.

`geometry.patches_per_sheet` on the app's own `default_recipe("CR30", paper)` with
`hflag=True`, every paper in `papers.list_papers()`, three commits
(`<scratchpad>/r9/cap.py`):

```
                 a70b0c6e  (before the ink reserve)      d0cfc7f8  (HEAD)
paper        pointy  turned   delta            pointy  turned   delta
A2             1760    1824     +64              1760    1786     +26
594x420        1786    1782      -4              1786    1782      -4
329x483        1100    1102      +2              1100    1102      +2
483x329        1140    1100     -40              1140    1100     -40
A3              836     858     +22               836     858     +22
420x297         864     874     +10               864     874     +10
11x17           840     816     -24               840     816     -24
Legal           480     504     +24               480     504     +24
A4              405     391     -14               405     391     -14   <- 400 pat: 1 -> 2 sheets
A4R             396     416     +20               396     390      -6
Letter          375     378      +3               375     378      +3
LetterR         399     384     -15               399     384     -15
203x254         308     323     +15               308     323     +15
127x178         120     130     +10               120     130     +10
4x6              78      77      -1                78      77      -1
```

* **Round 8's 416 -> 390 is real**, and it is the *turned* count before and after the ink
  reserve on **A4R**, not turned against pointy. The reserve costs A4R 26 patches and A2
  38; no other paper moves.
* **But no user ever had the 416.** That layout printed the strip letters on the patches
  and was never tagged. What a user compares is turn OFF against turn ON, and on A4R that
  is 396 -> 390: a 400-patch job needs **two sheets either way**. Round 8's headline
  sentence, "400 patches that fitted one turned page now need two", is true only against a
  build nobody has.
* **The turn DOES cost a sheet, on A4 portrait**: 405 -> 391, so 400 patches goes from one
  sheet to two. That is the same before and after the reserve, so it is the turn's own
  cost and not the fix's. Round 8 did not name it.
* At HEAD, 8 papers gain and 7 lose; the largest loss is 40 patches (-3.5 % on 483x329)
  and the largest gain 26 (+1.5 % on A2, +8.3 % on 127x178). **"a little, in either
  direction" is measured true**, and the sentence hands the number straight to the panel,
  which round 8's own M9 found agrees on every count. Round 6's K3 is the side I land on.

**Ships-with-it, no changelog change required.** Round 8's fix note promised the sentence
would be "reworded with the release notes"; it was not, and on this measurement it does
not need to be. What the sentence does not say is that on A4 portrait a 400-patch job
gains a sheet. That is one clause if anyone wants it, and it is not untrue without it.

---
## N7 - **RELEASE BLOCKER.** On a TURNED honeycomb the ruler-marker panel greys the switch that PRINTS and offers the one that does NOTHING, its greyed reason is false, and unticking the live box makes the panel promise "No dashes will be printed" while the sheet prints them. The changelog sentence "which is which follows the turn" is untrue

New on this branch: `one_axis_only` does not exist on master (`git show master:ui/dialogs/layout_options_panel.py | grep -c one_axis_only` -> 0; introduced in `1f4ff390`).

### What the engine prints (measured, `<scratchpad>/r9/edge_truth.py`)

Same chart built eight times, CR30 honeycomb, A4, 345 patches, markers on; marker ink is
the XOR against the same chart with markers off:

```
turn  top_bottom sides | dashes drawn where
True  True       True  | top(1753) bottom(1920) left(362) right(384)*
True  True       False | top(1753) bottom(1920) left(362) right(384)*   <- sides made NO difference
True  False      True  | NOTHING PRINTED
True  False      False | NOTHING PRINTED
False True       True  | top(588) bottom(588) left(2736) right(2850)
False True       False | NOTHING PRINTED
False False      True  | top(588) bottom(588) left(2736) right(2850)    <- top_bottom made NO difference
False False      False | NOTHING PRINTED
* the left/right pixels are the end dashes of the top and bottom combs, identical with sides off
```

So on a **turned** honeycomb the printed comb is decided **entirely by
`helper_markers_top_bottom`** and `helper_markers_sides` is inert; on a **pointy** one it
is the exact opposite. That half is right and follows `geometry.py:871`.

### What the panel shows (driven in the real window, `<scratchpad>/r9/drive_markers_ui.py`)

```
turn=False: top_bottom checked=True enabled=False | sides checked=True enabled=True
turn=True : top_bottom checked=True enabled=False | sides checked=True enabled=True
```

**Identical.** `ui/tabs/tab_chart.py:18422` is

```python
_hex = self._chart_is_hexagonal()
panel.set_helper_markers_supported(not _hex, one_axis_only=_hex)
```

and `layout_options_panel.py:4409` is `self.helper_markers_top_bottom.setEnabled(supported and not one_axis_only)`.
Neither reads the turn. So on a turned honeycomb the panel greys the box that governs the
sheet and leaves live the box that governs nothing.

Pictures: `UI-marker-group-turnTrue.png` (Top/bottom greyed and reading as unticked, Sides
pink and live) beside `APP-turn-mark-uim-top.png`, the sheet the same session generated,
which has top dashes and no side dashes.

### Three consequences, each measured

1. **The greyed box's reason is false for this orientation.** Its tooltip reads *"Not
   available on hexagonal patches … dashes along the top and bottom edges would point at
   the seam between two columns rather than at the patches. The left and right dashes line
   up exactly and stay available."* On a turned chart the top and bottom dashes are the
   ones that land and the left and right ones are never drawn at all.
2. **The panel promises silence and the sheet prints.** Unticking "Sides (vertical)", the
   only live box, produces on screen:
   `'No dashes will be printed - tick at least one of the two edge boxes, or turn the
   markers off.'` The engine prints the full top and bottom combs anyway, because
   `helper_markers_top_bottom` is still ticked behind the greyed box (the panel's own
   "DISABLE, NEVER UNTICK" doctrine).
3. **The user cannot switch the printed dashes off** except by unticking "Print helper
   markers" altogether, because the box that controls them is greyed.

### And the changelog says the opposite of the code

> *"The comb that lines up is drawn and the other is greyed with the reason, and which is
> which follows the turn above."*

The drawing follows the turn. **The greying does not.** That sentence is untrue as
shipped, and an untrue changelog line is on the standing orders' fix-without-asking list.

**RELEASE BLOCKER.** The fix is one argument: pass the turn into
`set_helper_markers_supported` and grey the OTHER box when `hex_flat_top` is on, swapping
the two tooltips with it. Then `_helper_marker_edge_warning_text`, which already asks
`isEnabled()` as well as `isChecked()`, becomes correct on its own.

---
## N8 - **THE TENTH SELF-VALIDATING TEST**, and it is worse than blind: four tests in `tests/test_helper_markers.py` PIN the N7 fault as correct behaviour. The word `flat_top` appears **zero** times in that file's 70 tests

```
$ grep -c flat_top tests/test_helper_markers.py
0
```

The file was extended by this branch (213 lines changed) for the feature "a honeycomb can
carry the comb of dashes it is straight along". The branch also introduces a SECOND
honeycomb orientation for which the answer is the opposite one. The second orientation is
never built, never passed, never asserted on.

Four of its tests state the wrong half as fact, in their names and their assertions:

| test | what it asserts | true on a turned honeycomb? |
|---|---|---|
| `test_ticking_the_markers_on_does_not_hand_back_the_dropped_comb:509` | `not helper_markers_top_bottom.isEnabled()`, docstring "on a honeycomb, where the engine silently refuses to draw it" | **No.** That is the only comb the engine draws |
| `test_the_dropped_comb_comes_back_when_the_patches_do:533` | the "dropped comb" is top/bottom | **No** |
| `test_the_saved_choice_is_never_unticked_by_the_greying:550` | greys top/bottom | **No** |
| `test_the_panel_warns_when_the_only_comb_that_prints_is_unticked:561` | "the only comb that prints" is sides | **No.** Sides prints nothing |

And two engine tests carry the same blindness:
`test_a_honeycomb_gets_the_comb_for_the_axis_it_is_straight_along:312` and
`test_the_comb_a_honeycomb_keeps_actually_lands_on_its_patches:360` are run on `SS` and on
`CR30` with `hflag=True` and no turn.

### Proved three ways

1. **The shipped fault leaves the file green.** It is shipped; the file is green.
2. **Mutating the ENGINE so a turned honeycomb reverts to the side comb
   (`geometry.py:871`, `if geom.hex_flat_top:` -> `if False:`) leaves all 70 green.**
   The suite as a whole does catch it, in a different file
   (`test_the_honeycomb_can_be_turned.py::test_the_comb_that_survives_is_the_one_that_lands[True]`),
   so the engine has a backstop. The panel has none.
3. **Mutating the PANEL in the direction of the FIX also leaves all 70 green.** I wrote the
   correct greying (read the turn from `hex_flat_top_cb`, grey the box the engine drops):
   70 passed. So the file has no opinion about the turn in either direction.

### The three-assertion test nobody wrote (run in the worktree, then deleted)

```
test_engine_truth                                  PASSED
  turned + top_bottom -> dashes;  turned + sides -> nothing
test_the_panel_greys_the_comb_the_engine_drops     FAILED
  "the panel greys Top/bottom on a TURNED honeycomb, which is the only comb the
   engine prints"
test_the_warning_tells_the_truth_on_a_turned_sheet FAILED
  "the panel says 'No dashes will be printed' on a turned honeycomb whose
   top/bottom comb is ticked and WILL print"
```

Twenty offscreen lines, half a second, no window. `git status --short` clean afterwards.

**RELEASE BLOCKER, together with N7** - N7 is the fault; this is why nine rounds did not
see it.

---

## N9 - four narrower tests, each proved not to catch its own named fault, each with a backstop elsewhere. Ships-with-it, named

Verified by mutation, one at a time, on a clean worktree.

| test | mutation | its own file | the suite |
|---|---|---|---|
| `test_hex_scanner_support.py::test_the_cht_boxes_are_the_recorded_patch_rects:64` - docstring: the boxes "sit inside their hexagons"; asserts only `len()` and the set of `loc`s | `cht_writer.py:135`, every box `"x": 0.0` (every scanner sample collapses onto the left edge of the page) | **11 passed** | caught, by one test in another file: `test_cht_writer.py::test_cht_boxes_track_colormunki_offset_stagger` |
| `test_the_honeycomb_spacer_is_a_ring.py::test_the_scanner_dialog_passes_the_orientation:649` - asserts `"flat_top=flat_top" in inspect.getsource(_clamp_sample_area)`, i.e. the CALLEE's text | `scanin_dialog.py:4309`, pass `False` instead of `_flat` at the CALL SITE - the exact fault it names | **92 passed** | caught, by `test_the_honeycomb_can_be_turned.py::test_the_scanner_mesh_is_told_the_orientation_by_a_resolver` |
| `test_every_geometry_key_reaches_the_geometry.py` (whole file, 7 tests) - exists because "a missing key silently makes capacity ESTIMATES disagree with the actual render" | `instruments.py:563`, `GEOM_BUILD_KEYS` -> `GEOM_BUILD_KEYS[:10]` in the filter, so 18 geometry keys are dropped from every estimate | **7 passed** | not measured beyond the file |
| the same file | `instruments.py:562`, `law = False`, so "Use instrument margins" stops reaching the geometry while `"margins_are_law="` stays in the source the test greps | **7 passed** | not measured beyond the file |

The file's own named fault - a NEW `build()` argument that moves the geometry and is not in
the tuple - it does catch, because it probes every parameter. What it cannot see is the
filter that consumes the tuple.

---
## N10 - the on-screen run, and one process fact worth keeping

Five charts generated in the real window (`<scratchpad>/r9/drive_round9.py`,
`drive_markers_ui.py`), settings sandboxed twice over. Renders in the proof folder.

| case | recipe | result |
|---|---|---|
| A | turned, markers OFF, app defaults | 374 patches, 17 strips of 22, letters A..Q whole |
| B | the same with markers ON | dashes above the letters, no collision (instrument margins OFF) |
| C | pointy, markers ON | **no top dashes exist at all**, only sides |
| D | turned, markers ON, **instrument margins ON** | dashes printed THROUGH B, C, D, E, F, G (N4) |
| E | pointy, markers ON, instrument margins ON | control: no top dashes, letters clean |

The "Chart layout information" panel agreed with the built chart on total, fill-up,
patches on this page, rows, columns and pages in every case, and disagreed on patch size
(13.89x12.02 against 13.86x12) and pitch (10.41 against 10.39) - round 8's M9, sub-pixel
at 300 dpi, present on the pointy control too. Not a finding.

**`QScreen.grabWindow(0, x, y, w, h)` on this machine returns the DESKTOP WALLPAPER at the
requested size.** Round 7 lost nine shots to `screencapture`; round 8 recorded
`grabWindow` returning 0x0. It does neither here: it returns a correctly sized, entirely
wrong picture, which is the worst of the three because it looks like a success. One is
kept in the proof folder as `ZZ-grabWindow-returns-the-WALLPAPER-not-the-window.png`.
Every picture in this round that shows a window is `QWidget.grab()` of the real, shown
widget; every picture that shows ink is the app's own TIFF or a build through
`chart.build_from_recipe`.

**Settings.** `CHROMIQ_SETTINGS_FILE=/tmp/chromiq-round9.ini` for every run, plus a
per-run copied store. Before and after:
`defaults read com.chromiq.ChromIQ custom_output_path` -> the empty string (the owner's
value), and the domain still holds 414 keys.

---
# WHAT I DID NOT MEASURE, PLAINLY

* **Printing.** Nothing went through `lp`, PostScript, a PDF export or a printer. Every
  claim about paper is about the TIFF the app writes.
* **Any measurement.** No instrument, no `chartread`, no `.ti3`. I mutated the `.cht`
  writer (N9) but did not run a real scan through the result.
* **The Guided path.** Every on-screen chart here was built in Manual.
* **The spacer rows of the N5 cross** (12 of 192) errored on my own duplicate keyword and
  were not re-run. Spacer settings are covered by rounds 3-6, not by me.
* **Fonts other than the bundled default.** Round 8's M1 crossed 200 families; I did not
  repeat it. My N5 cross is on the shipped font.
* **The full suite against the four N9 mutations of `instruments.py`.** I ran each against
  its own file only; both would very likely be caught somewhere, and neither is this
  branch's doing.
* **Whether the N7 fix I wrote is the right fix.** I wrote one to prove the tests do not
  block it. It is a probe, not a proposal, and it was reverted.
* **Whether any of this would satisfy the owner.** Only Knut or Basti can confirm
  behaviour into a specification.

---

# RELEASE VERDICT: **HOLD**

**For the paper, this branch is in good shape and that deserves saying plainly.** Round 8
asked for one thing and got it: the strip-letter tests now read the ink off a built page
against a second render, and they survive six independent mutations of the drawing AND the
layout (N1). The floor those tests compare against does not move (N2). Over 180
configurations the turn never cuts a strip letter, and the pointy chart it replaces is cut
by up to 2.96 mm (N5), so every one of round 8's six carried findings is confirmed as
"not the turn's doing". The changelog's capacity sentence is measured true (N6).

**The blocker is N7, and N8 is why it survived nine rounds.**

On a turned honeycomb the engine prints the top and bottom comb of ruler dashes and
nothing at the sides - measured, eight builds, a truth table. The Create Chart panel greys
"Top/bottom (horizontal)" and leaves "Sides (vertical)" live, identically for both
orientations, because `tab_chart.py:18422` passes only `one_axis_only=_hex`. So:

* the greyed box carries a reason that is false for this chart ("The left and right dashes
  line up exactly and stay available" - on a turned sheet they are never drawn);
* unticking the only live box makes the panel state **"No dashes will be printed"** while
  the sheet prints a full comb;
* the user cannot switch off the dashes that do print;
* and the changelog says "which is which follows the turn above", which is untrue of the
  greying. **An untrue changelog line is on the standing orders' own fix-without-asking
  list.**

`tests/test_helper_markers.py` - 70 tests, extended by this branch for this feature -
contains `flat_top` zero times, and four of its tests assert the wrong half as fact. A
twenty-line offscreen test with the turn ticked fails on the shipped tree in half a second.

**What I would do before tagging**, in order:

1. Pass the orientation into `set_helper_markers_supported` and grey the box the engine
   drops, swapping the two tooltips with it. `_helper_marker_edge_warning_text` already
   asks `isEnabled()` as well as `isChecked()`, so it becomes correct for free.
2. Rewrite the four panel tests in `tests/test_helper_markers.py` to be parametrised over
   the turn, and add the engine-truth assertion they lean on.
3. Correct the changelog clause, or make it true.
4. Re-gate.

None of that touches geometry, capacity or a single pixel of ink.

**Ships-with-it, named:** N3 (the letter metric is unmasked and a helper dash would blind
it - a trap for whoever parametrises those rows next), N4 (top ruler dashes printed through
the strip letters; byte-identical on a rectangular chart at master, so pre-existing, but
newly reachable on a comb), N9 (four narrow tests with backstops elsewhere), and from
round 8 carried forward unchanged: M1, M5, M6, M7, M9, M13.

**4.2.2 list, added by this round:**
* place the top helper dashes clear of the strip label band (N4, all charts);
* the POINTY honeycomb has no ink reserve at all - a strip-label offset of 3 mm prints
  2.29 mm of letter on the patches, measured on master today (N5);
* `test_the_cht_boxes_are_the_recorded_patch_rects` should assert a coordinate (N9).

**Nothing found, said plainly:** N1, N2, N5, N6, N10.

## Housekeeping

* Worktree `<scratchpad>/wt9` at `d0cfc7f8`, verified clean after every mutation.
  `git worktree remove` it when done. The main tree carries only this file.
* Harness: `<scratchpad>/r9/` - `probe1.py`, `sweep_floor.py`, `turn_vs_pointy.py`,
  `markers_blind.py`, `marker_collision.py`, `marker_collision2.py`,
  `marker_into_patches.py`, `rect_marker.py`, `edge_truth.py`, `dpi_a3_bite.py`,
  `cap.py`, `crops.py`, `drive_round9.py`, `drive_markers_ui.py`, `mutate.sh`.
* Proof folder: `~/Desktop/ChromIQ-hex-proof/16-ninth/` with `findings.md`.

---

## N11 - the gate, run once on a still tree

`<scratchpad>/wt9` at `d0cfc7f8`, `git status --short` empty before and after:

```
QT_QPA_PLATFORM=offscreen pytest --runslow -n auto
12624 passed, 180 skipped, 4 xfailed in 221.82s (0:03:41)
```

No `[gwN] node down`, no `Fatal Python error`, no `Timeout (0:0X:XX)!` dump, no FAILED and
no ERROR line. Green, and within the 3:15-3:30 band CLAUDE.md records.

**The tree is green and the blocker is still a blocker**, which is the whole point of N8:
the suite has no assertion that can see it.

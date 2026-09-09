# Rotating the CR30's hexagons — MEASURED FACTS BEFORE ANY DESIGN
2026-09-09. Everything here is measured from shipped code and a real chart
(Basti's `~/ChromIQ/youtube`, a CR30 hexagonal A4 sheet, 390 patches).

## What the sheet does today
`workflow/layout_engine/raster.py:1069 _hexagon_points` builds a **pointy-top**
hexagon (single apex top and bottom, flat vertical left/right sides) and
staggers it horizontally by the patch's index WITHIN THE STRIP:

    dx = -w/4 if step % 2 == 0 else +w/4

Measured on the real chart (patch slot 12.02 x 10.33 mm, 300 dpi):

    along a strip  A1->A2 : dx = +6.10 mm   dy = +10.33 mm
    across strips  A1->B1 : dx = +12.02 mm  dy =   0.00 mm
    x down strip A        : 14.4, 20.5, 14.4, 20.5, 14.4, 20.5 …

So strips run DOWN the page, 26 patches each, 15 across, and reading one means
moving right, left, right, left by 6.1 mm every patch. That is exactly the
report.

## ⚠ THE STATED FIX IS A NO-OP, AND THE NUMBER IS WRONG
A regular hexagon has SIX-fold rotational symmetry: rotating it by 60° maps it
onto itself. So does the hex lattice. Measured, these hexagons are regular to
within 1 %: width 12.02 mm, apex-to-apex height ph x 4/3 = 13.77 mm, ratio
1.146 against the exact 2/sqrt(3) = 1.1547.

The transformation that turns a pointy-top tiling into a flat-top one is **30°**
(equivalently 90°). That is what moves the stagger from the along-strip axis to
the across-strip axis and produces what the report actually asks for:

    along a strip : dx = 0          (a straight line, a ruler works)
    across strips : dy = +/- half the pitch (alternate strips offset)

The OUTCOME described is right and achievable. The MEANS as stated would change
nothing. Any UI wording must say what it does, not "60°".

## What else is hexagonal, and what a changed default would touch
* `instruments.is_hexagonal(geom)` gates the whole hex path; SpectroScan and
  CR30 both reach it.
* **EIGHT of the twenty shipped CR30 built-in presets are hexagonal**
  (`hflag=True` rows in `_cr30_preset`, `docs/dev_builtin_presets.md`), each
  with a bundled `.ti1` + `recipe.json`, and `tests/test_cr30_builtin_presets.py`
  builds all twenty and checks each lands on the paper, patch count, page count
  and patch SHAPE its name promises.
* The measure overlay draws the CR30's 33 mm body and 4 mm aperture to scale on
  the patch being asked for; the patch rectangles come from the same layout.
* `workflow/scanin_target.py` builds a `.cht` from the derived geometry.
* `geometry.py` reserves `hxeh` / `hxew` overhang for the apexes; those reserve
  the wrong axis if the orientation flips.
* Capacity: the sheet is not square, so transposing the lattice changes how many
  patches fit. Must be measured, not assumed.

## Basti's rulings, 2026-09-09
1. **The eight hexagonal CR30 presets are NOT a blocker.** *"the support for the
   device is new and the user base very small so the presets should not be that
   much of an issue."* So changing what they build is acceptable; it still has
   to be DELIBERATE, stated in the changelog, and their tests updated rather
   than deleted.
2. **His expectation to test, not assume:** *"i also have the hope that with
   this change the number of patches on a sheet stays the same and only strip
   and row lengths change a bit but with the same outcome."* Measure the patch
   count both ways on real builds and report it; do not reason it.
3. **NO STRETCHING** (Basti, 2026-09-09): *"the rotation should not stretch
   them"*. That rules out FLIP-B (the coordinator's own model, 1.540:1, aperture
   clearance 3.196 mm) and leaves FLIP-A, which keeps the hexagon regular and
   byte-identical in shape, size, area and 4.000 mm clearance. It also restates
   his 2026-08-28 ruling recorded at `workflow/layout_engine/area_fit.py:106`:
   *"A HEXAGON'S PROPORTIONS ARE NOT THE USER'S TO CHOOSE."* Any option that
   would stretch is off the table and does not need costing.
4. **SCOPE CUT (Basti, 2026-09-09):** *"so maybe for now we could add this
   option in manual and from profile gamut module for now and leave it off by
   default and out of guided for now."*

   What that removes from the risk list, and it is most of it:
   * the eight hexagonal CR30 presets are UNCHANGED, so there is no
     backward-compatibility question left to answer at all;
   * nobody's patch count moves unless they tick the box themselves, so the
     A4 405 -> 391 loss stops being a silent regression and becomes a
     consequence the user chooses;
   * no Guided wiring, no default migration, no change to what any existing
     project rebuilds.

   What it does NOT remove, and the report must still answer:
   * a box that is off by default only helps somebody who finds it, so the
     report must still say whether the cheaper H3/H4 answer (the rows are
     already straight; the ruler markers are switched off by a rule that is
     measurably false) is the better thing to do FIRST;
   * if the user ticks it on A4 they lose a row. The capacity readout and the
     page-count line must follow the tick, or the box quietly costs them a
     sheet;
   * it is still saveable as a default and as part of a preset, per his
     original request, so the field still has to reach `LayoutRecipe`, the
     preset store and the per-target settings;
   * nothing here has been read by a real CR30 on paper.
5. **THE NUMBER IN THE LABEL IS 30 (Basti, 2026-09-09):** *"the let it say 30°
   if this is right"*. It is right, and it is the only rotation that does
   anything: measured on the drawn polygon about its own centroid, 60/120/180
   move zero vertices, 30 and 90 move them 13.384 mm. 30° takes a pointy-top
   hexagon to a flat-top one; the slot transposes with it so the hexagon stays
   regular (FLIP-A), which is what ruling 3 requires.

   BUT THE LABEL MUST NOT BE ONLY THE NUMBER. Every comparable control in this
   app names the outcome, not the mechanism: "Double density", "Hexagon patches
   (suits the round CR30, fits more per sheet)". A checkbox reading only
   "Rotate hexagons by 30°" tells a beginner nothing about why they would want
   it. Carry the 30 AND say what it does, e.g.
       "Straight strips (turn the honeycomb 30°)"
   with the tooltip explaining the outcome (a strip becomes a straight line a
   ruler can follow, alternate strips start half a patch over) and the
   prerequisite/cost (on A4 it fits one row fewer).
6. **VISIBILITY RULE (Basti, 2026-09-09):** *"but only visible when device is
   cr30 or spectroscan and hexagonal is active. if not then not visible"*.

   So the control is a CHILD of the hexagon option, gated on BOTH:
       instrument in {CR30, SS}  AND  the hexagon patch shape is on
   Rotating a rectangle is meaningless, so with the honeycomb off it is hidden.

   ⚠ THIS IS THE EXACT SHAPE OF THE BUG CLASS FIXED ON 2026-09-08, and the
   design must answer it BEFORE the control exists. `_dd_check` (the box that
   turns the honeycomb on for a CR30/SS) is itself hidden for other
   instruments, so the new control has TWO independent reasons to disappear.
   The settled doctrine, from `docs/design/per_target_settings.md` §4c D-2 and
   `tab_measure.py` ("DISABLE ONLY, NEVER UNTICK. The saved value belongs to
   the target"):
     * hiding it must NOT clear it. Turn the honeycomb off, turn it back on,
       and the rotation choice must still be there;
     * it must not reach the build while hidden. `hflag` already gates the
       whole hex path, so a rotation with no honeycomb must be inert by
       construction, not by the widget being empty;
     * whatever is stored for the run must survive a load, and the session must
       not overwrite it (the `_dd_memory` fault, twice).
   The report must state which of these it guarantees and how, and the tests
   must pin all three.
7. **RULER MARKERS STAY INDEPENDENT (Basti, 2026-09-09):** *"ruler marker
   remain independent"*.

   So the helper/ruler-marker controls are NOT coupled to the new rotation
   option: ticking or unticking the rotation must not enable, disable, tick,
   untick or hide a marker control, and vice versa. Two separate settings, each
   with its own answer, each stored on its own.

   And H4 stays its own item. The finding that hexagonal charts return NO
   markers at all (`geometry.py:704`, on the false premise that "a honeycomb
   has no rows to line a ruler up with") is reported SEPARATELY, not folded into
   this feature and not fixed as a side effect of it. It is governed by #152 and
   #164, which are Knut's, so it is a specification question for him.

## Basti's answers to the five open questions, 2026-09-09
1. **Give it the millimetre.** The option's own recipe carries a 5.0 mm right
   margin on A4, so the turn GAINS patches (405 -> 414) instead of losing them.
2. **CR30 only.** Not offered for the SpectroScan: a motorised flatbed has no
   ruler and no hand, so a straight strip buys it nothing. Ruling 6's "CR30 or
   SpectroScan" is superseded: the control is visible only for a CR30 with the
   honeycomb on.
3. **The markers should simply be an option the user can switch on.** His words:
   *"can't they be turned on by the user if he wants? they are optional anyway
   and benefitial here but only as an option i think."*
   CHECKED, AND HE CAN RULE ON THIS DIRECTLY: the rule is NOT in any binding
   design spec. `docs/design/` contains no helper-marker document; the behaviour
   is a code decision at `workflow/layout_engine/geometry.py:704` citing #152 and
   #164. So CLAUDE.md's "report it and get it approved" applies to Basti, and he
   has now answered. Knut should be told, not asked.
   Today the user CANNOT switch them on: `tab_chart.py:18358` calls
   `set_helper_markers_supported(not self._chart_is_hexagonal())`, which disables
   the controls for any honeycomb. The fix is to stop disabling them, defaulting
   OFF, exactly as he describes.
4. Question 4 was badly asked; restated below and still open.
5. **The changelog names no paper size.** Only that the patch count per sheet
   can change, up or down, so check the count on screen.
8. **NO MARGIN SPECIAL-CASING (Basti, 2026-09-09):** *"i just noticed that when
   this is manual and from profile gamut only we don't need to adjust the
   margins for it because the user can do it himself."*
   Correct, and it deletes a whole piece of machinery: the option's recipe does
   NOT carry a 5.0 mm right margin, and answer 1 above is superseded. Both
   modules that show the control expose the four margin boxes, so the user sets
   them. Consequence to keep honest: at the stock 6 mm right margin the turn
   costs a row on A4 and gains one at 5 mm, and the tooltip already says the
   patch count can change either way and to check the count on screen, naming no
   paper size (ruling 5). The capacity readout must follow the tick so the
   number is there to check.

---

## The CR30 honeycomb's spacer is drawn as a full-width rectangle (found 2026-09-09)

Basti, looking at the 01-markers proof sheet: *"in your proof the spacers look
weird for the hexes"*. He is right, and it is **pre-existing, not from the
marker change** — a control page built with `helper_markers=False` has the
identical 22 black rules.

**What the code does.** `raster.py:1487` draws the inter-patch spacer as
`_fill_rect(draw, [x0, yB, xR - 1, y_next - 1], _fill)` — a solid, full-width
rectangle from one slot's bottom to the next slot's top — with **no hexagon
branch**, while the patch immediately above it (`:1477`) has one.

**Measured, CR30 honeycomb:**

| | mm |
|---|---|
| hexagon height | 13.856 (slot 10.392 + two apexes of 1.732) |
| row pitch | 11.692 (slot + spacer 1.300) |
| the black bar | y = 10.392 .. 11.692, full width |
| this hexagon's bottom apex reaches | 12.124 |
| next hexagon's top apex starts at | 9.960 |

So the bar is painted straight through the interlock zone. It covers **1.300 mm
of each 1.732 mm apex — 75 % of the point** on the row above; the row below is
drawn afterwards and paints its own apexes back over the bar. The printed result
is a hexagon with its bottom point cut off flat, an asymmetric black rule with
sawteeth on one side only, and a white sliver above it. Photographed at 3x in
`~/Desktop/ChromIQ-hex-proof/01-markers/05-the-spacer-across-the-honeycomb.png`.

**It is CR30-only.** The SpectroScan honeycomb has `pspa = 0.00`, so no bar is
ever drawn and its honeycomb tessellates as printtarg `-h` intends. The CR30 is
the only instrument that asks for both hexagons and a spacer.

**What a spacer is FOR, and whether a CR30 needs one.** printtarg's spacer gives
a strip reader a contrast edge to segment a swipe on. A CR30 is read patch by
patch, one button press per patch, and emits no strip at all
(`core/measure_pace.py`, `test_the_cr30_row_states_no_reading_rate.py`). Nothing
in the read path consumes it.

**Capacity, A4 portrait, one page** (binary-searched on the real geometry):

| | patches | strips x steps |
|---|---|---|
| square patches, spacer 1.30 | 336 | 16 x 21 |
| honeycomb, spacer 1.30 (today) | 368 | 16 x 23 |
| honeycomb, spacer 0.50 | 400 | 16 x 25 (+32) |
| **honeycomb, spacer 0.00** | **416** | 16 x 26 (**+48**) |

Dropping the bar therefore COSTS NOTHING and gains 48 patches a sheet, which is
the direction Basti asked for on the 1 mm ruling ("give it the one mm so there
are more patches instead less").

**⚠ RE-CHECK THIS AFTER THE ROTATION.** Basti, same session: *"if you fix this
for this honeycomb orientation then you might have another look at the same
thing when the honeycomb is rotated"*. Rotating to flat-top moves the interlock
from the vertical axis to the horizontal one: the apexes become left/right
points and the spacer band, if any survives, sits between COLUMNS rather than
between rows. `raster.py` draws the between-patch spacer down the strip only, so
a rotated chart may need the bar in the other direction or not at all — and
whichever it is, it is a second decision, not this one carried over. Do not
close the rotation commit without repeating this measurement on the rotated
geometry and photographing it at 3x the same way.

**Status: REPORTED TO BASTI, awaiting his call.** It changes what comes out of
the printer on a chart type that is already shipped, so it is not mine to
decide. Options put to him: (a) no spacer for a CR30 honeycomb, matching the
SpectroScan; (b) keep the gap, stop painting it; (c) paint it as the
complementary zigzag band instead of a rectangle.

### CORRECTION, same day — the spacers are OFF by default, and my table was wrong

Basti: *"but they are off by default anyway right?"* Yes, and the capacity table
above is wrong because of it.

`presets.default_recipe("CR30")` sets `spacer_mode="none"`, and `chart.py:209`
turns that into `spacer_on=False`, so `spacer(1.3)` returns 0.0: no gap, no bar.
The proof page that started this called `le_chart.build_chart` DIRECTLY, whose
own default is `spacer_mode="colored"`, so it photographed a state a user only
reaches by deliberately switching spacers on.

Built through the shipped default instead:

| CR30 honeycomb, A4 | strips x steps | full-width black rules |
|---|---|---|
| default (`spacer_mode="none"`) | 9 x **26** | **0** |
| user turns spacers on | 10 x 23 | 22 |

So the "+48 patches" offered to him DOES NOT EXIST — the default already gets
the 416. Nothing is being lost today. The defect is confined to the opt-in
path, which his 2026-08-28 ruling deliberately keeps available.

### RULING (Basti, 2026-09-09): a RING around each hexagon, built AFTER the rotation

He proposed the shape himself: *"would it make sense to draw spacers only for
hexes around the whole hex?"* It is better than all three options put to him:

* a bar separates two of a hexagon's six neighbours; a ring separates all six;
* **it costs no patches**, because it comes out of the patch's own area rather
  than out of the page, so the pitch stays tessellated at 26 steps per strip
  (today's opt-in bar costs 3 steps a strip);
* the aperture has room to spare — a 0.65 mm ring leaves 10.700 mm across the
  flats against a 4.0 mm aperture, 2.7x clear; even 1.00 mm leaves 10.000 mm.

Timing: **after the rotation**, on his call, because the rotation changes which
neighbours are which and building the ring first means building it twice.

Two questions still open when it is built:
1. **What colour a ring takes.** `contrast.spacer_for_mode(mode, rgb, nxt, …)`
   picks from a PAIR of patches, and a ring has up to six neighbours. Needs a
   rule, not an extension of the pair logic.
2. **The rotated case**, per his re-check note above.

### RULING (Basti, 2026-09-09): where the rotation option sits

*"the new option will then be in the expert section - patches and spacers
section i think"*.

So: **Expert Options → Patches & spacers**, in `ui/dialogs/layout_options_panel.py`,
NOT in the Basic frame and not a group of its own. That is the same collapsed
section the ruler helper markers live in (`_expert_frame`, which ships
collapsed — a driver must call `set_collapsed(False)` before it can grab the
widget, or `QWidget.grab()` returns a null pixmap and `save()` fails silently).

It stays consistent with the earlier rulings: visible only while the instrument
is a CR30 AND hexagons are on, off by default, savable as a default and inside a
preset, Manual and from-profile-gamut only.

### RULING (Basti, 2026-09-09): on a ROTATED honeycomb it is the TOP AND BOTTOM markers

*"but will markers on top and bottom also be allowed?"* — *"those are the ones
that make sense once the honeycomb is rotated"*. Yes, and the axes invert again,
which is the mirror of the correction made in `9ec5e921`:

| | stagger applied to | centres uniform in | comb that LANDS |
|---|---|---|---|
| pointy-top (today) | x, indexed by patch down the strip | y | **sides** (left/right) |
| flat-top (rotated) | y, indexed by the strip | x | **top and bottom** |

So `helper_marker_lines_mm`'s hexagonal branch must ask `geom.hex_flat_top` and
drop the OTHER comb, not the same one. A gate that only asks `is_hexagonal`
would keep the sides on a rotated sheet, which is the identical fault the
correction commit was written for, one orientation along.

To be MEASURED on both orientations before the commit closes, in the shape the
correction used: worst distance from a patch centre to its nearest dash, both
combs, both instruments. Not reasoned.

### The turn ALSO fixes the spacer shape, for the turned orientation only

Measured 2026-09-09 on a CR30 A4 honeycomb, 210 patches, 300 dpi, spacers
switched ON (the opt-in path):

| | full-width black rules on the sheet |
|---|---|
| pointy-top | **22** |
| rotated | **0** |

Why, and it is structural rather than lucky. `raster.py` draws the inter-patch
spacer as a rectangle spanning the strip, between one patch's bottom edge and
the next patch's top edge. On a pointy-top sheet those are APEXES, so the
rectangle is painted straight through the interlock and cuts 75 % off each
point. On a rotated sheet consecutive patches in a strip meet along their FLAT
horizontal edges, and the apexes point sideways, out past the strip the
rectangle spans. So the rectangle is exactly the right shape there and touches
no apex.

**This does not close the ring item.** The pointy orientation is still the
default and still draws the 22 rules when a user switches spacers on, and that
is the orientation the ring was ruled for. What it changes is the scope: a user
who turns the honeycomb also gets correct spacers today, so the ring is needed
for the un-turned case alone. Re-read this before building it.

### ...but the diagonals open up, and that is the SAME defect, not a new one

Basti, looking at the rotated proof shot: *"the ne orientation had spacers
active and the diagonals between the hexes had tiny gaps"*. Measured at 600 dpi,
white area INSIDE the patch field (well within its own bounding box):

| | spacers off (the CR30 DEFAULT) | spacers on |
|---|---|---|
| pointy-top | **0.00 %** | 6.64 % |
| rotated | **0.00 %** | 2.35 % |

So the honeycomb tessellates perfectly in BOTH orientations as shipped, and both
open up the moment a user switches spacers on.

**One cause, two symptoms.** `raster.py` inserts the spacer along the STRIP axis
only, growing the pitch on one axis while a honeycomb interlocks in three
directions. The edges perpendicular to the strip get their clean 1.3 mm; the
diagonals are simply pulled apart, into slivers whose width nobody chose. The
turn halves the damage (6.64 % -> 2.35 %) and cannot remove it, because the
mechanism is one-axis by construction.

This is the third measured argument for the ring and the strongest: a ring is
the only spacer shape that can give a honeycomb a UNIFORM gap, because it comes
out of the patch's own area on all six sides instead of being inserted between
rows on one axis. Recorded here so the ring commit starts from the measurement
rather than from the idea.

**A modelling note, so the next person does not repeat it.** An idealised
polygon-distance model of this said the diagonals still touch at a 1.3 mm
spacer. It was wrong, and the rendered sheet is what showed it: the model
carried the stagger as plen/4 while the pitch had grown to plen+pspa, so it
described a lattice the renderer does not draw. Measure the ink.

### WHY THE SEAM NUMBERS DIFFER BETWEEN THE SPECTROSCAN AND THE CR30

Basti: *"but it is funny that for the spectroscan the numbers are different
than for the cr30"*. They are, and it is not about the devices.

**The seam is a property of where a patch pitch lands on the PIXEL GRID, not of
the instrument.** A CR30 patch is 12.0 mm and a SpectroScan patch is 7.0 mm, so
at the same resolution the two land at different fractional pixel positions and
round differently. Measured, fractional part of the pitch in pixels against seam
count:

| chart | dpi | frac(pwid px) | frac(plen px) | seams | where |
|---|---|---|---|---|---|
| SS | 150 | 0.339 | 0.800 | 80 | vertical |
| SS | 200 | 0.118 | 0.734 | 0 | - |
| SS | 300 | 0.677 | 0.601 | 0 | - |
| SS | 400 | 0.236 | 0.467 | 81 | vertical |
| SS | 600 | 0.354 | 0.201 | 54 | vertical |
| SS | 720 | 0.425 | 0.841 | 372 | mixed |
| CR30 | 300 | 0.732 | 0.744 | 365 | mixed |
| CR30 | 360 | 0.079 | 0.293 | **1222** | mixed |
| CR30 | 600 | 0.465 | 0.488 | 0 | - |
| CR30 | 720 | 0.157 | 0.585 | 0 | - |
| CR30 rot | 300 | 0.744 | 0.732 | 250 | mixed |
| CR30 rot | 400 | 0.658 | 0.976 | 0 | - |

**No single-variable rule fits**, and that was checked rather than assumed: the
CR30 at 200 dpi and at 600 dpi have almost the same `frac(pwid px)` (0.488 and
0.465) and 192 seams against 0. Two distinct staggers does not predict it
either (SS at 300 dpi has two staggers and zero seams). It is the JOINT effect
of three independent roundings — the strip's x bounds, the slot's y bounds, and
the apex offset `t6 = ph/6` on top of both.

**THE STRUCTURAL FINDING, and it is the useful one.** Classifying each seam by
its shape: they are predominantly along the **VERTICAL flat sides**, where two
hexagons of the same row meet, or mixed. Never purely diagonal.

That explains why the "one stagger for the whole page" attempt made things
worse (270 -> 714): it closed the vertical family and opened the diagonal one.
A fix that addresses one family alone will always do that. The shared vertex
lattice has to make neighbouring hexagons take the SAME rounded coordinates on
EVERY shared edge, flat and diagonal together, or it is not a fix.

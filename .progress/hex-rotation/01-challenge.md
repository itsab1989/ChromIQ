# Rotating the CR30's hexagons — ADVERSARIAL CHALLENGE
Reviewer notes, 2026-09-09. Every entry is CONFIRMED (reproduced or measured
here) or SUSPECTED (reasoned, not yet measured). Nothing below is implemented.

Scratch scripts live in the session scratchpad, not in the repo.

---
## H1 — CONFIRMED. You are right about 60°, and more strongly than you claimed.

`00-measured.md` says the hexagons are "regular to within 1 %". They are regular
to floating-point exactness, and by construction, not by luck:

`workflow/layout_engine/instruments.py:728-730` sets, for the CR30 hex branch,
`plen = pscale * sqrt(0.75) * 12.0` with `pwid = pscale * 12.0`, and
`raster.py:1069 _hexagon_points` puts the apexes at `±plen/6` past the slot. So

    flat-to-flat  w                = 12.000000 mm
    apex-to-apex  4/3 · plen       = 13.856406 mm
    ratio                          = 1.154700538
    exact 2/√3                     = 1.154700538      delta = 0.0e+00
    six side lengths               = 6.928203 mm each (max−min = 8.9e-16 mm)

Measured by rotating the drawn polygon about its own centroid, in mm, with no
pixel rounding:

| rotation | identical vertex set | max vertex movement |
|---|---|---|
| 60° | **True** | 0.000000 mm |
| 120° | True | 0.000000 mm |
| 180° | True | 0.000000 mm |
| 30° | False | 13.384261 mm |
| 90° | False | 13.384261 mm |

So "rotate the hexagons by 60°" is not merely a lattice symmetry: it does not
move a single printed pixel. It is a **literal no-op**, not an approximate one.
The 1 % in `00-measured.md` was 300 dpi pixel snapping, not the geometry.

The same branch exists for the SpectroScan at `instruments.py:685-691`
(`plen = pscale * sqrt(0.75) * 7.0`), so this holds for SS charts too.

## H2 — CONFIRMED. The lattice is a textbook triangular lattice, and the strip
runs along the ONE direction that is not a lattice line.

CR30 hex, spacers off (the CR30 default — `presets.default_recipe` sets
`spacer_mode="none"`), slot 12.000 × 10.392 mm. Centres, measured from
`_hexagon_points`:

    strip 0 patch 0  (3.0000,  5.1962)
    strip 0 patch 1  (9.0000, 15.5885)
    strip 0 patch 2  (3.0000, 25.9808)
    strip 0 patch 3  (9.0000, 36.3731)

    along a strip   dx = +6.0000  dy = +10.3923   |d| = 12.0000
    across strips   dx = +12.0000 dy =  +0.0000   |d| = 12.0000

Every one of the six nearest neighbours is at exactly 12.0000 mm, at bearings
0°, ±60°, ±120°, 180°. The three straight lines of centres therefore run at
**0°, +60°, −60°**. The strip runs at **90°**, which is the one direction in the
plane that a hex lattice has no straight line along. That is the whole bug, and
it is a choice of axis, not a property of hexagons.

## H3 — CONFIRMED, AND IT CHANGES THE ANSWER. Today's honeycomb ALREADY has
perfectly straight lines. They run across the page, not down it.

From H2: `across strips dy = +0.0000`. A horizontal ROW of this chart is dead
straight, at a 12.0000 mm pitch, with no stagger whatsoever — because
`raster.py:1477` staggers by `j`, the patch's index **within its strip**, and
every strip starts at `j = 0`. So all strips carry the identical
`−w/4, +w/4, −w/4 …` phase and a row is collinear by construction.

The sheet already prints row numbers down the left in a 7.5 mm band
(`ROW_LABEL_BAND_MM`, `instruments.py:50`, switched on for SS and CR30), giving
each patch an A1/B2 coordinate. A user who lays the ruler HORIZONTALLY and works
along row 1, row 2, row 3 gets exactly what the request asks for **on charts
already printed**: a straight line, and every second row starting 6 mm over.

What is wrong is not the sheet. It is that ChromIQ's reading order, its Measure
overlay and its `.ti2` strip structure all walk the column, which is the zigzag.
See H12 for what that means for the recommendation.

## H4 — CONFIRMED. The shipped rule "a honeycomb has no rows to line a ruler up
with" is false, and it is why the CR30's ruler markers are switched off.

`workflow/layout_engine/geometry.py:704-706`:

```python
from .instruments import is_hexagonal as _is_hex
if _is_hex(geom):
    return []
```

and the docstring at `:693-695`: *"Hexagonal charts return no markers at all —
SpectroScan or CR30 (#159): a honeycomb has no rows to line a ruler up with.
This is #152's rule, and it follows the SHAPE, not the instrument."*
The UI greys the controls to match — `ui/tabs/tab_chart.py:18358`
`panel.set_helper_markers_supported(not self._chart_is_hexagonal())`, and
`_helper_marker_lines_frac` bails at `:18427`.

H3 measures that premise false: a honeycomb has straight lines along three of
its axes and a zigzag along the fourth. **Exactly one** of the page's two axes is
straight, whichever orientation the hexagons take. So the correct rule is not
"no markers on a honeycomb" but "markers on the straight axis only" — today that
is the top/bottom edge comb (`helper_markers_top_bottom`), and the side comb is
the one that has nothing to line up with.

This is a pre-existing defect independent of the request, and it is the cheapest
real improvement available to a CR30 user. It is also governed by #152/#164,
which are Knut's, so it is a spec question and not ours to just fix.

## H5 — THE THREE CANDIDATE LATTICES. Naming them, because "rotate" is ambiguous
and the two readings do very different things.

Both readings produce the straight-strip / offset-alternate-strips outcome the
owner asked for. They are NOT the same change.

| | slot (across × along) | drawn hexagon | apex overhang | stagger overhang |
|---|---|---|---|---|
| **TODAY** pointy-top | 12.000 × 10.392 | regular, 12.00 w × 13.86 tall | `hxeh` = plen/6 = 1.732 (along) | `hxew` = pwid/4 = 3.000 (across) |
| **FLIP-A** rotate the hexagon, transpose the slot | 10.392 × 12.000 | **regular**, 13.86 w × 12.00 tall | `hxew` = pwid/6 = 1.732 (across) | `hxeh` = plen/4 = 3.000 (along) |
| **FLIP-B** keep the slot, swap the overhang axis *(the coordinator's model)* | 12.000 × 10.392 | **stretched**, 16.00 w × 10.39 tall | `hxew` = pwid/6 = 2.000 (across) | `hxeh` = plen/4 = 2.598 (along) |

FLIP-B tiles perfectly — the interlock is affine-invariant, so any slot aspect
tessellates — but the hexagon is no longer regular: 1.540 : 1 instead of
1.1547 : 1.

## H6 — CONFIRMED, AND IT IS THE FINDING THAT SHOULD DECIDE THIS. FLIP-B COSTS
THE CR30 ITS PLACEMENT TOLERANCE, WHICH IS THE ONE NUMBER ITS WHOLE GEOMETRY
WAS DERIVED FROM.

Inradius (largest circle that fits inside the patch), measured on the drawn
polygons:

| patch | inradius | clearance round the 4 mm aperture | area |
|---|---|---|---|
| 12 mm square (`hflag=False`) | 6.000 mm | 4.000 mm | 144.0 mm² |
| TODAY, regular pointy-top | **6.000 mm** | **4.000 mm** | 124.7 mm² |
| FLIP-A, regular flat-top | **6.000 mm** | **4.000 mm** | 124.7 mm² |
| FLIP-B, stretched flat-top | **5.196 mm** | **3.196 mm** | 124.7 mm² |

`instruments.py:640-666` derives the CR30's 12 mm cell from exactly this number
and from nothing else: *"12 mm leaves 4.00 mm of clearance all round the 4 mm
window, against 3.00 mm at 10 mm … It also sits ABOVE the only geometry a CR30
has been proven to read"*. FLIP-B lands at 3.196 mm, which is within 0.2 mm of
the 10 mm cell that comment explicitly rejects as too tight, on an instrument
whose body is a 33 mm opaque disc that hides the patch the moment it is set
down. FLIP-B therefore buys a straight ruler line by spending the aiming margin
the straight ruler line exists to help with.

FLIP-B also contradicts a shipped ruling. `area_fit.py:106-121`:
*"A HEXAGON'S PROPORTIONS ARE NOT THE USER'S TO CHOOSE … Ignoring it drew
STRETCHED hexagons — measured +17 % on a SpectroScan and +20 % on a CR30 …
Fixed rather than papered over on Basti's ruling (2026-08-28)."* FLIP-B is that
same stretch, deliberately, at 1.540 : 1.

FLIP-A keeps the patch **byte-identical in shape, size, area and clearance**.
Only its packing onto the sheet changes. That is the version I recommend.

## H7 — THE CAPACITY ANSWER. The owner's hope is MOSTLY met, and the one place
it is not is A4, which is where ten of the twenty presets live.

Patch-first, `presets.default_recipe("CR30", <paper>, mode="hex")`, one full
page. "down × across" is patches per strip × strips per page.

| paper | TODAY | FLIP-A | FLIP-B |
|---|---|---|---|
| **A4 portrait** | **405** = 27 × 15 | 391 = 23 × 17 (**−3.5 %**) | **390 = 26 × 15 (−3.7 %)** |
| **Letter portrait** | **375** = 25 × 15 | 378 = 21 × 18 (+0.8 %) | **375 = 25 × 15 (0.0 %)** |
| A4 landscape | 396 = 18 × 22 | 416 = 16 × 26 (+5.1 %) | 396 = 18 × 22 (0.0 %) |
| Letter landscape | 399 = 19 × 21 | 384 = 16 × 24 (−3.8 %) | 399 = 19 × 21 (0.0 %) |
| A3 portrait | 836 = 38 × 22 | 858 = 33 × 26 (+2.6 %) | 836 = 38 × 22 (0.0 %) |
| Legal | 480 = 32 × 15 | 504 = 28 × 18 (+5.0 %) | 480 = 32 × 15 (0.0 %) |
| Tabloid 11×17 | 840 = 40 × 21 | 816 = 34 × 24 (−2.9 %) | **819 = 39 × 21 (−2.5 %)** |

Ink-block extents (mm), A4 portrait: today 186.00 w × 284.06 h; FLIP-A
180.13 × 282.00; FLIP-B 184.00 × 275.40. So the "block gets a bit wider and a
bit shorter" prediction is right in shape for FLIP-B, wrong in sign for width
(it gets 2 mm *narrower*, because the apex reserve 2·pwid/6 = 4.0 mm is smaller
than the stagger reserve 2·pwid/4 = 6.0 mm it replaces — the width is *given
back*, not consumed).

**CONFIRMED, and it disappoints the hope on A4.** The coordinator's mechanism is
right: the slot grid is untouched and only the reserve moves. But the reserve
does not move for free. Along the strip it grows from `plen/6` to `plen/4`, i.e.
`+2 × 0.866 = +1.732 mm`, and on A4 at the default 6 mm bottom margin the
current layout has only **0.944 mm** of slack left over after 27 rows:

    A4 today  hxeh=1.7321  usable strip length 281.536 mm  pitch 10.392  27 rows  leftover 0.944 mm
    A4 flipB  hxeh=2.5981  usable strip length 279.804 mm  pitch 10.392  26 rows  leftover 9.604 mm

So A4 loses a whole row: 405 → 390 patches, exactly 15 gone. The same thing
happens on Tabloid (40 rows → 39). Every other paper measured is unchanged.

It is a knife-edge, not a structural loss — sweeping the bottom margin:

| margin_b | today | FLIP-B |
|---|---|---|
| 0–4 mm | 27 × 15 = 405 | 27 × 15 = 405 |
| **6 mm (the default)** | **27 × 15 = 405** | **26 × 15 = 390 ← row lost** |
| 8–13 mm | 26 × 15 = 390 | 26 × 15 = 390 |

Note the coordinator's own worked example — *"the same 15 strips × 26 patches =
390 on A4"* — is already the **post-loss** number. Today's A4 default is 27 × 15.
The 26 × 15 = 390 in `00-measured.md` is Basti's own `youtube` chart, whose
margins are larger than the default, and at those margins FLIP-B genuinely costs
nothing.

**Page count.** On A4 the capacity boundary moves from 405 to 390/391, so any
chart with 391–405 patches goes from one page to two, and 781–810 from two to
three. Letter is unaffected at every count tested. This is a real, user-visible
regression for a small band of patch counts, and the "Guided" auto-fill sizes
charts *to* capacity, so that band is not hypothetical.

---
*Rulings received mid-review: FLIP-B is out ("the rotation should not stretch
them"); scope cut to an opt-in box in Manual + the from-profile-gamut module,
OFF by default, not in Guided, no default change, presets untouched. H5–H7 are
kept because they are the measured record of why FLIP-B is out. Everything from
H8 down is written to the reduced scope.*

## H8 — CONFIRMED. FLIP-A's A4 loss is NOT recovered by the bottom margin, and
IS recovered by ONE MILLIMETRE of the right one.

`presets.default_recipe("CR30", "A4", mode="hex")`, patch-first, sweeping one
margin at a time:

| swept | today | FLIP-A |
|---|---|---|
| bottom margin 0 → 6 mm | 405 (27 × 15) at every value | **391 (23 × 17) at every value** |
| top margin 0 → 6 mm | 405 at every value | **391 at every value** |
| **right margin 0.0 → 5.0 mm** | 405 (27 × 15) | **414 (23 × 18)** |
| **right margin 5.5 mm and up** | 405 (27 × 15) | **391 (23 × 17)** |

So the A4 loss is **structural on the strip axis and a knife-edge on the width**,
the opposite way round from FLIP-B:

* along the strip, 24 rows would need `24 × 12.0 + 2 × 3.0 = 294.0 mm` against
  281.5 mm available. Not close. No margin recovers it.
* across the page, 18 columns need `18 × 10.392 + 2 × 1.732 = 190.52 mm` against
  `210 − 14.4 − 6.0 = 189.6 mm`. **Short by 0.92 mm.** Drop the default right
  margin from 6.0 to 5.0 and A4 goes from 405 to **414, a 2.2 % gain**, not a
  3.5 % loss.

This changes the recommendation materially: FLIP-A is not a capacity regression
on A4, it is a capacity regression *at the current default right margin*. He
should be told he can have the straight strips **and** more patches on A4 for one
millimetre. Whether the default margin may move is his call, not ours — but the
option's own default recipe could carry the smaller right margin without
touching anybody else's.

Letter needs no such help: 375 → 378 (+0.8 %) at the default, and 396 (+5.6 %)
if the top or bottom margin is 3 mm or less.

## H9 — THE CHEAPER OPTIONS, PRICED ON THE SAME TERMS. Read this before deciding
to build anything.

Three ways to get a straight line of patches for a CR30 user. Priced identically.

### Option 1 — FLIP-A: the new checkbox (what was asked for)
* **Sheet:** rebuilt. Flat-top hexagons, strips straight down the page, alternate
  strips offset by half a pitch. Exactly the requested outcome.
* **Already-printed charts:** no help at all. A box that is off by default helps
  only somebody who finds it, ticks it, and prints a new sheet.
* **Patches per A4:** 405 → 391, or 414 with 1 mm off the right margin (H8).
* **Blast radius:** everything in H12. Eleven code sites, four of them
  re-implementations of the hexagon that would silently keep drawing pointy-top.
* **Cost:** the largest of the three.

### Option 2 — H4: let the ruler markers back onto the straight axis
* **Sheet:** rebuilt, but the change is a comb of dashes along two page edges,
  not a new lattice. `geometry.py:704-706` returns `[]` for every honeycomb; the
  correct rule is *"the comb the honeycomb has no straight line for is the side
  one; the top/bottom comb is exact"* — H3 measures the top/bottom comb's line
  (a row) as dead straight at a 12.0000 mm pitch with `dy = 0.0000`.
* **Already-printed charts:** no help either. The dashes are printed ink
  (`raster` draws them into the page), so an old sheet has none.
* **Patches per sheet:** **unchanged. Zero cost.**
* **Blast radius:** one `if`, the UI gating at `tab_chart.py:18358` and
  `:18427`, the `helper_markers_sides` control, and a spec conversation with
  Knut because #152's rule is his.
* **Cost:** by far the smallest, and it is a straight bug fix rather than a
  feature.

### Option 3 — read along the rows instead of down the columns
* **Sheet:** UNCHANGED. Same ink, same lattice, same capacity, same everything.
  Only the order in which ChromIQ asks for patches changes.
* **Already-printed charts:** this is the only option that could ever help one —
  and I have to report that **it does not, as the code stands.** The reading
  order is the `.ti2`'s patch order, which the CR30 helper walks and reports back
  as `loc` (`workflow/cr30/measure_bridge.py:4, :23`). `SAMPLE_LOC` itself is
  derived from the slot index and the strip length
  (`permutation.location_label(gslot, steps, …)`, called from
  `geometry.patch_rects_px:521`), so writing the `.ti2` row-major renames every
  patch: A1..A15 across the top instead of A1..A27 down the left. Strip identity
  is baked into `STEPS_IN_PASS`, the `.cht`, the Measure strip highlight and the
  fork's "next strip" prompts. It is a transposition of the whole strip axis, not
  a loop reversal.
* **Patches per sheet:** **unchanged — the ink is identical, so 405 stays 405
  on A4.** This is the only option with no patch cost at all.
* **Blast radius:** the `.ti2` writer, the labeller, the `.cht`, the overlay, the
  fork's strip prompts. Comparable to Option 1 and touching the measurement
  path rather than the layout path, which is worse.

**AND THE ZERO-COST ONE NOBODY HAS PROPOSED.** On a sheet already printed, today,
with no software change whatsoever: the rows are straight (H3) and the sheet
already prints row numbers 1…N down the left in a 7.5 mm band
(`ROW_LABEL_BAND_MM`, `instruments.py:50`, on for SS and CR30). A user who lays
the ruler **horizontally against row number N** gets a straight line of 15
patches at a 12.0 mm pitch, with every second row starting 6 mm over. That is
the requested outcome, on paper he already owns, for the price of a sentence in
the help text.

**My recommendation, in order:** say that sentence first (it is free and it works
retroactively); fix H4 next (it is a genuine defect, costs no patches and helps
every honeycomb, SpectroScan included); build FLIP-A third, as the opt-in box he
asked for, with the right-margin note from H8 attached to it.

I would not build FLIP-A *instead* of the other two. It is the most expensive of
the three and the only one whose benefit is gated behind a checkbox that is off.

## H10 — CONFIRMED. THE TICK CANNOT QUIETLY COST A SHEET, PROVIDED ONE TUPLE IS
EDITED. Miss that tuple and every readout goes stale at once.

Every capacity number in the app is derived through one chokepoint:
`instruments.geom_from_build_kwargs` (`instruments.py:407-459`), which builds the
geometry with `**{k: v for k, v in kw.items() if k in GEOM_BUILD_KEYS}`
(`:456`). `GEOM_BUILD_KEYS` (`instruments.py:398-405`) already documents the
failure mode in its own comment: *"a missing key silently makes capacity
ESTIMATES disagree with the actual render (clip_border_width once did exactly
that — #93). This is the single source of truth shared by every capacity
calculation."*

Every one of these calls it, so all of them follow the new field automatically
**if and only if** it is added to that tuple and to `build()`'s signature:

| readout | file:line |
|---|---|
| Manual "Calculated Patches" group | `ui/tabs/tab_chart.py:4140`, fed by `_recipe_capacity` `:16278-16296` |
| the engine capacity used by Auto patch count / pages | `ui/tabs/tab_chart.py:12442`, `_engine_capacity` `:12444`, `:16301-16353` |
| the layout estimate + page-count line | `ui/tabs/tab_chart.py:17766-17798` |
| the live preview's geometry | `ui/tabs/tab_chart.py:18503` |
| "room for N more patches" / last-page capacity | `ui/tabs/tab_chart.py:18732-18751`, used at `:19206`, `:19225` |
| the Manual layout panel's own info line | `ui/dialogs/layout_options_panel.py:3363`, `:4123`, `:2961` |
| Chart layout information panel | `ui/tabs/tab_chart.py:18079`, `:18747`, `:18796` |
| **the from-profile-gamut module's capacity hint and "fill to N pages"** | `ui/dialogs/ti2_relayout_dialog.py:3067` (`_engine_cap` `:3039-3075`), `:7016` |
| Preferences → Chart Layout preview | `ui/dialogs/settings_dialog.py:5702` |
| the Measure tab's geometry | `ui/tabs/tab_measure.py:521` |
| margin inspector | via `LayoutRecipe.build_kwargs` in `workflow/margin_inspector.py:264` |

**One extra site does NOT go through that tuple and must be changed by hand.**
`area_fit.derive_area_patch_size` hard-codes the honeycomb's aspect:

```python
if kw.get("hflag") and instruments.hex_capable(str(kw.get("instrument") or "")):
    ratio = math.sqrt(3) / 2.0          # area_fit.py:120-121
```

`ratio` is height : width. Flat-top needs `2/sqrt(3)`, the reciprocal. The
from-profile-gamut module and every area-first recipe take this path
(`geom_from_build_kwargs:434-438`), so leaving it would size a flipped honeycomb
to the pointy-top aspect and draw a 1.54 : 1 stretched hexagon — the exact shape
ruling 3 forbids. It is also the one place where the mistake would be silent:
it tiles, so nothing errors.

Answer to the question as asked: **no readout goes stale by accident, but only
because the codebase already paid for that guarantee once.** The plan must edit
`GEOM_BUILD_KEYS`, `build()` and `area_fit.derive_area_patch_size`, and the test
suite must pin all three.

## H11 — CONFIRMED BY CALCULATION. The scanner sample cap is orientation-blind,
and it is safe for FLIP-A only by luck.

`workflow/scanin_runner.py:138-166` computes the largest Sample-area fraction a
hexagonal chart can be read at, from a formula derived for a **pointy-top**
hexagon: *"the ink is a pointy-top hexagon whose corners sit at (0, ±2h/3) and
(±w/2, ±h/3)"*, giving `m ≥ w·h / (2·(2h + 3w))`. Its own docstring says the
limit *"is not a rate but a switch … 0 of 150 patches at 60 %, 150 of 150 at
70 %"*.

Measured by calling the shipped function:

| lattice | slot w × h | shipped cap | correct cap | verdict |
|---|---|---|---|---|
| TODAY pointy | 12.000 × 10.392 | 0.6443 | 0.6443 | correct |
| **FLIP-A flat** | 10.392 × 12.000 | **0.6351** | 0.6443 | conservative — safe, wastes 0.9 % of sample area |
| FLIP-B flat *(now out of scope)* | 12.000 × 10.392 | 0.6443 | 0.6351 | would have escaped on every patch |

For a regular hexagon FLIP-A always presents `w < h`, and the pointy formula is
conservative in that direction, so the scanner path is **safe by accident, not by
design**. It should still be made orientation-aware (`w` and `h` swap roles), and
if it is not, the reason must be written down where somebody will find it.

## H12 — EVERY INTEGRATION POINT, CHECKED ONE BY ONE.

`instruments.is_hexagonal(geom)` is documented as **the** single test
(`instruments.py:206-215`) and is honoured. The new orientation must ride the
same way: one field, read **only** inside a branch already guarded by
`hexagonal` / `hflag`. Below, "breaks" means "keeps drawing or measuring
pointy-top while the sheet is flat-top".

| # | site | file:line | what happens if untouched | verdict |
|---|---|---|---|---|
| 1 | the hexagon itself | `raster.py:1069-1088 _hexagon_points` | draws pointy-top on a flat-top slot: hexagons 12.00 wide on a 10.39 pitch, ink overlapping neighbours | **must change** — needs a flat-top branch |
| 2 | apex / stagger reserve, SS | `instruments.py:588-591` | `hxeh = plen/6`, `hxew = 0.25·pwid` are the pointy-top values; flat-top needs `hxew = pwid/6`, `hxeh = 0.25·plen` | **must change** |
| 3 | apex / stagger reserve, CR30 | `instruments.py:728-731` | same | **must change** |
| 4 | resized-hexagon reserve | `instruments.py:357-361` (`if geom.hexagonal and (patch_w or patch_h)`) | a Manual patch-size box or any area-first recipe re-derives the pointy-top reserve, **under-reserving `0.25·plen − plen/6 = 0.79 mm` on the strip axis**, so the apex prints past the margin | **must change** |
| 5 | capacity | `geometry.py:83, 90` (`arowl … − 2·hxeh`) and `:155` (`avail_w … − 2·hxew`) | correct **automatically**, because they consume `hxeh`/`hxew` rather than re-deriving them | **no change**, provided 2–4 are done |
| 6 | placement | `geometry.py:278` `_hex_shift = g.hxeh if g.row_stagger_mm <= 0 else 0.0`, and `:324` `x0 = … + g.hxew` | the vertical half-pitch offset of alternate strips is exactly the existing ColorMunki `row_stagger_mm` mechanism, which this line already special-cases | **reusable as is** if the flip is expressed as `row_stagger_mm = plen/2` |
| 7 | recorded patch rects | `geometry.py:546-549` (`_dx = ±(w/4)` by `j`) and `:519-520` (`_stag` by strip parity) | `:546-549` would keep applying a horizontal zigzag that no longer exists → every recorded box a quarter-patch off the ink, which is the exact 2026-08-13 fault the comment at `:536-545` documents | **must change** — and the `_stag` line at `:519-520` already does the new job |
| 8 | `.cht` for scanin | `cht_writer.boxes_from_patch_rects:123-137`, `scanin_target.py:231` | derived purely from #7 | **no change** |
| 9 | scanner sample-area cap | `scanin_runner.hex_max_sample_fraction:138-166` | conservative rather than unsafe for FLIP-A (H11), but derived for the wrong orientation | **should change**; if not, say why in the docstring |
| 10 | vector PDF | `vector_pdf.py:185-193` | consumes `("hex", pts, values)` generically | **no change** |
| 11 | Measure overlay hexagon | `ui/tiff_preview.py:1747-1771 _patch_hexagon` | draws pointy-top outlines over flat-top ink | **must change** |
| 12 | Measure click / hit test | `ui/tiff_preview.py:1491-1512 _in_hexagon` and `:1478-1487` | a click on a drawn apex selects the neighbour — the fault its own docstring records (7.2–7.7 % of click area) | **must change** |
| 13 | strip zigzag outline | `ui/tiff_preview.py:1696-1745`, `set_hex_zigzag` `:1645`, `tab_measure.py:4728-4729` | traces a zigzag the sheet no longer has; the flipped strip outline is a plain rectangle grown by the stagger | **must change** |
| 14 | scanner grid mesh | `ui/scan_grid_marquee.py:793-806` | fourth independent copy of the pointy-top vertices | **must change** |
| 15 | margin inspector | `workflow/margin_inspector.py:283-287` (`y0 −= h_px/6`, `y1 += h_px/6`) | reports the apex overhang on the wrong axis: understates left/right margins by `pwid/6` and overstates top/bottom | **must change** |
| 16 | area-first hexagon aspect | `area_fit.py:118-121` `ratio = sqrt(3)/2` | sizes a flipped honeycomb to the pointy-top aspect and silently draws a 1.54 : 1 stretched hexagon — ruling 3's exact forbidden case, and it tiles so nothing errors | **must change** |
| 17 | the "two heights" note | `workflow/hex_support.py:83-131` `HEX_HEIGHT_FACTOR` + `hex_two_heights_note()` | a shipped, translated string that says the hexagon "is a third **taller**" than its slot. Flat-top is a third **wider**. Wrong in 12 languages | **must change** — see H14 |
| 18 | Chart layout information | `ui/chart_layout_info_panel.py:144, 185, 254-258` | shows tip-to-tip height via `HEX_HEIGHT_FACTOR`; would report the wrong dimension | **must change** |
| 19 | legacy sidecar compensation | `ui/tabs/tab_measure.py:528-578 _apply_hex_stagger` | fingerprints a legacy sidecar as "a column of ≥2 patches sharing one x". **A flat-top chart has exactly that fingerprint by design**, so every new flipped chart would be mistaken for a 2026-06-28-vintage sidecar and shifted by ±w/4 | **must change — this one is a silent half-patch mis-registration on every flipped chart, and it is the single nastiest item on this list** |
| 20 | ruler helper markers | `geometry.py:704-706`, `tab_chart.py:18358, 18427` | returns no markers for any honeycomb, both orientations | **independent of this feature — see H16** |
| 21 | `layout_from_render` | `workflow/layout_from_render.py` | assumes axis-aligned rectangles; only used for prebuilt/printtarg charts, never an engine honeycomb | **no change** |
| 22 | live preview | `tab_chart.py:18503` → `geom_from_build_kwargs` | follows automatically | **no change** |

**Nineteen sites, of which four are independent re-implementations of the same
six vertices** (#1 raster, #11/#12 preview, #14 marquee) and a fifth reads them
back out of the recorded rects (#15). That duplication is the real risk here, not
the arithmetic: `instruments.is_hexagonal`'s own docstring says three consumers
disagreeing *"is not a visible bug, it is a half-patch mis-registration"*, and
adding an orientation gives each of the four copies a fresh chance to disagree.
**Before the orientation is added, those four should be made to call one
function.** That is the single most valuable thing in the whole plan.

Item **#19** deserves a line of its own. `_apply_hex_stagger` decides a sidecar is
legacy when *"a column of TWO OR MORE patches that all share one x"* exists. In a
flat-top chart every column shares one x, on purpose. So a brand-new flipped
chart would be detected as legacy and shifted a quarter patch, on every patch of
every page, and the symptom would be exactly the one Sebastian reported in
August: *"the highlight sat between two hexagons"*.

## H13 — THE VISIBILITY HAZARD (ruling 6), and the four guarantees.

The new control has two reasons to disappear: the instrument is not a CR30 or a
SpectroScan, and the honeycomb is off. Its parent (the honeycomb switch) is
itself hidden for other instruments. That is the shape of the four faults fixed
in `ff3d1b2b`, `ca0f639c`, `e1aeaf2f` and `d1adbe31`.

**The one structural difference that decides the design.** The density
checkbox is *one widget with three meanings* — "Double density" on a ColorMunki,
"Hexagon patches" on an SS/CR30, "rig" elsewhere — which is why its tick has to
be **cleared** on an instrument change and remembered separately
(`tests/test_the_density_tick_belongs_to_one_instrument.py:272-280`,
"the deliberate exception"). **The rotation box has ONE meaning on both
instruments that can show it.** A CR30 honeycomb and a SpectroScan honeycomb are
built by the same `hflag` branch shape and turn 30° in the same direction. So it
is not the exception; it is the ordinary case that test file already pins as
`test_a_control_the_other_instrument_hides_keeps_its_value` (`:259`).

### 1. Hiding must not clear it — HIDDEN, NEVER UNTICKED. No per-instrument memory.
Follow `cm_stagger_cb` exactly (`layout_options_panel.py:928-945`, visibility at
`:2389-2391`, load at `:4425`, save at `:4604`): `setVisible(...)` and nothing
else. Never `setChecked(False)` on a hide.

I am recommending **against** the `_update_dd_visibility` memory pattern, and the
reason is the commits themselves: three of the four faults were caused by the
memory, not by the hiding. `ff3d1b2b` is a memory that restored on an
app-driven instrument change; `e1aeaf2f` is a memory that went stale because
`setChecked(False)` on an already-false box emits nothing; `ca0f639c` is a
remembered value reaching printtarg through a neighbouring control. A memory is a
second writer, and §4c D-2/D-4 exist because second writers are how a chosen
value gets destroyed. The rotation box needs no memory because its meaning never
changes, so there is nothing to protect it from.

Consequence, stated so nobody has to discover it: a tick made on a CR30 **will**
still be ticked on a SpectroScan. That is correct under D-2 (a value they chose
is not overwritten) and it is the same behaviour `cm_stagger` has today.

### 2. It must not reach a build while hidden — INERT BY CONSTRUCTION, confirmed.
Every place the orientation could act is already behind the honeycomb gate:

* `raster.py:1206-1207` `ss_hex = is_hexagonal(geom)` and `:1477` `if ss_hex:` —
  the shape is only ever drawn on a honeycomb;
* `instruments._build_base` sets `hxeh = hxew = 0.0` in the `else` of `if hflag:`
  (`:589-591` SS, `:728-733` CR30) — no reserve exists to flip;
* `instruments.build:357` `if geom.hexagonal and (patch_w or patch_h):` — the
  resize path is gated;
* `area_fit.py:118-121` `if kw.get("hflag") and instruments.hex_capable(...)`;
* `Geom.hexagonal`'s own docstring (`instruments.py:178-198`) makes it the single
  source of truth for "am I drawing a hexagon".

So the guarantee is real, **provided the new field is never read outside a branch
already guarded by `hexagonal`**. That is a rule, and a rule needs a test:
`build(key, hflag=False, hex_flat_top=True)` must return a `Geom` equal in every
field to `build(key, hflag=False)`. That makes inertness a pinned property rather
than a habit.

### 3. A run's stored value must survive a load — ONE WRITER, THE RECIPE.
The field goes in `LayoutRecipe` (`workflow/layout_engine/presets.py`), so it is
written into `<stem>.channels.json` with the rest of the recipe and is per-target
by construction — which is what `docs/design/per_target_settings.md` §1.2 makes
binding: *"the ChromIQ engine on/off, and its whole layout recipe"* is per
target, and Knut's correction is that it must be **all** of them, not a
selection.

The `d1adbe31` protection (the Guided row is applied last, and a PRESENT recipe
loses to it) is inherited **only because the value rides inside the recipe**.
So the design rule is absolute: **no separate `AppSettings` key for this.**
"Savable as a default" must mean "saved inside the default recipe
(`manual_engine_recipe`)", which §4c D-4 already classifies as *not an answer* —
a seed for a target with nothing stored, which a stored recipe overrides. A
parallel settings key would be a second writer and would reproduce `d1adbe31`
exactly.

### 4. Never ticked-and-disabled, never enabled-and-invisible.
`ca0f639c`'s fault was a box *"left ticked but disabled with no gesture to
recover, which still reached the build"*. Rule: this control is **hidden or
shown, never enabled/disabled**, matching `cm_stagger_cb`. Combined with #2
(inert while hidden) there is no reachable state in which it is set and
un-unsettable.

### The tests, in the shape of the sibling file
New file `tests/test_the_rotation_tick_belongs_to_the_honeycomb.py`, reusing that
file's `pick_instrument_as_a_person` / `app_sets_instrument` / `is_hidden`
helpers (`:59`, `:74`, `:80`):

1. `test_the_box_is_hidden_unless_hexagonal_and_hex_capable` — over every
   instrument × {hex on, hex off}: visible for exactly `{SS, CR30} × hex on`.
2. `test_hiding_it_never_unticks_it` — tick on a CR30 honeycomb, turn the
   honeycomb off, turn it back on: still ticked. Then i1Pro and back: still
   ticked.
3. `test_the_app_moving_the_instrument_never_changes_it` — the `app_sets_instrument`
   route (plain `setCurrentIndex`, no `activated`), the door `ff3d1b2b` found.
4. `test_a_runs_stored_answer_survives_the_app_seeding_the_instrument` — the
   `d1adbe31` case: a stored recipe with the flag on, loaded while the saved
   global default has it off; the run's value must win, and Guided/Manual/panel
   must agree afterwards.
5. `test_a_saved_default_does_not_overwrite_a_stored_recipe` — §4c D-4.
6. `test_it_is_never_ticked_and_unclickable` — over every route, in the shape of
   `test_no_density_box_is_ever_ticked_and_unclickable` (`:353`).
7. `test_a_rotation_flag_without_hexagons_changes_no_geometry` — the inertness
   invariant of #2, at the `instruments.build` level, over every instrument.
8. `test_the_flag_round_trips_through_the_recipe` — `to_dict`/`from_dict`/
   `channels.json`/preset export, and a recipe written **before** the field
   existed loads with it off (the `row_indicators` tri-state precedent,
   `instruments.py:335-338`: *"every recipe written before this existed renders
   byte-identically"*).

Two of the four guarantees are things I would refuse to ship without: #2's
inertness test and #8's old-recipe test. The other two are the sibling file's
existing shapes and cost almost nothing.

### On coupling with the ruler markers (ruling 7)
There is none in what I propose, and there never was: my H9 listed the markers as
a **separate, cheaper item**, not as a component of this feature. To be explicit
about the design: the rotation checkbox must not enable, disable, tick, untick or
hide `helper_markers`, `helper_markers_top_bottom`, `helper_markers_sides` or any
of the four `helper_marker_*` values (`presets.py:177-188`), and none of those
may touch the rotation. Two settings, two answers, two stored values.

One fact that is **not** a coupling and must not be turned into one: which page
axis is straight depends on the orientation (H3). If Knut ever changes the marker
rule (H16), the honest rule is orientation-dependent. That is a fact the marker
code would read off the geometry, exactly as it already reads the pitch off the
layout — not a control influencing another control.

## H14 — THE WIRING, AND THE EXACT i18n BILL.

### Where the field must be learned (reduced scope: Manual + gamut + default + preset)

| # | place | file:line | why |
|---|---|---|---|
| 1 | the recipe field | `workflow/layout_engine/presets.py:36` area (beside `cm_stagger`) | makes it per-target, presettable and default-able in one move |
| 2 | recipe → dict | `presets.py:382` | preset export, `channels.json` |
| 3 | dict → recipe | `presets.py:264` | must default to OFF so every recipe written before today is unchanged |
| 4 | build kwargs | `presets.py` `build_kwargs()` (the block containing `"cm_stagger": self.cm_stagger`) | |
| 5 | `build()` signature | `instruments.py:287` area | |
| 6 | **`GEOM_BUILD_KEYS`** | `instruments.py:398-405` | **the single line that makes every capacity readout in H10 follow the tick** |
| 7 | `chart.build_chart` kwarg | `workflow/layout_engine/chart.py:101` and `:215` | the non-UI entry point |
| 8 | the checkbox + tooltip | `ui/dialogs/layout_options_panel.py:928-945` pattern | **serves all three of Manual (`tab_chart.py:4978`), the from-profile-gamut module (`ti2_relayout_dialog.py:5163`) and Preferences → Chart Layout (`settings_dialog.py:5195`) from one widget**, because all three embed the same panel |
| 9 | visibility gate | `layout_options_panel.py:2389-2391` (`_sync_instrument_widgets`) **plus** `_area_is_hexagonal()` `:3210-3229` | ruling 6 needs BOTH conditions, and `_area_is_hexagonal` is already the panel's single answer to "is this a honeycomb", working with a shape combo (`self.mode`) or without one (`_recipe_hflag`, `:4547`) |
| 10 | load into the widget | `layout_options_panel.py:4425` area | |
| 11 | read out of the widget | `layout_options_panel.py:4604` area | |
| 12 | re-gate on shape change | wherever `_update_area_hex_locks()` is called (`:3205`, `:4563`) | the honeycomb can be turned on and off without an instrument change, and `_sync_instrument_widgets` alone will not see that |

**`data/parameters.yaml`: NO.** That file drives `ParameterWidget` rows for
`targen`/`printtarg` flags. The engine's layout recipe is not in it — `cm_stagger`
appears in no YAML anywhere in the repo (verified by grep). Putting it there
would create a second writer, which §H13.3 forbids.

**`_shared_get` / `_shared_set`: NO.** `tab_chart.py:7029-7110` mirrors only the
eight settings Guided and Manual both own (instrument, paper, pages, the two
densities, left border, no-strip-limit, preconditioning). Ruling 4 keeps this out
of Guided, so it has nothing to mirror. Adding it there would be the `ca0f639c`
shape: a value crossing a boundary where it means nothing.

**`docs/design/per_target_settings.md`, what is binding:** §1.2 puts *"the
ChromIQ engine on/off, and its whole layout recipe"* per target, with Knut's
correction that it is **all** of them; §S1.1 (`:95`) requires the per-target list
to be **generated, not hand-written**; §4c D-1 to D-4 (`:406-411`) govern
defaults. All four are satisfied by putting the field in `LayoutRecipe` and
nowhere else. Nothing in that document forbids a new per-target field; it
requires that a new one not be forgotten, which riding the recipe guarantees.

### The i18n bill, counted

Twelve catalogues (`data/i18n/{de,es,fr,it,ja,nl,no,pl,pt,ru,sv,zh_CN}.json`,
5,067 keys each) plus twelve `parameters.<code>.yaml` overlays, which are **not**
touched (no `parameters.yaml` change).

| new English string | why | × 12 |
|---|---|---|
| the checkbox label | reused verbatim as the tooltip TITLE, as `cm_stagger` does (`:928` and `:931` are the same string) | 12 |
| the tooltip body | | 12 |
| a flat-top variant of `hex_two_heights_note()` | `hex_support.py:110-131` is shipped in all 12 and says the hexagon *"is a third taller"*. Flat-top is a third **wider**. It is quoted in two places (`chart_layout_info_panel.py:144`, `layout_options_panel.py:979`) | 12 |

**3 new English strings, 36 translated strings.** The third one is the one that
will be forgotten: it is not new UI, it is an existing sentence that becomes
false. `hex_support.py:117-124` warns that these are *"long, shipped, and
translated into twelve languages, and retiring their keys mid-beta to add a
paragraph is not a trade worth making"* — so the flat-top variant must be a NEW
key, chosen at runtime, with the existing key untouched.

Process, per CLAUDE.md: no em dash in any of the three (the existing
`cm_stagger` tooltip has one and is frozen baseline, so it is not a precedent);
`python scripts/i18n_extract.py --missing de` after the strings land;
`tests/test_i18n.py` fails on a missing key, a stale key, a placeholder mismatch
or an over-long short label. §M of `unified_measurement_management.md` does not
apply — that catalogue governs measurement messages, and this is a Create Chart
control.

## H15 — THE WORDING.

Constraints: outcome first, the number 30 present (ruling 5), no jargon, no em
dash, honest about the cost, and it must not promise a shape change it does not
make.

### Checkbox candidates

1. **`Straight strips (turn the honeycomb 30°)`** — recommended.
   Outcome first, mechanism in brackets, five words before the bracket. Matches
   the house shape of `Hexagon patches (suits the round CR30, fits more per
   sheet)` and `Offset every second strip`.
2. `Strips in a straight line (honeycomb turned 30°)`
   Plainer, slightly long for the panel's second column.
3. `Turn the honeycomb 30° for straight strips`
   Mechanism first. Accurate, and the weakest of the three: a beginner reads
   "30°" before they read why they would want it.

I would not use "rotate": in this panel "turn" reads as an action the app does to
the sheet, while "rotate" collides with `indicator_rotation` and the page
rotation the renderer already talks about.

### Tooltip body for candidate 1 (title = the label, as `cm_stagger` does)

> Turns the honeycomb a sixth of a turn so a strip runs in a straight line.
>
> Without it, the patches in one strip sit alternately a little left and a
> little right of each other, so reading a strip means moving side to side at
> every patch. With it, one strip is a straight line you can lay a ruler along,
> and every second strip starts half a patch further down, which gives the ruler
> a clear edge to sit against.
>
> It only applies to hexagonal patches, so it is offered for the CR30 and the
> SpectroScan and only while Hexagon patches is switched on.
>
> The patch itself does not change: same shape, same size, same room around the
> instrument's window. Only the way the patches are packed onto the sheet
> changes, so the sheet holds a slightly different number. On A4 at the standard
> margins it is one row fewer, 391 patches instead of 405, which can push a large
> chart onto an extra sheet. Calculated Patches and the page count above always
> show the real number for the settings you have now, so check them after
> switching this on.

Word count 175, in the range of the existing `_hex_ratio_note` and the
`cm_stagger` tooltip. No em dash. "a sixth of a turn" carries the 30° in words as
well as in the label, which reads better in the twelve translations than a bare
degree symbol repeated.

### The exact UI elements the tooltip refers to, by name

* **`Hexagon patches`** — the relabelled density checkbox in Manual
  (`ui/tabs/tab_chart.py`, the `-h` box; relabelled per instrument, which
  `tests/test_the_density_tick_belongs_to_one_instrument.py:94` pins), and the
  **Patch shape** combo in Preferences → Chart Layout and in the
  from-profile-gamut module (`LayoutOptionsPanel.modes_for` `:267-270`,
  `("hex", tr("Hexagonal — denser"))`).
  ⚠ The combo's own label reads "Hexagonal — denser", not "Hexagon patches", so
  the tooltip names two different things in the two places it is shown. Either
  the tooltip says *"the hexagonal patch shape"* (neutral, my preference on a
  second pass) or the two labels are aligned first. **Open question 6.**
* **`Calculated Patches`** — the group box at `ui/tabs/tab_chart.py:4140`.
* **the page count** — the layout estimate line, `tab_chart.py:17766-17798`.

### What the label must NOT say

Not "60°": measured at zero vertex movement (H1), so it would be a false
statement on the face of a control. Not "Rotate hexagons": the *patch* is not
what visibly changes for the user; the *strip* is.

## H16 — SEPARATE ITEM, FOR KNUT: the ruler markers are switched off on a false
premise. (ruling 7: independent of the rotation feature, and still wanted.)

**What the rule says today.** `workflow/layout_engine/geometry.py:704-706`:

```python
from .instruments import is_hexagonal as _is_hex
if _is_hex(geom):
    return []
```

with the reason in the docstring at `:693-695`: *"Hexagonal charts return no
markers at all — SpectroScan or CR30 (#159): a honeycomb has no rows to line a
ruler up with. This is #152's rule, and it follows the SHAPE, not the
instrument."* The UI matches: `ui/tabs/tab_chart.py:18358` greys the six marker
controls whenever `_chart_is_hexagonal()`, and `:18427` refuses the preview
overlay.

**What I measured.** The premise is false. A honeycomb has straight lines of
centres along three directions at 0°, ±60° (H2), and on any page exactly one of
the two page axes is one of them:

| lattice | patches ACROSS the page (a row) | patches ALONG a strip (a column) |
|---|---|---|
| **today, pointy-top** | **straight**, pitch 12.0000 mm, `dy = 0.0000` | zigzags ±6.0 mm |
| **flat-top (this feature)** | zigzags ±5.196 mm | **straight**, pitch 12.0000 mm |

`geometry.helper_marker_lines_mm` already builds two independent combs and
already has a switch for each: `helper_markers_top_bottom` steps ACROSS the page
with the strips, `helper_markers_sides` steps DOWN the page with the patches
(`:657-675`, and its own warning that *"the names are the EDGE, never the
axis"*). So the machinery to offer exactly one of them already exists and is
already Knut's own #164 control.

**The honest rule, if he wants one.** *"A honeycomb gets the comb for the axis
its patch centres are straight along, and not the other. That is the top and
bottom comb on a pointy-top sheet and the side comb on a flat-top one."*
Today that would restore the top/bottom dashes to every SpectroScan and CR30
honeycomb, at zero cost in patches, ink or capacity.

**Caveats I owe him, so this is a decision and not a sales pitch.**
* The dashes are **printed ink** (`raster` draws them into the page), so this
  helps only charts printed after the change, not one already on the table.
* On today's sheet the straight axis is the SHORT one on a portrait A4: a
  horizontal row holds 15 patches, against 27 down a strip. So the straight line
  the markers would mark is shorter than the one the app currently asks the user
  to walk.
* This is #152's and #164's rule and both are his, so under CLAUDE.md's
  binding-spec rule this is reported, not fixed. `docs/design/` has no document
  covering the markers, which is itself worth noting.

### Sequencing, in the narrow form asked for

Both are worth doing. **Do H16 first**, and the reason is not that it is cheaper:

* H16 is a **defect** — a shipped rule resting on a measurably false premise —
  and the rotation is a **feature**. A defect that is known and not written down
  gets rediscovered.
* H16 needs a ruling from Knut, and rulings take calendar time that
  implementation does not. Starting the ask now costs nothing and unblocks later.
* Doing H16 first makes the rotation **cheaper and safer**, without coupling
  them: if the marker rule becomes "the straight axis", the flat-top orientation
  arrives into a rule that already reads the axis off the geometry, instead of
  arriving into a blanket `return []` that somebody will later have to
  re-derive with two orientations live at once. One less thing to get wrong in
  H12's nineteen sites.
* Neither changes the value of the other for the user. They are two separate
  aids to the same gesture, and a user can have either, both or neither.

Does either change the value of the other? Only mildly, and in H16's favour: on a
flat-top sheet the straight axis is the LONG one, so markers on a flat-top chart
mark a 23-patch line rather than a 15-patch one. If both ship, the pair is worth
more than the sum. That is an argument for doing both, not for coupling them.

## H17 — WHAT I WOULD NOT DO.

1. **I would not ship the label "Rotate hexagons by 60°".** Measured: zero vertex
   movement (H1). A control whose label states something the code provably does
   not do is worse than no control. Ruling 5 has already settled this at 30°.
2. **I would not add a separate `AppSettings` key for "savable as a default".**
   It creates the second writer that `d1adbe31` was written to remove. The
   default belongs inside the default recipe. (H13.3)
3. **I would not add the orientation before the four copies of the hexagon are
   made to call one function** (H12 #1, #11, #12, #14). Four copies of six
   vertices, each with a chance to keep drawing pointy-top, is exactly the
   half-patch mis-registration `instruments.is_hexagonal`'s docstring warns about,
   and it is invisible on a screenshot.
4. **I would not touch `_apply_hex_stagger`'s legacy fingerprint casually**
   (H12 #19). A flat-top chart looks exactly like a 2026-vintage unstaggered
   sidecar. That detection must gain a positive signal (the recipe's orientation)
   rather than a cleverer heuristic.
5. **I would not change the default right margin for everybody to recover the A4
   row** (H8). One millimetre buys 414 patches instead of 391, but the CR30
   family's margins are Knut's export and the default is a shipped value. Offer
   it as a note attached to the option, or as a per-recipe default for the
   flipped mode, and let him rule.
6. **I would not act on H16 myself.** It contradicts a shipped rule of Knut's
   (#152/#164). CLAUDE.md: *"A fault that contradicts the specification is not
   simply fixed. Report it, say which rule it breaks, and get the change reviewed
   and approved."*
7. **A citation correction, offered because acting on it would be worse than the
   error.** The briefs cite "CLAUDE.md principle 10" (backward compatibility) and
   "CLAUDE.md principle 6" (the beginner's mental model). **Neither exists.**
   `/Users/Basti/develop/ChromIQ/CLAUDE.md` has no numbered list of principles at
   all (its only numbered lists are the "Adding a parameter" recipe at `:436-439`
   and the two binding-spec obligations at `:460-463`). The substance of both is
   real and is written down elsewhere — backward compatibility as the
   `row_indicators` tri-state at `instruments.py:335-338` (*"every recipe written
   before this existed renders byte-identically"*), and the beginner's mental
   model in the i18n rules and in `feedback_tooltip_writing`. I have followed the
   substance and cited the real sources; nobody should quote the numbers.

---

# THE PLAN, IF HE SAYS BUILD IT

Numbered, with the file and line each step touches. Steps 1 and 2 are
preparation and are worth doing even if the feature is then dropped.

1. **Pool the four hexagons into one function.** Move the six vertices out of
   `raster.py:1069-1088` into `workflow/hex_support.py` as
   `hexagon_points(x0, y0, w, ph, index, orientation)`, and make
   `ui/tiff_preview.py:1747-1771` (`_patch_hexagon`), `ui/tiff_preview.py:1491-1512`
   (`_in_hexagon`) and `ui/scan_grid_marquee.py:793-806` call it. **No behaviour
   change in this step**, pinned by rendering a page before and after and
   comparing bytes.
2. **Pin the inertness invariant that does not exist yet**: for every instrument,
   a `Geom` built with `hflag=False` is unaffected by any orientation argument.
   (New test; see below.)
3. **The recipe field.** `presets.py` — dataclass field beside `cm_stagger:36`,
   `from_dict:264` defaulting False, `to_dict:382`, `build_kwargs()`.
4. **The geometry.** `instruments.py`: `build()` signature `:287`; the reserve
   swap in `_build_base` for SS `:588-591` and CR30 `:728-731`; the resize path
   `:357-361`; the `row_stagger_mm` branch beside `:363-366`; **and
   `GEOM_BUILD_KEYS:398-405`**, which is what makes every readout in H10 follow.
5. **The area-first aspect.** `area_fit.py:118-121` — `ratio` becomes
   `2/sqrt(3)` for a flat-top honeycomb.
6. **The drawing.** `raster.py:1477` passes the orientation into the pooled
   function; the row-label protrusion `raster.py:1389` (`strip_w // 4`) is a
   pointy-top allowance and becomes `plen // 4` on the vertical axis.
7. **The recorded rects.** `geometry.py:546-549` — the per-patch `±w/4` becomes
   the per-strip `±plen/4`, which `:519-520` already applies via
   `row_stagger_mm`. This is the line that keeps the `.cht`, the overlay and the
   margin inspector honest.
8. **The margin inspector.** `workflow/margin_inspector.py:283-287` — the apex
   overhang moves from `y0/y1` to `x0/x1`.
9. **The legacy-sidecar fingerprint.** `ui/tabs/tab_measure.py:528-578` — add a
   positive test on the stored recipe's orientation so a flat-top chart is never
   mistaken for a legacy unstaggered sidecar (H12 #19).
10. **The scanner sample cap.** `workflow/scanin_runner.py:138-166` — swap `w`
    and `h` for a flat-top chart, or record in the docstring why it is left
    conservative.
11. **The reporting note.** `workflow/hex_support.py:83-131` — a flat-top variant
    of `hex_two_heights_note()` as a NEW key, chosen at runtime; consumers at
    `ui/chart_layout_info_panel.py:144, 185, 254-258` and
    `ui/dialogs/layout_options_panel.py:979`.
12. **The control.** `ui/dialogs/layout_options_panel.py` — checkbox + tooltip in
    the `cm_stagger_cb` pattern `:928-945`; visibility on instrument **and**
    `_area_is_hexagonal()` (`:2389-2391` and `:3210-3229`); load `:4425`; save
    `:4604`; re-gate wherever `_update_area_hex_locks()` runs (`:3205`, `:4563`).
    One widget serves Manual (`tab_chart.py:4978`), the from-profile-gamut module
    (`ti2_relayout_dialog.py:5163`) and Preferences → Chart Layout
    (`settings_dialog.py:5195`).
13. **i18n.** 3 new English strings; `python scripts/i18n_extract.py --missing de`
    then the other eleven; `tests/test_i18n.py` and
    `tests/test_no_new_em_dash_in_user_facing_text.py` are the gate.
14. **Changelog.** One line, and it must name the A4 patch-count change (H8) and
    say the option is off by default so nothing existing moves.
15. **`--runslow` green** before any merge or tag decision.

## TESTS THAT MUST EXIST

* `test_a_flat_top_honeycomb_is_a_regular_hexagon` — six equal sides, ratio
  `2/sqrt(3)`, both orientations, both instruments. The FLIP-B guard.
* `test_the_rotation_is_inert_without_hexagons` — plan step 2. Every instrument.
* `test_the_flipped_lattice_has_a_straight_strip` — measured off
  `geometry.patch_rects_px`: `dx == 0` down a strip, `±plen/2` between adjacent
  strips. The whole point of the feature, asserted on the recorded geometry
  rather than on a picture.
* `test_the_recorded_rects_match_the_ink` — the 2026-08-13 fault, re-run for the
  new orientation: render at high dpi, find each hexagon's real centroid,
  compare with the recorded rect.
* `test_a_flat_top_chart_is_never_treated_as_a_legacy_sidecar` — H12 #19.
* `test_the_capacity_readout_follows_the_tick` — mutate `GEOM_BUILD_KEYS` to drop
  the key and prove the test goes red (a mutation that is proven to land).
* `test_the_four_hexagon_drawings_agree` — the pooled function, called by all
  four sites, both orientations.
* `test_the_rotation_tick_belongs_to_the_honeycomb` — the eight cases in H13.
* `test_a_recipe_written_before_this_field_renders_byte_identically` — the
  `row_indicators` precedent.
* `test_no_new_em_dash_in_user_facing_text` and `test_i18n` — already exist and
  will fail on the three new strings until they are translated.

## OPEN QUESTIONS NEEDING HIS ANSWER BEFORE CODE

1. **Does the option's own default recipe get a 5.0 mm right margin on A4?**
   H8: at 6.0 mm the flip costs a row (405 → 391); at 5.0 mm it gains one
   (414). One millimetre is the whole difference between "costs you patches" and
   "gains you patches", and the tooltip's honesty paragraph depends on the answer.
2. **Does it apply to the SpectroScan as well as the CR30, or only be offered
   there?** Ruling 6 says visible for both. The SpectroScan is a motorised
   flatbed with no ruler and no hand: the straight strip buys it nothing that I
   can see. Offering a control that does nothing useful for one of the two
   instruments that show it is a decision, not an oversight, and he should make
   it knowingly.
3. **H16 — may the ruler markers be offered on the straight axis of a
   honeycomb?** Knut's call (#152/#164). See H16 for what he needs to rule on.
4. **Should the four hexagon drawings be pooled first (plan steps 1–2) as its own
   commit?** It is the largest single risk reducer and it is not the feature.
5. **What does the changelog say about A4?** A user who ticks the box and loses a
   row should read it in the changelog, not discover it.
6. **"Hexagon patches" or "Hexagonal — denser"?** The tooltip must name the
   parent control, and the two places that show it use different words
   (H15). Align the labels, or make the tooltip say "the hexagonal patch shape".
7. **Is a fifth verdict needed anywhere?** No. Stated only so it is on the record
   that I looked: nothing in this feature touches the Measurement Report's limit
   sets or §M.

## RATING

**7 / 10.**

Up: the outcome is real and the complaint is legitimate — a hand-placed round
instrument being walked down the one axis of a hex lattice that has no straight
line is a genuine ergonomic mistake, and it is ChromIQ's, not the hexagon's. The
fix is geometrically clean once the number is right, the patch itself is
untouched (6.000 mm inradius, 4.000 mm clearance, identical area), the capacity
cost is a millimetre of margin rather than a real loss, and the app already owns
every mechanism it needs: `row_stagger_mm` for the half-pitch offset,
`is_hexagonal` as the single gate, `GEOM_BUILD_KEYS` as the single capacity
chokepoint, and `LayoutOptionsPanel` serving all three modules from one widget.
Scoped to an opt-in box that is off by default, it cannot hurt anybody who does
not go looking for it.

Down: nineteen sites, four of them independent copies of the same six vertices,
and the failure mode of every one of them is a half-patch mis-registration that
looks fine on screen. One of them (`_apply_hex_stagger`'s legacy fingerprint)
would misfire on **every** flipped chart by design. And the benefit is gated
behind a checkbox that is off, which means the two cheaper items — H16's markers,
and the free one, telling users the rows are already straight — reach more people
for less risk.

Not higher, because a feature whose whole value is behind an off-by-default tick
should not be the most expensive thing on the list. Not lower, because the
request is right about the problem even though it was wrong about the number, and
the fix is honest work rather than a workaround.

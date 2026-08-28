STATUS: in-progress

# 05 — Chart-layout critique for the CR30 (#159)

**Role:** CR30-CHART-CRITIC. Adversarial review of two *unfinished* chart-layout
decisions, before they land. Everything below is read from the working tree of
`feature/cr30-instrument-159` and cited `file:line`. No production file was
edited by this report.

**The two decisions under attack**

1. Offer **hexagonal patches** for the CR30, as the SpectroScan does.
2. **Spacers OFF by default** for the CR30, user-changeable; Guided always off.

Findings are ranked BLOCKER / SERIOUS / MINOR and collected at the end.

---

## Section 1 — Decision 1: hexagons for the CR30

### 1.0 What is actually in the tree

At the time of writing, the hex-for-CR30 work is **uncommitted** in the working
tree (HEAD `7c6b53ff`; `git status` shows only `instruments.py` and
`presets.py` modified, with `layout_options_panel.py` edited live during this
review). What has landed:

* `workflow/layout_engine/instruments.py` — the CR30 branch now takes `hflag`
  and sets `plen = pscale * sqrt(0.75) * 10.0`, `hxeh = plen/6`,
  `hxew = pscale * 0.25 * 10.0`, and emits `("HEXAGON_PATCHES", "True")`.
* `instruments.py:249` — the patch-resize overhang fix widened from
  `key == "SS"` to `key in ("SS", "CR30")`.
* `workflow/layout_engine/presets.py` — `LayoutRecipe.mode()` for CR30 changed
  from `"spot"` to `"hex"/"flat"`; `default_recipe` maps the mode to `hflag`;
  `factory_defaults` emits `CR30|A4|flat` and `CR30|A4|hex`.
* `workflow/hex_support.py:104` — `recipe_is_hexagonal` widened to
  `inst in ("SS", "CR30")`.
* `ui/dialogs/layout_options_panel.py` — CR30 mode label is now "Patch shape:",
  `modes_for("CR30")` returns `flat`/`hex`, and a CR30-specific tooltip.

The critique below is against that state.

### 1.1 BLOCKER — the renderer draws SQUARES for a CR30 hex chart

`workflow/layout_engine/raster.py:1056`

```python
ss_hex = getattr(geom, "key", "") == "SS" and getattr(geom, "hxew", 0.0) > 0
```

The renderer decides "am I drawing hexagons?" by **instrument key**, not by the
geometry. A CR30 has `key == "CR30"`, so `ss_hex` is False and
`draw.polygon(_hexagon_points(...))` is never reached — the branch at
`raster.py:1244-1248` falls through to `_fill_rect`.

The result is not "a rectangular chart". It is the **worst of both**: the
geometry has already shortened `plen` to 8.660 mm and reserved
`hxew = 2.500 mm` / `hxeh = 1.443 mm` of page for apexes and stagger that are
never drawn. The user gets 10.000 × 8.660 mm **rectangles**, un-staggered, on a
page that has given up 5 mm of width and 2.9 mm of height for nothing.

**Proved by rendering, not by reading.** `default_recipe("CR30","A4",mode="hex")`
→ `chart.build_from_recipe` at 150 dpi produces a grid of rectangles.
The identical call with `instrument="SS"` on the same `.ti1` produces a proper
interlocking honeycomb, so the path works and only the key test rejects the
CR30. Renders kept at
`scratchpad/render/{cr30_hex_corner.png, ss_hex_corner.png}`.

Also gated on the same flag, one line below the failure:

* `raster.py:1222` — `_protrude = (strip_w // 4) if ss_hex else 0`, the
  clearance that stops staggered patches covering the row numbers in the `rlwi`
  band. The CR30 is the *only* instrument for which those row numbers are the
  primary ergonomic feature (`instruments.py`, CR30 branch: *"the single most
  useful piece of furniture on the page"*), and it is the one that will not get
  the clearance.

**Fix:** both tests must key off the geometry, not the instrument —
`getattr(geom, "hxew", 0.0) > 0` alone is already the sufficient and honest
condition, since only a hexagonal geometry ever sets it. If a belt-and-braces
instrument list is wanted, it must read `key in ("SS", "CR30")`.

### 1.2 BLOCKER — the recorded patch rects do not carry the CR30 stagger

`workflow/layout_engine/geometry.py:475`

```python
# The same test the renderer uses to decide it is drawing hexagons.
_ss_hex = getattr(geom, "key", "") == "SS" and getattr(geom, "hxew", 0.0) > 0
```

`patch_rects_px` applies the ±¼·width hexagon stagger only under this flag
(`geometry.py:512-515`). The comment above it records exactly why that matters:
without it the recorded box *"described a place no ink is: measured ±21 px on an
84 px patch … seen as overlay hexagons sitting over their neighbours"*, and
*"everything reading this geometry inherited it, the expected-vs-measured
overlay and the scanner target's patch boxes alike"*.

Today the CR30 is saved by the previous blocker — the raster does not stagger
either, so the two agree by accident. **Fix 1.1 alone and this becomes a live
mis-registration bug**: the sheet would be staggered and every recorded rect
would point half a patch away. The Measure tab's current-patch highlight, the
margin inspector's ink extremes, and `workflow/scanin_target.py` all read these
rects.

The two fixes are therefore **one change, not two** — the comment on
`geometry.py:474` literally says it is mirroring the renderer's test, so the two
must be corrected together or the tree passes through a state that is worse
than either endpoint.

### 1.3 BLOCKER — helper markers are not suppressed on a CR30 honeycomb

Two places, both `"SS"`-only:

* `workflow/layout_engine/geometry.py:669` —
  `if getattr(geom,"key","") == "SS" and getattr(geom,"hxew",0.0) > 0: return []`
  in `helper_marker_lines_mm`. This is the engine-side refusal to emit ruler
  dashes for a chart with no straight rows.
* `ui/tabs/tab_chart.py:16175` and `:16180` — `_chart_is_hexagonal()` tests
  `panel.instr.currentData() == "SS"` (and the recipe fallback
  `instrument.upper() == "SS"`). It drives
  `panel.set_helper_markers_supported(...)` at `:16467` and the early return in
  `_helper_marker_lines_frac` at `:16536`.

This is **#152 reproduced verbatim for the CR30**. Knut's report was: *"When
instrument is SpectroScan and Patch shape is Hexagonal, the checkbox for 'Show
helper markers' with its spinboxes and belonging labels are not greyed with
explanation tool-tip, as specified."* Pick CR30 + Hexagonal today and the
controls stay live, the tooltip never explains itself, and the engine will
compute dashes against a staggered grid.

**Fix:** `geometry.py:669` should drop the key test (`hxew > 0` is the real
condition). `_chart_is_hexagonal` in `tab_chart.py` should delegate to
`workflow.hex_support.recipe_is_hexagonal` — which was already widened to
`("SS","CR30")` at `hex_support.py:104` — instead of carrying its own second
copy of the instrument list. Two copies of the same predicate is how these three
sites drifted apart in the first place.

### 1.4 SERIOUS — the "hexagons cost nothing" claim, measured

Both the code comment (*"a honeycomb costs nothing in readability and packs
roughly 15 % more patches onto the sheet"*, `instruments.py`) and the shipped
tooltip (*"roughly 8 % more patches … The shape costs a CR30 nothing to read"*,
`layout_options_panel.py:130-133`) make quantitative claims. They disagree with
each other, and one of them is wrong.

Measured through the real engine (`geometry.patches_per_sheet`, CR30, spacers
off, default 6 mm border):

| paper | square 10 mm | hex 10 mm | gain |
|---|---|---|---|
| A4 portrait | 513 | 558 | **+8.8 %** |
| A4 landscape | 513 | 567 | +10.5 % |
| A3 portrait | 1080 | 1215 | +12.5 % |

So the **tooltip's "8 %" is right for A4 and the code comment's "15 %" is
wrong** — 15.5 % is the infinite-sheet pitch ratio (100 mm² ÷ 86.6 mm²), and a
real page never sees it because the honeycomb hands back 2·`hxew` = 5.0 mm of
width and 2·`hxeh` = 2.9 mm of height as apex/stagger reservation. Fix the
comment; the tooltip is fine (and might say "8–12 % depending on paper").

**On "costs nothing to read".** With a round instrument the right comparison is
clearance around the 4 mm aperture, and here the implementation has quietly
chosen one end of a trade-off without saying so. The code sets the hexagon's
**flat-to-flat width equal to the square's width** (`pwid` stays `pscale*10.0`;
only `plen` shrinks to 8.660). That means:

* inradius 5.000 mm, identical to the 10 mm square → **minimum clearance
  around the aperture is unchanged at 3.000 mm**. The honeycomb is not more
  forgiving as implemented.
* patch **area** falls from 100.0 to 86.6 mm², so the safe-placement region
  (the patch eroded by the 2 mm aperture radius) falls from 36.0 mm² to
  31.2 mm² — **−13.4 %**. The *minimum* tolerance is the same; the *area* of
  tolerance is not.

The 7.5 %-larger-inradius / +12 % clearance advantage a hexagon can have over a
square exists only at **equal area**, i.e. flat-to-flat 10.746 mm. This
implementation does not do that, and it should not: measured, an equal-area
hexagon yields **493 patches on A4, fewer than the 513 the square gives**,
because the reservation overhead outweighs the packing gain.

**There is free clearance on the table, though.** Capacity is quantised by
whole columns, so on A4 portrait every hexagon width from 10.000 to 10.200 mm
gives the *same* 558 patches:

| hex flat-to-flat | A4P patches | clearance | vs square |
|---|---|---|---|
| 10.000 (as coded) | 558 | 3.000 mm | +8.8 % patches, +0 % clearance |
| **10.200** | **558** | **3.100 mm** | **+8.8 % patches, +3.3 % clearance** |
| 10.500 | 510 | 3.250 mm | −0.6 % patches, +8.3 % clearance |
| 10.746 (equal area) | 493 | 3.373 mm | −3.9 % patches, +12.4 % clearance |

10.200 mm is strictly better than 10.000 mm on A4 portrait — same patch count,
3.3 % more clearance — and 10.500 mm buys 8.3 % more clearance for a 3-patch
loss. This is a genuine choice on a device **whose minimum patch size has never
been measured** (`chromiq-cr30-research/MEASUREMENT.md:486-488`: what
EXP-MEAS-005 measured was *repeatability* with the aperture *"well inside"* the
patch; *"a deliberate experiment placing the aperture near a patch edge"* was
never run). The current 10.000 mm is the SpectroScan branch's equal-width
convention copied across — which is exactly what the CR30 branch's own comment
says the branch exists to avoid: *"a spot grid is NOT the SpectroScan's grid,
and the differences are the whole point of this branch existing."*

I am not asking for a different number by fiat — the point is that **the number
was inherited rather than chosen, and the sheet is paying for a clearance gain
it does not receive.** It should be a deliberate decision, recorded.

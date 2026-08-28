STATUS: complete

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

> **Re-verified against commit `22f005aa`** ("cr30: hexagonal patches in every
> Create Chart module, and spacers off by default without killing the control"),
> which landed while this report was being written. Blockers 1.1, 1.2 and 1.3
> are all still present in that commit. `raster.py:1056`, `geometry.py:475` and
> `geometry.py:669` are unchanged, and a fresh render of
> `default_recipe("CR30","A4",mode="hex")` still produces rectangles.
> `geometry.patch_rects_px` on a CR30 hex geometry returns **one distinct x per
> column** — i.e. no stagger recorded — which is 1.2 measured directly.

### 1.5 Should hexagons be the CR30 DEFAULT?

**No — keep Rectangular, as the SpectroScan does. Recommendation, with the
reasoning, not a preference.**

The pro-hex case is sound and I could not break it. For a round 4 mm aperture,
hexagonal close packing genuinely is the efficient arrangement (90.7 % of the
sheet within reach of an inscribed circle against 78.5 % for a square grid —
both numbers in the Guided tooltip at `tab_chart.py:11841-11846` are correct and
correctly describe *this* layout), the clearance around the aperture is
unchanged at 3.000 mm, and the measured gain is real: 532 → 576 patches on A4.

What decides it against being the *default* is what a honeycomb silently
switches off:

1. **The scanner and camera tools refuse it** unless the user finds
   "Allow hexagonal charts in the scanner and camera tools" under
   Preferences → Beta (`hex_support.py:73-79`, `hex_scanner_message`). A default
   must not require a Beta opt-in somewhere else to stay whole.
2. **The ruler helper markers are unavailable** — `geometry.helper_marker_lines_mm`
   returns `[]` for a hexagonal geometry (`geometry.py:669`), by design, because
   a honeycomb has no straight rows to line a ruler against.
3. **It does not currently work at all** (1.1–1.3).

And what is bought is small in the currency that matters to a CR30 user, which
is *time*, not patches. `chromiq-cr30-research/INTEGRATION.md:277-279`: *"If a
reading takes ~1 s … a 400-patch chart is ~7 minutes of manual placement."*
The A4 gain of 44 patches is therefore worth roughly **45 seconds on a 9-minute
sheet** — while costing three capabilities that stop working without saying so.

There is also a **consistency** argument, which the brief asks about
explicitly. `layout_options_panel.py:127-129` tells the SpectroScan user
*"rectangular is the safe default"* and the CR30 user the same words. Two
instruments, one control, one label, two different defaults would be a mental
model a user has to learn for no benefit they can see. Defaulting both to
Rectangular and letting the (very good) CR30 tooltip sell the honeycomb is the
coherent answer.

**What would change my mind:** a measured tolerance envelope. The research repo
is unambiguous that this does not exist —
`chromiq-cr30-research/MEASUREMENT.md:483-489`: *"This does NOT give the minimum
patch size … The minimum patch size needs a deliberate experiment placing the
aperture near a patch edge until the reading degrades. **Chart layout is still
blocked on that**, not on this number."* Until that experiment is run, the
default should be the shape that keeps every other ChromIQ feature working.

### 1.6 SERIOUS — an unmeasured ergonomic claim in a user-facing string

`ui/tabs/tab_chart.py:11848-11850`, the Guided hexagon tooltip:

> *"The honeycomb also helps you aim: six sides funnel a round barrel towards
> the middle of the cell in a way four right angles do not, and the interlocking
> rows make it harder to lose your place in a large grid."*

Nobody has tested either half. No CR30 placement experiment has been run at all
(§1.5), and "harder to lose your place" is the opposite of what the honeycomb
does to the column coordinate (§1.7). This sits in the same dialog as the patch
-size tooltip, which is scrupulously honest — *"nobody has yet measured how
small a CR30 patch can safely be"* — so the dialog currently applies two
different standards of proof to two claims about the same instrument.

The rest of that tooltip is excellent and should stay: the packing numbers are
right, the 532/576 figure matches a real render, and *"you keep exactly the same
room around the aperture"* is exactly true of the implemented equal-width
hexagon. It is the one aiming sentence that outruns the evidence.

### 1.7 SERIOUS — the column coordinate zigzags, and only the rows are honest

The CR30's whole ergonomic case rests on the 2-D A1/B2 coordinate; the CR30
geometry branch calls the `rlwi = 7.5` row-number band *"the single most useful
piece of furniture on the page"*. On a honeycomb that coordinate is **half
true**:

* **Row numbers still work.** Rows are straight horizontal lines at `plen`
  pitch; `raster.py:1225-1230` draws the number against the row's true
  mid-y. Verified on the SpectroScan hex render.
* **Column letters do not.** `raster._hexagon_points` offsets every patch by
  `∓w/4` on alternating rows, so a "column" is a vertical zigzag of total
  amplitude `w/2` — **5.0 mm on a 10 mm CR30 patch, half a patch width** —
  while its letter sits on a straight line at the top of the page. Visible in
  the SpectroScan render at `scratchpad/render/ss_hex_corner.png`: column A's
  patches alternate left and right under a single "A".

This is followable but it is a real cost, and it is the cost that lands on
precisely the instrument that needs the coordinate most — a CR30 user reads
~500 of these by hand over ~9 minutes. It should be stated, and the Guided
tooltip currently claims the opposite ("harder to lose your place").

**Mitigation that already exists and should be checked before anything is
built:** the Measure tab arms click-to-jump over every patch on the first
`patch_ready` event (`tab_measure.py:10243-10247`) and highlights the next patch
with a haloed ring. On a honeycomb the ring is drawn as a **hexagon**, not a
rectangle — `tiff_preview.py:2635` and `:2660-2668`, guarded by `_hex_zigzag`,
which is now true for a CR30 hex chart because `chart_is_hexagonal` →
`recipe_is_hexagonal` was widened at `hex_support.py:104`. So the on-screen
answer to "which patch now?" is correct for a honeycomb. **This survives the
attack and is the strongest thing in the feature** — provided 1.2 is fixed,
because `_patch_hexagon` (`tiff_preview.py:1569-1592`) draws the hexagon around
the *recorded rect* and applies no stagger of its own.

### 1.8 What survives — hex support does NOT assume motorised positioning

I attacked this and could not break it.

* **`recipe_is_hexagonal`** (`hex_support.py:82-104`) is now instrument-list
  driven and includes CR30. Everything keyed off it follows for free:
  `margin_inspector.py:282-285` (the apex correction to the reported ink
  extremes), `scanin_dialog.py:1974-2015` (the sample-area cap),
  `tab_measure.py:4190` (`set_hex_zigzag`), `tab_measure.py:505-520` (the
  legacy-sidecar stagger compensation).
* **`hex_max_sample_fraction`** (`scanin_runner.py:140-160`) derives the cap
  from the chart's own `w`/`h` proportions, with no instrument in it.
* **The `.cht` / scanner path** is corner-placed by the user, not
  machine-found — the `-p` perspective search was removed precisely because it
  *"collapses on a honeycomb"* (`hex_support.py:19-22`). Nothing there assumes a
  motor.

**`HEXAGON_PATCHES` is accepted downstream, and is inert on the CR30's path.**
`native/chartread_helper/chromiq_chartread.c:3819-3820` parses the keyword into
`hex` and passes it to `read_strips` at `:4246`. `hex` is then dereferenced in
exactly one place — `:1753-1786` — which lives inside the `rmode == 2` branch
(`:1541`, *"For xy mode, read each sheet"*), gated on `inst2_xy_locate` /
`inst2_xy_holdrel`, and its whole job is to turn 1–3 user-placed fiducials into
`ox/oy/ax/ay/aax/aay/px/py` **navigation vectors for a motorised table**
(consumed by `read_xy` at `:1802`). A CR30 has no XY capability, so
`check_mode` puts it on `rmode = 0` (spot) at `:1230`/`:1247` and the hex
navigation code is never reached. **So this is the one place that genuinely
does assume motorised positioning, and the CR30 correctly never enters it.**
Nothing rejects the keyword; nothing errors.

Minor caveat: emitting `HEXAGON_PATCHES` in a CR30 `.ti2` is a claim about the
sheet that third-party CGATS readers or stock Argyll `chartread` could act on.
Contained in practice, because ChromIQ already refuses stock chartread for a
CR30 chart (M-CR30-STOCK-READER, `tab_measure.py:4407-4451`).

---

## Section 2 — Decision 2: spacers off by default, mechanically

Basti has ruled: **CR30 spacers off by default, Guided always off, changeable in
the other modules.** Nothing below argues with that. This is only whether the
mechanism delivers it.

### 2.1 What survives — the dead-control trap was correctly avoided

The trap is real and is at `workflow/layout_engine/instruments.py:228`:

```python
if spacer_width is not None and geom.pspa > 0:   # only when spacers are on
    pspa = float(spacer_width)
```

A zero base width makes the Manual "Spacer size" box permanently inert. The
implementation avoids it exactly as its own comment says: the geometry keeps a
real `pspa = spacer(1.3)` and the *default* lives in
`presets.default_recipe`, which sets `r.spacer_mode = "none"` for a CR30 →
`spacer_on=False` → `spacer()` returns 0.0.

Verified by running `instruments.build` directly:

| call | resulting `pspa` |
|---|---|
| `build("CR30", spacer_on=False)` (the new default) | 0.000 |
| `build("CR30", spacer_on=True)` | 1.300 |
| `build("CR30", spacer_on=True, spacer_width=3.0)` | 3.000 |

Both halves of the requirement hold: off by default, and fully turnable on with
a live width box. **This is right, and the reasoning recorded in the comment is
the right reasoning.**

### 2.2 The same coupling on every other instrument — one is already broken

Sweeping `build(k, spacer_on=True, spacer_width=3.0)` across all seven
instruments:

| instrument | base `pspa` | with `spacer_width=3.0` |
|---|---|---|
| i1 | 1.000 | 3.000 |
| p3 | 2.000 | 3.000 |
| CM | 1.000 | 3.000 |
| **SS** | **0.000** | **0.000** |
| CR30 | 1.300 | 3.000 |
| 41 | 2.032 | 3.000 |
| 51 | 1.778 | 3.000 |

**The SpectroScan's geometry branch hard-codes `pspa=0.0`, so its "Spacer size"
box has never done anything and never can.** That is the exact fault the CR30
comment describes, already shipped on another instrument, and it is a
pre-existing bug not introduced by this work. Worth reporting because (a) it is
the precedent that makes the CR30's approach demonstrably the right one, and
(b) a CR30 user and an SS user meet the same control with different truth.

### 2.3 SERIOUS — "Spacer size" is enabled but inert whenever spacers are off

`spacer_width` is **never disabled**. The only enable/disable logic near it is
`ui/dialogs/layout_options_panel.py:2898-2904`:

```python
def _sync_spacer_swatches(self, *_a) -> None:
    ...
    on = (self.custom_spacer_cb.isChecked()
          and (self.spacer_mode.currentData() or "colored") == "colored")
    for b in self._spacer_swatches:
        b.setEnabled(on)
```

— which greys only the custom-colour swatches, not the width box.

So with `Spacers: None` the user can type a width into "Spacer size" and it is
silently discarded at `instruments.py:228`. This has always been latent for
every instrument, but **the CR30 is the first instrument that ships with
`spacer_mode="none"` as its default**, so it is the first where a user meets the
dead control out of the box, on the very setting the ruling says must be
changeable. Verified: `build("CR30", spacer_on=False, spacer_width=3.0).pspa`
== 0.0.

**Fix:** disable `spacer_width` (and its label/tooltip row) whenever
`spacer_mode.currentData() == "none"`, from the same handler that already runs
on `spacer_mode.currentIndexChanged` (`layout_options_panel.py:673`). One line
in `_sync_spacer_swatches`, or a sibling `_sync_spacer_width_enabled`.
This makes the control tell the truth for every instrument, and it makes
"off by default, changeable" legible: the user sees the width greyed, changes
Spacers to Coloured, and the width lights up.

### 2.4 What survives — "always off in Guided" is expressible without a leak

`workflow/chart_creator.py:1199-1206`:

```python
elif params.instrument == "CR30":
    ...
    if not params.is_manual:
        kw["spacer_on"] = False
        kw["spacer_mode"] = "none"
```

This sits **inside** the `elif params.instrument == "CR30"` arm, so it cannot
reach another instrument. `params.is_manual` is the existing Guided/Manual
discriminator already used at `chart_creator.py:1108`. A Manual chart carrying a
layout recipe never reaches this branch at all (it goes through
`_engine_kwargs`), so a Manual user who deliberately turns spacers on keeps
them. **No special case, no leak. This is correct.**

### 2.5 What survives — nothing breaks at `pspa == 0`

I traced every consumer of `pspa` and each one guards zero:

| site | behaviour at 0 |
|---|---|
| `geometry.py:104` `if (g.plen + g.pspa) <= 0` | `plen` is 10 mm, never trips |
| `geometry.py:107` capacity | `(arowl − …) / (plen + 0)` — fine |
| `geometry.py:342` | guarded `geom.pspa > 0` |
| `geometry.py:543` `spacer_rects_px` | returns `[]` early |
| `raster.py:1053, 1266` | `if sp_px > 0 and spacer_mode != "none"` |
| `margin_inspector.py:264` | expands the ink box by 0 |
| `area_fit.py:121,124` | divides by `height + pspa`, `height > 0` |
| `tab_measure.py:476` | spacer height 0 |

Capacity maths measured end to end (A4 portrait, CR30): 513 patches with
spacers off, 456 with them on. Both render.

**`.cht` / `SAMPLE_LOC`:** no exposure. `cht_writer` contains no reference to
`pspa`, spacers, gaps or insets — a `.cht` describes the rectangle sampled
inside each recorded patch box. `emit_cht` defaults False
(`layout_engine/chart.py:188`) and is not set on any CR30 path.

**Measure-tab patch highlighting:** driven by `patch_rects_px`, which does not
read `pspa`. Unaffected.

Zero-spacer is also not novel to the engine — the SpectroScan has shipped that
way since #93 (§2.2). **The ruling is mechanically safe.**

---

## Section 3 — everything else, and why the blockers got through

### 3.1 Correction to §1.4 — the equal-width choice IS deliberate

`tests/test_cr30_registration.py:130-136` pins it explicitly:

```python
assert sq.pwid / 2 == hexg.pwid / 2, "same clearance around the aperture"
assert hex_area < sq.pwid * sq.plen, "less paper per patch"
```

So the equal-width hexagon was chosen and tested, not copied unthinkingly, and
the Guided tooltip's *"you keep exactly the same room around the aperture"* is
an accurate description of it. **I withdraw the "inherited rather than chosen"
half of §1.4.**

What stands is narrower and still worth acting on: because capacity is
quantised by whole columns, **flat-to-flat 10.200 mm yields the identical 558
patches on A4 portrait with 3.3 % more clearance than 10.000 mm.** That
headroom is free and is currently unclaimed. It is a MINOR, not the SERIOUS I
first graded it.

### 3.2 BLOCKER-adjacent — why the gate is green on a feature that does not work

`tests/test_cr30_registration.py` is thorough about `Geom` **fields** — shape,
overhang, keyword, spacer on/off/size, preset keys, capacity ordering. Not one
test renders a CR30 chart or inspects a recorded rect. Meanwhile the whole
existing hex suite is hard-coded to the SpectroScan:

* `tests/test_layout_raster.py:89` — `default_recipe("SS", "A4", mode="hex")`
* `tests/test_layout_raster.py:510, 527` — `_hexagon_points`, "SpectroScan hex
  patches render as hexagons whose top apex pokes above…"
* `tests/test_hex_overlay_geometry.py:34, 77, 100, 108` — every fixture builds
  `instruments.build("SS", …)`

That is exactly why 1.1 and 1.2 pass: the assertions that would catch them exist
and are pointed at the other instrument. **Parametrising those two files over
`("SS", "CR30")` would have caught both blockers and is the single highest-value
change in this report after the fixes themselves.**

### 3.3 SERIOUS — Manual resets a CR30 to i1Pro

`ui/tabs/tab_chart.py:5235`, in `_sync_engine_panel_selection`:

```python
eng = {"3p": "p3"}.get(self._active_instrument_flag(), self._active_instrument_flag())
if eng not in ("i1", "p3", "CM", "SS"):
    eng = "i1"
```

A CR30 is not in the list, so switching Manual on seeds the engine layout panel
with **i1Pro**. The user picked a CR30 and the panel silently says i1Pro —
different patch size, different clip-border behaviour, different preset.

### 3.4 SERIOUS — Preferences → Chart Layout opens on i1 for a CR30

`ui/tabs/tab_chart.py:16790`, in `current_layout_combo`, the same missing entry:

```python
if instr not in ("i1", "p3", "CM", "SS"):
    instr = "i1"
```

Its own docstring says the point of this method is *"so Preferences opens on
what the user is editing, instead of always resetting to i1/A4 (which made a
preset saved under any other combination look lost)"* — which is precisely what
now happens to every CR30 preset.

Both 3.3 and 3.4 are one-word fixes and are independent of either decision under
review; they are CR30 registration gaps.

### 3.5 MINOR — the `~15 %` in the code comment is wrong

`workflow/layout_engine/instruments.py`, CR30 hex comment: *"packs roughly 15 %
more patches onto the sheet."* Measured through `geometry.patches_per_sheet`:
**+8.8 %** (A4 portrait), +10.5 % (A4 landscape), +12.5 % (A3 portrait). 15.5 %
is the infinite-sheet pitch ratio and no real page reaches it, because the
honeycomb hands back 2·`hxew` = 5.0 mm of width and 2·`hxeh` = 2.9 mm of height.

The two user-facing strings are already right (`layout_options_panel.py:130`
says 8 %; `tab_chart.py:11835` says ~8 % and quotes a real 532/576 render).
Only the code comment is wrong — and the SpectroScan's own Guided label
(`tab_chart.py:11870`, *"packs ~15% more per sheet"*) against its tooltip's
*"roughly 14%"* has the same disease.

### 3.6 MINOR — an old `CR30|A4|spot` preset becomes unreachable

`LayoutRecipe.mode()` changed from `"spot"` to `"flat"/"hex"`, so
`preset_key()` moved from `CR30|A4|spot` to `CR30|A4|flat`.
`PresetStore.get` (`presets.py:471-475`) does a plain dict lookup and falls back
to `default_recipe` on a miss — no migration. Demonstrated:

```
saved under CR30|A4|spot; get("CR30","A4","flat") -> patch_w_mm = 0.0
```

i.e. the saved preset is silently gone. Graded MINOR only because the CR30 has
never shipped in a beta and no test or on-disk preset in this repo pins the old
key (checked with a fixed-string grep). If any tester's
`chromiq-layout-presets.json` has been written during on-screen driving, it
needs a one-line rename `CR30|<paper>|spot` → `CR30|<paper>|flat` in
`PresetStore.from_dict`.

### 3.7 MINOR — the "Double density" checkbox carries state across a meaning change

In Guided, one `_dd_check` means "Double density" on CM, "Hexagon patches" on SS
and now on CR30 (`tab_chart.py:11807-11890`), and its state is persisted as
`chart_double_density` (`tab_chart.py:17812`). It is force-unchecked only when
*hidden* (`:11888-11891`), so CM-with-double-density → CR30 arrives with
**hexagons silently on**. Pre-existing between CM and SS; the CR30 inherits it.

### 3.8 MINOR — a stale comment, and a red test on the branch

* `ui/tiff_preview.py:1496-1499` (`set_no_swipe`) still says *"which a CR30
  chart's square patches must not get"* — no longer true now that a CR30 chart
  can be a honeycomb. The **code** is correct (`set_hex_zigzag` is driven by
  `chart_is_hexagonal`, which now includes CR30); only the comment misleads.
  `tab_measure.py:4191-4193` carries the same stale sentence.
* `tests/test_target_instrument_gate.py::test_an_unknown_instrument_name_is_fatal_for_our_fork[CR30]`
  **fails** at `22f005aa`. It expects `Unrecognised chart target instrument` and
  gets the newer, better `The chart was made for 'CR30', which ChromIQ reads
  itself.` Not caused by either decision under review (it belongs with the
  earlier target-instrument work), but the branch gate is red and a release
  decision needs a green `--runslow`.

### 3.9 What a CR30 user would expect that neither decision covers

1. **A time estimate on the page, not only in a tooltip.** The Guided and Manual
   tooltips warn that A4 holds ~500 patches; at the ~1 s/reading figure in
   `chromiq-cr30-research/INTEGRATION.md:277-279` that is a ~9-minute unbroken
   sitting. No other instrument needs this because no other instrument is a
   hand press per patch. The patch-count readout in Create Chart could carry
   the minutes beside it for a CR30.
2. **Nothing warns that patch size is the one unmeasured variable.** The
   tooltips say it well; the *chart* does not. A CR30 sheet built at a
   below-default patch size is the one case the research repo explicitly calls
   blocking (`MEASUREMENT.md:483-489`). Whatever the margin inspector does for
   thresholds today, a CR30-specific floor is not expressible.
3. **Consistency:** everything else about the CR30 follows the SpectroScan's
   mental model (same "Patch shape:" label, same flat/hex vocabulary, same
   preset-key shape). That is right and should be preserved — which is the
   consistency argument in §1.5 against defaulting the two differently.

---

## Findings, ranked

### BLOCKER

1. **The renderer draws squares for a CR30 hexagonal chart.**
   `workflow/layout_engine/raster.py:1056` — `ss_hex` is gated on
   `key == "SS"`. Proven by render at commit `22f005aa`. The user gets
   10.000 × 8.660 mm rectangles on a page that has already surrendered 5.0 mm of
   width and 2.9 mm of height to apex/stagger reservation. §1.1
2. **The recorded patch rects carry no stagger for a CR30.**
   `workflow/layout_engine/geometry.py:475`. Measured: `patch_rects_px` returns
   one distinct x per column. Latent today (the raster does not stagger either);
   **fixing 1 without 2 makes it a live half-patch mis-registration** in the
   Measure-tab highlight, the margin inspector and `workflow/scanin_target.py`.
   Must be fixed in the same change as 1. §1.2
3. **Helper markers are not suppressed on a CR30 honeycomb.**
   `workflow/layout_engine/geometry.py:669`, `ui/tabs/tab_chart.py:16175`
   and `:16180`. This is #152 reproduced verbatim for a new instrument. §1.3

### SERIOUS

4. **"Spacer size" is enabled but inert whenever spacers are off**, and the CR30
   is the first instrument to ship with them off by default, so it is the first
   where a user meets the dead control out of the box — on the very setting the
   ruling says must be changeable. `ui/dialogs/layout_options_panel.py:2898`
   greys only the swatches. §2.3
5. **Hexagons should not be the CR30 default.** A honeycomb silently disables
   the scanner/camera tools (Beta opt-in required) and the ruler helper markers,
   to buy ~45 s on a ~9-minute A4 sheet, and would make the CR30 and the
   SpectroScan default differently under an identical control and label. §1.5
6. **An unmeasured ergonomic claim ships as fact** in the Guided tooltip
   (`ui/tabs/tab_chart.py:11848-11850`, "six sides funnel a round barrel…",
   "harder to lose your place"), in a dialog that is otherwise scrupulous about
   saying what has not been measured. §1.6
7. **The column coordinate zigzags by half a patch width (5.0 mm) on a
   honeycomb** while its letter sits on a straight line — on the instrument
   whose entire ergonomics rest on that coordinate. §1.7
8. **Manual resets a CR30 to i1Pro** — `ui/tabs/tab_chart.py:5235`. §3.3
9. **Preferences → Chart Layout opens on i1 for a CR30** —
   `ui/tabs/tab_chart.py:16790`. §3.4

### MINOR

10. The `~15 %` in the CR30 hex code comment is wrong; measured +8.8 % on A4
    portrait. The SS Guided label/tooltip disagree with each other too. §3.5
11. Flat-to-flat **10.200 mm gives the identical 558 patches with 3.3 % more
    aperture clearance** than the coded 10.000 mm on A4 portrait — free
    headroom, currently unclaimed. §3.1
12. An old `CR30|A4|spot` preset is unreachable after the mode-key change; no
    migration in `PresetStore.from_dict`. §3.6
13. The shared "Double density"/"Hexagon patches" checkbox carries state across
    a meaning change, so CM→CR30 can arrive with hexagons silently on. §3.7
14. Stale comments at `ui/tiff_preview.py:1496-1499` and
    `ui/tabs/tab_measure.py:4191-4193` ("a CR30 chart's square patches"). §3.8
15. `tests/test_target_instrument_gate.py::…[CR30]` fails at `22f005aa`
    (unrelated to these decisions, but the branch gate is red). §3.8
16. **The SpectroScan's "Spacer size" box has never worked** — its geometry
    hard-codes `pspa=0.0`. Pre-existing; found while verifying that the CR30
    avoided the same trap. §2.2

---

## What I attacked and could not break

* **`recipe_is_hexagonal` was widened correctly** (`workflow/hex_support.py:104`),
  and every consumer keyed off it follows for free — the margin inspector's apex
  correction, the scanin sample cap, the measure overlay, the legacy-sidecar
  compensation. §1.8
* **The Measure tab highlights a honeycomb patch as a hexagon**, both the
  next-to-read ring and the click-to-jump hover outline
  (`ui/tiff_preview.py:2635`, `:2660-2668`). Given fix 2, patch identification
  on screen is genuinely solved. §1.7
* **Nothing downstream rejects `HEXAGON_PATCHES`.** The helper parses it
  (`native/chartread_helper/chromiq_chartread.c:3819`) and uses it only inside
  the XY branch (`:1753-1786` under `rmode == 2` at `:1541`), which computes
  motorised navigation vectors and which a CR30 never enters — `check_mode`
  puts a spot instrument on `rmode = 0`. **This is the one place that truly
  assumes motorised positioning, and the CR30 correctly never reaches it.** §1.8
* **The spacer default is mechanically right.** Real 1.3 mm base in the
  geometry, off via `spacer_mode="none"` in `default_recipe`, fully turnable on
  with a live width box. Verified by running `instruments.build`. §2.1
* **"Always off in Guided" is expressible without a special case that leaks** —
  `workflow/chart_creator.py:1204` sits inside the CR30 arm and uses the
  existing `params.is_manual` discriminator. §2.4
* **Nothing breaks at `pspa == 0`** — every consumer guards zero, `.cht`
  generation has no spacer dependence, capacity and rendering both verified. §2.5
* **The equal-width hexagon is a deliberate, tested choice**, and the Guided
  tooltip describes it accurately (90.7 % vs 78.5 % packing, same clearance,
  532/576 patches — all three verified). §3.1

---

## Concrete changes

1. `workflow/layout_engine/raster.py:1056` — drop the instrument test:
   `ss_hex = getattr(geom, "hxew", 0.0) > 0`. Only a hexagonal geometry ever
   sets `hxew`. (Rename the local off `ss_` while you are there.)
2. `workflow/layout_engine/geometry.py:475` — the same edit, in the same commit
   as 1. Its comment already says it is mirroring the renderer's test, so the
   two must never diverge.
3. `workflow/layout_engine/geometry.py:669` — the same edit in
   `helper_marker_lines_mm`.
4. `ui/tabs/tab_chart.py:16168-16181` — make `_chart_is_hexagonal` delegate to
   `workflow.hex_support.recipe_is_hexagonal` instead of carrying a second copy
   of the instrument list. Two copies is how these sites drifted apart.
5. `ui/dialogs/layout_options_panel.py` — disable `spacer_width` and its
   label/tooltip row whenever `spacer_mode.currentData() == "none"`, from the
   handler already wired to `spacer_mode.currentIndexChanged` (`:673`). Benefits
   every instrument; required for the CR30 ruling to be legible.
6. `tests/test_hex_overlay_geometry.py` and the hex tests in
   `tests/test_layout_raster.py` (`:75-110`, `:510`, `:527`) — parametrise over
   `("SS", "CR30")`. This alone would have caught changes 1 and 2.
7. `ui/tabs/tab_chart.py:5235` and `:16790` — add `"CR30"` to both instrument
   tuples.
8. **Default:** leave `default_recipe("CR30", …)` at `hflag=False` /
   mode `"flat"`, matching the SpectroScan. Do not promote hexagons to the CR30
   default until the tolerance-envelope experiment
   (`chromiq-cr30-research/MEASUREMENT.md:483-489`) has been run.
9. `ui/tabs/tab_chart.py:11848-11850` — remove or hedge the "six sides funnel a
   round barrel" / "harder to lose your place" sentences. Everything else in
   that tooltip is accurate and should stay. If the honeycomb's effect on the
   column coordinate is worth a word, it is that **rows** stay straight and
   **columns** step half a patch left and right.
10. `workflow/layout_engine/instruments.py` — correct the CR30 hex comment from
    "roughly 15 %" to the measured "+8.8 % on A4 portrait, +12.5 % on A3"; and
    reconcile `tab_chart.py:11870` ("~15%") with its own tooltip ("roughly 14%")
    for the SpectroScan.
11. *(Optional, free)* Consider flat-to-flat **10.200 mm** for the CR30 hexagon:
    identical 558 patches on A4 portrait, 3.3 % more clearance around the 4 mm
    aperture. If taken, record it as a deliberate choice next to the existing
    equal-width assertion in `tests/test_cr30_registration.py:130-136`.
12. `ui/tiff_preview.py:1496-1499` and `ui/tabs/tab_measure.py:4191-4193` —
    update the "a CR30 chart's square patches" comments.
13. `workflow/layout_engine/presets.py`, `PresetStore.from_dict` — rename any
    `CR30|<paper>|spot` key to `CR30|<paper>|flat` on load, if any tester's
    preset file has one.
14. `tests/test_target_instrument_gate.py:89` — update the expectation to the
    new CR30 message so the branch gate can go green.

STATUS: complete

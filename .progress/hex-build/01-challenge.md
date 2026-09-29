# Two commits, challenged before they exist
2026-09-09. Adversarial round on **Commit A (pool the hexagon)** and
**Commit B (the rotation option)**. Everything below is measured against the
shipped tree at `478c7396` unless it says SUSPECTED.

Read alongside `.progress/hex-rotation/00-measured.md` (the owner's rulings) and
`.progress/hex-rotation/01-challenge.md` (H1..H17). Nothing settled there is
reopened here.

---

## P1 — CONFIRMED. It is FIVE copies, not four, and two of them are 50 lines apart in the same file.

The brief names four sites. Measured, the six vertices are written out **five**
times in shipped code, plus a sixth in a test:

| # | site | file:line | form |
|---|---|---|---|
| 1 | page renderer | `workflow/layout_engine/raster.py:1069-1087` `_hexagon_points` | six int tuples, applies its own ±¼·w stagger from `step` |
| 2 | Measure single-patch outline | `ui/tiff_preview.py:1747-1771` `_patch_hexagon` | `QPainterPath`, floats, stagger already baked into the `QRect` |
| 3 | **Measure strip outline** | `ui/tiff_preview.py:1710-1719` `_strip_zigzag_path.verts` | a *dict* of the same six vertices, floats — **the copy the brief does not list** |
| 4 | Measure hit test | `ui/tiff_preview.py:1491-1512` `_in_hexagon` | not vertices at all: two linear inequalities |
| 5 | scanner grid mesh | `ui/scan_grid_marquee.py:796-802` `_cell_uv` | six float tuples in unit-square space |
| (6) | test-local re-implementation | `tests/test_hex_sample_clamp.py:34` `_in_hexagon` | a seventh formula, in the suite |

**`vector_pdf.py` is NOT a copy.** `workflow/layout_engine/vector_pdf.py:185-193`
consumes the `("hex", pts, values)` rows that `raster.py:1481` already produced
from site 1. It has no vertices of its own and needs no change in Commit A.
The brief's "the vector-PDF path" is the wrong fourth site; the fourth site is
`_strip_zigzag_path` and the fifth is `scan_grid_marquee`.

Sites 2 and 3 are **byte-identical arithmetic written twice in one file**
(`left, right = b.left(), b.right() + 1`, `t6 = h / 6.0`, the same six
expressions). `_patch_hexagon`'s own docstring says it matches "the same
pointy-top/flat-side geometry the strip zigzag uses" — an English promise where
a shared function would have been a mechanical one. That pair alone justifies
Commit A.

## P2 — CONFIRMED, AND IT IS A NEGATIVE RESULT. The five copies AGREE today, to within raster's integer rounding. There is no latent bug here to harvest.

I swept w = 20..199 px, ph = 20..199 step 7, both stagger parities (2 × 180 × 26
= 9,360 hexagons) and compared every vertex of site 1 against sites 2/3/5, with
the ±¼·w stagger applied to the recorded rect exactly as
`geometry.patch_rects_px:546-549` applies it.

* sites 2, 3 and 5 are **identical to 1e-14** (5 and 2 differ only in writing
  `v + hh - t6` versus `y0 + 5 * t6`, a float-association artefact);
* site 1 differs from them by **at most 0.5 px, and only ever 0.5 px**, entirely
  from its own `round()` on each vertex. Worst case measured: w=20, ph=27,
  step 0, apex y = `-4` (raster, rounded) against `-4.5` (preview, exact).
* site 4 (`_in_hexagon`) is **algebraically exact** against sites 2/3: at
  `dx = 0` its `top` is `y - t6` (the apex) and at `dx = 1` it is `y + t6` (the
  shoulder), linear between — which is the same straight edge sites 2/3 draw.

And the stagger itself agrees: `raster.py:1478` calls
`_hexagon_points(x0, y0, xR - x0, yB - y0, j)` with
`x0 = px(place.x_of(p))`, `xR = px(place.x_of(p) + place.pwid)` (`:1316`,
`:1322`), and `geometry.py:547` computes `_dx` from `px(x_of(p)+pwid) -
px(x_of(p))` — the same two roundings, the same subtraction, the same `j`
parity, the same `round()`.

**So A1's most valuable possible answer is not available: they do not already
disagree.** That is worth stating plainly, because the honest justification for
Commit A is *"five copies each get a fresh chance to disagree when an
orientation is added"*, not *"there is a bug in there now"*. Do not write a
changelog line implying a fix.

## P3 — CONFIRMED. Pooling naively WILL change pixels, because one of the five deliberately does not round, and the reason is measured and written down.

`ui/tiff_preview.py:1720-1723`, in `_strip_zigzag_path`, immediately above the
transform:

> NOT rounded. Snapping the vertices looks like the fix for the uneven halo and
> is not: it measured worse (spread 0.14 -> 0.21 device px), and on a 7 mm
> hexagon — 18.5 logical px on screen — it moves each vertex by 2.7% of the
> patch, off the ink it is describing.

Site 1 rounds every vertex (Pillow's `polygon` needs ints). Sites 2/3/5 must
not. A pooled `hexagon_points(...)` that returns ints "because the renderer
needs them" silently reverts that measured finding on the Measure overlay, at
up to 0.5 image px, magnified by the preview zoom (at 8× that is 4 screen px of
halo). **Rounding must be a parameter of the pooled function, defaulting to
off, and the renderer must be the only caller that asks for it.**

Equally: the pooled function must NOT round `cx` independently of `left`/`right`
in the float path. Site 1 does (`cx = round(x0 + w/2 + dx)`) and is allowed to;
nobody else may inherit it.

## P4 — CONFIRMED. `workflow/hex_support.py` is the WRONG home, and the prior plan (H12/step 1) names it.

Measured import graph:

* `workflow/layout_engine/raster.py:16-33` imports only `core.stem_paths`,
  `core.logger`, `core.resource_path` and its own siblings. **No
  `workflow.*` import at all**, in either direction.
* `workflow/hex_support.py:36-42` imports `json`, `pathlib.Path`,
  `core.stem_paths`, **`core.i18n.tr`** and `core.text_io.read_text`, and its
  functions read files off disk (`chart_is_hexagonal` opens a `.channels.json`).
* Nothing under `workflow/layout_engine/` imports `hex_support` today (grep:
  every importer is `ui/*` plus `workflow/margin_inspector.py:283`).

Putting the pooled geometry there makes the page renderer depend on the
translation catalogue and on a file-reading module, and inverts a dependency
that is currently clean. It also drags the pooled function into `ui/` through
a module whose other exports are user-facing prose.

**The right home is a new dependency-free module,
`workflow/layout_engine/hexagon.py`** — pure arithmetic, `import math` at most,
no `core.*`, no Qt, no Pillow. Then:

* `raster.py` imports it as a sibling (`from . import hexagon`);
* `geometry.py:546-549` imports it for the `_dx` it currently inlines, which is
  the single most important consumer to pool because it is the one every
  downstream box (`.cht`, the overlay, `margin_inspector`) is derived from;
* `ui/tiff_preview.py` and `ui/scan_grid_marquee.py` import
  `workflow.layout_engine.hexagon` directly. **Check this cost:**
  `scan_grid_marquee` today does not import `layout_engine` at all, and
  `raster.py` pulls in `tifffile` + `PIL` + `numpy` — a bare `hexagon.py` with
  no package-level re-exports avoids paying that at marquee import time.
  Verify `workflow/layout_engine/__init__.py` does not eagerly import `raster`
  before wiring this up.

Do not put it in `geometry.py`: `geometry` imports `instruments`, and
`ui/scan_grid_marquee.py` importing `geometry` to draw a mesh cell is a wider
blast radius than it needs.

## P5 — CONFIRMED. Commit A will turn a test red on purpose, and one of them asserts on SOURCE TEXT.

Three tests reach into the copies. A pooling commit must be planned around
them, not surprised by them:

| test | file:line | what it does | effect of pooling |
|---|---|---|---|
| `test_the_drawn_cell_is_a_hexagon` | `tests/test_hex_scanner_support.py:90-96` | `inspect.getsource(ScanGridMarquee._cell_uv)`, then `assert "self._grid.hexagonal" in src` and `hex_block.count("(cxu,") == 2` | **goes RED the moment the vertices move out of `_cell_uv`.** `(cxu,` will not be in the source any more |
| `test_hexagon_points_shape_and_stagger` | `tests/test_layout_raster.py:510-524` | calls `raster._hexagon_points(...)` by name, checks the ±w/4 stagger | red if the private name is deleted; fine if `raster._hexagon_points` stays as a thin adapter |
| `test_the_first_hex_column_is_not_left_of_the_margin` | `tests/test_layout_raster.py:663` | calls `raster._hexagon_points` again | same |

Also `tests/test_a_hexagon_is_taller_than_its_row_pitch.py:18` states in its own
docstring that it exists so *"a change to `_hexagon_points` that leaves
`HEX_HEIGHT_FACTOR` alone still turns this red"* — it measures the drawn ink,
so it is the good kind of guard and will not move.

**Decision Commit A must make explicitly:** keep `raster._hexagon_points` as a
one-line delegate (two tests keep working, the pooling is still real), and
rewrite `test_the_drawn_cell_is_a_hexagon` to assert on the returned array
rather than on source text. Rewriting a source-text assertion into a behavioural
one is a strict improvement and belongs in Commit A, not left for Commit B.

## P6 — CONFIRMED. There is NO golden-page test in the suite, so "nothing visible changed" is not currently provable by anything that exists.

`grep -l render_pages tests` returns 12 files; none of them hashes or stores a
reference page. Every one asserts on a property (ink present, a row label
matches, a margin is respected), so **all twelve would stay green through a
half-pixel drift in the hexagon**, and eleven would stay green through a
quarter-patch one.

Measured, so the cost of fixing that is known: rendering a **400-patch A4 CR30
honeycomb at 300 dpi takes 0.04-0.05 s and is bit-deterministic** across
repeated calls in one process (sha256 of `np.asarray(images[0]).tobytes()`
identical, CR30 2 pages and SS 1 page).

### The concrete before/after test A3 asks for

Two things, and they answer different questions:

1. **An ephemeral proof, run once, kept out of the suite.** A throwaway script
   that renders a matrix — `{CR30, SS} × {hflag on} × {300, 600 dpi} × {A4
   portrait, A4 landscape, 100×150 roll} × {spacers none, spacers on} ×
   {row indicators on/off}` — and prints a sha256 per page. Run it on
   `478c7396`, run it on the pooled tree, `diff` the two manifests. **It must
   compare rendered page BYTES, not geometry rows**, because the geometry rows
   are not what Commit A changes: `raster._hexagon_points` is the only caller
   whose output reaches pixels, and a rounding regression there shows up in
   pixels and nowhere else. Roughly 24 pages, about 1.5 s a run. This is the
   only artefact that can catch P3's rounding hazard.
2. **A permanent equivalence test in the suite,
   `tests/test_the_hexagon_is_drawn_from_one_place.py`.** It must compare **the
   geometry rows**, because that is what stays true forever:
   * over a sweep of `(w, ph, step)`, the pooled function's *unrounded* output
     equals `_patch_hexagon`'s path elements, `_strip_zigzag_path.verts`'s six
     values and `_cell_uv`'s six points, to 1e-9;
   * the pooled function's *rounded* output equals what `raster` paints;
   * every vertex of the rounded output is within 0.5 px of the unrounded one
     (the pin on P3: nobody may quietly widen that);
   * `_in_hexagon(b, x, y)` agrees with a point-in-polygon test of the pooled
     polygon on a grid of sample points inside and outside each box.

**Byte-for-byte alone is not enough and geometry rows alone are not enough.**
Bytes cannot pin the Qt paths (they never reach a rendered page in the suite);
rows cannot see a rounding change that only manifests as ink.

**Name the tests that would NOT catch a regression here, because it is a long
list:** every test in `tests/test_layout_raster.py` except the two that call
`_hexagon_points` by name; `test_hex_overlay_geometry.py` (it asserts the centre
is inside and the corners are outside, which a 0.5 px drift cannot break);
`test_hex_strip_overlay.py` (asserts the path is non-None and has the right
element count); `test_marquee_geometry_cache.py` (asserts the cache identity,
not the values); `tests/test_cr30_builtin_presets.py` (patch count, page count,
shape — all survive a half pixel).

## P7 — CONFIRMED. `GEOM_BUILD_KEYS` is guarded by NOTHING.

```
$ grep -rn GEOM_BUILD_KEYS --include=*.py .   (excluding .venv)
workflow/layout_engine/instruments.py:397   the definition
workflow/layout_engine/instruments.py:456   the one use
```

**Zero test references.** The tuple whose own comment says *"a missing key
silently makes capacity ESTIMATES disagree with the actual render
(clip_border_width once did exactly that)"* and *"This is the single source of
truth shared by every capacity calculation"* is pinned by no test at all. H10
identified it as the chokepoint; nobody checked whether the chokepoint is
defended. It is not.

Measured cross-check of what the tuple contains today:

* `build()` takes two keyword arguments that are **not** in the tuple —
  `margins_are_law` and `fill_beyond_ruler` — and that is correct, because
  `geom_from_build_kwargs:454-455` derives both explicitly from
  `layout_mode` / `use_instrument_margins` and passes them separately. Not a
  bug, but it means "every `build()` kwarg is in the tuple" is the WRONG shape
  for the test.
* `clip_band` is in the tuple and is **never emitted by
  `LayoutRecipe.build_kwargs()`**; it is injected by
  `geom_from_build_kwargs:426`. Harmless, and it means "every tuple entry is a
  recipe key" is also the wrong shape.

**The right shape, and it is a mutation test:** for each key `k` in
`build()`'s signature minus the two derived ones, build a `Geom` twice through
`geom_from_build_kwargs` with `k` at its default and at a non-default value; if
the two `Geom`s differ, `k` MUST be in `GEOM_BUILD_KEYS`. That is generated, it
cannot be forgotten, and it goes red for the rotation field the moment somebody
adds it to `build()` and not to the tuple. **It should land in Commit A**, not
Commit B: it is a guard on existing code, it can be proven to work today, and
Commit B then inherits it.

## P8 — CONFIRMED, AND THIS IS THE ONE THAT WOULD SHIP BROKEN. Ruling 2 (CR30 only) breaks H13's "inert by construction" guarantee for the SpectroScan, and it is exactly the `ca0f639c` shape.

H13 was written under ruling 6 (*"CR30 **or** SpectroScan"*). Basti's answer 2
supersedes it: **CR30 only**. H13's guarantee #2 was reasoned under the old
scope and does not survive the new one.

The precedent in the tree, `instruments.py:363-365`:

```python
row_stagger = 0.0
if key == "CM" and cm_stagger:            # ← an INSTRUMENT gate, not just a flag gate
    row_stagger = 0.5 * (plen + 0.5 * pspa)
```

`cm_stagger_cb` is visible only for `inst == "CM"`
(`layout_options_panel.py:2389-2391`) and its effect is gated on `key == "CM"`.
Two gates, matched. Now take them apart for the rotation:

* the control is visible only for **CR30 + honeycomb** (rulings 2 and 6);
* under H13.1 hiding must never untick, and there is deliberately no memory, so
  the recipe field stays `True`;
* the user switches the instrument to **SpectroScan** and leaves the honeycomb
  on. The box vanishes. The flag is still `True` in the recipe.

If `build()` gates the orientation on `hflag` / `hexagonal` alone — which is
what H13.2's whole argument rests on ("every place the orientation could act is
already behind the honeycomb gate") — **the SpectroScan chart silently builds
flat-top from a control the person can no longer see, cannot untick, and was
never offered.** That is `ca0f639c` restated: *"left ticked but disabled with no
gesture to recover, which still reached the build"*, with "hidden" for
"disabled".

**Required:** the gate in `build()` must be `if key == "CR30" and hflag and
flat_top`, mirroring `key == "CM" and cm_stagger` exactly. And `area_fit
.derive_area_patch_size:123` must gate the same way — it currently uses
`instruments.hex_capable(instrument)`, which is **True for the SpectroScan**, so
copying that predicate would flip the SS aspect ratio and draw a stretched
hexagon (ruling 3's forbidden case) on an instrument that never showed the box.

**And the design that makes this un-get-wrong:** put the orientation on the
`Geom` (`hex_flat_top: bool`, defaulting False) and set it **only inside the
CR30 `hflag` branch of `_build_base` / `build`**. Every downstream consumer then
reads `geom.hex_flat_top`, never the recipe. One gate, one writer, and no site
in H12's nineteen can disagree with `build()` about which orientation it is —
which is precisely the property `instruments.is_hexagonal`'s docstring was
written to give the shape.

## P9 — CONFIRMED, and quantified. H12 #19 is real, and it is a quarter of a patch on every patch of every flipped chart.

`ui/tabs/tab_measure.py:568` decides a sidecar is legacy by:

```python
legacy = any(len(xs) >= 2 and len(set(xs)) == 1 for xs in columns.values())
```

Measured on a real CR30 honeycomb (A4 portrait, 400 patches, 300 dpi):

* today, column "D" has `xs = [495, 567, 495, 567, ...]`, **2 distinct x**, so
  `legacy` is **False** across the whole page — the discriminator works;
* a FLIP-A chart has, by definition, one x per column. `legacy` becomes
  **True**, and every box is then shifted by
  `round(±w/4)` where the flipped `pwid` is `10.3923 mm` = **123 px** at 300 dpi,
  giving **±31 px on a 123 px patch**.

That is a quarter-patch mis-registration of the Measure highlight, the click
target and the patch-by-patch ring on **every patch of every flat-top chart**,
and it is the symptom Sebastian already reported once
(`tab_measure.py:539`: *"the highlight sat between two hexagons"*).

The fix must be a **positive** signal, as H17.4 says: the sidecar's recipe
already round-trips, so read the orientation off it and return early. Do not
make the heuristic cleverer. Note that a legacy sidecar predates the field, so
`recipe.get("hex_flat_top")` is absent → falsy → the heuristic still runs for
exactly the vintage it was written for.

## P10 — CONFIRMED. H12's list is incomplete: the reported patch WIDTH also becomes wrong, at three sites that have no hexagon branch at all.

`hex_support.py:105` states the rule that makes the reporting code correct
today: *"The WIDTH needs no correction: the hexagon's sides are flat and
vertical, so it is exactly as wide as its slot. Only the height was ever
wrong."* Under FLIP-A that sentence inverts — the height needs no correction and
the width does. So every site that reports the patch size has TWO faults, not
one, and the second is at a line with no `if hexagonal` to extend:

| site | file:line | today | flat-top |
|---|---|---|---|
| Manual layout estimate | `ui/tabs/tab_chart.py:17808-17811` — `patch_w=geom.pwid`, `patch_h=_ph` | `_ph = plen·4/3` (corrected), width raw | width must become `pwid·4/3`; height must become `plen` raw. **Both numbers wrong, in opposite directions**: width understated 25 %, height overstated 33 % |
| chart size from the sidecar | `ui/tabs/tab_chart.py:17895-17897` — `return (r0["w"]*25.4/dpi, ph, pitch)` | same | same |
| the recipe summary line | `ui/tabs/tab_chart.py:12520-12524` — `tr("patch {w:g}×{h:.2f} mm, row pitch {p:g} mm")` | width raw, height via `hex_patch_height_mm` | the *label* is wrong too: on a flat-top sheet the second number is a **column** pitch across the page, not a row pitch down a strip |

`margin_inspector.py:283-287` is the same inversion in geometry rather than
prose, and its comment states the premise explicitly: *"The hexagon's flat sides
span exactly the staggered slot, so no horizontal expansion is right."* Under
FLIP-A the horizontal expansion is the only one that IS right, and the
`y0 -= h/6` / `y1 += h/6` must become `x0 -= w/6` / `x1 += w/6`. Left alone, the
inspector understates left/right margins by `pwid/6` (1.73 mm at 12 mm) and
overstates top/bottom by the same, on the tool whose entire job is telling the
user whether the ink clears the paper edge.

**`HEX_HEIGHT_FACTOR` should not be renamed.** It is the right number
(`4/3`) on both orientations; only the axis it applies to changes. Renaming it
touches `chart_layout_info_panel.py:144,185,254`, `tab_chart.py:116-119` and a
test file name for no gain. What is needed is a second helper —
`hex_patch_width_mm(flat_to_flat_mm)` — and a single call site that decides which
axis is the long one from `geom.hex_flat_top`.

## P11 — CONFIRMED. The scanner path (B4), item by item.

1. **`workflow/scanin_runner.py:140-168 hex_max_sample_fraction`.** Measured by
   calling the shipped function on the real CR30 honeycomb (`pwid` 12.000,
   `plen` 10.392):
   * today, `f(12.000, 10.392)` = **0.644338** — correct;
   * FLIP-A presents the transposed slot, `f(10.392, 12.000)` = **0.635134**;
   * the true flat-top limit is the pointy formula with the axes swapped, i.e.
     **0.644338** again (the hexagon is congruent, only turned).

   So the shipped function is **conservative by 0.92 percentage points**, which
   the UI floors to an integer anyway (`int(frac*100)`): **63 % instead of
   64 %**. Safe, and it costs the user one percentage point of sample area. It
   is safe *only* because FLIP-A always presents `w < h` and the pointy formula
   errs downward in that direction; it is not safe by design. Make it
   orientation-aware (swap the roles of `w` and `h` when the chart is flat-top),
   or say in the docstring why it was left.

2. **`hex_two_heights_note()`, `workflow/hex_support.py:109-131.`** Ships in
   twelve catalogues and says *"it is a third taller: set 9.78 mm and you get a
   patch 13.05 mm from tip to tip, taller than it is wide."* On a flat-top sheet
   every clause of that is false: it is a third **wider**, and it is **wider
   than it is tall**. Per the function's own docstring (*"both are long,
   shipped, and translated into twelve languages, and retiring their keys
   mid-beta to add a paragraph is not a trade worth making"*), the flat-top text
   must be a **NEW key chosen at runtime**, not an edit. Two consumers:
   `ui/chart_layout_info_panel.py:144` and
   `ui/dialogs/layout_options_panel.py:979`.

3. **`hex_patch_height_mm()`, `hex_support.py:134-142`.** Returns
   `row_pitch × 4/3`. Correct for pointy-top, wrong for flat-top, and its
   docstring's rule (*"Report only, never geometry"*) is worth preserving: add
   `hex_patch_width_mm` beside it rather than giving this one a flag, so
   nothing that already calls it can silently change meaning.

4. **`tests/test_a_hexagon_is_taller_than_its_row_pitch.py`.** The assumption is
   in the file name, the module docstring and the assertions. It renders and
   measures real ink, which is the right kind of test — so **extend it, do not
   rename it**: keep the pointy case exactly as it is (it is a regression guard
   on shipped behaviour) and add a flat-top case that measures a hexagon
   **wider** than its column pitch by the same 4/3.

5. **What else is in the scanner path, and the answer is: three more strings and
   nothing structural.**
   * `ui/dialogs/scanin_dialog.py:4319-4346 _clamp_sample_area` reads `w`/`h`
     off the recorded rects and hands them to `hex_max_sample_fraction`, so it
     follows item 1 automatically — but its tooltip says the square *"reaches
     past the hexagon's **slanted sides**"*, and on a flat-top hexagon the sides
     are the flat parts and the slants are at the ends.
   * `ui/dialogs/scanin_dialog.py:2439` — *"inside a hexagon, whose sides slant
     away **above and below**"*. Same inversion.
   * `ui/dialogs/scanin_target_dialog.py:382` — *"the sampling square, which
     escapes the hexagon above a Sample area of about 64 %"*. Still true (the
     cap is unchanged by the turn); no change needed. Worth stating so nobody
     "fixes" it.
   * `workflow/scanin_target.py` and `cht_writer.boxes_from_patch_rects` derive
     everything from `geometry.patch_rects_px`. **No change**, and that is the
     payoff of doing the recorded-rects change once and correctly.
   * `workflow/scanin_runner.sample_margin` is symmetric in `w` and `h`
     (`span = w+h`, `disc = span² - 4(1-f)wh`), so the read box itself is
     orientation-independent. **No change.**
   * `tests/test_hex_sample_clamp.py:34` carries its own pointy `_in_hexagon`.
     It tests the clamp, not the chart, so it can stay — but it is a seventh
     copy of the shape and should be pointed at the pooled function by Commit A.

## P12 — CONFIRMED. B5, the Measure overlay: what reads patch geometry, what breaks, and the on-screen proof harness ALREADY EXISTS.

Everything the Measure tab draws over a honeycomb hangs off one switch,
`ui/tabs/tab_measure.py:4729`:

```python
self._preview.set_hex_zigzag(chart_is_hexagonal(self._ti1_path))
```

which turns on four behaviours in `ui/tiff_preview.py`, every one of them
pointy-top:

| what | file:line | flat-top verdict |
|---|---|---|
| per-patch outline in "Show only measured patches" | `_patch_hexagon` `:1747`, used at `:2730`, `:2773`, `:3073` | draws a pointy hexagon over flat-top ink — a wrong shape on every unread patch |
| the expected-vs-measured split clip | `:2988` `_hex = self._patch_hexagon(...)` | the diagonal is clipped to the wrong hexagon |
| the strip highlight | `_strip_zigzag_path` `:1695` | traces a zigzag the sheet no longer has. **A flat-top strip is a plain rectangle** grown by `pwid/6` at each side for the apexes — so this is not "flip the vertices", it is a different outline |
| the click / hover hit test | `_in_hexagon` `:1491`, `_patch_at` `:1478-1487` | a click on a drawn apex selects the neighbour, which is the exact fault `_in_hexagon`'s docstring was written to remove (7.2-7.7 % of click area) |

Two things that do **not** break, measured rather than assumed:

* `_hover_patch_bounds` `:1772` and `_strip_patches` `:1685` select a strip's
  patches by **centre-x inside the strip rect**, deliberately never by y. On a
  flat-top sheet every centre-x in a column is identical, so this gets *more*
  reliable, not less.
* `geometry.strip_rects_px:463-478` already applies `row_stagger_mm` with the
  same parity test as the two other places, so a vertically-staggered strip
  rect lands on its own patches — provided the flip is expressed through
  `row_stagger_mm` (see P14).

And `_apply_hex_stagger` mis-registers every box by a quarter patch — P9.

### How to prove it on screen

**`scripts/drive_hex_overlay.py` already does exactly this job** and needs one
new argument. It builds a hexagonal chart into a throwaway project, opens it in
Measure, and grabs the preview three ways: plain, with the patch-by-patch
highlight on a known patch, and zoomed on that patch (`:131`, `:151`, `:158`).
It sandboxes Basti's preferences into a throwaway `.ini` (`:56-60`), which
satisfies the CLAUDE.md rule.

So B5's proof is: run it twice on the same tree, once flat-top and once not,
and **look at the zoomed shots** — the highlight ring either hugs the hexagon it
names or it sits a quarter patch off, and at the zoom level that script uses
that is not a subtle difference. The script's own header records the precedent
for judging it (`:103`, *"until the before/after screenshots came out
byte-identical"*).

Add to the driver, because a picture of a correct highlight does not prove the
click: click the CENTRE of a known patch and the four CORNERS of its recorded
box, and assert the centre selects it and the corners do not. That is the
assertion `_in_hexagon` exists for, and it is currently only made in an
offscreen unit test (`tests/test_hex_overlay_geometry.py:237-247`) against a
synthetic `QRect`, never against a real chart.

## P13 — CONFIRMED. B1: the field's home, and the two guards that already exist for free.

**Name.** `hex_flat_top: bool = False` on `LayoutRecipe`
(`workflow/layout_engine/presets.py:36`, beside `cm_stagger`). Not
`hex_rotation`, not `rotate_hexagons`: `indicator_rotation`,
`clip_image_rotation` and `clip_flip_180` already exist and all carry degrees or
a flip, so a boolean called "rotation" reads like a third of those. `flat_top`
names the state, which is what the recorded geometry, the renderer and the
overlay each need to ask about.

**Where it must go, verified against the current tree** (H14's line numbers have
drifted; the panel's load/save are now `:4451` and `:4630`, not `:4425`/`:4604`):

| # | place | file:line | note |
|---|---|---|---|
| 1 | dataclass field | `presets.py:36` | beside `cm_stagger` |
| 2 | `from_dict` | `presets.py:264` | `bool(d.get("hex_flat_top", False))` — an old recipe loads OFF |
| 3 | `to_dict` | `presets.py:382` | |
| 4 | `build_kwargs()` | `presets.py`, the block containing `"cm_stagger": self.cm_stagger` | |
| 5 | `build()` signature | `instruments.py:287` area | |
| 6 | `GEOM_BUILD_KEYS` | `instruments.py:397-404` | **the line H10 identified, and P7 shows nothing guards it** |
| 7 | the `Geom` field | `instruments.py:156` area, beside `row_stagger_mm` | P8: the ONE writer everything downstream reads |
| 8 | `chart.build_chart` kwarg | `workflow/layout_engine/chart.py:101`, `:215` | the non-UI entry point |
| 9 | the checkbox | `ui/dialogs/layout_options_panel.py:928-945` pattern | one widget serves Manual (`tab_chart.py:4978`), the relayout dialog (`ti2_relayout_dialog.py:5163`) and Preferences (`settings_dialog.py:5195`) — all three verified present at those lines |
| 10 | visibility | `layout_options_panel.py:2389-2391` + `:3210-3229` | **see the correction below** |
| 11 | load into the widget | `layout_options_panel.py:4451` | |
| 12 | read out of the widget | `layout_options_panel.py:4630` | |

**Two existing guards fire for free, and they are worth knowing about before
the field is added:**

* `tests/test_the_full_recipe_really_is_full` (`tests/test_layout_presets.py:100-125`)
  enumerates `fields(LayoutRecipe)` and asserts every one appears as
  `name=` in the round-trip sample's source. **Adding `hex_flat_top` turns it
  RED immediately** until it is added to the sample at `:87`, which then makes
  `test_all_fields_persist_through_named_dict` prove the preset-store round
  trip. B1 needs no new round-trip test: two good ones already exist and will
  demand to be fed.
* `LayoutRecipe(**{k: v for k, v in recipe.items() if k in valid})` is the
  loading idiom in **five** places (`tab_measure.py:516-521`,
  `margin_inspector.py:259-262`, `layout_options_panel.py:2860`,
  `settings_dialog.py:5798`, `tab_chart.py:15266`), all generated from
  `fields(LayoutRecipe)`. So a sidecar written before the field exists loads
  cleanly, and one written after reaches every consumer. No hand-written list
  to update.

**§4c, checked rather than remembered** (`docs/design/per_target_settings.md`,
the "Confirmed behaviour — an instrument default is not an override" table,
confirmed by Basti 2026-09-02):

* **D-1** an instrument default may set a value nobody chose — satisfied: the
  CR30 default recipe may carry `hex_flat_top=False`.
* **D-2** it may not overwrite a chosen value — satisfied **only** by having no
  second writer. Riding inside the recipe is what gives this for free.
* **D-3 / D-4** the app's own starting point (`default_recipe`, saved defaults,
  `manual_engine_recipe`) is **not an answer** — so "saveable as a default"
  must mean *saved inside the default recipe*, and H17.2 is right: **a separate
  `AppSettings` key would be a second writer and would rebuild `d1adbe31`.**

§S1.1 (`per_target_settings.md:95`) requires the per-target list to be
**generated, never hand-written**. Riding `LayoutRecipe` satisfies it: the list
is `fields(LayoutRecipe)`. **Nothing in that document forbids a new per-target
field.** So B1 has no binding blocker — but it has a binding *shape*, and the
shape is "one writer, inside the recipe, nowhere else".

**The correction to H14 item 9.** H14 says gate visibility on
`_area_is_hexagonal()`. Measured, `_area_is_hexagonal` (`:3210-3229`) ends with
`bool(hexed and instruments.hex_capable(str(inst)))`, and `hex_capable` is
**True for the SpectroScan**. Under Basti's answer 2 (CR30 only) that predicate
shows the box on a SpectroScan honeycomb. The gate must be
`self._area_is_hexagonal() and inst == "CR30"`, and the same explicit `CR30`
test must appear in `build()` (P8) and in `area_fit.derive_area_patch_size`.
Three gates, all naming the instrument, or the box appears where it was ruled
out and acts where it was never shown.

## P14 — CONFIRMED. `row_stagger_mm` is NOT reusable as-is, and reusing it carelessly destroys the apex reserve.

H12 item 6 says the vertical half-pitch offset *"is exactly the existing
ColorMunki `row_stagger_mm` mechanism"* and is *"reusable as is if the flip is
expressed as `row_stagger_mm = plen/2`"*. Two measured problems with that.

**1. It is hard-gated on the ColorMunki and it clobbers `hxeh`.**
`instruments.py:362-365`:

```python
row_stagger = 0.0
if key == "CM" and cm_stagger:
    row_stagger = 0.5 * (plen + 0.5 * pspa)
    hxeh = 0.25 * plen          # ← overwrites the honeycomb's apex reserve
```

A CR30 honeycomb sets `hxeh = plen/6` at `:729`. If a flat-top branch is added
to this block in the obvious way, `hxeh` is rewritten to `0.25·plen` and the
apex reserve is gone. On flat-top that happens to be *arithmetically*
acceptable — the vertical reserve is now the stagger, and the apex reserve
moves to `hxew = pwid/6` — but only because two unrelated quantities happen to
share a variable. **Write it explicitly**, with the flat-top branch setting both
`hxeh` and `hxew` itself, rather than falling through the CM block.

Measured today, so the two meanings are on the record: CR30 honeycomb
`hxeh = 1.7321` (`= plen/6`, the **apex** overhang) and `hxew = 3.0000`
(`= pwid/4`, the **stagger** overhang). They are not the same kind of number,
and the flip swaps *which kind sits on which axis*, not just the values.

**2. The pointy stagger is symmetric, `row_stagger_mm` is one-sided.**
The `±w/4` zigzag is symmetric about the slot, total span `w/2`, and the
geometry reserves it as `2·hxew` on both edges (`geometry.py:155`). The
ColorMunki stagger shifts odd strips **down only** by the full amount, and
`geometry.py:278` reflects that with a special case:

```python
_hex_shift = g.hxeh if g.row_stagger_mm <= 0 else 0.0
```

so **the moment `row_stagger_mm` becomes non-zero, the apex-clearance shift is
switched off**, with the comment *"its overhang is downward-only and already
absorbed below"*. That comment is true of the ColorMunki and false of a flat-top
honeycomb, whose apexes stick out sideways and whose stagger is downward-only:
the *horizontal* clearance must now come from `hxew`, and `x0` already adds
`g.hxew` at `:325`, so the flat-top case wants `_hex_shift = 0` **and** a
non-zero `hxew` — which is what the line gives, by accident, from a premise
about a different instrument. Write the intent down or the next person will
"fix" it.

**Consequence for capacity:** because the reserve is `2·hxeh` along the strip
(`geometry.py:83`, `:90`) and `2·hxew` across (`:155`), the flip does not merely
transpose the page: it transposes the *reserves* too, and that is why the
patch count moves at all. Basti's ruling 2 requires this to be **measured on
real builds and reported**, before and after, and answer 1 (the option's own
5.0 mm right margin) has to be re-measured against whatever the reserves
actually come out as — not carried over from H8's numbers, which were computed
for a different `hxeh`/`hxew` split.

## P15 — CONFIRMED. B3: every capacity readout, re-verified at today's line numbers.

`GEOM_BUILD_KEYS` is used in exactly one place (`instruments.py:456`), inside
`geom_from_build_kwargs`, and all of these call that function — verified by
reading the cited lines, not by trusting H10:

| readout | file:line | verified |
|---|---|---|
| Manual "Calculated Patches" group | `ui/tabs/tab_chart.py:4140` | ✔ `count_grp = QGroupBox(tr("Calculated Patches"), inner)` |
| the engine capacity behind Auto patch count / pages | `ui/tabs/tab_chart.py:12442` | ✔ `return instruments.geom_from_build_kwargs(kw, thresholds=None)` |
| the layout estimate + page-count line | `ui/tabs/tab_chart.py:17795-17811` | ✔ (H14 cited `:17766`, a comment — the code is 30 lines down) |
| the from-profile-gamut capacity hint | `ui/dialogs/ti2_relayout_dialog.py:3067` | ✔ |
| Preferences → Chart Layout preview | `ui/dialogs/settings_dialog.py:5702` | ✔ |
| the Measure tab's geometry | `ui/tabs/tab_measure.py:521` | ✔ |
| margin inspector | `workflow/margin_inspector.py:259-264` | ✔ |

**Two sites do NOT go through the tuple:**

1. `area_fit.derive_area_patch_size:123` — `ratio = math.sqrt(3)/2.0`, called
   from inside `geom_from_build_kwargs:436` **before** `build()`. Must become
   `2/sqrt(3)` for a flat-top CR30, and must be gated on the instrument (P8),
   not on `hex_capable`.
2. `raster.apply_furniture_reserves(geom, kw)` — called at
   `geom_from_build_kwargs:458` with the raw `kw`, not the filtered one. It
   reserves the label band and bottom sheet text. Nothing orientation-dependent
   there today, but `raster.py:1389` `_protrude = (strip_w // 4) if ss_hex else 0`
   — the row-label protrusion allowance — **is** pointy-top's `±w/4` stagger.
   See P18: the correct flat-top value is `pwid // 6`, not `plen // 4`. It is
   not a capacity number, so it will not show up in any readout; it will show up
   as row labels with hexagons drawn over them.

**And the guard that must exist**: P7's generated mutation test on
`GEOM_BUILD_KEYS`. Without it, item 6 of P13's table is a line somebody can
forget, and H10's whole "no readout goes stale by accident" claim rests on
nobody forgetting it.

## P16 — CONFIRMED. B2: the four guarantees, each with the mechanism and the exact existing test shape to copy. And the answer to B6.

I read all four commits. The single most useful thing in them is not any of the
four fixes: it is `ff3d1b2b`'s closing line — **"NOTHING CAUGHT IT. The
review's mutation, memory always wins, passed the whole gate: 11980 passed,
exit 0. The hole was that every test asserted on the widget."** Every test
below therefore asserts on what reaches the **build or the stored recipe**, and
the widget is checked only where the guarantee is about the widget.

The sibling file `tests/test_the_density_tick_belongs_to_one_instrument.py`
already contains every shape needed. Its helpers are
`pick_instrument_as_a_person` (`:59`), `app_sets_instrument` (`:74`) and
`is_hidden` (`:80` — *"`isHidden()`, NOT `isVisible()`"*).

| # | guarantee | mechanism | test, and the shape to copy |
|---|---|---|---|
| 1 | hiding must not clear it | `setVisible(...)` and nothing else, exactly as `cm_stagger_cb` (`layout_options_panel.py:2389-2391`). **No per-instrument memory dict** — three of the four 2026-09-08 faults were caused by the memory, not the hiding | `test_a_control_the_other_instrument_hides_keeps_its_value` (`:259`), asserting on `get_recipe().hex_flat_top`, not on `isChecked()` |
| 2 | inert while hidden | `Geom.hex_flat_top` is written **only** inside `build()`'s `key == "CR30" and hflag` branch; every one of H12's nineteen sites reads `geom.hex_flat_top`, never the recipe. This is the only mechanism that survives ruling 2 — see P8 | `test_a_hidden_triple_density_cannot_reach_the_chart` (`:281`). Generated form: over every instrument key and both `hflag` values, `build(k, hflag=h, hex_flat_top=True)` must equal `build(k, hflag=h)` field-for-field **except** for CR30 with `hflag=True` |
| 3 | a run's stored value survives a load | one writer, inside `LayoutRecipe`. **No `AppSettings` key.** `d1adbe31`'s rule — a PRESENT recipe loses to the guided row, an ABSENT one resets after it — is inherited automatically, and only because the value rides in the recipe | `test_a_runs_stored_answer_survives_the_app_seeding_the_instrument` (`:194`), plus `tests/test_a_fresh_run_opens_on_its_own_defaults.py` for the absent-recipe half |
| 4 | never ticked-and-disabled | hidden or shown, **never** `setEnabled(False)`. Combined with #2 there is no reachable state that is set and un-unsettable | `test_no_density_box_is_ever_ticked_and_unclickable` (`:353`), which is already `@parametrize`d over routes |

### B6 — the smallest set that would have caught each of the four faults

Four tests. Not one of them is new in shape; all four are the sibling file's,
re-aimed at the recipe.

1. **`ff3d1b2b` (a memory restored on an app-driven instrument change).**
   `app_sets_instrument` CR30 → i1 → CR30 and assert
   `get_recipe().hex_flat_top` is unchanged in both directions. Copy of `:223`.
   *This feature has no memory, so the test is really a guard against somebody
   adding one later* — which is exactly why it must exist before the control
   does.
2. **`ca0f639c` (a hidden control reached the build through a neighbour).**
   Set `hex_flat_top=True` on a CR30 honeycomb, switch to a **SpectroScan**
   honeycomb, and assert the built `Geom` and the rendered page are identical to
   `hex_flat_top=False`. **This one is not hypothetical — P8 shows it is what
   the obvious implementation does.** Copy of `:281`.
3. **`e1aeaf2f` (`setChecked(False)` on an already-false box emits nothing).**
   The round trip in test 1 run in **both** directions — set True, round trip,
   assert True; set False, round trip, assert False. The second direction is the
   one an emit-dependent implementation drops.
4. **`d1adbe31` (a saved default overwrote a run's stored answer).**
   A stored run recipe with `hex_flat_top=True` loaded while the saved global
   `manual_engine_recipe` has it False: the run's value must win, and Manual and
   the panel must agree afterwards. Copy of `:194` and of
   `test_a_run_reopens_on_its_own_instrument.py`, the file `d1adbe31` added.

**A test in this set only counts if the mutation is proven to land.** All four
commits say so in their own messages; `ff3d1b2b`'s mutation passed 11,980 tests
green. So each of the four must be run once against a deliberately broken
implementation and shown red, and that must be recorded in the commit message.

## P17 — SUSPECTED. The honeycomb choice itself is silently lost on an instrument round trip, in the panel.

Not caused by either commit, and it will be blamed on Commit B when it is
noticed. `_on_instr_changed` (`layout_options_panel.py:2419-2423`) rebuilds the
shape combo and falls back to index 0 when the previous key is not offered:

```python
prev_mode = self.mode.currentData()
self.mode.clear()
for k, lbl in self.modes_for(inst):
    self.mode.addItem(lbl, k)
j = self.mode.findData(prev_mode)
self.mode.setCurrentIndex(j if j >= 0 else 0)
```

`modes_for("CR30")` is `[("flat", …), ("hex", …)]` (`:269-270`), so index 0 is
**Rectangular**. `modes_for("i1")` is `[("clip", …), ("noclip", …)]`, which
contains no `hex`. So CR30 + Hexagonal → i1Pro → CR30 leaves the panel on
**Rectangular**, and the honeycomb the person chose is gone with no memory and
no gesture that says so.

The rotation box then correctly hides (its parent is off) and correctly keeps
its value (H13.1) — so Commit B behaves — but the user's report will be *"I
turned the rotation on and it disappeared"*. Worth confirming and reporting
separately; do not fold it into either commit.

---

# THE IMPLEMENTATION ORDER

## COMMIT A — pool the hexagon. Nothing visible changes.

1. **`workflow/layout_engine/hexagon.py`, new, dependency-free** (P4). No
   `core.*`, no Qt, no Pillow, no `workflow.*`. One function:

   ```python
   def hexagon_points(x0, y0, w, h, *, step=None, flat_top=False, snap=False)
   ```

   * `step=None` → no stagger (the caller's rect already carries it: the three
     Qt/marquee callers and `geometry`'s own recorded rect);
   * `step=int` → `dx = round(-w/4) if step % 2 == 0 else round(w/4)`, byte-identical
     to `raster.py:1075`;
   * `snap=False` returns floats and is the default — **P3: rounding must be
     opt-in, and `raster` is the only caller that may ask for it**;
   * `flat_top` exists from day one but is unused in Commit A. Every caller
     passes `False`. This is the whole point of doing A first.

2. **`workflow/layout_engine/raster.py:1069-1087`** — `_hexagon_points` becomes a
   one-line delegate with `snap=True`, keeping the name so
   `tests/test_layout_raster.py:513` and `:663` still pass (P5).

3. **`workflow/layout_engine/geometry.py:546-549`** — the inline `_dx` becomes
   the pooled stagger. This is the highest-value single line in Commit A:
   `.cht`, the Measure overlay, `scanin_target` and `margin_inspector` are all
   downstream of it.

4. **`ui/tiff_preview.py:1747-1771`** (`_patch_hexagon`) and **`:1710-1719`**
   (`_strip_zigzag_path.verts`) — both call the pooled function with
   `step=None, snap=False`. Two copies collapse into one call each; the "matches
   the same geometry the strip zigzag uses" docstring promise becomes mechanical.

5. **`ui/tiff_preview.py:1491-1512`** (`_in_hexagon`) — either keep the
   inequality and pin it against the pooled polygon by test, or replace it with
   a point-in-polygon on the pooled points. **Prefer keeping it**, because it is
   called in a loop over every box on the page on every click, and the tests
   below make its agreement mechanical anyway. Do measure the loop cost before
   choosing.

6. **`ui/scan_grid_marquee.py:796-802`** — call the pooled function in unit
   space, `step=None, snap=False`.

7. **`tests/test_hex_scanner_support.py:85-96`** — rewrite the
   `inspect.getsource` assertion into a behavioural one on the returned array
   (P5). This is a strict improvement and belongs here.

8. **New: `tests/test_the_hexagon_is_drawn_from_one_place.py`** (P6 item 2).

9. **New: `tests/test_every_geometry_key_is_in_the_chokepoint.py`** (P7) — the
   generated mutation test on `GEOM_BUILD_KEYS`, landed on existing code where
   it can be proven to pass today and proven to fail when a key is removed.

10. **The ephemeral byte proof** (P6 item 1): render the matrix on `478c7396`
    and on the branch, `diff` the sha256 manifests, paste the result in the
    commit message. Do not add the script to the suite.

**Tests that must exist after Commit A:** the two new files above, plus
`tests/test_hex_scanner_support.py` rewritten, plus every existing hex test
still green: `test_layout_raster.py`, `test_hex_overlay_geometry.py`,
`test_hex_strip_overlay.py`, `test_hex_aspect_is_regular.py`,
`test_a_hexagon_is_taller_than_its_row_pitch.py`, `test_marquee_geometry_cache.py`,
`test_cr30_builtin_presets.py`, `test_hex_sample_clamp.py`.

**Highest risk in Commit A:** *the pooled function returns rounded vertices to
everybody, silently reverting the measured "NOT rounded" decision at
`ui/tiff_preview.py:1720-1723` and putting a half-pixel of drift on the Measure
overlay at every zoom level.* Nothing in the suite would catch it (P6), and it
is the natural thing to write, because the renderer needs ints and it is the
first caller anybody ports.

## COMMIT B — the rotation option.

Order matters: geometry before drawing, drawing before the control, the control
last, so that at no point does a reachable widget produce a chart the engine
cannot lay out.

1. `workflow/layout_engine/instruments.py:156` — `Geom.hex_flat_top: bool = False`.
2. `instruments.py:287` — `build(..., hex_flat_top: bool = False)`; the gate is
   `if key == "CR30" and hflag and hex_flat_top:` (P8), and it sets **both**
   `hxeh` and `hxew` itself rather than falling through the `key == "CM"` block
   at `:362-365` (P14).
3. `instruments.py:397-404` — `GEOM_BUILD_KEYS` gains `"hex_flat_top"`. P7's
   test from Commit A goes red until this line lands, which is the point.
4. `instruments.py:357-361` — the resized-hexagon reserve (`if geom.hexagonal and
   (patch_w or patch_h)`) swaps axes for a flat-top geometry.
5. `workflow/layout_engine/area_fit.py:118-124` — `ratio` becomes `2/sqrt(3)`,
   **gated on the instrument**, not on `hex_capable` (P8, P15).
6. `workflow/layout_engine/geometry.py:546-549` — the recorded rects. The
   per-patch `±w/4` goes; the per-strip offset at `:519-520` already does the
   new job **provided** `row_stagger_mm` carries it (P14). Measure the recorded
   rects against the rendered ink before going further; every remaining step is
   downstream of this being right.
7. `workflow/layout_engine/raster.py:1477-1481` — pass `flat_top` into the
   pooled function (one argument, because of Commit A); `raster.py:1389`
   `_protrude = (strip_w // 4)` becomes `pwid // 6` (P18 — **not** `plen // 4`,
   which is what the earlier plan says and is wrong).
8. `workflow/margin_inspector.py:283-287` — the apex overhang moves from
   `y0/y1` to `x0/x1` (P10).
9. `ui/tabs/tab_measure.py:528-578 _apply_hex_stagger` — a **positive** early
   return on the sidecar recipe's `hex_flat_top` (P9). Highest-severity item in
   the whole commit.
10. `ui/tiff_preview.py` — `_patch_hexagon`, `_strip_zigzag_path`, `_in_hexagon`
    take the orientation. `_strip_zigzag_path` is **not** a flipped zigzag: a
    flat-top strip outline is a rectangle grown by `pwid/6` on each side (P12).
    The orientation must reach the preview from the sidecar recipe, the same
    route `set_hex_zigzag` already uses (`tab_measure.py:4729`).
11. `ui/scan_grid_marquee.py` — orientation into the mesh, read off the same
    sidecar recipe the `GridSpec` already comes from.
12. `workflow/scanin_runner.py:140-168` — orientation-aware, or a docstring
    saying why it stays conservative at 63 % (P11 item 1).
13. `workflow/hex_support.py` — `hex_patch_width_mm()` beside
    `hex_patch_height_mm()`; a **new key** for the flat-top two-heights note,
    the existing key untouched (P11 items 2-3).
14. `ui/tabs/tab_chart.py:17808`, `:17895`, `:12520`,
    `ui/chart_layout_info_panel.py:144,185,254` — the reported patch size, both
    axes and the pitch label (P10).
15. `workflow/layout_engine/presets.py:36, 264, 382, build_kwargs()` — the
    recipe field. `tests/test_layout_presets.py:100` goes red here and demands
    the round-trip sample at `:87` be fed (P13).
16. `workflow/layout_engine/chart.py:101, :215` — the non-UI entry point.
17. `ui/dialogs/layout_options_panel.py:928-945` pattern — the checkbox and
    tooltip; visibility at `:2389-2391` and on `_area_is_hexagonal() and
    inst == "CR30"` (P13); load `:4451`; save `:4630`; re-gate wherever
    `_update_area_hex_locks()` runs (`:3205`, `:436`, `:4563` area).
18. i18n: 3 new English strings + 36 translations;
    `python scripts/i18n_extract.py --missing de`; `tests/test_i18n.py` and
    `tests/test_no_new_em_dash_in_user_facing_text.py` are the gate.
19. **Measure the patch count both ways on real builds** and report it — ruling
    2 requires it measured, not reasoned, and P14 shows H8's numbers were
    computed on a different `hxeh`/`hxew` split and cannot be carried over.
20. CHANGELOG, naming no paper size (answer 5), saying the count per sheet can
    move in either direction.
21. `--runslow` green.

**Tests that must exist for Commit B:**

* the four in P16's B6 list, each mutation-proven;
* `test_a_flat_top_honeycomb_is_a_regular_hexagon` — six equal sides, ratio
  `2/sqrt(3)`, measured off the rendered ink at 1200 dpi in the shape of
  `tests/test_a_hexagon_is_taller_than_its_row_pitch.py`. The FLIP-B guard, and
  ruling 3's only mechanical defence;
* `test_the_flipped_lattice_has_a_straight_strip` — off `patch_rects_px`:
  `dx == 0` down a strip, `±plen/2` between adjacent strips. The feature's whole
  value, asserted on geometry rather than on a picture;
* `test_the_recorded_rects_match_the_ink` — the 2026-08-13 fault re-run for the
  new orientation: render high-dpi, find each hexagon's ink centroid, compare
  with the recorded rect;
* `test_a_flat_top_chart_is_never_treated_as_a_legacy_sidecar` — P9, with the
  ±31 px number in it so a regression is legible;
* `test_a_recipe_written_before_this_field_renders_byte_identically` — the
  `row_indicators` precedent (`instruments.py:335-338`);
* `test_the_capacity_readout_follows_the_tick` — P7's generated test already
  covers the mechanism; this one covers the user-visible number in the panel;
* extend `tests/test_a_hexagon_is_taller_than_its_row_pitch.py` with a flat-top
  case rather than renaming it (P11 item 4);
* `tests/test_cr30_builtin_presets.py` must stay green untouched — the eight
  hexagonal presets carry no `hex_flat_top`, so `from_dict` defaults it False
  and nothing they build moves. **If that file needs an edit, the default
  leaked.**

**Highest risk in Commit B:** *`ui/tabs/tab_measure.py:568`.* Every flat-top
chart matches the legacy-sidecar fingerprint by construction, and the
consequence is a **31 px shift on a 123 px patch, on every patch of every
page** — the Measure highlight, the click target and the patch-by-patch ring all
naming the wrong hexagon. It is silent, it is universal, it looks exactly like a
bug somebody already reported and had fixed, and no test in the suite is
looking at it.

---

# WHAT I WOULD REFUSE

1. **I would refuse to put the pooled function in `workflow/hex_support.py`**,
   which is what the prior plan (H12 step 1) says. It makes the page renderer
   depend on `core.i18n` and on a file-reading module, and inverts a dependency
   that is currently clean (P4).

2. **I would refuse to ship Commit A with a changelog line implying a fix.** The
   five copies agree today, measured over 9,360 hexagons (P2). Commit A prevents
   a future disagreement; it does not repair a present one.

3. **I would refuse to ship Commit A without the ephemeral byte-level
   before/after** (P6). "Nothing visible changed" is currently provable by
   nothing in the suite, and the natural implementation regresses a measured
   sub-pixel decision (P3).

4. **I would refuse to gate the new field on `hflag` alone.** P8 is not a
   hypothetical: with ruling 2 in force, `hflag`-only gating builds a flat-top
   SpectroScan sheet from a control that instrument never showed. The gate is
   `key == "CR30"`, in all three places (`build`, `area_fit`, the panel's
   visibility).

5. **I would refuse a separate `AppSettings` key for "savable as a default"**,
   and a `_shared_get`/`_shared_set` entry. Both create the second writer that
   `d1adbe31` was written to remove (P13, and H17.2 before it).

6. **I would refuse to add a per-instrument memory for the rotation box.** Three
   of the four 2026-09-08 faults were the memory, not the hiding. The box has
   one meaning on the one instrument that shows it, so it needs none.

7. **I would refuse to touch `_apply_hex_stagger`'s heuristic.** Add a positive
   test on the stored orientation and return early; leave the fingerprint alone
   for the vintage it was written for (P9).

8. **I would refuse to rename `HEX_HEIGHT_FACTOR` or
   `tests/test_a_hexagon_is_taller_than_its_row_pitch.py`.** The number is right
   on both orientations; only the axis moves (P10, P11 item 4).

9. **I would refuse to carry H8's A4 capacity numbers forward without
   re-measuring.** The flip transposes the *reserves*, not just the page, and
   `hxeh`/`hxew` are two different kinds of quantity that swap axes (P14). The
   5.0 mm right-margin answer depends on numbers that have not been measured
   against the implementation that will actually exist.

10. **I would refuse to fold P17 (the panel losing the honeycomb on an
    instrument round trip) into either commit.** It is pre-existing, it will be
    misattributed to Commit B, and it should be confirmed and reported on its
    own.


## P18 — CONFIRMED. A correction to the earlier plan: the row-label clearance is not what it was said to be.

`workflow/layout_engine/raster.py:1383-1390`:

```python
# For hex patches the left column's even rows stagger 1/4 width LEFT past x0,
# so clear that protrusion too, else the hexagons cover the numbers.
_gap = max(1, px(1.0))
_protrude = (strip_w // 4) if ss_hex else 0
_rx = x0 - _protrude - _gap
```

The row-number band sits to the **left** of the patch block, and `_protrude`
clears whatever the leftmost column's ink sticks out horizontally. Today that is
the `-w/4` stagger.

The prior plan (H12/step 6) says this *"becomes `plen // 4` on the vertical
axis"*. That is wrong twice over: the clearance is horizontal in both
orientations because the band is always to the left, and on a flat-top sheet
there is no horizontal stagger at all — what sticks out to the left is the
**apex**, by `pwid/6`.

So `_protrude` for a flat-top honeycomb is `pwid // 6` (in px, `hxew`), which is
**smaller** than today's `pwid // 4`, not transposed. Get it wrong in the
transposing direction and the row numbers move `plen/4` further left for no
reason, eating the left margin the inspector then reports as compliant.

Measured on the shipped CR30 honeycomb: today `pwid/4 = 3.000 mm`; flat-top
wants `pwid/6` of the *new* `pwid` (10.392) = **1.732 mm**.

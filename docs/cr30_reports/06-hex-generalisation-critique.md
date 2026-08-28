STATUS: in-progress

# 06 — Hexagon generalisation critique (#159)

**Role:** CR30-HEX-CRITIC. Adversarial review of the *generalisation* of
hexagonal-patch support from a SpectroScan special case to a capability any
instrument's geometry can carry. Written against the live working tree of
`feature/cr30-instrument-159` while another agent implements. Every claim is
cited `file:line` and, where it is a behavioural claim, proved by running the
real engine. No production file or test was edited by this report.

**The design under attack:** do *not* widen `key == "SS"` to
`key in ("SS","CR30")`. Replace identity with capability — drive the gates off
`hxeh`/`hxew` (which a hexagonal `Geom` already sets non-zero), or add an
explicit boolean on `Geom` that whichever branch builds a hexagon sets.

Sections are appended as they are finished. Findings are ranked
BLOCKER / SERIOUS / MINOR and collected at the end.

---

## Section 1 — What actually landed, and whether the capability is derivable

### 1.0 State of the tree at the time of writing

HEAD `aed369d9` ("cr30: 12 mm cell (wip)") plus an uncommitted working tree
touching `tests/test_cr30_registration.py`, `ui/dialogs/layout_options_panel.py`,
`ui/tabs/tab_chart.py`, `workflow/chart_creator.py`,
`workflow/layout_engine/{geometry,instruments,preflight,raster}.py`. The
critique is against that combined state.

The implementer took the **explicit-flag** route, not the inference route:

* `workflow/layout_engine/instruments.py:153` — `Geom.hexagonal: bool = False`.
* `instruments.py:161-170` — `is_hexagonal(geom)`, "THE single test".
* `instruments.py:173-189` — `hex_capable(key)` = `build(key, hflag=True).hexagonal`,
  and `hex_capable_instruments()`.
* The two building branches set it about themselves: `instruments.py:534` (SS)
  and `instruments.py:693` (CR30), both `hexagonal=bool(hflag)`.
* The three known gates now call it: `raster.py:1057-1058`,
  `geometry.py:478-479`, `geometry.py:674-675`.
* `instruments.py:299` — the overhang-follows-patch-size rule was
  `key in ("SS","CR30") and geom.hxew > 0 and (patch_w or patch_h)`; it is now
  `geom.hexagonal and (patch_w or patch_h)`.
* `workflow/hex_support.py:104-105` — `recipe_is_hexagonal` is
  `bool(hflag) and hex_capable(str(inst))`, so every downstream consumer of it
  generalises for free.
* `ui/tabs/tab_chart.py:3288` and `:16178-16188` — `_warn_if_hexagonal_selected`
  and `_chart_is_hexagonal` both call `hex_capable` instead of matching `"SS"`.

**This is the right shape and it is better than what I was asked to check.**
The three blockers of report 05 are fixed, and fixed *together* — §4 below
proves the raster and the recorded rects still agree.

### 1.1 The capability is NOT derivable from `hxeh` — proved

The brief offered `hxeh`/`hxew` as the inference source. `hxeh` is unsafe, and
the implementer's comment at `instruments.py:151-152` names the exact reason.
Measured through the real builder:

```
build("CM", cm_stagger=True)  ->  hexagonal=False  hxeh=3.500  hxew=0.000
```

`instruments.py:304-305`: the ColorMunki's brick-wall row stagger sets
`hxeh = 0.25 * plen` **on a rectangular geometry**. Any gate written as
`hxeh > 0` would have turned a ColorMunki double-density chart into a honeycomb
in the renderer and in the recorded rects. That is a shipped instrument, not a
hypothetical.

`hxew` happens to be safe **today** — swept over all seven instruments × both
`hflag` states, `hxew > 0` exactly matches `hexagonal`:

| key | hflag=False | hflag=True |
|---|---|---|
| i1 / p3 / 41 / 51 | hex=F, hxew=0 | hex=F, hxew=0 |
| CM | hex=F, hxew=0 | hex=F, hxew=0 (density 2, *squares*) |
| SS | hex=F, hxew=0 | **hex=T, hxew=1.750** |
| CR30 | hex=F, hxew=0 | **hex=T, hxew=3.000** |

But it is safe only by coincidence of the current instrument set, and it is a
*float* answering a *shape* question — the CM precedent shows exactly how such a
coincidence ends. The explicit flag is correct and the reasoning recorded at
`instruments.py:138-152` is the right reasoning. **This survives the attack.**

Two residual soundness checks, both pass:

* `build()` returns `replace(geom, …)` (`instruments.py:317`) and never names
  `hexagonal`, so a dataclass `replace` carries it through unchanged. Verified:
  `build("CR30", hflag=True, patch_w=20).hexagonal` is True.
* The only other `replace()` on a `Geom` in the tree is
  `raster.apply_furniture_reserves` (`raster.py:362`), which sets
  `label_band_mm` / `bottom_reserve_mm` only. `chart.py:416` replaces a
  *recipe*, `calibration.py:94` a *target*. No path can strip the flag.

### 1.2 Can `hexagonal` be True with a degenerate geometry?

`build(key, hflag=True, pscale=0)` gives `hexagonal=True` with
`hxeh = hxew = plen = 0`. The renderer would then draw six coincident points.
This is pre-existing and equally true of `pscale=0` on a square chart
(zero-size rects), and `_fill_rect` / `draw.polygon` both survive it. Not a
finding — recorded so nobody re-derives it.

---

## Section 2 — THE CRUX: every hexagon-related gate, with a verdict

The question each site is really asking, and whether identity or capability is
the right answer for it. **A gate that means "is a SpectroScan" must not become
"is hexagonal", and vice versa** — so the list separates the two.

### A. Converted to the capability — correct, and verified

| # | Site | Asks | Verdict |
|---|---|---|---|
| A1 | `workflow/layout_engine/instruments.py:153` `Geom.hexagonal` | the flag itself | correct |
| A2 | `instruments.py:161-170` `is_hexagonal(geom)` | **is hexagonal** | correct |
| A3 | `instruments.py:173-189` `hex_capable` / `hex_capable_instruments` | **can be hexagonal** | correct |
| A4 | `instruments.py:534` (SS), `:693` (CR30) `hexagonal=bool(hflag)` | declares itself | correct |
| A5 | `instruments.py:299` resize→overhang | **is hexagonal** | correct (was `key in ("SS","CR30")`) |
| A6 | `raster.py:1057-1058` `ss_hex` | **is hexagonal** | correct |
| A7 | `raster.py:1224` `_protrude` row-number clearance | **is hexagonal** | correct (shares A6's local) |
| A8 | `geometry.py:478-479` recorded-rect stagger | **is hexagonal** | correct |
| A9 | `geometry.py:674-675` `helper_marker_lines_mm` | **is hexagonal** | correct |
| A10 | `workflow/hex_support.py:104-105` `recipe_is_hexagonal` | **is hexagonal** | correct — every consumer generalises for free |
| A11 | `ui/tabs/tab_chart.py:3288` `_warn_if_hexagonal_selected` | **is hexagonal** | correct |
| A12 | `ui/tabs/tab_chart.py:16178-16188` `_chart_is_hexagonal` | **is hexagonal** | correct |
| A13 | `tests/test_hex_overlay_geometry.py:38` `HEX_INSTRUMENTS = hex_capable_instruments()` | **can be hexagonal** | correct, and the right way to parametrise |

The A10 chain is worth naming, because it is where most of the value is. Through
`recipe_is_hexagonal` the following generalised **without being touched**, and I
verified each reads only the recipe:

* `workflow/margin_inspector.py:282-286` — the apex correction to the reported
  ink extremes (and it correctly does *not* re-apply the ±¼-width stagger,
  because `patch_rects_px` already carries it).
* `ui/dialogs/scanin_dialog.py:1974-1985` — the hexagonal sample-area cap,
  computed by `scanin_runner.hex_max_sample_fraction` **from `w`/`h` alone**.
  A CR30 hexagon has `h/w = 10.392/12 = 0.866`, exactly the SpectroScan's ratio,
  so both get the same 64.4 % ceiling. No instrument appears in that maths.
* `ui/dialogs/scanin_dialog.py:1741` and
  `ui/dialogs/scanin_target_dialog.py:367-384` — the Beta opt-in refusal.
* `ui/tabs/tab_measure.py:4190` `set_hex_zigzag`, and `:505` the legacy-sidecar
  compensation.
* `ui/scan_grid_marquee.py:214-215, 279-338, 624` — the marquee draws hex cells;
  the flag is passed in from the scanin dialog, so it is capability-driven.

### B. Correctly still instrument identity — do NOT generalise these

| # | Site | Asks | Why identity is right |
|---|---|---|---|
| B1 | `hex_support.py:130` `settings_are_hexagonal` (`printtarg-i == "SS"`) | **did printtarg draw hexagons** | printtarg has no CR30 at all: `chart_creator.ENGINE_ONLY_INSTRUMENTS = {"CR30"}` (`:141`) and `ti2_relayout.instrument_to_flag` (`:53-58`) returns `"CR30"`, which is not a printtarg `-i` code. A CR30 chart can only ever be an engine chart, so it always has a recipe and never needs this fallback. |
| B2 | `chart_creator.py:1866` `-h` in the printtarg argv (`{"CM","SS"}`) | **does printtarg `-h` apply** | same |
| B3 | `tab_chart.py:11733` `dd_flag` in the command preview | **does printtarg `-h` apply** | same |
| B4 | `tab_chart.py:6824` Manual `-h` ParameterWidget visibility | **is this the printtarg widget's instrument** | same |
| B5 | `layout_options_panel.py:1964-1971` `inst == "SS"` → `area_method = by_grid` | **is a flatbed** | the CR30 has its own arm at `:1960-1963` that deliberately leaves the area method alone — the comment says why ("meaningless for a flatbed but perfectly meaningful for a hand-placed device"). Two devices, two answers, correctly separated. |
| B6 | `presets.py:413` `instrument == "SS"` → `patch_first` | **is a flatbed** | the CR30 has its own arm at `:421` with a different reason (a hand-aimed patch size must not float). Duplicated *code*, not a duplicated *meaning*. |
| B7 | `native/chartread_helper/chromiq_chartread.c:3819-3820` → `hex` | **motorised XY navigation** | **verified twice over.** `hex` is dereferenced in exactly one place, `:1753-1786`, inside `} else if (rmode == 2) {` at `:1541` ("For xy mode, read each sheet"), computing `ox/oy/ax/ay/aax/aay/px/py` for `read_xy`. And a CR30 never gets there by two independent routes: (a) `:3711-3720` — a CR30 chart is refused outright unless `-x` (external values) is given, and (b) the entire `check_mode` block that could ever set `rmode` is inside `if (xtern == 0)` at `:918`, so with `-x` the initialiser at `:908` (`int rmode = 0`) stands and the read goes to spot mode at `:2600` ("Spot mode. This will be used if xtern != 0"). Report 05's finding is confirmed and strengthened. |

### C. MEANS HEXAGONAL, still hard-coded to a name — the generalisation is unfinished

| # | Site | Effect today |
|---|---|---|
| **C1** | `ui/tabs/tab_chart.py:11530` `elif instr == "SS": kw["hflag"] = bool(dd)` in `_engine_geom` | **CR30 is absent from the whole `elif` chain.** BLOCKER — measured in §3.1. |
| C2 | `tab_chart.py:11568` `if instr == "SS" and dd` (`_engine_info_line`) | the Guided layout-info line never says "hexagonal" for a CR30 |
| C3 | `tab_chart.py:11615` `if r.instrument == "SS" and r.hflag` (`_engine_info_line_from_recipe`) | the Manual info line never says "hexagonal" for a CR30 |
| C4 | `workflow/layout_engine/presets.py:171-177` `LayoutRecipe.mode()` | two byte-identical arms. A third hex-capable instrument falls to `"default"`, so its flat and hex recipes **collide on one `preset_key()`** and silently overwrite each other |
| C5 | `presets.py:451` `elif instrument in ("SS", "CR30"): r.hflag = (mode == "hex")` | a name list where `hex_capable()` exists |
| C6 | `presets.py:523-525` `factory_defaults` | `["flat","hex"] if inst == "SS" else ["flat","hex"] if inst == "CR30"` — the duplication is literal |
| C7 | `ui/dialogs/layout_options_panel.py:90-95` `mode_label_for` | two arms both returning `tr("Patch shape:")` |
| C8 | `layout_options_panel.py:177-181` `modes_for` | two byte-identical arms |
| C9 | `layout_options_panel.py:124-165` `mode_tooltip_for` | per-instrument prose, legitimately different — but a new hex instrument falls through to the generic "Layout mode" tooltip |
| C10 | `tab_chart.py:11803-11895` `_update_dd_visibility` | per-instrument arms; a new hex instrument gets the checkbox **hidden and force-unchecked** at `:11891` |

C4–C10 are the same defect in seven places: **"which instruments have a
flat/hex mode" is written down seven times and derived nowhere**, while
`instruments.hex_capable()` is sitting there as the answer. That is precisely
the shape of the fault this whole exercise exists to remove — the three original
`key == "SS"` gates drifted apart for exactly this reason. It is not currently
*wrong* (both lists happen to say SS+CR30), so it is SERIOUS, not a blocker;
but the next instrument will half-land, and C4 will do it silently.

---

## Section 3 — Downstream: what breaks when a non-SS instrument becomes hexagonal

### 3.1 BLOCKER — the Guided patch count ignores everything the CR30 does

`ui/tabs/tab_chart.py:11495-11531`, `_engine_geom`. The `if/elif` chain that
translates the Guided selectors into engine kwargs has arms for `i1`/`p3`, `CM`
and `SS`. **It has no `CR30` arm at all**, while
`workflow/chart_creator.py:1183-1206` — the path that actually *builds* the
chart — sets three things for a CR30 that the estimate does not:
`layout_mode="patch_first"`, `hflag=bool(double_density)`, and (Guided only)
`spacer_on=False` / `spacer_mode="none"`.

Measured through the real engine, A4, Guided defaults:

| | patches/sheet |
|---|---|
| what the readout shows, hexagon box **off** | **315** |
| what the readout shows, hexagon box **on** | **315** — the box changes nothing |
| what the chart really holds, rectangular | **345** |
| what the chart really holds, hexagonal | **390** |

So the big PATCHES number on the first screen of Create Chart is wrong by
30 patches on a rectangular CR30 sheet and by 75 on a hexagonal one, and
**ticking "Hexagon patches" does not move it**. That readout is also
`self._predicted_patch_count`, which feeds the Suggest-name button
(`tab_chart.py:11693`).

This is exactly the failure `GEOM_BUILD_KEYS` was written to prevent — its own
comment (`instruments.py:389-394`) says *"a missing key silently makes capacity
ESTIMATES disagree with the actual render (clip_border_width once did exactly
that — #93)"*. The lockstep is between `chart_creator._engine_build_kwargs` and
`tab_chart._engine_geom`, and it is broken.

**Ranked BLOCKER, not SERIOUS,** because it is the number the user chooses the
chart by, it is wrong in the *conservative* direction on the shape switch (the
feature under review looks like it does nothing), and it is on the default
screen for the instrument being added.

### 3.2 SERIOUS — the row-number band overflows at the ruled 12 mm cell

Not a hexagon fault; found while verifying `raster.py:1224`'s `_protrude`
clearance, which report 05 called the CR30's most important furniture.

`rlwi = 7.5` mm is inherited from the SpectroScan's 7 mm patch. The row-number
font, though, scales with the patch (`raster.effective_indicator_size_mm`), and
at the CR30's 12 mm cell a two-digit row number is **8.43 mm wide against a
7.5 mm band**. Measured at 300 dpi, A4, `default_recipe`:

| inst | shape | patch | indicator | "13" width | band | text starts at |
|---|---|---|---|---|---|---|
| SS | flat | 7.0 | 4.25 mm | 5.08 mm | 7.5 | 7.37 mm (inside a 6 mm margin) |
| SS | hex | 7.0 | 4.25 mm | 5.08 mm | 7.5 | 7.45 mm |
| **CR30** | **flat** | **12.0** | **7.00 mm** | **8.43 mm** | **7.5** | **4.01 mm — 2 mm inside the margin** |
| **CR30** | **hex** | **12.0** | **7.00 mm** | **8.43 mm** | **7.5** | **4.10 mm** |
| CR30 | flat | 12.0, margin 2 mm | 7.00 mm | 8.43 mm | 7.5 | **0.03 mm from the paper edge** |
| CR30 | flat | 8.0 | 4.83 mm | 5.79 mm | 7.5 | 6.65 mm (fits) |

So on every CR30 sheet at the ruled size the row numbers print **outside the
patch area's left margin**, and at a 2 mm margin they land 30 µm from the paper
edge — inside the unprintable zone of most inkjets. It affects the rectangular
default as much as the honeycomb, so it is not gated behind an option.

Also note `raster.py:1224` `_protrude = strip_w // 4` takes another 3.0 mm on a
hexagonal CR30, which the placement does *not* reserve (only `hxew` on the patch
block is reserved) — the numbers move left by exactly that much. It happens to
be cancelled here by the block's own `+hxew` shift, but the two are computed in
different modules and nothing ties them together.

### 3.3 What survives downstream — verified, do not re-derive

* **`patch_rects_px` consumers.** The complete list, and every one is
  shape-agnostic (it reads the recorded rects, which now carry the stagger for
  any hexagonal geometry):
  1. `workflow/layout_engine/chart.py:362-370` — writes them into
     `<stem>.strips.json` under `"patches"`; this is what the Measure tab and
     the margin inspector load.
  2. `chart.py:385` → `cht_writer.boxes_from_patch_rects` — the `.cht` boxes.
     `cht_writer.py:123-140` has no shape logic at all: it converts a rect to
     CHT bottom-left mm. A honeycomb `.cht` is therefore correct by
     construction, and `emit_cht` is False by default (`chart.py:188`).
  3. `workflow/scanin_target.py:230` — the scanner target's patch boxes, via
     the same `boxes_from_patch_rects`.
  4. `workflow/margin_inspector.py` — reads the sidecar rects; adds the apex
     only, never the stagger (`:277-286`).
  5. `ui/dialogs/ti2_relayout_dialog.py:6926-6929, 7035, 7116-7135` — the
     editor's engine preview.
  6. `ui/tabs/tab_measure.py` via `_apply_hex_stagger` and the loaded boxes.
* **`SAMPLE_LOC`** is written by `permutation.location_label`
  (`geometry.py:493`) from the slot index — it never sees the shape. Identical
  labels for flat and hex.
* **The render and the recorded rects use the identical stagger.**
  `raster._hexagon_points` (`raster.py:934`) computes
  `dx = round(-w/4) if step % 2 == 0 else round(w/4)` on `w = xR - x0` where
  `xR = px(x_of(p) + pwid)`; `geometry.patch_rects_px` (`:520-523`) computes
  the same expression on `_x1 - _x0` where `_x1 = px(x_of(p) + pwid)`. Same
  quantity, same rounding, same parity variable (`j` = `step`). They cannot
  diverge without one of them being edited.
* **The vector PDF and the Tier D device raster** get the hexagon too:
  `raster.py:1247-1249` records `("hex", _pts, dev)` under the same `ss_hex`
  flag, so `collect_device_geom` consumers follow automatically.

### 3.4 If a *third* instrument is made hexagonal tomorrow

I walked it as an i1Pro to find where the "one-line change" claim fails. Adding
`hexagonal=bool(hflag)` to a branch is **not** sufficient:

1. `presets.LayoutRecipe.mode()` (C4) returns `"clip"`/`"noclip"` for i1, so the
   flat and hex recipes get the **same `preset_key()`** and overwrite each other
   in `PresetStore`. Silent data loss, not a missing feature.
2. `layout_options_panel.modes_for` (C8) offers no `hex` entry, so the shape is
   unreachable from Manual.
3. `tab_chart._update_dd_visibility` (C10) hides the Guided checkbox and
   force-unchecks it at `:11891`.
4. `tab_chart._engine_geom` (C1) never maps the checkbox to `hflag` — the same
   hole the CR30 is in now.
5. `chart_creator._engine_build_kwargs` has no arm either.

None of that is caught by a test, because `hex_capable_instruments()` would
return the new instrument and the *engine* tests would pass. The engine half of
the generalisation is done; the **recipe/UI half is still seven hard-coded
lists**.

---

## Section 4 — The tests: I tried to make them pass on a broken implementation

**Method.** The tree was copied (`rsync`, minus `.git`/`.venv`) to a scratch
directory so nothing the implementer is holding could be touched, and each
mutation was applied there and reverted. Baseline over
`test_cr30_registration.py`, `test_hex_overlay_geometry.py`,
`test_layout_raster.py`, `test_layout_geometry.py`, `test_margin_inspector.py`,
`test_hex_scanner_support.py`, `test_cht_writer.py`, `test_engine_ui.py`:
**314 passed, 1 skipped**. Every mutation below was verified to actually land
(the mutated line was grepped back out before the run).

| # | Mutation — a plausible way to get it wrong | Result |
|---|---|---|
| M1 | `raster.py` gate back to `key == "SS" and hxew > 0` (the original blocker) | **CAUGHT** — `test_a_hex_chart_really_renders_hexagons[CR30]` |
| M2 | `geometry.patch_rects_px` stagger gate back to `key == "SS"` | **CAUGHT** — `test_the_loaded_boxes_are_the_recorded_boxes[20.0-CR30]` |
| M3 | `helper_marker_lines_mm` gate back to `key == "SS"` | **CAUGHT** — `test_a_honeycomb_gets_no_ruler_helper_markers[CR30]` |
| M4 | `is_hexagonal()` inferred from `hxeh > 0` (the unsafe inference the brief offered) | **CAUGHT** — `test_hex_capability_is_asked_of_the_geometry_not_a_list` |
| M5 | the CR30 branch stops setting `hexagonal=bool(hflag)` | **CAUGHT** — same test |
| M6 | the resize→overhang rule narrowed back to `key == "SS"` | **CAUGHT** — `test_a_resized_hexagon_recomputes_its_overhang` |
| M7 | the renderer staggers the **opposite way** from the recorded rects (a live half-patch mis-registration, render and rects each self-consistent) | **CAUGHT** — `test_spectroscan_hex_pokes_above_first_row` |
| M8 | `_hexagon_points` draws a **rectangle** (`t6 = 0`) while still labelling the row `"hex"` | **CAUGHT** — `test_spectroscan_hex_pokes_above_first_row` |
| M9 | hexagons drawn with **no** horizontal stagger (`dx = 0`) | **CAUGHT** — `test_hexagon_points_shape_and_stagger`, `test_spectroscan_hex_pokes_above_first_row` |
| M10 | `default_recipe` stops mapping `mode="hex"` → `hflag` for the CR30 | **CAUGHT** — `test_a_honeycomb_gets_no_ruler_helper_markers[CR30]` |

**Verdict: the tests are not theatre. I could not construct a broken hexagon
that the suite accepts.** The two design decisions that make them work are worth
naming so they are not undone:

1. `_drawn_shapes` (`tests/test_cr30_registration.py:570-587`) asserts on
   `render_pages(..., collect_device_geom=True).patch_geom` — **what the
   renderer actually drew**, not on `Geom` fields. Its docstring records that
   pixel-corner sampling was tried first and cannot answer the question,
   because in a honeycomb a slot's corners are filled by its neighbours. That
   is correct and it is the reason M1 is caught.
2. `HEX_INSTRUMENTS = instruments.hex_capable_instruments()`
   (`tests/test_hex_overlay_geometry.py:38`) — the parametrisation is
   *derived*, so a new hex-capable instrument is covered the moment it exists.
   This is the single best thing in the change.

### 4.1 SERIOUS — the coverage is not symmetric, and `test_layout_raster.py` is still SS-only

M8 and M9 were caught, but **only by SpectroScan tests**. The five hex tests in
`tests/test_layout_raster.py` are all still hard-coded:

* `:75-90` `test_hex_strip_count_matches_columns_not_interlock` — `default_recipe("SS", …)`
* `:510` `test_hexagon_points_shape_and_stagger`
* `:527-532` `test_spectroscan_hex_pokes_above_first_row` — `build("SS", hflag=True)`
* `:647` the row-number label clearance (`_protrude`) — `build("SS", hflag=True)`
* `:653-656` `test_spectroscan_hex_first_column_not_clipped` — `build("SS", hflag=True)`

Report 05's change #6 asked for both files; only `test_hex_overlay_geometry.py`
got it. The one at `:647` is the one that matters most, because §3.2 shows the
CR30's row-number band behaves **differently** from the SpectroScan's at the
same code — 8.43 mm of text in a 7.5 mm band against 5.08 mm in the same band.
A shared code path with different geometry is exactly where an SS-only test
stops being a proxy. Parametrising these five over `HEX_INSTRUMENTS` would have
found §3.2.

### 4.2 SERIOUS — nothing tests the Guided/Manual UI wiring at all

§3.1's blocker is live in the tree **with a green suite**. `_engine_geom` and
`_engine_info_line*` have no CR30 coverage, and no test compares
`tab_chart._engine_geom` against `chart_creator._engine_build_kwargs` for any
instrument — which is the invariant `GEOM_BUILD_KEYS` exists to protect. One
parametrised test ("the estimate agrees with the build, per instrument, per
mode") closes §3.1 and pins the lockstep for every future instrument.

---

## Section 5 — Backward compatibility: proved, not argued

The requirement is that existing SpectroScan hexagonal charts and existing user
projects render and measure **identically**. I proved it three ways against
`master` (extracted with `git archive` into a scratch tree, so both versions run
the same probe script on the same input).

**5.1 A whole chart, byte for byte.** A fixed 120-patch `.ti1`, built through
`chart.build_from_recipe` with `default_recipe("SS", "A4", mode=…)`, seed 7,
randomise off, 150 dpi:

| artefact | flat | hex |
|---|---|---|
| rendered TIFF (SHA-256) | **identical** | **identical** |
| `.strips.json` (strip rects **and** every patch rect) | **identical** | **identical** |
| `.ti2` | identical apart from the `CREATED` timestamp | same |

So the pixels a SpectroScan user prints, and the boxes the Measure tab and the
margin inspector read, are unchanged.

**5.2 Geometry and capacity, swept.** 864 combinations —
`{i1, p3, CM, 41, 51, SS} × {A4, A4R, A3, Letter} × hflag × density 1–3 ×
pscale {0.8, 1.0, 1.5} × cm_stagger` — comparing `patches_per_sheet`, `hxeh`,
`hxew`, `plen`, `pwid`. **Zero differences.** This is the check that would have
caught the `instruments.py:299` rewrite if `geom.hexagonal` had not been an
exact substitute for `key in ("SS","CR30") and hxew > 0`.

**5.3 The Manual resize path, swept.** 240 combinations —
`{i1, p3, CM, 41, 51, SS} × hflag × patch_w {None,6,10,20,30} ×
patch_h {None,6,10,20}` — comparing `hxeh`, `hxew`, `plen`, `pwid`, `rrsp`.
**Zero differences.**

The probes are kept at
`scratchpad/{bc_probe.py, cap_probe.py, rs_probe.py}` and are re-runnable
against any two trees; §"Concrete changes" asks for 5.2 and 5.3 to be adopted
as a test rather than left in a scratch directory.

### 5.4 MINOR — a CR30 hex chart built *on this branch before the fix* is now misread

`ui/tabs/tab_measure.py:481-529` `_apply_hex_stagger` compensates *legacy*
sidecars whose rects were recorded without the stagger, and identifies them by
fingerprint: "a column of two or more patches that all share one x".

A CR30 hexagonal chart built between commit `22f005aa` and the fix has exactly
that fingerprint — its rects are unstaggered because `geometry.py:475` still
said `"SS"` — **and it was also drawn as squares**. After the fix,
`chart_is_hexagonal` returns True for it, the legacy fingerprint matches, and
the Measure highlight is shifted ±¼ patch onto ink that was never staggered.
The chart is wrong either way, but it now fails *differently* than it looks.

MINOR because the CR30 has never shipped in a beta — but Basti and Knut drive
this branch on screen, so any CR30 honeycomb in a real project folder from the
last few days should be rebuilt rather than measured.

### 5.5 MINOR — a `.ti2` separated from its sidecar loses its shape

`hex_support.chart_is_hexagonal` reads only `<stem>.channels.json` and fails
open. The `.ti2` itself carries `HEXAGON_PATCHES "True"`
(`instruments.py:527`/`:684`, asserted at
`tests/test_cr30_registration.py:331`) and is never consulted. A chart imported
as a bare `.ti2` therefore measures as if it were rectangular: rectangular
highlight over hexagons, and the scanner sample-area cap silently lifted.
Pre-existing for the SpectroScan; it now applies to a second instrument. The
fallback is one `find_kword`-equivalent away.

---

## Section 6 — What a real user hits that the design does not cover

### 6.1 SERIOUS — three user-facing strings quote numbers from the 10 mm cell

The cell was ruled to 12 mm (HEAD `aed369d9`, "cr30: 12 mm cell (wip)"). The
patch-count claims were not re-measured. Measured now, through
`geometry.patches_per_sheet` on `default_recipe`:

| paper | rectangular | hexagonal | gain |
|---|---|---|---|
| **A4 portrait** | **345** | **405** | **+17.4 %** |
| A4 landscape | 368 | 396 | +7.6 % |
| A3 | 782 | 836 | +6.9 % |

And the provenance of the shipped figures, confirmed by forcing the old size:
`patch_w = 10 mm` gives **532 flat / 576 hex** — exactly the pair three strings
still quote. They are the *previous* ruling's numbers.

| site | says | truth |
|---|---|---|
| `ui/tabs/tab_chart.py:11836` (Guided checkbox **label**) | "Hexagon patches (suits the round CR30, **~8 % more per sheet**)" | +17.4 % on A4P; ~7 % on A4L/A3 |
| `ui/tabs/tab_chart.py:11848` (Guided tooltip) | "532 patches rectangular, **576 hexagonal**" | 345 / 405 |
| `ui/dialogs/layout_options_panel.py:142` (Manual tooltip) | "532 patches rectangular, **576 hexagonal**" | 345 / 405 |
| `workflow/layout_engine/presets.py:175` (comment) | "packs **~15 %** more per sheet" | +17.4 % A4P, +6.9 % A3 |

`workflow/layout_engine/instruments.py:640` already says "345 patches
rectangular, 405 hexagonal (+17 %)" — the geometry comment was updated and the
four sites above were not. Graded SERIOUS because two of them are **translated
strings**: changing them costs a German pass and a `tests/test_i18n.py` run, so
it is cheaper to fix before the strings are translated than after.

The honest phrasing is a range, not a number — the gain is +17 % on A4 portrait
and +7 % on A4 landscape and A3, because the honeycomb hands back
`2·hxew = 6.0 mm` of width and `2·hxeh = 3.5 mm` of height, and a wider sheet
absorbs the width penalty less well.

### 6.2 SERIOUS — the "Double density"/"Hexagon patches" checkbox leak now changes the SHAPE

`ui/tabs/tab_chart.py:11803-11895`: one `_dd_check` carries three meanings, and
it is force-unchecked **only when hidden** (`:11888-11891`). It is visible for
CM, SS and CR30, so:

* ColorMunki with **Double density** on → switch to CR30 → arrives with
  **hexagons silently on**;
* SpectroScan with **Hexagon patches** on → switch to ColorMunki → arrives at
  **double density**, which needs hardware the user may not own.

Report 05 graded this MINOR (§3.7) when a CR30 honeycomb was drawn as squares.
It is now SERIOUS, because the shape actually changes — and §3.1 means the
patch-count readout **does not move**, so nothing on screen hints that the
sheet just changed shape. The state is persisted as `chart_double_density`
(`tab_chart.py:17812`), so it survives a restart.

### 6.3 MINOR — text written for a SpectroScan is now shown to a CR30 user

* `workflow/hex_support.py:69-70`, `hex_scanner_message()` — the way out it
  offers is *"make the chart with square patches: in Create Chart, **with the
  SpectroScan selected**, set the layout to Rectangular."* This message is now
  raised for a CR30 honeycomb (`scanin_dialog.py:1741`,
  `scanin_target_dialog.py:384`), telling a CR30 user to select a different
  instrument. Translated string.
* `ui/dialogs/settings_dialog.py:3201-3203` — *"for the SpectroScan it is
  rectangular vs hexagonal patches"*, in the help for the very preset grid that
  now also holds `CR30|…|flat` / `CR30|…|hex`. Translated string.
* `ui/tiff_preview.py:1496-1499` and `ui/tabs/tab_measure.py:4191-4193` —
  *"which a CR30 chart's square patches must not get"*. Code comments only; the
  code is right (`set_hex_zigzag` is driven by `chart_is_hexagonal`), but the
  comment now asserts the opposite of the feature. Carried over from report 05
  §3.8 and still present.

### 6.4 Mixed shapes, switching shapes, other machines, printing, reports

Walked, and each is fine or already covered above:

* **Mixed hex and rect in one project.** Each run carries its own chart,
  `.channels.json` and recipe; `chart_is_hexagonal` is asked per chart path
  (`tab_measure.py:4190`, `:506`). Two runs of one target may differ freely.
  No shared state was found. **Survives.**
* **Switching shape after a chart exists.** `_chart_is_hexagonal` deliberately
  reads the live selectors, not the built chart — that is #152's ruling
  (`tab_chart.py:16157-16171` records Knut's report and why). The margin
  inspector and the measure overlay keep reading the *chart's* sidecar, so the
  built chart is never re-judged by the selector. **Correct as designed.**
* **Measured on another machine.** The whole run folder travels, sidecar
  included, so the shape survives. A bare `.ti2` does not — §5.5.
* **Printing.** `PostScriptGenerator` takes the rendered TIFF; nothing on that
  path knows the patch shape. **No exposure.**
* **Reports and the overlay.** Both read the recorded rects, which now carry
  the stagger for any hexagonal geometry (§3.3). `margin_inspector` adds the
  apex and correctly does not re-add the stagger. **Survives.**

---

## Findings, ranked

### BLOCKER

1. **The Guided patch count ignores the CR30 entirely.**
   `ui/tabs/tab_chart.py:11495-11531` (`_engine_geom`) has no `CR30` arm, so the
   estimate is built without `hflag`, without `layout_mode="patch_first"` and
   with spacers ON, while `workflow/chart_creator.py:1183-1206` builds the real
   chart with all three. Measured, A4: the readout says **315** whether the
   hexagon box is ticked or not; the sheet holds **345** rectangular and
   **390–405** hexagonal. The headline number on the default screen is wrong,
   and ticking the feature under review moves nothing. Breaks the
   `GEOM_BUILD_KEYS` lockstep contract (`instruments.py:389-394`). §3.1

### SERIOUS

2. **"Which instruments can be hexagonal" is written down seven times and
   derived nowhere.** `presets.py:171-177` (`mode()`), `:451`, `:523-525`
   (`factory_defaults`); `layout_options_panel.py:90-95` (`mode_label_for`),
   `:177-181` (`modes_for`), `:124-165` (`mode_tooltip_for` fallback);
   `tab_chart.py:11803-11895` (`_update_dd_visibility`). `hex_capable()` exists
   and answers all of them. The worst is `mode()`: a third hex-capable
   instrument gets `"default"`, so its flat and hex recipes **collide on one
   `preset_key()`** and silently overwrite each other. §2-C, §3.4
3. **The row-number band overflows at the ruled 12 mm cell** — a two-digit row
   number is 8.43 mm wide against `rlwi = 7.5` mm, so the numbers print ~2 mm
   into the left margin, and 0.03 mm from the paper edge at a 2 mm margin.
   Affects rectangular and hexagonal alike; the CR30 is the only instrument
   whose patch is nearly twice the band's design size. §3.2
4. **Three user-facing strings and one comment quote the 10 mm cell's numbers.**
   "~8 % more per sheet" (`tab_chart.py:11836`), "532 rectangular / 576
   hexagonal" (`tab_chart.py:11848`, `layout_options_panel.py:142`), "~15 %"
   (`presets.py:175`). Truth at 12 mm: 345/405 on A4 portrait (+17.4 %), +7 % on
   A4 landscape and A3. Two of them are translated strings. §6.1
5. **The shared checkbox now silently changes the patch SHAPE.**
   CM double-density → CR30 arrives with hexagons on; SS hexagons → CM arrives
   at double density. Force-unchecked only when hidden
   (`tab_chart.py:11888-11891`), persisted as `chart_double_density`. Was MINOR
   while a CR30 honeycomb rendered as squares; it is not any more — and finding
   1 means the patch count does not even move. §6.2
6. **`tests/test_layout_raster.py`'s five hex tests are still SS-only**
   (`:75-90`, `:510`, `:527-532`, `:647`, `:653-656`). The one at `:647` is the
   row-number clearance — the exact code whose CR30 behaviour differs (finding
   3). Report 05 asked for both hex test files; only
   `test_hex_overlay_geometry.py` was parametrised. §4.1
7. **Nothing tests the Guided/Manual → engine wiring**, which is why finding 1
   is live under a green suite. No test compares `tab_chart._engine_geom` with
   `chart_creator._engine_build_kwargs` for any instrument. §4.2
8. **The Guided and Manual info lines never say "hexagonal" for a CR30** —
   `tab_chart.py:11568`, `:11615`. The one line that summarises what the engine
   will build omits the shape the user just chose. §2-C2, C3

### MINOR

9. Text written for a SpectroScan is now shown to CR30 users:
   `hex_support.py:69-70` ("with the SpectroScan selected") and
   `settings_dialog.py:3201-3203`. Both translated. §6.3
10. Stale comments asserting the opposite of the feature —
    `ui/tiff_preview.py:1496-1499`, `ui/tabs/tab_measure.py:4191-4193`
    ("a CR30 chart's square patches"). §6.3
11. A CR30 hexagonal chart built on this branch *before* the fix is now
    actively mis-highlighted: `_apply_hex_stagger`'s legacy fingerprint matches
    it and shifts the boxes ±¼ patch onto ink that was drawn unstaggered.
    Rebuild rather than measure any such chart. §5.4
12. A `.ti2` separated from its `.channels.json` loses its shape.
    `chart_is_hexagonal` fails open and never consults the `.ti2`'s own
    `HEXAGON_PATCHES` keyword, which is written on every hexagonal chart. §5.5
13. `presets.py:413` / `:421` and `layout_options_panel.py:1960` / `:1964`
    duplicate *code* for SS and CR30 where the *meanings* genuinely differ
    (flatbed vs hand-placed). Correct as written; noted so a future tidy-up does
    not merge them into one wrong rule. §2-B5, B6

---

## What I attacked and could not break

* **`hxeh` could never have been the capability, and the code says so.**
  `build("CM", cm_stagger=True)` gives `hexagonal=False` with `hxeh = 3.5`
  (`instruments.py:304-305`). The explicit `Geom.hexagonal` flag is the right
  call and `instruments.py:151-152` records the reason. `hxew` happens to track
  `hexagonal` exactly across all seven instruments today, but it is a float
  answering a shape question and the CM precedent shows how that ends. §1.1
* **The flag survives every path a `Geom` takes.** `build()`'s `replace()`
  (`:317`) carries it; the only other `replace()` on a `Geom` in the tree is
  `raster.apply_furniture_reserves` (`:362`), which touches two furniture
  fields. §1.1
* **The renderer and the recorded rects cannot diverge.** They compute the same
  `±¼·(px(x+pwid) − px(x))` from the same parity index, and now share one
  predicate. Both blockers of report 05 were fixed in one change, as required.
  §3.3
* **The whole `recipe_is_hexagonal` chain generalised for free** — margin
  inspector, scanin sample cap, scanner/camera refusal, measure zigzag, marquee
  cells, legacy-sidecar compensation. `hex_max_sample_fraction` derives the cap
  from `w`/`h` alone, and a CR30 hexagon's `h/w` is 0.866, identical to the
  SpectroScan's, so both get the same 64.4 % ceiling. §2-A10
* **`HEXAGON_PATCHES` is doubly unreachable on a CR30 read.** In
  `chromiq_chartread.c`, `hex` is used only at `:1753` inside `rmode == 2`
  (`:1541`) — motorised XY navigation vectors — and a CR30 both requires `-x`
  (`:3711-3720`) and never enters the `check_mode` block that could set `rmode`
  (`:918`), so `rmode` stays 0 (`:908`) and the read goes to spot mode
  (`:2600`). §2-B7
* **The printtarg-side gates were correctly left as instrument identity** —
  `settings_are_hexagonal`, the `-h` argv, the command preview, the Manual `-h`
  widget. A CR30 chart can only ever be an engine chart
  (`ENGINE_ONLY_INSTRUMENTS`). §2-B
* **Backward compatibility is exact.** A SpectroScan chart's TIFF and
  `.strips.json` are byte-identical to `master`, flat and hex; 864 capacity /
  geometry combinations and 240 resize combinations across the six pre-existing
  instruments show zero differences. §5
* **The tests are real.** Ten deliberate breakages, each verified to land; all
  ten caught. The `collect_device_geom` shape record and
  `HEX_INSTRUMENTS = hex_capable_instruments()` are the two decisions that make
  that true. §4

---

## Concrete changes

Each is actionable without re-deriving anything above.

1. `ui/tabs/tab_chart.py:11530` — add a `CR30` arm to `_engine_geom` mirroring
   `chart_creator._engine_build_kwargs:1183-1206`: `kw["hflag"] = bool(dd)`,
   `kw["layout_mode"] = "patch_first"`, and (Guided only) `spacer_on=False` /
   `spacer_mode="none"`. Verify against §3.1's table: the readout must read 345
   with the box clear and 405 with it ticked. **Finding 1.**
2. Add one parametrised test asserting `tab_chart._engine_geom(...)` and
   `chart_creator._engine_build_kwargs(...)` produce the same
   `patches_per_sheet` for every instrument in `chart_creator.ENGINE_INSTRUMENTS`
   and every mode. This is the `GEOM_BUILD_KEYS` contract, currently unpinned.
   **Findings 1, 7.**
3. Route the seven flat/hex lists through `instruments.hex_capable()`:
   `presets.LayoutRecipe.mode()` (`:171-177`), `default_recipe` (`:451`),
   `factory_defaults` (`:523-525`), `layout_options_panel.mode_label_for`
   (`:90-95`), `modes_for` (`:177-181`), and give `mode_tooltip_for` a hex
   fallback. `_update_dd_visibility` (`tab_chart.py:11803-11895`) keeps its
   per-instrument prose but should decide *visibility* from `hex_capable`.
   **Finding 2.**
4. `presets.LayoutRecipe.mode()` specifically — make the hex arm
   `if hex_capable(self.instrument): return "hex" if self.hflag else "flat"`
   **before** the `return "default"`, so a new hex instrument cannot collide its
   two preset keys. **Finding 2.**
5. Widen `rlwi` for the CR30 (or cap the row-number font to the band) so a
   two-digit number fits inside 7.5 mm at a 12 mm cell — measured need is
   ≥ 8.43 mm of text plus the 1 mm gap plus, on a honeycomb, the 3.0 mm
   `_protrude`. Whichever way it is fixed, add the assertion "the row number
   starts at or right of `margin_l`". **Finding 3.**
6. Re-measure the four capacity claims and rewrite them as a range:
   `tab_chart.py:11836` (checkbox label), `:11848` (Guided tooltip),
   `layout_options_panel.py:142` (Manual tooltip), `presets.py:175` (comment).
   Numbers to use: A4 portrait 345 → 405 (+17 %), A4 landscape 368 → 396,
   A3 782 → 836 (+7 %). Do it **before** the German pass. **Finding 4.**
7. Force-uncheck `_dd_check` on every instrument change whose *meaning* changes,
   not only when it is hidden (`tab_chart.py:11888-11891`), or split the
   persisted key so CM's `chart_double_density` and the SS/CR30 shape are two
   settings. **Finding 5.**
8. Parametrise the five hex tests in `tests/test_layout_raster.py`
   (`:75-90`, `:510`, `:527-532`, `:647`, `:653-656`) over
   `instruments.hex_capable_instruments()`, exactly as
   `tests/test_hex_overlay_geometry.py:38` already does. `:647` first — it is
   the one that finds finding 3. **Findings 6, 3.**
9. `tab_chart.py:11568` and `:11615` — replace `instrument == "SS"` with
   `hex_capable(instrument)` so the info line names the shape on any hexagonal
   chart. **Finding 8.**
10. `workflow/hex_support.py:69-70` — drop "with the SpectroScan selected" from
    `hex_scanner_message()`; the sentence works without it. And
    `ui/dialogs/settings_dialog.py:3201-3203` — say "for the SpectroScan and the
    CR30", or better, "for instruments that offer it". Both are translated:
    change them in the same pass as change 6. **Finding 9.**
11. `ui/tiff_preview.py:1496-1499` and `ui/tabs/tab_measure.py:4191-4193` —
    correct the "a CR30 chart's square patches" comments; a CR30 chart may now
    be a honeycomb, and `set_no_swipe` is about swiping, not shape.
    **Finding 10.**
12. `workflow/hex_support.chart_is_hexagonal` — fall back to the `.ti2`'s
    `HEXAGON_PATCHES` keyword when no `.channels.json` is found, so a chart
    imported as a bare `.ti2` is not measured as if it were rectangular.
    **Finding 12.**
13. Adopt §5.2 and §5.3 as a test: build every
    `{instrument} × {paper} × {hflag} × {density} × {pscale} × {cm_stagger}`
    geometry and pin `patches_per_sheet`, `hxeh`, `hxew`, `plen`, `pwid` to a
    stored table. 864 combinations run in under a second and would have made
    this whole backward-compatibility section a one-line check. Probe scripts
    are in the scratchpad and are directly reusable.
14. Tell Basti and Knut to **rebuild, not measure**, any CR30 hexagonal chart
    made on this branch before the fix — its sidecar rects are unstaggered and
    `_apply_hex_stagger` will now shift them onto ink that never moved.
    **Finding 11.**

STATUS: complete

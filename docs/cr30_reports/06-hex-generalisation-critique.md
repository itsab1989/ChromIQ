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


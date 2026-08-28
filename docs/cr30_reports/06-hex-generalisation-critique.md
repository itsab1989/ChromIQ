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


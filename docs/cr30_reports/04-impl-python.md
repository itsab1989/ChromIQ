# CR30 implementation — Python side — [CR30-IMPL-PY]

STATUS: in-progress
Branch: `feature/cr30-instrument-159`
Started: 2026-08-28

Companion to `01-surface-map.md` (task list), `02-design.md` (frozen design) and
`03-design-critique.md` (**the corrections; where design and critique disagree,
the critique wins**).

Scope boundary: the C side (`native/**`), the vendored driver
(`workflow/cr30/**`), `workflow/measure_manager.py` and
`workflow/chartread_engine.py` belong to **[CR30-IMPL-C]** and are NOT touched
here. Requests for changes in those files are collected in §R at the end.

---

## T1 — geometry  ✅

### The CR30 `_build_base` branch (`workflow/layout_engine/instruments.py`)

A branch **of its own**, not an SS copy — following critique B1/G6, not §3 of the
design. Every field is justified in a block comment in the source; the decisions
that differ from the design are:

| Field | Design said | Shipped | Why |
|---|---|---|---|
| `pspa` | "Spacers: **none**" | **`spacer(1.3)`** | The only hardware-proven CR30 read (`EXP-SPEC-001a`) used the ColorMunki extra-high sheet, which sets `pspa = pscale * 1.3` (`instruments.py:433`). Removing the one geometric feature present in the only proven layout would be inventing a geometry. Routed through `spacer()` so `-n` still turns it off **and** so build()'s Manual "spacer width" box stays live — that box is silently ignored when `pspa == 0` (`:218-219`), which is exactly what an SS copy would have produced. |
| `tspa`, `lcar` | (from SS, `0.0`) | `0.0` | Same value, **different derivation**. SS's zeros come from it being a motorised flatbed whose head is machine-positioned. Ours come from there being no swipe at all: a hand needs no run-in or run-out. |
| `rlwi` | not mentioned | **`7.5`** | The genuinely good SS argument (critique B1). `raster.py:1215-1233` draws row **numbers** in this reserved band; with the column letters that gives the sheet a 2-D `A1/A2/B1` coordinate. Finding one patch among several hundred by hand is the CR30's whole ergonomic problem. |
| `padlrow` | — | `False` | Padding the last column with blank patches exists so a strip reader traverses a full-length strip. No strip here; blank patches are paper the user pays for. |
| patch | 10.0 × 10.0 provisional | same, `rrsp == pwid` | 2.5× the 4 mm aperture — the same patch:aperture ratio the i1Pro uses (`:371-372`). Columns touch, which is the topology `EXP-SPEC-001a` proved. **Not a measured minimum** (`EXP-MEAS-005` measured repeatability, not tolerance); labelled provisional in the UI — see T2. |
| `mxrowl` / `ruler_mm` | — | `MAXROWLEN` / `0.0` | No ruler, no jig, as CM and SS. |

Also added: `TARGET_INSTRUMENT_NAME["CR30"] = "CR30"` (with the stock-chartread
consequence written at the constant), `supported()`, `_MARGIN_LABEL_TO_KEY`.

### The clip band — code and UI made to AGREE, by making it real

The design says the clip band is *"off by default, offerable"*; the critique
measured it **inert** (`lbord 0.0`, `has_clip_border False`). Resolved in the
design's favour rather than the critique's, because the critique objects to the
*silence*, not to the feature: `("CM", "SS")` → `("CM", "SS", "CR30")` at
`instruments.py:311-315` **and** at the three UI gates
(`layout_options_panel.py:1857, 1946, 2289` — see T2). Measured after the change:
`clip_content_mode="notes"` → `lbord = 20.0`, `has_clip_border = True`, A4
capacity 475 → 425.

Rationale: the band is a **notes** band, not a physical clip. A CR30 sheet is
hand-read for up to half an hour, so a band naming the run is worth *more* here
than on a strip chart, not less. It stays **off by default** (`default_recipe`).

### Measured capacity (this branch, `geometry.compute`)

| Paper | mode | patch | grid | patches/page |
|---|---|---|---|---|
| A4 | `patch_first` | 10.00 × 10.00 | 19 × 25 | **475** |
| A4 | `area_first` | 10.02 × 10.15 | 19 × 25 | 475 |
| A3 | `patch_first` | 10.00 × 10.00 | 27 × 36 | **972** |
| A3 | `area_first` | 10.27 × 10.39 | 27 × 35 | 945 |
| A4 | notes band on | 10.00 × 10.00 | 17 × 25 | 425 |

### `layout_mode` chosen explicitly (critique B2 / G7)

`presets.default_recipe` sets **`patch_first`** for CR30. The table above is the
argument: `area_first` floats the patch to 10.27 × 10.39 mm on A3 and to
something else on every other paper, so the "provisional 10 mm" the UI labels
would be a lie and the user would not know what size they are aiming at.

### Other layout-engine registrations done with T1

- `presets.SUPPORTED_INSTRUMENTS` += `"CR30"`; `LayoutRecipe.mode()` → **`"spot"`**
  (named rather than left to the `"default"` fallthrough, so the preset key reads
  `CR30|A4|spot`); `factory_defaults()` ships `["spot"]` → one preset,
  `CR30|A4|spot`. Verified.
- `default_recipe` also sets `clip_content_mode = "off"` (with CM/SS).
- `build_kwargs()` **edge_spacers**: CR30 deliberately NOT added to the
  `("i1","p3","CM")` tuple — there is no strip to bracket, and leaving it out
  reclaims the two end gaps for patches. Verified `False`.
- `chart.py::_instr_friendly` += `"CR30": "CR30"` (a no-op against the `.get`
  fallback; listed so the table is a complete answer, not a coincidence).
- `papers.ENGINE_EXCLUDED_PAPERS`: **no entry, deliberately**, with the reasoning
  in the source — the existing exclusions are mechanical (a 20 mm p3 patch on a
  4×6 card; the SS table vs A2 landscape) and a hand-placed device has no
  mechanism to be limited by.

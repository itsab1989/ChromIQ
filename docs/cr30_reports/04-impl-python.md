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

## T2 — the registrations  ✅

Worked through `01-surface-map.md` §12 file by file. Everything below is done
unless it is in §U (unfinished) at the end.

| File | What was registered |
|---|---|
| `workflow/layout_engine/instruments.py` | `TARGET_INSTRUMENT_NAME`, `supported()`, `_MARGIN_LABEL_TO_KEY`, the clip-band gate, the `_build_base` branch, the hex capability |
| `workflow/layout_engine/presets.py` | `SUPPORTED_INSTRUMENTS`, `mode()`, `default_recipe`, `factory_defaults` |
| `workflow/layout_engine/chart.py` | `_instr_friendly` |
| `workflow/layout_engine/papers.py` | no exclusions, with the reasoning in the source |
| `workflow/chart_creator.py` | `ENGINE_INSTRUMENTS`, new `ENGINE_ONLY_INSTRUMENTS`, `_should_use_engine`, `_engine_build_kwargs`, `_build_printtarg_args` |
| `data/patch_db.py` | `INSTRUMENT_LABELS`, `INSTRUMENT_MODEL_WORDS`, **and the hand-maintained tuple in `instrument_family_of`** — an entry in only one of the last two is silently blind |
| `ui/ti2_loader.py` | `KNOWN_INSTRUMENTS`, new `spectral_options_unavailable`, bidir docstrings |
| `ui/dialogs/layout_options_panel.py` | `INSTRUMENTS`, `mode_label_for`, `mode_tooltip_for`, `modes_for`, the three band gates, `_instr_friendly`, the patch-first default on a user switch, **and the "Spacer size" enable fix** |
| `ui/dialogs/settings_dialog.py` | `_MARGIN_INSTRUMENTS`, `_LAYOUT_INSTRUMENTS`, the pace `labels`, its own CM/SS band gate |
| `core/settings.py` | `THRESHOLD_INSTR_LABEL` |
| `core/measure_pace.py` | `MODEL_DEFAULTS`, `ESTIMATE_PATCHES`, `_ARGYLL_MODEL_KEYS`, `explanation_for` |
| `ui/tabs/tab_chart.py` | `_MARGIN_INSTR_LABEL`, `_suggest_target_name`, the Guided tooltip (as a SEPARATE key), the Guided `-h` checkbox, the hex heads-up, the helper-marker gate, **the two `("i1","p3","CM","SS")` tuples** |
| `ui/dialogs/ti2_relayout_dialog.py` | the name map (`ENGINE_INSTRUMENTS` filter was already free) |
| `ui/tabs/tab_profile.py`, `ui/tabs/tab_check_refine.py` | the FWA / illuminant / observer gate |
| `ui/tabs/tab_measure.py` | the CR30 guard, the repair path, the swipe-arrow suppression |
| `workflow/ti2_relayout.py` | `instrument_to_flag` |
| `data/parameters.yaml` + 12 overlays | the `-i` choice, its label and its tooltip bullet |
| `data/i18n/*.json` ×12 | English placeholders; German for the §M message (a hard gate — see below) |

### Decisions inside T2 worth stating

**FWA is gated off, and by a better test than the one asked for.** The surface
map asks for `is_colormunki(...) or is_cr30(...)`. Shipped instead:
`ui/ti2_loader.spectral_options_unavailable(name, has_spectral)`, which gates on
**either** an instrument whose light cannot excite optical brighteners **or a
measurement with no spectral columns at all**. Both tabs already computed and
stored `_detected_has_spectral` and their own docstrings proposed exactly this
("*this can later become `not self._detected_has_spectral`*"). It matters
because of critique **A3**: while the `.ti3` still says `"Unknown Instrument"`,
the instrument-name half of the test cannot see a CR30 — the spectral half
still closes the hole. FWA, illuminant and observer are all computed *from* the
spectral curve, so this is correct for every instrument, not a CR30 special
case. It changes behaviour for one existing case: a spectra-free `.ti3` from any
instrument now gates them too. Full suite green.

**`EXTERNAL_INSTRUMENTS` was rejected for T3** — see T3.

**The Guided instrument tooltip is a ~1,200-character single `tr()` key.** The
CR30 bullet is **appended as its own `tr()` key** (`tab_chart.py`, string
concatenation) rather than merged, because editing that key fails
`test_i18n.py` 24 times (12 stale + 12 missing). Same technique for the CR30
sentence appended to `hex_scanner_message()`.

**German is not optional for a §M headline.**
`test_i18n.py::test_the_catalogue_is_actually_translated_into_german` asserts
`tr(msg.title) != msg.title` for **every** catalogue message, so an English
placeholder fails. `M-CR30-STOCK-READER` therefore ships with a real German
title *and* body; every other new key is an English placeholder in all 12
catalogues, per the brief.

## T3 — engine-only enforcement  ✅

`ENGINE_ONLY_INSTRUMENTS = {"CR30"}` (`chart_creator.py`), enforced twice:

1. **`_should_use_engine` returns True for a CR30 before every other test** —
   ahead of the Manual `use_chromiq_layout_engine` setting and both legacy
   printtarg clip flags, each of which can otherwise route a chart to printtarg.
2. **`_build_printtarg_args` raises** for an engine-only key instead of emitting
   `-iCR30`. This is what makes the route *unreachable* rather than merely
   unused: a lost guard fails loudly instead of shelling out to a tool that
   answers "Unsupported instrument type".

Also: `_engine_total_patches` **re-raises** for an engine-only instrument
instead of returning `None`. Returning None falls through to `query_patches` →
`_binary_search` → printtarg, so swallowing the error could only produce a wrong
number or bury the real reason under printtarg's refusal.
`tab_chart.py:12339` already catches and shows it.

### Forcing the engine, NOT `EXTERNAL_INSTRUMENTS` — and why

Both were on the table (critique G5). `EXTERNAL_INSTRUMENTS` **hides its members
from the Guided instrument combo** (`tab_chart.py:3406-3408`), and rightly so —
for an i1iSis the layout is recomputed by i1Profiler, so Guided has nothing to
optimise. A CR30 chart is ours to lay out, and Guided is exactly where a
first-time user picks the device. Filing it there would have removed it from the
one screen it most belongs on. Recorded in the source at `patch_db.py`.

## T4 — the Measure tab, and the price of the honest name  ✅

`"CR30"` had to go into `KNOWN_INSTRUMENTS`, or
`_blocked_by_unusable_target_instrument` refuses every CR30 measurement. But
with it there, that guard's claim ("*ArgyllCMS … does not know this one*") is
silenced for the one case where it is **still true**. So the question is split
in two, and each guard answers only its own half:

| Guard | Asks | CR30 chart |
|---|---|---|
| `_blocked_by_unusable_target_instrument` (existing) | does **ChromIQ** know this name? | passes |
| `_blocked_by_stock_chartread_for_cr30` (**new**, runs first) | can the **selected reader** use it? | blocks when `chartread_engine == "argyll"` |

The new window **offers the switch** rather than only naming the setting: it is
in Preferences → Measurement, several clicks from a user who has just pressed
Start, and there is exactly one right answer for this chart. Declining cancels —
a measurement that cannot succeed must not begin — and declining does **not**
touch the setting.

**§M procedure followed in one commit**: `M-CR30-STOCK-READER` in
`unified_measurement_management.md` §M-PROPOSED (with the `> **headline**` line
and the opening "Awaiting review" note updated), `approved=False` in
`measurement_messages.CATALOGUE`, and the ID in `AWAITING_APPROVAL`.
The window is registered in `WINDOW_SOURCES` too, so
`test_the_window_takes_its_text_from_the_catalogue` covers it.

⚠ One structural note: `test_the_window_writes_no_prose_of_its_own` forbids any
`tr()` literal over 60 characters in a catalogued window. The guard's two **log**
lines are sentences, and a log line is not window prose — so the window is split
out as `_cr30_stock_reader_window()` (catalogue text + two button labels only)
and the logging stays in the guard. That is the shape the test is asking for.

Told at chart creation as well as measure time: the Guided instrument tooltip,
the `parameters.yaml` `-i` tooltip and the layout panel's shape tooltip all say
that a CR30 chart can only be read by ChromIQ.

## T5 — margins and pace  ✅

- `_MARGIN_INSTRUMENTS` (`settings_dialog.py`), `THRESHOLD_INSTR_LABEL`
  (`core/settings.py`) and `_MARGIN_INSTR_LABEL` (`tab_chart.py`) all carry
  `"CR30" → "CR30"`. That closes the silent-wrongness trap at
  `tab_chart.py:16174`, where `.get(flag, "i1Pro")` was judging a CR30 chart
  against the i1Pro's 38 mm top margin.
- **No `_MARGIN_SEED` rows, deliberately.** The SpectroScan is in exactly the
  same position: in the picker, with nothing seeded, so
  `thresholds_for_combo` returns None and `check_violations` returns `[]`. No
  aperture or positioning data exists for a CR30, so checking nothing is the
  honest answer, and a threshold can still be set by hand.
- **Pace follows the SpectroScan precedent**: `MODEL_DEFAULTS["cr30"] =
  (100.0, None)`, `ESTIMATE_PATCHES["cr30"] = None`, `_ARGYLL_MODEL_KEYS` +=
  `("cr30", "cr30")`, a `labels` row and an `explanation_for` branch. `None`
  renders as **Off**, `None` patches as **N/A**. No swipe concept invented.
  The rate is inert in both directions (nothing subscribes to patch events for
  pace, and the CR30 does not stream samples); it is 100.0 rather than 0 or 1
  only so the Preferences spinbox shows the shipped default instead of
  clamping it to the bottom of `SAMPLE_HZ_RANGE`. **The row's real job** is
  closing `_pace_config`'s unknown-instrument fallback to the i1Pro's
  `(100.0, 20)` — proved by a test.

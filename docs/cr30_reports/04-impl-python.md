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

## R1 / R2 / the chart critique — the rulings that arrived mid-task

### R2 — spacers OFF by default, and still turnable on  ✅

Basti, 2026-08-28, final. This **reverses the T1 decision above** (the critique's
"keep a spacer"); the ruling wins and T1's table should be read with that in
mind. What was implemented is the *pair* of requirements, because they pull
against each other:

- **Off by default** — `presets.default_recipe("CR30", …)` sets
  `spacer_mode = "none"`, and `chart_creator._engine_build_kwargs` forces
  `spacer_on=False` for **Guided only** (Manual keeps its own control).
- **Still turnable on** — the geometry keeps a **real 1.3 mm base width**.
  This is the trap: `build()` honours the Manual "Spacer size" box only while
  `geom.pspa > 0` (`instruments.py:218-219`), so a hard `pspa=0.0` would have
  made the spacer off *and un-turn-on-able*, which is exactly what the ruling
  forbids. Proved end to end by a test: default 0.0 → Coloured 1.3 → width box
  2.5 → None 0.0.

**And the control is no longer dead.** `layout_options_panel._sync_spacer_swatches`
now greys the whole "Spacer size" row whenever there is no spacer to size —
either because Spacers is set to None, or because the instrument's geometry has
none at all. The CR30 is the first instrument to ship with spacers off, so it is
the first where a user meets that dead box out of the box. **The same fix covers
the SpectroScan, whose "Spacer size" box has never worked in any mode** because
its geometry hard-codes `pspa = 0.0` (found by the chart critic; fixed here
because it is the same line of code).

No warning or nag about honeycomb visibility was added, per the ruling.

### R1 — hexagonal patches, and the three blockers  ✅

Offered for the CR30 in **every** Create Chart module: the Manual/editor shape
selector (`modes_for` → `flat`/`hex`, label "Patch shape:", its own help text),
the Guided `-h` checkbox (relabelled and retooltipped, as the SpectroScan's is),
`presets` (`mode()`, `default_recipe`, two factory presets `CR30|A4|flat` and
`CR30|A4|hex`), `chart_creator._engine_build_kwargs`, and
`hex_support.recipe_is_hexagonal`.

**Default is RECTANGULAR**, by ruling.

#### The three blockers, and the shape of the fix

The chart critic found that a CR30 honeycomb was **laid out as hexagons and
drawn as squares** — the sheet paid for the apex overhang and shortened rows,
and got rectangles. Three gates each asked `key == "SS"` on their own:
`raster.py:1056`, `geometry.py:475` (patch rects), `geometry.py:669` (helper
markers), plus `tab_chart.py`'s UI gate.

Per Basti — *"we own the layout engine, so you should be able to add the hex
patches to any instrument we want"* — this was fixed as a **generalisation, not
a second name in three tuples**:

- **`Geom.hexagonal: bool`** — an explicit flag the building branch sets about
  itself. **The single source of truth.**
- **`instruments.is_hexagonal(geom)`** — the one predicate; all three gates now
  call it.
- **`instruments.hex_capable(key)` / `hex_capable_instruments()`** — capability
  **probed from the geometry** (`build(key, hflag=True).hexagonal`), not held in
  a list. An instrument offers hexagons exactly when its `_build_base` branch
  honours `hflag`, so adding the shape to a new instrument needs **no second
  registration anywhere** and cannot be half-done. Used by the UI gates in
  `tab_chart.py` and by `hex_support.recipe_is_hexagonal`.

**Why an explicit flag and not `hxew > 0`:** the ColorMunki's row stagger sets
`hxeh` without being hexagonal, so the overhang floats answer a different
question. An explicit flag also says what it means at the call site.

All three fixed in **one change**, as required — fixing the raster alone would
leave a live half-patch mis-registration between what is drawn and what the
Measure highlight, the margin inspector and `scanin_target.py` believe was drawn.

`build()`'s hex-overhang recompute (a resized hexagon keeping its unresized
reservation) is now keyed on `geom.hexagonal` too, so it covers every honeycomb
rather than only the SpectroScan's.

Helper markers: #152's rule ("a honeycomb has no rows to line a ruler against")
now follows the **shape**, not the instrument, in both `geometry.py` and
`tab_chart.py`.

#### Measured, on this branch, at the shipped 12 mm

| Paper | rectangular | hexagonal | gain |
|---|---|---|---|
| A4 | 345 | 405 | **+17.4 %** |
| A3 | 782 | 836 | +6.9 % |

⚠ **These differ from the +8.8 % / +12.5 % in the chart critique**, which was
measured before the 12 mm ruling landed. The gain is strongly paper-dependent,
so the user-facing text quotes the A4 pair concretely and says the gain depends
on the paper, rather than quoting a single percentage.

#### The geometry claim, corrected before it reached the user

The forwarded rationale quoted a hexagon's **+7.5 % inradius / +12 % clearance**
at equal patch AREA. **That is not what this branch ships**, and the numbers
would have been false in the help text. Computed, not quoted:

| | flat-to-flat | area | inradius | clearance round the 4 mm window | A4 |
|---|---|---|---|---|---|
| square, 12 mm | — | 144.0 mm² | 6.000 | **4.00 mm** | 345 |
| hexagon, equal **width** (**shipped**) | 12.000 | 124.7 mm² | 6.000 | **4.00 mm** | **405** |
| hexagon, equal **area** | 12.895 | 144.0 mm² | 6.447 | 4.45 mm | 350 |

So the shipped honeycomb buys **density at unchanged clearance** (the
90.69 % vs 78.54 % circle-packing result), not extra clearance. The equal-area
hexagon buys 0.45 mm of clearance and **loses** the density (350 against the
square's 345 — no gain at all). The two cannot be had at once. Density at equal
clearance is the better trade and is what ships; the swap is a one-line change
(the `12.0` in the `hflag` branch) if hardware ever says otherwise. All of this
is written into the geometry comment.

### The 12 mm cell, and the justification that was wrong

`plen = pwid = rrsp = pscale * 12.0`. **The old comment was factually wrong and
has been removed, not merely edited**: it claimed 10 mm was "2.5× the aperture,
the same patch:aperture ratio the i1Pro uses". The i1Pro's ratio is 10/5 = 2.00
and this one is 12/4 = 3.00 — never a match — and the aperture ratio is not what
governs the size anyway. The shipped reasoning is occlusion: the CR30's body is
a **33 mm opaque disc**, so the patch is invisible the moment it is set down and
the user aims from the cells around it; 12 mm gives 4.00 mm of clearance against
3.00 mm at 10 mm, and sits **above** the only geometry a CR30 has been proven to
read (`EXP-SPEC-001a`, 10.4 × 13.0 mm). Still labelled **provisional** in the UI.

### The too-small-patch guard — built, then REMOVED

Implemented (aperture constant, a 6 mm floor, a plain-language refusal at
`_engine_kwargs`, a per-instrument preflight floor and nine tests), then removed
in full on Basti's ruling: *"if no instrument has it now we leave it out and
don't invent something new here."* Nothing of it remains; `preflight.MIN_PATCH_MM`
is back to the one shared 6 mm **warning** that applies to every instrument. A
comment in the geometry branch records the ruling so it is not re-invented.

### The unmeasured ergonomic claim  ✅

The Guided and panel help text said the honeycomb's six sides "funnel a round
barrel towards the middle" and make it "harder to lose your place" as statements
of fact. Both now say plainly that this is reasoning and **has not been
measured**, next to the packing figures, which have. That dialog is scrupulous
about the same distinction for patch size; it is now consistent.

## T6 — tests  ✅

`tests/test_cr30_registration.py`, **69 tests**, plus the existing hex suite
parameterised over every hex-capable instrument (`test_hex_overlay_geometry.py`,
79 tests, up from 40).

Sections: geometry and every claim its comment makes · spacers off-and-turnable ·
hexagons (geometry, keyword, resized overhang, packing, all four modules) · the
clip band · layout mode · presets · engine-only enforcement · the `.ti2`
identity chain · the FWA gate · pace and margins · the Measure-tab guards ·
**hexagons that are actually drawn**.

### The tests that would have caught the blockers

The chart critic's finding was that the whole existing hex suite was hard-coded
to `"SS"` and `test_cr30_registration.py` asserted only on `Geom` fields — it
never rendered and never inspected a rect. Fixed three ways:

1. **`test_hex_overlay_geometry.py` is parameterised over
   `instruments.hex_capable_instruments()`**, asked of the engine rather than
   listed, so a future hex-capable instrument is covered the moment it exists.
   Its `_hex_geom` helper now derives `pscale` from the instrument's own patch
   width, so a test can ask for "a 20 mm hexagon" without knowing the device.
2. **A render test that asserts on the shape actually drawn**, with the
   SpectroScan as a positive control on the identical path, plus a negative
   control (`i1`/`p3`/`CM` with `hflag=True` must still draw rectangles —
   `-h` means double density on a ColorMunki).
   ⚠ *Pixel corner-sampling was tried first and is unsound*: in a honeycomb the
   corners of a patch's slot are filled by its **neighbours**, so "is the corner
   still paper" is False for a correct honeycomb as well as for the bug. The
   test uses `collect_device_geom`, which records `("hex", …)` / `("rect", …)`
   per patch — the same record the vector PDF and the Tier D device raster are
   built from, and the only unambiguous evidence.
3. **A rect-stagger test**: `patch_rects_px` must yield exactly two alternating
   x values on a honeycomb and one per column on a flat chart, with the offset
   matching the quarter-width the renderer draws with.

### Mutation-proved

Every check below **landed** (asserted in the mutation script) and was **caught**:

| Mutation | Caught by |
|---|---|
| `pspa=spacer(1.3)` → `pspa=0.0` | the two spacer tests |
| `("CM","SS","CR30")` → `("CM","SS")` in the band gate | the clip-band test (and *only* that test) |
| `_should_use_engine`'s engine-only branch disabled | 2 of the 4 engine-only cases |
| FWA gate back to `is_colormunki` only | 2 of the 5 gate cases |
| **`is_hexagonal` back to `key == "SS" and hxew > 0`** (the exact original bug) | **6 tests**: the render test, the rect-stagger test, the helper-marker test and 3 parameterised overlay tests |

### An existing test I changed, and why it is not a weakening

`tests/test_ti2_loader.py::test_known_instruments_registry` pins
`KNOWN_INSTRUMENTS` exactly. `"CR30"` was added to the pinned tuple with a
comment saying why. That test exists so that adding an entry is a **deliberate
act visible in a diff** — which this is — not to forbid additions. Flagging it
here rather than treating it as routine.

`tests/test_hex_overlay_geometry.py::test_a_square_spectroscan_chart_is_unaffected`
was renamed to `…_a_square_chart_…` when it was parameterised over both
instruments; the assertions are unchanged and one was added
(`is_hexagonal(g) is False`).

## Suite state

`QT_QPA_PLATFORM=offscreen pytest -n 8 --dist loadfile`:
**7787 passed, 253 skipped, 3 xfailed, 4 failed.**

The 4 failures are `tests/test_both_readers_raise_the_same_windows.py::
test_the_helper_really_prints_that_line[capability|ccmx_read|ccmx_set|mode_set]`.
**Pre-existing and not mine** — proved by `git stash`ing this entire branch's
Python work and re-running: they fail identically without any of it. They
exercise the compiled helper and belong to [CR30-IMPL-C].

The release gate (`--runslow`) was **not** run, per the brief.

⚠ Eight tests reported `ERROR` at teardown on one `-n 8` run
(`test_qt_message_filter`, `test_preferences_website_link`,
`test_profile_engine_parity`, …). All eight pass in isolation and did not recur;
`BrokenPipeError` in xdist teardown, not a regression.

## §R — Requests for changes in [CR30-IMPL-C]'s files

Not edited by me. Ordered by how much Python behaviour depends on them.

**R-1 — `.ti3` must carry `TARGET_INSTRUMENT "CR30"` (critique A3, G3).**
`chromiq_chartread.c:3636`. While the `.ti3` says `"Unknown Instrument"`,
`tab_profile._detected_instrument` cannot see a CR30, so the **instrument** half
of the FWA gate is blind. The Python side is defended anyway — the gate also
fires on "no spectral columns", which a CR30 `.ti3` always satisfies — but every
other consumer of the identity chain (the measurement report, the wrong-device
warning, `instrument_label`) is reading a lie until this lands.

**R-2 — exclude CR30 from `_engine_should_fall_back`
(`measure_manager.py:537+`, critique B8/G5).** A failed engine run can be
**automatically** relaunched on stock chartread, which for a CR30 chart is a
fatal `Unrecognised chart target instrument`. My guard
(`TabMeasure._blocked_by_stock_chartread_for_cr30`) only covers the deliberate
Preferences setting at **start**; it does not see an automatic fallback
mid-run. Suggested test: `ui.ti2_loader.is_cr30(read_target_instrument(ti2))`.

**R-3 — `patch_by_patch` is a visible per-target checkbox that will read
"off" while a CR30 read is patch-by-patch regardless** (critique B8.2). `-x` is
always spot mode (`chromiq_chartread.c:887`, every `rmode` assignment is inside
`if (xtern == 0)`). Force it, hide it, or explain it. The control is
`ui/tabs/tab_measure.py:11157/11175` (mine) but the decision is yours — tell me
which and I will do the UI half.

**R-4 — where does the CR30 instrument *family* come from in `-x` mode?**
(critique F4.) `_detected_instrument` is fed by the engine's `instrument`
event, which never fires when Argyll opens no device. Until something supplies
it, the CR30 branches already written into `ui/ti2_loader.py`
(`calibration_instructions_html`, `measurement_instructions_html`) are dead code
and every CR30 window shows the generic wording. Cheapest fix on my side: fall
back to the chart's own `TARGET_INSTRUMENT`. Say the word and I will wire it.

**R-5 — two sounds per patch** (critique D6). The CR30 beeps for itself, and
`measurement_window_sounds.md:54-55` already defines a patch-read cue for
patch-by-patch. `--json` gags Argyll's beep, but Argyll never opens this device.
345 patches × 2 beeps needs a decision before a beta tester meets it.

**R-6 — an orphaned `-x` helper** (critique D9/F8). Other instruments' helpers
exit when the device closes; this one has no device.

## §U — Unfinished, risky, or deliberately not done

Numbered, so they can be picked up without re-deriving anything.

1. **`ui/dialogs/welcome_dialog.py` still does not mention the CR30**
   (surface map 5.26). Two prose `tr()` keys list the supported instruments
   (`:764` glossary, `:1044`). Editing either changes the key → 24 `test_i18n`
   failures each, and the brief forbids it. **Deliberately deferred to the
   pre-final translation sweep**, where the keys can be re-cut in one pass.
2. **The 12 parameter overlays carry a stale `tooltip_body` for
   `printtarg -i`.** The English gained a CR30 bullet; the translated bodies did
   not. `test_parameters_overlay_covers_every_parameter` only checks presence,
   so nothing fails — but 12 languages ship an instrument list missing the CR30.
   Predicted by surface map §9.2; a translation-sweep item.
3. **The A4 hex gain (+17.4 %) does not match the chart critique's +8.8 %.**
   Mine is measured at the shipped 12 mm; theirs predates the ruling. The gain
   is strongly paper-dependent (+6.9 % on A3). Worth one confirmation before
   anyone quotes a headline figure.
4. **Whether the hexagon should be sized at equal WIDTH (shipped) or equal AREA
   is a genuine open trade** — density against 0.45 mm more clearance, table
   above. Nobody has a CR30 in front of them. One-line switch, documented in the
   source.
5. **`INSTRUMENT_LABELS["CR30"] = "CR30 (ChnSpec)"` but the `parameters.yaml`
   label is `"CR30 (ChnSpec, patch by patch)"`.** Deliberate (the YAML one sits
   beside "SpectroScan (flatbed)"), but they appear in different places and
   someone may want them identical.
6. **The Manual "Spacer size" box now greys out for the SpectroScan too.** That
   is a fix — its geometry hard-codes `pspa = 0.0`, so the box never worked —
   but it is a **visible change to an instrument outside #159's scope**. Flagged
   deliberately.
7. **The FWA gate now also fires on any spectra-free `.ti3`, for every
   instrument.** Correct (FWA/illuminant/observer are computed *from* spectra)
   and it is what protects the CR30 while R-1 is open, but it is a behaviour
   change beyond the CR30. Full suite green.
8. **`_MARGIN_INSTR_LABEL.get(flag, "i1Pro")` still falls back to the i1Pro for
   a genuinely unknown flag** (`tab_chart.py:16174`). Closed for the CR30 by
   registering it; the general trap is untouched, being out of scope.
9. **No live patch-size feedback in the layout panel.** With the too-small guard
   dropped (ruling), a user can set a 3 mm CR30 patch and only meet
   `preflight`'s 6 mm warning in the Preferences preview. Consistent with every
   other instrument, which is the point of the ruling.
10. **`hex_capable()` calls `build()` on every query.** Cheap (a dataclass
    construction, no I/O) and called from UI event handlers, not paint paths.
    Noting it because it is a probe, not a lookup.
11. **`settings_are_hexagonal()` (`hex_support.py`) is still SpectroScan-only.**
    Correct: it detects **printtarg**-drawn hexagons from recorded Create Chart
    settings, and a CR30 chart is engine-only, so it always has a recipe and
    never reaches that path. Left alone deliberately.
12. **Nothing in the reading path was implemented** — that is the C work, by the
    brief. Everything above assumes the `-x` route is made to work
    (critique A1/A2).

STATUS: complete

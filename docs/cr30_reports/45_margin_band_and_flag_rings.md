# 45 — The margin band and the flag rings (beta-3)

**Status: COMPLETE.** Both of Basti's on-screen faults challenged, decomposed
and re-measured; every claim below is tagged **PROVEN** (something was run and
its output is quoted) or **INFERENCE** (read from code, not executed).

Inputs: Basti's screenshots on the Desktop (his filenames are the fault
statements), his driver `scripts/drive_cr30_left_margin_and_flag_rings.py`,
its screenshots in `~/Desktop/cr30-margin-and-rings/`, and the driver's
surviving sandbox chart
(`$TMPDIR/chromiq_cr30_margin_4einbno7/ChromIQ/cr30-margin/runs/run1/`).
Nothing was driven on screen for this report — the geometry questions were
answered through the engine's own API on the driver's own generated chart, and
the widget questions on the real `TiffPreview` offscreen. `~/ChromIQ` and the
plist were not touched.

---

## Fault A — "margins left was set to 1mm but measured says 8,6mm"

### The single most important new fact

**Basti's screenshot is not the driver's chart.** The panel in his screenshot
shows *Hexagonal — denser*, 26 strips × 44 rows, 1144 patches, patch size
7.45×6.52 mm, strip length 288.6 mm, and the red warning *"Top margin is too
small for the strip labels — they overflow toward the page edge."* That
warning is emitted **only for `area_first` charts**
(`ui/tabs/tab_chart.py:16374` returns early otherwise), and `area_first`
switches the engine into **margins-are-law mode**
(`workflow/layout_engine/instruments.py:385`: `law = area_first or
use_instrument_margins`). **PROVEN** by rebuilding that recipe (CR30 or SS,
hex, area-first by-grid 26×44, margins T6 R2 B1 L1): the engine reproduces his
panel — patch 7.52×6.51 (his "estimate" column verbatim), strip length 288.6,
and margins where right/top/bottom track the boxes within hex-apex/stagger
rounding (R 2.2, T ~6.7, B ~1.7) **while the left alone is box + 7.5 mm**.

So his chart was running in the one mode whose written contract
(`geometry.py:74–84`, Knut's words: *"the patch area is exactly the
page-margin box — no hidden leader/trailer/clear-area, no label/text
reserve"*) says the left should have been 1.0 — and three of his four margins
kept that contract. The row-label band is the only furniture that escapes it:
`compute()` subtracts `rlwi` from `avail_w` unconditionally
(`geometry.py:125`) and `placement()` adds it to `x0` unconditionally
(`geometry.py:294`), law mode or not. **PROVEN**: building the driver's recipe
with `use_instrument_margins=True` still gives `x0 = 8.5 = margin_l 1.0 +
rlwi 7.5`.

The driver's own chart (patch-first, default mode) shows the same left offset
for a *different* reason — see A1.

### A1. Is "outside the margin" actually wrong?

Two different answers for the two modes, and Basti hit the mode where it is
wrong.

**In margins-are-law mode (area-first, or "Use instrument margins"): wrong,
by the mode's own contract.** The contract quoted above is Knut's; the top
strip-label band already obeys it (labels live inside the top margin, slide
toward the page edge, and flag a violation when the margin is too small — the
exact warning Basti's screenshot shows). The row-label band is the one reserve
that was never taught the rule. **PROVEN** (x0 unchanged under law).

**In the default printtarg-style mode: consistent, and merely unexplained.**
The default mode's own documented model (`geometry.py:86–89`) is that
furniture is reserved *outside* the margins — the top label band (7.0 mm) is
reserved outside `margin_t` in exactly the same way (see A2), and printtarg
itself places the SpectroScan row-label band outside `-m`. The engine's
SS geometry is pinned to printtarg parity ("verified 161/161" per
`workflow/chart_creator.py`), so silently moving the band inside the margin in
default mode would break a tested invariant. **INFERENCE** from the code and
its comments; the 161/161 figure is quoted, not re-run.

**Does the clip precedent generalise?** Knut's beta-13 ruling (commit
`2d2656bb`, 2026-06-28) is written as a *model*, not a clip-only patch: *"the
patch area is governed by the page margins alone"*, with the UI flooring the
clip-side margin at the band width so printtarg parity survives at defaults.
That model generalises naturally to `rlwi` — but Knut applied it only where he
was looking (the clip), and the row-label band came later in #93. Nothing in
`docs/design/` covers chart-layout margins at all (**PROVEN** — searched; the
only "margin"/"row label" hits are a UI label in
`verification_printing_and_target.md` and per-target settings vocabulary), so
there is no binding specification either way. **Verdict: the law-mode fix
honours Knut's recorded reasoning (both the law contract and the clip model
point the same way); extending it to the default mode would change layouts and
break printtarg/SS parity, and that is the owner's call — the default there is
change nothing.**

### A2. The other three margins — decomposed, none is a second fault

For the **driver's chart** (patch-first CR30, square 12 mm, A4, margins
L1 T6 R2 B1), re-measured through the app's own `measure_from_engine` on the
app's own `channels.json` and decomposed from the engine's own `Geom`
(**PROVEN**, exact to the quoted 0.01 mm — the residue is 300 dpi pixel
rounding, 0.085 mm/px):

| edge | set | measured | decomposition | class |
|---|---|---|---|---|
| Left | 1.0 | 8.47 | 1.0 margin + **7.5 row-label band** | reserved band outside the margin (fault A) |
| Right | 2.0 | 9.51 | 2.0 margin + **7.5 column-quantisation leftover** (avail 199.5 mm, 16 × 12 mm columns = 192) | correct-and-unexplained |
| Top | 6.0 | 16.51 | 6.0 margin + **7.0 strip-label band** + **3.5 vertical centering** | band = same class as left; centering = documented default |
| Bottom | 1.0 | 4.48 | 1.0 margin + **3.5 vertical centering** | correct-and-unexplained |

Notes, each verified numerically against `compute()`/`placement()`:

- The **right** figure equalling `rlwi` is a numeric coincidence (199.5 − 192
  = 7.5). The leftover lands on the right because the default
  `patch_area_align = "center-left"` anchors the block left; "center" or
  "right" would move it. Not a fault.
- The **top/bottom 3.5 mm each** is the same alignment default splitting the
  7 mm row-quantisation slack evenly (fv = 0.5). Not a fault.
- The **top band** (7.0 mm = `label_band_mm`, the rendered strip-label height)
  is the vertical twin of the left band: furniture outside the margin in
  default mode, inside it under law. Same class as fault A, same verdict
  per mode.
- `hxew`/`hxeh` play no role in the driver's chart (square, both 0). On
  Basti's hex chart they explain the residual ±0.7 mm on top/bottom (apex =
  h/6) and cancel on the left (block start +hxew, stagger −hxew) — which is
  why his left is *still* exactly margin + 7.5.

**No second geometry fault hides here.** The one additional genuine fault
found is fault A's own sharpest form: the law-mode contract violation above.

### A3. What should the user see?

Options, with measured layout cost (charts built both ways through
`geometry.compute`, **PROVEN**):

| | option | layout cost | risk |
|---|---|---|---|
| 1 | **Law mode: band inside the margin** (patches start at `margin_l`; row numbers render inside the left margin, sliding toward the page edge, with a "Left margin is too small for the row numbers" warning below the preview when `margin_l` < what they need — the exact mirror of the existing top-label rule) | Basti's chart: same 26×44 = 1144 patches, each grows 7.52 → ~7.81 mm (+4% usable width); patch-first law charts gain up to one column | changes law-mode layouts for SS + CR30; golden tests to update; **no** printtarg-parity risk (parity is a default-mode property) |
| 2 | **Default mode: explain, don't move** — in "Measured from Preview": rename the rows to what they measure ("Left (to first patch)"), and add indented band lines when non-zero: "row-number band 7.5 mm" under Left, "strip-label band 7.0 mm" under Top; extend the panel's info card | zero | none |
| 3 | Default mode: band inside margin everywhere, floor the left-margin box at `rlwi` (full clip model) | at default 6 mm margins A4/CR30: 345 → 368 square (+23), 405 → 432 hex (+27); at Basti's margins ±0 | breaks SS printtarg parity (161/161) and every SS/CR30 golden layout; band unrenderable below 7.5 mm without the same overflow rule |
| 4 | Clamp the margin control's minimum at ~8.5 | zero | dishonest: the box genuinely governs where the *band* starts (page-edge white before the row numbers), and clamping forbids layouts that print fine today |

**Recommendation: 1 + 2 together.** 1 fixes the case Basti actually
reproduced (his chart was law mode, and law mode promises the box); 2 fixes
the comprehension gap in the mode where the geometry is right. 3 is the full
Knut model but pays for it in broken parity for no complaint anyone has made;
4 is a lie. Option 1 changes chart layouts and therefore **needs the owner's
go-ahead before implementation** (no design doc governs it; Knut's recorded
reasoning supports it but he is not here to confirm).

### A4. Reach

- **SpectroScan: yes, identically.** Same `rlwi = 7.5`; **PROVEN** — SS with
  the driver's margins gives the same `x0 = 8.50`, and Basti's own chart
  rebuilds identically as SS or CR30.
- **Guided: yes.** Guided always routes through the engine
  (`chart_creator.py:1096`, Sebastian #170: Guided *"should never use
  printtarg"*), lists the CR30, and uses the same `placement()`.
  **INFERENCE** (code path read, not driven on screen).
- All other instruments have `rlwi = 0` — untouched by any option above.

---

## Fault B — "red overlays for flagged patches are partly covered"

### B1. Cause confirmed; scope narrower than feared

The loop (`ui/tiff_preview.py:2506` `for rect, c_exp, c_meas, warn in
items:`) fills each patch *and* draws its warn ring in the same iteration —
cause confirmed by reading it and by measurement below. But the two branches
differ structurally:

- **Hex branch**: the ring is stroked *on* the hexagon path
  (`painter.drawPath(hexp)` with a centred pen), so half the pen lies outside
  the patch — in territory the tessellating neighbour fills. A neighbour drawn
  later covers it. **PROVEN**: on the real widget, real chart TIFF, two
  adjacent slots, 146 pixels differ between the two draw orders, 37 of them
  ring-red only when the flagged patch is drawn last
  (`scratchpad/probe_rings.py`; Basti's 592/144 is the same result at
  Retina dpr 2).
- **Rect branch**: the ring is deliberately inset so its outer edge lands
  exactly on the fill box (`inset = hw/2`, the Sebastian drift fix), i.e.
  wholly inside the patch's own rectangle. **PROVEN immune**: same probe,
  rectangles, both vertical and horizontal adjacency (shared-edge boxes, so
  "too far apart to touch" is excluded): **0 differing pixels**.
- **The other overlays are safe by paint order**, not by luck: the
  current-patch ring (`#1f8f6b`), the spot-mode hover outline, and the strip
  hover outline are all drawn *after* the items loop
  (`tiff_preview.py:2619–2716`), so no fill can cover them. **INFERENCE**
  from code order (each is unconditional follow-on painting in the same
  function). The white unread-cover and cell grid are drawn *before* the
  items loop — also safe.

So the fix is **local to the items loop**, not a whole-paint restructure —
but within that loop it must be structural (two passes), because:

**No ordering fixes it.** With two *adjacent flagged* hexagons, a ring loses
pixels whichever item is drawn last — **PROVEN**: 187 differing pixels, 38
ring-red lost in *each* direction. "Sort flagged items last" would fix single
flags and silently fail exactly where two neighbouring patches both misread —
the likeliest real cluster.

### B2. Is two-pass (all fills, then all rings) correct and sufficient?

**Yes.** Pass 1: fill/split + the 1 px seam stroke per item (hex) or the
snapped `fillRect`/triangle (rect). Pass 2: halo + ring for every `warn`
item, same geometry as today.

- *Rings over fills*: a ring overhanging its neighbour's fill by half a pen
  width is precisely the appearance of today's flagged-drawn-last render —
  the render Basti's own probe (and mine) treats as the correct baseline, and
  the point of the white halo (Sebastian: unmistakable on any patch colour).
  Nothing new is lost.
- *Two adjacent flagged patches*: their ring paths coincide exactly along the
  shared hexagon edge (tessellation), so red overprints red there; the later
  halo whitens a sliver either side of the shared edge. Both rings remain
  complete around their perimeters. Acceptable — and strictly better than
  today, where one of them is guaranteed mutilated. **INFERENCE** (geometry
  of coincident paths), pinned by the order-invariance test below rather than
  by a pixel-count claim.
- Keep the rect ring in pass 2 as well: proven unaffected today, but one rule
  ("fills never paint after rings") is the invariant worth having.

### B3. Screen only — the export is clean

**PROVEN** (by finding the actual artefact): Basti's screenshot is the live
Measure-tab preview — it carries `TiffPreview`'s screen-only legend chip
("expected ◤ · measured ◢ (screen colours approximate)"), the dark app frame
and window title; the vertical "targen … | ChromIQ layout engine | ChromIQ
4.1.4" text is the chart's own printed furniture, which is what lends it the
exported-report look. And there is no second renderer to fix:
`#ff2b2b`/warn-ring painting exists once in the codebase
(`tiff_preview.py` only — **PROVEN** by grep); `workflow/measurement_report.py
per_patch_overlay` is data-only; the Measurement Report PDF embeds only
`_TrendChart` renders (`measurement_report_dialog.py:1395–1420`); the
Quality_Check / Refine_Strips outputs are text. The fix lands in exactly one
place. (The project's fix-the-viewer-not-the-export scar was checked, not
assumed.)

### B4. Is the pixel-diff a valid measure of "the ring was covered"?

It measures ring coverage **iff** three conditions hold, and in this run all
three were checked rather than believed:

1. **The two renders differ in nothing but list order** — fresh widget each
   render, same size, same TIFF, same items, deterministic painting, enough
   event pumping. Then *any* stable differing pixel is order-dependent paint.
   The rect cases are the built-in negative control: same harness, 0 pixels —
   so the harness does not manufacture differences (this kills the "counting
   red ink in a chart full of red" failure: the diff, not the colour, is the
   signal; the red classification only *names* the difference).
2. **The items provably touch.** The slots share an edge coordinate
   (A1 y 195..337, A2 y 337..478 from the chart's own geometry), and in hex
   mode the drawn ink demonstrably interlocks (the diff is non-zero). The
   earlier "rectangles too small to touch" failure is excluded by
   construction, with one caveat named below.
3. **The diff is local to the two items.** Bounding box of all differing
   pixels: [290,113]–[309,125], a ~20×12 px cluster at the A1/A2 interlock —
   nothing from the legend, caption or elsewhere. **PROVEN** (printed by the
   probe).

One honest caveat on Basti's rect intuition: a zero diff on rectangles means
"order-independent", and by itself would not distinguish "ring inset inside
its own box" from "boxes never overlap". Here the two readings coincide —
the boxes share only an edge *and* the ring is inset off that edge — so the
conclusion (rect immune, hex not) stands, but the zero needed the code
reading to be interpretable. With that, I believe the measurement.

---

## Ranked recommendations

### Fault B (do first — one file, no ruling needed, no layout change)

1. **Split the items loop in `ui/tiff_preview.py` (~line 2506) into two
   passes**: iterate `items` once drawing fills/splits/seams only, then
   iterate again drawing halo + ring for every `warn` item (both branches).
   ~15-line refactor inside one function; no signature, data, or export
   changes; behaviour elsewhere in the paint order untouched.
2. Tests are **already in the tree**: `tests/test_warn_ring_draw_order.py` —
   two `xfail(strict=True)` cases that document the fault today and will
   *fail the suite* if the fix lands without flipping them (remove the xfail
   markers with the fix), plus a passing rect case pinning the immunity the
   refactor must not lose. Verified: `1 passed, 2 xfailed` in 0.4 s.
3. Needs no ruling. Purely additive visibility; the flagged-drawn-last look
   is already the app's intended appearance.

### Fault A (two changes of different weight)

1. **Needs the owner's ruling first — law mode**: make `margins-are-law`
   honour its own contract on the left: in `compute()`/`placement()`, when
   `g.margins_are_law`, stop subtracting/adding `rlwi`; render the row
   numbers inside the left margin sliding toward the page edge (mirror of the
   top-label rule), and add the mirrored inspector warning ("Left margin is
   too small for the row numbers…") when `margin_l` is under what they need.
   This is the fix for the chart Basti actually screenshotted: his other
   three margins already obey the box; afterwards his left reads ~1.0 (plus
   the warning, at 1 mm). Cost measured: his 26×44 chart keeps 1144 patches,
   each +4% wider. Knut's beta-13 clip model and his law-mode contract both
   point this way, but it changes SS/CR30 law-mode layouts and golden tests —
   Basti decides.
2. **No ruling needed — display**: in `ui/margin_inspector_panel.py`, say
   what is measured. "Left (to first patch)" / "Top (to first patch)", plus
   an indented line per non-zero band ("row-number band 7.5 mm",
   "strip-label band 7.0 mm") and a sentence in the panel's info card
   explaining that in the default mode furniture bands sit between the margin
   and the patches, printtarg-style. Zero layout change; fixes the "the app
   ignored my setting" reading in the mode where the app is right.
3. **Recommend against** moving the band inside the margin in the *default*
   mode (option 3 in A3): +23/+27 patches per A4 at default margins is real,
   but it breaks the pinned printtarg/SS parity and rewrites every SS/CR30
   golden layout to close a complaint that option 1 already closes where it
   was made. If Basti wants the patches, it is his trade to order.
4. Right/top/bottom: no code change — they are quantisation leftover,
   the label band (covered by 1+2), and the documented centering default.
   If anything, the band lines from 2 make them self-explanatory.

### What needs Basti's ruling, in one list

- Fault A change 1 (law-mode `rlwi`): yes/no, and the exact overflow
  behaviour for row numbers at tiny left margins.
- Whether the default mode should ever adopt the full clip model (A3
  option 3) — default is change nothing.
- Fault B needs nothing: say the word and it ships as a two-pass refactor
  with the xfail markers removed.

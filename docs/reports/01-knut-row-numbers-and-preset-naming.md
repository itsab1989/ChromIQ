# Knut, 2026-08-30 — two reports from the Create Chart tab

STATUS: in-progress

Two independent issues, analysed against the real code before any design.

---

## Issue 1 — "show patch (row) indicators" for any instrument

### Knut's words
> How do one show the patch label numbers on any instrument? I can find a patch
> pattern, but this seems only to affect the files. There is no checkbox to
> "show patch (row) indicators" next to the "Show strip indicators"... Should
> this not be possible for any chart if user wants it, just like your new CR30
> and the SpectroScan?

### What ALREADY exists (cited)
* `workflow/layout_engine/raster.py:1213-1245` — draws **row numbers** down a
  reserved band to the LEFT of the patch block, giving the sheet a 2-D A1/B2
  coordinate. Uses `label_patch(_j + 1)`, so the **Patch pattern does reach
  paper here** (contrary to Knut's impression that it only affects files —
  it only affects files on every OTHER instrument).
* Gated on two conditions: `_row_band_px > 0` (i.e. `geom.rlwi > 0`) and
  `p == 0` (leftmost strip only).
* `workflow/layout_engine/raster.py:1061` — `_row_band_px = px(geom.rlwi)`.
* `workflow/layout_engine/instruments.py:96` — `rlwi: float  # row-label width (mm)`.
* **`rlwi` is HARD-WIRED per instrument**: `7.5` for SS (`:558`) and CR30
  (`:717`); `0.0` for i1 (`:474`), CM (`:520`, `:538`), DTP41/51 (`:740`, `:756`).
* `workflow/layout_engine/instruments.py:638-644` states the rationale
  explicitly: *"rlwi = 7.5 — THE reason to take anything from the SpectroScan…
  the single most useful piece of furniture on the page and it exists only
  where rlwi > 0."*
* `workflow/layout_engine/geometry.py:147,279` — `_rlwi = 0.0 if
  g.fill_beyond_ruler else g.rlwi`: in **area-first the band is not reserved**,
  and the numbers are clamped at the paper edge (raster.py, Basti's ruling
  2026-08-30).
* UI: `show_strip_indicators` checkbox → `ui/dialogs/layout_options_panel.py:3442,3585`;
  recipe field `presets.py:96`, JSON key `draw_indicators` (`presets.py:235,354`).
  **There is no row counterpart — no field, no key, no checkbox.**

### Assessment
Knut is right: the feature is ~90 % built and reachable only by choosing a
SpectroScan or a CR30. The gap is a recipe field + a checkbox + making `rlwi`
come from the recipe instead of the instrument table.

### The design problems that make this NOT a one-line change
1. **Turning it on costs patch area.** `rlwi` is subtracted from `avail_w`
   (`geometry.py:148`, `area_fit.py:38`), so enabling it changes patch counts
   and sizes. Must be visible to the user, not a silent shrink.
2. **Backward compatibility.** A plain `bool` default would flip existing
   charts: default `True` adds a band to every i1Pro recipe ever saved;
   default `False` REMOVES the numbers from SS/CR30 charts. The default must
   reproduce today's behaviour exactly (on for SS/CR30, off elsewhere).
3. **Left-edge collisions.** The i1Pro has a left clip border (`lbord`), and
   the band sits in `[x0 - rlwi, x0]`. Interaction unverified.
4. **Band width vs digits.** 7.5 mm was chosen for the SS. A 3-digit row count
   at a large indicator font may not fit; today it clamps at the paper edge.
5. **Multi-page / multi-strip.** Numbers are drawn only for `p == 0`. Whether
   that is the leftmost strip *per page* needs verifying.

---

## Issue 2 — a preset silently names the project after itself

### Knut's words
> I loaded a preset "i1Pro-A4-162p-1page-Portrait-w7.5mm" when I did not have a
> name in the project name field… The name was then automatically defined as
> "i1Pro-A4-162p-1page-Portrait-w7.5mm" instead of asking user to define a
> name… I thought this was fixed? or was this deliberate?

### What ALREADY exists (cited)
* `ui/tabs/tab_chart.py:9265` `_ensure_profile_name(default)` — seeds the name
  field **only when empty** (#70, Knut's own model: a preset never overwrites a
  name the user already chose).
* Callers pass `p.default_target_name` (`:10104`, `:10145`), which is
  `_sortable_builtin_name(file_group, name, suffix)` (`:1230`) — this produces
  exactly the string Knut saw.
* `_set_manual_name_plain` (`:9254`) sets `_name_typed_by_user = False`, so the
  app **already knows** the name is its own, not the user's.
* `_typed_project_peek` (`:8699-8707`) relies on that flag, with a comment
  naming the trap: *"A NAME THE APP FILLED IN IS NOT A NAME THE USER TYPED."*

### The finding that settles "was this deliberate?"
**Two tooltips promise an ask that does not exist:**
* `ui/tabs/tab_chart.py:7322` — *"Picking it asks for a name, then copies the
  bundled patch set…"*
* `ui/tabs/tab_chart.py:7452` — *"Picking it asks for a name and builds the
  chart right away."*

`grep -rn "QInputDialog" ui/` finds **no name prompt on any preset path**
(the hits are the CR30 serial, a profile preset name, a measure preset name, a
check/refine preset name, and an export format). The wording entered in
`06607de8` / `44284a3c`. So the help text and the behaviour disagree, which is
why Knut believed it was fixed.

### The real defect
The seeded name is **provisional in the code and permanent on disk**: if the
user never types, `_name_typed_by_user` stays `False` yet that string becomes
the project folder, the `.icc` stem and the name printed on the sheet
(CLAUDE.md: *"The chart's own files carry the sanitised project name as their
stem"*). The app's own §S4.7 gate deliberately stays silent for such a name,
so nothing ever asks. An 81-character folder named after a layout preset also
fails principle 5 (files land in obvious, self-describing places) — the code
itself notes `default_target_name` "makes an 81-character one" (`:9229`).

---

## Open questions for the challenge agent
Numbered, in the report body below as work proceeds.

---

## Owner's rulings, 2026-08-30 (after challenge report 03)

**Row numbers vs the clip border (bug B2).** In "Prioritise chart area" with a
left clip border the digits are drawn and the clip strip is then pasted over
them, so they never appear — the i1Pro's default configuration. **Ruling: warn,
change no rendered output.** The inspector says plainly that the numbers will
not appear, why, and gives two remedies. The feature is unavailable in that one
combination and says so. No existing chart changes.

**The 7.5 mm of dead paper (bug B4) — OPEN, TRACKED SEPARATELY.**
`workflow/layout_engine/area_fit.py:38` subtracts `rlwi` when sizing patches,
while `workflow/layout_engine/geometry.py:147,279` deliberately do not
re-reserve it under `fill_beyond_ruler`. In "Prioritise chart area" the patch
block is therefore fitted 7.5 mm narrower and that paper is left empty on the
right. Measured by the challenge agent: patch width 173.99 → 166.49 mm, block
[26, 199.99] → [26, 192.49].

This is **pre-existing** and affects SpectroScan and CR30 charts as shipped
today; the row-number option only makes it reachable on more instruments.
**Ruling: leave it, report separately** — the row-number work must not carry a
geometry change that alters output already in users' hands. Fixing it would
make existing SS/CR30 area-first charts slightly wider and needs its own
verification pass.

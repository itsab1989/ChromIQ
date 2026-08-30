# Challenge of the row-numbers + preset-naming IMPLEMENTATION

STATUS: complete

Adversarial review of the uncommitted working tree on `master` (2026-08-30),
implementing the two Knut reports analysed in `01-…` and challenged in `02-…`.
Appended to as work proceeds; nothing here is final until `STATUS: complete`.

Proof folder: `~/Desktop/knut-fixes-challenge/`

## Method
- Read the diff line by line against reports 01/02.
- Static probes of the geometry/area-fit asymmetry with MEASURED pixels.
- Drive the REAL app (real MainWindow, real event loop) with the plist and
  preset store backed up first.
- Targeted test files only (no `--runslow`, no full suite).

---
## Safety (done before anything was touched)
- `~/Library/Preferences/com.chromiq.ChromIQ.plist` → `~/Desktop/knut-fixes-challenge/backup/com.chromiq.ChromIQ.plist.orig` (sha1 `d45d76f1ecd3f95d464b82a7b03c378a61361c4d`).
- `~/Library/Preferences/ChromIQ/presets/` (18 files) → `backup/presets.orig/` via `rsync -a`.
- A **detached `git worktree` at HEAD** (`40b60896`) was used for before/after
  comparison instead of `git stash`, so the working tree was never disturbed.

---

## F1 — REGRESSION (confirmed, real widgets): changing the instrument in the
## layout panel switches the SpectroScan's / CR30's row numbers OFF

`ui/dialogs/layout_options_panel.py:3632-3634` stores `None` only while the
checkbox still equals the instrument default, but `_on_instr_changed`
(`:1980-2060`) never re-syncs the checkbox when the instrument changes. The box
therefore carries the OLD instrument's state into the NEW instrument and is
written back as an EXPLICIT value.

Probe: the real `LayoutOptionsPanel(with_selectors=True)` in a real
`QApplication`, nothing touched but the instrument combo:

```
1. i1 (start / app default)   inst=i1    box=False  recipe.show_row_indicators=None
2. switch to SpectroScan      inst=SS    box=False  recipe.show_row_indicators=False   <-- explicit OFF
3. switch to CR30             inst=CR30  box=False  recipe.show_row_indicators=False   <-- explicit OFF
   -> geom_from_build_kwargs(r).rlwi == 0.0 for both (was 7.5 before this change)
5. set_recipe(pristine SS)    inst=SS    box=True   None
6.   then switch to i1        inst=i1    box=True   show_row_indicators=True           <-- explicit ON
```

i1 is the panel's first instrument and the app default, so **"pick SpectroScan
in Create Chart → Manual" is the ordinary path**, and it now produces a
SpectroScan chart with no row numbers — the exact furniture `instruments.py:638`
calls *"the single most useful piece of furniture on the page"*. Step 6 is the
mirror: an i1 chart silently gains a 7.5 mm band nobody asked for.
Affects both panels that own an instrument selector: Create Chart → Manual
(`ui/tabs/tab_chart.py:4539`) and the TI2 re-layout dialog
(`ui/dialogs/ti2_relayout_dialog.py:5091`). Preferences → Chart Layout is NOT
affected — `settings_dialog.py:3685` calls `set_recipe` on every combo change,
which re-syncs the box.

---

## F2 — NO REGRESSION on untouched recipes (proved, with the mutation proved to land)

28 cases (i1, p3, CM, SS, CR30 × patch_first/area_first × flat/hex × A4/A3,
1–6 pages) built through the real `chart.build_chart` with `emit_cht=True,
export_pdf=True`, in this tree and in the HEAD worktree, `seed=12345`,
`chart_date="2026-01-02"`:

| output | NEW vs HEAD |
|---|---|
| `.tif` (all pages) | identical, 28/28 |
| `.cht` (all pages) | identical, 28/28 |
| `.pdf` | identical, 28/28 |
| `.strips.json` | identical, 28/28 |
| `.ti2` | identical once the `CREATED` timestamp line is normalised, 28/28 |

**Probe honesty.** The first two runs of this probe reported "all 28 differ",
which was the probe, not the code: `.ti2` carries `CREATED` and `RANDOM_START`
from the clock. Fixing the seed and the date reduced it to `.ti2` alone, and
normalising `CREATED` closed it. A same-tree-twice control run now differs in
0 of 28. **Mutation proof that the probe can see a change:** re-running with
`row_indicators=True` changes the `.tif`/`.cht`/`.pdf` in every i1/p3/CM case
(and correctly changes nothing on SS/CR30, which already had the band).

---

## F3 — BUG: on the i1Pro's OWN built-in configuration the new option prints
## NOTHING, and still costs 7.5 mm of paper

The 121 built-in i1 presets are `layout_mode: area_first`, `clip_border: True`,
`clip_content_mode: "notes"`, `clip_side: "left"` (`tab_chart.py:1277`ff).
Measured on exactly that configuration (A4, `margins=(10,10,10,26)`):

```
row_indicators=None  derived patch w = 173.99 mm   rlwi=0.0  x0=26.00  block = [26.00, 199.99]
row_indicators=True  derived patch w = 166.49 mm   rlwi=7.5  x0=26.00  block = [26.00, 192.49]
```

and the rendered page-1 TIFFs differ **only** in `x ∈ [1269, 2362] px`
(107–200 mm) — i.e. **the left 45 mm is byte-identical**: no digit is visible.

Mechanism, proved by spying on `PIL.ImageDraw.text`: raster DOES draw all 556
numbers (first at `(246, 83)` px = 20.8 mm), and then
`raster.py:1359` `img.paste(_clip, (_ax, _ay))` pastes the opaque clip strip
over `[0, 26] mm` and erases every one of them.

Cross-check that isolates the cause (same recipe, one variable changed):

| clip content | clip side | difference in the left 45 mm when the box is ticked |
|---|---|---|
| notes | left  | **none** — the numbers are erased |
| notes | right | digits at 242–396 px |
| off   | left  | digits at 153–291 px |
| off   | right | digits at 242–396 px |

So on the i1 family the user pays 7.5 mm (the patches get 4.3 % narrower and
7.5 mm of paper is left blank on the RIGHT, because `area_fit._usable`
subtracts `rlwi` while `geometry.placement` does not add it back) and receives
nothing at all.

### F3a — the new inspector warning says the opposite of what happens
`ui/tabs/tab_chart.py:16448-16456`:
> "⚠ The row numbers **will be printed over the clip border on the left** …"

They are not printed over it. They are painted **under** it and disappear. A
user who reads that warning and decides "fine, I can live with it printing over
the notes" gets a chart with no numbers and 7.5 mm of dead paper. The condition
(`rlwi>0 and fill_beyond_ruler and lbord>0 and clip_side=="left"`) selects the
right cases; the sentence describes the wrong outcome, and the case deserves a
refusal or a disable, not a warning.

### F3b — the area-first asymmetry wastes 7.5 mm even with no clip band
`workflow/layout_engine/area_fit.py:38` subtracts `g.rlwi` with no
`fill_beyond_ruler` exemption, while `geometry.py:147` and `:279` both use
`_rlwi = 0.0 if g.fill_beyond_ruler else g.rlwi`. In area-first the patches are
therefore SIZED as if the band existed and PLACED as if it did not: the block
still starts at `margin_l` and now ends 7.5 mm short of `margin_r`. Dead paper
on the right, in every area-first chart with the band on.

---

## On-screen journeys (the real app, real MainWindow, real `activated` signal)

Driver: a real `QApplication` + `MainWindow`; QSettings redirected to a temp
`.ini`; projects redirected to `/tmp/zz-challenge-projects` via
`custom_output_path`; the preset store redirected to a COPY of the user's own
via `CHROMIQ_PRESETS_DIR`. `~/ChromIQ` was never written to.
A **modal watchdog on a `QTimer`** records and closes each dialog — the first
attempt used only `processEvents()` and blocked inside the modal's nested event
loop, which is itself worth knowing: **the new ask really is a nested
`exec()` reached from the combo's `activated` signal**, exactly the
"modal in a suite that types nothing" hazard report 02 flagged.

### J1 — built-in i1Pro preset, empty name, nothing open → PASSES
`11-J1-i1-noname-modal0.png`. The InfoDialog *"Your project needs a name
first"* appears; the name field stays empty; the combo reverts to `none`;
**nothing at all is created on disk** (#175 satisfied).

### J2 — same preset with "ZZ-challenge-1" typed → PASSES
Builds into `ZZ-challenge-1/runs/run1/` with `ZZ-challenge-1.ti1/.ti2/.tif`,
`.channels.json` and the `exports/` sidecars all carrying the user's stem. No
dialog.

### J3 — PREBUILT (copy-only) preset, empty name, nothing open → PASSES
`21-prebuilt-noname-modal0.png`. Same dialog, combo reverted, nothing on disk.

### J5 — a preset picked while a project is OPEN → PASSES
`32-open-knut.png`. No dialog; the chart lands in
`ZZ-challenge-1/runs/run2/` under the open project's name.

### **F4 — BUG: a project OPEN + the name field CLEARED still names the project
### after the preset**
`ui/tabs/tab_chart.py:11209-11216`:

```python
_typed = (self._manual_target_name_edit.text().strip() … )
if not _typed and not target_name and not _is_named(self._file_mgr):
    self._ask_for_a_project_name(…); self._abandon_prebuilt_attempt(); return False
name = _typed or target_name or default_name
```

The comment above it says *"An open project is not asked about: the chart is
being added to it, **and its name is already the answer**."* It is not: when a
project is open the guard is skipped, and with the field empty the fallback
`default_name` — **the preset's own name** — wins. Reproduced in the running
app: with `ZZ-challenge-1` open and the name box cleared, picking
"ColorMunki · A4-300p-1page TC3.00 by Pharmacist" created a whole new project

```
ColorMunki-A4-300p-1page-TC3.00-by-Pharmacist/runs/run1/
    ColorMunki-A4-300p-1page-TC3.00-by-Pharmacist.ti1/.ti2/_01.tif …
```

— i.e. **Knut's exact reported fault, still reachable**, and worse than before
because it now also silently leaves the open project. The open project's name
is available (`self._file_mgr` holds it) and is never consulted. Same shape in
`_generate_from_ti1:11424` (`if not _typed and not _is_named(...)`), which then
falls through to whatever the caller passes.

---

## F5 — the ColorMunki layout panel draws two controls on top of each other
## (PRE-EXISTING, and the change moved them without fixing it)

`ui/dialogs/layout_options_panel.py:711` puts `clip_enable` (+ label + ⓘ) at
grid row 6 col 1, and `:726` puts `cm_stagger_cb` (+ ⓘ) at grid row 6 col 1 as
well. `_sync_instrument_widgets` (`:1958`) shows the clip selector for
CM/SS/CR30 and the stagger checkbox for CM — **so on a ColorMunki both are
visible in the same cell.** Measured in the running app (global rects):

```
clip_enable       (138, 1099, 360, 22)
cm_stagger_cb     (138, 1101, 360, 18)    !! OVERLAP
_clip_enable_tip  (504, 1099, 22, 22)
_cm_stagger_tip   (504, 1099, 22, 22)     !! exactly coincident
```

`44-CM-basic-block-crop.png` shows the result: the "Clip border:" row reads
**"nOffset every second strip"** — the stagger checkbox painted over the combo,
leaving one letter of "On" showing.

**Not a regression.** The same probe run against the HEAD worktree reports the
identical two overlaps (rows 5/5 there instead of 6/6). But the diff's own
comment at `:694-698` reasons about the row numbers going "directly under the
strip letters" and moves both colliding widgets one row down without noticing
they collide; a change that touches this grid is the moment to fix it.

## F6 — the ChromIQ engine OFF hides the whole panel (no inconsistency)
Driven: `TAB._manual_engine_check.setChecked(False)` →
`_manual_layout_grp.isVisible() == False` and the new checkbox with it
(`43-engine-off.png`). The control is never offered where the engine cannot
honour it. Nothing to fix.

## F7 — "Show row numbers" stays live while "Show strip indicators" is off,
## and then costs paper for nothing
`raster.py:1217` draws the row numbers INSIDE `if draw_indicators:`
(`raster.py:1181`), but `geometry.py:147/279` reserve `rlwi` regardless. So with
the strip letters switched off the band is still taken out of the page and
nothing is drawn in it. `_on_show_indicators` (`layout_options_panel.py:3185`)
greys `indicator_font`, `indicator_size`, bold/italic and the underline row —
but **not** the new checkbox. Driven: strip indicators OFF →
`show_row_indicators.isEnabled() == True`, `indicator_font.isEnabled() == False`
(`42-strip-indicators-off.png`). Report 02 D2.2 flagged exactly this and the
implementation did not answer it.

## F8 — the patch-count estimate DOES follow the toggle (passes)
Driven in the real app, Manual + engine:

| instrument | box off | box on |
|---|---|---|
| i1Pro A4 | 525 patches (21 cols) | **500** (20 cols) |
| SpectroScan A4 | **1000** (25 cols) | 960 (24 cols) — default is ON |

## F9 — persistence: the field survives everywhere it should (passes)
- **Layout preset store** (Create Chart → "Update preset", and the same store
  Preferences → Chart Layout writes): after ticking the box on i1/A4 and
  clicking update, `load_presets("chart_layout")` reads back
  `i1|A4|clip -> show_row_indicators = True`. A preset written **before** this
  field existed loads back as `None` (`i1|A4R|clip -> None`, key present after
  the round-trip through `asdict`), i.e. "the instrument's own behaviour".
- **Per run / per target**: the built chart's
  `<stem>.channels.json → layout.recipe` carries
  `"show_row_indicators": true` alongside `"show_strip_indicators": true`, with
  `layout.engine == "chromiq"`. Written by `chart_creator.py:1391`
  (`params.layout_recipe.to_dict()` = `asdict`), so it cannot drop a field.
- **`GEOM_BUILD_KEYS`** has `"row_indicators"` (`instruments.py:394`), so every
  capacity estimate uses the same geometry as the render — the class of bug
  `clip_border_width` once caused is closed here.
- `_layout_recipe_values` (`tab_chart.py:5330`) compares `to_dict()` minus the
  app-global styling keys, so the "preset modified" indicator notices the row
  toggle. Correct, and consistent with `show_strip_indicators`, which is also
  per-chart and deliberately NOT in `INDICATOR_STYLE_KEYS`
  (`core/settings.py:417`).

**Consistency verdict:** `show_row_indicators` is persisted exactly like its
nearest neighbour `show_strip_indicators` — a per-chart recipe field, carried by
`asdict`, stored in the layout preset store and in `channels.json`, and NOT an
app-global styling key. No inconsistency found here.
---

## F10 — a targeted test FAILS on this working tree

```
QT_QPA_PLATFORM=offscreen pytest tests/test_layout_options_panel.py \
  tests/test_layout_presets.py tests/test_layout_geometry.py \
  tests/test_scanner_builtin_presets.py tests/test_knut_issues_45_59_60_62.py \
  tests/test_project_name_collision.py -q
→ 1 failed, 178 passed, 2 skipped
```

`tests/test_layout_presets.py::test_the_full_recipe_really_is_full`

```
AssertionError: these recipe fields are never set in the round-trip sample, so a
dropped one would pass unnoticed: ['show_row_indicators']
```

That test exists **precisely** to catch a new recipe field whose persistence is
untested; it reads `inspect.getsource(test_all_fields_persist_through_named_dict)`
and demands every field appear there. The implementation added the field and did
not extend the sample. **The everyday tier is red as the tree stands**, so the
release gate cannot be green either.
(`tests/test_i18n.py`, `test_message_catalogue.py`,
`test_design_specs_are_binding.py`, `test_cht_writer.py`,
`test_i1pro3_builtin_presets.py` — 233 passed.)

## F11 — hostile extremes (probe results)

All built through the real engine with `row_indicators=True`, measuring the
leftmost inked pixel column and whether any ink sits at `x = 0` (= clamped off
the sheet):

| case | pages | patches/page | first ink | ink at x=0 |
|---|---|---|---|---|
| SS A3, 4×3 mm patches (≈130 rows → 3-digit labels) | 1 | 9177 | 98 px (8.3 mm) | none |
| SS A4, indicator size 8 mm | 2 | 1053 | 42 px (3.6 mm) | none |
| SS A4, indicator size **14 mm** | 2 | 1026 | **12 px (1.0 mm)** | none |
| SS A4, left margin 0 mm | 2 | 1092 | 20 px | none |
| SS A4, left margin 0.4 mm | 2 | 1092 | 24 px | none |
| SS A4 hexagonal + band | 2 | 1170 | 91 px | none |
| i1 A4, clip band on the RIGHT | 4 | 420 | 207 px | none |
| SS A4, use_instrument_margins | 2 | 1080 | 90 px | none |
| SS A4, indicators rotated 90° | 2 | 1053 | 90 px | none |

- **Three-digit rows fit.** At ~130 rows the widest label still ends inside the
  7.5 mm band. Report 02's worry does not bite at realistic sizes.
- **A large indicator size DOES overflow the band** — 14 mm puts the digits
  1.0 mm from the paper edge on a 6 mm margin, i.e. 5 mm outside the 7.5 mm
  band. Nothing warns: `preflight.indicator_width_warning`
  (`workflow/layout_engine/preflight.py:76`) compares a **two-letter strip
  label against the strip width** and knows nothing about the row band. The
  digits always grow LEFT from the patch edge, so they never cover a patch —
  they eat the margin and then clamp at the page edge.
- **Hexagons + band is fine**: the `_protrude = strip_w // 4` allowance
  (`raster.py:1233`) keeps the honeycomb's left stagger off the digits.
- `paper="A2L"` / `"A6"` raise `ValueError: unknown paper code` — expected, those
  codes are not in `papers`, so "smallest paper / A2 landscape" could not be
  driven through this API. Not a finding about this change.

---

# THE DESIGN CHALLENGE — should `_ask_for_a_project_name` become an input dialog?

**Verdict: yes in principle, and the minimal correct shape is narrower than it
looks. Two of the three call sites can resume in place; one cannot.**

## D1. What already exists, and how the two copies have DRIFTED
| | `ui/txt_loader.py:146 _ask_profile_name` | `ui/ti2_loader.py:845 _ask_project_name` |
|---|---|---|
| pre-fill | none, placeholder `e.g. Canon_ProGraf_Glossy_240g` | pre-filled + `selectAll()` |
| invalid-character check | yes — `/\:*?"<>\|` | **none** |
| sanitises before returning | yes (`FileManager._sanitise`) | **no — returns `edit.text().strip()` raw** |
| live validation | yes (`textChanged`) | only on click |
| collision offer | "Overwrite existing folder" → `rmtree` after a second `QMessageBox` | "Replace existing" → moved to `old/` |
| self-collision guard | yes | none |

A third near-copy sits at `ui/ti2_loader.py:1140-1230` (the .ti2 import
dialog), which follows the txt_loader shape. **The drift is itself a finding:**
one dialog permanently deletes and the other archives, for the same words
("Replace"/"Overwrite"); one rejects `:` and the other accepts it and hands an
unsanitised name onward.

**Where a shared helper belongs:** NOT in either loader — `tab_chart` must not
import a loader module to ask a question. A new `ui/dialogs/name_prompt.py`
(next to `layout_options_panel.py`), exporting one function that takes
(parent, working_dir, prefill, purpose) and returns `str | None`, with the
collision policy passed IN rather than baked in. Per CLAUDE.md the new wording
goes to §M-PROPOSED in `docs/design/unified_measurement_management.md` first;
`tests/test_message_catalogue.py` enforces that.

## D2. `_name_typed_by_user` — the flag that decides whether §S4.7 speaks
Today `_ask_for_a_project_name` (`tab_chart.py:12099`) only calls
`field.setFocus()`; the flag is set **only** by `_mark_name_typed_by_user`
(`:9172`), wired to `textEdited` (`:3405`, `:3865`). Qt emits `textEdited`
**only for a keystroke or a paste — never for `setText()`**. So a dialog that
writes the answer into the field programmatically leaves
`_name_typed_by_user == False`, `_typed_project_peek` (`:8706`) returns None,
and §S4.7 stays silent: the user types a name that already exists and is never
told. **Requirement: the new dialog must set `_name_typed_by_user = True`
explicitly (or call `_mark_name_typed_by_user()`), because the name came from a
person.** This is the same class as the bug Knut reported.

## D3. Can the action continue, or must it still abort?
- **`_generate_from_ti1` (`:11424`) — CAN RESUME.** The guard sits above the
  documented "THE BUILD STARTS HERE" line and above
  `self._generate_btn.setEnabled(False)` (`:11437`); the docstring at
  `:11334` states every refusal above `target_started.emit()` is undoable.
  Nothing has been torn down at that point. Taking the name and falling through
  is safe.
- **`_on_generate` (`:12341`) — CAN RESUME**, but only if the name is taken
  **before** `_gate_typed_project_name()` (`:12309`), not after: §S4.7 must see
  the final name. Today the ask is inside the big `try` whose docstring
  (`:12124`) explains that four returns between the question and the point of
  no return once left an armed "Replace it" behind. Resuming *forward* is
  fine; resuming *backwards* past the gate is not.
- **`_create_prebuilt_target` (`:11209`) — CANNOT RESUME AS PLACED.** The guard
  runs **after** `_gate_route_and_replace(...)` (`:11190`), i.e. after §S4.7 and
  the replace question have already been asked *about the old name*. Answering
  the name now would invalidate the answer just given — the user would have
  agreed to replace project X and then named the project Y. The fix is not a
  field in the dialog; it is to **move the name guard above
  `_gate_route_and_replace`**, ask there, and only then gate. With that move it
  can resume like the other two.

## D4. Cancel (#175)
- `_generate_from_ti1`: Cancel must `return False` before the button is
  disabled — the caller's preset undo (`_restore_preset_state`, `:7841`) then
  puts the tab back. Its snapshot already carries
  `snap["recipe"] = panel.get_recipe()` (`:7747`), a whole `LayoutRecipe`, so
  **the new checkbox is restored by the undo** (verified by reading; the field
  is part of the dataclass the snapshot stores).
- `_create_prebuilt_target`: Cancel must call `_abandon_prebuilt_attempt()`
  (`:11117`) — which clears the gate answer, `_layout_owned_by_build`, the
  dropdown and the prebuilt state. The current code does this. If the guard
  moves above `_gate_route_and_replace`, Cancel becomes *simpler*, because no
  gate answer has been armed yet.
- `_on_generate`: Cancel must leave the `try/finally` at `:12124` to disarm the
  pending replace — i.e. it must `return` inside that block, never raise.

## D5. Collision ownership
**§S4.7 must keep it.** It already owns "this name is an existing project" with
three real outcomes (rename the existing / create alongside / create and
delete), it knows the open project, and it drives the run picker. A second
collision UI inside the name dialog would ask the same question with a
different and weaker vocabulary (`txt_loader`'s "Overwrite" *deletes*; §S4.7's
"Rename" *moves*). The name dialog should therefore validate **shape only** —
empty, invalid characters, sanitises-to-empty — and hand the name to §S4.7.
Anything else lets the user answer the same question two ways.

## D6. The body text is already wrong for an input dialog
Current text (verbatim, captured on screen — `11-J1-i1-noname-modal0.png`):
> "Type a name into that box — the one just above the "Generate Chart" button —
> and pick the preset again."

With a field in the dialog that sentence is false, and it is the only sentence
that tells the user what to do. Draft replacement (beginner level, no jargon,
no "(s)", names the exact elements, states outcome and prerequisite):

> **Give this project a name**
>
> Before ChromIQ can make your chart it needs a name for the project. The name
> is used for everything this project produces: the folder that holds all the
> files, the name printed on the chart itself, and the finished ICC profile.
>
> Type the name below and press Continue. ChromIQ will then create the chart
> you picked, under that name.
>
> A name that says which printer and paper this is for works best, for example
> **Canon PRO-300 Baryta Gloss**. You can change it later, and ChromIQ will
> offer to rename the folder for you.

Buttons: **Continue** (default, Return) and **Cancel** (Escape). Cancel must
say, in the tab, that nothing was created.

## D7. Draft tooltip for the ⓘ next to the field
> **Choosing a project name**
>
> This name follows the whole job. It becomes the folder in your ChromIQ
> folder, it is printed on the chart so you can tell two printed sheets apart
> months later, and it becomes the name of the ICC profile your programs will
> show in their profile lists.
>
> Put in what you will want to recognise later: the printer, the paper, and —
> if you use more than one — the ink set. For example:
> **Canon PRO-300 · Hahnemuehle Photo Rag 308**, or
> **Epson P900 Baryta Gloss MK**.
>
> Leave out the date and the patch count. ChromIQ records those itself, and a
> date in the name only makes the folder look out of date.
>
> You may use letters, numbers, spaces, hyphens and full stops. Spaces become
> hyphens in the folder name. Slashes and the characters \ : * ? " < > | cannot
> be used, because folders cannot contain them.
>
> Nothing here is permanent: rename the project at any time and ChromIQ offers
> to move the folder, the chart files and the profile with it.

## D8. Edge cases to test once the field exists
1. only spaces; 2. leading/trailing spaces; 3. a name that sanitises to empty
(e.g. `///`); 4. 200+ characters (macOS 255-byte filename limit); 5. non-ASCII
and emoji; 6. the open project's own name; 7. a different existing project's
name (§S4.7 must fire); 8. a name differing only by case (APFS folds case, so
`canon` and `Canon` collide on disk but not in the string compare); 9. NFC vs
NFD (macOS stores NFD — a name pasted as NFC will `exists()`-match but compare
unequal); 10. Return accepts / Escape cancels / the window close button
cancels; 11. the dialog opening while `self._runner.is_running` (both guards
sit above the `is_running` check in `_create_prebuilt_target:11151` but NOT in
`_generate_from_ti1` — check the order); 12. pasting a `.ti1`/`.ti2` filename
(`FileManager.strip_workfile_ext` exists for exactly this).
---

# SUMMARY

## 1. REGRESSIONS AND BUGS (numbered, with file:line and a reproduction)

**B1 — Selecting SpectroScan or CR30 in the layout panel switches their row
numbers OFF.** `ui/dialogs/layout_options_panel.py:3632-3634` writes an explicit
`False` whenever the checkbox disagrees with the new instrument's default, and
`_on_instr_changed` (`:1980`) never re-syncs the checkbox across an instrument
change. Reproduce: open Create Chart → Manual, tick the ChromIQ engine, expand
"ChromIQ layout", change Instrument from i1Pro (the default) to
"SpectroScan (flatbed)", type a name, Generate. The sheet has no row numbers —
`92-SS-after-instrument-switch.png`, built by the real app with the box never
clicked. Also reproduced against the bare widget:
`recipe.show_row_indicators == False`, `geom.rlwi == 0.0`.
The mirror case writes an explicit `True` and gives an i1Pro chart a 7.5 mm band
nobody asked for. **The single most serious finding: it silently removes
existing, shipped furniture from two instruments.**

**B2 — On the i1Pro's own default configuration the new option prints nothing
and still costs 7.5 mm.** area-first + a left clip border: `raster.py` draws the
digits, then `raster.py:1359` `img.paste(_clip, …)` paints the clip strip over
them. Reproduce in the app: engine on, i1Pro, tick "Show row numbers" (the
estimate falls 525 → 500), name it, Generate → `52-i1-rowson-leftedge.png` has
column letters and no digits at all. Isolated: with `clip_content_mode="off"`
or `clip_side="right"` the digits appear; with notes-on-the-left they do not.

**B3 — The new inspector warning states the opposite of what happens.**
`ui/tabs/tab_chart.py:16448` — "The row numbers **will be printed over** the
clip border on the left". Measured: they are painted **under** it and vanish
(B2). Its condition selects the right charts; its sentence misinforms.

**B4 — area-first sizes the patches as if the band existed and places them as
if it did not.** `workflow/layout_engine/area_fit.py:38` subtracts `g.rlwi`
unconditionally; `workflow/layout_engine/geometry.py:147` and `:279` use
`0.0 if g.fill_beyond_ruler`. Measured (i1, A4, notes-left): patch width
173.99 mm → 166.49 mm, block `[26.00, 199.99]` → `[26.00, 192.49]`. **7.5 mm of
paper is left blank on the right** in every area-first chart with the band on.

**B5 — A prebuilt preset picked with a project OPEN and the name box EMPTY
still creates a project named after the preset.** `ui/tabs/tab_chart.py:11209`
skips the guard when `_is_named(...)` is true and then falls through to
`name = _typed or target_name or default_name`. The comment above it claims the
open project's name "is already the answer"; the code never reads it.
Reproduced (`log-1.txt`): with `ZZ-challenge-1` open and the field cleared,
picking "ColorMunki · A4-300p-1page TC3.00 by Pharmacist" created
`ColorMunki-A4-300p-1page-TC3.00-by-Pharmacist/runs/run1/…`. HEAD reaches the
same folder name, but HEAD *shows* it in the name field first
(`_ensure_profile_name` seeded it); the new code leaves the field **empty**
while creating it, so the user now gets no cue at all. **Visibility regression.**

**B6 — `tests/test_layout_presets.py::test_the_full_recipe_really_is_full`
fails.** The guard test that exists to catch exactly this omission was not
updated: `['show_row_indicators']` is never set in the round-trip sample. The
everyday tier is red, so the release gate cannot be green.

## 2. GAPS, OVERSIGHTS AND UI INCONSISTENCIES

**G1 — "Show row numbers" stays enabled when "Show strip indicators" is off,
and then only costs paper.** `raster.py:1217` nests the digits inside
`if draw_indicators:`; `geometry.py:147` reserves the band regardless.
`_on_show_indicators` (`layout_options_panel.py:3185`) greys the font, size,
bold/italic and underline controls but not the new box
(`42-strip-indicators-off.png`). Report 02 D2.2 raised this and it was not
answered — either nest the reservation too, or grey the box, or make the row
toggle genuinely independent.

**G2 — Two controls are drawn on top of each other on a ColorMunki.**
`clip_enable` and `cm_stagger_cb` are both at grid row 6 col 1
(`layout_options_panel.py:711` / `:726`); their ⓘ buttons are pixel-identical.
The panel reads "nOffset every second strip" (`44-CM-basic-block-crop.png`).
**Pre-existing** — the HEAD worktree shows the same two overlaps at row 5 — but
this change moves both widgets and reasons about that grid without noticing.

**G3 — No check that the digits fit the 7.5 mm band.** At
`indicator_size_mm = 14` the digits start 1.0 mm from the paper edge on a 6 mm
margin, i.e. 5 mm outside the band. `preflight.indicator_width_warning`
(`preflight.py:76`) only compares a two-letter STRIP label to the strip width.
Report 02 D2.6 predicted this. (They never cover a patch — they grow left — so
this is cosmetic, not corrupting.)

**G4 — The 7.5 mm band width is not a user control and not per-instrument.**
`ROW_LABEL_BAND_MM = 7.5` (`instruments.py:53`) is the SpectroScan's number
applied to every device. On a CR30 (12 mm patches) it is generous; on a dense
i1 chart it is 4 % of the page. A width field, or deriving it from the measured
digit width, is the obvious next question.

**G5 — The tooltip is stated unconditionally where the behaviour is
conditional.** `_prebuilt_tooltip` (`tab_chart.py:7322`) and the Knut-preset
tooltip (`:7452`) now say "Picking it asks for a name" — true only when no
project is open and the field is empty. With a project open it correctly does
not ask, and the tooltip does not say so. (Both are plain strings, not `tr()` —
pre-existing, but they are now load-bearing.)

**G6 — The new ask is a nested modal reached from `activated`.** The first run
of the driver blocked inside it. Report 02 D2.8 warned that headless drivers
(`scripts/drive_*.py`) selecting a built-in will now block; nothing in the diff
provides a suppression hook. `tests/test_project_name_collision.py:459`
(`test_a_name_the_app_filled_in_never_raises_the_window`) still passes because
it patches `QMessageBox.exec` and the new dialog is an `InfoDialog`, but its
stated intent — "a suite that types nothing must not hit a modal" — is now
violated in spirit.

**G7 — Unexplained, needs a second look.** In one sequence (`log-7.txt`) a
SpectroScan build made with the box unticked (panel `False`, estimate 1000
patches) recorded `show_row_indicators: null` in `channels.json` and printed the
band anyway (`7-SS-off-leftedge.png`). It followed a "Create X and keep Y"
answer to the rename dialog. A clean single build with no rename is fully
consistent end to end (`log-8.txt`, `81-clean-SS-off-leftedge.png`), and in
`log-9.txt` the same rename answer reset `show_strip_indicators` from the user's
`False` back to `True` while leaving the row field alone. **I could not reduce
this to a reliable reproduction and I am not asserting a mechanism** — but a
build that discards a just-made panel choice is worth someone's attention, and
it is not specific to the new field.

## 3. WORDING

**W1 — the inspector warning is wrong, not merely clumsy** (B3). Suggested
replacement, subject to §M-PROPOSED:
> ⚠ The row numbers cannot be printed on this chart. "Prioritise chart area,
> then fit patches to it" gives the left strip to the patches, and the clip
> border is printed over the numbers afterwards, so nothing shows. Switch to
> "Prioritise patch size, then fit to page", or move the clip border to the
> right edge.

**W2 — the tooltip's cost sentence is true only in patch-first.** "It costs
7.5 mm of paper down the left edge, so switching it on can leave room for fewer
or slightly smaller patches" is right for patch-first and understates
area-first, where the 7.5 mm is spent and *nothing is printed*.

**W3 — "which is why those two have always printed it"** reads as a promise the
app currently breaks (B1).

**W4 — checked against the house rules and CLEAN:** no "(s)" plurals anywhere
in the four new strings; the count-bearing sentence ("The numbers restart at 1
on every page") is verified true (`raster.py:1179` indexes the per-page slot
list); no Markdown; all four strings are in all twelve catalogues and
`tests/test_i18n.py` passes; the German uses Du-form as ruled.

**W5 — `_ask_for_a_project_name`'s body is good beginner English but is a dead
end** — see the design section: it explains the fix and then makes the user go
and do it somewhere else, and repeat the action they just took.

## 4. WHAT I TRIED AND COULD **NOT** BREAK

- **No regression on untouched recipes.** 28 instrument × mode × shape × paper
  combinations, TIFF/CHT/PDF/strips.json byte-identical to HEAD, `.ti2`
  identical once `CREATED` is normalised; probe proved deterministic
  (same-tree control: 0 of 28 differ) and proved able to see a change
  (`row_indicators=True` moves every i1/p3/CM output).
- **`.cht` / scanin alignment is safe** — the most dangerous item on the list.
  Every `.cht` box was sampled against the `.ti2` colour of its `SAMPLE_LOC`
  across 12 configurations (SS/i1/CR30 × patch-first/area-first × band on/off,
  plus hexagons and ColorMunki stagger): **0 wrong of 5,700 boxes**. The check
  is mutation-proved — shifting every box by 7.5 mm flags 479 of 480. An
  earlier, weaker version of this check (colour-uniformity only) reported 0 on
  the same mutation; it was discarded as broken.
- `.ti2` carries no coordinates at all (`SAMPLE_ID`/`SAMPLE_LOC` + values), so
  there is nothing there to misalign.
- `strips.json` (the Measure-tab strip overlay) tracks the band correctly:
  x 71 → 159 px on SS patch-first, 307 → 396 px on i1 patch-first, and in
  area-first x stays and the width shrinks by 88 px = the dead space of B4.
- **Persistence is consistent with the neighbouring options** — layout preset
  store, `channels.json → layout.recipe`, `GEOM_BUILD_KEYS`, the preset-modified
  comparison and the preset-undo snapshot all carry the field (F9, D4).
- **Engine OFF** hides the whole layout group, so the control is never offered
  where it cannot work.
- **Extremes**: three-digit row labels fit the band; hexagons do not cover the
  digits; margin 0 / 0.4 mm does not clip them; rotated indicators, instrument
  margins and a right-hand clip band all behave.
- The name ask itself works on every route I could reach with nothing open:
  Knut built-ins, prebuilt bundles, and (correctly) stays silent with a project
  open.

## 5. OPEN QUESTIONS FOR THE OWNER

1. **B1 is a shipped-behaviour change.** Should the checkbox follow the
   instrument (re-sync on every instrument change, so it always shows that
   instrument's default until touched), or should the recipe carry a separate
   "the user has touched this" flag? The first is simpler and loses an explicit
   choice on an instrument switch; the second needs a new field.
2. **B2/B4 — what should ticking the box do in area-first with a left clip
   band?** Refuse (grey the box with the reason), reserve the band anyway
   (area-first stops being "the margin box exactly"), or draw the digits over
   the clip content on purpose? Today it costs paper and prints nothing.
3. Should the row toggle be **independent of "Show strip indicators"**, or stay
   nested (G1)? Report 02's open question 2 is still open, and the
   implementation answered it implicitly by leaving the box live with no effect.
4. **B5** — with a project open and the name box cleared, should the app use the
   open project's name, ask, or refuse?
5. Is **7.5 mm** right for every instrument, or should the band be per-device or
   user-set (G4)?
6. The **inline-name-dialog** design: is asking mid-auto-run acceptable at all,
   or should the built-ins ask at selection time before anything starts? (My
   analysis says mid-run, above `target_started`, with the prebuilt guard moved
   above `_gate_route_and_replace` — see D3.)
7. Where should the shared name dialog live, and which collision policy wins —
   `txt_loader`'s destructive "Overwrite" or `ti2_loader`'s archiving "Replace"?
   They disagree today (D1).
8. `docs/design/per_target_settings.md:1.2` makes "the whole layout recipe"
   per-target and binding, with an on-screen test plan covering *every
   parameter, both states*. Does `show_row_indicators` need adding to
   `per_target_settings_test_plan.md` before this ships?

---

## SESSION SAFETY NOTE — full disclosure

The driver redirected `QSettings` to a temp `.ini` (`core.settings.QSettings`
replaced before `AppSettings()` was constructed), projects to
`/tmp/zz-challenge-projects` and the preset store to a copy. **It leaked
anyway**, twice, and both leaks were found and repaired:

1. `~/Library/Preferences/com.chromiq.ChromIQ.plist` changed during the session
   (`d45d76f1…` → `d737ae5d…`). **Restored byte-for-byte from the backup**
   (`d45d76f1…` verified after `killall cfprefsd`).
2. At 22:30 a chart was built into the user's real project
   `~/ChromIQ/test/runs/run1/`, archiving the previous run to
   `~/ChromIQ/test/old/2026-08-30_223009/`. **Fully restored**: the archived
   copy was moved back, my files removed, and the empty archive folder deleted.
   The user's own eleven earlier `old/` archives were not touched. A copy of the
   state as I found it after the leak is kept at
   `~/Desktop/knut-fixes-challenge/backup/chromiq-test-as-i-left-it/` in case
   anything is missed. `~/ChromIQ/CR30-Test` was never touched.

The cause was not pinned down. `core/i18n.py:64` reads the real
`QSettings("ChromIQ","ChromIQ")` directly for `custom_output_path` (read-only,
so not the writer), and `core/settings.py:783` goes through the patched name.
Something else writes the real store despite the patch. **This is the memory
note "On-screen drivers write to your REAL settings and presets" happening
again, and the redirect that is supposed to prevent it is not sufficient** — a
finding in its own right for whoever writes the next driver.

Disclosure of consequence: because the real plist was in play, some driven
phases may have read the user's real settings rather than the sandbox. Every
finding above is nevertheless either (a) reproduced independently in an
isolated widget/engine probe with no MainWindow (B1, B2, B4), (b) visible in a
built artefact on disk (B5, and the sheets in the proof folder), or (c) a
static code/test fact (B3, B6, G1–G5). G7 is explicitly reported as
not-reproducible.

STATUS: complete

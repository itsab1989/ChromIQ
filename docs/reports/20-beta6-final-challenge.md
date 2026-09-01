# 20 — Beta 6 final challenge

**STATUS: COMPLETE** (2026-09-01)
Branch: master @ 42bffb09 · version 4.1.5-beta.5

Evidence: `~/Desktop/beta6-proof/6-final-challenge/` (see its `INDEX.md`).

Findings are APPENDED as they are established. Nothing here is a fix; this is a
report only.

---

## 1. Row-label geometry (`raster.apply_row_label_geometry`)

**Swept 14,976 combinations** — 5 instruments × 13 papers (portrait and
landscape, A2…4×6) × 2 layout modes × 9 text sizes (0/auto…24 mm) × clip border
on/off × clip side left/right × "use instrument margins" on/off × hexagons ×
ColorMunki stagger. Driver + full output:
`~/Desktop/beta6-proof/6-final-challenge/01-row-label-sweep-14976-combos.txt`.

**What holds up.** No combination puts the margins off the page (0 of 14,976),
and **no layout that lays out with row indicators off fails with them on**
(0 of 14,976). The largest raise is 56.75 mm (p3, 24 mm labels, clip border) —
large, but the paper is what §R1.4 says should pay, and the chart still lays
out. Landscape papers and non-A4 sizes behave the same as portrait A4. The
rendered page (`10-onscreen-preview-click3.png`) shows the labels right-aligned,
clear of the notes band, inside the raised margin — §R1.1/R1.3/R1.4 as written.

### 1a · SHOULD-FIX — the left margin is raised for a clip border that is on the RIGHT

`workflow/layout_engine/raster.py:433`

```python
floor = max(float(getattr(geom, "lbord", 0.0) or 0.0),
            float(_DEFAULT_TEXT_EDGE_CLIP_MM if _edge is None else (_edge or 0.0)),
            float(kw.get("clip_border_width") or 0.0) if has_border else 0.0)
```

`has_border` correctly gates the `clip_border_width` term on `on_left`. The
**`geom.lbord` term in the same `max()` is not gated at all** — and `lbord` is
an instrument constant (20 mm for i1/p3), not an answer about which edge the
band is on. `instruments.py:363-368` puts the band into `margin_r` when
`clip_side == "right"`, so with the band on the right the left edge is bare
paper — and the row labels are still pushed in as if 20 mm of border were there.

Measured (`01-clip-side-and-margins.txt`), i1 / A4 / area-first, row indicators
on:

| clip side | left margin | patches per A4 sheet |
|---|---|---|
| left  | 33.89 mm | 651 |
| **right** | **28.00 mm** | **570** |

The correct floor with no border on the left is the 4 mm text-distance-to-edge,
giving `4 + 6.89 + 1 = 11.89 mm` — so the chart is losing **16.1 mm of paper
and 81 patches per sheet (−12.4 %)** to a border that is printed on the other
side. On a p3 it is 126 vs 150 (−16 %).

The code's own comment at `raster.py:424-428` asserts that "`lbord` says WHETHER
a clip border is on this edge". It does not; `Geom.clip_side` does. This is the
same class of mistake the comment above it was written to record.

### 1b · SHOULD-FIX — the >99-row clamp does not do what its docstring promises

`raster.py:1838-1841` (in `row_label_band_mm`):

> *"A page that somehow holds more than 99 rows is not left to walk off the
> paper: the renderer clamps the label at the same floor this band is measured
> from…"*

The renderer's actual clamp is `raster.py:1356`:

```python
_tx = max(0, _rx - _tw)
```

That is the **paper edge**, not the floor. With a clip border on the left and a
chart of more than 99 rows, a three-character label is clamped to x = 0 — inside
the border, which is drawn over it. That is K9, the exact fault this work closed
for the ordinary case, still reachable at the boundary. It is also inside the
printer's unprintable edge. Reachable in principle (a 2 mm patch pitch on A3
gives >120 rows); I did not find a stock preset that reaches it, which is why
this is should-fix rather than blocker — but the docstring states a guarantee
the code does not provide, and that is the part that will mislead the next
reader.

### 1c · The circularity is REDUCED, not removed (nice-to-have)

The commit message says the fixed two-character allowance removed the
provisional/final mismatch (9.43 mm asked, 5.22 mm delivered). It removed the
**row-count** half. The **auto text size** half remains: with
`indicator_size_mm = 0` (the default), `effective_indicator_size_mm`
(`raster.py:279-304`) shrinks the label to fit `geom.pwid × INDICATOR_FIT_FRAC`,
and `pwid` in area-first is derived *from* the width the band has just changed.

Measured (`01-provisional-vs-final.txt`), provisional vs final left margin, auto
size:

| instrument | paper | provisional | final | drift |
|---|---|---|---|---|
| i1 | 4×6 | 33.79 mm | 34.30 mm | **+0.51 mm** |
| i1 | A4 | 33.79 mm | 33.89 mm | +0.10 mm |
| SS | A4/A4R/A3/Letter | 11.08 mm | 11.18 mm | +0.10 mm |

At an explicit text size the drift is exactly 0.000 in every case, which
confirms the mechanism. Sub-millimetre, so it does not change a patch count in
any combination I measured — but it is the same circularity, and the report
that says it is gone will be believed.

### 1d · Dead code — `_rows_that_fit` (nice-to-have)

`raster.py:439-467` is defined and **called from nowhere** (grepped across the
repo; only its own definition matches). It was orphaned when the band became a
fixed two-character allowance. It reads `kw.get("orientation")`, a key
`LayoutRecipe.build_kwargs()` has never emitted, so had it stayed live it would
have sized the band for portrait on every landscape sheet.

### 1e · Two different defaults for a missing `dpi` in one module (nice-to-have)

`raster.py:319` uses `int(kw.get("dpi") or 150)`; `raster.py:396` uses
`int(kw.get("dpi") or 300)`. Both read the same key from the same hand-built
kwargs dicts. Sub-pixel in effect, but the whole point of
`_DEFAULT_TEXT_EDGE_CLIP_MM` was that a missing key must not mean two things.


## 2. Estimate versus render (hand-built layout kwargs)

Evidence: `~/Desktop/beta6-proof/6-final-challenge/02-estimate-vs-render.txt`,
produced by driving the real window.

### 2a · The 368/345 fix HOLDS — Guided agrees with Guided, 40/40

`tab_chart._engine_geom` (11702) against `chart_creator._engine_build_kwargs`
(1128), five instruments × four papers × density on/off, comparing the number
the tab shows with the number the build lays out:

```
Guided mismatches: 0 / 40
```

CR30 A4 reads **345** on both sides — the exact figure the last round got wrong.

### 2b · SHOULD-FIX — the Gamut module's "≈ N sheets" ignores the Manual layout entirely

`ui/tabs/tab_chart.py:15187` `_gamut_per_sheet`, whose own docstring says
*"Patches per sheet under the CURRENT Manual layout — engine-exact when the
engine is on"*, and `:15358` `_gamut_sheet_estimate`, *"EXACT with the ChromIQ
layout engine (the same geometry that will build the sheet, asked in
advance)"*.

It calls `_engine_capacity` with **four scalars taken from `_collect_manual()`**
(instrument, paper, density, margin, patch-scale) and never looks at the
`LayoutRecipe`, which is what actually builds a Manual sheet. Measured against
the recipe's own render, i1 / A4, engine on:

| Manual layout | what the sheet really holds | what the box says |
|---|---|---|
| stock default | 525 | **550** |
| row indicators ON | 500 | **550** |
| 20 mm margins all round | 540 | **550** |
| area-first, 10 × 10 grid | 100 | **550** |
| clip border off | 525 | **550** |
| clip band 60 mm | 425 | **550** |
| patch 20 × 20 mm, patch-first | **88** | **550** |
| spacer scale 3.0 | 420 | **550** |

**Eight of eight wrong, and the number never moves.** On the 20 mm-patch layout
it is 6.25× too high: a 500-patch gamut set is told "about one sheet" when it
takes six. This is the same family as the 368-on-a-345-sheet fault — a hand-
assembled kwargs dict standing in for `LayoutRecipe.build_kwargs()` — and it is
the last one of that family still open.

A second, smaller defect in the same three lines: `_gamut_per_sheet` calls
`_engine_capacity` **without `guided=`**, so it takes the default `guided=True`
(`tab_chart.py:11772`) while describing a *Manual* chart. For a CR30 that
branch forces `spacer_on=False, spacer_mode="none"` (`tab_chart.py:11760-11763`),
which is Guided's rule and never Manual's.

### 2c · Checked and clean

* **The Manual info line** (`tab_chart.py:5044`) routes through
  `_engine_info_line_from_recipe` whenever a recipe exists — the recipe path,
  not the scalar one.
* **The Manual patch-count figure** is the requested patch count, not a
  capacity, so there is nothing for it to disagree with (measured: it reads
  484 across all six layouts above, unchanged, which is correct).
* **`instruments.geom_from_build_kwargs`** is fed the whole kwargs dict, not a
  filtered one, so `apply_row_label_geometry` sees `dpi`, `patch_pattern` and
  the indicator fields on the recipe path.


## 3. Row indicators without strip letters

Evidence: `~/Desktop/beta6-proof/6-final-challenge/03-row-indicator-tristate.txt`.

### 3a · What holds up

* **The capacity estimate DOES account for the band in this combination.**
  Letters off + rows explicitly on, A4: i1 **651** (vs 682 with no band),
  CM **48** (vs 63), SS 1080, CR30 345. The band is paid for, once, in the
  margin.
* **A recipe dict round-trips the tri-state cleanly** — all six
  (strips × rows) states survive `to_dict()` → JSON → `from_dict()`.
* The chart sidecar stores a **recipe dict**, not build kwargs
  (`chart_creator.py:1390-1398`), so the normal Manual path is on the clean
  route.

### 3b · SHOULD-FIX — "untouched" becomes "explicitly off" through `from_build_kwargs`

`workflow/layout_engine/presets.py:381-384` maps the tri-state to kwargs as

```python
"row_indicators": (self.show_row_indicators
                   if self.show_row_indicators is not None
                   else (None if self.show_strip_indicators else False)),
```

and `:242-244` maps it back with `None if d.get("row_indicators") is None else
bool(...)`. The two are not inverses when the strip letters are off. Measured:

| strips | rows in | rows out |
|---|---|---|
| True | None | None ✔ |
| True | True / False | True / False ✔ |
| **False** | **None** | **False** ✘ |
| False | True / False | True / False ✔ |

So a recipe where **nobody touched the box** and the strip letters happen to be
off comes back as **a person's explicit "off"**. From that moment the recipe no
longer follows the instrument: switch to a SpectroScan or a CR30 and the row
numbers those devices have always printed stay off, permanently. That is
verbatim the stickiness the tri-state was introduced to prevent — the comment
at `presets.py:369-372` names it: *"writing False into the field would make an
untouched SpectroScan lose its row numbers for good"*.

Reachable through every path that stores or reads build kwargs rather than a
recipe: `LayoutRecipe.from_dict` routes to `from_build_kwargs` whenever the
dict carries `nolpcbord` or `draw_indicators` (`presets.py:199-200`), and
`chart_creator.py:1396` uses `from_build_kwargs` for any chart built without a
recipe.

### 3c · Worth a ruling, not a bug — a SpectroScan loses its row numbers with the letters off

Same mapping, seen from the user's side. Measured, A4:

| instrument | letters on, box untouched | letters **off**, box untouched |
|---|---|---|
| SS | band 6.08 mm, 1080 patches | **band 0.00**, 1120 patches |
| CR30 | band 9.43 mm, 345 patches | **band 0.00**, 368 patches |

Turning off the strip letters on a SpectroScan silently turns off the row
numbers too — on the one instrument whose whole point is the 2-D grid. This is
the documented ruling ("an untouched box still follows the strip letters", so
all 130 built-ins render unchanged), so it is not a defect; it is worth Knut
seeing, because it is the case he would meet.

(Incidentally: CR30 A4 with the band off is **368**, and with it **345** — the
two numbers from round four's fault. The 368 was the band's width, exactly.)

### 3d · The tri-state's own control is broken — see section 10

The Preferences → Chart Layout panel uses the *same* `LayoutOptionsPanel` and
the same `changed` signal (`ui/dialogs/settings_dialog.py:3283-3284` →
`_on_layout_field_changed` → `_layout_store.set(self._recipe_from_fields())`).
The first-click fault in section 10 therefore applies there too — and there it
is worse, because `_on_layout_field_changed` is the **only** writer: the first
click stores `None`, the dialog closes, and the saved per-combination default
never records the answer at all.


## 4. The K3/K4 shield (`ui/tabs/tab_chart.py`)

Attacked on screen, in the real window, sandboxed. Evidence:
`04-shield-row-indicator.txt`, `08-end-to-end-drive.txt`.

### 4a · It holds — including against the new tri-state

The obvious attack is the interaction with finding 10. The release watcher
`_release_ui_values_that_moved` (`tab_chart.py:13646`) runs on `panel.changed`
and asks the **recipe** whether the field moved — and section 10 proves the
recipe is one click behind for `show_row_indicators`. Driven, with the field
recorded as imposed by the chart:

```
=== the LOSING combination, stated in the user's words:
    the run's own stored answer is 'no row indicators' (False);
    the chart just loaded carries the untouched state (None);
    the person ticks the box ONCE to say 'yes'.
    box on screen after the click : True   (the person sees 'yes')
    still shielded                : True          <- the click did NOT release it
    value the shield writes       : True          <- and it is stored anyway
    -> the click survives
```

So the field **does** stay on the shielded list — condition 1 never releases it,
exactly as predicted — and the setting survives anyway because
`_keep_the_targets_own_values` (`tab_chart.py:13692-13712`) requires **both**
conditions: nothing reported a change **and** the value still equals what the
sidecar put there. The second condition is what saves it. The comment at
`:13696-13702` argues for both conditions on other grounds; this is a third
case where one alone would have been wrong.

Crossed against the plain controls for contrast (same driver): the strip-
indicator checkbox and `strip_gap_mm` are both released on their first move.

### 4b · Three target switches in a row — clean

`Guided build → project A → project B → project A`, reading the panel each
time: `[('E2E-Probe', True, 0.0), ('E2E-Other', True, 0.0), ('E2E-Probe', True,
1.0)]` — the row-indicator answer and the nudged strip gap both come back.
`meta.json` for both runs holds `show_row_indicators: True`,
`strip_gap_mm: 1.0` throughout.

### 4c · What I could NOT test, said plainly

I could not drive a **run switch through the bar's own combo**: the combo did
not repopulate after a run was added under it in this harness, and driving
`MeasurementTargetController.set_profile_run()` directly bypassed
`load_target_settings` entirely (instrumented: **0 calls**), so the panel simply
kept whatever it had. That is a harness limitation, not a finding, and I am not
reporting the panel state it produced as a bug. **The run-switch leg of K3/K4
is therefore UNVERIFIED by me for beta 6** — the target-switch leg is verified
and clean, and the guard test `test_the_chart_sidecar_never_files_into_the_
target.py::test_an_ordinary_panel_edit_does_not_hand_the_run_back_to_the_chart`
was mutation-proved to work (section 9).


## 5. The twelve teardown ERRORS

**Severity: SHOULD-FIX (test hygiene, not product) — and they are NOT inert-by-
design. They are an unowned pipe leak in a test helper, and the fix is already
written elsewhere in the suite.**

### What I could reproduce

* **Everyday tier**, `pytest -n auto`, this tree:
  `8366 passed, 262 skipped, 3 xfailed in 85.74s` — **0 failed, 0 errors,
  0 warnings**.
* **Slow subset**, `pytest --runslow -m slow -n auto`:
  `121 passed, 1 warning in 127.19s`. The warning is
  `PytestUnraisableExceptionWarning` — `BrokenPipeError: [Errno 32] Broken
  pipe` raised inside `_pytest/fixtures.py::finish`, attributed to
  `tests/test_skip_strip_replay.py`.
* That file **alone**, `pytest --runslow tests/test_skip_strip_replay.py`:
  `14 passed, 1 warning` — so it does **not** "pass clean alone"; the noise is
  there on its own too, it is simply not always attributed to a teardown.

I did not run the full `--runslow` gate (the coordinator runs it), so I did not
observe the "12 errors" line myself. What I can say is what the errors are.

### The cause, PROVEN by mutation

`tests/helpers/replay_tools.py:78-93`, `reap_live_sessions()` — the safety net
`tests/conftest.py` calls after every test:

```python
if session.proc.poll() is None:
    session.proc.kill()
    killed += 1
...
_LIVE.remove(session)
```

It kills the helper and **never joins the reader thread and never closes
`stdin`/`stdout`/`stderr`**. The `TextIOWrapper` around a `stdin` that still
holds buffered bytes raises `BrokenPipeError` when CPython finalises it — an
*unraisable* exception, so it lands on whatever pytest phase happens to be
running when the garbage collector gets to it. `ReplaySession.finish()`
(:171-181) has the same hole.

I proved it by mutation, and the mutation lands:

| tree | `pytest --runslow tests/test_skip_strip_replay.py` |
|---|---|
| as shipped | `14 passed, **1 warning**` |
| + join the reader and close the pipes in `finish()` **only** | `14 passed, **1 warning**` (no change — so `finish()` is not the site) |
| + the same in `reap_live_sessions()` | `14 passed` — **0 warnings** |
| the eight replay files together, `-n auto` | `60 passed` — **0 warnings** (`1 warning` before) |

The mutation was reverted and the revert verified: `git diff
tests/helpers/replay_tools.py` is empty and `git status` shows only this report.

### Why this matters more than "noise"

The identical fix, with a comment explaining exactly this failure mode, is
already in the suite — `tests/test_cr30_external_values.py:163-192`:

> *"an unraisable BrokenPipeError at teardown is reported by pytest as an ERROR
> on an otherwise passing test, which is exactly the noise that hides a real
> failure later… ORDER MATTERS. Killing first ends the pump thread's iterator
> on its own… So: kill, reap, JOIN the reader, and only then close. An earlier
> attempt at this fix closed first and did nothing."*

It was never carried over to `tests/helpers/replay_tools.py`, which **nine**
test files use. So the answer to "are they hiding a real fault" is: they are
hiding nothing today, but they are not a property of xdist or of Qt and they
are not going to go away on their own. A gate that prints errors is a gate
people stop reading.

### Did the count grow because of this work?

No. Nothing in `1bbc2211`, `8d422c84` or `42bffb09` touches
`tests/helpers/replay_tools.py`, `tests/conftest.py`, or any replay test
(`git show --stat` on all three). The leak predates the round.


## 6. The import dialogs

Evidence: `~/Desktop/beta6-proof/6-final-challenge/06-import-dialogs.txt`.
Both dialogs constructed for real, in all thirteen languages, with 0 / 1 / 50
projects and with a 100-character mixed-script project name, each laid out at
**its own minimum width** — the width a user can actually drag it to.

### 6a · What holds up — the minimum width really does follow the buttons

`_width_the_buttons_need` (`ui/dialogs/project_picker.py:122`) is doing its job.
Measured minimum widths and worst button overlap:

| language | picker min width | overlap |
|---|---|---|
| Chinese | 560 px (the floor) | 0 |
| Polish | 572 | 0 |
| English | 627 | 0 |
| **German** | **697** | **0** |
| Swedish | 696 | 0 |

**Zero overlap in 13 languages × 3 project counts × 2 dialogs**, and zero with
the long name. The German case that round three fixed (Cancel drawn over the
last word of "Stattdessen neues Projekt anlegen") is gone and the floor has
moved with it, 560 → 697.

Heights: the tallest dialog in any language, with 50 projects listed, is
**383 px** — no small-screen problem. With **0** projects the picker is not
shown at all and the person goes straight to the name box, which is right.

The run-naming button (`tab_profile.py:4380-4396`) was pushed through
`fit_button_width` with 16 labels — "a new run", "the selected run", and
Run 1…12, 99, 128 — in every language: **0 clipped**.

### 6b · SHOULD-FIX — the run-naming button is ENGLISH in eleven of twelve languages

This is the button round two introduced and round three said it had fixed.

`1bbc2211` renamed *"File it here"* to the three run-naming strings and added
them to every catalogue **with the English text as the value**. `8d422c84`
noticed (*"the import button's translations were lost when it was renamed"*)
and fixed **German only**.

Of the 6 short (≤ 90 character) UI strings the three challenge commits
introduced:

| language | English-valued |
|---|---|
| de | 0 |
| es, fr, it, ja, nl, no, pl, pt, ru, sv, zh_CN | **3** — `File it in a new run`, `File it in the selected run`, `File it in {run}` |

So a Swedish or Japanese user importing a measurement is offered
*"File it in Run 3"* in English, beside "Avbryt" / "キャンセル". (The other three
new keys are long CR30 help texts, deliberately deferred and tracked by
`tests/test_help_cards_untranslated_are_tracked.py` — those I do not count.)

### 6c · MISSING GUARD — `test_i18n.py` cannot see this

`tests/test_i18n.py:78 test_catalog_is_complete` asserts every key is **present**
(`:80` — *"{len(missing)} untranslated"*). A key whose value is the English
source string is present, so it passes. There is no check anywhere that a
short UI string is actually different from its key. That is precisely how the
same three strings survived two rounds that each claimed to have dealt with
them.


## 7. THE OWNER'S QUESTION — Check & Refine and the project/run dialog

**Short answer: it CAN be done, it is roughly a day's work, and I recommend
NOT doing it for beta 6 — but the tab does need one small change, because it
already imports today and does it worse than anywhere else in the app.**

### What Check & Refine actually does with a `.ti3`

`ui/tabs/tab_check_refine.py:1198-1225`. `_on_browse_ti3` runs the file through
`ui.ti2_loader.resolve_ti3` (`ui/ti2_loader.py:1028`), which has three outcomes:

| the file is… | what happens |
|---|---|
| inside a project | returned unchanged (`ti2_loader.py:1050`) |
| outside, with a sibling `.ti2` | the **full chart-import flow** — `_handle_outside` → `_ask_profile_name` → a whole new project is created |
| outside, bare | `_handle_outside_ti3_only` (`:1534`) — a **new measurement-only project** is created |

So this tab is **already an import door**. It just has the *old* one: name a
project, or overwrite one. No project list, no run picker, no "File it in
Run 3".

### What it would take to give it the Build Profile dialog

`tab_profile._offer_import_into_a_project` (`ui/tabs/tab_profile.py:4235`) and
`_file_into_project` (`:4311`) are already written as a pair that takes
`(measurement, fm, ctl)`. Making them reusable is mechanical:

1. **Give the tab a controller.** `main_window.py:305-308` loops over
   `_tab_chart, _tab_measure, _tab_print, _tab_profile` calling
   `set_target_controller`. `TabCheckRefine` is simply not in that tuple and
   has no such method — `tab_check_refine.py:1211-1215` says so in as many
   words. Adding one is ~15 lines, copied from `tab_profile.py:5040`.
2. **Lift the two methods** off `TabProfile` into a mixin or a helper module.
   They already only use `self` for `self.window()` and as a dialog parent.
3. **Move the bar** after a successful file, which is what a controller buys.

### Why a naive version would be WRONG — four concrete ways

1. **The ICC would not follow, and the user would be told the profile is
   missing.** `_auto_fill_icc` (`tab_check_refine.py:1236-1268`) looks for
   `merged.icc` or `<stem>.icc` **beside the `.ti3`**. §I.9's "new run" is
   `duplicate_run(source, groups=("chart",))` — chart only, deliberately, so
   there is no `.icc` in it. The import would succeed and be followed
   immediately by *"No matching .icc or .icm file was found in: …"*. The tab
   would have filed the measurement and then declared itself unable to do its
   own job.
2. **The reports would move, silently.** `tab_check_refine.py:1372-1377` writes
   the quality report and the refine-strip list into
   `reports_subdir(self._ti3_path.parent)` — *next to the measurement*. Filing
   the `.ti3` into Run 3 moves every future report into Run 3's `reports/`.
   That is arguably right, but it is a change to where a user's checks land
   and it must be a decision, not a side effect.
3. **There is nothing to validate against.** §I.9's step I.5 is the whole
   safety of the import: patch count **and** patch identity, against
   `Run.chart_ti2`. Check & Refine has **no chart** — its two inputs are a
   `.ti3` and an `.icc`. A run picker with no I.5 behind it is the fault the
   spec records verbatim: *"a six-patch file bearing no relation to anything
   went into a real project with not one word on screen."*
4. **The semantics do not fit, and the spec says so.**
   `docs/design/unified_measurement_management.md` §6c:
   *"`profcheck` (Check & Refine) | a profile against **the data it was built
   from**"*. And §I.9, "Where the door is": *"The module lives on the Measure
   tab for verifications. For a profiling run the import is offered in the
   Build Profile tab… the tab a person is on already says which act they are
   performing."* Check & Refine's act is **checking**, and its `.ti3` is very
   often someone else's file, or a competitor's, or last year's. Asking "which
   run should this go in?" of a file the user only wants to look at is the
   wrong question, and answering it costs a project folder.

Under the binding-specs rule this is not ours to decide: putting an import
door on a third tab **amends §I.9's "where the door is"**, and that is
Sebastian's call.

### Recommendation

**For beta 6: do not add the dialog.** It is a feature, not a fix, it needs a
spec amendment, and three of its four failure modes above are user-visible.

**What I would fix instead, and it is small:** the tab silently creates a
project for an external `.ti3` today (`resolve_ti3` → `_handle_outside_ti3_only`).
Given that the whole point of rounds 2–4 was that measurement imports must not
happen behind the user's back, the honest minimum is that Check & Refine either
(a) **does not import at all** — check the file where it lies, write the report
beside it, which is what the tab's own report path already supports — or (b)
routes through the same door as everywhere else. (a) is a two-line change and
needs no spec amendment; (b) is the feature above. I recommend (a) for beta 6
and (b) as a backlog item with a spec question attached.

**And regardless of which:** if a controller is ever added, `tab_profile.py`'s
`_offer_import_into_a_project` / `_file_into_project` must be lifted to a shared
place rather than copied — the comment at `tab_profile.py:4356-4363` records
that the run picker's signal was once left unconnected and *"EVERY import went
to 'a new run' no matter what was selected on screen"*. A copy is how that comes
back.


## 8. End-to-end drive: anything a demanding tester would report

`~/Desktop/beta6-proof/6-final-challenge/08-end-to-end-drive.txt`,
`08-onscreen-endstate.png`, plus the Guided → Manual run in
`10-onscreen-run.txt`. Real `MainWindow`, settings sandboxed to
`/tmp/beta6-final.ini`, output in a temp folder; `~/ChromIQ` was never written
to (checked: the driver's `custom_output_path` points into `$TMPDIR`, and
`defaults read com.chromiq.ChromIQ custom_output_path` still reports the key
does not exist).

What worked, first time, with no intervention:

* **Guided** named a project, built a chart, wrote `runs/run1/E2E-Probe.ti1` and
  the TIFF, and the preview drew it (`10-onscreen-preview-click1.png`).
* **Manual** opened on the same chart, the layout panel round-tripped its
  recipe, and the live preview re-rendered the same patch set with the new
  layout (`10-onscreen-preview-click3.png` — 484 patches, 22 strips, row
  numbers 1…22, the notes band intact and clear of the labels).
* Runs were created and selected; `meta.json` was written per run.
* **Restore Used Chart** answers correctly for a run with no stored chart:
  *"This profile run has no stored chart yet. A copy is kept when you star…"*
  — greyed with a reason, which is the right state, not a failure.
* All five tabs constructed and stayed enabled.

Faults found on the drive are reported in their own sections: **10** (the
swallowed first click, which the owner met on screen and I reproduced), **1a**
(the clip-side margin), **2b** (the Gamut sheet estimate).

Two smaller things worth a tester's line:

* **The strip-indicator checkbox does twice the work it needs to.**
  `layout_options_panel.py:441-442` connects `show_indicators.toggled` to both
  `_on_show_indicators` (which itself ends in `self._emit()`, line 3282) and
  `_emit`. Measured: `changed` fires **twice** per click, so the live preview
  re-renders the whole chart twice for one tick. Nice-to-have.
* **`_rows_that_fit` is dead code** — see 1d.


## 9. Regression guards for rounds two to four (mutation-proved)

Method: put the fault back, prove it **lands** (the anchor is unique and in the
function under test; the module still imports; a probe shows the behaviour
changed), then run the whole everyday tier. Every mutation was reverted and the
revert verified byte-identical; `git status` at the end lists only this report.
Raw output: `~/Desktop/beta6-proof/6-final-challenge/09-mutations.txt`.

| fault put back | landing proof | tier | verdict |
|---|---|---|---|
| **R4-1** a missing `text_edge_clip` reads as zero (`raster.py:432`) | anchor unique, imports | `2 failed` | **CAUGHT** — `test_the_estimate_matches_what_is_built.py`, both tests |
| **R3-5b** the left margin is no longer raised (`raster.py:435`) | anchor unique, imports | `1 failed` | **CAUGHT** — `test_area_first_fills_the_margin_box.py::test_patch_first_still_reserves_the_band` |
| **R2-1 / R3-2** the K4 shield releases the whole recipe bucket (`tab_chart.py:13639`) | anchor unique, imports | `1 failed` | **CAUGHT** — `test_the_chart_sidecar_never_files_into_the_target.py::test_an_ordinary_panel_edit_does_not_hand_the_run_back_to_the_chart` |
| **R3-5a** the band goes back to a fixed 7.5 mm (`row_label_band_mm`, `raster.py:1843`) | **measured**: CR30 A4 band `9.432 / 3.439 / 29.752 mm` at 0 / 2 / 24 mm text → all `7.500`; margin_l `14.43 / 8.44 / 34.75` → all `12.50`; patches per sheet `345 / 368 / 322` → all `345` | `8366 passed` | **NO GUARD** |
| **R3-1** scalar UI values are shielded again (`tab_chart.py:13591` + `:13705`) | **measured**: driving `_keep_the_targets_own_values` with `ui:mode` imposed, the app's `'manual'` is overwritten back to the stored `'gamut'` — the verification-target regression, reproduced | `8366 passed` | **NO GUARD** |

### The two holes, plainly

1. **§R1.2 — "the band is not a fixed 7.5 mm, because the label text size
   varies" — has no test at all.** It is the headline rule of
   `docs/design/row_label_geometry.md`, it changes printed output and patch
   counts by up to 46 patches an A4 sheet in my mutation, and reverting it to
   the constant it replaced passes 8,366 tests. What *is* guarded is that the
   margin gets raised (R3-5b) — not what it is raised **by**.

2. **The regression round three found on screen — a verification target
   reopening in the wrong module — has no test.** The commit message for
   `8d422c84` says the K4 and F1 fixes were given guards "each proven by a
   mutation that lands", and both of those hold up here. The regression that
   the same commit *fixed* did not get one. Putting it back is green.

Not separately mutation-tested, and I say so rather than implying coverage:
F5 (learn decline vs failure), F1 (`_set_engine_checked`), Restore Used Chart
dropping the shield, the "row indicators" rename, the import button naming the
run, and the `TooltipButton` accent. The K4 and Restore-Used-Chart guards are
the two the commit message claims and describes in detail, and the K4 one is
confirmed above.


## 10. The owner's item 10 — the first click on "Show row indicators" is swallowed

**Severity: SHOULD-FIX for beta 6** (a printed-output setting needs three clicks
to take effect, and the preview and the built chart can disagree). Not a
BLOCKER: nothing is destroyed and the workaround is to click again.

### The cause, and the coordinator's hypothesis is HALF right

`ui/dialogs/layout_options_panel.py:474-476`

```python
self._row_indicators_touched = False
self.show_row_indicators.clicked.connect(self._mark_row_indicators_touched)
self.show_row_indicators.toggled.connect(self._emit)
```

`QAbstractButton` emits **`toggled` before `clicked`** — `nextCheckState()` runs
inside `click()` and fires `toggled`, and `clicked` is emitted afterwards. So on
the very first click the order is:

1. `toggled(True)` → `_emit()` → `changed` **is emitted** (the signal is NOT
   swallowed — that half of the hypothesis is wrong);
2. the consumer calls `apply_to_recipe`, which at
   `layout_options_panel.py:3719-3720` reads
   `self.show_row_indicators.isChecked() if self._row_indicators_touched else None`
   — and `_row_indicators_touched` is **still False**, so it returns **`None`**;
3. only then does `clicked` fire and set `_row_indicators_touched = True`, with
   nothing re-emitting.

So the refresh happens and costs a full preview render; it just renders the
*unchanged* recipe. The preview is right for the recipe it was handed; the
recipe is wrong.

### Measured — the real panel, real `QTest.mouseClick` on the real box

`~/Desktop/beta6-proof/6-final-challenge/10-row-indicator-clicks.txt`. Each row
is what `apply_to_recipe()` returns inside the `changed` handler:

| instrument | click 1 | click 2 | click 3 |
|---|---|---|---|
| i1  (default OFF) | box ON, recipe **None**, band 0.00, margin_l 26.00 | box OFF, recipe False, band 0.00, margin_l 26.00 | box ON, recipe **True**, band **6.89**, margin_l **33.89** |
| p3  (default OFF) | box ON, recipe **None**, band 0.00 | box OFF, recipe False, band 0.00 | box ON, recipe True, band 9.43 |
| CM  (default OFF) | box ON, recipe **None**, band 0.00 | box OFF, recipe False, band 0.00 | box ON, recipe True, band 9.43 |
| CR30 (default ON) | box OFF, recipe **None**, band **9.43 (still on)** | box ON, recipe True, band 9.43 | box OFF, recipe False, band 0.00 |
| SS  (default ON)  | box OFF, recipe **None**, band **6.08 (still on)** | box ON, recipe True, band 6.08 | box OFF, recipe False, band 0.00 |

This reproduces the owner's sequence exactly, and explains why his step 5
("turned it OFF — the preview refreshed") looked like a refresh while nothing
appeared: on an i1 the *geometry is identical* for `None` and `False`
(band 0.00, margin_l 26.00 in both). **Three clicks are needed before a row
label is printed** on i1/p3/CM, and three before one stops being printed on
CR30/SS.

### It is NOT Guided that arms it

The arming condition is `_row_indicators_touched == False`, which
`_set_recipe_impl` resets on every load from a recipe whose field is `None`
(`layout_options_panel.py:3572`). Measured above on a **freshly constructed
panel with no Guided step at all** — five instruments, all five swallow the
first click. Guided's generate merely reloads the panel, which is one of many
ways to re-arm it: switching target, switching run, Restore Used Chart and
loading a preset all reset the same flag.

### Crossed against every other checkbox on the panel — only the tri-state one

Same driver, same clicks, `show_indicators` (strip letters), `nolimit`,
`helper_markers_cb`, `export_pdf`: every one of them reports the new value on
click 1. They are plain booleans read straight off the widget, with no
"who touched it" flag to be late. **The fault is specific to
`show_row_indicators`**, the only tri-state control on the panel.

### Side finding while crossing them — the strip-indicator box emits twice

`layout_options_panel.py:441-442` connects `show_indicators.toggled` to BOTH
`_on_show_indicators` (which itself ends in `self._emit()`, line 3282) and
`_emit`. Measured: **`changed` x2 on every strip-indicator click**, so the live
preview renders the same chart twice. Nice-to-have; wasted work only.


### ON SCREEN, in the real window — the owner's exact sequence

`~/Desktop/beta6-proof/6-final-challenge/10-onscreen-run.txt`, driver
`10-driver-onscreen.py`. Real `MainWindow`, settings sandboxed to
`/tmp/beta6-final.ini`, output in a temp folder, Guided generate → Manual →
`auto_update_preview` ON → three clicks on the real checkbox:

```
   during `changed` #1: touched=False recipe.show_row_indicators=None  signature-unchanged=True
 click 1: box=True  touched=True  recipe=True   preview-timer-armed=False   <-- NEVER ARMED
   during `changed` #1: touched=True  recipe.show_row_indicators=False signature-unchanged=False
 click 2: box=False touched=True  recipe=False  preview-timer-armed=True
   during `changed` #1: touched=True  recipe.show_row_indicators=True  signature-unchanged=False
 click 3: box=True  touched=True  recipe=True   preview-timer-armed=True
```

The screenshots `10-onscreen-preview-click1.png` and
`10-onscreen-preview-click3.png` show it: no row numbers after click 1, the
1…22 band after click 3.

### The full chain, cited

1. `layout_options_panel.py:476` — `toggled` → `_emit` → `changed`, emitted
   **before** `clicked` sets the flag.
2. `layout_options_panel.py:3719` — `apply_to_recipe` returns `None` because
   `_row_indicators_touched` is still False.
3. `tab_chart.py:4574` — `panel.changed` → `_refresh_manual_command_preview`,
   synchronously.
4. `tab_chart.py:4936` → `_maybe_schedule_auto_preview`.
5. `tab_chart.py:17687` — `if self._layout_signature() == self._last_auto_sig:
   return` — the signature (`tab_chart.py:17539`, `repr(recipe.to_dict())`) is
   **identical**, so the 450 ms timer at line 17689 never starts.
6. `layout_options_panel.py:475` — `clicked` then sets the flag and emits
   nothing. No later signal re-schedules anything.

### It is NOT only the preview — the preview and the CHART disagree

`10-build-vs-preview.txt`. After ONE click, read back from the same panel:

```
  before click            show_row_indicators = None
  inside `changed`        show_row_indicators = None   <- what the preview renders
  read afterwards (build) show_row_indicators = True   <- what the CHART gets
```

`tab_chart.py:18254` reads `_current_layout_recipe()` live at build time, by
which point the flag is set. So: **click the box once and press Generate Chart,
and the printed sheet carries row labels — with a raised left margin and a
different patch count — while the on-screen preview shows the sheet without
them.** That is why this is a should-fix and not a cosmetic lag.

## 11. Found while checking my own safety — the settings sandbox has one hole

**Severity: should-fix (development safety, not product).**

`core/settings.py:796-798` promises:

> *"set `CHROMIQ_SETTINGS_FILE=/some/scratch.ini` and the app physically cannot
> reach the real store."*

`core/i18n.py:64` reaches it:

```python
from PyQt6.QtCore import QSettings
custom = QSettings("ChromIQ", "ChromIQ").value("custom_output_path", "")
```

That is the real `~/Library/Preferences/com.chromiq.ChromIQ.plist`, not
`AppSettings`, and `user_i18n_dir()` is called from `_catalog_file` — i.e. on
**every `set_language`** — and from `translate_parameters`.

Measured (`11-settings-sandbox-hole.txt`), with the sandbox set and
`custom_output_path` pointed at a temp folder:

```
AppSettings store     : /tmp/beta6-sandbox-proof.ini
AppSettings value     : '/tmp/some-temp-folder'
raw QSettings store   : /Users/Basti/Library/Preferences/com.chromiq.ChromIQ.plist
i18n.user_i18n_dir()  : /Users/Basti/ChromIQ/i18n        <- the REAL folder
```

It is a **read**, so nothing of the owner's can be corrupted through it, and I
verified by value after every run that `custom_output_path` is still the
owner's (empty string = the default `~/ChromIQ`) and that `~/ChromIQ` has not
been written to since 31 Aug 08:00. But two things follow:

1. A driver author who reads CLAUDE.md's sandbox rule and believes it will be
   wrong about this one path — and this project has already lost a day to a
   settings leak.
2. `tests/conftest.py` sandboxes `core.settings.QSettings` by name
   (commit `322c3d20`); `core.i18n` imports `QSettings` itself, so **the test
   suite is not sandboxed here either**. Every test that calls `set_language`
   reads the developer's own plist and can pick up translation overrides from
   the developer's own `~/ChromIQ/i18n` — the same class of shared state that
   commit was written to remove.


---

## Verdict

### Is it safe to tag beta 6?

**Not as it stands — but it is close, and nothing here destroys data.** One
finding changes printed output behind the user's back, one makes the app tell
the user a number that is wrong by up to 6×, and one ships an English button to
eleven languages. Those three are what I would clear first.

### The shortest list that would make it safe

| # | What | Where | Why it blocks |
|---|---|---|---|
| 1 | **The first click on "Show row indicators" is swallowed** | `ui/dialogs/layout_options_panel.py:475-476` | The preview and the built chart **disagree** after one click (§10). It is the owner's own reproduction, it takes three clicks to turn a printed feature on, and the same fault silently discards the answer in Preferences → Chart Layout (§3d). The fix is to emit after the flag is set — e.g. mark `touched` from `nextCheckState`/`pressed`, or re-emit from `_mark_row_indicators_touched`. |
| 2 | **The Gamut module's "≈ N sheets" ignores the Manual layout** | `ui/tabs/tab_chart.py:15187`, `:15358` | Wrong in 8 of 8 measured layouts, by up to 6.25× (88 real vs 550 claimed), while its own docstring says "EXACT" (§2b). Route it through `LayoutRecipe.build_kwargs()` like every other estimate. |
| 3 | **The run-naming button is English in 11 of 12 languages** | `data/i18n/*.json`, 3 keys | Round two introduced it with English values; round three fixed German only and reported it fixed (§6b). Cheap to clear, and it is a button the owner's tester will meet. |

### Should-fix, but I would not hold the tag for them

| # | What | Where |
|---|---|---|
| 4 | The left margin is raised 16 mm for a clip border that is on the **right** — 81 patches an A4 sheet (§1a) | `workflow/layout_engine/raster.py:433` |
| 5 | "Untouched" becomes "explicitly off" through `from_build_kwargs` when the strip letters are off — the tri-state stickiness, reintroduced (§3b) | `workflow/layout_engine/presets.py:381`/`:242` |
| 6 | The >99-row clamp does not do what its docstring promises; a wide label is clamped at the paper edge, not at the floor (§1b) | `raster.py:1356` vs `:1838` |
| 7 | The twelve teardown errors are an unowned pipe leak in `reap_live_sessions`, and closing the pipes removes them entirely (§5) | `tests/helpers/replay_tools.py:78-93` |
| 8 | `core/i18n.py:64` escapes the settings sandbox (§11) | `core/i18n.py:64` |

### Nice-to-have

`_rows_that_fit` is dead code (§1d); two different defaults for a missing `dpi`
in one module (§1e); the strip-indicator checkbox emits `changed` twice per
click (§8); the residual auto-text-size circularity, ≤ 0.51 mm (§1c).

### Where guards are missing — say it plainly

* **§R1.2, the headline rule of `docs/design/row_label_geometry.md`, has no
  test.** Reverting the band to the fixed 7.5 mm it replaced changes the band,
  the margin and the patch count on a CR30 A4 sheet, and 8,366 tests pass
  (§9).
* **The verification-target regression round three fixed has no test.** Putting
  it back — proven to land, the app's own module choice overwritten by the
  stored one — is green (§9).
* **`tests/test_i18n.py` cannot see an untranslated value.** It checks that keys
  are *present*, so an English value passes; that is how the same three strings
  survived two rounds that each claimed to have dealt with them (§6c).
* **The run-switch leg of K3/K4 is unverified by me** — my harness could not
  drive it honestly, and I am not reporting the state it produced (§4c).

### What held up under attack, and deserves saying

* The 368-on-a-345-sheet fix: **40 of 40** Guided combinations agree between the
  estimate and the build.
* The row-label geometry: **14,976** combinations, **0** off-page margins and
  **0** layouts that fail with row indicators on but succeed without.
* The K3/K4 shield survived the tri-state attack — because it requires *both*
  of its two conditions, and the second one saved it (§4a).
* The import dialogs: **0** button overlaps in 13 languages × 3 project counts
  × 2 dialogs, and **0** clipped run-naming labels over 16 labels × 13
  languages. The German 560 → 697 floor is doing exactly what it was written
  for.
* Nothing in `~/ChromIQ` was touched, `~/Desktop/i1Profiler` was not touched,
  the working tree is clean apart from this report, and every source mutation
  was restored and verified byte-identical.

---

**STATUS: complete.**

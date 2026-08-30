# Verification 3 — are R1–R4 actually fixed?

STATUS: complete

Adversarial re-verification of the four fixes made in answer to
`docs/reports/04-challenge-name-dialog-and-fixes.md`, whose verdict was
**NO — do not tag**. Working tree on `master`, uncommitted, 2026-08-31.

Proof folder: `~/Desktop/knut-fixes-verify-3/` — `shots/`, `logs/`, `work/`
(rendered TIFFs and their geometry sidecars), `backup/`, `INDEX.md`.

## Method
- The real `MainWindow` in a real `QApplication`, on screen, driven through the
  real signals (`QComboBox.activated`, `QTest.keyClicks`, `_on_generate`).
  No re-implementation of anything under test.
- A modal watchdog records every window that opens — class, title, buttons,
  every label, the line-edit contents — screenshots it, then acts. An unplanned
  modal is screenshotted and rejected, so a missing window and an extra window
  are both recorded results.
- Data loss is measured by SHA-1 fingerprints of every file in the project
  before and after.
- Every claim about ink on paper is a pixel count from a rendered TIFF, in a
  window taken from **that sheet's own geometry sidecar**.
- Sandbox: `core.settings.QSettings` **and** `core.i18n.QSettings` redirected to
  a temp `.ini` seeded from the real store, `CHROMIQ_PRESETS_DIR` a copy,
  `custom_output_path` a temp root, and a tripwire on `FileManager.root_dir`
  that raises if it ever resolves to `~/ChromIQ`. It never fired.

## Safety — NO DRIFT

| | before | after |
|---|---|---|
| `~/Library/Preferences/com.chromiq.ChromIQ.plist` | `d45d76f1…` | **`d45d76f1…` — identical** |
| `~/Library/Preferences/ChromIQ/presets/` | — | **byte-identical (`diff -rq` clean)** |
| `~/ChromIQ` top level | 23 entries | **identical** |
| `~/ChromIQ` to depth 3 | 229 entries | **identical** |
| `ui/tabs/tab_chart.py` after four mutations | `b68bd588…` | **`b68bd588…` — restored exactly** |

`~/ChromIQ/CR30-Test` was never touched. No source file was edited except the
four deliberate, checksum-verified mutations in §5, all reverted.

---

# 1. R1 — the name is now gated on every route. VERIFIED FIXED.

The side-by-side from report 04, repeated: **same preset, same name, same
project**, once typed into the NAME BOX and once into the NEW DIALOG. SHA-1 of
every file before and after. `scripts/zz_v3_r1.py`, log `logs/r1.log`.

| # | route | name given via | §S4.7 shown | files changed | files gone |
|---|---|---|---|---|---|
| A | prebuilt (TC3.00) | **box** (`keyClicks`) | ✅ 4-button window | `[]` | `[]` |
| B | prebuilt (TC3.00) | **dialog** | ✅ 4-button window | `[]` | `[]` |
| C | `.ti1` (Knut i1 162p) | **box** | ✅ | `[]` | `[]` |
| D | `.ti1` (Knut i1 162p) | **dialog** | ✅ | `[]` | `[]` |
| E | Generate Chart, empty box | **dialog** | ✅ | `[]` | `[]` |
| E2 | Generate Chart | **box** (control) | ✅ | `[]` | `[]` |

Report 04's control B produced **one** window and replaced seven files including
the `.ti2`. It now produces **two** windows — "Give this project a name", then
"There is already a project called “ZZ-verify3-PB”" with
`[Continue this project] [Replace it] [Use a different name] [Cancel]` — and
Cancel changes nothing. Shots `V3-B-pb-dialog-01/02.png`,
`V3-D-ti1-dialog-01/02.png`, `V3-E-gen-dialog-01/02.png`.

## The routes and answers the side-by-side does not reach
`scripts/zz_v3_r1b.py` / `zz_v3_r1c.py`, logs `r1b.log` / `r1c.log`.

| case | result |
|---|---|
| F — a second prebuilt built-in (ABW1110) | name dialog → §S4.7 → Cancel; nothing changed |
| G — **Guided** mode + Generate, empty box | name dialog → §S4.7; the name lands in **both** name fields; nothing created |
| H — a project already OPEN, name box cleared, prebuilt preset | **no dialog at all**, chart added to the open project, target still `ZZ-verify3-H`; **no folder named after the preset**. This is `tab_chart.py:11241`'s `(None if _named else default_name)` doing its job |
| I/L — dialog name + **"Replace it"** + confirm | archived to `old/2026-08-31_000542/` (11 files), rebuilt in the same project under the right stem `ZZ-verify3-R.ti2`; no new root created |
| J — dialog name + **"Continue this project"** | `run2` created inside `ZZ-verify3-I`; target name correct; no new root |
| M — dialog name + **"Use a different name"** | nothing built, nothing on disk, `_pending_replace=None`, `_adopted_via_gate=False`, `_layout_owned_by_build=False` — **but the name box comes back EMPTY**, see N2 below |

## Cancel at the new, EARLIER ask (#175) — clean on all three routes
Case K, three preset routes, `logs/r1b.log`:

```
combo now = 0 (was 0) data=None          <- dropdown reverted to "none"
name field = ''  typed_flag=False
_pending_replace=None _adopted_via_gate=False _layout_owned_by_build=False
_prebuilt_active=False _knut_active=False _tc918_active=False
is_named=False       roots created = []
```

Moving the ask earlier introduced **no** #175 regression.

## Scope note — only two preset families are reachable
`TC918_PRESET_KEY` and every `MUNKI_TARGEN` key are absent from
`BUILTIN_PRESET_KEYS` (`tab_chart.py:2083`), so `_apply_tc918_preset` and
`_apply_colormunki_td_preset` cannot be reached from the dropdown or the ★
overlay — `findData` returns −1. The two live families are the prebuilt files
and the Knut `.ti1` presets, and both are covered above.

---

# 2. R2 — the warning now fires on exactly the right charts. VERIFIED FIXED.

Eight combinations (4 clip-content modes × 2 clip sides), and for each one the
warning and the ink come from **the same recipe**: the panel's own normalised
`_current_layout_recipe()`, which is what the inspector judges.
`scripts/zz_v3_r2final.py`, log `logs/r2-final.log`.

The measuring window is the row-number band taken from each render's own
`.strips.json` — `[x0 − 9 mm, x0]` over the patch rows.

| clip content | side | ink in the band, rows OFF | rows ON | digits add | digits covered | warning fires | |
|---|---|---|---|---|---|---|---|
| `off` | left | 0 | 20 993 | **+20 993** | no | no | OK |
| `off` | right | 0 | 19 980 | +19 980 | no | no | OK |
| `notes` | left | 18 706 | 18 710 | +4 | **yes** | **yes** | OK |
| `notes` | right | 0 | 19 980 | +19 980 | no | no | OK |
| `text` | left | 36 491 | 36 491 | 0 | **yes** | **yes** | OK |
| `text` | right | 0 | 19 980 | +19 980 | no | no | OK |
| `image` | left | 36 491 | 36 491 | 0 | **yes** | **yes** | OK |
| `image` | right | 0 | 19 980 | +19 980 | no | no | OK |

**Mismatches: none.** The false positive report 04 measured (`off`/left:
96 313 dark pixels of perfectly printed digits, with a warning saying they would
not appear) is gone — that row now reads *digits print, no warning*.

Visual proof, cropped from the rendered sheets:
`shots/V3-R2-F-off-left-on-band.png` shows the numbers 1–6 printed cleanly;
`shots/V3-R2-F-notes-left-on-band.png` shows the notes band printed over them
with no digit anywhere. Looked at, not just counted.

The panel round-trip was proved separately (`logs/r2-roundtrip.log`): the
margins are re-derived by the panel (5.0 → 26.0/9.0), but every field the
condition depends on — `rlwi`, `lbord`, `fill_beyond_ruler`, `clip_side`,
`clip_content_mode` — round-trips unchanged (`geom_same=True` in all 8).

**Two probes of mine were wrong before this one was right**, and both are
recorded in the log so nobody repeats them: a fixed 20 mm window from the paper
edge contains no patches once the panel sets a 26 mm left margin (it reported
every chart "covered"), and a whole-page diff moves 1.7 M pixels because turning
the band on re-sizes the area-first patches.

---

# 3. R3 — the band is released, and a ticked box survives. VERIFIED FIXED.

`scripts/zz_v3_r2r3.py`, log `logs/r2r3.log`, shots `V3-R3a/b-*.png`.

**Half one — no dead paper.** Tick "Show row numbers" on an i1Pro, then switch
"Show strip indicators" off:

```
strip ON : box=True enabled=True  recipe=True  build_kwargs.row_indicators=True  rlwi=7.5
strip OFF: box=True enabled=False recipe=True  build_kwargs.row_indicators=False rlwi=0.0
```

**Half two — the answer survives.** Switch the strip labels back on:

```
strip ON again: box=True enabled=True recipe=True rlwi=7.5   -> SURVIVED
```

An explicit **False** survives the same round trip as False (R3e), and an
untouched SpectroScan keeps `None` throughout (R3c) — so nothing is made sticky.

**It reaches the capacity estimate AND the render**, measured in `patch_first`
where the band actually costs paper (i1Pro / A4 / 300 patches):

| | rlwi | capacity per page | patch block starts at |
|---|---|---|---|
| strip ON + row ON | 7.5 | 441 | 396 px = **33.53 mm** |
| strip ON + row OFF | 0.0 | 462 | 307 px = 25.99 mm |
| **strip OFF + row ON** (the R3 fault state) | **0.0** | **462** | **307 px = 25.99 mm** |
| strip OFF + row OFF | 0.0 | 462 | 307 px = 25.99 mm |

The fault state now lays out identically to "row numbers off": the 7.54 mm and
the 21 patches per page report 04 measured as lost are back, in the estimate
(441 → 462) and on the sheet (33.53 → 25.99 mm). The derivation lives in one
place, `presets.py:build_kwargs`, which both `geom_from_build_kwargs` (every
capacity estimate) and `chart.build_chart` (the render) read.

---

# 4. R4 — fixed in the dialog, NOT in the name box. PARTIALLY FIXED.

`scripts/zz_v3_r4.py`, log `logs/r4.log`.

**The dialog is correct at the byte boundary** (`name_prompt.py:79`):

| typed | chars | bytes | result |
|---|---|---|---|
| 120 ASCII | 120 | 120 | accepted |
| 121 ASCII | 121 | 121 | refused — "too long for a folder" |
| 40 emoji | 40 | 160 | refused (too long) |
| 30 emoji | 30 | 120 | refused (no letters or numbers) |
| 40 CJK | 40 | 120 | accepted |
| 41 CJK | 41 | 123 | refused (too long) |
| 250 ASCII | 250 | 250 | refused |
| 120 ASCII + trailing spaces | 125 | 120 | accepted (trimmed first) |

Driven on the real preset route with 250 characters: Continue is **disabled**,
the red error is shown, `roots created = []`, `is_named = False` — **nothing
half-built**. Shortening the name in the same window then builds normally
(case N2b). `shots/LONG-01b-typed.png`, `V3-N2-long-01b-typed.png`.

**But the identical fault reproduces verbatim one box over.** The
"Printer profile project name" field has **no length cap at all**
(`maxLength = 32767`, Qt's default — nothing in `ui/tabs/tab_chart.py` or
`core/file_manager.py` sets one). Pasting the same 250 characters there and
picking a preset:

```
[ERROR] ui.tabs.tab_chart: Prebuilt copy failed: [Errno 63] File name too long:
  …/ZZZ…(250)/runs/run1/ZZZ…(250).channels.json
MODAL: "Could not create target"   [Close]
LEFT BEHIND: 7 entries — project.json, "Where are my files.txt",
             runs/run1/, the .ti1, the .ti2, meta.json
is_named = True          <- the app is now pointed at the broken folder
```

That is report 04's R4 word for word (`04-…md:167-184`), and #175's "a refused
action leaves nothing behind" is broken exactly as it was. The cap belongs in
`validate()` **and** on the field — or, better, at the one place that makes the
folder. Not a regression from this work; not fixed by it either.

---

# 5. Is the fix guarded by tests? Mutation-proved, and the answer is "two of three".

Four guards were deleted one at a time, each removal asserted to have landed
(`assert s.count(block) == 1`), the file restored and re-checksummed after every
run. 126 tests across the five name/preset files:

| guard removed | file:line | result |
|---|---|---|
| `_on_generate`'s ask | `tab_chart.py:12218-12226` | **1 failed** — `test_a_name_given_in_the_dialog_is_checked_against_existing_projects` |
| `_generate_from_ti1`'s ask | `tab_chart.py:11428-11437` | **2 failed** — `test_knut_newbatch.py::test_g1_generate_from_ti1_asks_instead_of_inventing`, `…::test_g1_the_live_preview_never_asks_for_a_name` |
| **`_apply_prebuilt_preset`'s ask** | `tab_chart.py:11081-11092` | **125 passed** — nothing caught it |
| `_create_prebuilt_target`'s ask | `tab_chart.py:11202-11218` | **125 passed** — nothing caught it |

Widened to every test file that names the prebuilt route
(`test_preset_honors_bar_run`, `test_knut_issues_45_59_60_62`,
`test_prebuilt_presets_offer_no_setup`, `test_per_target_settings_events`,
`test_preset_panel_locks`, `test_a_loaded_patch_set_is_the_one_built`,
`test_new_run_creation_rules`, `test_the_marker_follows_the_editable_design`,
`test_project_name_collision`, `test_chart_integrity`): **208 passed with the
guard deleted.**

**And the guard is load-bearing.** With it removed, driven on screen
(`scripts/zz_v3_mut.py`, `logs/mutation-negative-control.log`):

```
MODALS SEEN (1): ['Give this project a name']       <- no §S4.7
files changed = ['runs/run1/cache/new_run.json',
                 'runs/run1/exports/ZZ-mut-i1profiler.pxf',
                 'runs/run1/meta.json']
```

R1 comes straight back, in the same silence, on the same route report 04
measured it on — and 333 targeted tests stay green. `_create_prebuilt_target`'s
own guard is dead on this route (the box is no longer empty by the time it
runs), which is exactly why it could not save the fix.

**The fix is right; the fence around it has a gap.** Report 04's requirement was
"a driven test … on both the prebuilt and the `.ti1` route"; the new unit test
covers `_on_generate` only.

---

# 6. New findings

**N1 — R4 is only half fixed** (§4 above). The 250-character crash and the
half-built project are still reachable through the name box.

**N2 — "Use a different name", reached from the dialog, is a dead end.**
Measured side by side (`logs/r4.log`, case N4):

```
from the DIALOG : name box after = ''               combo = None
from the BOX    : name box after = 'ZZ-verify3-N4'  combo = None
```

The person names the project in the new window, is told the name is taken,
picks "Use a different name" — and gets an **empty** box, the preset dropdown
back at "none", and nothing to edit. #175's undo (`_restore_preset_state`) wipes
the name the dialog just wrote, after `_focus_project_name_field`
(`tab_chart.py:9181-9187`) has put the cursor in it. That is the "explain it, close,
make them start again" dead end `_ask_for_a_project_name`'s own docstring says
this work set out to remove — reintroduced one window later. Reachable only
because §S4.7 can now fire on a preset route at all, so it is **new**.

**N3 — the row-number box can disagree with the sheet.** `logs/r2r3.log`, R3d.
Load a recipe that has strip indicators off, on a SpectroScan or CR30, then
switch the strip labels back on:

```
loaded (strip off): box=False enabled=False recipe=None rlwi=0.0
strip switched ON : box=False               recipe=None rlwi=7.5   <- numbers WILL print
```

`_row_indicators_default` (`layout_options_panel.py:3191-3205`) asks
`build_kwargs()`, which since the R3 fix answers False whenever the strip labels
are off — so the box is drawn clear, while the untouched `None` recipe still
resolves to the instrument's own 7.5 mm band once the labels come back. Costs no
paper and loses nothing; the box simply lies. One click either way corrects it.

**N4 — the prebuilt guard has no test** (§5 above).

**N5 — `scripts/zz_p10_rows2.py` cannot see the R2 fix and must not be
trusted.** Its "W" section re-implements the warning condition by hand:

```python
fires = (g.rlwi > 0 and g.fill_beyond_ruler and g.lbord > 0
         and (getattr(g, "clip_side", "left") or "left") == "left")
```

It never calls `_engine_text_overflow_warnings`, so it still reports
`clip=off side=left → WARNS=True` — the pre-fix answer, for ever. Re-running it
as a check would have produced a false "R2 is not fixed".

**N6 — the new dialog's wording has been through no catalogue.**
`test_message_catalogue.py`'s `WINDOW_SOURCES` is an allow-list of *measurement*
windows; "Give this project a name" is a Create Chart window (its sibling
`_project_exists_message` **is** in the list, `test_message_catalogue.py:323`)
and is in neither the list nor §M. The suite is green because nothing looks at
it. Report 04's W3 judged the wording good; this is a process gap, not a text
defect.

**N7 — `ui/dialogs/name_prompt.py` IS UNTRACKED.** `git status` shows it under
`??`, and `ui/tabs/tab_chart.py:12169` imports it. A commit that does not add it
ships an app that raises `ModuleNotFoundError` the first time anybody picks a
preset with an empty name box. `tests/test_row_numbers_follow_the_instrument.py`
is untracked too. Both must be `git add`ed before anything is tagged.

**N8 — 23 untracked `zz_*` / `drive_55_*` driver scripts are still in
`scripts/`.** They are throwaway probes from three reporting passes (mine
included), one of them actively misleading (N5). They should be deleted before a
tag — none is referenced by any test or by the app.

---

# 7. Tests run

380 targeted tests green, no `--runslow`, no source edited during any run:
`test_i18n`, `test_message_catalogue`, `test_design_specs_are_binding`,
`test_row_numbers_follow_the_instrument`, `test_layout_presets`,
`test_layout_options_panel`, `test_layout_geometry`,
`test_project_name_is_never_invented`, `test_project_name_collision`,
`test_knut_newbatch`, `test_backing_out_of_a_preset_changes_nothing`,
`test_scanner_builtin_presets`, `test_the_live_preview_only_follows_the_user`,
`test_live_preview_does_not_replace_a_preset`, `test_txt_loader`.
`python scripts/i18n_extract.py --missing de` → **0 missing of 4676**.

## The four changed test fixtures
None is vacuous, and each change was necessary rather than convenient: with an
empty name box these tests would now sit on a real `QDialog.exec()` in a
headless run.

- `test_backing_out_of_a_preset_changes_nothing.py:96-98` — the refusal is still
  injected at `_generate_from_ti1` / `_create_prebuilt_target` returning False
  (`:102-105`), which is what a real refusal ends in. Every assertion about
  settings, mode, printtarg rows, the dropdown, family flags and tick boxes is
  untouched and still runs. `setText` does not fire `textEdited`, so
  `_name_typed_by_user` stays False and §S4.7 stays silent — the test's own
  subject is unaffected.
- `test_scanner_builtin_presets.py:186-190` — subject is the engine flag; the
  name only stops the preset being refused before it can be measured.
- `test_the_live_preview_only_follows_the_user.py:341-345` and
  `test_live_preview_does_not_replace_a_preset.py:47-51` — subject is queued
  re-renders and settling; a project name changes neither.
- `test_layout_presets.py:60` — adds `show_row_indicators=False` to the
  all-fields round-trip. It strengthens the test rather than weakening it.

The one thing the fixtures do cost: no automated test now exercises a built-in
preset with an **empty** name box, which is the state the whole fix is about.
That is the same hole as N4, seen from the other side.

---

# 8. VERDICT

## Report 04's "NO — do not tag" can be reversed on R1, R2 and R3. It cannot be reversed as written on R4, and there is one new hard blocker that has nothing to do with the four fixes.

**Required items from report 04 §6:**

| | required | status |
|---|---|---|
| R1 | §S4.7 asked about the name the person typed, on all three routes | **DONE** — 11 driven cases, both routes, both name entry points, fingerprinted |
| R3 | no recipe reaches the engine with the band reserved and nothing drawn | **DONE** — recipe, capacity estimate and render, both halves |
| R2 | `and r.clip_content_mode != "off"` | **DONE** — 8/8 combinations against pixels |
| R4 | a length cap in `validate()` | **HALF DONE** — the dialog is right; the name box has no cap and still crashes on Errno 63 leaving a half-built project |

**Safe to tag as a beta? YES — after two things that take minutes:**

1. **`git add ui/dialogs/name_prompt.py` and
   `tests/test_row_numbers_follow_the_instrument.py`** (N7). Without the first,
   the tagged build raises `ModuleNotFoundError` on the first preset picked with
   an empty name box. This is the only true blocker I found.
2. **Delete the 23 untracked `zz_*` / `drive_55_*` scripts from `scripts/`**
   (N8), including `zz_p10_rows2.py`, which reports the pre-fix answer for R2
   for ever (N5).

**Not blockers, but they should be on the list before GA**, in this order:

3. **N1 / R4's other half** — cap the name box, or cap at `set_target_name` /
   `Project.create` where every route passes. Today one paste still leaves a
   250-character broken project behind, against #175.
4. **N4** — a test on the prebuilt route. The guard that stops report 04's
   critical finding can be deleted and 333 targeted tests stay green; I proved
   both halves of that (the mutation lands, and the fault returns).
5. **N2** — "Use a different name" from the dialog should hand the name back to
   an editable box, or simply re-open the dialog with the name pre-filled.
6. **N3** — the row-number box drawn clear on a chart that will print numbers.
7. **N6** — put "Give this project a name" through §M-PROPOSED and add it to
   `WINDOW_SOURCES`, so its wording is governed like its sibling window.

Everything else in report 04 that was not in scope here — R5, R6, O1–O8 and the
i1Profiler round trip (G) — is untouched by this work and still open.

STATUS: complete

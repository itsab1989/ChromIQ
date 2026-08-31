# End-to-end verification — the loader wording, F2, F4, and what a window promises

STATUS: complete

Adversarial verification of the uncommitted work on top of v4.1.5-beta.5.
Every result below was measured by driving the REAL app on screen — real
`MainWindow`, real tabs, real projects in a scratch working folder, modals
driven by clicking their real buttons. No mock harness. `CHROMIQ_SETTINGS_FILE`
pointed at a scratch `.ini` before anything constructed `AppSettings`, and every
driver asserted on `AppSettings._qs.fileName()` before building a widget.

**Proof:** `~/Desktop/knut-wording/` — `INDEX.md`, `shots/` (a PNG and a JSON of
every observable, for every window whose words changed), `listings/`
(sha256 inventories before and after every destructive attempt).

---

## V0. Verdict

**Can a user lose work? — No.** Eleven destructive attempts across all three
import routes, under five hostile conditions, and **every single file was
recoverable by hash afterwards**: 31 of 31, 24 of 24, every time. The archive
is genuine, the rollback is genuine, and Return never replaces anything.

**Does any window still misdescribe what it does? — Yes, in six places**, and
two of them are the reverse of each other:

* the failure window says **“Nothing has been changed”** while the project it
  is talking about has already been emptied into `old/` — driven, `lie2`;
* the same window fires for errors that have nothing to do with a replace, and
  then says a replace failed when none was attempted — driven, `lie`;
* it names the **working folder** where §S4.7's twin names the project;
* the bare-`.ti3` name prompt is still titled **“Copy Chart Files”**;
* the self-collision refusals still say *“the measurement's own folder”* for a
  file three levels down inside the project, and one of them still says
  **“overwrite”**;
* a **third** replace dialog — *Copy the whole project in* — still says
  **“Replace existing”**, its own red line names a button called *“Replace it”*
  that is not on the window, and it archives a whole project on **one click,
  with no confirmation at all**.

**Is M-IMPORT-REPLACED-KEPT shown? — No. It has no call site.** Neither does
M-IMPORT-PROJECT-EXISTS. Two of the three new catalogue entries, and their 24
translations, are dead. Section VC.

And the guards: three of the five things this pass fixed can be un-fixed with
the targeted suite green (VF).

---

## VA. Trying to lose a project

Every attempt used a project holding, in each of 3–4 runs: a `.ti2`, a `.ti3`
measurement, an `.icc` profile, a printed page TIFF, `reports/report_N.json`,
`exports/…-colours.txt`, and a **typed run description** in `meta.json`; plus a
project-level `exports/`. 24–31 files.

| # | route / condition | result | unrecoverable |
|---|---|---|---|
| A1 | `.txt`, project **OPEN**, Replace it | archived to `old/<stamp>/`, new empty project | **0 / 31** |
| A2 | `.txt`, **Return** on the confirmation | nothing replaced, manifest still `run4 [run1..run4]` | 0 |
| A3 | `.txt`, **Go back** | nothing replaced | 0 |
| A4 | bare `.ti3` | archived | **0 / 31** |
| A5 | `.ti2` | archived | **0 / 31** |
| A6 | `.txt`, **project root read-only** | nothing moved, failure window, manifest intact | **0 / 24** |
| A7 | `.txt`, **one sub-folder read-only** | partial archive **rolled back in full**, 24 files still in place | **0 / 24** |
| A8 | `.txt` **inside** the project, imported under the project's own name | refused, source untouched | 0 |
| A9 | replace succeeds, then the **copy** fails | project in `old/`, everything readable | **0 / 24** |
| A10 | *Copy the whole project in* ▸ Replace existing | archived | **0 / 24** |
| A11 | two `_copy_txt` replaces **5 ms apart** | `old/2026-08-31_130757` and `…-2`, first archive intact, no `runs/runs` nesting | 0 |

A11 is the same-second collision from report 09 §C3, driven through the real
`_copy_txt` rather than through `_archive_project_contents` alone. Through the
UI the two replaces land seconds apart, so the suffix path is only reachable at
function level — which is where it was measured.

**The three `rmtree` sites are gone.** `grep shutil.rmtree` over `core/`,
`ui/`, `workflow/`, `main.py` returns no live call in either loader; the only
occurrences in those two files are the comments explaining what used to be
there.

---

## VB. Making the windows lie

### VB.1 The subject IS right in the confirmation — all three routes

Measured from the live `QMessageBox`:

| route | `informativeText` ends |
|---|---|
| `.txt` | *“…and **the measurement** you are importing is put into its first run.”* |
| bare `.ti3` | *“…and **the measurement** you are importing…”* |
| `.ti2` | *“…and **the chart** you are importing…”* |

That is the W5 fix, and it works. It is also the **only** window the subject
reaches.

### VB.2 The bare-`.ti3` name prompt is still titled “Copy Chart Files”

`ui/ti2_loader.py:1188` — `dlg.setWindowTitle(tr("Copy Chart Files"))`, on the
dialog shared by three `.ti2` callers and one bare-`.ti3` caller. Captured from
the live dialog on the `.ti3` route:

```
TITLE: Copy Chart Files
LABEL: The following files from <b>outside-ti3/</b> will be copied into your
       working folder as a new profile set:  •  measured.ti3
```

Unlike a `QMessageBox` (whose `windowTitle` reaches nobody on macOS — report 11
§C3), a `QDialog`'s title bar **is** on screen. So the person importing a
measurement reads “Copy Chart Files” at the top of the window while they type
the name. Item 2 of the build fixed the confirmation and left the window the
confirmation is raised from.

### VB.3 The self-collision refusals — W4, unfixed in both loaders

Driven: a measurement at `Canon/runs/run2/measured.txt`, imported under the
name `Canon`. The guard **works** — nothing was lost — but the sentence is:

> “That name points to the measurement's own folder. Pick a different name.”

The name points at the **project the measurement is inside**, three levels up.
`dir_holds` was deliberately widened to ancestors (report 10 F1), so the
sentence became wrong in a new way at the moment the guard was fixed. Report 11
§C6 drafted the replacement — *“That name points at the project this
measurement is already inside…”* — and it was never applied.

`ui/txt_loader.py:309` and `ui/ti2_loader.py:1308` are worse: they still say
**“You're trying to overwrite the measurement's / chart's own folder.”** —
“overwrite”, the word this pass exists to remove. (Effectively unreachable
today, because `_on_name_changed` hides the Replace button on a self-collision;
still the wrong word sitting in twelve translation files.)

### VB.4 M-PROJECT-REPLACE-FAILED names the wrong folder

`tab_chart._replace_failed_message` passes **`root`** — the project. Both
loaders pass **`_resolve_working_dir(settings)`**. Measured, project root made
read-only:

> ChromIQ was going to move everything in this project into its own “old”
> folder … and it could not:
> **`/…/scratchpad/probe/work-ro-root`**   ← the working folder, not `…/Canon`

The *reason* line happens to name the right path, because the `OSError`'s own
message contains it. Change the failure and that coincidence goes.

### VB.5 The failure window fires for failures that are not a replace — **and then it lies**

Both loaders wrap the **entire** resolve function:

```python
try:
    …the whole flow…
except OSError as exc:
    _say_the_replace_failed(parent, _resolve_working_dir(settings), exc)
    return None
```

Driven twice.

**(a) No replace anywhere.** A brand-new name (`BrandNewName`, no collision),
source `.txt` chmod 000, so the only `OSError` in the story is `shutil.copy2`:

```
window : "The existing project could not be moved aside"
         "…and it could not: /…/work-lie"
         "Nothing has been changed. Anything that had already been moved has
          been put back, and no new chart has been made."
         "…or choose “Use a different name” and leave this project alone."
on disk: BrandNewName/project.json
         BrandNewName/Where are my files.txt
         BrandNewName/runs/run1/meta.json
```

Four untruths in one window: there was no existing project; nothing was moved
aside; **something WAS changed** — a half-built project is on disk and nothing
removes it; and there is no “Use a different name” button anywhere on screen at
that moment.

**(b) The worst version — a real replace, then the copy fails.** Project
`Canon`, 3 runs. Replace it → confirm → the archive **succeeds** → the source
becomes unreadable → `shutil.copy2` raises:

```
on disk: old/2026-08-31_125825/runs/run1..run3/…   (24 files, all recoverable)
         project.json  →  current_run run1, runs ["run1"]
window : "The existing project could not be moved aside … it could not …
          Nothing has been changed."
```

The project the person was looking at is now empty. They are told nothing
happened, so they have no reason to look in `old/`. **The data is safe and the
sentence is false**, which is the precise failure mode this round exists to
remove.

### VB.6 A third dialog, a third spelling, and no second look

`ui/ti2_loader._ask_project_name` — reached from **Print ▸ Load chart** (and
Measure ▸ Load chart) when the file is a complete ChromIQ project and the user
picks *Copy the whole project in*. Driven on screen with `Canon` open and a
donor project outside:

```
windowTitle : "Copy project"
buttons     : Continue (default) · "Replace existing" · Cancel
red line    : "A project named “Canon” already exists. Choose a different name,
               or Replace it (the existing one is moved to its own old/ folder)."
after one click on "Replace existing":
  message boxes raised in the whole flow : 1  (the "complete ChromIQ project" chooser)
  M-IMPORT-REPLACE-CONFIRM shown         : false
  old/2026-08-31_131043                  : the whole project, 0 unrecoverable
```

So: the button is a **third** name for the act (“Overwrite existing folder” →
“Replace it”, and this one is still **“Replace existing”**); its own red line
names a button, *“Replace it”*, that is not on the window; and it is the one
replace path in the app with **no confirmation step** — one click and the
project is archived. The consequence is right. The vocabulary and the ceremony
are not, and the ruling was about consistency of both.

---

## VC. Is M-IMPORT-REPLACED-KEPT ever shown? — **No. Say it plainly.**

```
$ grep -rn M_IMPORT_REPLACED_KEPT --include=*.py .
workflow/measurement_messages.py:1298:M_IMPORT_REPLACED_KEPT = _m(
workflow/measurement_messages.py:1308:    M_IMPORT_REPLACED_KEPT,
```

Definition and registration. **No call site.** The same is true of
**M-IMPORT-PROJECT-EXISTS**:

```
workflow/measurement_messages.py:1283:M_IMPORT_PROJECT_EXISTS = _m(
workflow/measurement_messages.py:1307:    M_IMPORT_PROJECT_EXISTS, …
```

Only **M-IMPORT-REPLACE-CONFIRM** is wired (`txt_loader.py:331`,
`ti2_loader.py:1327`), and it is the one I could photograph.

Two consequences:

1. **The promise the catalogue makes is not kept.** After a successful replace
   the person is still told nothing about where their project went — which was
   report 10's finding 9, the reason M-IMPORT-REPLACED-KEPT was written. It is
   still open; it now merely *looks* closed, because there is an entry for it in
   the catalogue and a translation for it in twelve languages.
2. **The specification now describes a window the app does not have.**
   `unified_measurement_management.md` gives M-IMPORT-PROJECT-EXISTS a button
   row — *Replace it · Use a different name · Cancel*, default Cancel, Cancel
   far right, “a Return keypress must never be a replace” — for a window that
   is never opened. The owner's ruling was that the loaders **keep their own
   prompt**; that prompt has OK / Replace it / Cancel and no such body. Under
   CLAUDE.md's rule that only confirmed behaviour goes into a specification,
   this is text describing something that does not exist.

`tests/test_message_catalogue.py` cannot catch it: it checks that a new entry is
declared awaiting approval and defined in the spec. Nothing checks that anything
renders it.

**Related, and the same shape:** the loaders' new red line —

> “{name}” is already a project. Choose a different name, or click “Replace it”.

— is a **literal in `ui/txt_loader.py:271` and `ui/ti2_loader.py:1270`**, not a
catalogue render. The comment four lines below it says why that is unsafe
(*“WINDOW_SOURCES … cannot express a module-level function — text written
straight into this file is invisible to every check we have”*). The confirmation
followed that advice; the line under the name box did not.

**§S4.8 was never written.** Report 11 §C7 drafted it and step 5 of its plan
called for it. `grep S4.8 docs/design/unified_measurement_management.md` → no
match. Three §M entries now describe messages for a route with no §S sequence.

---

## VD. F4 on screen — the run bar and the manifest after replacing the OPEN project

Driven: project `Canon`, 4 runs, opened so the bar is live; `.txt` imported over
it; Replace it.

| | before | after |
|---|---|---|
| run picker items | `Run 1 (overwrite) · Run 2 · Run 3 · Run 4 · New run` | **`Run 1 (overwrite) · New run`** |
| `project.json` | `current_run run4`, `runs [run1..run4]` | `current_run run1`, `runs [run1]` |
| run folders on disk | run1..run4 | run1 |
| `fm.project()` is the pre-replace object | — | **False** (a fresh read) |

**The bar does not lie any more, and no phantom runs are written back.** I then
went further and forced the failure: holding the pre-replace `Project` object
and calling `save_manifest()` on it puts `run4 [run1..run4]` straight back over
a folder holding only `run1`. That path does not exist in the app — the only
component that stores a `Project` is `FileManager` (`_project`, set at
`file_manager.py:732/2485/2561`), and `forget_cached_project()` clears it — but
it is what `project_replaced_on_disk()` is protecting against, and it is one
stored reference away from returning.

**Three of the four F4 call sites work. The fourth is dead code.**

```
$ grep -n _target_ctl ui/tabs/tab_check_refine.py
1216:        _ctl = getattr(self, "_target_ctl", None)
1217:        if _ctl is not None and hasattr(_ctl, "project_replaced_on_disk"):
1218:            _ctl.project_replaced_on_disk()
```

That is the only mention of `_target_ctl` in the file. `TabCheckRefine.__init__`
takes `(runner, settings, parent)` and no controller; nothing ever sets the
attribute. The `getattr` default makes it a silent no-op rather than a crash, so
it reads as done.

**And the `.ti2` loader's own call sites have no F4 at all** —
`tab_print._on_load_ti2` (`:1405`), `tab_print.set_ti2_path` (`:1341`),
`tab_measure` (`:4297`). Benign today: `_handle_outside`, the only replace path
those reach, is entered only when no project is open, so there is no stale bar
to correct. It is benign by routing, not by design, and “all four loader call
sites” is not the same statement as “every call site that can replace a
project”.

---

## VE. F2 on screen — a genuinely failing archive, through a real button

`main.py`'s own `_log_excepthook` installed; project root `chmod 0o555`; the
import driven through **Build Profile ▸ Load measurement data**, the name typed
with `QTest.keyClicks`, both buttons really clicked.

```
window shown            : yes  — icon Warning, "The existing project could not
                                 be moved aside", one OK button
excepthook fired        : []   — nothing escaped to the log-only path
files before / after    : 24 / 24
unrecoverable by hash   : 0
manifest                : untouched, current_run run3, runs [run1,run2,run3]
old/ archives           : none
```

Repeated with only `runs/` unwritable, so the archive fails **part way**:

```
window shown            : yes, reason names runs/ exactly
files before / after    : 24 / 24     (the partial move was fully rolled back)
unrecoverable by hash   : 0
```

**F2 works.** Two caveats: the folder it names is wrong (VB.4), and it fires for
errors that are not a replace and then makes a false claim (VB.5). Also, a
failed archive leaves an empty `old/<stamp>/` directory behind — litter, not
loss, and the next archive suffixes past it.

**The test that guards it does not test this.**
`test_a_replace_that_cannot_be_carried_out_is_shown_not_just_logged`
monkeypatches `_say_the_replace_failed` itself, so it proves the `except` branch
calls a function — not that a window appears — and it covers only the `.txt`
route.

---

## VF. Return-key safety, and whether `test_s47_window_shape` really catches a change

**Return is safe in every new window.** Driven, not reasoned:

| window | default button | Return sent → |
|---|---|---|
| M-IMPORT-REPLACE-CONFIRM, `.txt` | **Go back** | dialog closed, **nothing replaced**, `old/` empty, manifest still `run4 [run1..run4]` |
| same, `.ti3` / `.ti2` | **Go back** | — |
| the name prompt during a collision | `OK` is default **but hidden**; Replace it and Cancel are `autoDefault=False` | dialog **stays open**, collision line still showing, 24/24 files in place |
| M-PROJECT-REPLACE-FAILED | (OK only) | closes |
| “Copy project” (whole-project route) | **Continue** | dialog stays open, re-shows the error |

**§S4.7 in Create Chart is unchanged.** Captured live and compared with report
11's pre-work baseline, O1–O10:

```
text          : "There is already a project called “Canon”"     ✔ identical
windowTitle   : ""                                              ✔
icon          : Icon.NoIcon                                     ✔
defaultButton : Cancel                                          ✔
creation order: [Continue this project, Cancel, Replace it, Use a different name] ✔
left-to-right : [Continue this project, Replace it, Use a different name, Cancel] ✔
picker items  : [A new run (nothing already there is touched), Run 1, Run 2, Run 3] ✔
picker current: currentData ""                                  ✔
picker label  : "Make the new chart in:", above the button row  ✔
```

### The mutations — each one proven to land, run on an rsync'd copy in the scratchpad, never in the repo

Targeted set: `test_project_name_collision` `test_message_catalogue`
`test_txt_loader` `test_ti2_loader` `test_an_import_never_destroys_a_project`
`test_s47_window_shape` `test_project_name_is_never_invented` (+ `test_i18n`
where relevant). Baseline for the whole set including
`test_ti2_loader_model`, `test_no_project_is_ever_invented`,
`test_design_specs_are_binding` and `test_settings_can_be_sandboxed`:
**307 passed**.

| # | mutation | caught? |
|---|---|---|
| M1 | §S4.7 `setDefaultButton(cancel)` → `(replace)` | **yes** — `test_return_is_never_an_overwrite` |
| M2 | §S4.7 `spread_message_box_buttons(box, order=[…])` → `(box)` | **yes** — `test_cancel_sits_on_the_far_right…` |
| M6 | `_copy_txt` archive → `shutil.rmtree(dest)` | **yes** |
| M7 | `project_replaced_on_disk` never drops the cache | **yes** |
| M8 | same-second suffix → `mkdir(exist_ok=True)` | **yes** |
| M9 | the loader's failure window → a `log.warning` | **yes** (but see VE) |
| M10 | `_discard_run`'s “it holds work” guard → `if False` | **yes** |
| **M4a** | **`.txt` confirmation `setDefaultButton(_back)` → `(_yes)`** | **NO — 270 passed** |
| **M4b** | **`.ti2` confirmation, the same** | **NO — 270 passed** |
| **M5** | **drop `subject=tr("the measurement")` at the bare-`.ti3` call site** | **NO — 270 passed** |
| **M11** | **`_next_run_index`'s on-disk skip → `while False`** | **NO — 312 passed** (incl. `test_project_run`, `test_folder_layout_v2/e2e`, `test_deleting_never_half_destroys`, `test_per_run_description_fields`, `test_knut_beta147_batch`, `test_run_description_labels`) |

So `test_s47_window_shape.py` is a real guard — it catches exactly the two
mutations that motivated it. But **the property it exists to pin is unguarded on
the two windows this pass added**: making Return an immediate replace in both
loaders leaves everything green. And the one wording fix in item 2 can be
reverted, verbatim, with everything green.

M11 matters most: it is one of the five data-safety fixes in the list, and
nothing anywhere notices its removal.

Two more tests worth naming, both structurally unable to fail for the reason
they claim:

* `test_the_bar_is_told_when_a_replace_empties_the_project` calls
  `ctl.project_replaced_on_disk()` **itself**. No test drives a call site — which
  is why the dead one in `tab_check_refine` (VD) was not noticed.
* `test_a_replace_that_cannot_be_carried_out_is_shown_not_just_logged`
  monkeypatches the very function whose window is the subject (VE).

Both pass. Neither would fail if the wiring were removed from the tab.

---

## VG. Regression hunt in what was touched

An AST comparison of HEAD against the working tree, for all 14 changed `.py`
files, on **decorators, argument lists, return annotations and docstring
presence** for every function and class:

```
PROBLEMS: 6 — all four intentional, none of them damage
  core/file_manager.py   Project._next_run_index   doc: '' -> 'The next free run number…'
  ui/dialogs/name_prompt.py ask_for_project_name   args: + exists=None
  ui/ti2_loader.py       _ask_profile_name         args: + subject: str|None = None
  ui/ti2_loader.py/_txt  _is_self_collision        doc: '' -> 'True when the folder…'
  tests/…is_never_invented _fake                   args: + **kw
```

**No stolen decorator, no lost docstring, no changed signature.** In particular
the `subject` parameter's explanatory comment sits *between* the signature and
the string literal — the shape that in another language would have destroyed the
docstring. In Python comments are stripped by the tokenizer, so
`_ask_profile_name.__doc__` is intact; verified at runtime, not assumed.

The three programmatically `try:`-wrapped bodies were compared at AST level —
old function body vs the new `Try.body`, unparsed:

```
resolve_txt : body identical? True   handlers ['OSError']  orelse 0  finalbody 0
resolve_ti2 : body identical? True   handlers ['OSError']  orelse 0  finalbody 0
resolve_ti3 : body identical? True   handlers ['OSError']  orelse 0  finalbody 0
```

The indentation change is semantically inert. **What is not inert is the
SCOPE** of those handlers — VB.5.

`verify_chart_snapshot.restore_slot`: `_rollback_ok` is initialised before the
`try` and re-initialised inside the `except`; both are correct, and the `finally`
reads it on every path. A non-`OSError` in the main body still deletes the stash,
exactly as before. `shutil.Error` subclasses `OSError`, so a failing
`shutil.move` inside the rollback is caught.

**i18n:** all 12 languages carry `Replace it`, `Go back`, the new collision
line, `the measurement`, `the chart` and all three new message titles and
bodies; none carries a stale `Overwrite existing folder`,
`Overwrite existing folder?`, the old collision line or the old
“permanently delete” body. `test_i18n.py` green. (`data/i18n/staging/*.partial.json`
for sv/no/it/nl still hold the removed English keys — dead files, but they would
carry the dead keys forward if one of those languages is ever completed from
staging.)

One translation-quality note, not a bug: `render()` does
`tr(body).format(**kw)`, so `{subject}` is substituted **after** translation.
In German, *“…und die Messung, die Sie importieren…”* vs *“…und das Chart…”*
requires different articles and case in the surrounding sentence, and the
template cannot vary. Worth a translator's eye before approval.

---

## VH. The destructive-call inventory, re-run against the current tree

`shutil.rmtree` / `unlink` / `os.remove` across `core/`, `ui/`, `workflow/`,
`main.py`. **The three loader `rmtree`s are gone.** Nothing in the diff adds a
new destructive call: `_archive_project_contents` only gained a `mkdir` loop,
and `_discard_run` only gained an early `return`.

One site is still able to destroy user work, and it is **not** one report 09
listed as unsafe:

**`Run.clear_reads()` — `core/file_manager.py:831`, called from
`ui/tabs/tab_measure.py:10962`.** Report 09 recorded it as *“safe only because
`reset_chart_artefacts` archives `reads/` at `:1317` under the identical
`not keep_results` condition. The method itself has no guard; a future caller
destroys hand-taken readings.”* **That future caller already exists.** The
“Measure again to average” branch starts a fresh averaging set with

```python
run = Run.for_dir(ti3.parent)
run.clear_reads()          # "discard any stale reads/"
```

and `_averaging_active` is a per-session flag — `False` after a restart. So:
average three reads today, quit, come back tomorrow, measure, press *Measure
again to average* → the three `.ti3` files from yesterday are gone. Measured
against the real objects:

```
BEFORE               : ['read1.ti3', 'read2.ti3', 'read3.ti3']
AFTER reads_dir      : does not exist
old/ archive         : []          ← nothing archived
Trash                : nothing (core.trash is not involved)
```

Every other `rmtree` on user data is one report 09 already reviewed and cleared
(`exports/`, `cache/`, the chart stash, the snapshot slot, `run_delete.py`'s
`move_to_trash` path). No pruning of `old/` exists anywhere.

---

## V1. Numbered list of what is still wrong

**Windows that misdescribe what they do**

1. **The failure window fires for any `OSError` in the whole import**, not only
   a failed archive, because both loaders wrap the entire `resolve_*` body. It
   then asserts *“The existing project could not be moved aside”* and *“Nothing
   has been changed”*. Driven twice: with no project and no replace involved, a
   half-built project (`project.json`, `Where are my files.txt`,
   `runs/run1/meta.json`) is left on disk; and after a **successful** archive
   followed by a failed copy, the project is empty, everything is in `old/`, and
   the person is told nothing happened. `ui/txt_loader.py:69-76`,
   `ui/ti2_loader.py:458-496` and `:968-984`.
2. **It names the working folder, not the project.** Both loaders pass
   `_resolve_working_dir(settings)`; `tab_chart._replace_failed_message` passes
   the project root. `ui/txt_loader.py:75`, `ui/ti2_loader.py:495/983`.
3. **The bare-`.ti3` name prompt is titled “Copy Chart Files”**, and its body
   says “The following files … as a new profile set”. `subject` reaches the
   confirmation only. `ui/ti2_loader.py:1188`.
4. **W4 is unfixed in both loaders**: *“That name points to the measurement's /
   chart's own folder”* for a file that may be at any depth inside the project
   — and `ui/txt_loader.py:309` / `ui/ti2_loader.py:1308` still say
   **“overwrite”**. Report 11 §C6 wrote the replacement text.
5. **A third replace dialog keeps the old vocabulary and has no second look.**
   `_ask_project_name` (`ui/ti2_loader.py:876`): the button says **“Replace
   existing”**, the red line tells the user to click *“Replace it”* — a button
   that is not on the window — and one click archives a whole project with no
   confirmation. Driven; the archive is genuine and nothing is lost.

**Messages that exist but are never shown**

6. **M-IMPORT-REPLACED-KEPT has no call site.** Report 10's finding 9 — the
   person is still never told where their project went — is open, and now looks
   closed. Twelve translations of a message nobody sees.
7. **M-IMPORT-PROJECT-EXISTS has no call site**, and the specification now
   describes it as a four-button window with a stated default and button order
   that the app never opens. Under CLAUDE.md's rule, that is unconfirmed
   behaviour written into a specification.
8. **The loaders' new red line is a literal**, not a catalogue render —
   `ui/txt_loader.py:271`, `ui/ti2_loader.py:1270` — in the same two files whose
   own comments explain that literals there are checked by nothing.
9. **§S4.8 was never written into the specification** (report 11 §C7, plan step
   5), so three §M entries describe messages for a sequence that has no rule.

**Wiring**

10. **`tab_check_refine.py:1216` is dead code.** `TabCheckRefine` has no
    `_target_ctl` and never had one; the `getattr` default makes the F4 call a
    silent no-op. Three of the four claimed call sites work.
11. **No F4 on the `.ti2` loader's call sites** — `tab_print._on_load_ti2`,
    `tab_print.set_ti2_path`, `tab_measure:4297`. Benign today only because
    routing keeps `_handle_outside` unreachable while a project is open.

**Guards**

12. **Making Return press “Replace it” in BOTH new confirmations leaves 270
    tests green** (M4a, M4b). The exact property `test_s47_window_shape.py` was
    written to pin is unguarded on the windows this pass added.
13. **Dropping `subject=tr("the measurement")` leaves 270 tests green** (M5).
    The measurement-called-a-chart fault can return verbatim.
14. **Removing `_next_run_index`'s on-disk skip leaves 312 tests green** (M11),
    across every file-manager and run-layout test file I could find. One of the
    five data-safety fixes has no guard at all.
15. **`test_the_bar_is_told_when_a_replace_empties_the_project` calls
    `project_replaced_on_disk()` itself**; no test drives a call site. That is
    why #10 was not noticed.
16. **`test_a_replace_that_cannot_be_carried_out_is_shown_not_just_logged`
    monkeypatches `_say_the_replace_failed`**, so it cannot prove a window
    appears, and it covers one of the three routes.

**Still able to destroy user work (inventory, VH)**

17. **`Run.clear_reads()` from `ui/tabs/tab_measure.py:10962`** destroys
    `reads/readN.ti3` — hand-taken averaging measurements — with no archive and
    nothing in the Trash, whenever “Measure again to average” starts a fresh set
    over reads left by an earlier session. Report 09 predicted this caller and
    recorded the site as safe; it is not.

**Minor**

18. A failed archive leaves an empty `old/<stamp>/` behind.
19. `data/i18n/staging/{sv,no,it,nl}.partial.json` still carry the four removed
    English keys.
20. `{subject}` is substituted after translation, so the German article and case
    around it cannot agree. Worth a translator's eye before approval.

---

**Nothing in the repository was changed by this verification** except this
report. Settings sandboxed to
`/…/scratchpad/probe/driver.ini` for every driver, asserted before any widget
was built. `defaults read com.chromiq.ChromIQ custom_output_path` — *does not
exist*, before and after. `~/ChromIQ` top level: 23 entries, identical.
`~/ChromIQ/CR30-Test` and `~/Desktop/i1Profiler`: no file modified.
Mutation testing was done on an `rsync`'d copy in the scratchpad.

STATUS: complete

# Round 4 — the collision notice in the name dialog, and a re-check of what shipped

STATUS: complete

Adversarial review, 2026-08-31, against `master` at `bd463b94`
(tagged `v4.1.5-beta.5`).

Proof folder: `~/Desktop/knut-round4/` (INDEX.md inside).

## Method
- Read the code first; trusted nothing in the brief.
- Drove the REAL app on screen — real `MainWindow`, real event loop, real
  `QDialog.exec()` — with `~/ChromIQ` redirected into a throwaway sandbox and a
  `Path.mkdir` tripwire that raises on any write under the real folder.
- Targeted `pytest tests/<file>.py` only. No `--runslow`.
- Mutation tests were run in a **separate clean `git clone`**, so no source file
  in the working tree was edited at any point. `git status` is unchanged.

## Safety — and one failure to report
- `~/Library/Preferences/com.chromiq.ChromIQ.plist` → `backup/…plist.orig`
  (sha1 `d45d76f1ecd3f95d464b82a7b03c378a61361c4d`).
- `~/Library/Preferences/ChromIQ/presets/` (7 files) → `backup/presets.orig/`.
  **No drift** (`diff -rq`, identical).
- `~/ChromIQ` fingerprinted before and after (1,396 entries). **No drift** —
  `diff` of the two listings is empty. `CR30-Test` never touched.
- **THE PLIST DID DRIFT, AND MY SANDBOX MEASURE IS THE REASON.** The rounds-2/3
  measure `QSettings.setDefaultFormat(QSettings.Format.IniFormat)` **does not
  redirect this app**. Measured after the fact:

  ```
  QSettings.defaultFormat()          -> Format.IniFormat
  QSettings("ChromIQ","ChromIQ").format()   -> Format.NativeFormat
  QSettings("ChromIQ","ChromIQ").fileName() -> ~/Library/Preferences/com.chromiq.ChromIQ.plist
  ```

  Four keys were written by my drivers and have been **restored** (file sha1
  back to `d45d76f1…`, `cfprefsd` restarted, values re-read from `defaults`):

  | key | was | driver left it |
  |---|---|---|
  | `session_target_name` | `''` | `ZZ-round4-plain` |
  | `use_chromiq_layout_engine` | `1` | `0` |
  | `window_fullscreen` | `1` | `0` |
  | `window_geometry` | (owner's) | (driver's 1500×1000) |

  Anyone re-running this work must patch `core.settings.QSettings` /
  `core.i18n`'s `QSettings` **by name**, the way `tests/conftest.py` does. The
  default-format trick reports success and does nothing.

---

# PART 1 — should the name dialog show the collision notice?

## 1.1 What actually exists (verified, not taken on trust)

`ui/tabs/tab_chart.py:9189 _refresh_project_exists_line` is wired to
`textChanged` on both name fields (`:3402` guided, `:3864` manual) and to
`ui/main_window.py:1166`. Per keystroke it does, per field:

```python
root  = self._file_mgr.resolved_root_for_name(typed)      # core/file_manager.py:2378
shown = (root / "project.json").is_file()
if shown and self._file_mgr.is_named():
    shown = not same_dir(self._file_mgr.working_dir(), root)   # the open project is not news
```

and on a match shows `tab_chart.py:9233`:

> You already have a project with this name. Your new chart goes into it.

The dialog (`ui/dialogs/name_prompt.py:56 validate`) checks **shape only**:
empty, `FORBIDDEN = /\:*?"<>|`, >120 UTF-8 bytes, no alphanumerics. Its module
docstring (`:9-15`) states the D5 ruling in as many words.

## 1.2 Is it "information, not a decision"? — the strongest case AGAINST

The brief's framing is defensible but incomplete, and the strongest objection is
not the one report 03 wrote down. D5 said §S4.7 must own the *decision*. The
real problem with the proposal is narrower and harder:

**The sentence is not the same fact in the two places, because the dialog sits
before a fork the label sits after.**

Measured on screen (`logs/b-prebuilt.log`, `shots/B1a-box-modal1.png`):
§S4.7 offers **four** outcomes and a run picker —

```
"There is already a project called “ZZ-round4-PB”"
[Continue this project] [Replace it] [Use a different name] [Cancel]
run picker: ["A new run (nothing already there is touched)", "Run 1"]
```

So after the dialog, "your new chart goes into it" is one of **six** end states
(continue-into-run-1, continue-into-a-new-run, replace, rename, cancel, and the
silent adopt below). Putting that sentence in the dialog does not restate a
fact; it **predicts an outcome the user has not chosen yet**, and it predicts
the one the app is at pains not to assume — `_gate_typed_project_name`'s own
comment (`tab_chart.py:8814-8818`) says a new run is deliberately the default
*because* it is the answer that cannot cost anything.

That is the line, and it is not "information vs decision". It is:

> **A notice before a fork may describe what is THERE. It may not describe what
> will HAPPEN, because the person has not chosen yet.**

By that line the notice belongs in the dialog — with different words.

## 1.3 …and the case FOR is stronger than report 03 allowed

Three measured facts that report 03's D5 did not have:

1. **§S4.7 stays silent on an existing project that holds nothing.**
   `_gate_typed_project_name` returns early at `tab_chart.py:8821-8822` when
   `not peek.holds_anything`. Measured (`logs/a-label.log`):

   ```
   ZZ-round4-empty : line visible=True | peek.exists=True holds_anything=False -> NO window
   ```

   So for an empty project the label is the **only** signal there will ever be,
   and it is the one case where "your new chart goes into it" is exactly true.
   Withholding it from the dialog means a person who names their project in the
   dialog is told nothing at all, on a route where the box would have told them.

2. **The dialog and the box are the same act.** Verified end to end
   (`logs/d-equiv.log`): same name, same preset, same project, typed into the
   BOX versus into the DIALOG →
   `§S4.7 window identical: True`, `files created identical: True`,
   `whole tree identical: True`. There is no behavioural difference left to
   justify a difference in what the person is told.

3. **Cost is not an argument either way.** Measured
   (`logs/p2-cost.log`): the check is a single `stat`, **flat** in the number of
   projects — 6.1 µs at 0, 50, 200 and 1,000 projects; ~12 µs per keystroke for
   both fields. `peek_project` — the full, still non-mutating read — is 34 µs.
   `Project.load` (the migrating path) is never reached: `_refresh_project_exists_line`
   calls neither it nor `peek_project`, and `working_dir()` — whose
   `get_target_name()` invents a name — is reached only behind `is_named()`
   (`tab_chart.py:9215-9221`). 5,000 checks against a project left its file list
   byte-identical.

   The one cost caveat: `root_dir()` re-reads `custom_output_path` from settings
   on every call (`core/file_manager.py:2354`), so with the working folder on a
   network volume each keystroke is a remote `stat`. Not measured here; worth
   knowing before the check is duplicated.

## 1.4 Does the check find every collision? Three answers, all measured.

| worry | verdict |
|---|---|
| APFS case folding (`canon` vs `Canon`) | **NOT a bug.** The filesystem is case-insensitive, so `is_file()` matches. Driven: typing `zz-ROUND4-a` against a project `ZZ-round4-A` **shows** the line (`logs/a-label.log`). `same_dir` uses `samefile`, so the open project is still recognised in any case. |
| NFC vs NFD | **A real defect — but not in the check.** `FileManager._sanitise` (`core/file_manager.py:2187`) uses `_ILLEGAL = [^\w\-.]+`, and a combining diacritic is not `\w`. Measured: NFC `Café` → folder `Café`; the **same name pasted as NFD** → folder `Cafe`. The label is *honest* — it correctly reports "no such project", because the build really would make a different folder. Report 04's O2, unfixed. |
| a folder that is not a project | **A gap.** `ZZ-round4-plain`, holding the user's own `my scans.tif`, gives **no line and no window**, and the build adopts the folder — writing `project.json`, `Where are my files.txt` and `runs/run1/` into it (`logs/e-gaps.log`). Nothing was destroyed, but the line answers *"is there a ChromIQ project here"*, not *"is that name free"*. |

Copying the check into the dialog would therefore copy **no** case bug, and
would inherit the NFD name-mangling that is upstream of it.

## 1.5 The wording — and the main window's sentence is wrong too

`data/i18n/de.json:4055` shows the label is already shipped in twelve
languages. It has been through **no** catalogue: it is prose written straight
into the tab, and `_refresh_project_exists_line` is not in
`tests/test_message_catalogue.py:309 WINDOW_SOURCES` — while its sibling
`_project_exists_message` is (`:323`). So the tab's collision *window* is
governed and the tab's collision *line* is not. Adding a third un-catalogued
copy makes that worse, not better.

**The main window's sentence is imprecise, and it is imprecise in exactly the
case where something is at stake.** Measured:

| what the name points at | the line says | what actually happens next |
|---|---|---|
| a project holding nothing | "Your new chart goes into it." | true — silent adopt, no window |
| a project holding a chart / measurement / profile | "Your new chart goes into it." | a four-button window; "into it" is one of four, and even "Continue this project" defaults to **a new run**, not "into it" |

The promise is most confident where the risk is highest. That inversion is the
defect worth fixing, whether or not the dialog ever gets a notice.

### Proposed wording — TRUE in both places, identical text

> **You already have a project with this name. ChromIQ will ask what to do with it.**

- True for a project that holds work: the very next window asks.
- Not true today for an **empty** project, where nothing asks. Two ways to make
  it true, and the choice is the owner's (OQ-2): let §S4.7 fire on an empty
  project too, or use a two-form label:
  - holds nothing → *"You already have a project with this name. Your new chart goes into it."* (today's sentence, correct here)
  - holds something → *"You already have a project with this name. ChromIQ will ask what to do with it."*

  The two-form version needs `peek_project` rather than `is_file()`, which the
  measurement above shows is affordable (34 µs), and `peek_project` is
  explicitly the non-mutating read (`core/file_manager.py:2700`).

House rules checked: no Markdown, no "(s)", no count-bearing noun, no dash, no
project name interpolated (the label is a fixed 524 px and `default_target_name`
makes 81-character names — the reason `:9224-9231` gives for leaving the name
out is sound and survives this change).

## 1.6 Where it should sit, and whether it may block Continue

- **Below the field, above the error line** (`name_prompt.py:138-143`), styled as
  information, not as the red `#e05555` error at `:142`. Two coloured lines in
  one small dialog, one red and one not, is the only layout that keeps "this is
  a fact" visually distinct from "this is refused".
- **It must NOT block Continue.** Agreed with the brief, and the code agrees:
  every §S4.7 outcome including "Replace it" is legitimate, so a disabled
  Continue would make the dialog refuse a thing §S4.7 exists to offer.
- **The open project's own name must show nothing.** The existing check already
  gets this right, measured both in the same case and in a different case
  (`logs/a-label.log`: with `ZZ-round4-A` open, typing `ZZ-round4-A` and
  `zz-round4-a` both leave the line hidden). A copy in the dialog **must reuse
  `_refresh_project_exists_line`'s exact test** — `same_dir` behind `is_named()`
  — not re-derive it. The dialog is reachable with a project open: the R4 route
  (`tab_chart.py:12235`) opens it whenever the typed name is unusable, whatever
  the project state.
- **`name_prompt.py` must not grow a disk read.** Its docstring promises it
  "never touches the disk" (`:12`) and `validate()` is a pure function three
  tests call directly (`test_project_name_is_never_invented.py`). The notice
  should arrive as a **callback passed in** by `_ask_for_a_project_name`, so the
  one implementation of the rule stays in the tab.

## 1.7 Guided vs Manual

Identical, and measured. `_active_name_field` (`tab_chart.py:8682`) returns the
manual field when the Manual button is checked, the guided one otherwise;
`_ask_for_a_project_name` (`:12174`) writes through it, and `_on_generate`
(`:12231`) reads the matching one. Driven, five unusable names × two modes
(`logs/c-routes.log`): the same dialog, the same prefill, the same Cancel
behaviour, nothing on disk, in both modes.

`_refresh_project_exists_line` refreshes **both** labels every time, each keyed
on its own field's text, so the hidden panel's label can never contradict the
visible one.

**One inconsistency the proposal would inherit:** the prebuilt route reads
`self._manual_target_name_edit` directly (`:11087`, `:11212`) while the dialog
writes through `_active_name_field()`. Report 04's O6, unchanged.

---

# PART 2 — re-check of what shipped

## 2.1 A clean checkout runs. VERIFIED.

`git clone --depth 1` of the repo at `bd463b94` into a fresh directory:
`ui/dialogs/name_prompt.py` and `tests/test_row_numbers_follow_the_instrument.py`
are both present, and

```
import ui.tabs.tab_chart   -> OK
import ui.dialogs.name_prompt -> OK
import main                -> OK
```

Report 05's N7 (the `ModuleNotFoundError` blocker) is closed.

## 2.2 The 23 `zz_*` scripts are gone — one file is not.

`ls scripts/ | grep zz` is empty; nothing in the repo references any `zz_*`
name except the two committed reports that cite them as evidence
(`04-…md`, `05-…md` — nine dangling citations, harmless but now unresolvable).

**`scripts/drive_55_transport_note.py` is still untracked** (`git status`), and
it is named in report 05's N8 as one of the scripts to remove. It is worse than
the others: **`docs/cr30_reports/55_transport_verify.md:186, 729, 751` — a
committed document — cites it as the driver that produced its evidence.** So a
clean checkout has a committed report pointing at a file that is not in the
repo. Either commit the script or amend those three citations. This is N7's
mirror image.

## 2.3 R4's other half. **FIXED ON TWO ROUTES OF THREE — and NOT on the route
## report 05 measured the fault on.**

`from ui.dialogs.name_prompt import validate as _validate_name` appears at
exactly two places in the whole codebase: `tab_chart.py:11429`
(`_generate_from_ti1`) and `:12230` (`_on_generate`). The prebuilt-preset route
has no such branch — `_apply_prebuilt_preset:11087` and
`_create_prebuilt_target:11212` still test only `not …text().strip()`.

**Where it works** (driven, five bad names × the `.ti1` route × Generate Chart ×
Guided and Manual = 25 cases, `logs/c-routes.log`): the dialog opens
**pre-filled with the bad name**, Cancel changes nothing, `is_named` stays
False, `roots created = []`. Shortening the name inside the window then builds
correctly (`ZZ-round4-recovered`). Three consecutive Generates with three
Cancels open exactly three windows — **no loop**.

**Where it does not** — see BUG 1.

## 2.4 The new prebuilt-guard test is real. VERIFIED by mutation.

In the clean clone, the guard block at `tab_chart.py:11087-11092` was deleted
(uniqueness asserted, 974,700 → 974,381 bytes, the deletion confirmed by
re-reading the file):

```
FAILED tests/test_project_name_is_never_invented.py::test_a_prebuilt_preset_asks_before_it_gates
1 failed, 13 passed
```

Report 05's N4 is closed. Two further mutations, same method:

| guard deleted | caught? |
|---|---|
| `_apply_prebuilt_preset`'s ask (`:11087`) | **yes** — 1 failed |
| `_ask_for_a_project_name`'s `_name_typed_by_user = True` (`:12188`) | **yes** — 1 failed |
| `_on_generate`'s `_validate_name` branch (`:12235`) | **NO — 117 passed** |
| `_generate_from_ti1`'s `_validate_name` branch (`:11434`) | **NO — 117 passed** |

See BUG 4.

## 2.5 The headline fix, re-verified end to end. HOLDS.

Same name, same preset (TC3.00 prebuilt), same project holding a chart, a
measurement and a profile. `logs/d-equiv.log`:

```
BOX    : [§S4.7 four-button window]                          -> Continue this project
DIALOG : ["Give this project a name"] + [the SAME §S4.7 window] -> Continue this project

§S4.7 window identical?   True
files created identical?  True     (runs/run2/ + 11 files, project.json changed)
whole tree identical?     True
```

Nothing was lost on either path, and the two paths are indistinguishable on
disk. Cancel on either path changes nothing (`logs/b-prebuilt.log`).

---

# BUGS AND REGRESSIONS

## BUG 1 — CRITICAL. On the prebuilt-preset route an unusable name is still accepted: `///` silently builds a project called **“session”**, and 250 characters still crash with Errno 63 leaving a half-built project.

`ui/tabs/tab_chart.py:11087-11089` and `:11212-11214` guard on
`not self._manual_target_name_edit.text().strip()` alone. The `_validate_name`
branch that fixes this on the other two routes was never added here — and this
is the route report 05's N1 measured the fault on.

**Reproduction** (driven, `logs/b-prebuilt.log`, `logs/d-equiv.log`,
`shots/D4-slashes-typed.png`, `shots/D4-slashes-after.png`):

1. Create Chart → Manual, empty project state.
2. Paste `///` into "Printer profile project name".
3. Pick **★ ColorMunki · A4-300p-1page TC3.00 by Pharmacist**.

```
MODALS SEEN: 0
target name : 'session'
new on disk : session/, session/project.json, session/Where are my files.txt,
              session/runs/run1/{session.ti1, session.ti2, session.channels.json,
              session_01.tif, meta.json}, session/runs/run1/exports/{…}
```

A complete project, chart and all, under a name **nobody typed** — and
`name_prompt.py:67-72` says in its own comment that this is precisely what
`validate()` exists to prevent. `a/b` behaves the same way and builds `a_b`.

With 250 characters, the same route:

```
[ERROR] ui.tabs.tab_chart: Prebuilt copy failed: [Errno 63] File name too long
MODAL: "Could not create target" [Close]
LEFT BEHIND: project.json, "Where are my files.txt", runs/run1/, the .ti1,
             the .ti2, meta.json
is_named = True   (the app is now pointed at the broken folder)
```

That is report 04's R4 and report 05's N1, word for word, unchanged. #175 —
"a refused action leaves nothing behind" — is still broken.

**The `///` case is the worse half**: it is silent, it succeeds, and the person
has no way to know their project is called "session" until they look in Finder.

## BUG 2 — After "Use a different name", the collision line stays on screen over an EMPTY name box.

`ui/tabs/tab_chart.py:7976-7981` restores the name fields inside
`w.blockSignals(True) / setText(text) / blockSignals(False)`. Blocking is
deliberate — it stops `textEdited` re-arming `_name_typed_by_user` — but it also
suppresses `textChanged`, which is the **only** thing wired to
`_refresh_project_exists_line` (`:3402`, `:3864`). Step 11 of the restore
(`:8009-8012`) refreshes the locks, the row visibility, the marker support and
the command preview, and does not refresh this label.

**Reproduction** (driven, `shots/D3-after-different-name.png` — the screenshot
shows the empty box with the pink line under it):

1. A project `ZZ-round4-EQ` exists and holds work.
2. Create Chart → Manual, name box empty, pick the TC3.00 prebuilt preset.
3. In "Give this project a name" type `ZZ-round4-EQ`, click **Continue**.
4. In the §S4.7 window click **Use a different name**.

```
name box after : ''
preset combo   : 0 (none)
collision line : True     <-- "You already have a project with this name.
                              Your new chart goes into it."
```

The line describes a name that is not in the box, at the exact moment the person
is being asked to type a different one. Report 05's N2 said this path gives an
empty box; it also gives a stale warning, which N2 did not catch.

## BUG 3 — `validate()` accepts names the filesystem will refuse on Windows, and names that silently become a different folder.

`ui/dialogs/name_prompt.py:56`. Measured (`logs/p3-validate.log`):

| typed | validate() | folder actually made |
|---|---|---|
| `CON`, `NUL`, `AUX`, `LPT1`, `COM1` | ACCEPTED | `CON`, … — **reserved device names; `mkdir` fails on Windows**, the platform ChromIQ ships for |
| `🎨🎨1` | ACCEPTED | `1` |
| NFD `Café` | ACCEPTED | `Cafe` |
| `.hidden` | ACCEPTED | `hidden` |
| `Canon.` | ACCEPTED | `Canon` |
| `Canon<TAB>Pro` | ACCEPTED | `Canon_Pro` |

The reserved-name row is the same class of fault as the Errno 63 bug that this
work fixed: the check passes, `mkdir` fails, and the half-built folder is left
behind. The others are silent renames — the dialog never shows the person the
folder name it is going to make.

## BUG 4 — R4's other half has no test at all: deleting either half of the fix leaves 117 targeted tests green.

Mutation-proved in the clean clone, both deletions asserted unique and confirmed
in the file afterwards (974,700 → 974,643 bytes each):

```
_on_generate:12235       branch removed -> 117 passed
_generate_from_ti1:11434 branch removed -> 117 passed
```

(`tests/test_project_name_is_never_invented.py`, `test_project_name_collision.py`,
`test_knut_newbatch.py`, `test_backing_out_of_a_preset_changes_nothing.py`.)

This is report 05's N4 exactly, in a new place, and it shipped in the same
commit that added a test for the other guard. There is a ready-made test to copy
— `test_the_name_dialog_refuses_what_a_folder_cannot_hold` already asserts
`validate("a/b")` and `validate("///")` are refusals; nothing asserts the tab
*calls* it.

## BUG 5 (pre-existing, unchanged) — a pasted NFD name makes a different folder from the same name typed.

`core/file_manager.py:2187 _sanitise`, `_ILLEGAL = [^\w\-.]+`. NFC `Hahnemühle`
→ `Hahnemühle`; the same name pasted from Finder (NFD) → `Hahnemu_hle`. No
warning, and no collision line, because they really are two folders. Report 04's
O2 and report 03's D8 item 9, still open.

---

# GAPS, OVERSIGHTS AND UI INCONSISTENCIES

**G1 — The collision line answers the wrong question.** It asks "is there a
ChromIQ project at that path", not "is that name free". A folder holding the
user's own files gets no line, no window, and is adopted by the build
(`logs/e-gaps.log`). Nothing is destroyed, but the person is not told the folder
was already there.

**G2 — The name box has no length cap.** `maxLength = 32767` (Qt's default);
nothing in `ui/tabs/tab_chart.py` sets one. Report 05 recommended a cap on the
field. Two routes now catch it downstream; BUG 1's route does not.

**G3 — The dialog never shows the folder it will make.** A person typing
`Canon PRO-300 / Baryta` is refused; a person typing `Canon PRO-300, Baryta`
gets `Canon-PRO-300_-Baryta` with no comment. If any information belongs in this
dialog ahead of a collision notice, it is this one.

**G4 — Two collision UIs already disagree about the same word.** `txt_loader`'s
"Overwrite existing folder" **deletes**; §S4.7's "Replace it" **archives to
`old/<date>/`**. Report 03 open question 7, report 04 R5. Still open, and it is
the strongest existing argument for D5's "one owner" rule.

**G5 — `_refresh_project_exists_line` is not in `WINDOW_SOURCES`
(`tests/test_message_catalogue.py:309`) while `_project_exists_message` is
(`:323`).** The window is governed; the line beside it is not. Both are about
the same fact. The dialog's own text ("Give this project a name" and its body)
is likewise ungoverned — report 05's N6, unchanged, and it is now translated
into twelve languages (`data/i18n/de.json:1409, 3809`).

**G6 — the prebuilt route reads `_manual_target_name_edit` while the dialog
writes `_active_name_field()`** (`:11087`/`:11212` vs `:12174`). Benign today
because `_activate_builtin_preset` switches to Manual first. Report 04's O6.

**G7 — nine dangling citations.** Reports 04 and 05 are committed and cite
`scripts/zz_*.py` files that were correctly deleted. Not worth a commit on their
own, but worth knowing before somebody goes looking.

**G8 — `QApplication.processEvents()` never returns in this app.** Method note,
not a user bug: something in the main window re-arms a zero-interval timer, so
"process everything pending" has no end. Any future on-screen driver must use a
nested `QEventLoop` with a `singleShot` quit. It cost two runs to find.

---

# WORDING

**W1 — "Your new chart goes into it." is imprecise wherever it matters.**
See §1.5. It is exactly true for an empty project (where nothing else is said)
and states one of four outcomes for a project that holds work (where a window
follows). Suggested replacement in §1.5; the choice between one sentence and two
is OQ-2.

**W2 — the §S4.7 body says the same thing.**
`workflow/measurement_messages.py:1154`: *"That name is already taken, so
building now would carry on inside that project rather than start a new one."*
That describes the default of the button the window does **not** default to
(`box.setDefaultButton(cancel)`, `tab_chart.py:8849`) and does not mention that
"Continue this project" itself defaults to a **new run**, which the bullet three
paragraphs later then explains. The window is marked `approved=False` — still
§M-PROPOSED — so this is fixable without breaking a ruling.

**W3 — the dialog's own text is good beginner English and untouched by this
report.** No "(s)", no Markdown, no jargon, names what the name is used for,
gives a concrete example, says the choice is reversible. It has still never been
through §M (G5).

**W4 — "Could not create target"** (the Errno 63 window, BUG 1) uses "target",
which appears nowhere else in the Create Chart tab — the field says "Printer
profile project name" and every other window says "project".

**W5 — the empty-box rule, report 04's O1, is unchanged.** `name_prompt.py:155`
suppresses the message whenever `not edit.text().strip()`, so three spaces greys
Continue and shows nothing. Measured this round: `validate("")` and `validate("   ")` both return
*"Type a name to continue."*, so **Continue is disabled and nothing is shown** —
three spaces are a silent dead end, indistinguishable on screen from a box that
has not been typed in.

---

# OPEN QUESTIONS FOR THE OWNER

1. **BUG 1 is the tag-blocker.** Should the `_validate_name` branch be copied
   into `_apply_prebuilt_preset` (`:11087`), or — better, and one place instead
   of four — should the check move into `_ask_for_a_project_name` itself, with
   every route calling it unconditionally and it deciding whether a window is
   needed? The second cannot be forgotten by a fifth caller.
2. **Should §S4.7 fire on an existing project that holds nothing?** Today it
   does not (`tab_chart.py:8821`) and the label is the only signal. The answer
   decides whether the label needs one sentence or two (§1.5), and it is a
   change to specified behaviour, so it is yours and not ours.
3. **Should the dialog show the collision notice at all** — my verdict below is
   "yes, with different words", but D5 was your ruling and the wording change is
   the substance of it.
4. **Should the notice's rule live in the tab and be passed to the dialog as a
   callback**, keeping `name_prompt.validate()` a pure function, or should the
   dialog be given the `FileManager`? The first keeps one implementation of the
   rule and keeps three unit tests working.
5. **Should the dialog show the FOLDER NAME it will create** (G3)? It is the
   information a beginner is actually missing, and it would make BUG 5 (NFD) and
   the `🎨🎨1 → 1` case visible instead of silent.
6. **Windows reserved names** (BUG 3) — refuse `CON`/`NUL`/`AUX`/`COM1`/`LPT1`
   on every platform for portability, or only on Windows? Refusing everywhere
   keeps one rule and one message.
7. **`scripts/drive_55_transport_note.py`** — commit it (three committed CR30
   reports cite it) or delete it and amend those citations?
8. **Should "Use a different name" re-open the name dialog pre-filled** instead
   of emptying the box (BUG 2 / report 05's N2)? That is the one change that
   would make the dialog the single place the name is ever given.

---

# VERDICT ON THE DESIGN

## YES — the dialog should show it. NOT in the main window's words, and the main window's words should change too.

The D5 ruling survives: §S4.7 keeps the decision, keeps the four buttons, keeps
the run picker, and keeps the vocabulary. Nothing about a notice in the dialog
takes any of that away, and the measured equivalence of the two routes (§1.2,
fact 2) leaves no principled reason to tell a person less because they answered
in one window rather than the other.

But the brief's own framing — "it is the same fact the main box already
displays" — is what is wrong. It is not the same fact, because the label sits
*after* the fork and the dialog sits *before* it. "Your new chart goes into it"
is a prediction, and in the dialog it predicts an outcome the person has not
been offered yet. In the main window it is a prediction too, and it is wrong
there for the same reason — which is the finding I did not expect to make.

**The words, in both places:**

> You already have a project with this name. ChromIQ will ask what to do with it.

**with one condition attached**: today that sentence is false for an existing
project that holds nothing, because §S4.7 stays silent there (`:8821`). Either
let §S4.7 fire on an empty project (OQ-2), or use two forms — today's sentence
where nothing is at stake, the new one where something is. Do not ship the new
sentence alone until one of those is decided.

**Placement:** under the field, above the red error line, in the ordinary text
colour — never in the error colour, and never disabling **Continue**. It is
information; §S4.7 owns the decision, exactly as D5 says.

**Never shown for the open project's own name** — reuse
`_refresh_project_exists_line`'s `same_dir`-behind-`is_named()` test verbatim
rather than writing a second one, and pass the answer into `name_prompt.py` as a
callback so that module keeps its promise never to touch the disk.

**And do not ship it before BUG 1.** A notice that tells a person their name is
taken, on a route that will then build them a project called "session" without
asking, is not an improvement.

STATUS: complete

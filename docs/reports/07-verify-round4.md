# Round 5 — verifying the fixes made after report 06

STATUS: complete

Adversarial verification, 2026-08-31, of the UNCOMMITTED working tree on
`master` at `bd463b94` (tagged `v4.1.5-beta.5`).

Proof folder: `~/Desktop/knut-round5/` (INDEX.md inside).

## Method
- Read the diff first, then every call site it touches; trusted nothing in the
  brief.
- Drove the REAL `MainWindow` with a real event loop and real `QDialog.exec()`.
- Targeted `pytest tests/<file>` only. Never `--runslow`. No source file in the
  working tree was edited at any point.

## Safety — the redirect that actually works
Report 06 found `QSettings.setDefaultFormat(IniFormat)` does **not** redirect
this app, and the owner's plist drifted by four keys. This round patches
`core.settings.QSettings` **by name** (the way `tests/conftest.py:672` does) and
**proves the redirect took before doing anything else**:

```
AppSettings()._qs.fileName()      -> <sandbox>/ChromIQ.ini      (asserted)
get("custom_output_path")         -> <sandbox>/projects         (asserted)
```

A `Path.mkdir` + `open(..., 'w')` tripwire refuses any write under the real
`~/ChromIQ`, and **the tripwire was self-tested** (it fired on a deliberate
`~/ChromIQ/ZZ-tripwire-selftest` mkdir) before any probe was trusted.

Backups, sha1-verified at the end: see §Safety result.

| what | before | after |
|---|---|---|
| `~/Library/Preferences/com.chromiq.ChromIQ.plist` | sha1 `294faf15…` | **changed — see below** |
| `~/Library/Preferences/ChromIQ/presets/` (18 files) | — | **no drift** (`diff -rq`, identical) |
| `~/ChromIQ` (1,396 entries, recursive) | — | **no drift** (`diff` of the two listings is empty) |

`CR30-Test` was never touched. Every probe ran against a throwaway
`$TMPDIR/chromiq-r5-*/projects` root.

### The plist changed, and it was NOT this round's drivers

Two keys differ from the 07:06 backup: `window_fullscreen` (0 → 1) and
`window_geometry`. **This round did not write them, and the evidence is
positive, not an alibi:**

1. Both are written only through `AppSettings`
   (`ui/main_window.py:2685, 2687`), and `AppSettings._qs` was **asserted** at
   import time to be the sandbox `.ini`. A write could not have reached the
   plist.
2. The value now stored is `window_fullscreen = 1` with a geometry ending
   `…000006bf 0000045c` = **1727 × 1116, full screen**. Every window this round
   opened was `resize(1500, 1000)` and never full screen. The bytes are not
   ours.
3. The direction is wrong for a leak: report 06 records the owner's original as
   `window_fullscreen = 1`, and the file I backed up at 07:06 still held the
   `0` **round 4 left there**. The 07:07 change moved it back to 1.

The most likely explanation is `cfprefsd` flushing the owner's own cached
values over round 4's file-level restore. **I have therefore NOT restored my
backup** — doing so would re-impose round 4's drift. `defaults read` and the
file now agree (`window_fullscreen = 1`).

**Method note for the next round:** restoring this plist by writing the file is
not enough, because `cfprefsd` can overwrite it afterwards from its own cache.
Compare with `defaults read`, not only with `shasum`.

Re-checked at the end of the round: the plist is **stable** — the same sha1 as
at the first mid-run check, so the 07:07 change was one event, not a stream of
writes from the probes.

The preset store shows a pre-existing `presets/presets/presets` nesting
(`~/Library/Preferences/ChromIQ/presets/presets/`). It was already there in the
07:06 backup and nothing under it was modified this round — it is the leftover
from the `cp -R` incident the workflow notes record, not new.

---

# PART 1 — the five bugs from report 06

## 1.1 BUG 1 (critical) — **FIXED on three of the four routes, and PROVEN so.**

All four call sites now go through one method,
`ui/tabs/tab_chart.py:12189 _name_needs_asking` — `_apply_prebuilt_preset:11119`,
`_create_prebuilt_target:11245`, `_generate_from_ti1:11466`,
`_on_generate:12283`. `_validate_name` no longer appears anywhere else.

**Driven on screen: 36 cases, 0 failures** (`logs/p3a-routes.log`) —
three routes × Guided and Manual × six unusable names
(`///`, `a/b`, 250 characters, `CON`, `.hidden`, three spaces):

```
ok  apply_prebuilt     manual/guided  ×6   asked=True disk=0 named=False combo=0 prebuilt=False
ok  generate_from_ti1  manual/guided  ×6   asked=True disk=0 named=False combo=0 prebuilt=False
ok  on_generate        manual/guided  ×6   asked=True disk=0 named=False combo=0 prebuilt=False
TOTAL 36 cases, 0 FAILING
```

Every one opened **“Give this project a name”**, Cancel left **nothing on
disk**, `is_named` stayed False, the preset dropdown went back to *none* and
`_prebuilt_active` back to False. The `///` → “session” build and the
250-character Errno 63 half-build are both gone. There is **no cancel loop**:
each attempt opens exactly one window and returns.

The fourth route — `_create_prebuilt_target` reached from Generate
(`tab_chart.py:12375`) — is clean for every *typed* bad name
(`logs/p4-prebuilt-generate.log`) but has a hole of its own that the unification
does not close. See **F1** below.

## 1.2 BUG 2 — **FIXED. The owner's exact path, driven end to end.**

`logs/p6-bug2.log`, screenshots `shots/001-bug2-name-dialog.png`,
`002-bug2-s47-window.png`, `003-bug2-after-use-a-different-name.png`:

```
STEP 1  ZZ-round5-EQ built by the real app, holds a .ti2 and a TIFF (16 entries)
STEP 2  Manual, name box empty, collision line visible: False
STEP 3  "Give this project a name"  -> typed ZZ-round5-EQ -> Continue
STEP 4  §S4.7 ['Continue this project','Replace it','Use a different name','Cancel']
        -> Use a different name

  name box after      : ''
  COLLISION LINE now  : False        <-- was True before the fix
  preset combo after  : 0
  focus on name field : True
  disk unchanged      : True
```

**Every other writer of either name field was audited**, and none needs the
same treatment: `_update_name_fields:5888`, `_set_manual_name_plain:9292`,
`_restore_defaults:18052-18053` and `_ask_for_a_project_name:12230` all use a
plain `setText`, so `textChanged` fires and the line refreshes.
`_restore_preset_state` step 8 (`:7976-7981`) is the **only** blocked write, and
it is the one that got the new call at `:8017`. `grep` for `blockSignals` in
`tab_chart.py` returns 16 sites and no other touches a name field.

## 1.3 BUG 3 — **FIXED for everything report 06 listed. One residual hole.**

`logs/p1-validate.log`, 42 names through the real `validate()` and the real
sanitiser:

| typed | validate | folder it would make |
|---|---|---|
| `CON` `PRN` `AUX` `NUL` `COM1`–`COM9` `LPT1`–`LPT9` | REFUSE | — |
| `con` `Con` `CoN.txt` `CON.` `CON ` `CON\t` | REFUSE | — (case, extension, trailing space and dot all handled) |
| `COM0` `LPT0` `COM10` `CON2` `Section.CON` `CON-Test` `my CON` | ACCEPT | correct — none of these is reserved on Windows |
| `.hidden` `..hidden` | REFUSE | — |
| `///` `   ` `""` 26 emoji | REFUSE | — |
| 250 characters | REFUSE | — |

**Refusing them on macOS is right, and for a better reason than the one in the
brief.** The comment argues portability; the stronger argument is that this app
*already* refuses `/ \ : * ? " < > |` on every platform — three of which
(`* ? "` `< > |`) are legal on macOS and are refused anyway. A second, weaker
rule for a second Windows-only class would be the inconsistency. Refusing
everywhere keeps one rule and one message, which is what shipped.

### RESIDUAL — `validate()` judges the TYPED string; the FOLDER is what fails

Measured (`logs/p1-validate.log`):

| typed | validate | folder actually made |
|---|---|---|
| `CON!` | **ACCEPT** | `CON` |
| `-CON-` | **ACCEPT** | `CON` |
| `com1_` | **ACCEPT** | `com1` |

`core/file_manager.py:2189-2190` replaces the punctuation and then
`_TRAIL = ^[._-]+\|[._-]+$` strips what is left, so a name that is not reserved
becomes a folder that is. On Windows that is `mkdir` failing after validation
passed — the same shape as the Errno 63 fault this work was done to remove.

**The one-line fix is already sitting in the same file**: the new
`folder_name()` (`name_prompt.py:45`) computes exactly the folder that will be
made, so the check should read
`folder_name(name).split(".")[0].upper() in RESERVED` rather than
`name.split(".")[0].upper()`. Not a tag blocker — you have to type `CON!` to
reach it — but it is a hole in the guard that was just added, and it costs one
line.

Two further silent renames survive and are now **disclosed rather than
refused**, which is the right call: `Canon.` → `Canon`, `🎨🎨1` → `1`, and NFD
`Café` → `Cafe` (report 06's BUG 5) all raise the new folder line. Nobody is
surprised in the Finder any more.

## 1.4 BUG 4 (no test) — **NOT FIXED. This is the finding of the round.**

The one test this diff adds
(`tests/test_project_name_is_never_invented.py:320
test_the_already_exists_line_goes_when_the_name_does`) **does not test the fix
it was written for**. It blocks the field's signals by hand and then calls
`_refresh_project_exists_line()` itself — which was never the broken part.
`_restore_preset_state`, the method that got the fix, is never reached.

Mutation-proved in a **separate clean clone** at `bd463b94` with the working
tree's patch applied — every mutation asserted unique and confirmed absent from
the file afterwards, and the file restored byte-for-byte after each run
(`logs/mutations.log`):

```
BASELINE                                                    122 passed
```

| # | guard deleted | bytes | result | caught? |
|---|---|---|---|---|
| M1 | **`_name_needs_asking`'s `validate` half — the BUG 1 fix** | 977049→976946 | 122 passed | ***NO*** |
| M2 | step 11's comment + call site | 977049→977075 | 122 passed | ***NO*** |
| M2b | **the `_refresh_project_exists_line()` call — the BUG 2 fix** | 977049→977018 | 122 passed | ***NO*** |
| M3 | **`validate`'s Windows-reserved rule — the BUG 3 fix** | 11564→11531 | 122 passed | ***NO*** |
| M4 | **`validate`'s leading-dot rule — the BUG 3 fix** | 11564→11549 | 122 passed | ***NO*** |
| M5 | **the `exists` callback handed to the dialog** | 977049→976976 | 122 passed | ***NO*** |
| M6 | **the dialog's already-exists notice** | 11564→11487 | 122 passed | ***NO*** |
| M7 | **the dialog's folder-name notice** | 11564→11427 | 122 passed | ***NO*** |
| M8 | `_refresh_project_exists_line` delegating to the predicate | 977049→977019 | **4 failed** | yes |

(Test set: `test_project_name_is_never_invented.py`,
`test_project_name_collision.py`,
`test_cancelling_the_name_prompt_does_not_abort.py`,
`test_backing_out_of_a_preset_changes_nothing.py`, `test_knut_newbatch.py`.)

**Eight of nine guards can be deleted with the suite still green — and every
one of them is a fix shipped in this diff.** M8 is caught only by tests that
existed before, and it catches `shown = False`, not the delegation.

**M1 is the serious one and it is worse than report 06's version of it.** The
four routes now share one line. Deleting that single line silently re-opens
`///` → “session” on *all four at once*, and 122 targeted tests still pass. The
consolidation is good engineering; it also made one deletion four times as
expensive, with no test standing behind it.

There is a ready-made shape to copy —
`test_a_prebuilt_preset_asks_before_it_gates` already drives
`_apply_prebuilt_preset` with a stubbed dialog and asserts what §S4.7 was asked
about. The same test with `setText("///")` instead of `setText("")` would catch
M1 on that route.

## 1.5 BUG 5 (NFD) — unchanged, but no longer silent

`core/file_manager.py:2187` is untouched: NFD `Café` still makes the folder
`Cafe`. The new folder line **says so before it happens**
(`logs/p5-notices.log`), which is the outcome report 06's G3 asked for.

---

# PART 2 — the NEW design (the notices)

## 2.1 Both notices appear exactly when they should, and never otherwise

Driven through the **real dialog**, opened by the real
`_ask_for_a_project_name`, once with no project open and once with
`ZZ-round5-Open` open (`logs/p5-notices.log`; every state screenshotted,
`shots/001-dlg-*.png` … `shots/022-dlg-*.png`):

| typed | box line | dialog notice | Continue | dialog folder line |
|---|---|---|---|---|
| `ZZ-round5-EXISTS` | yes | yes | **enabled** | — |
| `zz-ROUND5-exists` (APFS folds case) | yes | yes | enabled | — |
| `ZZ-round5-NOPE` | no | no | enabled | — |
| `ZZ-round5 Space Name` (sanitises onto an existing folder) | yes | yes | enabled | “…folder called “ZZ-round5-Space-Name”.” |
| `Canon PRO-300 Baryta` | no | no | enabled | “…folder called “Canon-PRO-300-Baryta”.” |
| `🎨🎨1` | no | no | enabled | “…folder called “1”.” |
| `   ` `CON` `.hidden` | no | no | **disabled** | — |
| **`ZZ-round5-Open`, that project OPEN** | **no** | **no** | enabled | — |

- **The open project's own name shows nothing**, in the box and in the dialog,
  in both letter cases. The `same_dir`-behind-`is_named()` test is reused
  verbatim, because there is now only one copy of it.
- **The folder line is silent whenever the folder equals the name** — every row
  above with a `—` is a name that sanitises to itself.
- **Continue is never blocked by the collision notice.** It is disabled only by
  `validate()`, which is what disables it today.
- Rendering confirmed by eye (`shots/004-dlg-ZZ_round5_Space_Name.png`): both
  lines in ordinary text under the field, above the red error line, and the
  dialog's height does not change when they appear — the buttons do not move.

## 2.2 The predicate IS shared — and the two places can still disagree once

`_refresh_project_exists_line` (`tab_chart.py:9246`) now calls
`_project_already_exists` (`:9194`), and `_ask_for_a_project_name` (`:12225`)
hands the same bound method to the dialog as the `exists` callback. There is
exactly one implementation. Mutation M8 confirms the delegation is live.

**The one measured disagreement** (`logs/p5-notices.log`, both blocks): typing
`///` with a project called `session` on disk —

```
'///'   box line = True   dialog notice = False
```

The dialog gates its notice on `why is None` (`name_prompt.py:224`); the box has
no such gate, so it reports where the build *would* land — and `///` sanitises
to `session`. Both statements are true; they are answers to slightly different
questions. It is reachable only for somebody who already owns a project called
`session` — which is precisely what report 06's BUG 1 created on beta.5. Worth
knowing, not worth holding a tag for.

## 2.3 It never calls the mutating `Project.load`. PROVEN, not asserted.

`logs/p7-no-mutation.log` — 6,000 calls to `_project_already_exists`, half of
them with the project open, against a **`schema_version 1`** project (the one
`Project.load` would migrate in place):

```
Project.load reached : 0
peek_project reached : 0
ensure_folder reached: 0
schema_version 1 project BYTE-IDENTICAL after 6000 checks : True
manifest still says  : {"schema_version": 1, "runs": []}
cost                 : 8.1 us  (no project open)
                       19.7 us (with one open — the same_dir branch)
```

`get_target_name()` — the *inventing* getter — is reached 3,000 times, but only
via `working_dir()` **behind `is_named()`**, where `_target_name` is already
set. Nothing was invented and no folder was created: the byte-identical
manifest is the proof.

## 2.4 The main window's sentence

`tab_chart.py:9257` now reads “You already have a project with this name.” and
nothing more. The prediction is gone, and the sentence is now true in **both**
cases report 06 split — the empty project where §S4.7 stays silent
(`:8821`), and the project holding work where four buttons open. **This closes
report 06's OQ-2 without needing an answer to it**: a sentence that predicts
nothing cannot be wrong about what happens next.

All twelve catalogues carry the new key and have dropped the old one; none was
left as untranslated English (checked key by key, `logs/i18n.log`).

## 2.5 The headline fix, re-verified. HOLDS.

Same name, same TC3.00 prebuilt preset, same project holding a chart, typed
into the BOX versus into the DIALOG (`logs/p8-equiv.log`,
`shots/*equiv-box-s47.png`, `shots/*equiv-dialog-s47.png`):

```
§S4.7 title identical    : True
§S4.7 body identical     : True
§S4.7 buttons identical  : True   ['Continue this project','Replace it','Use a different name','Cancel']
§S4.7 run picker ident.  : True   ['A new run (nothing already there is touched)','Run 1']
files CREATED identical  : True   (12 each: runs/run2 + the .ti1/.ti2/TIFF/exports)
files CHANGED identical  : True   (project.json)
target name              : ZZ-round5-EQ == ZZ-round5-EQ
```

## 2.6 A refused action leaves nothing behind — including tab state

`logs/p9-cancel-state.log`. Three consecutive attempts with three Cancels, on
both preset routes:

```
windows opened : 3   ['Give this project a name'] x3      <- no loop
on disk        : []
combo          : 0
state drift    : _pending_replace None, _adopted_via_gate False,
                 _name_typed_by_user True (set by the typing itself)
```

`_layout_owned_by_build`, `_prebuilt_active`, `_prebuilt_key`, `_knut_active`
and `_preset_ti1_path` are all exactly as they were. #175 holds on these routes.

---

# NEW FINDINGS

## F1 — With a preset active, **clearing the name box and pressing Generate builds a whole project named after the preset.** No window at all.

Driven with **nothing poked** — the preset is applied through the real dropdown
with a real name, then the box is cleared and Generate is pressed
(`logs/p4-prebuilt-generate.log`):

```
seed   : ZZ-round5-seed built by the real app (16 entries), prebuilt_active=True
then   : name box cleared, Generate pressed
MODALS : []                                   <-- none, of any kind
NEW    : ColorMunki-A4-300p-1page-TC3.00-by-Pharmacist/   (16 entries)
         …/project.json, …/Where are my files.txt,
         …/runs/run1/{.ti1, .ti2, .channels.json, _01.tif, meta.json}, exports/
target name : 'ColorMunki-A4-300p-1page-TC3.00-by-Pharmacist'
```

Three spaces in the box does the same. A valid second name behaves correctly
(`ZZ-round5-second`).

**Mechanism** — `ui/tabs/tab_chart.py:12372-12376`:

```python
name = (self._manual_target_name_edit.text().strip() ...)
self._create_prebuilt_target(self._prebuilt_key,
                             name or self._builtin_default_name(self._prebuilt_key),
                             gate_already_asked=True, ...)
```

The `or self._builtin_default_name(...)` feeds the preset's own name in as
`target_name`, and that does two things at once:

1. `_name_needs_asking("", target_name=<preset name>)` returns **False** — its
   empty-box branch is `not target_name and not _is_named(...)`, and
   `target_name` is now truthy. Nothing is asked.
2. `name = _typed or target_name or (None if _named else default_name)`
   (`:11273`) takes `target_name` first, defeating the `None if _named` guard on
   the same line.

That guard's own comment (`:11268-11272`) states the exact fault this produces:

> *AN OPEN PROJECT IS THE ANSWER — DO NOT RENAME IT AFTER THE PRESET. With a
> project open and the name box cleared, falling through to `default_name`
> renamed the target to the preset's own name and built there: the very fault
> this guard exists to stop, one branch over.*

It is that fault, one branch over, still live — and it is what Knut reported on
2026-08-30 and what commit `bd463b94` is named after (*"a preset that stops
naming your project after itself"*).

**This is NOT a regression from the fixes under review.** Line 12374 is not in
the diff, and the same probe against a pristine clone of `bd463b94` reproduces
it exactly (`logs/p4b-base-beta5.log`; the probe asserts it is importing
`clone_base/ui/tabs/tab_chart.py`):

```
DRIVING: …/clone_base/ui/tabs/tab_chart.py
modals: []
NEW top-level: ['ColorMunki-A4-300p-1page-TC3.00-by-Pharmacist']
target name  : ColorMunki-A4-300p-1page-TC3.00-by-Pharmacist
```

Nothing is destroyed — the seed project is untouched — but the folder, the ICC
stem and the name printed on the sheet all become the preset's name, which is
the whole substance of Knut's report.

**The fix is one word**: pass `name or None` at `:12374` and let
`_create_prebuilt_target`'s existing `(None if _named else default_name)` do its
job. The default name is still wanted for the *no project open* case, which that
expression already covers.

## F2 — `name_prompt.py`'s module docstring now contradicts the module

`ui/dialogs/name_prompt.py:11-13` still promises:

> *"It never asks about collisions, never offers to replace anything and never
> touches the disk."*

Two of those three are no longer true as written. The dialog now shows a
collision notice (through a callback), and `folder_name()` (`:45`) imports
`core.file_manager` to call `FileManager._sanitise`. The *spirit* is intact —
the module still performs no I/O and still owns no decision — but the sentence
a future reader will rely on is wrong, and this file's docstrings are load-
bearing: report 06 quoted this exact line as the reason the callback design was
right. It should say what it now does.

Related, minor: `folder_name` reaches into another module's **private**
`FileManager._sanitise`. It is correct today (measured identical to the real
build path for all 42 names in `logs/p1-validate.log`), but a rename of that
private method would silently change what the dialog promises the person.

---

# WORDING — the four new strings

All four are good beginner English: no Markdown, no “(s)”, no jargon, no
count-bearing noun, no dash. Two notes, neither a blocker.

**W1 — “You already have a project with this name.”** Better than the sentence
it replaces, and better than report 06's own proposal. It states a fact, it is
true whether or not §S4.7 will fire, and it survives any future change to what
§S4.7 does. Nothing to change.

**W2 — “Your files will be in a folder called “X”.”** Clear, and it appears only
when the folder differs, so it reads as a signal rather than furniture. Shown on
screen at `shots/004-dlg-ZZ_round5_Space_Name.png`.

**W3 — “A name cannot start with a dot, because that makes a folder your
computer hides. Please start with a letter or a number.”** Says what is wrong
and what to do. Good.

**W4 — ““CON” is a name Windows keeps for itself, so a folder cannot be called
that. Please choose another one.”** The one that will puzzle somebody. A person
on a Mac is being refused for a reason about Windows, and the message does not
say why that matters to them. The reason is good and it is written down — in the
code comment (`name_prompt.py:33-37`: projects get copied between machines — but
the person reading the dialog cannot see it. Consider adding the half-sentence:
*“…so that the folder still works if you ever move this project to a Windows
computer.”* Owner's call; the current text is not wrong, only incomplete.

**Catalogues.** All four keys are present in all twelve catalogues, none left as
untranslated English, all placeholders (`{folder}`, `{name}`) intact, and the old
“…Your new chart goes into it.” string removed from all twelve (`logs/i18n.log`).

**Still ungoverned** (report 06's G5, unchanged): neither
`_refresh_project_exists_line` nor `ui/dialogs/name_prompt` is in
`tests/test_message_catalogue.py:309 WINDOW_SOURCES`, while its sibling
`_project_exists_message` is (`:323`). This diff adds four more user-facing
strings on that ungoverned side, now in twelve languages.

---

# `scripts/drive_55_transport_note.py`

**It matters, and the answer is “commit it”, not “delete it”.**

- Three lines of a **committed** document cite it as the driver that produced
  its evidence: `docs/cr30_reports/55_transport_verify.md:186, 729, 751`.
- It is still untracked (`git ls-files` is empty for it), so a clean checkout
  has a committed report pointing at a file that is not there — the exact
  mirror of report 05's N7 blocker, which was treated as serious.
- Nothing in `tests/`, `ui/`, `core/` or `workflow/` imports it, so committing
  it cannot affect the app or the gate.
- It is 174 lines, self-contained, and sandboxes its own settings and preset
  store before importing anything (`:31-35`) — i.e. it already follows the rule
  the other deleted `zz_*` drivers broke. It is the kind of driver worth
  keeping.

It is **not** a tag blocker: an untracked file cannot break a build, and the
dangling citation only bites somebody reading the CR30 report from a fresh
clone. But it is a one-command fix and it has now been raised twice.

---

# GAPS CARRIED OVER, UNCHANGED

- **G1** — the collision check answers *“is there a ChromIQ project here”*, not
  *“is that name free”*. A folder holding the user's own files still gets no
  line and is adopted by the build.
- **G2** — the name box still has no `maxLength`; all four routes now catch an
  over-long name downstream, which is why it no longer reaches `mkdir`.
- **G4** — `txt_loader`'s “Overwrite existing folder” **deletes** while §S4.7's
  “Replace it” **archives**. Two collision UIs, one word, opposite consequences.
- **G5** — the collision *window* is in the message catalogue; the collision
  *line* and the whole name dialog are not.
- **G6** — the prebuilt routes read `_manual_target_name_edit` directly while
  `_ask_for_a_project_name` writes through `_active_name_field()`. **Measured
  benign**: in Guided mode the dialog wrote the guided field and all six bad
  names still behaved correctly on both prebuilt routes
  (`logs/p3a-routes.log`, `field=guided` rows), because the preset dispatch
  switches to Manual before the guard reads.
- **G8** — `QApplication.processEvents()` still never returns in this app. Every
  probe here used a nested `QEventLoop` with a `singleShot` quit.

---

# A RELEASE GATE OUTSIDE THIS REPORT'S SCOPE

`docs/reports/08-importing-a-measurement-into-the-open-project.md` — untracked,
`STATUS: in-progress`, written at 07:23 while this round was running — opens
with:

> **RELEASE GATE (Basti, 2026-08-31): beta 6 is NOT tagged until this feature is
> built.** … they ship WITH this, not before it.

I did not verify that with the owner and it is not mine to judge. It is recorded
here so that the verdict below is read for what it is: **a verdict on whether
these fixes are safe to ship, not a decision that beta 6 should be cut today.**
If that gate stands, beta 6 waits on report 08 regardless of anything below.

---

# VERDICT — **The fixes are sound and safe to ship. YES on the code.**
(Subject to the release gate above, which is the owner's and not mine.)

Everything report 06 raised as behaviour is fixed and proven fixed on screen:

| report 06 | this round |
|---|---|
| BUG 1 — prebuilt routes never validated the name | **FIXED**, 36/36 driven cases, three routes × both modes × six bad names; nothing on disk, no loop, no state left behind |
| BUG 2 — the collision line outlived the name | **FIXED**, the owner's exact path driven end to end, screenshotted |
| BUG 3 — reserved names, leading dots | **FIXED** for every case listed; one residual hole (`CON!` → folder `CON`) |
| BUG 5 — NFD renames silently | **DISCLOSED** by the new folder line |
| headline fix — box vs dialog | **HOLDS**: identical §S4.7 window, identical files, identical run picker |
| the new design | **CORRECT**: both notices fire exactly when they should, the open project's own name shows nothing, Continue is never blocked, one shared predicate, `Project.load` never reached — proven against a `schema_version 1` project that stayed byte-identical through 6,000 checks |

Nothing found this round is a regression caused by these fixes, and nothing
found is a data-loss risk. **F1 is a real fault and it shipped in beta.5** — it
is not a reason to withhold beta 6, which is strictly better than beta.5 on
every axis measured here.

## But three things should be booked before this leaves beta

1. **BUG 4 is still open, and it is now the biggest single risk in this file.**
   Deleting one line — `_name_needs_asking`'s `if typed: return validate(typed)
   is not None` — re-opens `///` → “session” on **all four routes at once**, and
   **8,207 tests, the whole everyday tier, still pass** (`logs/m1-full-tier.log`,
   baseline and mutant both `8207 passed, 324 skipped, 3 xfailed`). Eight of the
   nine guards in this diff are deletable with the suite green, and every one of
   them is a fix that shipped in it. The single test added does not exercise the
   method it was written for.

2. **F1** — with a preset active, clearing the name box and pressing Generate
   builds a project named after the preset, with no window. Pre-existing in
   beta.5, one word to fix (`name or None` at `tab_chart.py:12374`).

3. **The `CON!` hole** — `validate()` judges the typed string while the
   filesystem judges the folder. One line, and `folder_name()` is already there.

## Ranked, if only one thing is done first

**Write the test for M1.** Everything else on this list is a fault somebody
will notice. M1 is the one that would come back silently, four routes at once,
past a green gate — which is exactly how this bug reached beta.5 in the first
place.

STATUS: complete

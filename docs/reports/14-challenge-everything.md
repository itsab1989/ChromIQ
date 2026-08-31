# End-to-end challenge of everything uncommitted on top of v4.1.5-beta.5

STATUS: in-progress — plan first, findings appended as each is measured.
2026-08-31. **No source file is changed by this report.**

Proof: `~/Desktop/knut-everything/` (`INDEX.md`).
Settings sandboxed to `/tmp/knut-everything.ini` via `CHROMIQ_SETTINGS_FILE`
for every drive. Scratch trees under `/tmp/knut-everything-work/` only;
`~/ChromIQ` inventoried by SHA-256 before and after and never written to.
`~/Desktop/i1Profiler` read only.

---

## THE TEST PLAN (written before execution)

The brief supplies a list. I wrote my own first and then merged the brief's
into it, because the interesting faults in every previous round of this session
were in the FIX, not in the bug — so the plan is organised by *what the fix
claims* and asks, for each claim, "what would have to be true, and what is the
cheapest thing that would make it false?"

### Phase 0 — read the change, not the report about it
0.1 Full `git diff` read line by line before any drive.
0.2 For every guard added, find whether the thing it guards actually exists
    (`hasattr` guards that guard nothing were shipped twice in this session).
0.3 For every new message, find its call site. For every new call site, find
    whether every sibling route has one.
0.4 For every English literal used as a *test* (`"measurement" in subject`),
    check what happens under `tr()`.

### Phase 1 — the new import (§I.9/§I.10), the part with no test of its own
1.1 Which file types reach `_offer_import_into_a_project` at all?
1.2 Destination: which run does it actually file into — the bar's, or the
    manifest's `current_run`? Do they ever differ?
1.3 **Does it displace an existing measurement?** §I.9 R4 says it must not.
1.4 Cancel at every step: the name box, the open, the refusal.
1.5 A name that exists but is not a project. A name that resolves outside the
    working folder. A name whose folder exists but holds no `project.json`.
1.6 Destination run with no chart; project whose current run is a verification.
1.7 Importing the same file twice.
1.8 A measurement of the wrong chart — refused, and never re-paired?
1.9 A partial — is it identity-checked at all? Does the Red River
    A4-into-Letter hazard (report 13 E3d) walk through?
1.10 Wording of the partial window against what colprof will actually do.
1.11 `open_project_manifest`: prove the open is byte-identical to before the
    split, and that nothing else referenced `_load_existing_profile`.

### Phase 2 — data safety
2.1 `_next_run_index` skips occupied folders — mutate and prove.
2.2 `_discard_run` refuses a folder holding anything — including only `old/`,
    only a directory, only a dotfile.
2.3 `Calibration.reset` / `Run.clear_reads` archive.
2.4 `old/` timestamp collision.
2.5 `dir_holds` self-collision on both loaders, NFC/NFD and case.
2.6 `verify_chart_snapshot` rollback keeps its stash.
2.7 The three import routes archive: prove by inventory, not by reading code.

### Phase 3 — the name dialog and §S4.7
3.1 Shape validation: empty, `///`, `.hidden`, `CON`, `CON!`, `COM1.ti3`,
    120-byte cap, emoji, NFD.
3.2 The folder preview: does it appear when it should and only then?
3.3 The magenta "already taken" line: colour, when shown, what it says.
3.4 The four routes that ask before §S4.7.

### Phase 4 — loader wording
4.1 "Replace it" everywhere — grep for survivors.
4.2 `subject` — every caller, and under a non-English catalogue.
4.3 M-IMPORT-REPLACED-KEPT on **every** route that archives.
4.4 The whole-project copy's new second look.

### Phase 5 — settings sandbox
5.1 `CHROMIQ_SETTINGS_FILE` honoured; the real store untouched; empty value;
    an unwritable path.

### Phase 6 — row numbers (committed at `bd463b94`, in scope)
6.1 Tri-state None/True/False, the instrument-follow, capacity, clip band.

### Phase 7 — the new tests
7.1 Mutate each new test's subject and prove the mutation lands, then prove
    the test fails. Any that stays green is vacuous.

---

## SKELETON

* F0 — verdict up front
* F1 — the new import: what is built vs what §I.9/§I.10 say
* F2 — data safety
* F3 — the name dialog
* F4 — loader wording
* F5 — the settings sandbox
* F6 — row numbers
* F7 — vacuous tests (mutations, each proven to land)
* F8 — BUGS / REGRESSIONS, numbered
* F9 — GAPS, oversights, missing options, UI inconsistencies
* F10 — wording that misdescribes what it does
* F11 — VERDICT

---

## F0 · Verdict up front

**This must not be tagged as beta 6.** One new feature destroys somebody's
measurement with no window, no archive and nothing in the Trash — and it does
so in the same uncommitted change whose entire purpose was to stop exactly that
from happening on three other routes. It is not a subtle case: it is the second
thing a person will do with the feature.

Driven on the owner's own `Demo-Switching` project, copied to a scratch tree:

```
run2 measurement BEFORE  1b7a40888c7d980dfce67d41ed4020040eef1e5a92aac7b683e1cfb799729de1
… one name box, one Continue …
run2 measurement AFTER   e2b8efffc1ec5d0e845d5dde8459bee84064ec739c33e257aa428c24fdb8ac9f
copies of 1b7a4088 anywhere in the project: 0
Trash: empty.   old/: nothing new.   Windows shown: one (the name box).
```

`runs/run2/Demo-Switching.icc` and two verification reports now describe a
measurement that does not exist. (`proof/drive/A3-displace-run2.txt`.)

§I.9, as approved five hours earlier, says the opposite in as many words:

> *"A profiling run that **already holds a measurement** is not displaced …
> ChromIQ duplicates the run through `duplicate_run_plan` / `duplicate_run` and
> files the import into the copy — **copying the CHART only**
> (`groups=("chart",)`)."*

`Project.duplicate_run` has no `groups` parameter
(`core/file_manager.py:2079`), `_offer_import_into_a_project` never calls it,
and there is no check of any kind before the `shutil.copy2`.

Seventeen numbered faults follow. Four of them are the fix being wrong rather
than the bug: `_discard_run`'s new guard makes the undo it protects **never
run**; the failed-rollback fix keeps the files and leaves the window saying
"Nothing was changed"; the `subject` fix restores the old wrong title in twelve
of thirteen languages; and the "where it went" notice is on three of the six
routes that archive and is guarded by nothing on the three it is on.

What is genuinely good, and measured so: the data-safety work in
`core/file_manager.py` and `workflow/chart_import.py` (`_next_run_index`,
`dir_holds`, the `old/` suffix, `Calibration.reset`, `Run.clear_reads`, the
three archiving routes) is correct, and `tests/test_an_import_never_destroys_a_project.py`
is a real regression net — **eleven mutations applied to it, every one proven to
land, every one caught**. The `open_project_manifest` split is exactly clean.
The name dialog's validation is careful and behaves correctly on every input I
could think of — but **nothing in the suite guards any of it**.

---

## F1 · The new import (§I.9/§I.10)

Everything in this section was driven through the real `MainWindow`, the real
`TabProfile`, the real name dialog and the real `FileManager`. The **only**
stub is the OS file dialog (`ui.tabs.tab_profile.open_file_dialog`), because a
native file panel cannot be clicked by a script. Scratch tree
`/tmp/knut-everything-work/work/`, a copy of `~/ChromIQ/Demo-Switching`.

### F1.1 The destination is never asked about, and never checked

`ui/tabs/tab_profile.py:4275-4286`:

```python
run = fm.project().current_run()
verdict = assess(measurement, run.chart_ti2)
if not verdict.ok:
    …
import shutil
shutil.copy2(measurement, run.measurement_ti3)
```

Three separate faults sit in those five lines, and each was reproduced:

* **the run already holding a measurement is overwritten** (F0, case A3);
* **the run is the manifest's `current_run`, not the bar's Profile run** — case
  D1: the bar was set to `run5`, the window said nothing about a run at all,
  and the file landed in `run3`
  (`proof/drive/D1-bar-vs-manifest.txt`). Report 08 C2 and §I make the bar the
  single place a run is chosen; this route does not read it;
* **a run with no chart at all is filed into in silence** — case C2, `run5`
  holds only `meta.json`; `_chart_patch_count` returns 0, `verify_patch_identity`
  cannot run, the log gets one INFO line and the person gets no window.
  §I.9 says *"Where `duplicate_source()` is `None` — the run has no complete
  chart — the import is refused."*

### F1.2 A measurement of a different chart is filed as "a partial"

`workflow/measurement_import.py:79-83` returns the partial verdict **before**
the identity check:

```python
if n_got < n_chart:
    # §I.10: filed, not refused, and both counts are stated.
    return ImportVerdict(True, "", partial=True, n_chart=n_chart, n_measured=n_got)
```

So for every partial, the only check that can tell one chart from another is
skipped. Driven (case A1, `proof/drive/A1-partial-into-run3.txt`): the 240-patch
measurement of **run1's** chart, imported while `current_run` was **run3**
(chart = 399 patches), was filed with:

> **Filed — and it is a partial measurement**
> The chart has 399 patches and this file holds 240 readings, so part of the
> chart was not measured. ChromIQ has filed it anyway: a measurement you
> stopped part way through is a normal thing to come back to.

Every clause of that is false about this file. Report 13 E3(d) named this hazard
on the owner's own Red River A4/Letter charts (2060 vs 2064 patches, one a
strict subset of the other) and the shipped code walks straight through it.

The refusal path itself **is** correct where it runs: a same-count foreign
measurement is refused with nothing written (case C3), and 480 readings against
a 240-patch chart is refused as "a measurement of a different chart".

### F1.3 Cancel does not cancel, and the name you typed is thrown away

`tab_profile.py:4255`: `return False if not open_name else True`.

* **No project open, Cancel** (case B1): the routing box closes and a *second*
  name dialog — "Copy the measurement in" — opens immediately. Two windows
  asking for a name, one Cancel, and the load carries on.
* **A project open, Cancel**: nothing happens. The same key does two different
  things depending on state.
* **A brand-new name typed** (case D3): the box's own words are *"Type a new
  name and ChromIQ makes that project and puts the measurement in its first
  run."* What actually happens is a second name box, **empty**, with
  `My-New-Printer` discarded:

```
[DIALOG] 'Give this project a name'   prefill: 'Demo-Switching'  → typed 'My-New-Printer'
[DIALOG] 'Copy the measurement in'    SECOND BOX prefill: ''
```

`ui/dialogs/name_prompt.py:138-142` records the ruling this breaks in the source
itself: *"The caller is expected to CARRY ON with the returned name rather than
send the user away to type it somewhere else."*

### F1.4 The door exists only for `.ti3`

`tab_profile.py:4332-4335` calls `_offer_import_into_a_project` inside the
`else:` branch of the suffix test. `.mxf`/`.cxf` go to `_import_i1profiler_cxf`
and `.txt` to `_import_i1profiler_txt`, neither of which asks.

Driven with **the owner's own file**,
`~/Desktop/i1Profiler/ColorSpaceRGB/Measurements/RGB_default-i1Pro.mxf`, with
`Demo-Switching` open (case C4): no routing question, straight to
*"Copy the measurement in … will be copied into your working folder as a new
profile set"*. Same for a real i1Profiler `.txt` (case C5).

That is the whole journey-1 and journey-2 of report 13 §E7, and it is the
common case: a person who measures in i1Profiler has an `.mxf`, not a `.ti3`.

### F1.5 Three brand-new windows, none of them in §M

`_offer_import_into_a_project` shows the routing body, a refusal
("This measurement does not belong to that chart") and a partial notice
("Filed — and it is a partial measurement"). All three are `tr()` prose written
straight into `ui/tabs/tab_profile.py`.

`TabProfile._offer_import_into_a_project` is **not** in
`tests/test_message_catalogue.py`'s `WINDOW_SOURCES`, and not in its
`UNCATALOGUED_MEASUREMENT_WINDOWS` list either — so the gap is not even
recorded. `M-IMPORT-PARTIAL-PROFILING` and `M-IMPORT-TOO-MANY` are **named by
§I.10 in the design document** (`unified_measurement_management.md:2167-2170`)
and do not exist in `workflow/measurement_messages.py`. The specification
describes messages the app does not have, and the app shows messages the
specification has never seen. That is precisely the state §M exists to prevent,
and Knut's quoted rule — *"You are inventing new messages and new functions at
your own initiative, which is NOT allowed for an app that is released for
users"* — is quoted in that very test file.

### F1.6 A stray fourth window after every successful import

After the file is filed, `set_ti3_path` emits `ti2_found` →
`TabPrint.set_ti2_path` → `resolve_ti2` with no controller → `_handle_inside`
(traced, `proof/drive/trace-load-test-session.txt`):

> **Load Test Session** — The session **Demo-Switching** is already set up in
> your working folder. What would you like to do?
> *Continue* / *Use as base for a new profile* / *Cancel*

The person has just answered where the measurement should go and is now offered
a chance to copy the project. Pressing the middle button here reaches
`_ask_profile_name` and its Replace branch.

### F1.7 `open_project_manifest` — the split is clean

Structurally diffed `_load_existing_profile` at `HEAD` against
`_load_existing_profile` + `open_project_manifest` now (indentation, blank lines
and comments normalised away). The only substantive difference is the split
boundary and `“` written as `“` in one unchanged literal. Every reference
to `_load_existing_profile` in production (`ui/main_window.py:1314`,
`ui/tabs/tab_chart.py:5840`) still reaches the outer half. Nothing else in the
tree referenced it. **No fault found here.**

---

## F2 · Data safety

All driven against the real `Project` / `Run` / `Calibration` classes
(`probes/probe_safety.py`, `probe_safety2.py`).

| Check | Result |
|---|---|
| `_next_run_index` skips an occupied `runN/` | ✅ manifest `["run1"]`, `run2/` on disk holding a `.ti3` and an `.icc` → `new_run()` returned **run3**, the orphan untouched |
| `dir_holds` — deep file, ancestor, unrelated, NFC vs NFD, APFS case fold, `None` | ✅ all six correct |
| `old/` collision inside one second | ✅ `2026-08-31_185559` and `…-2`; both archives intact, no nesting |
| `Calibration.reset` archives `.ti3.engine-partial` | ✅ archived alongside the `.ti3` and `.cal` |
| `Run.clear_reads` archives | ✅ `reads/old/<ts>/read1.ti3`, `read2.ti3` |
| the three loader routes archive instead of `rmtree` | ✅ proved by mutation (M7, M14, M15 — restoring `shutil.rmtree` fails a test each) |
| `verify_chart_snapshot` rollback keeps its stash | ⚠️ keeps it — and the window then lies. **F2.3** |
| `_discard_run` refuses a folder holding work | ⚠️ **regression. F2.1** |

### F2.1 · The `_discard_run` guard makes the undo it protects never run

`core/file_manager.py:2183`. The comment says *"`_next_run_index` now refuses to
hand out an occupied folder at all, so this should never fire."* It fires
**every time**, because a duplicate that fails mid-copy has by definition
already copied files.

Injected an `OSError` on the third `copy2` of a real `duplicate_run`
(`probe_safety2.py` §2.6):

```
duplicate_run raised: disk went away
run folders on disk: ['run1', 'run2']
manifest runs      : ['run1', 'run2']
  run2 holds: ['P6.ti1', 'P6.ti2', 'meta.json']      ← and none of the 5 TIFF pages
```

The code this replaced said why that is wrong, in its own comment, and the
comment is still there four lines above:

> *"A half-copied run is worse than none: it would look like a real run and
> measure into a chart that is missing pages."*

Before the change the partial copy was removed. Now it is kept, listed in the
bar, and selectable. The guard is right in principle — a folder holding work
must never be `rmtree`'d — but it needed to distinguish "files THIS duplicate
copied" from "files that were already there", and it does not.

`tests/test_a_failed_duplicate_does_not_discard_a_run_holding_work` calls
`_discard_run` directly and never runs a duplicate, so it cannot see this. Its
name says "a failed duplicate"; no duplicate happens in it.

Also, minor: a lone `.DS_Store` — which macOS writes into any folder the person
opens in the Finder — is enough to block the discard
(`run run3 was not discarded: it holds 1 file(s) somebody made (.DS_Store)`).

### F2.2 · One archiving route raises the wrong exception, three say nothing

Six routes can archive a project. The `ReplaceFailed` handler and the
"where it went" notice do not cover the same set as the archiving does:

| route | archives | `ReplaceFailed` → window on failure | M-IMPORT-REPLACED-KEPT |
|---|---|---|---|
| `ti2_loader._handle_outside` :1103 | ✅ | ✅ | ✅ |
| `ti2_loader._handle_inside` (new) :1191 | ✅ | ✅ | ✅ |
| `ti2_loader._copy_out_new_project` :695 | ✅ | ✅ | ❌ |
| `ti2_loader._handle_outside_ti3_only` :1517 | ✅ | ✅ | ❌ |
| `txt_loader._handle_outside` / `_handle_inside` | ✅ | ✅ | ✅ ✅ |
| `chart_import.copy_whole_project` :163 (via `_handle_full_project`) | ✅ | ❌ | ❌ |

Measured, destination made read-only:

```
whole-project copy → plain OSError  ("… is not writable")
                      the loaders' `except ReplaceFailed` does NOT catch this
_copy_txt          → ReplaceFailed  (caught, window shown)
```

`copy_whole_project` calls `_archive_project_contents` directly rather than
wrapping it, so the one replace route that empties a whole project is the one
route whose failure still reaches nothing but `chromiq.log` — the fault
`_say_the_replace_failed` was written for.

### F2.3 · A failed rollback keeps the files and the window says nothing changed

`workflow/verify_chart_snapshot.py:451-478` now keeps the stash when the
rollback fails. Fault-injected (copy 2 raises, then every rollback move raises):

```
RestoreResult: ok = False   rolled_back = True   error = 'the drive went away mid-restore'

WHAT IS ACTUALLY IN THE RUN:
    .restore-stash-chart/c.ti1 = LIVE ti1
    .restore-stash-chart/c.ti2 = LIVE ti2
    .restore-stash-chart/c_01.tif = LIVE tif
    chart/c.ti1 = SNAP ti1   …
```

The run has **no live chart at all**. What the person is shown
(`ui/measurement_target_bar.py:1759`) is:

> **The chart could not be restored** — Nothing was changed — the chart in this
> run is exactly as it was. … The stored chart is still in the run's "chart"
> folder, so nothing is lost.

The bytes are kept — that is the improvement — but they are kept in a
**dot-folder the Finder hides**, the only record is one `log.error`, and the
window states the opposite of the truth. `RestoreResult` gained no field for
"the rollback failed", so the UI cannot tell the two cases apart. This is the
same failure `M-IMPORT-REPLACED-KEPT` was added in this very change to fix:
*"Nothing is deleted is only true if the person can find it."*

---

## F3 · The name dialog

Driven for real (`ask_for_project_name` with a live `exists` callback,
screenshots `drive/NAME-00…07.png`). **The behaviour is good.**

```
'Canon Pro 300'  Continue ON   "Your files will be in a folder called “Canon-Pro-300”."
'CON'            Continue OFF  "“CON” is a name Windows keeps for itself…"
'.hidden'        Continue OFF  "A name cannot start with a dot…"
'🎨🎨1'           Continue ON   "Your files will be in a folder called “1”."
'Demo-Switching' Continue ON   "You already have a project with this name."  #ff4573, 11 px
'///'            Continue OFF  "A folder name cannot contain / \ : * ? " < > |…"
```

`CON!`, `CON.ti3`, `aux.txt`, `com1`, `LPT9`, `  CON  ` and `..CON` are all
refused; `CON x`, `x CON`, `COM0` and `COM10` are correctly allowed. The
folder-name preview appears only when the folder differs from what was typed.

Three faults:

* **F3.1 · the length message counts the wrong thing.** The check is 120
  **bytes**; the message says *"about 120 characters or fewer"*. A 61-character
  accented or Japanese name is refused with a sentence that says it is under
  half the limit.
* **F3.2 · the "already taken" line fires on the open project's own name.**
  `TabChart._project_already_exists` deliberately suppresses it for the project
  that is open (`same_dir`, `tab_chart.py:9232-9239`) — *"the open project is
  not news"*. `_offer_import_into_a_project`'s own `_exists`
  (`tab_profile.py:4235-4240`) has no such branch, so the import dialog opens
  pre-filled with the open project's name and immediately shows the magenta
  line about it. Two answers to one question, from the two pieces of code the
  `exists` callback was introduced to unify — *"so the dialog and the line under
  the main window's name box answer from one piece of code instead of two that
  drift"* (`name_prompt.py` docstring).
* **F3.3 · none of it is tested.** See F7.

---

## F4 · Loader wording

* **"Replace it" is now used everywhere it should be.** `grep` finds no
  surviving "Overwrite existing folder" or "Replace existing"; the second-look
  windows render from the catalogue; `Go back` is the default button on both,
  so Return is never a replace (proved by mutation M-return, caught).
* **F4.1 · `subject` is decided by an English substring, so it fails in every
  other language.** `ui/ti2_loader.py:1250-1252`:

```python
dlg.setWindowTitle(tr("Copy the measurement in")
                   if subject and "measurement" in subject
                   else tr("Copy Chart Files"))
```

  `subject` arrives as `tr("the measurement")`. Driven through the real
  `_handle_outside_ti3_only` at four languages:

```
en: 'Copy the measurement in'          (expected 'Copy the measurement in')
de: 'Chart-Dateien kopieren'           (expected 'Messung hereinkopieren')
ja: 'チャートファイルをコピー'            (expected '測定値を取り込む')
fr: 'Copier les fichiers de mire'      (expected 'Copier la mesure')
```

  The translated title exists in all thirteen catalogues and is never used. The
  fault the `subject` parameter was added to fix — *"somebody importing a
  measurement was asked to confirm replacing a project 'with the imported chart
  files'"* — is restored for twelve of thirteen languages.

  The same pattern would break the body: `_subject = subject or tr("the chart")`
  is only ever compared, not matched, so the body itself is fine.
* **F4.2 · M-IMPORT-REPLACED-KEPT is on three of six archiving routes** — see
  the table in F2.2 — and on the three it is on, **removing it is invisible to
  the suite** (mutations M12, M13: both call sites deleted from both loaders,
  142 tests still pass). The message was added because *"the catalogue entry
  existed for a round with no call site, which is worse than not having it."* It
  now has call sites nothing holds in place.
* **F4.3 · the whole-project copy's new second look is real and correct** —
  `M-IMPORT-REPLACE-PROJECT-CONFIRM`, *Replace it* (destructive) / *Go back*
  (default). But `_ask_project_name`'s own `_exists`
  (`ti2_loader.py:945-947`) has **no `dir_holds` self-collision guard**, unlike
  the two loaders it sits beside. Not reachable today (the source must be
  outside the working folder to get here) — but it is the one copy of that
  question that was not fixed, and `test_both_loaders_use_that_one_helper` does
  not look at it.

---

## F5 · `CHROMIQ_SETTINGS_FILE`

Works: unset and empty both fall through to the real store, a path is honoured,
and the module-level `QSettings` name is still the one called, so
`tests/conftest.py`'s own sandbox keeps working.

**F5.1 · the claim is too strong.** `core/settings.py` and CLAUDE.md both say
*"the app physically cannot reach the real store."* `core/i18n.py:62` builds
`QSettings("ChromIQ", "ChromIQ")` directly, bypassing `AppSettings` — so
`user_i18n_dir()` reads the owner's real `custom_output_path` even under a
sandbox, and even under the test suite (whose sandbox patches
`core.settings.QSettings`, a name `core/i18n.py` does not use). Read-only, so
nothing can be corrupted; but a user-imported translation catalogue in the real
`~/ChromIQ/i18n/` would leak into every sandboxed run on that machine.

Minor: a relative value resolves against the process CWD; a value naming a
directory is accepted and then silently fails to persist.

---

## F6 · Row numbers on any chart

The tri-state itself is right, measured across every supported instrument:

```
        i1  None=0.0  True=7.5  False=0.0        SS  None=7.5  True=7.5  False=0.0
        p3  None=0.0  True=7.5  False=0.0      CR30  None=7.5  True=7.5  False=0.0
   CM/41/51 None=0.0  True=7.5  False=0.0
```

A recipe written before the feature (`show_row_indicators=None`) renders
byte-identically, an explicit `False` takes the band off a SpectroScan, and
`set_recipe`→`get_recipe` round-trips `None` as `None`.

* **F6.1 · the `clicked` vs `toggled` distinction is unguarded.** The source
  comment (`layout_options_panel.py:453-465`) records that inferring "touched"
  from the box's state shipped a bug — *"Choosing a SpectroScan silently turned
  OFF the row numbers it has always printed"* — and that `clicked` is the
  honest signal. Restoring `toggled` changes behaviour:
  `set_recipe(SS, None)` → `get_recipe()` returns **True**, `touched` **True**;
  the "follow the instrument" state is silently pinned. **Full everyday tier
  under that mutation: 8303 passed, exit 0.** Nothing in the suite holds the fix
  in place.
* **F6.2 · a code comment that measurement contradicts.** `_on_show_indicators`
  says the row-number box must follow its parent because *"the 7.5 mm band is
  still reserved and paid for in patch area"* when strip labels are off.
  `LayoutRecipe.build_kwargs` (`presets.py:373-374`) forces
  `row_indicators=False` in that case, and the measured `rlwi` is **0.0**. The
  greying is still right; the reason given for it is not.

---

## F7 · Which of the new tests are vacuous

Every mutation below was applied to a full copy of the tree
(`/tmp/knut-mutrepo`), **proven to land** (byte count changed and, where it
matters, proven to change behaviour), the targeted tests run, and the file
restored. The working tree was not touched.

### Proven VACUOUS

| # | Mutation | Test that should have caught it | Result |
|---|---|---|---|
| **M3** | a complete hand-written nearest-neighbour **re-pairing** function added to `workflow/measurement_import.py` (5633 → 6054 bytes) | `test_no_repair_is_attempted_anywhere_in_the_module` | **6 passed** |
| **M12** | both `_say_where_the_old_project_went` call sites deleted from `ui/ti2_loader.py` | — | **142 passed** |
| **M13** | both call sites deleted from `ui/txt_loader.py` | — | **142 passed** |
| **M17** | the Windows-reserved-names check disabled in `validate()` | — | **8254 passed, full everyday tier, exit 0** |
| **M18** | the leading-dot check disabled | — | (same run) |
| **M21** | the reserved check judges only the typed name, not `folder_name()` — the exact case the comment says the second clause exists for (`CON!` → folder `CON`) | — | **25 passed** |
| **M19** | the "You already have a project with this name" line never set | — | **25 passed** |
| **M20** | the folder-name preview never set | — | **25 passed** |
| **M22** | `clicked` → `toggled` on the row-numbers box (F6.1) | `test_row_numbers_follow_the_instrument.py` | **8303 passed, full everyday tier, exit 0** |

`test_no_repair_is_attempted_anywhere_in_the_module` greps the module for
`argmin`, `argsort`, `linear_sum_assignment` and `cdist`. It guards a
**vocabulary**, not a decision: a repair written in plain Python — which is how
anyone would write it in a module that imports neither numpy nor scipy — uses
none of those four words. Its own docstring says it *"Pins the DECISION, not just
today's behaviour"*; it pins neither.

`test_a_measurement_of_another_chart_is_refused_not_repaired` is **not** vacuous
(M2 kills it), but its docstring is wrong: *"A **shuffled** or foreign
measurement is refused."* `verify_patch_identity` pairs by `SAMPLE_ID`
(`paired_by: 'SAMPLE_ID'`, measured), so a row-shuffled file is still
`verified` and is filed. Only a foreign one is refused.

### Proven SOUND — mutation landed and was caught

M1 (drop the "more readings" refusal), M2 (drop the identity refusal),
M4 (`_chart_patch_count` always 0), M5 (`dir_holds` back to the parent-only
comparison), M6 (`old/` suffix removed), M7 (`shutil.rmtree` back in
`_copy_txt`), M8 (`forget_cached_project` call removed), M9 (`_discard_run`
guard removed), M10 (engine-partial unarchived), M11 (`_next_run_index` back to
manifest-only), M14 / M15 (`rmtree` back in `_copy_files` / `_copy_ti3_only`),
M16 (`subject=` dropped), M23 (no instrument follow), M24 (never stores `None`).

`tests/test_an_import_never_destroys_a_project.py` is the best file in the
change: eleven distinct mutations, eleven catches.

### Not tested at all

`TabProfile._offer_import_into_a_project` — 90 lines, four windows, one
`shutil.copy2` over somebody's measurement — has **no test of its own**, and no
test anywhere reaches it. So does `_say_the_replace_failed`'s whole-project
route, and every line of `name_prompt.validate` added in this change.

---

## F8 · BUGS AND REGRESSIONS

**1 — The import overwrites the measurement already in the destination run.**
`ui/tabs/tab_profile.py:4285`. *Repro:* copy `~/ChromIQ/Demo-Switching` to a
scratch working folder, set `current_run` to `run2` in `project.json`, open the
project, Build Profile → load control → any external `.ti3` of a 240-patch
chart → type `Demo-Switching` → Continue. `runs/run2/Demo-Switching.ti3` is
replaced; zero copies survive anywhere; the Trash is empty. Breaks §I.9
("a profiling run that already holds a measurement is not displaced") and
T2.6 ("nothing is ever deleted"). **Release-blocking.**

**2 — The import ignores the bar and files into `current_run`.**
`ui/tabs/tab_profile.py:4275`. *Repro:* same, manifest `current_run=run3`, set
the bar's Profile run to `run5`, import. The file lands in `run3`.

**3 — A partial is never identity-checked, so a foreign chart is filed as a partial.**
`workflow/measurement_import.py:79-83`. *Repro:* `current_run=run3` (399-patch
chart), import run1's 240-patch measurement. Filed, with "part of the chart was
not measured".

**4 — Cancel on the routing box opens a second name dialog when no project is open.**
`ui/tabs/tab_profile.py:4255`.

**5 — The name typed into the routing box is discarded; a second, empty box asks again.**
`ui/tabs/tab_profile.py:4257-4258` → `ui/ti2_loader.py:919 resolve_ti3`.

**6 — The routing question exists only for `.ti3`.** `ui/tabs/tab_profile.py:4332`.
`.mxf`, `.cxf` and `.txt` never see it. *Repro:* case C4 with the owner's own
`RGB_default-i1Pro.mxf`.

**7 — REGRESSION: `_discard_run`'s guard makes `duplicate_run`'s undo dead.**
`core/file_manager.py:2183`. A duplicate that fails mid-copy now always leaves a
half-copied run in the manifest and on disk. *Repro:* `probes/probe_safety2.py`
§2.6.

**8 — i18n: the bare-`.ti3` window is titled "Copy Chart Files" in every
non-English language.** `ui/ti2_loader.py:1250-1252`.

**9 — A failed rollback leaves the run with no chart and the window says
"Nothing was changed".** `workflow/verify_chart_snapshot.py:451-478` +
`ui/measurement_target_bar.py:1759`. Files land in a hidden
`.restore-stash-<name>/`.

**10 — The whole-project copy raises `OSError`, not `ReplaceFailed`, so its
failure is silent.** `workflow/chart_import.py:163`.

**11 — `M-IMPORT-REPLACED-KEPT` is missing from three of the six routes that
archive.** `ti2_loader.py:695`, `:1517`, `chart_import.py:163`.

**12 — `CHROMIQ_SETTINGS_FILE` does not cover `core/i18n.py:62`,** which reads
the real store directly. The doc claim is false.

**13 — The "already taken" line fires on the open project's own pre-filled name.**
`ui/tabs/tab_profile.py:4235-4240` vs `ui/tabs/tab_chart.py:9232-9239`.

**14 — A stray "Load Test Session" window after every successful import,**
offering to copy the project the person has just chosen.
`ui/tabs/tab_profile.py:4297` → `ui/tabs/tab_print.py:1341` → `resolve_ti2`.

**15 — A lone `.DS_Store` blocks `_discard_run`.** `core/file_manager.py:2180`.

**16 — Dead import.** `from core.file_manager import peek_project`,
`ui/tabs/tab_profile.py:4224`, never used.

**17 — The 120-**byte** cap reports itself as 120 **characters**.**
`ui/dialogs/name_prompt.py:109-111`.

---

## F9 · GAPS, OVERSIGHTS, MISSING OPTIONS, UI INCONSISTENCIES

1. **No run picker anywhere in the import.** §S4.7's picker ("Make the new
   chart in:", defaulting to *a new run*) was the design's answer and is not
   built. The person cannot see, let alone choose, where the file goes.
2. **`Project.duplicate_run(groups=…)` was never implemented,** so §I.9's whole
   "duplicate the chart, file into the copy" mechanism is absent.
3. **The window never names the destination.** Report 13 R8 asked for it
   specifically because Build Profile displays a *different* run's measurement
   from the one the bar has selected. The shipped window names neither run.
4. **`M-IMPORT-NO-WHITE` was not built,** so a partial with no white patch is
   filed, Build Profile arms, and `colprof` exits 1 with Argyll's raw
   `set_icxLuLut: can't handle test points without a white patch` — a string
   `_COLPROF_ERROR_PATTERNS` still has no entry for.
5. **A measurement with no device columns is filed unvalidated** on a profiling
   import (log line only). 2 521 of the 2 550 `.txt` files in the owner's own
   i1Profiler folder are of that shape, and they are all offered by the dialog's
   filter.
6. **Two name boxes for one act**, asking the same question in different words
   with different titles, different validation and different button labels
   ("Continue" vs "OK").
7. **Cancel means two different things** depending on whether a project is open.
8. **`Calibration.reset` still `shutil.rmtree`s `cal/exports/`** two lines after
   carefully archiving a `.ti3.engine-partial`. Regenerable, but the same method
   now holds both rules.
9. **`_ask_project_name` (whole-project copy) has no `dir_holds` guard,** the one
   copy of that question left un-unified.
10. **`RestoreResult` has no way to say the rollback failed,** so the UI cannot
    distinguish "nothing changed" from "the chart is in a hidden folder".
11. **The partial window understates the risk.** §I.10's own last paragraph
    records that `colprof` builds silently from 4 patches and reports 0.016 —
    its best number — for a profile 41.5 ΔE wrong. The shipped text says only
    *"a rougher profile"*. It also never states the proportion, which is what
    would make "2060 of 2064" read as suspicious rather than complete.
12. **`TabCheckRefine` still has no routing question** and, by its own new
    comment, no controller — so the same act has a door on one tab and not the
    other.

---

## F10 · WORDING THAT MISDESCRIBES WHAT IT DOES

1. **"Filed — and it is a partial measurement … part of the chart was not
   measured"** — said about a measurement of a different chart entirely (F1.2).
2. **"Type a new name and ChromIQ makes that project and puts the measurement in
   its first run"** — it does not; it opens a second, empty name box (F1.3).
3. **"Nothing was changed — the chart in this run is exactly as it was … nothing
   is lost"** — said when the run has no chart and the files are in a hidden
   dot-folder (F2.3).
4. **"That name is too long … shorten it to about 120 characters or fewer"** —
   the limit is 120 bytes; a 61-character name triggers it (F3.1).
5. **`measurement_import.py` module docstring: "It never re-pairs a measurement
   whose patch order does not match the chart. **It refuses it and says so.**"**
   A row-shuffled file is `verified` (pairing is by `SAMPLE_ID`) and is filed;
   a partial of a foreign chart is filed too. The refusal covers only a
   same-count foreign measurement.
6. **`test_a_measurement_of_another_chart_is_refused_not_repaired` docstring:
   "A **shuffled** or foreign measurement is refused."** Measured false.
7. **`test_a_failed_duplicate_does_not_discard_a_run_holding_work`** — no
   duplicate is run in it, failed or otherwise.
8. **`_discard_run`: "`_next_run_index` now refuses to hand out an occupied
   folder at all, so this should never fire."** It fires on every failed
   duplicate (F2.1).
9. **`_on_show_indicators`: "the 7.5 mm band is still reserved and paid for in
   patch area."** Measured `rlwi = 0.0` (F6.2).
10. **`core/settings.py` and CLAUDE.md: "the app physically cannot reach the real
    store."** `core/i18n.py:62` reaches it (F5.1).
11. **`name_prompt` docstring: the `exists` callback exists "so the dialog and
    the line under the main window's name box answer from one piece of code
    instead of two that drift."** The import passes a second, different
    implementation (F3.2).
12. **The comment above `exists_lbl`** in `name_prompt.py:192-203` is the
    folder-preview comment ("WHAT THE FOLDER WILL ACTUALLY BE CALLED…") sitting
    over the already-exists label, and it says the notice is in "Ordinary text
    colour, not the error red" — it is `SPEC_MAGENTA` (`#ff4573`), set three
    lines below by a comment that says the opposite.

---

## F11 · VERDICT

**No. This must not be tagged as beta 6.**

One release-blocking fault and five that would each be reported by the first
person to use the feature:

**Must change before any tag**

* **B1** — the import must not overwrite a run's existing measurement. Either
  build §I.9's `duplicate_run(groups=("chart",))` route or refuse; nothing
  in between is acceptable, and the current code does neither.
* **B2** — file into the bar's Profile run, or say in the window which run is
  being written to. Today it does neither and the two disagree.
* **B3** — run the identity check on a partial. One `if` in
  `workflow/measurement_import.py`.
* **B7** — restore `duplicate_run`'s undo. The guard must distinguish files this
  duplicate copied from files that were already there.
* **B8** — pass the subject as a token, not as a translated sentence to grep.
* **B5/B6** — either extend the routing question to `.mxf`/`.cxf`/`.txt` and
  carry the typed name through, or take the door out until it is whole. A door
  that appears for one file type out of four, discards what you typed, and does
  not cancel is worse than no door.

**Must change before the feature is called finished**

* **F1.5** — the three new windows to §M-PROPOSED, rendered from
  `workflow/measurement_messages.py`, with the method in `WINDOW_SOURCES`.
  §I.10 already names two of them; the app does not have them. Under CLAUDE.md
  this is not a style point: new user-facing text is not written into a tab
  until it is approved.
* **B9** — a `rollback_failed` field on `RestoreResult` and a window that says
  where the files are.
* **B10/B11** — the same exception type and the same notice on all six routes.
* **The vacuous tests** — M3, M12, M13, M17–M22. In particular
  `test_no_repair_is_attempted_anywhere_in_the_module` should assert on
  behaviour (feed it a shuffled and a foreign file and assert the verdicts),
  not grep for four library names.

**Safe to keep as it is**

The `core/file_manager.py` and `workflow/chart_import.py` data-safety work, the
three loader archive routes, the `open_project_manifest` split, the second-look
windows and their default buttons, the settings sandbox (with F5.1's claim
softened), and the row-number tri-state itself.

**On the gate.** 8424 passed / exit 0 is true and means very little here: the
release-blocking bug is in 90 lines with no test, and nine separate mutations of
the shipped code — including two that restore faults the source comments say
were found and fixed in this same session — leave the whole everyday tier green.

---

### Safety

* Settings sandboxed to `/tmp/knut-everything.ini` for every drive
  (`CHROMIQ_SETTINGS_FILE` set before any import).
* `defaults read com.chromiq.ChromIQ custom_output_path` → *does not exist*,
  unchanged. Full `defaults read` byte-identical before and after.
* `~/ChromIQ`: 1 058 files, SHA-256 inventory **identical** before and after.
  `~/ChromIQ/CR30-Test` never opened.
* `~/Desktop/i1Profiler`: no file modified.
* Working tree: `git status` and `git diff --stat` identical to the start of
  this run (32 files, 1 580 insertions, 288 deletions) apart from this report.
  Mutations were applied to `/tmp/knut-mutrepo` and `/tmp/knut-mut2`, never to
  the repository.
* Probe scripts in `/tmp/knut-everything-work/`, never in `scripts/`.

STATUS: complete

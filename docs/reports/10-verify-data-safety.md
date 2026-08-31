# End-to-end verification of the data-safety fixes

STATUS: complete

Round 5. Verifies the fixes made in response to
`docs/reports/09-the-three-rmtree-sites.md` (§Challenge). Adversarial: the goal
was to destroy a project through the app.

Proof: `~/Desktop/knut-datasafety/` (INDEX.md) — before/after listings with
SHA-256 for every destructive attempt, plus the modal windows as PNGs.

**Method.** The real `MainWindow`, the real tabs, the real dialogs, real
projects on disk. Automated: the OS file picker (a native modal a driver cannot
click) and the click on each modal window — every window is still BUILT by the
real code and its text is recorded verbatim before the click. No mock harness,
no re-implementation of anything under test.

**Safety, verified by value at the end.**

| check | result |
|---|---|
| `defaults read com.chromiq.ChromIQ custom_output_path` | *does not exist* — unset, as before |
| whole `com.chromiq.ChromIQ` domain, before vs after | **identical**, 391 lines |
| `~/ChromIQ` inventory, before vs after | **identical**, 1 395 entries |
| `~/ChromIQ/CR30-Test` modified since 09:30 | nothing |
| `~/Desktop/i1Profiler` modified since 09:30 | nothing |
| new items in `~/.Trash` | 0 |
| repo working tree | unchanged (`22 files changed, 600 insertions(+), 64 deletions(-)`, as at the start) |

Every driver set `CHROMIQ_SETTINGS_FILE` to a scratch `.ini` before anything
constructed `AppSettings`, and asserted on the resulting `fileName()` before
touching a widget. Mutation testing was done on an **rsync'd copy** of the tree
in the scratchpad, never in the repo.

---

## THE HEADLINE

**The three import routes are fixed and they hold.** I could not lose a byte
through any of them, including through the case that started all of this.

**A user can still lose work — through four other paths**, three of them
measured for the first time here, and one of those is created by the very
premise the `_discard_run` fix was written for. Separately, **the two new tests
that were supposed to pin the F1 fix and two of the three sites do not touch
them**: both mutations land, both stay green.

---

## A. Losing data through the real UI — `.txt`, `.ti2`, bare `.ti3`

Each route driven over a `Canon` holding a chart (`.ti1`/`.ti2`/page TIFF), a
measurement (`.ti3`), a profile (`.icc`), hand-taken averaging reads
(`reads/read1.ti3`), a quality report (`reports/report_1.json`) and a run
description in `meta.json`. Ten files.

| route | entry point | before → after | old/ archive | Trash |
|---|---|---|---|---|
| i1Profiler `.txt` | Build Profile ▸ Load measurement data | 10 → 14 | `old/2026-08-31_094313/` | empty |
| `.ti2` chart | Print ▸ Load chart | 10 → 15 | `old/2026-08-31_094400/` | empty |
| bare `.ti3` | Build Profile ▸ Load measurement data | 10 → 14 | `old/2026-08-31_094359/` | empty |

**Every one of the ten files is byte-identical in the archive.** The `.txt`
run, digest for digest (`A-txt/txt-before.json` vs the AFTER listing):

```
136d214497119e94  runs/run1/Canon.icc        →  old/2026-08-31_094313/runs/run1/Canon.icc
bb97092a28dd9d0b  runs/run1/Canon.ti3        →  old/2026-08-31_094313/runs/run1/Canon.ti3
91824cd7a3f17b3f  runs/run1/Canon_01.tif     →  old/2026-08-31_094313/runs/run1/Canon_01.tif
1efc9a0111e92e93  runs/run1/reads/read1.ti3  →  old/2026-08-31_094313/runs/run1/reads/read1.ti3
2184fa45bb040db5  runs/run1/reports/report_1.json → …/reports/report_1.json
38bce803ce76aec3  project.json               →  old/2026-08-31_094313/project.json
```

The archived manifest opens and reads as a project, and the archived
`meta.json` still carries the typed description
(`"description": "Knut's real run 1 — do not lose this"`). The `old/` folder
survives `Project.create` being run on the same folder afterwards, as the fix's
comment claims — measured, three times.

**A: PASS.** The earlier project is fully recoverable on all three routes.

---

## B. The project with a read-only sub-folder — the 2026-08-28 incident

This is what left 1 file of 6 with `project.json` gone while the app said
"Nothing was changed".

**B1 — read-only `runs/run1/reports/` (the incident's exact shape).**
`~/Desktop/knut-datasafety/B-readonly/`

```
files before: 10  files after: 14
CONTENT NOT RECOVERABLE ANYWHERE UNDER THE PROJECT: none
old/ archives: ['2026-08-31_094415']
  2026-08-31_094415: project.json=True
```

**The incident does not reproduce.** A top-level `shutil.move` is a rename; an
unwritable grandchild cannot defeat it. All ten files recovered, `project.json`
among them.

**B2 — read-only project ROOT.** `~/Desktop/knut-datasafety/B-readonly_root/`

```
!!! EXCEPTION ESCAPED THE SLOT: OSError … /work/Canon is not writable
files before: 10  files after: 10
old/ archives: []          new items in ~/.Trash: []
```

**Nothing half-written, nothing lost** — `os.access(…, W_OK)` is checked
before the first move (`workflow/chart_import.py:198-199`), and the destructive
call is still the first statement in `_copy_txt` that touches the destination,
so the abort happens before `Project.create`.

**But the user is told nothing at all.** See finding 5.

**B: PASS on data. FAIL on telling the user.**

---

## C. F1 — the source file inside the project being replaced

Driven through the real dialogs, at depth, with the source at
`<work>/Canon/runs/run1/…`.

| case | route | typed | what happened |
|---|---|---|---|
| `hand-made.txt` in run1 | Load Measurement ▸ *Use as base for a new profile* | `Canon` | "Overwrite existing folder" **never appears** |
| same | same | `canon` (case-different) | **never appears** |
| the project's own `Canon.ti2` | Load chart ▸ *Use as base for a new profile* | `Canon` | **never appears** |

All three: `files before: 10/11 → after: 10/11`, source still at its own path,
project untouched, nothing in `old/`, nothing in the Trash.

Clicking **OK** instead (`~/Desktop/knut-datasafety/H-f1_ok/`) refuses and keeps
the dialog open:

> *"That name points to the measurement's own folder. Pick a different name."*

**C: PASS.** `any(same_dir(dest, p) for p in path.parents)`
(`ui/txt_loader.py:222-226`, `ui/ti2_loader.py:1211-1215`) catches every
ancestor and folds case, as claimed.

One residual, unmeasured and narrow: `path.parents` walks the path **as given**.
A source reached through a symlink whose own components do not resolve into the
project (`/tmp/link/x.txt` → `<work>/Canon/runs/run1`) would not match. With the
`rmtree` gone this is no longer destructive — the archive moves the source into
`old/` and the import then fails on `shutil.copy2` — but it fails silently
(finding 5) and leaves an empty project behind.

---

## D. Replacing the project that is OPEN — **still broken, and now visible**

`~/Desktop/knut-datasafety/D-open_proj_bar/`. `Canon` with four runs, opened
through the real `MeasurementTargetController`, bar refreshed, then replaced by
an outside `.ti3` typed as `Canon`.

```
BAR BEFORE: ['Run 1 (overwrite)','Run 2 (overwrite)','Run 3 (overwrite)',
             'Run 4 (overwrite)','New run']   showing: Run 4 (overwrite)

=== WHAT THE USER NOW SEES IN THE BAR ===
profile-run combo lists: ['Run 1 (overwrite)','Run 2 (overwrite)',
                          'Run 3 (overwrite)','Run 4 (overwrite)','New run']
showing: Run 4 (overwrite)
runs ON DISK: ['run1']
project.json on disk: { … "current_run": "run1", "runs": ["run1"] }

=== ONE ORDINARY MANIFEST WRITE ===
the object the app still holds believes runs: ['run1','run2','run3','run4'] current: run4
project.json NOW: ['run1','run2','run3','run4'] run4
runs listed that DO NOT EXIST on disk: ['run2','run3','run4']
```

**Confirmed unfixed, and worse than the challenge measured** — the challenge
measured the cached object; this measures the **bar the person is looking at**.
After the replace it still offers Run 1 to Run 4 and still says Run 4 is
selected, while only `run1` exists. `peek_project` agrees with the bar and not
with the disk: `run_id='run4'`, `runs=(RunPeek(id='run1', …),)`.

`ui/tabs/tab_chart.py:9166` calls `self._file_mgr.forget_cached_project()` for
exactly this reason; none of the three import sites does.

**How bad now that the runs are in `old/` rather than gone:** materially better.
Nothing is destroyed — runs 2-4 are whole in `old/2026-08-31_095243/runs/`, and
a later write into a phantom `run4` would `mkdir` a fresh folder rather than
overwrite anything (`_next_run_index` reads the manifest, so a New run would be
`run5`). The damage is a **corrupted manifest and a lying bar**: the person is
invited to measure into a run that is not there, and the project's own record of
itself is wrong until something reloads it.

**D: still broken. Confirmed, not fixed, no longer destructive.**

---

## E. Two replaces inside one second, through the real UI

`~/Desktop/knut-datasafety/D-twice/` — two bare-`.ti3` imports over the same
`Canon`, both confirmed through the real windows.

```
elapsed for both replaces: 0.289 s
old/ archives: ['2026-08-31_095149', '2026-08-31_095149-2']
  2026-08-31_095149  : project.json=True
  2026-08-31_095149-2: project.json=True
```

Both archives whole, both manifests present, **no `runs/runs/run1` nesting**.

(The `.txt` route cannot do this — the second import is refused with `[BUSY]`
while `txt2ti3` from the first is still running, `ui/tabs/tab_profile.py:4293`.
The bare-`.ti3` route shells out to nothing and reproduces it in 0.289 s.)

**E: PASS.**

---

## F. `_discard_run` and `Calibration.reset`

**Neither is reachable by clicking.** `Project._discard_run` has exactly one
caller in the shipped tree — `core/file_manager.py:2087`, inside
`duplicate_run`'s `except OSError` — so it is reached only when a Duplicate-run
copy fails part way. `Calibration.reset` has one caller,
`workflow/chart_creator.py:625`, reached by generating a new calibration chart
for a calibration that already has one. Both verified directly:
`~/Desktop/knut-datasafety/F-discard-and-cal/`.

### `Calibration.reset` — the fix works

```
before: ['Cal-cal.cal','Cal-cal.ti1','Cal-cal.ti2','Cal-cal.ti3',
         'Cal-cal.ti3.engine-partial','Cal-cal_01.tif']
everything now under cal/: ['old/…/Cal-cal.cal','old/…/Cal-cal.ti3',
                            'old/…/Cal-cal.ti3.engine-partial']
the .engine-partial's CONTENT survives at: ['old/2026-08-31_095349/Cal-cal.ti3.engine-partial']
```

The interrupted measurement is archived, not unlinked. The name matches what
`workflow/measure_manager.py:733` actually writes (`ti3.name + ".engine-partial"`)
and what `Run.partial_ti3` (`core/file_manager.py:860`) answers with — checked,
not assumed.

The `.ti1`/`.ti2`/`_01.tif` still go without an archive, and that is
**deliberate**: `Calibration.reset`'s docstring records Knut's beta.148 ruling
(*"Only measurement ti3 files shall be copied to cal/old/…"*) and `chart/`
keeps the copy Restore Used Chart reads. Not a fault.

### `_discard_run` — the guard is far narrower than the hazard

`_keep` is `run.dir.glob("*")` filtered to `p.is_file()` and a suffix in
`Calibration.RESULT_SUFFIXES` (`.ti3 .cal .icc .icm`) or `.ti3.engine-partial`
(`core/file_manager.py:2142-2146`). `glob("*")` is not recursive and
`p.is_file()` drops every folder. Ten cases, measured:

| what the run held | verdict |
|---|---|
| a measurement + a profile (the case the fix was written for) | **KEPT** |
| the engine's partial measurement only | **KEPT** |
| a `.cal` (control) | **KEPT** |
| a PRINTED chart: `.ti1`/`.ti2`/page TIFF, not yet measured | **DESTROYED** |
| hand-taken averaging reads in `reads/` | **DESTROYED** |
| a verification chart + its measurement in `verifications/` | **DESTROYED** |
| a quality-check report in `reports/` | **DESTROYED** |
| an earlier archive the run made, in `old/` | **DESTROYED** |
| the run description the user typed (`meta.json`) | **DESTROYED** |
| an i1Profiler `.txt` not yet converted | **DESTROYED** |

Every destruction: `in the Trash: []`. Real ink on real paper (`_01.tif`,
`reads/`), a verification measurement, and a run's own `old/` archive — the one
thing the whole round is about keeping — are all outside the guard.

**F: `Calibration.reset` PASS. `_discard_run` PARTIAL — see finding 3.**

---

## G. Completeness — the inventory re-run against the current tree

Swept `core/`, `ui/`, `workflow/`, `main.py` for `shutil.rmtree`, `unlink`,
`os.remove/unlink/rmdir` and `shutil.move` onto a live path.

### The two the predecessor left as NEEDS-JUDGEMENT

**`ui/tabs/tab_chart.py:15266/15271` — SAFE.**
`_snapshot_profiling_chart` uses `shutil.copy2` (`:15251`), not `move`: the
originals never leave the run. And the verify build starts with
`reset_chart_artefacts()`, which archives the run's chart, measurement and
profile into `runs/runN/old/`. So even when `_restore_profiling_chart`'s move
loop fails part way and the `finally` at `:15271` destroys what is left of the
temp copy, the originals are in `old/`. Two independent backstops. Not a hazard.

**`workflow/verify_chart_snapshot.py:463/663` — SPLIT.**
Measured: `~/Desktop/knut-datasafety/G-restore-stash/`.

*Success path — deliberate, and the user is warned.* A restore replaces the
whole live chart; the displaced files are dropped:

```
live before: ['Canon.ti2','Canon_01.tif','Canon_02.tif','meta.json']
warning the app would show first — restore_would_lose_pages(): ['Canon_01.tif','Canon_02.tif']
live after : ['Canon.ti2','meta.json']
THE CHART THAT WAS ON SCREEN survives at: NOWHERE
```

`restore_would_lose_pages` (`:370`) exists precisely so the user decides, and
its docstring records Knut asking for it (#130, 2026-08-02). Whether this should
archive instead, under T2.6's *"nothing is ever deleted"*, is a design question
for the owner — **not a fault**.

*Rollback path — a real hole.* The docstrings promise *"Any failure puts
everything back as it was"* (`:400`, `:590`). Fault-injected — `copy2` raises,
then the second rollback `move` raises:

```
live after : ['Canon_02.tif','meta.json']
live page 1        survives at: NOWHERE
in the Trash: []          any old/ archive: none
restore_slot RAISED: OSError injected: the rollback could not put this one back
```

The rollback's own `shutil.move` is outside any `try`, so its exception escapes
the `except OSError` block — and the `finally: shutil.rmtree(stash,
ignore_errors=True)` still fires, destroying every displaced file the rollback
had not yet put back. **Two of three live chart files gone, nothing anywhere.**
Same shape at both `:463` and `:663`. Pre-existing; not introduced here.

### Nothing destructive was introduced by this change

The diff's five edits all move in the safe direction. `_archive_project_contents`
now takes `mkdir(exist_ok=False)` — a losing race raises `FileExistsError`
(an `OSError`), which aborts rather than merges. The `_discard_run` guard's early
`return` leaves the manifest listing the kept run and `current_run` pointing at
it, so a failed duplicate silently adopts a stranger's folder as the project's
current run; the user does see the failure (`ui/measurement_target_bar.py:1874-1875`
shows a warning), just not that.

### A path the fix's own premise creates and does not close

See finding 2.

---

## H. What the user is TOLD

Every string below is as captured on screen, verbatim.

**The button, and the line under the name box.** Both loaders now say the same
thing, and both are wrong:

| site | text |
|---|---|
| `ui/txt_loader.py:197`, `ui/ti2_loader.py:1184` | button **"Overwrite existing folder"** |
| `ui/txt_loader.py:252`, `ui/ti2_loader.py:1240` | *"“Canon” already exists. Click “Overwrite existing folder” to replace it."* |

**The confirmation window** (`ui/txt_loader.py:301-304`,
`ui/ti2_loader.py:1289-1292`), captured on all six replace runs:

> **Overwrite existing folder?**
> This will permanently delete:
>
>     /…/work/Canon
>
> and replace it with the imported measurement. Continue?

Nothing is permanently deleted any more. The window that asks for consent
describes the opposite of what the code does.

**The inconsistency the report complained about has moved, not gone.** Inside
`ui/ti2_loader.py` alone, two windows now ask the same question about the same
act:

- `:870` / `:893-894` — button **"Replace existing"**, body *"…or Replace it
  (the existing one is moved to its own old/ folder)"* — accurate.
- `:1184` / `:1289` — button **"Overwrite existing folder"**, body *"This will
  permanently delete"* — inaccurate.

Which one a person gets is decided by which file type they happened to load.

**Nobody is ever told where the old project went.** `_archive_project_contents`
writes no log line, and neither loader logs or displays the returned path. Not
in the confirmation window, not afterwards, not in the tab's log panel, not in
`chromiq.log`. The person is told their project will be *permanently deleted*,
it is in fact archived, and nothing anywhere says so or where — compare
M-PROJECT-REPLACE-CONFIRM, which promises *"That 'old' folder stays inside the
project, so you can open it at any time"*.

**The bare `.ti3` route says "chart files".** `_handle_outside_ti3_only`
(`ui/ti2_loader.py:1394`) reuses `_ask_profile_name`, so importing a
measurement asks *"and replace it with the imported **chart files**"* — measured
in `A-ti3` and `D-open_proj_bar`.

**The self-collision refusal is now inaccurate.** `ui/txt_loader.py:274` /
`:289` and `ui/ti2_loader.py:1262` / `:1277` still say *"the measurement's own
folder"* / *"the chart's own folder"*. With the guard fixed the name points at
an **ancestor** of that folder — the project the file lives inside — which is a
different sentence.

Routing these through §S4.7 is approved but unbuilt, so all of the above are
reported as findings, not regressions.

---

## The tests

`tests/test_an_import_never_destroys_a_project.py` — 7 passed in 0.33 s.
Mutation-tested on an rsync'd copy of the tree
(`scratchpad/mut/`), never in the repo. Every mutation proven to be on disk
before the run.

**Mutation A — revert the F1 guard in BOTH loaders** to
`(working_dir / name).resolve() == path.parent.resolve()`:

```
ui/txt_loader.py occurrences replaced: 1
ui/ti2_loader.py occurrences replaced: 1
ui/txt_loader.py:227:  return (working_dir / name).resolve() == txt_path.parent.resolve()
ui/ti2_loader.py:1214: return (working_dir / name).resolve() == ti2_path.parent.resolve()
→ 7 passed          (+ test_txt_loader.py + test_ti2_loader.py: 75 passed)
```

**Mutation B — put `shutil.rmtree(dest)` back at BOTH `ui/ti2_loader.py` sites**:

```
ti2_loader archive call sites found: 2
ui/ti2_loader.py:1347: shutil.rmtree(dest)
ui/ti2_loader.py:1430: shutil.rmtree(dest)
→ 7 passed
→ every test file that names these functions
  (test_ti2_loader_model, test_ti2_loader, test_txt_loader,
   test_an_import_never_destroys_a_project, test_chart_import): 100 passed
```

See findings 6 and 7.

---

# VERDICT

**Can a user still lose work through any of these paths? — YES, but not
through the three import routes.**

Those three are fixed and hold under every attack I could construct: an
outside `.txt`, `.ti2` and bare `.ti3` over a full project (all recoverable,
byte-identical), the read-only sub-folder that started this (does not
reproduce), the read-only root (clean abort, nothing written), the source file
inside the destination at depth and in a different case (refused, both loaders,
both file types), and two replaces inside one second (two archives, no
nesting). Nothing reached the Trash and nothing was lost.

## Still wrong

1. **F4 — the cached `Project` is never dropped, and now the bar shows it.**
   `ui/txt_loader.py:361`, `ui/ti2_loader.py:1351`, `ui/ti2_loader.py:1435` —
   none calls `forget_cached_project()`, which `ui/tabs/tab_chart.py:9166` calls
   for the same act. Measured through the real bar: after replacing an open
   4-run `Canon`, the Profile-run combo still lists `Run 1 … Run 4` and still
   shows `Run 4` while `runs ON DISK: ['run1']`, and one ordinary manifest write
   puts `['run1','run2','run3','run4'] / run4` back on disk. Not destructive now
   that the runs are in `old/`, but the project's record of itself is wrong and
   the person is invited to measure into a run that does not exist.
   *(Known unfixed; the brief asked me to confirm. Confirmed.)*

2. **`duplicate_run` destroys an unlisted run's work — the new guard protects
   the undo, not the act.** `core/file_manager.py:2073-2078` copies into
   `new_run()`'s folder, which `_next_run_index` (`:2154-2160`) allocates from
   the **manifest** while `ensure_dir()` is `exist_ok=True` — the exact premise
   the `_discard_run` comment states. On the **success** path `_discard_run` is
   never called, so nothing guards it. Measured
   (`~/Desktop/knut-datasafety/G-duplicate-clobber/`) on a manifest that has
   lost `run2` while the folder is still there:
   ```
   manifest lists: ['run1'] | runs ON DISK: ['run1','run2']
   run2's measurement reads: CTI3 RUN 2'S IRREPLACEABLE MEASUREMENT
   >>> Duplicate run 1
   duplicate_run returned: run2 -> folder run2
   its .ti3 now reads: CTI3 run1 measurement
   RUN 2'S MEASUREMENT survives anywhere under the project: NOWHERE
   RUN 2'S PROFILE survives anywhere: NOWHERE
   run 2's description now: (empty)
   in the Trash: []   old/ archives anywhere: []
   ```
   A stranger's measurement, profile, chart and typed description, gone, from
   the bar's Duplicate button, with the operation reporting success.

3. **`_discard_run`'s guard is a top-level suffix filter, and most of a run is
   neither.** `core/file_manager.py:2142-2146`: `run.dir.glob("*")` is not
   recursive and `p.is_file()` drops every folder. Measured destroyed, with
   nothing in the Trash: a printed but unmeasured chart (`.ti1`/`.ti2`/`_01.tif`
   — real ink), `reads/` (hand-taken averaging reads), `verifications/`,
   `reports/`, the run's own `old/` archive, `meta.json` (the description
   `per_run_description.md` governs), and an unconverted `.txt`. Compare
   `Run.reset_chart_artefacts`, which archives `reads/` (`:1317`) and names
   `partial_ti3` explicitly. The rule this needs is "the folder is empty of
   everything but `meta.json` a moment old", not a suffix list.

4. **`verify_chart_snapshot`'s rollback can destroy the live chart it exists to
   protect.** `workflow/verify_chart_snapshot.py:451-455` and `:648-652` — the
   rollback's `shutil.move` is outside any `try`, so its failure escapes the
   `except OSError` while `finally: shutil.rmtree(stash, ignore_errors=True)`
   (`:463`, `:663`) still fires. Fault-injected: of three displaced live chart
   files, one restored, **two destroyed, nothing in the Trash, no archive**, and
   the exception escapes `restore_slot` to a caller that expects a
   `RestoreResult`. Both docstrings promise *"Any failure puts everything back
   as it was"*. Pre-existing.

5. **F2 — the abort is completely silent.** Measured through a real
   `QPushButton` wired to the real slot, with `main.py`'s excepthook installed
   (`~/Desktop/knut-datasafety/H-told/`): after the user clicks *Yes* on
   "This will permanently delete…",
   ```
   WINDOWS the user saw after the confirm: NONE
   MESSAGE BOXES after the confirm: NONE
   Build Profile tab log panel says: ''
   the app is still alive: True
   ```
   The only trace is a `CRITICAL` traceback in `chromiq.log`
   (`OSError: … /work/Canon is not writable`). The app looks idle and the import
   never happened. `ui/tabs/tab_profile.py:4298` calls `resolve_txt` bare and the
   three `_copy_*` functions still take no parent widget.
   *(Known unfixed. It is no longer the 2026-08-28 incident — nothing is
   destroyed — but it is still that incident's silence.)*

6. **The test that is supposed to pin the F1 fix never enters it.**
   `tests/test_an_import_never_destroys_a_project.py:52-64` imports
   `core.file_manager.same_dir` and re-implements the guard's expression
   (`any(same_dir(work / name, p) for p in src.parents)`). It never imports
   `ui.txt_loader` or `ui.ti2_loader`, so it cannot fail when their guards
   change. **Mutation proven to land**, both loaders reverted to
   `.resolve() ==`: `7 passed`, and `75 passed` with both loader suites added.
   A fake that re-implements the code validates itself.

7. **Two of the three sites have no test at all.**
   `test_the_txt_import_route_itself_archives` (`:104`) drives
   `ui.txt_loader._copy_txt` only. `ui/ti2_loader.py::_copy_files` (`:1332`) and
   `::_copy_ti3_only` (`:1416`) are entered by nothing. **Mutation proven to
   land**, `shutil.rmtree(dest)` restored at both: `7 passed`, and `100 passed`
   across every test file in the suite that names these functions.

8. **The wording now contradicts the behaviour, on both loaders.** The button
   says "Overwrite existing folder"; the confirmation says "This will
   permanently delete"; nothing is deleted. `ui/txt_loader.py:197/252/301-304`,
   `ui/ti2_loader.py:1184/1240/1289-1292`. Two windows in `ui/ti2_loader.py`
   now perform the identical act with opposite words (`:870`/`:893` says
   "Replace existing … moved to its own old/ folder"). The bare-`.ti3` route
   says "chart files" for a measurement (`:1394` reusing `_ask_profile_name`).
   The self-collision refusals still say "the measurement's own folder" when the
   guard now means an ancestor of it (`ui/txt_loader.py:274/289`,
   `ui/ti2_loader.py:1262/1277`).

9. **Nothing records where the old project went.** `_archive_project_contents`
   (`workflow/chart_import.py:176-217`) logs nothing on success and neither
   caller logs or shows its return value. No window, no tab log, no
   `chromiq.log` line. The promise M-PROJECT-REPLACE-CONFIRM makes — *"that
   'old' folder stays inside the project, so you can open it at any time"* — is
   the one thing the person is never told.

## Verified correct, for the record

- `_archive_project_contents`'s same-second suffixing, through the real UI
  (two archives, `-2`, no nesting) — and its all-or-nothing pre-flight, which
  aborts a read-only root before moving anything.
- `Calibration.reset` archives `<stem>.ti3.engine-partial`; the name matches
  what `measure_manager` writes and what `Run.partial_ti3` answers with. Its
  removal of `.ti1`/`.ti2`/`_01.tif` is Knut's beta.148 ruling, not a fault.
- `ui/tabs/tab_chart.py:15266/15271` — safe: the snapshot is a `copy2`, and
  `reset_chart_artefacts` has already archived the originals to `old/`.
- The diff introduces no new destructive path.

STATUS: complete

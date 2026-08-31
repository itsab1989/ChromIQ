# End-to-end challenge: the import, the project picker and the run picker

**STATUS: complete.** Round 15, 2026-08-31. Base: everything uncommitted on
top of `bd463b94` (v4.1.5-beta.5). **No source file is changed by this run.**

Every previous round in this session found the fault in the FIX rather than in
the original bug. This plan is written on that assumption: each of the seven
things "new since report 14" is treated as a suspect, not as a resolution.

---

## THE TEST PLAN (written before any execution)

### Phase 0 — read the change as code, not as its own commentary
0.1 Read every hunk of `git diff` plus the three untracked new files
    (`workflow/measurement_import.py`, `ui/dialogs/project_picker.py`, the new
    tests). Note every early return, every `except Exception`, and every place
    an order-of-operations question exists (does state change before the
    verdict?).
0.2 List every call site of the new entry point and prove which file types
    reach it.

### Phase 1 — the journey on screen (attack A)
Real app, real event loop, real project trees copied out of `~/ChromIQ` into a
scratch working folder. For each case: bar run type + run, "Location being
edited", the tab standing on, the file that actually landed, and a screenshot.
* C1 no project open, working folder empty
* C2 no project open, working folder holds projects
* C3 project open, picker cancelled
* C4 "Make a new project instead"
* C5 chosen project whose chosen run already holds a measurement
* C6 chosen run that is new (the default)
* C7 project with one run; project with five runs
* C8 the same file imported twice in a row
* C9 a project last left on Verification (the run-type fix)

### Phase 2 — the other three file types (attack B)
`.mxf`, `.cxf`, `.txt` against the owner's real files in `~/Desktop/i1Profiler`
(read only, hashed before and after). Does an i1Profiler user reach the feature
at all?

### Phase 3 — the project picker (attack C)
none / 1 / 17 / 200 projects; corrupt `project.json`; a project one level
deeper; double-click; keyboard only; Escape; two names that collide once
elided; a name that is not a project folder; unreadable folder.

### Phase 4 — the run picker (attack D)
Calibration target; verification run; runs deleted on disk but still in the
manifest; a run id the picker offers that no longer resolves.

### Phase 5 — data safety (attack E)
SHA-256 inventory of the whole scratch tree before and after every path.
Deliberately try to orphan, half-write or destroy: refuse after a duplicate,
cancel after a new run, two imports racing the same run.

### Phase 6 — vacuity (attack F)
Mutate the shipped code; prove each mutation lands (source identity changes);
run the targeted tests. Specifically the import's own tests,
`test_no_repair_is_attempted_anywhere_in_the_module`, and the pickers.

### Phase 7 — wording and the catalogue (attack G)
Every new window's exact text, screenshotted, against §M and the house rules
(friendly, count-aware, no "(s)", no Markdown, no code words).

### Phase 8 — report 14's still-open items (attack H)

### Phase 9 — screenshots + INDEX.md into `~/Desktop/knut-import-live/`

---

## SKELETON (filled in as each phase completes)

* G0 — verdict up front
* G1 — what the code says before it is run (Phase 0)
* G2 — the journey on screen
* G3 — .mxf / .cxf / .txt
* G4 — the project picker
* G5 — the run picker
* G6 — data safety
* G7 — vacuous tests
* G8 — wording
* G9 — report 14's still-open items
* G10 — BUGS
* G11 — GAPS
* G12 — WORDING
* G13 — VACUOUS TESTS
* G14 — VERDICT

---

## G0 · Verdict up front

**Not safe to tag beta 6.**

The seven things listed as new since report 14 divide cleanly:

* **Sound and proved sound by mutation:** `duplicate_run(groups=…)` (item 1's
  mechanism), `_discard_run(just_created=True)` (item 3), the partial identity
  check (item 2). Each has a test that fails when I revert it.
* **Present in the code and UNREACHABLE in the shipped app:** everything item 1
  is *for* — the "Make a new run" offer, the partial notice, the "different
  chart" refusal, the whole of `workflow/measurement_import.assess`.
* **Broken:** item 6, "the run is chosen, not inherited". The choice is
  discarded, and the line that would have used it calls a method that does not
  exist.

The mechanism is one omission. `_file_into_project` builds §S4.7's run picker
and never connects its `currentIndexChanged`, so the answer it reads is the one
captured when the window was built — **always "a new run"**. A new run has no
chart. `assess()` is therefore always handed a `chart_ti2` that does not exist,
returns `n_chart = 0` and `checked: False`, and **files whatever it is given**.
I put a six-patch file bearing no relation to anything into the owner's
`Demo-Switching` copy and ChromIQ filed it without a single word.

And behind that: `run = next((r for r in proj.runs() if r.id == want), None)`
— `Project` has `all_runs()`, not `runs()`. Fixing the picker without fixing
that line turns a silent wrong answer into an `AttributeError` on every
non-default choice.

Separately, and independent of all of the above: **the door opens for files
that are already filed.** The gate asks `peek_project(p.parent).exists`, and a
run's measurement lives at `<project>/runs/runN/`, whose parent holds no
`project.json`. So loading a run's own `.ti3` now asks "Where should this
measurement go?", and answering it copies the file into another project under
that project's name. Answering Cancel loads nothing at all.

Nothing in any of this is caught by a test. With
`_offer_import_into_a_project` returning `False` on its first line **and**
`choose_project` returning `None` on its first line — the entire feature
switched off — the everyday tier is **8258 passed, 311 skipped, 3 xfailed,
exit 0**, byte-for-byte the same result as the unmutated tree.

**On styling:** an earlier pass of this report found the picker's buttons
unstyled and mis-ordered. That was my harness, which did not call
`apply_appearance`. **Withdrawn.** With the theme applied as `main.py:190`
applies it, every window in this flow is correctly styled, Cancel is hard
right, and nothing is clipped. `order=` is passed at exactly six call sites,
all of them inside this change, so the `spread_message_box_buttons` fix cannot
have disturbed any other window in the app.

---

## G1 · What the code says before it is run

Read hunk by hunk, looking for early returns, swallowed exceptions and
order-of-operations. Five things stood out before a single window was opened,
and all five were confirmed on screen:

1. `_file_into_project` connects nothing to the picker (`tab_profile.py:4328`
   ff.) while `tab_chart.py:8874` — the same picker, five hundred lines away —
   connects `_on_pick`.
2. `proj.runs()` (`:4352`) is not a method of `Project`.
3. `assess()` (`:4425`) runs **after** `new_run()` / `duplicate_run()` and
   after `ctl.set_profile_run()`, so a refusal cannot honour its own promise.
4. The `.ti3` gate (`:4485`) checks one folder level where every other
   comparable check in `ui/ti2_loader.py` walks ancestors.
5. `choose_project` is called without `accent=` (`:4259`), so
   `tint_dialog_primary` never runs for it — cosmetic only, and invisible
   because the `#primary` QSS carries the tint anyway.

Three dead imports remain in `_offer_import_into_a_project`: `QMessageBox`,
`peek_project` and `assess` are imported at `:4224-4227` and none is used in
that method. `peek_project as _peek` is imported twice inside
`_file_into_project` (`:4291` and `:4316`).

---

## G2 · The journey on screen

Twelve runs of the real app. Working folder: copies of `Demo-Switching`
(5 runs, measurements in runs 1 and 2, a profile in run 2, a calibration),
`Demo-Prefs-Speed` (3 runs) and `ChromIQ-Test-Chart` (1 run).
Screenshots: `~/Desktop/knut-import-live/`.

| Case | What happened | Where the file landed |
|---|---|---|
| C1 empty working folder | picker skipped, name box, **pre-filled with `Printer_Paper_Type_Instr_2026-08-31_21-42`** | Cancel → nothing |
| C2 projects present, "a new run" | picker → run picker → filed | a brand-new run, no chart |
| C3 picker cancelled / Escape | aborts cleanly, nothing written | — |
| C4 "Make a new project instead" | name box → **a second, empty name box** | `Fresh-Import-Project/runs/run1/` — but the bar still says the invented name |
| C5 **Run 2 chosen** (holds a measurement) | no §I.9 window at all | **run 6** — the choice was discarded |
| C6 the default | as C2 | a new run |
| C7 1 run / 5 runs | identical behaviour | a new run |
| C8 the same file twice | two new runs, run6 and run7 | never a word about the duplicate |
| C9 project last left on Verification | not reproducible in a fresh sandbox; the code path is real — see B2 | — |

**"Location being edited" and the bar** follow the import correctly on the
picker route (`work/Demo-Switching/runs/run6/`). They do **not** on the
"Make a new project instead" route: measured `target_name =
Printer_Paper_Type_Instr_2026-08-31_21-37`, `location_being_edited =
work/Printer_Paper_Type_Instr_2026-08-31_21-37/runs/run1/` — a folder that
does not exist — while the tab shows
`work/Fresh-Import-Project/runs/run1/Fresh-Import-Project.ti3`.

**Nothing is written to the tab's log.** The Measure tab's IMPORT module writes
four log lines; this one writes none, and the filed copy carries no record of
where it came from — no keyword, no sidecar, no line anywhere.

---

## G3 · `.mxf`, `.cxf`, `.txt` — can an i1Profiler user reach this at all?

**No. Plainly no.**

`_on_load_ti3` (`ui/tabs/tab_profile.py:4473-4487`) routes by suffix *before*
the new gate:

```
if p.suffix.lower() in (".mxf", ".cxf"):  self._import_i1profiler_cxf(p); 
elif p.suffix.lower() == ".txt":          self._import_i1profiler_txt(p); 
else:                                     <the new gate>
```

Driven with the owner's own files (`~/Desktop/i1Profiler`, read only, SHA-256
verified unchanged afterwards):

* `ColorSpaceRGB/Measurements/RGB_default-i1Pro.mxf` → exactly one window, the
  old one: *"The following files from **chromiq_cxf_unylsupl/** will be copied
  into your working folder as a new profile set"*. That is a **temporary
  directory name shown to the user**, and it is not the file they chose.
* `ColorSpaceRGB/TestCharts/TC2.txt` → *"The i1Profiler measurement **TC2.txt**
  will be copied into your working folder as a new profile set"*.

So the population the feature was justified for — `ui/dialogs/tools_dialogs.py:1324`
says in as many words *"Measured your chart in X-Rite's i1Profiler? This brings
those readings back into ChromIQ"* — cannot reach it. Report 14's bug 6 is
unchanged.

---

## G4 · The project picker

Built a working folder with 203 projects, a corrupt manifest, a project one
level deeper, a folder that is not a project, and two 68/71-character names.

* **203 projects**: listed in 0.03 s. Twelve rows, and a **thirteenth sliced in
  half** at the bottom edge (`_frame = 2 * lst.frameWidth() + 4` under-counts).
  No search, no filter, no type-to-jump affordance.
* **None**: `choose_project` returns `None`, `list_projects` is empty, so the
  caller falls through to the name box. Correct.
* **Corrupt `project.json`**: listed, and its row reads **"empty"**.
  `peek_project` deliberately returns `chart=True` for an unreadable manifest —
  its own comment says *"the honest answer is 'something is here' rather than
  'nothing is here'"* — and `_holds_phrase` never looks at `chart`, so the one
  project you must not treat as empty is the one described that way.
* **What a row says is the LAST-USED RUN, not the project.** `Demo-Switching`
  holds measurements in runs 1 and 2 and a profile in run 2; its row says
  "5 runs, a calibration", because `peek_project` reports `measurement` /
  `profile` for `current_run` only. A chart is never mentioned at all.
* **A project in a sub-folder is unreachable.** `list_projects` reads one level
  by design, and its docstring says *"Anything deeper is still reachable by
  typing its name"* — **false**. `FileManager.resolved_root_for_name
  ("Nested-Project")` returned `<work>/Nested-Project`, which does not exist,
  so `_exists()` is False, the import treats it as a new project and creates a
  **second, empty project of the same name** beside the real one. Meanwhile
  `open_project_manifest` (`tab_chart.py:5939`) and
  `ti2_loader._project_root_for` both support nested projects explicitly.
* **Escape** rejects, `choose_project` returns None, and because
  `list_projects(...)` is non-empty the caller returns True — the import stops
  and nothing is written. Correct, but note `list_projects` is walked a second
  time to decide that (`:4266`).
* **Double-click** accepts the row. Works.
* **Elision**: the two Red River names elide to
  `Red-River-Paper-ColorMunki-_-Letter-2052…pages-Standard-Patch-Set-v25` and
  stay distinguishable, because what differs is near the front. Two names
  differing only in the true middle would not be.
* **Layout**: with two or three projects the box is still drawn twelve rows
  tall, so most of the window is empty.

---

## G5 · The run picker

**It does not work.** `_build_run_picker` returns `(picker, [picker.currentData()
or ""])` — a snapshot. §S4.7 connects `currentIndexChanged` to write into that
list (`tab_chart.py:8874-8880`); the import does not. Screenshot 05 shows
"Run 2" selected at the instant "File it here" is pressed; screenshot 06 shows
the bar on **Run 6**.

Consequences measured:

* the §I.9 "That run already has a measurement" window **can never appear**;
* `verdict.partial` can never be true, so §I.10's notice can never appear;
* `assess` can never refuse, because it is never given a chart;
* `duplicate_run(groups=("chart",))` — the mechanism this whole round was
  built around — is **never called from the UI**.

**Behind it, a crash.** `proj.runs()` (`:4352`) does not exist:

```
>>> Project.load(Path('…/Demo-Switching')).runs()
AttributeError: 'Project' object has no attribute 'runs'
>>> [r.id for r in _.all_runs()]
['run1','run2','run3','run4','run5']
```

That line executes whenever `chosen[0]` is non-empty. It is non-empty **today**
whenever `_is_verification_target()` is true at the moment the picker is built
(`tab_chart.py:8948-8956` defaults to `peek.run_id` there) — and the picker is
built *before* the code sets the run type to profiling (`:4418` vs `:4325`), so
the fix for item 7 is applied too late to protect it.

**Calibration**: unreachable from this door — `_on_load_ti3` sends a
calibration target to `_pc_browse_ti3()` first (`:4461`). But if it were ever
reached, `_build_run_picker` returns `(None, [peek.run_id])`, no window is
shown at all, and the file is filed into `proj.current_run()` in silence.
The same silent path is taken whenever `_build_run_picker` raises, which
`:4326` swallows with a bare `except Exception`.

**Runs deleted on disk but still in the manifest**: harmless — `_next_run_index`
skips occupied folders and `new_run()` allocates the next free number.

---

## G6 · Data safety

Every path below was run on a copy of the owner's projects, with a full
`find -type f` diff before and after.

**Nothing was ever destroyed or overwritten.** Every import created new files
only; `duplicate_run(("chart",))` left run 2 byte-identical; the source file's
SHA-256 was unchanged every time; `~/ChromIQ` is byte-identical (1 058 files).

**But three things are orphaned or mis-stated:**

1. **A refusal leaves a run behind and says it did not.** Import
   `foreign-50.ti3` into an occupied run, accept "Make a new run", and the
   refusal window says *"ChromIQ did not file it, and nothing has been
   changed."* The tree afterwards:

   ```
   > runs/run6/Demo-Switching.ti1   .ti2   .channels.json
   > runs/run6/Demo-Switching_01.tif  _02.tif  _03.tif
   > runs/run6/meta.json
   ```

   plus `current_run: run6`, `runs: [… run6]`, and the bar pointing at it.

2. **Every ordinary import creates a chartless run.** A run holding a
   measurement and nothing else cannot be paired with anything: the measurement
   report finds its chart by the run's stem, and there is none.

3. **An unwritable destination crashes out of the click handler.** `chmod 555`
   on `<project>/runs`, then import:

   ```
   File "ui/tabs/tab_profile.py", line 4356, in _file_into_project
     run = proj.new_run() if want == "" and picker is not None \
   PermissionError: [Errno 13] Permission denied: '…/runs/run2'
   ```

   No window, no log line. `shutil.copy2` and `duplicate_run` at `:4434` and `:4401` are equally unguarded.


---

## G7 · Which of the new tests are vacuous

All mutations were applied to a **copy** of the repository at
`/tmp/knut15/mutrepo` (rsync, `.venv` symlinked); the working tree was never
edited. Every mutation was proven to land — by the file's changed size, by
importing the mutated symbol, or by a different test failing.

### Proven SOUND (the mutation lands and a test catches it)

| Mutation | Caught by |
|---|---|
| `_discard_run(new_run, just_created=True)` → `_discard_run(new_run)` | `test_a_failed_duplicate_is_still_undone` FAILED |
| the `groups` filter removed from `duplicate_run_plan` | `test_duplicating_for_an_import_copies_the_chart_only` FAILED |
| the partial's identity check reverted to an early return | `test_a_partial_is_still_checked_against_the_chart` FAILED |

So items 1, 2 and 3 of "what is new" are genuinely guarded **at the level of
the helper**. Nothing guards them at the level of the app.

### Proven VACUOUS

**`test_no_repair_is_attempted_anywhere_in_the_module`** — report 14 said this
and it is unchanged. Its docstring claims *"If someone adds a repair later,
this fails and they must re-read §I.9."* I added a **working greedy re-pairing
function** to the module:

```python
def _repair_by_device_values(measured, chart_rows):
    out = []
    for want in chart_rows:
        best = best_d = None
        for row in measured:
            d = sum((a - b) ** 2 for a, b in zip(want, row))
            if best_d is None or d < best_d:
                best, best_d = row, d
        out.append(best)
    return out
```

Proven to land (file 6 046 → 6 627 bytes) and proven to work:

```
>>> _repair_by_device_values([(0,0,0),(100,100,100)], [(99,99,99),(1,1,1)])
[(100, 100, 100), (0, 0, 0)]
```

```
tests/test_measurement_import.py  ........   8 passed
```

The test greps for four library names. A repair written in plain Python passes
it. It should assert on behaviour — feed `assess` a shuffled file and a foreign
file and pin the verdicts — which the other tests already do; as written it
adds nothing.

### Not tested at all — proven by switching the whole feature off

`_offer_import_into_a_project` made to `return False` on its first line, and
`choose_project` made to `return None` on its first line. Both proven to land
(the mutated `tab_profile` module resolves to the copy; the marker string is in
`__file__`).

```
mutated:    8258 passed, 311 skipped, 3 xfailed in 86.18s   exit 0
unmutated:  8258 passed, 311 skipped, 3 xfailed in 84.65s
```

**Identical.** With the entire feature — the project picker, the run picker,
`_file_into_project`, the §I.9 offer, the partial notice, the refusal — removed
from the running app, not one test anywhere notices. Confirmed by inspection:
`tests/test_measurement_import.py` tests only the pure `assess()` helper, and
neither `ui/dialogs/project_picker.py` nor `_offer_import_into_a_project` nor
`_file_into_project` is named in any test file in the repository.

An earlier, narrower mutation — deleting only the run picker
(`picker = None` before the window is built) — likewise left 122 selected
tests green.

---

## G8 · Wording, and what is not in §M

### Not in the catalogue at all

Four new user-facing windows write their own prose in the tab:

| Window | Where |
|---|---|
| "Where should this measurement go?" (the project list) | `ui/dialogs/project_picker.py:98` — a **module-level function** |
| "Where should the measurement go?" (the run picker) | `ui/tabs/tab_profile.py:4328` |
| "That run already has a measurement" | `ui/tabs/tab_profile.py:4374` |
| "Filed — and it is a partial measurement" / "This measurement does not belong to that chart" | `ui/tabs/tab_profile.py:4426`, `:4436` |

None is in `WINDOW_SOURCES`, and none is in `UNCATALOGUED_MEASUREMENT_WINDOWS`
either — so the debt is not even recorded. `test_message_catalogue.py` is
green. CLAUDE.md: *"New user-facing message text is governed by §M … it goes to
§M-PROPOSED first and is not written into a tab until it is approved."*

**`WINDOW_SOURCES` cannot express any of the first, third or fourth.** It is a
list of `(module, class, method)` triples resolved with
`getattr(getattr(mod, cls), method)` (`tests/test_message_catalogue.py:354`),
so a module-level function — `project_picker.choose_project`,
`ti2_loader._say_where_the_old_project_went`, `txt_loader._say_the_replace_failed`
— has no way to be listed. That is a structural gap, not an oversight in this
change, and it should be said plainly in the file.

Meanwhile §I.10 of the design **names two messages that do not exist**:
`M-IMPORT-PARTIAL-PROFILING`, `M-IMPORT-PARTIAL-VERIFICATION` and
`M-IMPORT-TOO-MANY` appear nowhere in `workflow/measurement_messages.py`.

### Text that misdescribes what it does

1. **"ChromIQ did not file it, and nothing has been changed."** — measured
   false: a run was created, six chart files copied into it, `project.json`
   rewritten and the bar moved. `tab_profile.py:4429`.
2. **"Type a new name and ChromIQ makes that project and puts the measurement
   in its first run."** — it opens a second, empty name box first and throws
   away what you typed. `tab_profile.py:4271-4283`. (Report 14 F10.2,
   unchanged.)
3. **"…with a copy of the same chart ({n} chart files)"** — no singular form,
   so a one-file chart reads **"1 chart files"**; and when the occupied run has
   no chart at all the plan is empty and it reads **"a copy of the same chart
   (0 chart files)"**, promising something it will not copy.
   `tab_profile.py:4382`. CLAUDE.md: *"Count-bearing messages get explicit
   singular/plural variants."*
4. **"The reason: 50 of 50 patches do not hold the colour the chart asked
   for"** — also not count-aware; one bad patch reads "1 of 1 patches".
5. **`project_picker.list_projects` docstring: "Anything deeper is still
   reachable by typing its name."** — false; typing it makes a second empty
   project (G4).
6. **A row reading "empty"** for a project whose manifest could not be read,
   where `peek_project` went out of its way to say "something is here".
   `project_picker.py:39-55`.
7. **"The following files from `chromiq_cxf_unylsupl/` will be copied…"** — the
   `.mxf` route names ChromIQ's own temporary folder to the user.
   `ui/ti2_loader.py` `_ask_profile_name`, reached from
   `tab_profile.py:4475`.
8. **`workflow/measurement_messages.py:1290`** — the comment block
   *"--- PROPOSED: where the replaced project went ---"* sits above
   `M_IMPORT_REPLACE_PROJECT_CONFIRM`, not above `M_IMPORT_REPLACED_KEPT`,
   which is what it describes; a second comment block was inserted between
   them.
9. **`core/file_manager.py:2157-2210`** — `_discard_run`'s long comment argues
   for a guard that its only caller now disables (`just_created=True`), so
   the guard is dead code and the comment describes protection that is not in
   force.
10. **The partial window still says only "a rougher profile"** while §I.10's
    own text records that `colprof` builds silently from four patches and
    reports its best number for a profile 41.5 ΔE wrong. Report 14 F9.11,
    unchanged.

### What reads well

The project picker's body and the §I.9 window are both good, plain,
beginner-level English, and "Make a new run" / "Cancel" is the right pair with
the right default. `count_phrase` is used correctly in `_holds_phrase`. The run
picker's label change ("File the measurement in:") fixes exactly the fault the
owner caught from the earlier pictures.

---

## G9 · Report 14's still-open items

| Item | State |
|---|---|
| Cancel opening a second name box | **masked, not fixed.** `if not name: return False if not open_name else True` — with no project open, `fm.is_named()` is nonetheless True because `_target_name` already holds the invented `Printer_Paper_Type_Instr_<date>`, so Cancel returns True and the import stops. Remove the invented name and the second box comes back. |
| The typed name discarded | **open**, screenshots 07/08 |
| `M-IMPORT-REPLACED-KEPT` on 3 of 6 archiving routes | **open**: 4 call sites (`ti2_loader.py:1109`, `:1197`, `txt_loader.py:122`, `:205`). `_copy_ti3_only` archives at `ti2_loader.py:1567` with no notice, and `chart_import.copy_whole_project:161` archives with no notice and still raises plain `OSError` rather than `ReplaceFailed` |
| `clicked` → `toggled` on the row-numbers box | not re-examined this round — the control is no longer in `ui/tabs/tab_chart.py` under the names report 14 used, and I did not want to report a stale citation |
| Bug 14, the stray "Load Test Session" window | **open**, screenshot 14 |
| Bug 16, dead import `peek_project` | **open**, and two more beside it |

---

## G10 · BUGS

**B1 — The run picker's answer is discarded; every import lands in a new run.**
`ui/tabs/tab_profile.py:4319-4351`. `_build_run_picker` returns a snapshot list;
§S4.7 connects `picker.currentIndexChanged` to update it
(`ui/tabs/tab_chart.py:8874-8880`), the import does not.
*Repro:* copy `~/ChromIQ/Demo-Switching` into a scratch working folder, Build
Profile ▸ load ▸ an external `.ti3` ▸ pick `Demo-Switching` ▸ set the combo to
**Run 2** ▸ "File it here". The file lands in `runs/run6`.
Screenshots 05, 06. **Release-blocking:** it makes items 1, 2, 3 and 6 of this
round unreachable.

**B2 — `proj.runs()` does not exist.** `ui/tabs/tab_profile.py:4352`.
`Project` has `all_runs()` and `run(id)`.
*Repro:* `Project.load(Path(p)).runs()` → `AttributeError`. Reached today when
`_is_verification_target()` is true as the picker is built, and on every
non-default choice once B1 is fixed. **Release-blocking.**

**B3 — The default destination is never validated.**
`ui/tabs/tab_profile.py:4425` — `assess(measurement, run.chart_ti2)` on a
brand-new run, whose `chart_ti2` does not exist, so `_chart_patch_count` = 0
and `verify_patch_identity` is `checked: False`.
*Repro:* make a six-row `.ti3` from any header, import it into
`Demo-Switching`, accept the default. Filed, silently, as
`runs/run6/Demo-Switching.ti3`. **Release-blocking.**

**B4 — A measurement already filed in a run is asked about, and can be copied
into another project.** `ui/tabs/tab_profile.py:4485` —
`peek_project(p.parent).exists`, one level, where
`ui/ti2_loader.py:1055 _project_root_for` walks ancestors.
*Repro:* Build Profile ▸ load ▸ `<work>/Demo-Switching/runs/run1/Demo-Switching.ti3`.
The routing window opens. Choose `Demo-Prefs-Speed` → the file is copied to
`Demo-Prefs-Speed/runs/run4/Demo-Prefs-Speed.ti3`. Choose Cancel → nothing is
loaded at all. Screenshots 15, 16. **Release-blocking** — it changes the
behaviour of an everyday act.

**B5 — "nothing has been changed" is said after a run has been created and a
chart copied into it.** `ui/tabs/tab_profile.py:4425-4433`. The verdict is
taken after `new_run()` (`:4356`), `duplicate_run()` (`:4401`) and
`set_profile_run()` (`:4420`).
*Repro:* import a 50-patch foreign `.ti3` into an occupied run, accept "Make a
new run". Tree diff shows `runs/run6/` with 7 new files and `current_run:
run6`.

**B6 — An unwritable destination raises `PermissionError` out of the click
handler with no message.** `ui/tabs/tab_profile.py:4356` →
`core/file_manager.py:1994` → `:1153`.
*Repro:* `chmod 555 <project>/runs`, then import into that project.
`shutil.copy2` (`:4434`) and `duplicate_run` (`:4401`) are equally unguarded.

**B7 — `.mxf`, `.cxf` and `.txt` never reach the feature.**
`ui/tabs/tab_profile.py:4474-4477`. *Repro:* load
`~/Desktop/i1Profiler/ColorSpaceRGB/Measurements/RGB_default-i1Pro.mxf` —
one window, the old one. Screenshot 10.

**B8 — The typed project name is discarded and a second, empty box asks
again.** `ui/tabs/tab_profile.py:4282` → `ui/ti2_loader.py:1038
_handle_outside_ti3_only` → `_ask_profile_name`. Screenshots 07, 08.

**B9 — The name box is pre-filled with a name ChromIQ invented.**
`ui/tabs/tab_profile.py:4237-4239` — `fm.is_named()` is true for the
placeholder `Printer_Paper_Type_Instr_<date>`. Continue is the default button.
Screenshot 09.

**B10 — After "Make a new project instead" the bar and the tab disagree.**
Measured: `location_being_edited` =
`work/Printer_Paper_Type_Instr_2026-08-31_21-37/runs/run1/` (a folder that does
not exist) while the tab shows `work/Fresh-Import-Project/runs/run1/…`. The
picker route updates the bar; this route does not.

**B11 — A stray "Load Test Session" window after a successful import**, on
every path where the destination run has a chart. Screenshot 14.

**B12 — "{n} chart files" has no singular form and can be 0.**
`ui/tabs/tab_profile.py:4382`.

**B13 — A project whose `project.json` cannot be parsed is listed as
"empty".** `ui/dialogs/project_picker.py:39-55` ignores `peek.chart`, which is
the flag `core/file_manager.py:2852` sets precisely for that case.

**B14 — A picker row describes the project's last-used run, not the project.**
`ui/dialogs/project_picker.py:39-55` + `core/file_manager.py:2948-2955`.

**B15 — A project in a sub-folder is invisible to the picker and unreachable by
name.** `ui/dialogs/project_picker.py:58-64`;
`FileManager.resolved_root_for_name` returns the shallow path, so typing the
name creates a second, empty project of that name beside the real one.

**B16 — The list box shows twelve rows and half of a thirteenth.**
`ui/dialogs/project_picker.py:155-161`. Screenshot 02.

**B17 — `_discard_run`'s guard is dead.** `core/file_manager.py:2157` — the
only caller (`:2124`) passes `just_created=True`, which skips it entirely, so
the "last thing between a bug of ours and somebody's work" is never executed.
Its `_skip = {"meta.json"}` set also still lets a lone `.DS_Store` block it
(report 14, bug 15) if it ever were.

**B18 — `chart_import.copy_whole_project` still archives silently and raises
plain `OSError`.** `workflow/chart_import.py:161-163`; the return value of
`_archive_project_contents` is discarded, so nothing can say where the project
went. Report 14 bugs 10 and 11, unchanged.

**B19 — Spec violations in §I.9/§I.10 as approved.**
* *"I.6 keeps its chart snapshot"* — `_file_into_project` never calls
  `_snapshot_profiling_chart`; the filed measurement has no record of what it
  measured.
* *"I.8 offers Open measurement report and Build the profile"* — there is no
  done window at all on this route.
* *"Where `duplicate_source()` is None … the import is refused with the reason
  `_duplicate_missing_phrase()` already writes"* — `duplicate_source()` is
  never called; `duplicate_run_plan` is called unconditionally and yields an
  empty plan.

**B20 — Four new windows outside §M**, none of them recorded in
`WINDOW_SOURCES` or in `UNCATALOGUED_MEASUREMENT_WINDOWS`. See G8.

---

## G11 · GAPS AND MISSING OPTIONS

1. **Nothing tells you what a run holds while you choose it.** §S4.7's window
   rewrites its informative text as the combo changes; this one does not. You
   cannot see from the window that Run 2 holds a measurement or that Run 3's
   chart has 399 patches rather than 240.
2. **No search or filter in the project picker.** With 203 projects it is a
   scroll.
3. **No provenance is recorded anywhere.** The copy is `copy2`'d under the
   run's stem; no keyword, no sidecar, no line in the tab's log, nothing in
   `meta.json`. The Measure tab's verification import stamps
   `CHROMIQ_VERIFICATION` and writes four log lines.
4. **The same file imported twice makes two runs and says nothing.** Measured:
   run6 and run7, identical content, no notice.
5. **A run holding a measurement and no chart is the normal outcome.** Nothing
   warns that the run cannot be paired or reported on.
6. **`TabCheckRefine` still has no routing question** (report 14 F9.12).
7. **`M-IMPORT-NO-WHITE` still unbuilt** (report 14 F9.4): a partial with no
   white patch files, Build Profile arms, and `colprof` exits 1 with a string
   `_COLPROF_ERROR_PATTERNS` does not recognise.
8. **A measurement with no device columns** — 2 521 of the 2 550 `.txt` files
   in the owner's own i1Profiler folder — is still filed unvalidated with only
   a log line. Report 14 F9.5, unchanged.
9. **`Calibration.reset` still `rmtree`s `cal/exports/`** two lines after
   carefully archiving a `.ti3.engine-partial`.

---

## G12 · SAFETY OF THIS RUN

* Settings sandboxed to `/tmp/knut15/settings.ini` (`CHROMIQ_SETTINGS_FILE`
  exported before anything constructed `AppSettings`); presets to
  `/tmp/knut15/presets`.
* `defaults read com.chromiq.ChromIQ custom_output_path` → *does not exist*,
  before and after.
* `~/ChromIQ`: 1 058 files, SHA-256 inventory **identical** before and after.
  `~/ChromIQ/CR30-Test` never opened.
* `~/Desktop/i1Profiler`: `RGB_default-i1Pro.mxf` SHA-256 verified unchanged;
  no file in the tree modified.
* All scratch trees under `/tmp/knut15/`; probe and driver scripts in
  `/tmp/knut15/`, never in `scripts/`.
* All mutations applied to `/tmp/knut15/mutrepo`, an rsync copy. The working
  tree was never edited by this run — the only file it writes is this report.
* Note for the record: **the working tree changed under this run** (three
  edits to `ui/tabs/tab_profile.py`, `ui/widgets.py`, `ui/dialogs/name_prompt.py`
  and `ui/dialogs/project_picker.py` between 21:15 and 21:34). Everything above
  was re-verified against `ui/tabs/tab_profile.py` md5
  `ab460e7dbb029bff7853dbba8a5a15cc`, and every screenshot in
  `~/Desktop/knut-import-live/` was re-taken afterwards with the theme applied.

---

## G13 · VERDICT

**No. Not safe to tag beta 6.**

### Must change before any tag

* **B1** — connect `picker.currentIndexChanged` the way `tab_chart.py:8878`
  does, or take the run picker off the window. A picker that ignores you is
  worse than no picker: it tells the person they have chosen.
* **B2** — `proj.runs()` → `proj.all_runs()`. B1 and B2 must be fixed
  together; fixing either alone makes the other worse.
* **B3** — refuse, or say so, when the destination run has no chart. As it
  stands the module whose entire purpose is to check finds nothing to check
  against on the only path the UI can reach.
* **B4** — `peek_project(p.parent)` → `ti2_loader._project_root_for(p,
  working_dir)`. A measurement already inside a project must not be asked
  about.
* **B5** — take the verdict **before** creating or duplicating a run, or stop
  claiming nothing changed.
* **B6** — wrap `new_run`, `duplicate_run` and `copy2` and say what failed.
* **B7/B8** — either carry `.mxf`/`.cxf`/`.txt` and the typed name through, or
  take the door out until it is whole. A door that opens for one file type in
  four and throws away what you typed is worse than none. (Report 14 said this
  and it is unchanged.)

### Must change before the feature is called finished

* **B20 / G8** — the four new windows to §M-PROPOSED, rendered from
  `workflow/measurement_messages.py`. Under CLAUDE.md this is not a style
  point. And `WINDOW_SOURCES` needs a shape that can name a module-level
  function, or the picker can never be covered by it.
* **B19** — the chart snapshot, the done window and the `duplicate_source()`
  gate that §I.9 as approved requires; or an amendment saying they are out.
* **B12/B13/B14/B15/B16** — the wording and the picker's honesty.
* **The tests.** Not one test touches the new UI: the entire feature can be
  switched off and the tier is byte-identically green. At minimum: a test that
  drives `_file_into_project` with a chosen run and asserts the file lands
  there, one that asserts a chartless destination is refused, and one that
  asserts a `.ti3` already inside a run is not asked about.
  `test_no_repair_is_attempted_anywhere_in_the_module` should assert on
  verdicts, not grep for four library names.

### Safe to keep as it is

`duplicate_run(groups=…)`, `_discard_run(just_created=…)`, `_next_run_index`'s
disk check, `Run.clear_reads`' archive, `Calibration.reset`'s engine-partial
rescue, the partial identity check inside `assess`, `dir_holds`, the loaders'
four archive routes, the button-order work in `spread_message_box_buttons`
(`order=` is passed at exactly six call sites, all inside this change, so no
other window in the app can have been disturbed), and the wording of the
project picker and the §I.9 window.

STATUS: complete

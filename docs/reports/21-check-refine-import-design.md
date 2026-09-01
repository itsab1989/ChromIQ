# 21 — Check & Refine: importing a measurement, and "check it where it is"

**STATUS: COMPLETE** (2026-09-01). Nothing below is implemented; this is a
design and a set of objections. Five faults in shipped code were found while
establishing today's behaviour and are reported, not fixed (F1 to F5).

**Author:** design round, 2026-09-01.
**Starts from:** `docs/reports/20-beta6-final-challenge.md` §7 (do not redo it).
**Binding:** `docs/design/unified_measurement_management.md` §I.9 (import doors),
§6c, §M (message catalogue).

---

## 0. What Basti decided, and what is being challenged

Two decisions arrived together, and only one of them is a decision about code.

**(A) Build it the same way as Build Profile.** Check & Refine gets the project
picker, the run picker and the "File it in Run 3" button, in the tab's own
violet (`ui/tabs/tab_check_refine.py:51`, `_TAB_COLOR = "#9f82ff"`; Build
Profile's is `#37bcd6`, `ui/tabs/tab_profile.py:64`).

**(B) A new option: "check the file where it is"** — do not copy the
measurement into a project at all. Basti asks whether it belongs in the Build
Profile importer too, and asks for that to be challenged rather than assumed.

Report 20 §7 answered the feasibility question and I am not redoing it. What
follows starts from its four objections, adds four more found by driving the
real app, and answers the option (B) question in both tabs.

### The safety this round was driven under

`CHROMIQ_SETTINGS_FILE=/tmp/checkrefine-design/settings.ini` was exported before
anything constructed `AppSettings`; every driver prints the store it is using as
its first line. `custom_output_path` pointed at `/tmp/checkrefine-design/ChromIQ`,
a copy of the demo project tree from `$TMPDIR/chromiq-demo-projects-cache`.
Nothing under `~/ChromIQ/` was read, written or listed. Verified by value at the
end of the round, not against a backup:

```
$ python3 -c "import plistlib,os; print(repr(plistlib.load(open(os.path.expanduser(
    '~/Library/Preferences/com.chromiq.ChromIQ.plist'),'rb')).get('custom_output_path')))"
''            # empty, meaning "use ~/ChromIQ" — the same value as before the round
```

`defaults read com.chromiq.ChromIQ custom_output_path` prints a blank line
rather than "does not exist", because the key is present and empty. That is the
user's own value and it is what it was at the start. No project named in this
report (`Demo-Full-RGB`, `Ctl-Experiment`, `With-Sibling-ICC`,
`Imported-Desktop-Measurement`, `BP-New-Project`) exists anywhere under
`~/ChromIQ`; all four live in `/tmp/checkrefine-design/ChromIQ`. No source file
was edited: the controller experiment in §3 injected the attribute at runtime,
and `git status` shows only this report.

### Three faults in SHIPPED code found while establishing today's behaviour

These are reported, not fixed, per the binding-specs rule. They are listed here
because two of them change what the design in §7 has to do.

| # | Fault | Where |
|---|---|---|
| F1 | A **refused** import still leaves a new run on disk, while the window says "nothing has been changed" | `ui/tabs/tab_profile.py:4446` runs before `:4514` |
| F2 | `<stem>.print.json` is dropped by **every** run duplication, so the §2b converted-sheet guard stops firing on the copy | `core/file_manager.py:2028-2044` |
| F3 | Check & Refine's import moves no bar and opens no project, so the file field and the bar point at different projects | driven, `ui/tabs/tab_check_refine.py:1211` |

Each is proved in its own section below.

## 1. The complete user journey for (A)

Written as the design I would build, with option (B) folded in as the second
answer to the one question. Every UI element is named as it exists in the code.

### The start

The user has `~/Desktop/scan.ti3` — a measurement made in i1Profiler, or handed
over by a colleague, or found in last year's job folder. They open ChromIQ and
go to **5. Check & Refine**.

### Click 1 — the browse button

They click the folder button beside **`.ti3 test data file:`**
(`ui/tabs/tab_check_refine.py:351`, tooltip *"Browse for .ti3 file"*), and pick
the file. Nothing else changes yet.

### The fork, decided without asking anyone

`_on_browse_ti3` asks `_project_root_for(path, working_dir)`
(`ui/ti2_loader.py:1077`) — the same question `resolve_ti3` asks today.

* **The file is already inside a project** under the working folder → **no
  question is asked at all.** The path goes straight into the field, the ICC is
  auto-filled, the bar moves to that project and run, and the journey ends here.
  This is the common case and it must stay one click. *(Today it is one click but
  the bar does not move — F3.)*
* **The file is outside** → click 2.

### Click 2 — one window, two honest answers

A new window, **"Where should this measurement go?"**, in the tab's violet
(`_TAB_COLOR = "#9f82ff"`). It is `ui/dialogs/project_picker.choose_project`
with its `accent` argument used (`ui/dialogs/project_picker.py:144-146` — the
argument exists and Build Profile does not pass it today).

It shows the project list exactly as Build Profile's does, driven and verified:

```
Demo-Full-RGB          ·   3 runs, a calibration
With-Sibling-ICC       ·   1 run, a measurement, a profile
```

Buttons, left to right, Cancel far right (`spread_message_box_buttons`):

| Button | Role | What it does |
|---|---|---|
| **File it in this project** | primary, violet | → click 3 |
| **Make a new project instead** | secondary | → the name box, then click 3 |
| **Just check it where it is** | secondary | → skip to "The check" |
| **Cancel** | reject | nothing happens, the field stays as it was |

The primary is the filing answer, deliberately (§4e). With **no** projects in
the working folder the list is empty, and `choose_project` is not shown at all
(report 20 §6a) — the person goes straight to the name box, with
*"Just check it where it is"* offered there too.

### Click 3 — which run

Exactly Build Profile's window, reused unchanged: **"Where should the
measurement go?"**, with the run picker attached
(`tab_chart._build_run_picker` / `_attach_run_picker`), the label
**"File the measurement in:"**, and a button that names the run it will use —
*"File it in a new run"*, *"File it in Run 3"*
(`ui/tabs/tab_profile.py:4380-4396`). Cancel on the far right.

### What happens on disk

The shared helper (§7) performs, in this order — **note step 3, which is F1
corrected**:

1. **Open the project.** `tab_chart.open_project_manifest(root/"project.json")`
   — the whole open, not a cut-down one. This is what makes the bar follow.
2. **Find or make the run.** An existing run that holds no measurement is used
   as chosen. A run that already holds one is not displaced — the *"That run
   already has a measurement"* window offers a chart-only copy beside it.
   "A new run" is `duplicate_run(source, groups=…)`, never an empty folder.
3. **Validate BEFORE anything is created.** `assess(measurement, chart_ti2)` is
   run against the *source* run's chart, and a refusal stops here with nothing
   made. *(Today the duplicate is made first — F1.)*
4. **Copy the measurement** to `Run.measurement_ti3` — the run's canonical stem,
   per §I.9's I.7.
5. **Copy the sibling `.icc`/`.icm`, if there is one**, to `Run.profile_icc`
   (§2, breakage 1).
6. **Point the bar:** `set_run_type("profiling")`, `set_verification_id("")`,
   `set_profile_run(run.id)`, `project_replaced_on_disk()`.

### What the measurement bar does

Before: whatever was open. After: **the project and run the file went into**,
Run type Profiling. Driven on Build Profile's existing implementation:

```
BAR BEFORE: Demo-Full-RGB run3
BAR AFTER : Demo-Full-RGB run4 profiling
```

and, when a different project is chosen, the FileManager moves with it:

```
BAR AFTER : Imported-Desktop-Measurement run1 profiling
FileManager working_dir: …/ChromIQ/Imported-Desktop-Measurement
```

### What the tab shows

* **`.ti3 test data file:`** — `…/Demo-Full-RGB/runs/run4/Demo-Full-RGB.ti3`
* **`ICC / ICM profile:`** — the run's `.icc` if the run has one, the sibling
  `.icc` if one came with the measurement, otherwise **empty with a message
  that offers the browse button** (§2, breakage 1). Not *"Profile Not Found"*.
* **`Analyse Profile Quality`** (`:420`) enables only when both fields are
  filled — unchanged (`_update_run_btn`, `:165-168`).

### What the log says

One line per fact, in the tab's own log panel:

```
[OK] Filed into Run 4 of Demo-Full-RGB. The file you picked is untouched.
[OK] The profile from Run 3 was copied in with the chart.
Detected instrument: i1Pro 2 (spectral data present).
```

*(The third line already exists — `_detect_instrument`, `:223-240`.)*

### The check

`Analyse Profile Quality` → `profcheck` with `cwd = <the run folder>` → the
result dialog. The report lands in `runs/run4/reports/Quality_Check_1_….txt`
and, when strips are flagged, `Refine_Strips_….txt`.

### Where every file ends up

| File | Filed | In place |
|---|---|---|
| the measurement the user picked | **untouched, where it was** | untouched |
| its copy | `runs/runN/<project>.ti3` | — |
| the sibling `.icc`, if any | `runs/runN/<project>.icc` | — |
| the chart | copied from the source run | — (none) |
| quality report | `runs/runN/reports/Quality_Check_<n>_<stem>.txt` | `<source folder>/reports/Quality_Check_<n>_<stem>.txt` |
| refine strips | `runs/runN/reports/Refine_Strips_<n>_<stem>.txt` | `<source folder>/reports/Refine_Strips_<n>_<stem>.txt` |

### "Where are my files again?"

Three answers, all of which must work:

1. The bar's location line names the folder, because the bar followed.
2. The tab's own **reveal** button opens it (`reveal_in_file_manager`; Build
   Profile's is at `ui/tabs/tab_profile.py:4200-4208`) — **Check & Refine has no
   such button today and should get one.** Open question 6.
3. `Where are my files.txt` in the project root explains the layout — and needs
   a paragraph if in place ships (§4d).

## 2. The four naive-version breakages from report 20 §7, answered

### Breakage 1 — `_auto_fill_icc` fires "Profile Not Found"

**Real, and near-universal in the naive version.** Proved by construction and
by driving.

`Run.chart_ti2`, `Run.measurement_ti3` and `Run.profile_icc` all share
`<stem>` (`core/file_manager.py:777, 805, 918`). §I.9's new run is
`duplicate_run(source, ("chart",))`, and the `chart` group
(`core/file_manager.py:2029-2032`) contains no `.icc`. `_auto_fill_icc`
(`ui/tabs/tab_check_refine.py:1236-1268`) looks for `merged.icc` then
`<stem>.icc`/`.icm` beside the `.ti3`, finds neither, and warns. And the
displaced-run branch is the same: a run that already holds a measurement is
duplicated chart-only too (`ui/tabs/tab_profile.py:4490`). So **every** §I.9
import into Check & Refine would land in a run with no profile.

**It already happens today**, for the bare-`.ti3` case. Driven, on the real tab
(`01-todays-behaviour.txt`):

```
resolve_ti3 returned: …/Imported-Desktop-Measurement/runs/run1/Imported-Desktop-Measurement.ti3
--- _auto_fill_icc ---
icc after auto-fill: None
MODAL: QMessageBox 'No matching .icc or .icm file was found in: …
        Please browse for the profile file manually.'
```

With a **sibling** `.icc` it works today, because `_copy_ti3_only`
(`ui/ti2_loader.py:1593-1598`) carries it to `run.profile_icc`
(`03-sibling-icc-and-bar.txt`):

```
auto-filled icc: …/With-Sibling-ICC/runs/run1/With-Sibling-ICC.icc
```

**What the design does — three parts, and the third is a question for
Sebastian.**

1. **Carry the sibling `.icc`/`.icm` with the measurement**, exactly as
   `_copy_ti3_only` already does. That covers the commonest real case: a
   `.ti3` and its `.icc` handed over together.
2. **Copy the source run's profile with its chart** when the chosen run has one:
   `duplicate_run(source, ("chart", "profile"))` for the Check & Refine door
   only. The `profile` group already exists (`core/file_manager.py:2034-2036`)
   and carries `<stem>.icc`, `merged.icc` and `calibrated.icc` — precisely what
   `_auto_fill_icc` looks for.
   **This amends §I.9's "copying the CHART only".** §I.9's reason for chart-only
   was that a copied profile would be *orphaned the moment the import overwrote
   the `.ti3`*. For a Check & Refine import that reasoning does not hold: the
   profile is not orphaned, it is **the second operand of the act being
   performed**. But the reasoning is Sebastian's, the clause is his, and I am
   not entitled to reinterpret it. **Open question 1.**
3. **Never warn where a browse button will do.** Replace the modal
   *"Profile Not Found"* with an inline message beside the `ICC / ICM profile:`
   field and the browse button already next to it. The current window explains
   a fix and closes, leaving the person to do the thing it described — the exact
   pattern `ui/dialogs/name_prompt.py:160-163` was written to end.

### Breakage 2 — the reports move, silently

**Real, and a decision rather than a bug.**
`ui/tabs/tab_check_refine.py:1377` writes into
`reports_subdir(self._ti3_path.parent)`, so the reports follow the `.ti3`
wherever it is. Filing into Run 4 moves every future report into Run 4's
`reports/`.

**What the design does: it stops being silent, because the user chose it.**
Under this design the person has answered a window that says where the
measurement is going, and the log then says where the report went. That is
enough — a second window about report location would be nagging. The only part
that must be explicit is the **in-place** side, because a `reports` folder
appearing on someone's Desktop is genuinely unexpected (§4c) — and that is
covered by the wording in §5.

**What it does NOT do: move the reports already written.** Reports written
beside the file before it was filed stay beside the file. §4f explains why that
is the wrong outcome and proposes copying them in; whether to is **open
question 4**.

### Breakage 3 — there is nothing to validate against

**Real, and it is the reason the design must not offer a bare "new run".**
§I.9's step I.5 is the whole safety of the import: patch count, then
`verify_patch_identity`, against `Run.chart_ti2`. Check & Refine's own two
inputs are a `.ti3` and an `.icc` — it has no chart of its own.

**But the chart comes from the RUN, not from the tab.** That is what
`ui/tabs/tab_profile.py:4436-4446` established: "a new run" is
`duplicate_run(source, …)` and, where `duplicate_source()` is `None`, the import
is refused rather than filed blind. Check & Refine inherits this for free by
reusing the same helper. Driven, and it works:

```
MODAL: 'This measurement does not belong to that chart'
       'ChromIQ did not file it, and nothing has been changed.
        The reason: 225 of 240 patches do not hold the colour …'
MODAL: 'There is no chart to check this measurement against'
       '… “Imported-Desktop-Measurement” has no chart in it yet.'
```

So breakage 3 is answered **only** if the shared helper is genuinely shared —
which is why §7 lifts it rather than copying it.

**And it exposes F1.** Driven: the refusal window above appeared, and Run 4 was
on disk anyway with a full chart copy, listed in `project.json`, `current_run`
pointing at it, and the bar following. See §0 F1.

### Breakage 4 — §6c's "the data it was built from", and where the door is

**Real as a specification question, and NOT ours to settle.**
`unified_measurement_management.md` §6c describes `profcheck` as checking *"a
profile against **the data it was built from**"*. §I.9's "Where the door is"
places the profiling import in Build Profile, reasoning that *"the tab a person
is on already says which act they are performing"*.

Adding an import door to Check & Refine amends that clause. Two things are true
at once and both should be put to Sebastian:

* **The tab's act is checking, not filing.** Report 20 §7 is right that a
  `.ti3` opened here is often someone else's, or last year's, and asking "which
  run should this go in?" of a file the user only wants to look at is the wrong
  question. **Option (B) is the answer to that**, and it is why I recommend the
  two features together rather than (A) alone.
* **The door is already there, and it is the worst one in the app.** The tab
  imports today (`resolve_ti3` → `_handle_outside_ti3_only`), with no project
  list, no run picker, no validation and no bar move. §I.9's clause about where
  the door is was written when nobody had noticed this one.

**What the design does:** it does not decide. It makes the amendment explicit —
"the Check & Refine load control is a third import door, offering *file it* and
*check it where it is*" — and puts it to Sebastian as **open question 2**,
alongside §6c's wording, which arguably needs one clause added: *profcheck
compares a profile with a measurement; usually the one it was built from, but
not necessarily.* That sentence is a description of what the tool does, not a
new capability — **but it is still a specification change and still his.**

## 3. The controller question, settled with evidence

### What is actually absent

`TabCheckRefine` has no `set_target_controller`, no `_target_ctl`, and no
`load_target_settings`. Driven, on the real `MainWindow` with the real tab
(`~/Desktop/beta6-proof/7-check-refine-design/01-todays-behaviour.txt`):

```
TabCheckRefine has _target_ctl attr? -> False
TabCheckRefine has set_target_controller? -> False
TabCheckRefine has load_target_settings? -> False
```

The loop at `ui/main_window.py:305-308` is guarded by
`hasattr(_t, "set_target_controller")`, so the tab is skipped rather than
excluded by name. `_target_ctl` appears exactly once in the whole file — in the
comment at `ui/tabs/tab_check_refine.py:1211-1215` that says it never had one.

### Is there a documented reason?

**In git history: no.** The comment was added incidentally in `18867d76`
("The tile window asked for one press…", 2026-08-31), a CR30 commit; the diff
removes a `getattr(self, "_target_ctl")` guard that did nothing. No commit ever
added the tab to the loop or removed it. `26717574` ("#130 phase 4: wire the
shared target into Create Chart + Measure") is the only commit that touches
`set_target_controller` in `main_window.py`, and it wires two tabs.

**In the specifications: yes, one, and it is narrower than it looks.**
`docs/design/per_target_settings.md:355` records Knut's ruling that Print Chart
and Check & Refine *"can be kept as is for now"*, and `:369` puts a `❌ for now`
against `5. Check & Refine` with no store. That rules on **per-target
settings**, which is one of the things a controller feeds — not on the
controller itself. Print Chart carries the same `❌` and **does** have a
controller (`ui/tabs/tab_print.py:700`), so the ruling plainly does not forbid
one.

### What happens if it is given one — driven, not reasoned

I injected the controller onto the real tab at runtime, exactly as
`main_window.py:308` would (`tab._target_ctl = ctl`), with no source edit, and
then exercised the tab's whole surface: `set_paths`, instrument detection,
`set_calibration_mode(True/False)`, `clear_files`, and a full outside-`.ti3`
load. Output in `02-controller-injection.txt`:

```
=== (a) bare _target_ctl assignment ===
tab works? run btn enabled: False
after set_paths -> run btn: True | detected instrument: None
after clear -> ti3: None icc: None
controller 'changed' fired during all of that: 0 times
bar state unchanged? run = run3 type = profiling
```

**Nothing changes.** The attribute is inert: no code in `tab_check_refine.py`
reads it, `changed` is never connected, and `_load_settings_of_visible_tab`
(`ui/main_window.py:1512-1524`) returns at its first line because the tab has no
`load_target_settings`. A bare `set_target_controller` that only stores the
reference is a zero-risk change.

### But the call the comment points at would NOT do what it promises

The comment says *"If this tab is ever given a controller, the call belongs
here"* — meaning `_point_bar_at_current_run` (`ui/ti2_loader.py:1014`), the bar
refresh every other loader performs. **Driven, it does nothing useful:**

```
=== (b) with the bar refresh the comment points at ===
resolve_ti3 -> …/ChromIQ/Ctl-Experiment/runs/run1/Ctl-Experiment.ti3
bar BEFORE refresh: project = Demo-Full-RGB run = run3
bar AFTER  refresh: project = Demo-Full-RGB run = run3 type = profiling
  ^ the FileManager still points at: …/ChromIQ/Demo-Full-RGB
```

`_point_bar_at_current_run` asks `controller.project_or_none()`, which asks the
**FileManager** — and `resolve_ti3` creates a project folder on disk without
ever opening it. So the refresh re-points the bar at the project that was
already open, and the file field still names a different one. Adding the
controller and the call would produce the *appearance* of the fix and not the
fix, which is precisely what the comment it replaces was criticised for.

**The missing act is the OPEN, not the controller.** `_file_into_project`
(`ui/tabs/tab_profile.py:4317-4322`) does it explicitly, through Create Chart's
own `open_project_manifest`, and that is why Build Profile's bar follows:

```
BAR BEFORE: Demo-Full-RGB run3           (existing-project answer)
BAR AFTER : Demo-Full-RGB run4 profiling
BAR BEFORE: Demo-Full-RGB run4           (a different project chosen)
BAR AFTER : Imported-Desktop-Measurement run1 profiling
FileManager working_dir: …/ChromIQ/Imported-Desktop-Measurement
```

### Verdict on the controller

1. **Give the tab a `set_target_controller`, and make it store the reference and
   nothing else.** Do not connect `changed`; do not add `load_target_settings`.
   That keeps `per_target_settings.md`'s `❌ for now` true and is provably inert
   (0 signals, no behaviour change across the tab's whole surface).
2. **Do not add `_point_bar_at_current_run` to `_on_browse_ti3`.** It is a
   no-op on the path it would sit on. The bar follows only when the project is
   *opened*, and that belongs inside the shared filing helper (§7), not in the
   browse handler.
3. **F3, reported:** today, with no controller and no open, Check & Refine's
   import leaves the bar naming one project and the `.ti3 test data file:` field
   naming another. Driven, `01-todays-behaviour.txt`. This is the same shape as
   the fault quoted in `ui/tabs/tab_profile.py:5046-5050` (Knut, Demo-08 step 10)
   that `set_target_controller` was written for on Build Profile.

## 4. Option (B), "check the file where it is", challenged

### What is settled, and what is mine to argue

**Basti's ruling (settled, not up for debate here):** if ChromIQ works in
place, the resulting files are saved **where the measurement file is** — beside
the file the user picked, in its own folder. That applies to the check report
and, if "build in place" exists at all, to the ICC and everything else a build
produces.

So the objection "a report with nowhere to live" is answered and I do not argue
it. **What is still mine to recommend is WHETHER each feature should exist** —
check in place, build in place, both, or neither — and what the window must say
before someone chooses it.

### 4a · What a profile check actually needs beside the measurement

**Two files, and nothing else.** Proven by running the real binary on the two
files sitting loose in a folder that is not a project
(`06-inplace-writes.txt`):

```
$ cd /tmp/checkrefine-design/outside
$ profcheck -v2 desktop-measurement.ti3 desktop-measurement.icc
rc 0
Profile check complete, errors: max. = 300.109648, avg. = 30.185134, RMS = 60.788277
$ ls -a          # nothing was written into the folder
.  ..  bare.ti3  desktop-measurement.icc  desktop-measurement.ti3
```

`ProfcheckRunner.run` (`workflow/profcheck_runner.py:189-198`) passes
`cwd = params.ti3_path.parent` and the two paths. No `.ti2`, no chart, no
`verify_patch_identity` — **the tab never calls it**: `assess()`
(`workflow/measurement_import.py:60`) belongs to the importer, not to the check.
So the check itself is complete in place. Technically option (B) is nearly free.

**But three things the tab does around the check are not free.**

1. **`_notify_ti2` finds nothing** (`ui/tabs/tab_check_refine.py:214-217`):
   `ti3.with_suffix(".ti2")` next to a loose `scan.ti3` does not exist, so the
   Measure tab is never told which chart this was. That matters at step 3.
2. **Guided refinement silently uses the wrong chart.**
   `TabMeasure.start_guided_refinement` (`ui/tabs/tab_measure.py:4508-4512`)
   does `ti2 = ti3.with_suffix(".ti2"); if ti2.exists(): self.set_ti1_path(ti2)`
   — **and if it does not exist, it does nothing and carries on**, applying the
   refine-strip list from the foreign measurement to whatever chart the Measure
   tab happens to hold. The "Refine" half of "Check & Refine" is not safe in
   place without a guard.
3. **The §2b converted-sheet warning cannot fire.**
   `_warn_converted_measurement` (`ui/tabs/tab_check_refine.py:1273`) asks
   `read_print_record` (`workflow/verification_print.py:308-332`), which looks
   for `<stem>.print.json` beside the `.ti3`, in `chart/`, or one level up. A
   loose file has none, so the check runs without the warning that its numbers
   may be meaningless. *(This is not an argument against in place on its own —
   see F2 below, where filing the measurement destroys the same record.)*

### 4b · ChromIQ would be writing into a folder it does not own

Enumerated, and each proved where a real attempt was possible
(`06-inplace-writes.txt`, `07-vanishing-folder.txt`).

**A folder the user cannot write to.** `ensure_subdir`
(`core/file_manager.py:214-224`) catches the `mkdir` failure and **falls back to
the parent** — which on a read-only folder is read-only too, so the fallback
buys nothing and the write raises one step later:

```
READ-ONLY folder: ensure_subdir returned: …/readonly (exists: True)
  write_quality_report raised: PermissionError [Errno 13] Permission denied
```

**What the app does today with that failure.** `ui/tabs/tab_check_refine.py:1404-1406`:

```python
except Exception as exc:
    log.warning("Could not write quality report: %s", exc)
    self._log.appendPlainText(f"[WARNING] Could not write output files: {exc}")
```

The result dialog is then shown **exactly as if the report had been written**.
So the user reads their ΔE figures, closes the window, and has no report — and
the only notice is one line in a log panel that ChromIQ lets them switch off
(`hide_log_output`, `ui/main_window.py:2277`). **That behaviour is good enough
inside `~/ChromIQ`, where a write failure is nearly impossible; it is not good
enough in a folder ChromIQ does not own, where it is the expected case.**

**A folder that goes away mid-flight** (an unmounted share, an ejected volume,
a `.dmg` closed while the check ran). Proved by removing the folder between
`ensure_subdir` and the write:

```
write after the folder vanished -> FileNotFoundError [Errno 2] No such file or directory
```

Same swallow, same silent outcome.

**A sync folder — iCloud Drive, Dropbox, OneDrive.** `write_named_report`
(`workflow/profcheck_runner.py:436`) uses `Path.write_text`, which truncates
then writes; it is **not** atomic. `core/file_manager.py:227
write_json_atomically` exists precisely for this and is not used here. A sync
client can therefore upload a half-written or zero-length report. Worse, the
slot is then occupied for ever, because the numbering only looks for a free
name:

```
next check after a zero-length survivor wrote: Quality_Check_2_scan.txt
| the empty one is still there: 0 bytes
```

**A quarantined download.** Not reproduced (I did not want to attach a real
quarantine attribute to a file in this round). The likely behaviour is that the
`.ti3` reads fine and the write succeeds, since `com.apple.quarantine` gates
execution and not directory writes — **I am not certain of that and it should be
tested before shipping, not assumed.**

**Sanitisation.** Everything ChromIQ writes into a project goes through
`FileManager._sanitise` on the *project name*. An in-place write uses
`self._ti3_path.stem` **raw** (`ui/tabs/tab_check_refine.py:1372`). On macOS the
only illegal characters in a filename are `/` and NUL, neither of which can be
in a stem, so this is safe on this platform — but a stem containing a newline or
a leading dot would produce a report file the user cannot easily see, and no
code path sanitises it.

### 4c · Name collisions in a folder full of somebody else's files

For `~/Desktop/scan.ti3`, exactly this appears, driven:

```
what now sits beside the user's scan.ti3:
  ['holiday-photo.jpg', 'reports', 'scan.ti3']
reports/Quality_Check_1_scan.txt
reports/Quality_Check_2_scan.txt      # a second check
reports/Refine_Strips_scan.txt
```

**A folder named `reports` appears on the Desktop.** That is the first
surprise, and it is not small: `reports/` is a ChromIQ word, and on a Desktop
it reads as the user's own.

**The quality report never collides** — `write_named_report`
(`workflow/profcheck_runner.py:428-434`) increments `n` until the name is free.
Good.

**`Refine_Strips_<stem>.txt` DOES collide, and overwrites without archiving.**
`write_refine_strips` (`:461-468`) builds one fixed name and calls
`write_text`. Driven: I hand-edited the file between two checks and the second
check destroyed the edit.

```
refine strips twice -> Refine_Strips_scan.txt | Refine_Strips_scan.txt | same file: True
content after the second write: ['# CHROMIQ_REFINE_STRIPS_V1', '# Strip\tMaxDE']
```

**F4, reported (shipped code, pre-existing).** This is true inside a run folder
today, so it is not created by option (B). But CLAUDE.md's rule is absolute —
*nothing the user created is ever deleted, only archived* — and the difference in
place is that the file being overwritten sits in the user's own folder, where
they may reasonably have edited it. **In place must not inherit this behaviour
as it stands.**

**Does in place inherit archive-then-replace, and where would `old/` sit?**
It cannot, and it should not. `_archive_project_contents`
(`workflow/chart_import.py`) archives *a whole project* into its own `old/`.
Creating `~/Desktop/old/2026-09-01_142233/` beside somebody's holiday photos is
worse than the problem it solves. **My recommendation: in place writes only
never-colliding names.** That means `Refine_Strips_<stem>.txt` gains the same
`_<n>_` numbering the quality report already has, at least on the in-place path
— and preferably everywhere, which would also fix F4.

### 4d · What the user gives up, and whether the window must say so

`ui/file_guide.py:29-44` opens with:

> *"Every ChromIQ project lives in its own folder (inside ~/ChromIQ, or your
> custom output folder from Settings), named after the profile."*

An in-place check makes that sentence **false** for the files it writes. The
guide is shipped in two places — the Welcome/Help card and
`Where are my files.txt` in each project root — so if in place ships, the guide
needs a paragraph. It is one row and one sentence, not a rewrite.

Plainly, what is given up by choosing in place:

| Kept | Given up |
|---|---|
| the ΔE numbers and the result window | the run's `reports/` history — a project's record of every check of that profile |
| the report file, beside the measurement | `report_*.json`, which `duplicate_run`'s `reports` group carries with a run |
| the refine-strip list | the chart, so **guided refinement has no chart to load** |
| — | the §2b converted-sheet warning |
| — | any record of *which profile* was checked, once the two files drift apart |

**The window must say the first and third of those.** It must not recite the
table; one sentence about where the files go, and one about what the tab cannot
do afterwards, is honest and short. Draft in §5.

### 4e · Does it become the path of least resistance?

**Yes, if it is offered as a peer of "file it".** This is the objection I hold
to most strongly, and it is not answered by the file-location ruling.

The asymmetry is real and it is in the clicks. Filing costs: pick a project
(one window), pick a run (one window), read the outcome (sometimes a third
window). In place costs: nothing — it is the absence of all three. A person
checking a profile is in a hurry by definition; they are checking, not building.
Given a free option and a three-window option that produce the same numbers on
screen, the free one wins every time, and the run history the folder model
exists to give them quietly stops accruing.

**There is a shape that keeps the easy path honest, and it is not a warning.**
Three parts:

1. **In place is not a peer answer; it is what happens when the file is already
   somewhere sensible.** ChromIQ should *not* ask the question at all when the
   `.ti3` is already inside a project — it checks in place, which is what it
   does today and is obviously right. The question is asked **only** for a file
   outside the working folder.
2. **Ordering, and which button is primary.** In the one window that does ask,
   *"File it in a project"* is the primary (accented) button and comes first;
   *"Just check it where it is"* is a plain secondary. Both are one click. The
   cost difference then becomes one extra window for filing, not three: the run
   picker only appears once a project has been chosen.
3. **The result window offers the file-it path afterwards.** After an in-place
   check, the result dialog carries a *"Keep this in a project"* button that
   runs the same filing flow with the same file. This turns an irreversible
   choice into a deferred one, which is the answer to 4f.

**With those three, I think the risk is manageable. Without part 3 it is not,
and I would recommend against the feature.**

### 4f · Reversibility

Today, without part 3 above: **a person who checks in place and then wants it in
a project must do the work again** — browse the same file, answer the question
differently. And the reports they already produced do **not** follow: they stay
beside the measurement, and the run's `reports/` starts numbering at
`Quality_Check_1` again, so the same profile ends up with two histories both
numbered from 1, in two places, with nothing linking them.

That is a poor outcome and it is avoidable. **Part 3 of 4e is not a nicety; it
is what makes in place a deferral rather than a fork.** When the file is later
filed, the in-place `reports/` folder beside it should be copied into the run's
`reports/` alongside it — the numbering already handles the merge, because
`write_named_report` only ever takes a free name.

### 4g · Check versus build — they are NOT the same, and the difference is a ruling

Basti asked whether "check in place" is different in kind from "build in place".
**It is, and the difference is already written down in a confirmed
specification.**

`docs/design/per_target_settings.md:368-369`:

| Tab | In scope | Store |
|---|---|---|
| 4. Build Profile / Calibration & Profiling | ✅ | `runs/runN/meta.json` / `cal/meta.json` |
| 5. Check & Refine | ❌ for now | — |

**Build Profile is required to have a per-target settings store; Check & Refine
is required not to.** And `store_for_target` (`workflow/per_target_settings.py:239-244`)
returns `None` the moment `ctl.project_or_none()` is `None`. So a build in place
**cannot store its own settings**, and every one of the faults
`per_target_settings.md` was written to fix comes back for that build: the
algorithm, quality and black-generation values silently fall back to whatever
the last run used, with nothing on disk saying what actually built the profile.

Mechanically, build in place is the *easier* of the two —
`ProfileBuilder.build` (`workflow/profile_builder.py:188`) already uses
`cwd = params.ti3_path.parent` and `args.append(str(p.ti3_path.with_suffix("")))`
(`:397`), so colprof already writes `<stem>.icc` beside the `.ti3`. The reason
that never happens today is only that the `.ti3` is moved into a run first.
**Being easy is not being right.** A build in place also has nowhere for
`merged.icc`, `calibrated.icc`, `preconditioning.*`, `exports/`, the measurement
report's `report_*.json`, or the verification history that §6 exists to protect
— every one of them is a `Run` property (`core/file_manager.py:805-945`).

And there is a plain human difference behind the spec: **a check produces a
number you read once; a build produces a file you install and keep for a year.**
A profile with no run behind it has no record of which measurement made it, no
settings, no verification history and no place for one — and §6a already names
that exact damage: *"a year later nothing says which profile a given date was
measured against."*

### 4h · Recommendation

**Take option (B) for Check & Refine. Do NOT take it for Build Profile.**

*Reasons for taking it in Check & Refine:*
* The check needs nothing but the two files, proven by running the binary.
* The tab's report path was already written for it — the comment at
  `ui/tabs/tab_check_refine.py:1379-1381` says "works for run folders and for a
  browsed external `.ti3` alike", and it does.
* Checking somebody else's profile, or last year's, or a competitor's, is a
  normal thing to do, and §6c already describes this tool as the one that "never
  looks at a verification measurement". Making a project for it is the wrong
  answer, and it is the answer ChromIQ gives today (F3).
* Check & Refine is out of scope for per-target settings by ruling, so in place
  costs it nothing that a spec promises.

*Conditions I would attach, and I would not ship it without them:*
1. The three parts of 4e — outside-only question, filing as the primary button,
   and a *"Keep this in a project"* button on the result window (4f).
2. `Refine_Strips_` gains `_<n>_` numbering so nothing in the user's folder is
   ever overwritten (F4).
3. A write failure at the point of producing a result must be a **window**, not
   a log line, when the folder is not ChromIQ's own (§4b).
4. Guided refinement must refuse, with a sentence, when there is no chart beside
   the measurement, instead of silently using the loaded one (§4a.2).

*Reasons for NOT taking it in Build Profile:*
* It contradicts a confirmed specification — Build Profile's store is
  `runs/runN/meta.json`, and in place has none.
* Six other Run-shaped outputs have nowhere to go.
* The thing produced is kept, not read once.

*The option of doing neither, stated fairly.* Doing nothing leaves F3 standing:
Check & Refine silently makes a chartless project for every outside `.ti3`, and
then tells the user the profile is missing (driven, §2). That is worse than
either option. **If Basti does not want option (B), option (A) alone is still an
improvement — but then the "no chart, no ICC" problems of §2 must all be
answered, and they are the harder half.**

## 5. The wording (§M-PROPOSED drafts)

Every string below is new. New user-facing message text is governed by §M of
`unified_measurement_management.md`, so the windowed ones go to **§M-PROPOSED**
first and are not written into the tab until approved
(`tests/test_message_catalogue.py` enforces it). The button labels, field
messages and log lines are not §M windows; they are listed separately so the
translator sees the whole set at once.

House rules followed: no Markdown in the strings
(`feedback_no_markdown_in_message_strings`), no em dashes, explicit singular and
plural rather than "(s)", placeholders as part of the key.

### 5a · The one question, and its three answers

Reuses `ui/dialogs/project_picker.choose_project` with `accent="#9f82ff"`.

**Window title and body**

> `tr("Where should this measurement go?")`
>
> `tr("This measurement is not in one of your projects yet. Choose the project it belongs to and ChromIQ will open it and ask which run to file it in, so the check and everything it produces are kept with the rest of that work. Or check the file where it is, and the report is written next to it instead. Either way the file you picked is never moved or changed.")`

**Buttons**

* `tr("File it in this project")` (primary, violet)
* `tr("Make a new project instead")`
* `tr("Just check it where it is")`
* `tr("Cancel")`

**When the working folder holds no projects**, `choose_project` is skipped and
the name box is shown with the same third answer beneath it:

> `tr("You do not have any projects yet. Give this one a name and ChromIQ will make the project and put the measurement in its first run. Or check the file where it is, and nothing is filed anywhere.")`

### 5a-i · Two things "in Check & Refine's violet" does NOT get for free

Built and grabbed: `10-picker-in-violet.png` is the real
`choose_project` dialog with `accent="#9f82ff"` passed.

**The primary button turns violet; the selected row stays cyan.**
`tint_dialog_primary` restyles `#primary` only, and the list's highlight comes
from the app-wide stylesheet: `QListWidget::item:selected { background: {ACCENT} }`
with `ACCENT = SPEC_CYAN` (`ui/styles.py:203-206, 38`). So a Check & Refine
picker arrives with a violet button above a cyan-highlighted list. That is not
wrong, but Basti asked for the tab's accent and would notice. Fixing it means
one extra rule set on the dialog, not a change to the global sheet.

**The third answer is a real change to `choose_project`, not a parameter.**
The dialog builds exactly three buttons in fixed positions
(`ui/dialogs/project_picker.py:218-245`) and its comment records that the order
is Basti's ruling: *"the thing you came to do first, then the alternative, and
Cancel on the very right"*. Adding *"Just check it where it is"* means an
`extra_answers` argument and a re-run of `_width_the_buttons_need`, which report
20 §6a measured at 697 px minimum in German with three buttons. A fourth will
push that floor up, and it must be re-measured in all thirteen languages before
it ships, not after.

### 5b · M-CHECK-IN-PLACE · PROPOSED · checking a file where it lies, first time only

*Shown once per session, the first time somebody chooses "Just check it where
it is". It exists because a folder called "reports" appearing in somebody's own
folder is genuinely unexpected, and because two things the tab can normally do
will not work. It carries the same escape §6d gives its warning, so a person
working through a stack of files is not asked twice.*

> **ChromIQ will write the report next to your measurement**
>
> Nothing is copied into a project. The check runs on the file exactly where it is, and the report is written into a folder called "reports" beside it, at:
>
> {folder}
>
> Two things to know before you choose this. The check itself is complete and the numbers are exactly the ones you would get from a filed measurement, so nothing is lost there. But this check will not join the history of any project, so a year from now nothing will connect it to the profile it was about. And guided refinement needs the chart the measurement was made from, which is not here, so that button will not be available.
>
> You can change your mind afterwards. The result window offers to keep this in a project, and it brings the report with it.
>
> ☐ Do not ask again this session

Buttons: `tr("Check it here")` (primary) and `tr("Cancel")`.

### 5c · M-CHECK-NO-PROFILE · PROPOSED · no profile was found beside the measurement

*Replaces the current "Profile Not Found" window
(`ui/tabs/tab_check_refine.py:1261-1268`), which explains a fix, closes, and
leaves the person to do the thing it described. This one does the thing.*

> **ChromIQ could not find a profile to check this measurement against**
>
> A profile check needs two files: the measurement, which you have chosen, and the ICC profile you want to check it against. ChromIQ looked for one next to the measurement and in the run it belongs to, and there is none there.
>
> If you know where the profile is, choose it now. If you were expecting ChromIQ to have built one already, the profile is built on the Build Profile tab, and it will appear here on its own once it exists.

Buttons: `tr("Choose the profile")` (primary, opens the same file dialog the
`ICC / ICM profile:` browse button opens) and `tr("Not now")`.

**And the field itself says so**, so the window is never the only notice:

> `tr("No profile found yet. Use the button on the right to choose one.")`

### 5d · M-CHECK-REPORT-FAILED · PROPOSED · the report could not be written

*Today a failed report write is one line in a log panel the user can switch off
(§4b). Inside a ChromIQ project a write failure is nearly impossible; beside
somebody else's file it is the expected case, so it needs a window.*

> **The check finished, but the report could not be saved**
>
> The numbers above are correct and complete. What failed was writing them to a file.
>
> ChromIQ tried to write into:
>
> {folder}
>
> and the reason it could not was: {reason}
>
> This usually means the folder is read only, is on a disc that has been disconnected, or belongs to somebody else. Nothing has been changed there.
>
> You can save the report somewhere else, or file the measurement in a project and run the check again there, where ChromIQ always has somewhere to write.

Buttons: `tr("Save the report somewhere else")` (primary, a save dialog),
`tr("Keep this in a project")`, `tr("Close")`.

### 5e · M-CHECK-REFINE-NO-CHART · PROPOSED · guided refinement with no chart beside the measurement

*`TabMeasure.start_guided_refinement` (`ui/tabs/tab_measure.py:4508-4512`) does
nothing at all when there is no `.ti2` beside the `.ti3`, and then measures
against whichever chart the Measure tab happens to hold. Refusing is the honest
answer, and it is the same reasoning §I.9 gives for refusing to re-pair
patches.*

> **Guided refinement needs the chart this measurement was made from**
>
> Refinement re measures the strips that came out worst, which means ChromIQ has to print and read the same patches again, from the same chart. That chart is not next to this measurement, so there is nothing to re measure from.
>
> The list of strips to refine has still been saved, so nothing is lost:
>
> {file}
>
> If you have the chart, put it in the same folder as the measurement, with the same name and a .ti2 ending, and try again. If the measurement belongs to a project run, open that run instead and the chart is already there.

Button: `tr("Close")`.

### 5f · M-CHECK-KEEP-IN-PROJECT · PROPOSED · filing an in-place check afterwards

*The button that makes in place a deferral rather than a fork (§4f). Shown from
the result window and from M-CHECK-REPORT-FAILED.*

Button label: `tr("Keep this in a project")`.

On success, the window that confirms it, with count-aware plurals:

> **Filed in {run} of "{project}"**
>
> The measurement has been copied in, and the file you picked is exactly where it was and exactly as it was.
>
> The report from this check came with it, so the whole record is in one place now.

…and the plural variants for the reports carried across:

* `tr("The report from this check came with it, so the whole record is in one place now.")`
* `tr("The {n} reports beside your measurement came with it, so the whole record is in one place now.")`

### 5g · Not §M windows: labels, field messages and log lines

| Where | String |
|---|---|
| picker button | `tr("File it in this project")` |
| picker button | `tr("Make a new project instead")` |
| picker button | `tr("Just check it where it is")` |
| result window | `tr("Keep this in a project")` |
| ICC field | `tr("No profile found yet. Use the button on the right to choose one.")` |
| reveal button tooltip | `tr("Show these files in the Finder")` (platform name via the existing helper) |
| log | `tr("[OK] Filed in {run} of \u201c{project}\u201d. The file you picked is untouched.")` |
| log | `tr("[OK] The profile from {run} was copied in with the chart.")` |
| log | `tr("[OK] Checking the file where it is. The report will be written to {folder}.")` |
| log | `tr("[OK] Quality report saved: {folder}/{name}")` *(exists)* |

**One count-aware pair for the run picker**, because the existing button strings
were the ones report 20 §6b found untranslated in eleven languages. Whatever is
built must add these to every catalogue with real translations, and the guard
report 20 §6c asks for (a short string whose value equals its key is a failure)
would catch it if it happened again.

## 6. What could go wrong that nobody has thought of

Each row was driven where a drive was possible; the evidence file is
`08-edge-cases.txt`.

### 6a · The cases the brief named

**1. A `.ti3` already inside a DIFFERENT project.**
`_project_root_for` returns that project's root, so `resolve_ti3` hands the file
back unchanged and **no question is asked**:

```
E1 · _project_root_for -> …/ChromIQ/Demo-Full-RGB  => returned unchanged
```

Under the naive design this is the *right* outcome for the file and the *wrong*
outcome for the bar: the tab would check Demo-Full-RGB's run 2 measurement while
the bar names some other project. **The design must handle it explicitly:** when
the file is inside a project that is not the open one, ChromIQ opens that
project and points the bar at that run, with a log line saying so. No window.
That is the "one way to open a project" rule §I.9 states for the load control.

**2. A read-only source.** `shutil.copy2` succeeds and **copies the mode**:

```
E6 · copy2 of a read-only file: OK, mode 0o444
```

So the filed measurement inside the run is read only too, and a later
`chartread` or an averaging step that wants to write `<stem>.ti3` fails with a
`PermissionError` far from the cause. **The design should `chmod` the copy to
the run's normal mode after filing**, or use `shutil.copyfile` plus an explicit
`copystat` of the timestamps only. Not a blocker, but a real trap.

**3. A file on a network volume that disappears.** Two moments matter. Before
the check, `parse_ti3` raises and `assess` turns it into a clean refusal
(`workflow/measurement_import.py:69-73`). After it, the report write raises
`FileNotFoundError` and is swallowed (§4b). The design's answer is
M-CHECK-REPORT-FAILED.

**4. The same file imported twice.** `assess` accepts it, because it is a
genuine measurement of that chart:

```
E3 · the run's OWN measurement assessed against its OWN chart: ok
```

So a second import of the same file makes a second run holding an identical
measurement, with no notice. **Not wrong** (a person may deliberately want two
runs from one measurement), but it should be *said*: if the chosen run already
holds a byte-identical file, the window that offers to make a copy should say
so rather than describing it as a new result. Nothing in the code compares
content today.

**5. A measurement whose patch count matches no chart in the chosen run.**
Handled correctly, and the message is good:

```
E4 · REFUSED | 225 of 240 patches do not hold the colour the chart asked for,
     so the readings may not line up with the chart
```

**6. A calibration target selected in the bar.** §I.9 is explicit: *"A
calibration run still cannot import"*, for a data-safety reason (one `cal/` per
project, `Calibration.reset()` has no `old/` archive). **The Check & Refine door
must inherit that refusal, not invent an exception**, and the shared helper must
therefore be told the run type rather than assuming profiling. Note that
`_file_into_project` currently *asserts* profiling
(`ui/tabs/tab_profile.py:4507`) because Build Profile is disabled for
verification runs. Check & Refine is **not** disabled for them, so the
assumption does not transfer. **This is the single most likely way to build the
feature wrong.**

**7. A verification run.** `ui/main_window.py:1590` disables Build Profile for
verification runs; Check & Refine stays enabled, and checking a profile while a
verification run is selected is a legitimate thing to do. But filing a
*profiling* measurement into a verification selection is not. The design's
answer: while the bar's run type is Verification, the Check & Refine load
control offers **only** "check it where it is" and "file it in a profiling run
of this project", and the second sets the run type explicitly, exactly as
`:4505-4513` does and for the reason recorded there.

**8. The file being the run's own measurement already.** Covered by case 1: no
question, no copy, bar already right. This must be a fast silent path, because
it is the commonest case in the whole tab.

### 6b · Cases the brief did not name, found by driving

**9. A complete project that lives outside the working folder.** Someone copies
a project to a USB stick, or changes the custom output path in Settings, and
then browses a `.ti3` inside it:

```
E2 · the file is a run measurement of a REAL project: True
     _project_root_for -> None
     => ChromIQ treats a complete project as a loose file and offers to import it
```

`_project_root_for` (`ui/ti2_loader.py:1077-1086`) requires the path to be under
`working_dir` **before** it looks for `project.json`. So a real project outside
the working folder is invisible as a project, and every loader in the app offers
to import a copy of it into a second project with a different name. **The fix is
one line in the right place** (look for `project.json` walking up, and only then
ask whether it is under the working folder) but it changes behaviour in five
loaders, so it is not this design's to make. **Reported, open question 7.**

**10. F5 · A chosen existing run with no chart accepts anything.** Driven:

```
made run6 - chart_ti2 exists: False
assess(a 1-patch file, a run with NO chart) -> ACCEPTED | n_chart: 0 | n_measured: 1
```

`_chart_patch_count` returns 0 for a missing chart, which means "do not judge by
count" (`workflow/measurement_import.py:117-121`, correct on its own), and
`verify_patch_identity` reports "not checked", which `assess` logs and passes
(`:107-111`). The "There is no chart to check this measurement against" guard
exists but sits **inside `if run is None:`**
(`ui/tabs/tab_profile.py:4436-4446`), so it protects the *new run* answer and
not the *chosen run* answer. This is the fault §I.9's own comment says was
fixed: *"a six-patch file bearing no relation to anything went into a real
project with not one word on screen."* It was fixed for one of the two branches.
**Shipped code, reported, not fixed here.**

**11. F1 · A refused import leaves a run behind.** §0, §2 breakage 3.

**12. F2 · `<stem>.print.json` is dropped by every duplication.** §0, and it
means the §2b converted-sheet guard stops firing on any duplicated run,
including every run §I.9's import creates. Driven:

```
FULL duplicate copies .print.json?       False
CHART-ONLY duplicate copies .print.json? False
read_print_record on run1     : {'colour': 'through', …}
read_print_record on the COPY : None
```

**13. F4 · `Refine_Strips_<stem>.txt` overwrites without archiving.** §4c.

**14. Two histories numbered from 1.** If someone checks in place and later
files the measurement, `Quality_Check_1_…` exists in two places for the same
profile with nothing linking them (§4f).

**15. A stem that is not a filename ChromIQ would have chosen.** In-place
writes use `self._ti3_path.stem` raw (`ui/tabs/tab_check_refine.py:1372`), with
no `_sanitise`. Safe on macOS, unverified elsewhere.

## 7. Numbered implementation plan and module map

Nothing below is written yet. Steps 1 to 3 are prerequisites and can be built
before any of Basti's open questions are answered; steps 4 onward depend on
answers 1 to 3.

### 7a · Module map, reuse versus new

| # | Thing | Today | Under this design |
|---|---|---|---|
| 1 | `_offer_import_into_a_project` | `ui/tabs/tab_profile.py:4235`, a method on `TabProfile` | **moves** to `ui/measurement_filing.py`, a free function `offer_import_into_a_project(parent, measurement, fm, ctl, *, accent, run_type, extra_answers)` |
| 2 | `_file_into_project` | `ui/tabs/tab_profile.py:4311` | **moves** with it, as `file_into_project(...)` |
| 3 | `choose_project` | `ui/dialogs/project_picker.py:144`, already takes `accent` | reused, `accent` finally passed |
| 4 | `ask_for_project_name` | `ui/dialogs/name_prompt.py:155`, already takes `accent` | reused |
| 5 | `_build_run_picker` / `_attach_run_picker` | `TabChart` | reused through `self.window()._tab_chart`, unchanged |
| 6 | `assess` | `workflow/measurement_import.py:60` | reused, called **earlier** (F1) |
| 7 | `resolve_ti3` | `ui/ti2_loader.py:1028` | **no longer reached from Check & Refine**; still the Build Profile fallback |
| 8 | `TabCheckRefine.set_target_controller` | absent | **new**, ~4 lines, stores the reference only (§3) |
| 9 | in-place check | absent | **new**, and it is mostly the absence of code: skip the filing helper |
| 10 | `write_refine_strips` | `workflow/profcheck_runner.py:455` | **changed** to `write_named_report`-style numbering (F4) |
| 11 | reveal button on Check & Refine | absent | **new**, copied from `ui/tabs/tab_profile.py:4200` |
| 12 | `workflow/measurement_messages.py` | the §M catalogue | **new** entries once §M-PROPOSED is approved |

**The lift in rows 1 and 2 is not optional.** `ui/tabs/tab_profile.py:4356-4363`
records that the run picker's signal was once left unconnected and *"EVERY
import went to 'a new run' no matter what was selected on screen"*. A copy is
how that comes back.

### 7b · The steps

1. **Lift `_offer_import_into_a_project` and `_file_into_project` into
   `ui/measurement_filing.py`** as free functions taking `(parent, measurement,
   fm, ctl)` plus keyword arguments for `accent`, `run_type` and the extra
   answers a caller wants in the picker. `TabProfile` keeps two thin methods
   that call them, so its behaviour is byte-identical. **No behaviour change in
   this step**, and the existing tests
   (`tests/test_import_routing_and_run_choice.py`) must pass untouched.
2. **Fix F1 in the lifted code**: move `assess()` above `duplicate_run`, so a
   refused import creates nothing and the window's *"nothing has been changed"*
   is true. This is a behaviour change to shipped code and needs the
   report-and-approve step, but it is a correction of a false statement, not a
   design choice.
3. **Give `TabCheckRefine` a `set_target_controller`** that stores the reference
   and nothing else, and add it to the tuple at `ui/main_window.py:305-306`.
   Prove inertness the way §3 did: no `changed` connection, no
   `load_target_settings`, and the tab's whole surface unchanged.
4. **Rewrite `_on_browse_ti3`** as the fork in §1: inside a project (open it if
   it is not the open one, move the bar, done); outside, call the shared helper
   with the violet accent and the third answer.
5. **Carry the sibling `.icc`/`.icm`** in the shared filing helper, as
   `_copy_ti3_only` (`ui/ti2_loader.py:1593-1598`) already does.
6. **Copy the source run's `profile` group with its `chart` group** for the
   Check & Refine door, *if* open question 1 is answered yes.
7. **Replace `_auto_fill_icc`'s modal** with M-CHECK-NO-PROFILE plus the inline
   field message (§5c).
8. **Add the in-place path**: no copy, no project, report beside the file,
   M-CHECK-IN-PLACE once per session, and the guided-refinement refusal
   (M-CHECK-REFINE-NO-CHART).
9. **Add the "Keep this in a project" button** to the result window, running the
   same shared helper and carrying the in-place `reports/` across (§4f). This is
   what makes step 8 safe to ship.
10. **Make the report write failure a window** (M-CHECK-REPORT-FAILED) when the
    folder is not under the working folder.
11. **Number `Refine_Strips_`** so nothing in a user's own folder is ever
    overwritten (F4).
12. **Add the reveal button** to Check & Refine.
13. **Translate everything**, in the same commit, and add the report 20 §6c
    guard (a short UI string whose value equals its key is a failure) so the
    eleven-language regression cannot repeat.
14. **Amend the specifications**, once and only once Sebastian has ruled:
    §I.9's "Where the door is", §I.9's chart-only clause if question 1 is yes,
    §6c's `profcheck` row if question 2 is yes, and `ui/file_guide.py` if in
    place ships.
15. **Tests.** The three that would have caught the faults found this round:
    a refused import leaves no run (F1); a chosen existing run with no chart is
    refused (F5); a duplication carries `<stem>.print.json` (F2, if it is
    fixed). Plus: the in-place path creates nothing under the working folder,
    and the Check & Refine picker really is violet.

## 8. Open questions for Basti / Sebastian

Numbered so they can be answered by number. Questions 1 to 3 block code;
4 to 8 do not, but the answers should be known before the feature ships.

**1. May a Check & Refine import copy the run's PROFILE as well as its chart?**
*(Sebastian, specification.)* §I.9 says `duplicate_run(source, groups=("chart",))`
and gives its reason: a copied profile would be orphaned the moment the import
overwrote the `.ti3`. For a Check & Refine import the profile is not orphaned;
it is the second thing the tab needs to do its job, and without it the import is
followed immediately by "no profile found". Extending the group to
`("chart", "profile")` for this door only would amend that clause.
**Without an answer here, step 6 is not built and the design falls back to
"carry the sibling `.icc`, otherwise ask".**

**2. May Check & Refine be a third import door at all?**
*(Sebastian, specification.)* §I.9's "Where the door is" names two tabs and
gives a reason. Adding a third amends it. Two facts for the ruling: the tab
already imports today and does it worse than anywhere else in the app (F3, §2
breakage 4), and §6c's description of `profcheck` as checking "the data it was
built from" would want one clause added if a foreign measurement becomes a
first-class input.

**3. Is "check the file where it is" approved, and is "build the profile where
it is" refused?** *(Basti, then Sebastian for the spec text.)* My
recommendation, with reasons, is §4h: yes to check, no to build, because
`per_target_settings.md:368` requires Build Profile to have a store at
`runs/runN/meta.json` and in place has none, and because six other Run-shaped
outputs have nowhere to go. **I would not ship "check in place" without the
"Keep this in a project" button (§4f), and I would say so at the time of the
ruling rather than after.**

**4. When an in-place check is later filed, should its reports come with it?**
*(Basti.)* My recommendation is yes: without it, the same profile ends up with
two report histories both numbered from 1, in two folders, with nothing linking
them. Against it: it copies files the user did not ask to be copied.

**5. What should the wording of M-CHECK-IN-PLACE promise about "a year from
now"?** *(Basti, tone.)* The draft in §5b says the check "will not join the
history of any project". That is honest, and it is also the sentence most
likely to talk somebody out of a feature they asked for. It should be read
aloud before it is approved.

**6. Should Check & Refine get a reveal button?** *(Basti.)* Every other tab has
one (Knut's consistency point, `ui/tabs/tab_profile.py:4200-4202`). It becomes
much more useful once files can land in two different kinds of place.

**7. Should `_project_root_for` recognise a project that lives outside the
working folder?** *(Basti.)* Edge case 9: a real project on a USB stick, or
after the custom output path changes in Settings, is invisible as a project to
every loader in the app, and each offers to import a copy of it. It is a small
change in one function and a behaviour change in five callers, so it is its own
piece of work, not this one.

**8. Do F1, F2, F4 and F5 get fixed now, or tracked?** *(Basti.)* All four are
in shipped code and none was introduced by this design. F1 makes a §M window say
something untrue; F5 is the "six-patch file" fault fixed on one branch of two;
F2 silently disables the §2b converted-sheet guard on every duplicated run;
F4 overwrites a file the user may have edited. F1 and F5 sit in the code this
design lifts, so they are cheapest to fix during step 1 or 2. F2 and F4 are
independent.

---

## Where I am NOT certain, said plainly

* **Quarantined downloads** (`com.apple.quarantine`) were not tested. I expect a
  write beside such a file to succeed, because the attribute gates execution
  rather than directory writes, but I did not prove it and it should be tested
  before shipping.
* **iCloud Drive and Dropbox** were reasoned about from the non-atomic
  `write_text` in `workflow/profcheck_runner.py:436`, not driven against a real
  sync client. The non-atomicity is proved; the consequence for a specific sync
  client is not.
* **Windows and Linux** filename rules were not considered beyond noting that
  the in-place stem is not sanitised.
* **Whether F2 is a defect or a deliberate omission** I do not know. Nothing in
  `DUPLICATE_GROUPS` or its comments mentions `.print.json`, which reads like an
  oversight rather than a decision, but `verification_print.py` is Feature A's
  code and its author may have had a reason.

## STATUS: complete

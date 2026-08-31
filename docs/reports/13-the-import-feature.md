# Importing a measurement into the open project — the design

STATUS: in-progress — design for challenge, no code written

Basti approved (2026-08-31), and §I of `unified_measurement_management.md` now
carries the amendment (`⏳ Awaiting confirmation`, **Amendment approved by:
Sebastian, 2026-08-31**):

* **§I.9** — a PROFILING run may be an import destination. Calibration still
  cannot (one `cal/` per project, `Calibration.reset()` has no `old/` archive).
* **§I.10** — a partial measurement is FILED, not refused, with both counts
  stated. More readings than patches is still refused: that is a different
  chart, not a partial one.
* Entry point: **the Build Profile tab**, because it is disabled for
  verification runs (`ui/main_window.py:1590`) — so the tab you are on already
  says which act you are performing. Basti: *"clicking the button should allow
  me to do the import there instead of skipping around"*.

## What already exists — reuse, do not rebuild

| Piece | Where |
|---|---|
| The whole IMPORT sequence for verifications | `ui/tabs/tab_measure.py:10246 _on_import_measurement` — guards → convert → validate → dated folder + chart snapshot → file → say where it went |
| i1Profiler → `.ti3` conversion | `workflow/reference_convert.py` (`.mxf`/`.cxf` direct; `.txt` via `txt2ti3`) |
| The pairing check | `workflow/measurement_report.py:236 verify_patch_identity` |
| Run creation / duplication | `core/file_manager.py:1954 new_run`, `:2048 duplicate_run`, `:2021 duplicate_run_plan` |
| The run picker | `ui/measurement_target_bar.py` |
| Where a measurement belongs | `Run.measurement_ti3` — the run's canonical stem |

**The import module is heavily coupled to the Measure tab** — nine tab helpers
(`_verification_guard`, `_snapshot_verification_chart`, `_show_import_refusal`,
its own log pane…). So the plan is to lift the NON-UI core out, not to copy it.

## The design, to be challenged

1. **`workflow/measurement_import.py`** (new): the act, with no Qt. Takes a
   source file, a destination `Run`, and the run's chart; converts, validates,
   files, and returns a result object describing what happened (counts, the
   pairing verdict, where it landed). Raises nothing the caller cannot render.
2. **Both tabs present it.** Measure keeps its verification flow; Build Profile
   gains "Import a measurement" on the load control it already has. No tab
   switching.
3. **The pairing is REPAIRED, not merely detected.** The measured result: 100 %
   of patches recovered colour-equivalently from a fully shuffled measurement,
   96.7–99.4 % onto their exact original position. Basti's ruling makes the
   remainder harmless — patches asked to be the same colour are
   interchangeable. The multiset of device values separates the three cases:
   identical → re-pair and proceed; strict subset → partial, re-pair what is
   there and state both counts; neither → refuse, it is a different chart.
4. **A run that already holds a measurement is not displaced** — `duplicate_run`
   into a copy, per §I.9.

## Numbered open questions
1. Does the extraction of the Measure tab's core risk its verification flow,
   which is specified and hardware-confirmed (Sebastian, 2026-08-10)?
2. Should re-pairing be automatic, or offered? It changes data ChromIQ then
   builds a profile from.
3. What does the user see for a partial — a window, or a line in the report?
4. Where exactly in Build Profile does this live, and what is it called?
5. Does the imported `.ti3` need the original `.txt`/`.mxf` kept beside it?

---


# Challenge

**STATUS: in progress** — written section by section as each was measured.
2026-08-31. **No source file was changed.**
Proof: `~/Desktop/knut-import-feature/` (see its `INDEX.md`).
Settings were sandboxed to `/tmp/knut-import-sandbox/settings.ini` via
`CHROMIQ_SETTINGS_FILE` for every drive; the owner's own projects were
**copied** into `/tmp/knut-import-sandbox/work/` and never opened in place.
`~/Desktop/i1Profiler` was read only, and every source file's SHA-256 was
checked unchanged after use.

Skeleton, filled in below:

* **E0** — verdict up front
* **E1** — requirements analysis and the assumptions this rests on
* **E2** — the extraction: what is separable, and what proves the verification
  flow unchanged
* **E3** — re-pairing: three measured facts that change the design
* **E4** — partials: where the user is told, and the exact words
* **E5** — the destination run: `duplicate_run`, measured
* **E6** — the entry point in Build Profile
* **E7** — the journey, click by click, and where every file lands
* **E8** — what already exists that this must not duplicate
* **E9** — what I would do differently, including doing less
* **E10** — i18n
* **E11** — open questions only the owner can answer
* **E12** — rating

---

## E0 · Verdict up front

The destination model in report 13 is right and I am not attacking it: the bar
chooses the run, the file is copied never moved, the run's own stem is the
filed name. Four things in it are wrong or unbuilt, and three of them are
measured rather than argued.

1. **The re-pairing rule as written cannot be implemented as written, and the
   safety net named for it is a tautology.** Report 13 §3 says *"The multiset
   of device values separates the three cases: identical → re-pair and
   proceed"*. On ChromIQ's **own** `.ti2`/`.ti3` pair — `Demo-Switching` run 1,
   a file ChromIQ wrote from a chart ChromIQ wrote — the two device multisets
   are **not** identical: 23 of 240 values differ in the fourth decimal place,
   so an exact multiset test lands on *"neither"* and refuses. It has to be a
   **tolerant** match, and a tolerant match is a different animal: on the
   owner's own Red River charts, 47 pairs of patches lie within
   `PATCH_IDENTITY_TOL` of each other in device space while their **design
   colours differ by up to ΔE00 16.24**. Basti's ruling — *patches asked to be
   the same colour are interchangeable* — does not reach those, because they
   were not asked to be the same colour. **E3.**

2. **`verify_patch_identity` cannot validate a repair.** It compares the
   chart's device values with the measurement's device values. A repair
   assigns rows *by* device values. Measured: before a repair on shuffled real
   data `worst = 100.0, verdict = mismatch`; after it, `worst = 0.0001,
   verdict = verified` — and it is 0.0001 for **every** repair, right or wrong,
   because equality is what the repair produced. Report 08 C15's robustness
   claim, *"a bad repair cannot file"*, does not hold. **E3(c).**

3. **§I.10 and re-pairing together remove both existing guards against
   importing into the wrong run — and there are real files on this machine
   that walk through the hole.** Of 24 distinct charts under `~/ChromIQ`,
   **four pairs** have one chart's device multiset a strict subset of
   another's. The worst is the owner's own production set: a measurement of
   `Red-River…A4-2052p` (2060 patches) offered against the `Letter-2052p`
   run (2064) passes as *"2060 of 2064 came back"* — a different sheet size,
   filed with a friendly notice. Today it is refused on patch count. **E3(d).**

4. **§I.9's "duplicate the run and file into the copy" produces a run that
   contradicts itself, and I ran it.** On the owner's real run 1,
   `duplicate_run` copies the measurement (3 files, 41 911 B), the profile
   (111 712 B), 2 reports and an export sidecar. The import then overwrites
   the measurement, leaving `reads/read1.ti3`, `reads/read2.ti3`,
   `Demo-Switching.icc`, `reports/report_*.json` and
   `reports/Quality_Check_1_*.txt` describing a measurement that is no longer
   there — while `duplicate_run_plan`'s confirmation window has just told the
   user those files are being copied *for* them. **E5.**

And one conformance point that must be settled before code, not after:

5. **Report 13's entry point is not what §I.9 says.** §I.9, as approved,
   reads *"The IMPORT module is offered while the shared Run type is
   **Profiling** as well as **Verification**"* — and §I's opening defines the
   IMPORT module as *"A third mode on the Measure tab — GUIDED · MANUAL ·
   IMPORT"*. Report 13 §2 instead says *"Both tabs present it… Build Profile
   gains 'Import a measurement'"*. Those are different specifications. Basti's
   quoted steer supports the Build Profile door, so the amendment needs one
   more clause saying so — **reported, not fixed** (CLAUDE.md). **E6.**

**Recommended shape in one sentence:** build §I.9's profiling destination and
§I.10's partial filing, put **one** routing question on the load control Build
Profile already has, and **do not build automatic re-pairing in this change** —
detect the reorder, name it, and offer it as a separate deliberate act with a
number the user can judge.

---

## E1 · Requirements analysis, and the assumptions it rests on

### What is actually being asked for

> Basti: *"clicking the button should allow me to do the import there instead
> of skipping around"*

Read against what the app does today (report 08 §1, re-verified below), the
requirement is **not** "add an import capability". It is:

**R1.** A measurement chosen from outside every project must be able to land in
the **open** project instead of manufacturing a new one.
**R2.** The person must be able to do that **from the tab they are already on**
when they are about to build a profile.
**R3.** The run it lands in is chosen the way runs are always chosen — the bar.
**R4.** A run that already holds a measurement must not be displaced (§I.9).
**R5.** A partial measurement is filed with **both counts stated** (§I.10).
**R6.** Calibration is out (§I.9, data-safety reason).
**R7.** The user's own file is never moved or modified.

### Assumptions, stated so they can be refused

| # | Assumption | Status |
|---|---|---|
| A1 | The bar is the only place a destination run is chosen; no new combobox | inherited from report 08 C2, unchallenged, and I agree |
| A2 | A measurement's identity is its **device values**; the chart supplies `SAMPLE_ID`/`SAMPLE_LOC` | true for `.mxf`/`.cxf` — verified on the owner's three real files (E3a) — and **false for 2 521 of the 2 550 `.txt` files in `~/Desktop/i1Profiler`**, which carry no device columns at all |
| A3 | An imported measurement is colorimetrically usable wherever its device values match | **partly false**: a measurement is a set of *(device asked, colour returned)* pairs, so matching device values do **not** establish that the same printer, ink and paper produced them. Nothing in this design checks that, and nothing today does either |
| A4 | `verify_patch_identity` can act as the final gate on a repair | **false** — E3(c) |
| A5 | `duplicate_source()` is a safe gate for "can this run be duplicated" | **false** — it has no calibration branch; measured, E5 |
| A6 | `location_being_edited()` returns `""` when no project is open (report 08 C9 case 1) | **false** — measured: it returns an invented placeholder, `work/Printer_Paper_Type_Instr_2026-08-31_14-08/runs/run1/` |
| A7 | `colprof` builds silently from 4 patches and needs a white patch | accepted from report 08 D5/D6 as prior measurement; not re-run here |

### The one requirement nobody has written down

**R8. The import must say which run it is filing into, in words, at the moment
of choosing.** This is not decoration. Measured in the running app: with the
bar on `run3` (no measurement), the Build Profile tab goes on displaying
`runs/run2/Demo-Switching.ti3` and its Build button stays enabled —

```
bar=run1  run has ti3=True  | tab shows: …/runs/run1/Demo-Switching.ti3
bar=run2  run has ti3=True  | tab shows: …/runs/run2/Demo-Switching.ti3
bar=run3  run has ti3=False | tab shows: …/runs/run2/Demo-Switching.ti3
bar=run4  run has ti3=False | tab shows: …/runs/run2/Demo-Switching.ti3
bar=run5  run has ti3=False | tab shows: …/runs/run2/Demo-Switching.ti3
```

(`proof/drive/D4-follow-the-bar.txt`.) That is deliberate — `M-BUILD-ELSEWHERE`
is the approved window for exactly this divergence, and its own text says
*"switching 'Profile run' in the bar loads it for you when the run has one"*.
But it means **an import door in Build Profile sits on a tab that is showing a
different run's measurement from the one the import will write into**, in the
most common destination state of all: an empty run. Every wording in E7 names
the run for that reason.

---

## E2 · The extraction — is the core separable?

`_on_import_measurement` is `ui/tabs/tab_measure.py:10246-10341`. Read in full,
with every helper it reaches. **The answer is: a small core is separable, the
plan over-states how much of it, and the risky part is not the part being
lifted.**

### Every piece of tab state it touches, and what happens to each

| # | Touched | Line | Kind | What must happen to it |
|---|---|---|---|---|
| 1 | `self._runner.is_running` | :10252 | injected singleton | stays in the tab (a re-entrancy guard, not import logic) |
| 2 | `self._target_ctl` → `ctl.target.profile_run` / `.verification_id` | :10254, :10277, :10314 | bar controller | **becomes parameters**: `(run, verification_id)` |
| 3 | `self._blocked_by_new_run()` | :10257 → :5709 | opens a `QMessageBox`, reads `ctl` | stays in the tab. Note it is **not** in `WINDOW_SOURCES` and writes its own title |
| 4 | `self._verification_guard()` | :10259 → :1644 | returns a §M `Message` | half core (which message), half tab (showing it). Reads `_is_verification_run()` **and** `_guard_run()` |
| 5 | `self._guard_run()` | :10263 → :1620 | ctl **plus `self._ti1_path`** | ⚠ **the coupling that matters** — see below |
| 6 | `self._import_path` | :10266 | the chosen file | becomes a parameter |
| 7 | `self._say_on_screen(...)` | :10268, :10294 | a `QMessageBox` writing its own prose | stays; ⚠ **not in `WINDOW_SOURCES`**, and its two import strings are prose written outside §M |
| 8 | `self._show_import_refusal(M…)` | :10261, :10279, :10305, :10320 | §M window | stays in the tab (it is in `WINDOW_SOURCES`) |
| 9 | `self._settings.get("argyll_bin_path")` | :10289 | settings | becomes a parameter |
| 10 | `run.ensure_cache_dir()/"import"` | :10292 | `core.file_manager` | already core |
| 11 | `self._log.appendPlainText(...)` | :10298, :10329, :10332, and :10223 inside `_import_mismatch_reason` | the tab's log pane, **4 sites** | the core must **return** lines; both tabs then print them into their own log |
| 12 | `self._import_mismatch_reason()` | :10303 → :10200 | parse + count + identity, **plus a log write** | the true core, minus the log write |
| 13 | `self._chart_patch_count()` | :10083 | `@staticmethod`, reads the `.ti2` header | pure — moves as is |
| 14 | `self._snapshot_verification_chart()` | :10312 → :5524 | ⚠ **two windows + a bar mutation + a `meta.json` write** | **cannot move.** See below |
| 15 | `run.new_verification()`, `ensure_dir()`, `Run.measurement_ti3` | :10314-10318 | core | already core |
| 16 | `shutil.copy2` + `mark_verification_ti3` | :10326-10327 | core | moves |
| 17 | `self._update_import_panel()` | :10337 | UI refresh | stays |
| 18 | `self._ask_how_printed(dst)` | :10340 → :9811 | §M window + `workflow.verification_print` | stays |
| 19 | `self._show_import_done(...)` | :10341 | §M window, opens `MeasurementReportDialog` | stays |

**So the separable core is four steps — convert, validate, copy, stamp — about
20 of the 90 lines.** Everything else is a window, a bar mutation or a log pane.
That is still worth doing, because those four steps are exactly what the second
door needs. But "lift the non-UI core" undersells the work: the value is in
**one destination resolver and one verdict object**, not in moving `copy2`.

### The coupling the plan does not mention: `_guard_run`

`_guard_run` (`:1620`) prefers the bar, then **falls back to the loaded chart's
own run** by walking `self._ti1_path`'s ancestors up to `runs/runN`. `TabProfile`
has no `_ti1_path`; it has `_ti3_path`. So if Build Profile gets its own door
and asks its own question, **the two tabs will resolve "which run" by different
rules** whenever the bar cannot answer. That is the single highest-value thing
to extract: `resolve_import_destination(ctl, fallback_path) -> Run | None`,
used by both, so there is one answer.

### `_snapshot_verification_chart` is the trap in step 3

The plan reads I.6 as "the dated-folder front door". It is more than that
(`:5524`):

* if the run type is **not** verification it delegates to
  `_snapshot_profiling_chart` (`:5571`), which asks
  `_profiling_overwrite_choice(run)` — **a window** — and on "keep" writes
  `meta.chart_snapshot_stale = True` and logs a sentence;
* on the verification side it can ask `_chart_overwrite_choice(verification)`
  — **another window** — and it **mutates the bar** (`ctl.set_verification_id`).

Two consequences the design has to state:

1. **§I.9 as approved deletes the profiling chart snapshot by accident.** It
   says *"I.6 and I.7 become one step: the measurement is copied to
   `Run.measurement_ti3`"*. A native profiling read runs
   `_snapshot_profiling_chart` first, so `runs/runN/chart/` describes the chart
   that was measured and `chart_snapshot_stale` stays honest. An import that
   skips it leaves the run's stored chart copy unmaintained. **Reported, not
   fixed**: §I.9 needs a sentence, and I recommend *"a profiling import runs
   the same chart-snapshot step a native profiling read runs"*.
2. Calling `_snapshot_verification_chart()` from a profiling import — which is
   what the current code would do unchanged — already routes to the profiling
   branch. That is a **feature**, not a bug: the reuse is free. It just has to
   be deliberate and written down.

### What proves the verification flow is unchanged?

**What the tests do cover.** `tests/test_import_measurement_module.py` (450
lines, 15 tests) drives the **real** `TabMeasure` against a real
`MeasurementTargetController` and a real `Project`. It covers: IMPORT visible
only for verification runs (`:111`); the action-row swap (`:126`); the happy
path including the dated folder, `CHROMIQ_VERIFICATION "true"`, the bar moving
to the new folder, `has_snapshot(verification)` and the original's bytes
unchanged (`:141`); a count mismatch refused with nothing written (`:173`); a
**shuffled** measurement refused (`:191`); a dated folder that already holds a
measurement refused with the old file byte-identical (`:209`); the no-profile
guard (`:228`); and the info box naming the chart, the count and the
destination (`:243`). That is a real regression net, not an import smoke test.

**What they do not cover, proven by a mutation that is proven to land.** Both
`_capture_refusals` (`:92`) and `_silence_done_dialog` (`:100`) **monkeypatch
the two windows away**. I replaced both methods with raisers, from a pytest
plugin, without editing any source file
(`proof/mutation/mutant.py`, `proof/mutation/mutation.txt`):

```
[mutant] both IMPORT windows replaced with raisers — proven to land (identity changed)
tests/test_import_measurement_module.py  ...............   15 passed in 0.62s
tests/test_an_import_never_destroys_a_project.py ......    18 passed in 0.15s
```

**Fifteen tests pass with both IMPORT windows replaced by code that raises.**
The same mutation *does* fail `tests/test_message_catalogue.py` —

```
FAILED …[…-_show_import_refusal]
FAILED …[…-_show_import_done]
AssertionError: TabMeasure._show_import_done does not use the catalogue
```

— which is the second proof it landed, and which shows precisely what is
guarded: the **source text** references §M. Nothing guards the button order,
the default button, or the "Open measurement report" hand-off. This is the same
blind spot `tests/test_s47_window_shape.py` was written for after a challenge
pass reordered §S4.7's buttons and put Return on the destructive answer with 98
tests green.

**So, to prove the verification flow is unchanged, three things are needed and
only the first exists:**

1. the 15 existing tests, green — necessary, not sufficient;
2. **a window-shape test for the IMPORT module's two windows**, modelled on
   `test_s47_window_shape.py`: button order, `defaultButton()`, and that
   `_ask_how_printed`'s default is still *Not sure* (`tab_measure.py:9840` —
   the only safe answer, and the one that stores nothing);
3. **a byte-level before/after**: run the real import at `bd463b94` on the
   owner's real `.mxf` and record the filed tree, every file's SHA-256, and the
   verbatim text of all three windows; repeat after the extraction; diff. A
   sequence this specified deserves a golden file, not a promise.

---

## E3 · Re-pairing — three measured facts that change the design

Report 08 C5 measured re-pairing and found 100 % colour-equivalent recovery.
I did not re-run that; I attacked the parts it did not measure. All numbers
below are from the owner's own files. Scripts and raw output:
`proof/probes/p1_subset.*`, `p4_tautology.*`, `p4b_debug.*`, `p5_ambiguity.*`,
`p6_tolerant_cost.*`, `p7_knut_dup.*`, `p8_redriver.*`, `p9_group_spread.*`.

### (a) The converter really does supply what re-pairing needs — on `.mxf`

The owner's three real X-Rite measurements, converted with the shipped
`workflow.reference_convert.convert_i1profiler_measurement` and real ArgyllCMS
3.5.0 (`proof/probes/p10_convert.out`):

```
RGB_default-i1Pro.mxf   sha before/after 43e1efcfb1c73a63 / 43e1efcfb1c73a63  (untouched)
   -> n=2033  RGB columns: True  SAMPLE_ID[:5]=['1','2','3','4','5']  LOC[:5]=['1','2','3','4','5']
   TARGET_INSTRUMENT='i1Pro 2'  CHROMIQ_MEASURED='2014-08-05'
RGB_default-i1iO.mxf    -> n=2033  RGB: True   'i1iO 2'    '2014-09-18'   (untouched)
RGB_default-i1iSis.mxf  -> n=2033  RGB: True   'i1iSis XL' '2015-01-07'   (untouched)
```

`SAMPLE_LOC` is the row number, exactly as report 08 said, so re-pairing is the
only thing that can ever give an imported measurement a real square. Good.

**But the `.txt` half of the same file dialog is a different world.** Of the
**2 550 `.txt` files** in `~/Desktop/i1Profiler`, **6 carry `RGB_R`** and
**2 521 carry no device columns at all** (`grep -rl`, counts in
`proof/probes/txt-census.txt`). Most are scanner reference and ambient files
rather than printer measurements — but the load dialog's filter is
`*.mxf *.cxf *.txt *.ti3`, so they are all offered. **A measurement with no
device values cannot be re-paired at all**, and the design has no case for it:
today `verify_patch_identity` returns `checked: False, reason: "the measurement
carries no device values"` and `_import_mismatch_reason` logs
*"[INFO] The patch-identity check could not run … the import continues"* and
files it anyway. For a **verification** that is defensible. For a **profiling**
import it means filing an unvalidated measurement into a run and then building
a profile from it. **This needs a rule, and there is none. Open question 4.**

### (b) The multiset test, as written, refuses ChromIQ's own files

Report 13 §3: *"The multiset of device values separates the three cases:
identical → re-pair and proceed; strict subset → partial …; neither → refuse."*

Run that literally on `Demo-Switching` run 1 — a `.ti2` ChromIQ generated and
the `.ti3` ChromIQ's own chartread wrote from it (`proof/probes/p4b_debug.out`):

```
chart n 240   meas n 240
distinct chart keys 234   distinct meas keys 234
multisets equal? False
in chart not in meas: 23   e.g. (100.0, 26.867, 100.0), (100.0, 46.170, 18.491)
in meas not in chart: 23   e.g. (100.0, 26.868, 100.0), (100.0, 46.170, 18.490)
```

The values differ **in the fourth decimal place** — chartread's formatting, not
a disagreement. An exact multiset test lands on *"neither"* and refuses a file
ChromIQ wrote about a chart ChromIQ wrote. My first repair, written to the rule
as stated, matched **212 of 240** rows on a correct, in-order pair.

**So the match must be tolerant** — and `PATCH_IDENTITY_TOL = 1.0`
(`workflow/measurement_report.py:232`) is the natural tolerance, since it is
already the app's definition of "the same colour". That has to be written into
the design, because it changes what the design *is*: not a set relation, an
assignment problem.

### (c) After a repair, `verify_patch_identity` cannot fail

This kills report 08 C15's robustness argument — *"The repair is validated by
the app's own `verify_patch_identity` after the fact, so a bad repair cannot
file"*.

`verify_patch_identity` (`measurement_report.py:236`) compares
`design.rgb` against `measured.rgb` and **never looks at the measured XYZ**
(`:284-286`, `:311`). A repair assigns rows *by* that same comparison. Feeding
the repaired pairing back in therefore asks a question whose answer the repair
just constructed. Measured on the real file above
(`proof/probes/p4_tautology.out`):

```
RIGHT chart, rows shuffled (the case re-pairing is for)
    BEFORE repair: verdict='mismatch' compared=240 mismatched=239 worst=100.0
    AFTER  repair: verdict='verified' compared=212 mismatched=0   worst=0.0001
RIGHT chart, in order
    BEFORE repair: verdict='verified' … worst=0.0001
    AFTER  repair: verdict='verified' … worst=0.0001
```

`worst` after a repair is the repair's own matching threshold. It will be that
for a right repair and for a wrong one alike. **The post-check is a fake that
re-implements the code under test** — the exact pattern
`feedback_a_fake_that_reimplements_validates_itself` records.

A repair therefore needs a check made of something the repair did **not** use.
There is exactly one such thing in the file: the **measured XYZ**. Concretely,
and cheaply: compute mean and max ΔE00 of the *identity* pairing and of the
*repaired* pairing, and show both. A genuine reorder makes the number
dramatically better (that is what a reorder is); a repair that does not improve
it has repaired nothing and should not be trusted. That number is also the one
a human can judge, which matters for (e).

### (d) The two guards §I.10 and re-pairing remove, and the real files that walk through the hole

Today an import into the wrong run is caught by two crude tripwires: **exact
patch count** (`_import_mismatch_reason`, `tab_measure.py:10200`, `measured.n_patches
!= n_chart`) and **the identity check firing on any reorder**. §I.10 removes
the first for the "fewer" case; re-pairing removes the second. Nothing replaces
them.

Census of every `.ti2` under `~/ChromIQ` — 92 files, **24 distinct charts by
device multiset** (`proof/probes/p1_subset.out`):

```
STRICT SUBSET PAIRS (A's measurement would import into B's run as a "partial"): 4
    399 Demo-Switching.ti2                     SUBSET OF   400 Demo-Full-RGB.ti2
   2060 Red-River…A4-2052p-10pages…ti2         SUBSET OF  2064 Red-River…Letter-2052p-10pages…ti2
   2055 Red-River…Letter-2052p-9pages…ti2      SUBSET OF  2060 Red-River…A4-2052p-10pages…ti2
   2055 Red-River…Letter-2052p-9pages…ti2      SUBSET OF  2064 Red-River…Letter-2052p-10pages…ti2
NEAR MISSES (>=90% of A's values present in B):
   99.7%   940 Pro300…Jun26.ti2  vs  1176 knut.ti2
   98.8%   940 Pro300…Jun26.ti2  vs  1173 tc918eg-cm-a3.ti2
   99.1%  1173 tc918eg-cm-a3.ti2 vs  1176 knut.ti2
```

The Red River trio is the owner's own production patch set on **A4 vs Letter,
9 pages vs 10**. Under the proposed rules, a measurement of the A4 sheet
selected against the Letter run is filed as *"2 060 of 2 064 patches came
back"* — a friendly, reassuring, wrong sentence about a different sheet of
paper. Today it is refused.

**This is not an argument against §I.10.** It is an argument that the counts
alone are not a safe statement. Two cheap mitigations, neither of which needs a
threshold:

* **State the proportion, not only the counts** — "2 060 of 2 064" reads as
  complete; "4 patches short of the whole chart" reads as suspicious, and
  "300 of 1 176" reads as a third of a chart. Report 08 open question 9 asked
  for a threshold; the answer is that the *sentence* does the work, not a
  number. See E4.
* **Compare something the device values cannot fake.** The run's chart has a
  `.channels.json` and a `.ti1`; the import knows the source file's own
  patch count and its `TARGET_INSTRUMENT`. When a measurement is a *subset*
  rather than a truncation of the run's own read, say which run's chart it
  matches **best** across the project, and offer that run. The bar already
  knows every run (`run_ids()`), and this turns the hazard into a helpful
  sentence. I would build this before I built automatic re-pairing.

### (e) Is the premise behind Basti's ruling true? Mostly — with two real exceptions

Basti: *"if there is a chart with multiple patches of the same color … it will
not matter where which one is placed."* That is safe only if same device value
⇒ same **design** colour. Measured on all 24 distinct charts, grouping by
device value rounded to 3 dp (`proof/probes/p9_group_spread.out`):

| chart | n | duplicate groups | groups differing >1 ΔE00 | worst ΔE00 |
|---|---:|---:|---:|---:|
| `knut.ti2` | 1176 | 110 | **1** | **86.86** |
| `Red-River…A4-2052p` | 2060 | 2 | **1** | **13.16** |
| `Red-River…Letter-2052p-10pages` | 2064 | 2 | **1** | **13.16** |
| `Red-River…Letter-2052p-9pages` | 2055 | 2 | **1** | **13.16** |
| the other 20 charts | 64–1173 | 0–110 | 0 | 0.00 |

**22 of 24 charts: the premise holds exactly.** The two exceptions are real and
different from each other, and I checked what each number means rather than
reporting it:

* `knut.ti2` — the two rows are `182 "O7" 100 100 100 0.950470 1.000000 1.088830`
  and `0 "AP3" 100 100 100 95.10650 100.0000 108.8440`. **The same white, written
  on two different scales in one file** (0–1 and 0–100). It is a file artefact,
  not a colour disagreement — but it also means `_design_xyz_to_100` scales the
  whole array by one factor and hands `_reference_labs` an L\* of **8.99** for a
  paper-white patch of the owner's biggest chart. **Pre-existing, reachable
  today from the Measurement Report. Reported, not fixed.**
* `Red-River…` — patch 2046 asks for RGB 100/100/100 with a design Lab of
  `(100.2, 3.9, 17.9)` while the other whites carry `(100.0, 0.1, 0.0)`;
  device distance 0.0003, **ΔE00 13.16**, no scale artefact
  (`proof/probes/p8_redriver.out`). Here the ruling genuinely does not apply.

### (f) And the tolerant match reaches further than the ruling does

Because the match must be tolerant (b), it can also hand a reading to a patch
that is merely *within* 1.0 device units — a different patch the chart
deliberately distinguishes. Measured
(`proof/probes/p5_ambiguity.out`, `p6_tolerant_cost.out`):

| chart | n | exact duplicates | **tolerant-ambiguous** | worst design ΔE00 across a tolerant pair |
|---|---:|---:|---:|---:|
| `knut.ti2` | 1176 | 251 | 254 (21.6 %) | 0.04 |
| `tc918eg-cm-a3.ti2` | 1173 | 244 | 247 (21.1 %) | 0.24 |
| `Red-River…Letter-2052p-10pages` | 2064 | 25 | **138 (6.7 %)** | **16.24** |
| `Red-River…A4-2052p` | 2060 | 21 | 134 (6.5 %) | 16.24 |
| `Pro300…Jun26.ti2` | 940 | 38 | 40 (4.3 %) | 0.24 |

On the Red River charts **47 tolerant pairs differ by more than 1 ΔE00 and 41
by more than 3**; the worst is patches `579` and `1795`, device distance 0.667,
design Labs `(62.2, 21.0, −11.0)` and `(64.2, 16.7, 12.6)` — **ΔE00 16.24**.
Swap those two readings and the profile is built from a lie about two squares.

### Recommendation on question 2: **offered, not automatic — and not in this change**

1. **Detect and name the reorder.** Compute the assignment; report
   `aligned / reordered / partial / foreign` and the ΔE00 of the identity
   pairing versus the repaired pairing. That is new information the user does
   not have today and it costs one pass over an array.
2. **Do not repair silently.** It rewrites `SAMPLE_ID` and `SAMPLE_LOC` in a
   file ChromIQ then builds a profile from, with no undo beyond "your original
   is still on the Desktop", and its named safety net does not work (c).
   Principle: ChromIQ archives rather than deletes, and this is a *rewrite*.
3. **When a repair is offered, only accept unambiguous matches.** Repair a row
   only where exactly one chart patch lies within tolerance. Where a row's
   colour is ambiguous — the 6.7 % on Red River, the 21.6 % on a TC9.18 —
   **leave it where it was** rather than handing it to a neighbour in chart
   order. Report 08's stable-in-chart-order rule is fine for *exact*
   duplicates (the ruling covers those); it is not fine for tolerant ones.
4. **Refuse to repair a file with no device values at all**, on a profiling
   import.
5. **Ship this after the destination feature, not inside it.** The reorder
   problem is real (ChromIQ's own shuffled export creates it —
   `chart_exports.write_sidecars(also_shuffled=True)`), but it is a *separate*
   correctness feature with its own §M message and its own risk. Report 13's
   plan bundles it with §I.9/§I.10, and a bundled change is one green gate
   hiding two behaviours.

**Does re-pairing hide a real fault the user should see?** Yes, one, and it is
worth stating plainly: a shuffle-refusal today is also a coarse tripwire for
*any* file whose rows do not correspond to the chart, including causes nobody
has enumerated. Re-pairing makes every such file pass. It cannot, however,
detect a **genuine misread** — the instrument reading the wrong square — either
before or after, because the device values in a `.ti3` are *declared*, carried
from the chart definition, not measured. Neither today's check nor the repair
can see that. It is worth saying so in the design so nobody believes otherwise.

---

## E4 · Partials — where the user is told, and in what words

### The mechanics: can `test_message_catalogue.py` even express it?

Checked, because the brief asked. `WINDOW_SOURCES`
(`tests/test_message_catalogue.py:321-337`) is a list of
`(module, class, method)` triples, resolved as
`getattr(getattr(mod, cls), method)` (`:356-357`). So:

* a **module-level function** in a new `workflow/measurement_import.py`
  **cannot** be listed — there is no class to name;
* a **method** can, wherever it lives;
* and `test_the_window_writes_no_prose_of_its_own` (`:383-393`) then forbids
  any `tr()` literal of 60 characters or more inside it.

**Therefore the partial notice must be rendered by a method on a tab class, and
its text must live in `workflow/measurement_messages.py`.** That is a hard
constraint on the design, not a style preference — and it is also the reason
the new core module must *return a verdict*, never render one.

Two existing methods in the import path are **not** in `WINDOW_SOURCES` and do
write their own prose: `TabMeasure._say_on_screen` (`:6203`, used at `:10268`
and `:10294` for two import strings) and `TabMeasure._blocked_by_new_run`
(`:5709`). They are pre-existing gaps in the allow-list; this feature should
not widen them by adding a third.

### A window before, or a line in the report after? **A window before, and the label after.**

Three reasons, and the third is the one that decides it.

1. **Before is the only moment the person can act.** After the file is filed,
   the cheap answer ("measure the rest and import again") has become expensive.
2. **§I.10 says the user is told "both counts". A report line is not being
   told** — the Measurement Report is opened deliberately, and a profiling
   import's next step is Build Profile, not the report.
3. **Afterwards is already covered and needs no new string.** Once the
   measurement lands beside `Run.chart_ti2`, `classify()` finds `expected`, and
   Build Profile writes its own approved line — *"{n} of {m} patches
   measured"* plus the tooltip at `ui/tabs/tab_profile.py:4051-4057`. Report 08
   D7 measured that on the owner's own files. So the design gets the "after"
   half free, **and only by filing under the run's own stem**.

### Does anything warn when the partial is too sparse to mean anything?

**No, and under the approved §I.10 nothing will.** The amendment's last
paragraph records the measurement — colprof builds silently from 4 patches,
self-check 0.016 for a profile 41.5 ΔE wrong, white required and black not —
as *"One measured caution for whoever implements this"*. It is prose, not a
rule: §I.10 sets no threshold (deliberately, and I agree), and the
**M-IMPORT-NO-WHITE** message report 08 D8 proposed was **not carried into the
amendment**. So as approved today, a measurement with no white patch is filed,
Build Profile arms, `colprof` exits 1 and the user meets Argyll's raw string
`set_icxLuLut: can't handle test points without a white patch` —
which `_COLPROF_ERROR_PATTERNS` (`workflow/profile_builder.py:20-56`) has no
entry for.

**Recommendation: no threshold, one fact.** Say the counts always; say the
white sentence only when it is true. Both go to §M-PROPOSED.

### The wording, for §M-PROPOSED

Count-bearing, explicit singular and plural, never "(s)". `{chart}`, `{got}`,
`{run}` and `{folder}` are placeholders. The vocabulary is deliberately the one
Build Profile already uses for a native partial, so the two accounts of one
situation cannot drift.

#### M-IMPORT-PARTIAL-PROFILING · fewer readings than the chart, profiling run

> **Part of the chart was measured**
>
> This run's chart has {chart} patches. The file you chose holds {got} of them.
>
> That is a normal thing to have — a measurement can be stopped part-way and carried on later. ChromIQ has matched every reading to the patch it belongs to, and nothing has been thrown away.
>
> A profile made from part of a chart describes your printer only where it was measured. Build one from this when you are happy that {got} patches is enough of your chart; otherwise measure the rest first and import again.

Buttons: **File it in {run}** · **Cancel**. Default: **Cancel**.

Singular bodies: for `{got} == 1`, *"The file you chose holds one of them."*
and *"…when you are happy that one patch is enough of your chart"*; for
`{chart} == 1`, *"This run's chart has one patch."*

**One addition report 08 did not have, and E3(d) is why.** When the readings are
a *near-complete* subset the counts alone read as reassurance, and four real
chart pairs on this machine differ by 4 or 5 patches. So a second paragraph,
shown only when `{got} > 0.95 × {chart}`:

> Only {short} of the chart's patches are missing. If you did not stop this measurement part-way, check that it is a measurement of **this** run's chart and not of a similar one — a chart of the same patch set laid out for a different paper size can look almost identical here.

Singular: for `{short} == 1`, *"Only one of the chart's patches is missing."*

#### M-IMPORT-PARTIAL-VERIFICATION · the same, verification run

> **Part of the chart was measured**
>
> Your verification chart has {chart} patches. The file you chose holds {got} of them.
>
> ChromIQ has matched every reading to the patch it belongs to. The measurement is filed, and the report will cover the {got} patches that were read — the rest are not counted for or against your profile.

Singular, for `{got} == 1`: *"…the report will cover the one patch that was
read — the rest are not counted for or against your profile."*

#### M-IMPORT-TOO-MANY · more readings than the chart has patches (kept as a refusal, per §I.10)

> **This file holds more readings than your chart has patches**
>
> This run's chart has {chart} patches and the file you chose holds {got} readings, so it cannot be a measurement of this chart.
>
> Nothing has been imported and nothing has been changed. Check that you picked the measurement of **this** run's chart — and if you measured a different chart, select the run that chart belongs to in the bar above and import it there.

#### M-IMPORT-NO-WHITE · the readings cannot build a profile yet (profiling only)

*Shown after the file is filed, not instead of filing it: the readings are real
and the Measurement Report can use them. What is refused is the promise that a
profile can be built.*

> **This measurement has no white patch**
>
> ChromIQ filed your {got} readings, but the profile builder needs a reading of the paper itself — a patch printed at full white — before it can work out what white looks like on your printer. This file does not have one, so Build Profile cannot work from it yet.
>
> That usually means the measurement stopped before it reached the white patch. On a chart whose patches are shuffled, white is rarely near the beginning. Measure the rest of the chart and import again, or go back to Measure and tick “Refine / resume existing measurement (-r)”.

Singular, for `{got} == 1`: *"ChromIQ filed your one reading, but…"*

**There is deliberately no black-patch message.** `colprof` builds without a
black patch (report 08 D6, measured), and inventing a rule the tool does not
have is exactly what the specification policy exists to prevent.

#### M-IMPORT-NO-DEVICE-VALUES · the file cannot be checked at all (new, and E3(a) is why)

*A `.txt`/`.cxf` with no device columns. 2 521 of the 2 550 `.txt` files in the
owner's own i1Profiler folder are of this shape.*

> **This file does not say which patches were measured**
>
> The file you chose holds measured colours but no patch values, so ChromIQ cannot tell which patch of your chart each reading belongs to.
>
> Nothing has been imported. If this came from i1Profiler, export it again as a measurement rather than a reference file — or use i1Profiler's own saved measurement (.mxf), which always carries the patch values.

For a **verification** import this stays a warning rather than a refusal, which
is what the code does today (`tab_measure.py:10220-10226` logs
*"[INFO] The patch-identity check could not run …"*). For a **profiling**
import it must be a refusal: a profile is built from device→colour pairs, and
this file has no device half.

---

## E5 · The destination run — `duplicate_run` does not do what §I.9 needs

### What the three functions really do

| | |
|---|---|
| `Project.duplicate_run_plan` | `core/file_manager.py:2052` — `[(group, files, bytes)]` from what is on disk, over `DUPLICATE_GROUPS` (`:2028`): **chart, measurement, profile, refinement, reports, exports** |
| `Project.duplicate_run` | `:2079` — `new_run()` then `copy2` of everything the plan names; on `OSError` it `_discard_run`s the partial copy and re-raises. `meta.json` is fresh with `duplicated_from` |
| `MeasurementTargetController.duplicate_source` | `ui/measurement_target_bar.py:526` — the run, or `None` |

### Measured, on the owner's own `Demo-Switching` run 1

`proof/drive/D5-duplicate.txt`. The confirmation window would say:

```
chart         10 file(s)   1157305 B
measurement    3 file(s)     41911 B
profile        1 file(s)    111712 B
reports        2 file(s)       510 B
exports        1 file(s)        11 B
```

and the copy (`run6`) then holds:

```
Demo-Switching.ti3          <- the import is about to overwrite this
reads/read1.ti3             <- the SOURCE's averaging reads
reads/read2.ti3
Demo-Switching.icc          <- the SOURCE's profile
reports/report_2026-05-02_10-15-00.json
reports/Quality_Check_1_Demo-Full-RGB.txt
exports/Demo-Switching-i1profiler.txt
```

**So §I.9's route makes a run that contradicts itself the instant the import
completes**: `runs/run6/Demo-Switching.ti3` is the imported measurement, while
`reads/`, `reports/` and `Demo-Switching.icc` describe the measurement it
replaced. `Run.load_meta().averaging_read_count` comes across too
(`DUPLICATE_META_CARRY`), so the run claims a read count for reads that no
longer belong to its measurement. And `duplicate_run_plan`'s window has just
told the person their measurement and profile are being copied *for* them —
153 623 bytes copied in order to be orphaned.

**Recommendation: do not duplicate. Make a new run holding the chart alone.**
`DUPLICATE_GROUPS` already names the "chart" group, so this is one optional
parameter, not a new mechanism:

```python
Project.duplicate_run(source, groups=("chart",))   # plan and copy both honour it
```

The confirmation then lists one group and says something true: *"ChromIQ will
make a new run with a copy of this run's chart, and file the measurement
there. Everything in {run} stays exactly as it is."* Cheaper (1.16 MB instead
of 1.31 MB), honest, and it removes the orphan problem by construction.
`meta.duplicated_from` still records where the chart came from.

### `duplicate_source()` is not a safe gate — measured

§I.9 says: *"Where `duplicate_source()` is `None` — the run has no complete
chart — the import is refused."* Driven with `calibration_mode` on
(`proof/drive/D3-states.txt`):

```
=== CALIBRATION run type, calibration_mode ON
  run_type now: calibration      is_calibration: True
  duplicate_source() -> run1     <- §I.9 names THIS as the gate
  duplicate_state() -> False
  Build Profile tab enabled: True   (titled "4. Calibration & Profiling")
  load_btn enabled: True
```

`duplicate_source` (`:526`) checks `is_verification()` and the four chart files
but has **no calibration branch**; only `duplicate_state` (`:577`, calibration branch at `:587`) has one.
Under Run type = Calibration `target.profile_run` still names a real run, so
the gate returns it. §I.9 forbids calibration imports separately, so this is
defence in depth — but the specification names the wrong function, and the
right one is `duplicate_state()`, which returns `(enabled, reason)` and so also
supplies the sentence to show. **Reported, not fixed.**

### Every state the brief named

| State | What happens today | What must happen |
|---|---|---|
| **No runs at all** | not reachable: a project always materialises `run1` (`Project.create(...).current_run()`); with **no project open** `run_ids()` is `[]` and `project_or_none()` is `None` | the import offers the "which project" question instead (E6) |
| **Run with no measurement** | `duplicate_source()` → the run if the chart is complete | file straight in. Nothing displaced, nothing asked |
| **Run whose chart files were deleted** | `duplicate_source()` → `None`; `run4`/`run5` of `Demo-Switching` are exactly this, measured | **file it anyway** — the measurement is the valuable thing — and say the identity check could not run and the report will fall back to `reference_source: device`. Do **not** offer the new-run route: there is no chart to copy |
| **Verification selected while Build Profile is the tab** | cannot happen: `_apply_profile_tab_gate` (`ui/main_window.py:1590`) disables the tab, and the load button with it — measured, `load_btn enabled: False` | nothing to do; but the Measure-tab door must still exist for verifications, so the two doors are not equivalent |
| **Calibration selected** | Build Profile is **enabled** and renamed *"4. Calibration & Profiling"*; its load button routes to `_pc_browse_ti3()` (`tab_profile.py:4216-4221`) | §I.9 forbids the import. Because the tab stays live, a Build-Profile door needs its **own** run-type gate — the separation is not free |
| **A run already holding a measurement** | §I.9 says duplicate | new run with the chart only, per above |

---

## E6 · The entry point — and Basti's "one control, which asks"

> Basti, 2026-08-31: *"could there be an extra step that asks whether this shall
> be imported in an existing project (which would then be opened and the
> measurement imported) or whether it should be a new project? slightly
> different dialog when a project is already open -> import in this project or
> create a new one"*

**I agree with the shape and I am not adopting the second state as described.**
One control that asks is structurally better than a second control beside it,
for the reason he gives and for one more: the Build Profile load control is a
**40 × 40 icon with no label** (`MeasuredChartButton`, `tab_profile.py:358-369`;
measured size `QSize(40, 40)`, screenshot `proof/drive/D3-build-profile-header.png`).
Two unlabelled icons differing only by tooltip is the worst possible way to
express two overlapping acts. There is nowhere to put a second door that is
better than the door already there.

But the two states are **not** symmetrical, and the second one is not a dialog.

### (1) "Opening a project" is a 130-line act that lives somewhere else

`TabChart._load_existing_profile` (`ui/tabs/tab_chart.py:5892-6023`) is what an
open *is*. It: opens a file dialog on `project.json`; refuses a non-project
with `InfoDialog`; detects a project **outside** the working folder and offers
to **copy the whole project in**, through `_ask_project_name` — which carries
the `replace` flag and therefore the destructive branch; announces a schema
migration (`_maybe_announce_project_port`, `:5843`); calls
`FileManager.open_project_at` (`core/file_manager.py:2409`); refills the name
fields; clears **ten** pieces of TabChart state (`_tc918_active`,
`_knut_active`, `_preset_ti1_path`, `_pending_editor_recipe`, and the
prebuilt / applied / reflected modes); displays the run's chart with
`_display_run_chart` — TIFFs, margins, `_restore_chart_settings`, page count,
notes; then `_default_bar_to_current_run` and `_reset_run_type_for_loaded_project`.

And `MainWindow._on_masthead_load_project` (`:1308-1316`) **switches the tab to
Create Chart before running it** (`:1313`).

**Driven, standing on Build Profile with no project open, stubbing only the OS
file dialog** (`proof/drive/D6-open-project.txt`):

```
BEFORE the open
   is_named: False   project_or_none: None
   current tab: 4. Calibration & Profiling
   bar: run_type='profiling' profile_run=''
AFTER the open (the REAL _load_existing_profile ran)
   is_named: True    project: Demo-Switching
   current tab: 1. Create Chart      <- the user was on Build Profile
   bar: run_type='profiling' profile_run='run3'
   load_target_settings called on: ['chart','chart','chart','chart','chart']
```

Three things follow.

* **An import that "opens a project" sends the user to Create Chart** — the
  exact "skipping around" the request exists to remove. Basti's second state,
  built naively, produces the complaint that motivated it.
* **`load_target_settings` ran five times and every one was Create Chart.**
  `MainWindow._load_settings_of_visible_tab` (`:1512`) loads *the visible tab*,
  and the visible tab had already been changed. So Build Profile does not
  learn the new target from the open itself; it learns it from
  `_load_settings_of_tab_entered` when the user returns to it. An import that
  opens a project and then acts **without going back through a tab change**
  would act on a tab holding the previous target's settings —
  `per_target_settings.md` §2 L1 is what makes this safe, and only if the
  design goes through it.
* **The run is decided for you.** The open lands on the project's
  `current_run` from `project.json` — here `run3`, not `run1`. So after an
  open there *is* already a selected run, and it is a manifest value, not a
  choice.

**A partial open is not an option.** Skipping `_maybe_announce_project_port`
means an old project silently reorganises on disk; skipping the ten resets
means a preset from the previous project survives into this one; skipping
`_display_run_chart` means Create Chart shows the wrong project's chart. Any of
those is a new defect on the most-used path in the app.

**But a WHOLE open, called from the import, costs nothing — and I had this
wrong until I measured it.** The tab switch is not part of the open. It lives
in `MainWindow._on_masthead_load_project:1313`, one line *above* the call.
Driven, standing on Build Profile with no project open, calling
`TabChart._load_existing_profile()` **directly**
(`proof/drive/D7-third-shape.txt`):

```
BEFORE: tab=4. Calibration & Profiling  is_named=False  bar run=''
AFTER calling TabChart._load_existing_profile() directly:
   tab now: 4. Calibration & Profiling    <- it did NOT move
   is_named: True   project: Demo-Switching
   bar: run_type='profiling' profile_run='run3'
   load_target_settings called on: ['profile', 'chart', 'profile', 'chart']
   run_ids: ['run1','run2','run3','run4','run5']
   location_being_edited: third/Demo-Switching/runs/run3/
```

**Build Profile stayed on screen, the project opened correctly, the bar
re-pointed to the manifest's current run, and `load_target_settings` ran on
Build Profile** — `per_target_settings.md` §2 L3/L4 honoured, because
`_load_settings_of_visible_tab` loads whichever tab is visible and Build
Profile was. The five-Create-Chart-loads in the D6 drive were a consequence of
the *tab switch*, not of the open. **So the answer to "is an open too heavy to
perform inside an import" is: no. It is one method call and it is routine.**

See E6b for the recommendation this changes.

### (2) How the person chooses the existing project — **the name box, and it already exists**

There is **no project list anywhere in ChromIQ** — no `list_projects`, no
recents menu; Open Project is a file dialog on `project.json`
(`tab_chart.py:5897-5902`). So the choices are: a file dialog (state 2's
problem, above), a new list (a new mechanism, and report 03 §D5's rule says a
second weaker version of an owned question is a defect), or **the name box**.

The name box is the right answer, and Basti has **already ruled on this exact
window**. From §M-PROPOSED's awaiting-review note, 2026-08-31, about
M-IMPORT-REPLACE-CONFIRM / M-IMPORT-REPLACED-KEPT:

> *"Basti ruled that the consequence and the vocabulary are shared with §S4.7
> while the window stays the loaders' own, because theirs carries a name box and
> a live 'this name is taken' line that §S4.7's has no room for"*

`ui/dialogs/name_prompt.ask_for_project_name(parent, prefill=…, body=…,
exists=…)` (`:133`) already gives: live validation, the folder-name preview
("what the folder will really be called"), Windows-reserved names, and the
magenta **"this name is taken"** line driven by the `exists` callback.

**And that single box answers both of Basti's branches with no branching UI at
all**: a name that resolves to an existing project means *import into it*; a
name that does not means *create it*. That is §S4.7's own structure, and it is
already the structure the two loaders are being given for 4.1.3. It also means
state 1 and state 2 differ only in whether the box is pre-filled with the open
project's name.

The honest objection: **typing beats picking only if you remember the name.**
With 23 projects under `~/ChromIQ` that is a real cost. Two cheap mitigations,
both reusing what exists: pre-fill the box with the open project's name in
state 1, and — because the collision line already knows how to answer
"does this name exist" — add nothing else. If Basti wants a list, that is a
new mechanism and should be **open question 3**, not a silent invention.

### (3) Which run, once the project is chosen — §S4.7 already answers it

§S4.7 / **M-PROJECT-EXISTS** already carries a run picker: labelled
*"Make the new chart in:"*, offering **"A new run (nothing already there is
touched)"** first *"because it is the one answer that cannot cost anything"*,
then every run oldest-first, with a `{holds}` list under it that follows the
picker. The window's default button is **Cancel**.

**Reuse it verbatim, with one word changed and one button removed.**

* label → **"File the measurement in:"**
* default → **a new run**, for exactly §S4.7's reason, and it agrees with §I.9:
  a run that already holds a measurement is not displaced.
* **"Replace it" must not appear.** It clears a whole project
  (`M-PROJECT-REPLACE-CONFIRM`), and an import may never do that. Report 08
  C8/D10 counted three `shutil.rmtree` project-deleters reachable from these
  very loaders; the whole value of importing into a project the user names is
  that **no name collision arises, so no destructive button is reachable**.
  Keeping it here would re-import the hazard the design removes.
* when the project is open (state 1) the bar has already chosen a run, so the
  picker is pre-set to it rather than to "a new run" — the bar stays the one
  place a run is chosen (report 08 C2), and the picker only *shows* it.

### (4) One dialog or two? **One window, one option list, one option that varies.**

Consistency (principle 11) says the same act asks the same question. The two
states differ in exactly one line, so they are one message with one variable
paragraph — the way M-PROJECT-EXISTS already varies `{cal}` and `{holds}`.
Showing a person "import into an existing project" when one is already open
would be a choice with two meanings; showing "create a new project" is
meaningful in both. So:

| | state 1 — a project is open | state 2 — none is open |
|---|---|---|
| first option | **Import it into “{project}”** | **Import it into a project I already have** |
| second option | **Make a new project for it** | **Make a new project for it** |
| third | **Cancel** | **Cancel** |
| the box | pre-filled with `{project}`, read-only | empty, with the live "this name is taken" line |
| the run picker | pre-set to the bar's run | **a new run**, per §S4.7 |

### (5) The "create a new project" branch is **today's code, untouched**

`resolve_ti3` (`ui/ti2_loader.py:919`), `resolve_txt` (`ui/txt_loader.py:29`)
and `_import_i1profiler_cxf` (`tab_profile.py:4259`) keep their name prompt,
their §S4.7 collision handling and their `M-IMPORT-REPLACE-CONFIRM` /
`M-IMPORT-REPLACED-KEPT` work. The routing question is added **before** them
and calls them unchanged on the "new project" answer. Anything else turns a
working path into a rewrite, and this feature has no business doing that.

### (6) Cancel, at every step

The order is: **choose the file → ask → (name / pick a run) → validate →
file**. Nothing is created, opened, converted or switched until the last step.
Two things in today's code must be moved to honour that:

* the conversion currently runs **before** validation and writes into
  `runs/runN/cache/import/` (`tab_measure.py:10289-10292`). That needs a run,
  so a state-2 import cannot convert before the project is chosen — the
  conversion must go to a temp folder and be copied in afterwards, or the
  project must be opened first. `_import_i1profiler_cxf` already converts to a
  `tempfile.TemporaryDirectory` (`tab_profile.py:4266-4272`), so the pattern
  exists.
* `_snapshot_verification_chart` **mutates the bar** (`ctl.set_verification_id`)
  and can create a dated folder before the copy. On the profiling side its
  delegate can write `meta.chart_snapshot_stale`. Both are writes that happen
  before the measurement lands, and a cancel after them leaves a change behind.
  Today that is accepted for a verification (§I.6 says so). The profiling path
  should run its snapshot **after** the measurement is filed, not before.

### (7) Does this make `Tools ▸ Convert i1Profiler → TI3` redundant?

**Complementary in principle, contradictory in its shipped words, and the
words are the part that must change.**

`I1ProfilerToTi3Dialog` (`ui/dialogs/tools_dialogs.py:1318`) is a **format
converter**: pick a file, pick a folder and a name, press Convert. Its output
goes wherever the person says (`_OutputRow` + `_initial_dir`, `:537`, `:201`),
by default beside the i1Profiler file. That is a legitimate act this feature
does not cover — converting a measurement for something other than ChromIQ, or
for the Measurement Report on its own.

What it must stop saying is this, shipped and translated today (`:1324`,
`:1349`):

> *"This brings those readings back into ChromIQ **so you can build a profile
> from them** … a ChromIQ measurement file (.ti3) you can take **straight to
> the Build Profile tab**"*
> *"The resulting .ti3 **loads into Build Profile** and into the Measurement Report."*

That route produces a `.ti3` with **no chart beside it**, so `classify()`
returns `expected=None`, the Build Profile label shows no count and the tooltip
is empty — report 08 D7 measured it. **It is the silent path, and it is the one
the help text recommends.** Once the load control can file into a run, the help
should say: *convert here when you want the file for something else; to build a
profile from it, load it in Build Profile and ChromIQ will file it into your
project.* That is a help-text change, not a deprecation. **Open question 6.**

Note also `tool_availability.md:160` already lists `i1p_to_ti3` among the three
tools *"whose default is wrong"* because it writes to the projects root. That
draft is `⏳ Awaiting confirmation`, so it is reported here, not acted on.

### (8) Does it need a §M-PROPOSED entry? **Yes — one new message, and it is a window.**

`M-LOAD-INTO-PROJECT` below is new user-facing text, so under §M and
`tests/test_message_catalogue.py` it goes to §M-PROPOSED first, and the method
that renders it must be added to `WINDOW_SOURCES` — which, being
`(module, class, method)`, means it must be a **method on `TabProfile`** (and
on `TabCheckRefine` if that tab gets the same fork), not a helper function.

#### M-LOAD-INTO-PROJECT · where a measurement chosen from outside should go

*Shown when a measurement is chosen through Build Profile's load control and
the file lies outside every project. `{file}` is the file's name, `{project}`
the open project, `{run}` the run the bar has selected.*

**State 1 — a project is open:**

> **Where should this measurement go?**
>
> “{file}” is not inside any of your projects yet, and you have “{project}” open.
>
> •  **Import it into “{project}”** files it with that project's work, so ChromIQ can compare it against the chart it was measured from and everything about this printer stays in one folder. You choose which run it goes into below.
>
> •  **Make a new project for it** puts it in a folder of its own, named by you. Choose this when the measurement has nothing to do with “{project}” — a different printer, or a different paper.
>
> Either way your own file stays exactly where it is. ChromIQ works on a copy.

Picker: **File the measurement in:** — pre-set to {run}, with a new run first.
Buttons: **Import it into “{project}”** · **Make a new project for it** ·
**Cancel**. Default **Cancel**.

**State 2 — no project is open:**

> **Where should this measurement go?**
>
> “{file}” is not inside any of your projects, and you do not have a project open.
>
> •  **Make a new project for it** puts it in a folder of its own, named by you. This is the usual answer for a measurement you have just made.
>
> •  **Open that project first** — if this measurement belongs with work you already have, open that project and ChromIQ will bring you back here with this file still chosen.
>
> Your own file stays exactly where it is either way. ChromIQ works on a copy.

Buttons: **Make a new project for it** · **Open that project first** ·
**Cancel**. Default **Cancel**.

*(State 2's second answer is deliberately a hand-off, not a hidden open — E6(1).
If Sebastian prefers the box-and-picker version instead, its text is state 1's
with “{project}” replaced by the typed name; that needs the Open Project
refactor first.)*

---

## E6b · Option A, option B, or a third shape — the recommendation

Basti offered two shapes for the no-project-open case, and named B as not his
preference:

* **A** — the import asks which project, **opens it**, and imports.
* **B** — the import tells the person to open the project and select the run
  first, then start the import again.

**I recommend a third shape, C, and it is closer to A than to B.**

> **C — the import calls the app's own Open Project act, in place, and carries
> straight on.** One way to open a project, no new picker, no dead end, and the
> person does not leave the tab they are on.

### Why B is not merely "less preferred" — it is the shape already ruled against

The coordinator is right that this is the same shape, and the code agrees. The
old name dialog explained the fix, closed, and left the person to do it
elsewhere and repeat the action they had just taken. `name_prompt`'s docstring
now records the ruling in the source itself
(`ui/dialogs/name_prompt.py:138-142`):

> *"The caller is expected to CARRY ON with the returned name rather than send
> the user away to type it somewhere else: the dialog this replaced explained
> the fix, closed, and left the person to repeat the action they had just
> taken."*

An import that says *"open the project, pick the run, then start again"* is
that dialog with different nouns. Under principle 11 the two situations have to
be told apart on a real difference, and I looked for one:

| the name dialog's dead end | option B's dead end |
|---|---|
| the person had typed a name; the window knew the name | the person has chosen a file; the window knows the file |
| the fix was a text field the window could have carried | the fix is an act the window can call — measured, one line |
| repeating meant re-typing | repeating means re-opening the file dialog and re-finding the file |

**There is no difference of kind.** The only argument that could have made one
was "an open is too heavy to perform from here", and that argument is now
measured false (E6(1)). So B should be rejected for the same reason the name
dialog's dead end was.

### What survives from the case FOR B, and how C keeps it

The coordinator's three points for B are all real, and C keeps all three:

1. **One way to open a project.** C does not add one — it *calls* the existing
   act, `TabChart._load_existing_profile`, file dialog and all. The person
   picks the project through the same window ⌘O gives them, with the same
   external-project copy-in guard, the same migration announcement and the same
   ten state resets. Nothing is reimplemented, so nothing can drift.
2. **The run question is answered by the controls built for it.** After the
   open the bar is on the project's `current_run` (measured: `run3`). The
   import's own picker — §S4.7's, defaulting to **a new run** (E6(3)) — then
   shows that and lets it be changed, and moving it moves the bar. The bar
   stays the single place a run is chosen.
3. **Less new machinery.** C's new machinery is: remember the chosen file
   across the call, and check whether the open happened.
   `_load_existing_profile` returns `None` today, so the caller tests
   `FileManager.is_named()` / `get_target_name()` before and after — three
   lines. That is *less* new machinery than B, which needs a whole message
   naming controls on two other parts of the screen.

### The one thing C must not do

C must not perform the open and then act **silently**. The person asked to
import a file and is now looking at a different project than they were a
moment ago. So the sequence is: open → **the state-1 window reappears, naming
the project that is now open and the run it will file into** → they press
Import. One extra confirmation, on a screen that has just changed underneath
them, is right.

### "Where are my files?" — principle 5

**C wins, and B is the weakest of the three.**

* **C**: the person watches the project open, sees the Profile-run bar fill in,
  and the confirmation names the folder before anything is written.
  `location_being_edited()` is live and correct throughout — measured,
  `third/Demo-Switching/runs/run3/`.
* **A** (a name box that opens a project it resolves): the same end state, but
  the project was opened from a name typed into a box, so the person never saw
  which folder was chosen. It also needs the Open Project refactor, or a second
  way to pick a project.
* **B**: the person is told to go and do two things and come back. Between the
  two halves nothing on screen says where the file will land, because ChromIQ
  has been told nothing about it yet — and `location_being_edited()` with no
  project open returns **an invented placeholder**,
  `work/Printer_Paper_Type_Instr_2026-08-31_14-08/runs/run1/` (measured;
  report 08 C9 claims it returns `""`, which is wrong). A person reading the
  bar during B's gap is being shown a folder that does not exist.

### If Sebastian still wants B

Then it must not be a dead end, and it needs three things option B as described
does not have:

* **name the exact controls**: *"Press ⌘O, or the “Open Project” button at the
  top of the window, and choose the project's `project.json`. Then set
  “Profile run” in the bar to the run you want."*
* **keep the file**: the chosen file is remembered, so returning to Build
  Profile and pressing the load button again offers it as the default rather
  than reopening at the last folder.
* **one step back, not the whole journey**: the window's own button performs
  step one (it calls the same act), which is C — so a B that is not a dead end
  collapses into C anyway. That, more than anything, is why I recommend C.

### Recommendation, stated plainly

**Build C.** State 1 (a project is open) is unchanged from E6: one routing
question, the bar's run, no new control. State 2 (no project open) offers
**"Open a project and import into it"**, which calls the existing Open Project
act in place, then re-asks state 1's question. Option A's name box is the
fallback if Sebastian later wants project-picking without a file dialog, and
that is the moment to do the Open Project refactor — not now.

Wording for state 2 replaces the version drafted in E6(8):

> **Where should this measurement go?**
>
> “{file}” is not inside any of your projects, and you do not have a project open.
>
> •  **Open a project and import into it** — ChromIQ asks which project, opens it, and comes straight back here with this file still chosen. Choose this when the measurement belongs with work you already have.
>
> •  **Make a new project for it** puts it in a folder of its own, named by you. This is the usual answer for a measurement you have just made.
>
> Your own file stays exactly where it is either way. ChromIQ works on a copy.

Buttons: **Open a project and import into it** · **Make a new project for it** ·
**Cancel**. Default **Cancel**.

---

## E7 · The journey, click by click, and where every file lands

Three source formats × three destination states. **Nothing is written until the
last step of each journey.**

### Where files land, in one table

| what | where | why |
|---|---|---|
| the person's own file | **exactly where it was** | never moved, never modified. Proven by SHA-256 across three converts of the owner's real `.mxf` |
| the converted `.ti3`, project known | `runs/runN/cache/import/<source-stem>.ti3` | §I.4; `cache/` is documented always-safe-to-delete |
| the converted `.ti3`, project **not yet** known | a `tempfile.TemporaryDirectory` held on the tab, then copied in | the pattern `tab_profile._import_i1profiler_cxf:4273` already uses |
| the filed measurement, **profiling** | `runs/runN/<stem>.ti3` = `Run.measurement_ti3` | §I.9. The stem is what lets `_find_reference_ti2` find the chart; any other name silently falls back to `reference_source: device` |
| the filed measurement, **verification** | `runs/runN/verifications/<date>/<stem>-verify.ti3` | §I.6/§I.7, unchanged |
| the chart it was judged against, verification | `…/verifications/<date>/chart/` | §I.6, unchanged |
| the run's chart copy, profiling | `runs/runN/chart/` via `_snapshot_profiling_chart` | what a native profiling read does; **§I.9 omits it — E2** |
| the how-printed answer | beside the filed `.ti3`, via `workflow.verification_print.write_print_record`, `recorded: "asked-at-measure"` | `tab_measure.py:9852-9865` |
| the provenance of the import | `runs/runN/meta.json` — source path, source SHA-256, converter used, and the repair verdict if one ran | answers report 13's open question 5 without copying a second file |
| **nothing** | a copy of the original `.txt`/`.mxf` beside the `.ti3` | see below |

**Report 13's open question 5 — keep the original beside the `.ti3`?
Recommendation: no; record its identity instead.** A copy is 0.1–2 MB that
duplicates a file the person already has, in a folder they did not choose, and
it diverges the moment they re-export. Path + SHA-256 + converter + date in
`meta.json` makes the conversion auditable, says honestly where the readings
came from, and lets a later reader be told "the file this came from has
changed". Adding a `RunMeta` field means updating **both** halves of
`DUPLICATE_META_CARRY | DUPLICATE_META_FRESH` — the partition is exhaustive and
a test fails the day it is not (`core/file_manager.py:1539`, `:1560`, enforced at
`:2120-2128`).

### Journey 1 — an i1Profiler `.mxf`, into an EMPTY run of the OPEN project

1. Bar: **Run type = Profiling**, **Profile run = run3** (chart, no measurement).
2. Build Profile → the load icon (top right, 40 × 40).
3. File dialog *"Load measurement data"*, filter
   `Measurement data (*.ti3 *.txt *.mxf *.cxf)`. Choose
   `Desktop/MyChart-measured.mxf`.
4. **M-LOAD-INTO-PROJECT, state 1.** *"…you have “Demo-Switching” open."*
   Picker **File the measurement in:** pre-set to **run3**.
   → **Import it into “Demo-Switching”**.
5. Converted → `runs/run3/cache/import/MyChart-measured.ti3`
   (`convert_i1profiler_measurement`, no Argyll subprocess for `.mxf`).
6. Validated against `runs/run3/Demo-Switching.ti2`:
   count, then `verify_patch_identity`.
   * counts equal, identity verified → nothing said, step 8.
   * fewer → **M-IMPORT-PARTIAL-PROFILING**, *File it in run3* / *Cancel*.
   * more → **M-IMPORT-TOO-MANY**, refused, nothing written.
   * no device columns → **M-IMPORT-NO-DEVICE-VALUES**, refused.
   * reordered → **not repaired in this change**; refused as today with
     `M-IMPORT-MISMATCH`, whose last paragraph should name the shuffled export
     (E3).
7. *(nothing has been written outside `cache/` yet)*
8. Filed → **`runs/run3/Demo-Switching.ti3`**. Chart snapshot →
   `runs/run3/chart/`. Provenance → `runs/run3/meta.json`.
9. **M-HOW-PRINTED** — *Raw — no profile* / *With colour management* /
   *Not sure* (default). Recommended for profiling too: a profiling sheet
   printed **through** a profile makes the resulting profile wrong, and this is
   the only moment ChromIQ can ask.
10. **M-IMPORT-DONE**, profiling variant — *Open measurement report* /
    *Build the profile* / *Close*.
11. Build Profile's own label, with no new string:
    `…/runs/run3/Demo-Switching.ti3 — 940 of 940 patches measured`.
    If white is missing: **M-IMPORT-NO-WHITE** before step 10.

### Journey 2 — an i1Profiler `.txt`, into a run that ALREADY HOLDS a measurement

Steps 1–4 as above with **run1** selected; the picker's *"File the measurement
in:"* shows `run1 — holds a chart, a measurement and a built profile`.

5. Because run1 holds a measurement, the picker's default moves to
   **A new run (nothing already there is touched)**, per §S4.7, and the window
   adds: *"run1 already has a measurement, and an import never replaces one."*
6. → **Import it into “Demo-Switching”**.
7. `resolve` the destination: `Project.duplicate_run(run1, groups=("chart",))`
   → **run6** holding only `Demo-Switching.ti1/.ti2/.channels.json/_NN.tif`
   and `chart/` (E5 — *not* today's `duplicate_run`, which also copies the
   measurement, the profile and the reports and orphans them).
8. `.txt` → `.ti3` via **`txt2ti3`** (a real Argyll subprocess — it needs a
   `timeout=`) into `runs/run6/cache/import/`.
9. Validate against `runs/run6/Demo-Switching.ti2`; messages as journey 1.
10. Filed → `runs/run6/Demo-Switching.ti3`. The bar moves to **run6**.
11. **M-IMPORT-DONE** names run6, and says run1 is untouched.

`run1` is byte-for-byte unchanged. That is the whole point, and it is testable.

### Journey 3 — a plain `.ti3`, with NO PROJECT OPEN

1. Build Profile → the load icon → choose `Desktop/somebody-elses.ti3`.
2. **M-LOAD-INTO-PROJECT, state 2** (E6b wording).
3. → **Open a project and import into it**: the ordinary Open Project act runs
   **in place** — the `project.json` file dialog, the outside-the-working-folder
   copy-in guard, the migration announcement, the bar re-pointing to the
   project's `current_run`. **The tab does not change** (measured, D7).
   *Cancel there → back to step 2, nothing done.*
4. State 1's window reappears, now naming the project that is open and the run
   it will file into. Picker defaults to **a new run**.
5. → **Import it into “{project}”**. From here it is journey 1 from step 5,
   with no conversion (a `.ti3` passes through).
6. → **Make a new project for it** instead: **today's code, untouched** —
   `resolve_ti3` (`ui/ti2_loader.py:919`), its name prompt, §S4.7's collision
   handling, `M-IMPORT-REPLACE-CONFIRM` and `M-IMPORT-REPLACED-KEPT`.

### Journey 4 — the verification half, unchanged

Measure tab, Run type = Verification, IMPORT mode: §I.1–§I.8 exactly as today,
plus §I.10's partial filing. **No behaviour change beyond partials**, which is
what makes the "prove it is unchanged" work in E2 tractable.

---

## E8 · What already exists that this must not duplicate

| The feature needs | It already exists at | Verdict |
|---|---|---|
| the whole import sequence | `ui/tabs/tab_measure.py:10246 _on_import_measurement` | **reuse**, extract 4 steps (E2) |
| i1Profiler → `.ti3` | `workflow/reference_convert.convert_i1profiler_measurement` — verified on the owner's three real `.mxf`, sources untouched | **reuse** |
| the pairing check | `workflow/measurement_report.py:236 verify_patch_identity` | **reuse as a detector**, never as a repair's gate (E3c) |
| the chart's patch count | `TabMeasure._chart_patch_count` (`:10083`, static) | **move** to the core module |
| which run | `MeasurementTargetController` — `run_ids():181`, `verification_ids():185`, `selection_has_measurement():504`, `duplicate_state():577`, `location_being_edited():239` | **reuse**; no new combobox (report 08 C2) |
| a run holding the same chart | `Project.duplicate_run` / `duplicate_run_plan` (`:2079`, `:2052`) | **extend** with `groups=` — today's copies orphan themselves (E5) |
| "this name is already a project" | `ui/dialogs/name_prompt.ask_for_project_name(exists=…)` (`:133`) | **reuse**; note **no loader uses it yet** — report 08 D11, still true (`grep name_prompt` → only `tab_chart.py:12201`, `:12222`) |
| choosing a run, with a safe default | §S4.7 / **M-PROJECT-EXISTS**'s picker, defaulting to *a new run* | **reuse the shape**, minus "Replace it" (E6(3)) |
| opening a project | `TabChart._load_existing_profile` (`:5892`) | **call it**; do not reimplement (E6b) |
| "the measurement is in another run" | **M-BUILD-ELSEWHERE**, approved Knut 2026-08-04 | **reuse the vocabulary** for the tab-vs-bar divergence (E1 R8) |
| a partial measurement's count on screen | `TabProfile.set_ti3_path` (`:4013-4066`), `workflow/measurement_state.classify` | **free**, once the file lands beside `Run.chart_ti2` |
| moving a project's files safely | `core/trash.move_to_trash` | **not needed** — an import into a named project raises no collision, so no destructive button is reachable (report 08 C8) |
| a converter dialog | `Tools ▸ Convert i1Profiler → TI3` (`ui/dialogs/tools_dialogs.py:1318`) | **complementary**; its help text contradicts the new route and must change (E6(7)) |

### Three things it must NOT do

1. **Not a second run picker.** Report 03 §D5, and report 08 C2.
2. **Not a second import module.** Report 08 D12's §I.12 proposed *"the IMPORT
   module is the only implementation"*; the approved §I.9 dropped that clause,
   and Basti's steer supersedes it — but a Build Profile door must **route into
   the same core**, not grow its own guards, its own validation and its own
   §M vocabulary. Two implementations of one act is what §M exists to prevent.
3. **Not a fix for the three `rmtree` sites.** Report 08 D10 counted them at
   `ui/txt_loader.py:333`, `ui/ti2_loader.py:1324` and `ui/ti2_loader.py:1395`.
   They stay reachable from the *new project* branch, which this change does not
   touch. Mixing a destructive-path fix into a feature is how a green gate hides
   a regression.

---

## E9 · What I would do differently — including doing less

### Numbered plan, reuse vs new

1. **Amend §I before any code.** Three clauses are missing from the approved
   §I.9/§I.10 and each is a behaviour someone will otherwise invent:
   (a) the **entry point** — §I.9 says "the IMPORT module", report 13 says
   Build Profile; (b) the **profiling chart snapshot**, dropped by "I.6 and I.7
   become one step" (E2); (c) whether **re-pairing** happens at all — it is in
   report 13 §3 and in **no** clause of §I. *Reported, not fixed: these are
   Sebastian's to write.*
2. **Add the six messages to §M-PROPOSED** in the same commit:
   M-LOAD-INTO-PROJECT, M-IMPORT-PARTIAL-PROFILING,
   M-IMPORT-PARTIAL-VERIFICATION, M-IMPORT-TOO-MANY, M-IMPORT-NO-WHITE,
   M-IMPORT-NO-DEVICE-VALUES. `tests/test_message_catalogue.py` requires it.
3. **`workflow/measurement_import.py` — new, no Qt.** `plan_import(source,
   run, argyll) -> ImportPlan` and `perform_import(plan) -> ImportResult`.
   Verdicts: `ok / partial / too_many / no_device_values / unreadable /
   reordered / no_white`. Returns log lines; renders nothing. Takes
   `_chart_patch_count` with it.
4. **`resolve_import_destination(ctl, fallback_path) -> Run | None`** — the
   one answer to "which run", shared by both tabs, replacing `_guard_run`'s
   two different rules (E2).
5. **Tests for 3 and 4 before any UI**, on real `.ti2`/`.ti3` text fixtures —
   no Argyll, no `@pytest.mark.slow`, everyday tier.
6. **`Project.duplicate_run(source, groups=…)`** plus its plan (E5), with a
   test that the copy holds the chart and **nothing else**.
7. **Re-point the two tests that encode the withdrawn rules.**
   `test_a_patch_count_mismatch_is_refused_before_anything_is_written` (`:173`,
   5 of 8 patches — a *partial*, which §I.10 now files) and
   `test_reordered_patches_are_refused_by_the_identity_check` (`:191`). Both
   must be rewritten to the new rule in the same commit, deliberately, not
   deleted. Add `test_more_readings_than_the_chart_is_still_refused`.
8. **The window-shape test the module never had** (E2), modelled on
   `tests/test_s47_window_shape.py`.
9. **Lift the run-type gate**: `_import_available()` → True for Profiling;
   still False for Calibration, and **greyed with the reason rather than
   hidden** (report 08 D13 q10 — a hidden button taught nobody anything).
10. **Build Profile's routing question**: `M-LOAD-INTO-PROJECT` before
    `resolve_ti3` / `resolve_txt` / `_import_i1profiler_cxf`, shown only when a
    file is chosen from outside every project. "Make a new project" calls
    today's code unchanged.
11. **Bump `core/version.py`, then the gate**: `QT_QPA_PLATFORM=offscreen
    pytest --runslow -n auto`, green, before any beta.

### Doing less — three things I would cut

* **Cut automatic re-pairing from this change entirely** (E3). It is the
  highest-risk and lowest-urgency part: it rewrites user data, its named
  safety net does not work, it needs a tolerance the design has not chosen,
  and it can move a reading up to 16 ΔE00 onto the wrong patch on the owner's
  own charts. Detect and name the reorder; ship the repair separately, offered.
* **Cut Check & Refine from v1.** Report 08 D3 is right that it needs the same
  question, but its `.icc` asymmetry is unresolved (C7, open question) and the
  tab's act is a different verb. One tab, one door, one release.
* **Cut the "keep the original beside the `.ti3`" idea** (report 13 open
  question 5). Record identity in `meta.json` instead (E7).

### One thing I would ADD that is not in the design

**Say which run the measurement fits best.** When the readings are a subset of
the selected run's chart, the same comparison against the project's *other*
runs is nearly free — the bar already enumerates them — and it turns E3(d)'s
hazard into a helpful sentence: *"These readings also match run2's chart
exactly. Did you mean run2?"* That is worth more than the repair, costs less,
and cannot damage anything.

---

## E10 · i18n

* Every new string through `tr()`; runtime values as
  `tr("… {n} …").format(n=…)`, placeholders part of the key.
* **All five count-bearing messages need explicit singular and plural bodies**
  — `{got}`, `{chart}`, `{short}`, `{runs}` — never "(s)".
  `tests/test_i18n.py` fails on the bracketed form.
* `{project}`, `{file}`, `{run}`, `{folder}` are placeholders; folder paths,
  file names and run ids are never translated.
* `M-LOAD-INTO-PROJECT`'s buttons carry a project name **inside** the label —
  `tr('Import it into “{project}”')`. Check German and the CJK catalogues for
  width; `fit_message_box_buttons` exists for this and is already used by every
  window in the import path.
* **A pre-existing gap on the exact control this feature extends**:
  `TabProfile._on_load_ti3` (`:4222-4223`) passes the file dialog's caption and
  filter as **bare strings** — `"Load measurement data"`,
  `"Measurement data (*.ti3 *.txt *.mxf *.cxf)"` — with no `tr()`. Compare
  `TabMeasure._on_import_browse` (`:10188-10190`), which wraps both. Worth
  fixing in the same commit; it is two lines and it is the window this feature
  puts in front of everyone.
* After the strings land: `python scripts/i18n_extract.py --missing de`, add the
  German (Du-Form). The other twelve wait for the final, not the beta
  (`feedback_translation_only_before_final`).

---

## E11 · Open questions — only the owner can answer these

1. **§I.9 places the IMPORT module in the Measure tab** (*"a third mode on the
   Measure tab"*, *"offered while the shared Run type is Profiling as well as
   Verification"*). Report 13 and your own steer place the door in **Build
   Profile**. Those are different specifications. **Which, and will you write
   the clause?** Nothing may be built until this is answered — my
   recommendation is: the door is in Build Profile, the Measure tab keeps the
   verification door, and **both call one core**.
2. **§I.9's "I.6 and I.7 become one step" drops the profiling chart snapshot.**
   A native profiling read copies the chart into `runs/runN/chart/` and
   maintains `meta.chart_snapshot_stale`. Should a profiling import do the same?
   (My recommendation: yes — the code already routes there, so it is free.)
3. **Re-pairing is in report 13 §3 and in no clause of §I.** Do you want it at
   all in this change? My recommendation is **no**: detect and name the
   reorder, ship the repair as its own offered act later (E3). If you want it
   now, three sub-answers are needed: the tolerance (I propose reusing
   `PATCH_IDENTITY_TOL = 1.0`), whether ambiguous rows may be re-assigned
   (I propose **never**), and what validates the repair, since
   `verify_patch_identity` cannot (I propose showing ΔE00 before and after).
4. **A measurement with no device values at all** — 2 521 of the 2 550 `.txt`
   files in your own i1Profiler folder. Refuse it for a profiling import
   (my recommendation), or file it unvalidated as the verification path does
   today?
5. **A near-complete subset.** Four real chart pairs on this machine are strict
   device-value subsets of each other, including your Red River A4 / Letter
   sets, four patches apart. Do you want the extra "check it is this run's
   chart" paragraph (E4), the "these readings match another run better"
   sentence (E9), both, or neither?
6. **`Tools ▸ Convert i1Profiler → TI3`'s shipped help** tells the user to
   build a profile from its output and take it "straight to the Build Profile
   tab" — the silent path. Does the help text change to point at the new route,
   or does the tool change, or neither?
7. **Option A / B / C for the no-project-open case** (E6b). I recommend **C**:
   the import calls the ordinary Open Project act in place and carries on.
   Measured: it does not move the tab and it loads the visible tab's per-target
   settings correctly. Do you accept C?
8. **A project list.** ChromIQ has none — Open Project is a file dialog on
   `project.json`. If you want the import (or anything else) to offer a list of
   your projects, that is a new mechanism and needs your word before anyone
   builds one.
9. **`_import_available()` hides the button rather than greying it.** After
   §I.9 that stops mattering for profiling but remains for calibration. Hidden,
   or greyed with the reason?
10. **Pre-existing, found on the way, reported not fixed:**
    (a) `duplicate_source()` returns a run under Run type = Calibration —
    `duplicate_state()` is the safe gate, and §I.9 names the wrong one;
    (b) `location_being_edited()` with no project open returns an invented
    placeholder path, so the bar shows a folder that does not exist;
    (c) `knut.ti2` mixes 0–1 and 0–100 XYZ scales in one file, so
    `_design_xyz_to_100` hands the report an L\* of 8.99 for a paper-white
    patch; (d) `TabProfile._on_load_ti3`'s file-dialog caption and filter are
    not wrapped in `tr()`; (e) `colprof`'s no-white failure reaches the user as
    Argyll's raw string — `_COLPROF_ERROR_PATTERNS` has no entry for it.
    Which of these do you want in this change, and which as their own?

---

## E12 · Rating

**Correctness — 6/10.** The destination model is right and the two spec
amendments are right. But three load-bearing statements in the design do not
survive measurement: the multiset test as written refuses ChromIQ's own files;
the repair's named validator is a tautology; and `duplicate_run` copies the
very files the import then orphans. Each was found by running the real code on
the owner's real data, and each has a concrete fix. The score is not lower
because nothing in the *destination* half is wrong — the file locations, the
stem rule and the "copy never move" rule are all correct and all cited.

**Robustness — 5/10.** As written, the change removes both existing guards
against filing a measurement into the wrong run, at the same time, and four
real chart pairs on this machine walk through the resulting hole. The repair
rewrites `SAMPLE_ID`/`SAMPLE_LOC` in data a profile is then built from, with no
undo and no working check. Against that: the original file is never touched
(verified by SHA-256 across three converts), no name is asked so no `rmtree` is
reachable, and nothing is written before validation. Cutting the repair from
this change (E9) would take this to 8.

**Maintainability — 7/10.** The plan reuses heavily and honestly, and its one
new module has no Qt. Three points off for things the plan does not mention and
someone will otherwise discover: `_guard_run`'s two different answers to "which
run" once a second tab asks; `WINDOW_SOURCES` being a `(module, class, method)`
allow-list, so the new messages **must** be tab methods; and two existing tests
that encode exactly the rules §I.10 withdraws and must be re-pointed
deliberately rather than deleted. Also: the IMPORT module's two windows are
provably untested for shape — 15 tests pass with both replaced by raisers — so
"lift the core and prove nothing changed" currently has nothing to prove it
with.

**Efficiency — 7/10.** The validation is one pass over an array against a dict;
2 064 patches is microseconds beside a `txt2ti3` subprocess. The new tests are
text fixtures and stay in the everyday tier. Three points off: today's
`duplicate_run` route copies 153 623 bytes of measurement and profile per import
in order to orphan them (measured on run 1); the filed `.ti3` would be written
twice if the repair rewrites it; and the conversion happens before validation,
so a refused file has already been converted into the run's `cache/`.

**Overall: 6.5/10** — a sound destination design carrying a repair feature that
is not ready, and resting on three claims that measurement does not support.
Ship §I.9 and §I.10 with the corrected duplicate route and the routing question;
hold the repair.

---

**STATUS: challenged**

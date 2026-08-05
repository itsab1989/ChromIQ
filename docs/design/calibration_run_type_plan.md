<!--
The committed copy of the implementation plan posted on issue #137.

It is committed on purpose: tests/test_calibration_tables_conform.py (task T12)
parses the tables in this file and fails when a row has no code anchor, or names
a symbol that no longer exists. That is what makes Knut'''s rule -- "forces
implementation, so it is not skipped silently" -- true rather than hoped for.

Keep this file and the issue comment identical.
-->

# Implementation plan — Calibration as a Run type

**Design:** this issue (all nine decisions answered). **Full draft:** [`docs/design/calibration_run_type.md`](https://github.com/itsab1989/ChromIQ/blob/feature/measurement-sounds-131/docs/design/calibration_run_type.md).
**Status:** ready to build. Nothing below is open; every assumption is stated and marked **A#**.

---

## 0. How this plan is written, and why

Knut's method, adopted here verbatim:

> *"the only way to get the implementation right is to force claude to build complete tables with all combinations of responses and input conditions for all features, and then also force mapping in the tables the code lines where input conditions are implemented and where all options of output events/actions are implemented. This forces implementation, so it is not skipped silently."*

He is right, and #130 proves it: the §M message catalogue plus its `§M-x` map is why that model shipped without a message quietly going missing — a test parses the table and fails if code and table disagree in **either** direction.

So every table below has **two** code columns:

| column | meaning |
|---|---|
| **Read at** | the exact place the input condition is evaluated |
| **Acted at** | the exact place each possible outcome is performed |

A row with an empty **Acted at** is unimplemented work, not a description. **T12 adds a test that parses these tables out of this comment's committed copy and fails if any row has no anchor, or names an anchor that no longer exists.** That is the mechanism that makes "not skipped silently" true rather than hoped for.

Line numbers are from `feature/measurement-sounds-131` at the time of writing; they are anchors to *find* the code, and the test matches on symbol names, not numbers, so it survives edits.

---

## 1. What already exists — reuse map (read this before writing anything)

| Need | Already exists | Verdict |
|---|---|---|
| A third run type | `RUN_TYPE_PROFILING` / `RUN_TYPE_VERIFICATION` (`core/measurement_target.py:18-19`), `MeasurementTarget.run_type` (`:37`) | **Add one constant.** Not a new concept. |
| The bar's combo | `_type_combo` built at `ui/measurement_target_bar.py:593-595`, tooltip `:596`, change handler `_on_type_changed:1718` → `controller.set_run_type:118` | **Add one `addItem`.** |
| Box widths that do not clip | `_fit_box` (`:951`), already used at `:1105-1115` | **Reuse.** *"Project calibration"* is longer than *"Run 8 (overwrite)"*, which is what the floor was sized for — without `_fit_box` it clips to *"Project calibratior"* (found in the mockup). |
| The `cal/` folder model | `Calibration` (`core/file_manager.py:318-384`) — `stem`, `dir`, `cal_path`, `ti1/ti2/ti3/icc/cht/ps`, `chart_tiffs()`, `exists()`, `ensure_dir()` | **Reuse whole.** |
| Archive-instead-of-delete | `Run.old_dir` (`:716`), `Run.archive_to_old` (`:732-748`) — dated subfolder | **Lift the same two onto `Calibration`.** Fixes **D1**. |
| Chart snapshot / Restore | `ChartSlot` (`workflow/chart_slot.py:64`) is a plain dataclass of `live_dir` / `snapshot_dir` / `stem` / `suffixes`; `slot_for_run:115`, `slot_for_verification:123`, `slot_for:132`; `snapshot_slot` (`workflow/verify_chart_snapshot.py:289`), `restore_slot:395`, `snapshot_matches_live:211` | **Add `slot_for_calibration`, ~6 lines.** No new snapshot logic at all. This is what makes decision 3 cheap and what fixes **D3**. |
| Calibration chart knobs | `_on_cal_target_toggled` (`ui/tabs/tab_chart.py:3612-3636`) with `_pre_cal_snapshot` restore | **Move the handler to the run-type switch**, and extend it (§4.2a). |
| Routing a build to `cal/` | `ChartParams.cal_target` (`workflow/chart_creator.py:519`), consumed at `:594`, `:989`, `:1147`, `:1310`, `:1583`, `:1646` | **Reuse.** Transient field, in no preset and no settings key → **no migration**. |
| The `.cal` prefill | `_check_for_cal_file` (`ui/tabs/tab_chart.py:3545`), `set_cal_file_paths` (`:3536`) | **Reuse, with the D4/D6 fixes.** |
| Calibration preference | `calibration_mode` (`core/settings.py:158`), fanned out by `MainWindow._apply_calibration_mode` (`ui/main_window.py:1142-1146`) to four tabs' `set_calibration_mode` | **Reuse; the bar becomes a fifth listener.** |
| printcal wrapper | `workflow/printcal_runner.py` incl. the "no previous .cal" error text (`:42-50`) | **Reuse.** |
| Chart-integrity assessment | `assess_profiling_chart` (`workflow/chart_integrity.py:147`) | **Reuse, with a calibration branch.** Fixes **D2**. |
| Where files are explained | `ui/file_guide.py:261` (`cal/` row) | **Extend.** |

**Boundary against existing features — say this in the Dictionary (T11):** a **Profiling run** builds a profile; a **Verification** checks a finished profile; a **Calibration** prepares the *printer* before either. Profiling and Verification are per-run and there can be many; **there is exactly one calibration per project**. That single fact is why `Profile run` is fixed and disabled while Calibration is selected — see A1.

---

## 2. The one fact the data model must obey

**A1 (assumption, from the code).** `Calibration` is per **project**, not per run (`core/file_manager.py:318`, and the file guide already tells the user so at `ui/file_guide.py:261`). Therefore *"Profile run = Run 3 · Run type = Calibration"* is meaningless. The bar keeps three controls; while Calibration is selected, **Profile run** shows one fixed, disabled entry — *"Project calibration"* — and the Verification box hides.

`MeasurementTarget.profile_run` is left **untouched** when switching to Calibration, so switching back restores the user's run selection. The calibration target is identified by `run_type` alone. **This is the single most important invariant in the change** — see R3.

---

## 3. Tasks, in build order

Each is small, independently green, and ends with a full `--runslow` gate before the next begins.

| # | Task | Touches | Fixes |
|---|---|---|---|
| **T1** | `RUN_TYPE_CALIBRATION` constant + `MeasurementTarget.is_calibration()` | `core/measurement_target.py` | — |
| **T2** | `Calibration.old_dir` + `Calibration.archive_to_old`, and `ChartCreator` archives instead of `reset()` | `core/file_manager.py`, `workflow/chart_creator.py:594` | **D1** |
| **T3** | `slot_for_calibration` + `slot_for` dispatch | `workflow/chart_slot.py` | **D3** (half) |
| **T4** | Bar: third combo entry, fixed Profile run, hidden Verification box, button states | `ui/measurement_target_bar.py` | — |
| **T5** | Bar listens to `calibration_mode` (entry present only while the preference is on) | `ui/main_window.py`, `ui/measurement_target_bar.py` | — |
| **T6** | Create Chart: run type drives `cal_target`; the knob preset + **the Auto/Pages spec (§4.2a)** move off the checkbox; checkbox retired | `ui/tabs/tab_chart.py` | **D7** |
| **T7** | `_on_generate`: the `not cal_target_active` guard on the auto-patch estimate | `ui/tabs/tab_chart.py:8210` | **D7** |
| **T8** | `_resolve_target_chart` calibration branch (preview / Print / Measure all follow) | `ui/tabs/tab_chart.py:9081` | **D3** |
| **T9** | `_confirm_displacing_results` calibration branch + the new warning | `ui/tabs/tab_chart.py:8832` | **D2** |
| **T10** | Prefill: gate on the preference, fill both, switch neither, say so | `ui/tabs/tab_chart.py:3545` | **D4, D6** |
| **T11** | Tab 4 module gating; `RunMeta.calibration_used`; `-N` surfaced; all user-facing text + Dictionary + file guide + i18n | `ui/tabs/tab_profile.py`, `core/file_manager.py:256`, `data/parameters.yaml`, `ui/file_guide.py`, `data/i18n/*` | **D5** |
| **T12** | The table-conformance test (§0) + the on-screen walk | `tests/`, `scripts/` | — |

---

## 4. The tables

### Table A · Run type → every control in the bar

Input condition: `MeasurementTarget.run_type`. Read at `MeasurementTargetBar._sync_from_controller` (`ui/measurement_target_bar.py:1605`), which is the **single** place the bar's state is derived — no second path may set these.

| Control | Profiling | Verification | **Calibration** | Read at | Acted at |
|---|---|---|---|---|---|
| `_type_combo` items | Profiling · Verification | same | + **Calibration**, only while `calibration_mode` is on | `settings.get("calibration_mode")` | **T5** — `MeasurementTargetBar.set_calibration_mode` (new) |
| `_run_combo` contents | one entry per run + *New run* | same | **one entry: "Project calibration"** | `t.run_type` | **T4** — `_sync_from_controller`, run-combo branch (`:1636-1643`) |
| `_run_combo` enabled | yes | yes | **no** | `t.run_type` | **T4** — same block |
| `_run_combo` tooltip | current | current | **A4 text** (§Help, item 4) | `t.run_type` | **T4** |
| `_run_combo` width | `_fit_box` | `_fit_box` | `_fit_box` **incl. "Project calibration"** | — | **T4** — `_fit_box` (`:951`), call site `:1105` |
| `_verify_label` / `_verify_combo` | hidden | shown | **hidden** | `t.is_verification()` (`:1646`) | **T4** — `:1647-1649` |
| `_restore_btn` visible | yes | yes | **yes** | `_show_verification` (`:1654`) | **T4** |
| `_restore_btn` enabled | per `restore_state()` | per `restore_state()` | **per `restore_state()`, calibration branch** | `controller.restore_state` (`:228`) | **T3/T4** — `restore_state` gains `slot_for_calibration` |
| `_duplicate_btn` | per `duplicate_state()` | per `duplicate_state()` | **disabled + reason** | `controller.duplicate_state` (`:427`) | **T4** |
| `_delete_btn` | per `delete_state()` | per `delete_state()` | **disabled + reason** | `controller.delete_state` (`:338`) | **T4** |
| `t.profile_run` | user's choice | user's choice | **unchanged, not overwritten** | — | **T4** — see **R3** |

### Table B · Run type → Create Chart controls (§4.2a, decision 9)

Read at the run-type change handler (**T6**, the code moving out of `_on_cal_target_toggled`, `ui/tabs/tab_chart.py:3612`).

| Control | → Calibration | → back to Profiling / Verification | Acted at |
|---|---|---|---|
| Total Patch Count `-f` · **Auto** | untick **and disable**, value `0` | **restore tick + value** | **T6** — `_on_auto_patches_toggled` (`:4729`) + extended `_pre_cal_snapshot` |
| White Patches `-e` · **Auto** | untick **and disable**, value `0` | **restore tick + value** | **T6** — `_on_auto_neutral_toggled("white", …)` (`:4767`) |
| Black Patches `-B` · **Auto** | untick **and disable**, value `0` | **restore tick + value** | **T6** — `_on_auto_neutral_toggled("black", …)` |
| Grey Axis Steps `-g` · **Auto** | untick **and disable**, value `0` | **restore tick + value** | **T6** — `_on_auto_neutral_toggled("grey", …)` |
| Single Channel Steps `-s` | **`20`** | **restore the user's value** | **T6** |
| Thorough Optimisation `-G` | off | restore | **T6** (exists today) |
| printtarg randomise `-r` | on | restore | **T6** (exists today) |
| Pages | **disable** | re-enable per Auto patch count | **T6** — `_on_auto_patches_toggled` already disables it (`:4737-4744`) |
| targen section collapsed | **open, scrolled to `-f`…`-s`** | leave as the user had it | **T6** |
| "Create chart for calibration" checkbox | **gone** | gone | **T6** — remove `_cal_target_check` (`:2059`) and its group |

**Why disabled and not merely unticked:** a greyed box says *this is not yours to set right now*; an unticked one invites the user to tick it and get a chart printcal cannot use.

**A2.** "Restore what they were" means the **tick state and the value**, snapshotted at the moment of switching *to* Calibration, per control. Switching Calibration → Calibration is a no-op (no re-snapshot), or the user's originals would be overwritten with calibration values. **This is R1.**

### Table C · Generate → where files land, what is archived, what warns

| Condition | Chart goes to | Existing work | Window shown | Read at | Acted at |
|---|---|---|---|---|---|
| Run type = Profiling, run has nothing | `runs/runN/` | — | none | `assess_profiling_chart` (`workflow/chart_integrity.py:147`) | existing |
| Profiling, run has a measurement/profile | `runs/runN/` | → `runs/runN/old/<ts>/` | M-CHART-PROFILING | same | existing |
| Verification, run has verifications | `runs/runN/verifications/` | per §4 | M-CHART-W4 etc. | same | existing |
| **Calibration, `cal/` empty** | **`cal/`** | — | **none** | **T9** — `_confirm_displacing_results` (`:8832`) calibration branch | **T9** |
| **Calibration, `cal/` has a chart but no `.ti3`** | **`cal/`** | **→ `cal/old/<ts>/`** | **M-CAL-REPLACE-CHART** | **T9** | **T2** archive + **T9** window |
| **Calibration, `cal/` has a measured `.ti3` and/or `.cal`** | **`cal/`** | **→ `cal/old/<ts>/`** | **M-CAL-REPLACE-MEASURED** (names what moves) | **T9** | **T2** + **T9** |
| **Calibration, runs exist that were built on that `.cal`** | **`cal/`** | **→ `cal/old/<ts>/`; runs untouched** | **M-CAL-REPLACE-MEASURED** + the affected-runs line | `RunMeta.calibration_used` (**T11**) | **T9** |

**Today this is `Calibration.reset()` → `shutil.rmtree(cal/)`** (`core/file_manager.py:380-384`, called from `workflow/chart_creator.py:594-595`) — **no warning, no archive, unrecoverable.** That is D1 and it is the single most valuable fix in this issue. **Never delete: archive.**

### Table D · Run type = Calibration → each tab

| Tab | Behaviour | Read at | Acted at |
|---|---|---|---|
| 1 Create Chart | Table B; preview/Print/Measure resolve `cal/`'s chart | `_resolve_target_chart` (`:9081`) | **T8** |
| 2 Print Chart | unchanged — prints whatever tab 1 resolved | — | (no change; covered by **T8**) |
| 3 Measure | unchanged — measures whatever tab 1 resolved; writes `cal/<stem>.ti3` | — | (no change; **T8**) |
| 4 Calibration & Profiling | **Create Calibration File only** | `t.run_type` | **T11** — `TabProfile.set_calibration_mode` (`ui/tabs/tab_profile.py:628`) gains a run-type input |
| 4, Run type = Profiling **with** the preference on | Build Profile **and** Apply Calibration | same | **T11** |
| 5 Check & Refine | unchanged | — | *(nothing to do — no calibration branch)* |

### Table E · Restore / Duplicate / Delete × Run type

| Button | Profiling | Verification | **Calibration** | Acted at |
|---|---|---|---|---|
| **Restore Used Chart** | run's chart | that date's chart | **the calibration chart** (decision 3) | **T3** `slot_for_calibration` + `restore_state` (`:228`) |
| …with nothing stored yet | greyed, "nothing stored" | same | **greyed, calibration wording** | **T4** |
| …stored copy identical to live | greyed (`snapshot_matches_live:211`) | same | **same rule, free** | **T3** |
| **Duplicate run** | enabled | enabled | **greyed + "switch Run type to Profiling"** | **T4** |
| **Delete** | enabled | enabled | **greyed + "a project has one calibration; it is replaced, not deleted"** | **T4** |

### Table F · The `.cal` prefill (decision 7 — fixes D4 and D6)

Inputs: `calibration_mode` × does `cal/<stem>.cal` exist × what the user has already set.

| `calibration_mode` | `.cal` exists | `-K` field | `-I` field | `-K` on? | `-I` on? | Status line | Read at | Acted at |
|---|---|---|---|---|---|---|---|---|
| **off** | no | untouched | untouched | no | no | none | `settings.get("calibration_mode")` | **T10** |
| **off** | yes | **untouched** | **untouched** | **no** | **no** | **none** | same | **T10** — this is **D6**: today it fills and silently enables `-I` while the group is hidden |
| on | no | untouched | untouched | no | no | none | `Calibration.exists()` (`file_manager.py:376`) | **T10** |
| **on** | **yes** | **filled** | **filled** | **no** | **no** | **the A8 line** | `_check_for_cal_file` (`:3545`) | **T10** |
| on, user already set `-K` by hand | yes | **not overwritten** | filled | user's | no | "…already set" variant | **T10** | **T10** |

**The trap:** `ParameterWidget.set_value` **ticks the enable checkbox** for a `file_path` parameter whenever the value is non-empty (`ui/parameter_widget.py:175-178`). `_check_for_cal_file` sets `-K` then `-I`, and the mutex switches `-K` back off — which is why today's app silently arrives at "`-I` on, `-K` off" (**D4**). **T10 must set the value without tripping that tick** (block signals / set the control directly), not merely untick afterwards, or the mutex fires again. **This is R2.**

### Table G · Edge cases — every one, with expected behaviour

| # | Condition | Expected | Acted at |
|---|---|---|---|
| E1 | Preference off, project has `cal/` | Nothing uses it; file guide explains it (C13 text). No warning. | **T5**, **T11** |
| E2 | Preference turned off **while** Run type = Calibration | Fall back to Profiling, keep `profile_run`; no file touched | **T5** |
| E3 | Preference turned on, project has no `cal/` | Calibration selectable; tab 1 says "No calibration chart in this project yet" | **T5** |
| E4 | Calibration selected, **no project loaded** | Whole bar greyed, existing hint — unchanged | `has_project` (`:1613`) |
| E5 | Calibration selected **while measuring** | Bar locked, existing wording — unchanged | `measuring` (`:1616`) |
| E6 | Generate with Calibration, `cal/` empty | Build, no window | **T9** |
| E7 | Generate with Calibration over a measured calibration | Archive to `cal/old/<ts>/`, M-CAL-REPLACE-MEASURED | **T2**, **T9** |
| E8 | Generate with **Profiling** while `cal/` exists | `cal/` **untouched**; today's false warning about the run is gone | **T9** (D2) |
| E9 | Restore with Calibration, nothing measured yet | Greyed, calibration wording | **T4** |
| E10 | Restore with Calibration, snapshot == live | Greyed (`snapshot_matches_live`) | **T3** |
| E11 | Restore with Calibration after regenerating | Restores from `cal/chart/` | **T3** |
| E12 | Old project, schema 1/2, no `cal/` | Loads and migrates as today; `calibration_used` absent → "unknown" | **T11** |
| E13 | Old project **with** `cal/` from before this change | Works unchanged; no `cal/old/`, no `cal/chart/` until first use | **T2**, **T3** |
| E14 | `cal/` exists but `.cal` missing (chart made, never measured) | Restore available if snapshot exists; tab 4 says measure it first | **T3**, **T11** |
| E15 | `cal/` deleted **outside** ChromIQ while selected | No crash; treated as E3 | **T4** — `Calibration.exists()` guarded |
| E16 | Switch Calibration → Profiling → Calibration | Auto/`-s` restore then re-apply; **no double snapshot** (A2) | **T6** — **R1** |
| E17 | Switch to Calibration in **Guided** mode | Calibration forces Manual (as `set_calibration_mode` already does, `:3527`) | **T6** |
| E18 | A preset is loaded while Calibration is selected | Preset values land in the snapshot, not on screen; calibration values win until the type changes | **T6** |
| E19 | N-channel device type (`-d6`+) with Calibration | `-s` ramp per channel; `-N` visible and off (decision 8) | **T11** |
| E20 | Two ChromIQ windows on one project | Out of scope — unchanged from today (no file locking exists) | *(nothing to do — pre-existing, not introduced here)* |
| E21 | `Run type = Calibration` persisted in settings, preference later off | On load, coerce to Profiling (E2 path) | **T5** |

### Table H · Every user-facing string, and where it lives

All drafted in this issue under *"Help text this would touch"*. **English placeholders during beta; German written with them; the other eleven before GA.**

| # | String | Lives in | Acted at |
|---|---|---|---|
| A1 | "Enable calibration options" ⓘ, last paragraph | `ui/dialogs/settings_dialog.py:440` | **T11** |
| A2 | "Run type" ⓘ, third bullet | `ui/measurement_target_bar.py:596` | **T4** |
| A3 | "Profile run and Run type" ⓘ | `ui/measurement_target_bar.py:629` | **T4** |
| A4 | "Profile run" ⓘ while Calibration | `ui/measurement_target_bar.py:570` | **T4** |
| A5 | Restore / Duplicate / Delete ⓘ, calibration lines | `:661`, `:696`, `:730` | **T4** |
| A6 | The four greyed "Auto" boxes | `ui/tabs/tab_chart.py` (`-f`/`-e`/`-B`/`-g` rows) | **T6** |
| A7 | "Single Channel Steps" ⓘ, calibration sentence | `ui/tabs/tab_chart.py` (`-s` row) | **T6** |
| A8 | The `.cal` prefill status line | `ui/tabs/tab_chart.py:3545` | **T10** |
| A9 | "Declare extra inks as alpha channels (-N)" | `data/parameters.yaml` | **T11** |
| B6 | "Create Chart for Calibration" ⓘ | retired with the checkbox | **T6** |
| B7 | Calibration & Profiling header, steps 1-2 | `ui/tabs/tab_profile.py:171` | **T11** |
| B8 | printtarg `-K` / `-I` ⓘ | `data/parameters.yaml:886`, `:915` | **T10** |
| C9 | Dictionary: "Calibration run" | `ui/dialogs/welcome_dialog.py:599` | **T11** |
| C10 | File guide: `cal/old/` | `ui/file_guide.py:261` | **T11** |
| C11 | File guide: `cal/chart/` | same | **T11** |
| C12 | File guide: which calibration a run used | same | **T11** |
| C13 | File guide: `cal/` while the preference is off | same | **T11** |
| M1 | M-CAL-REPLACE-CHART | new | **T9** |
| M2 | M-CAL-REPLACE-MEASURED | new | **T9** |

**Two new windows, drafted now so T9 is not left inventing prose.** Both follow #130's rule: say what will be moved, where it goes, and that nothing is deleted.

> **M-CAL-REPLACE-CHART** — *title:* "Replace this project's calibration chart?"
> You already made a calibration chart for this project, but it has not been measured yet. Generating a new one replaces it.
> Nothing is deleted: the chart you have now is moved to the project's "cal/old" folder, in a folder named with today's date, and you can go back to it at any time.
> **Buttons:** *Replace the chart* · *Cancel*

> **M-CAL-REPLACE-MEASURED** — *title:* "Replace this project's calibration?"
> This project already has a finished calibration, and generating a new chart starts that work again from the beginning. You would need to print the new chart and measure it before this project has a calibration once more.
> These move to the project's "cal/old" folder, in a folder named with today's date — nothing is deleted, and you can go back to them at any time:
> • the calibration chart
> • its measurement
> • the calibration file (.cal) made from it
> {runs_line}
> **Buttons:** *Replace the calibration* · *Cancel*
>
> `{runs_line}` — real singular/plural, never "(s)":
> • one run → "Run 3 was built using this calibration. It is not changed, and its profile keeps working — but it was made with the calibration you are about to replace."
> • more → "Runs 3, 5 and 6 were built using this calibration. They are not changed, and their profiles keep working — but they were made with the calibration you are about to replace."
> • none → the line is omitted entirely.

---

## 5. Regression risk register

The bar is shared by three tabs, and #130's history is mostly sequencing bugs of exactly that kind. Each risk names the test that would catch it.

| # | Risk | Why it is plausible | Prevention | Caught by |
|---|---|---|---|---|
| **R1** | Switching Calibration → Calibration re-snapshots, so the user's originals are lost | The handler is called from a combo whose signal can fire twice (`_syncing` guard exists at `:1719` but the tab's own path is new) | Snapshot **only** on a real transition into Calibration; `_pre_cal_snapshot is None` is the guard, as today (`:3622`) | **T6** test: `to → to → away` restores the originals (E16) |
| **R2** | The prefill re-ticks `-I` | `ParameterWidget.set_value` ticks the enable box for `file_path` (`ui/parameter_widget.py:175-178`) — unticking afterwards re-triggers the `-K`/`-I` mutex | Set the value **without** tripping the tick, then assert both are off | **T10** test asserting `-K` off **and** `-I` off after prefill (Table F row 4) |
| **R3** | `profile_run` clobbered by selecting Calibration, so switching back lands on the wrong run | The run combo is rebuilt with one item; a naive `_select_data` would write that back through `_on_run_changed` (`:576`) | Do not emit while Calibration is selected; leave `MeasurementTarget.profile_run` untouched (A1) | **T4** test: select run3 → Calibration → Profiling ⇒ still run3 |
| **R4** | A calibration build silently wipes `cal/` | It does today (`Calibration.reset()`, `file_manager.py:380`) | Replace the call with `archive_to_old` | **T2** test: `cal/` contents present under `cal/old/<ts>/` after a rebuild; `reset()` no longer called from `chart_creator` |
| **R5** | Verification snapshot logic broken by the new slot | `slot_for` dispatches by `isinstance` (`chart_slot.py:132`) | Add the calibration branch **before** the `Verification` check by explicit type, not by duck-typing | **T3** test: all three slot kinds resolve to distinct dirs |
| **R6** | `-f0` still overridden at Generate | The estimate does not consult `cal_target` (`:8210` vs `:8151`) | The `not cal_target_active` guard (**T7**) | **T7** test forcing Auto on in code and asserting `-f0` survives (D7) |
| **R7** | Guided mode reached with Calibration selected | Calibration is Manual-only | Force Manual, as `set_calibration_mode` already does (`:3527`) | **T6** test (E17) |
| **R8** | The `Calibration` combo entry appears with the preference off | Two independent gates (settings + bar build order) | One gate: the bar's own `set_calibration_mode`, called from the existing fan-out (`ui/main_window.py:1142`) | **T5** test both directions, plus E21 coercion |
| **R9** | Old projects break | New `cal/old/`, `cal/chart/`, `RunMeta.calibration_used` | All three are *absent-means-unknown*; nothing is required to exist | **T11** test on a schema-1 fixture (E12, E13) |
| **R10** | A window's text drifts from the table | The #130 lesson exactly | Table H is machine-checked | **T12** |

---

## 6. Migration

**Nothing to migrate, by construction** — and that is a design choice, not luck:

- `cal_target` is transient (`workflow/chart_creator.py:519`): no preset, no settings key.
- `RunMeta.calibration_used` is a new optional field; **absent means "unknown"**, which is the honest state of every run built before it (`core/file_manager.py:256`).
- `cal/old/` and `cal/chart/` are created on first use.
- **A3:** the persisted `run_type` may already contain `"calibration"` if a user downgrades. On load, an unknown or preference-disabled run type coerces to Profiling (E21) rather than raising.
- No `settings_schema` bump is needed. *(If T11 ends up changing a default, it needs one — the project rule is that changing a default requires a migration.)*

---

## 7. Test plan

Every row of every table above becomes a test. Layout:

| File | Covers |
|---|---|
| `tests/test_calibration_run_type_bar.py` | Table A, Table E, R3, R8, E2/E4/E5/E21 |
| `tests/test_calibration_run_type_chart.py` | Table B, R1, R6, R7, E16/E17/E18 |
| `tests/test_calibration_archive.py` | Table C, R4, E6/E7/E8, D1 |
| `tests/test_calibration_slot.py` | Table E rows, R5, E9-E11, E14, D3 |
| `tests/test_calibration_prefill.py` | Table F, R2, D4, D6 |
| `tests/test_calibration_help_text.py` | Table H — every string present, every placeholder resolved, singular/plural real |
| `tests/test_calibration_tables_conform.py` | **T12** — parses the tables, fails on a missing anchor or a dead symbol |
| `scripts/drive_calibration_run_type.py` | the on-screen walk: every row of Tables A, B, D driven in the real `MainWindow` |

**Mutation-check every one:** put the bug back, watch the test fail, restore. A test that passes against both states is guarding nothing.

**On-screen is not optional here.** The bar is shared by three tabs and its faults are sequencing faults; headless tests missed exactly this class three times in #130. `scripts/mockup_calibration_run_type.py` already launches the real `MainWindow` in the proposed state — the driver is that script with assertions instead of screenshots.

**Gate:** `QT_QPA_PLATFORM=offscreen pytest --runslow -n 4 --dist loadfile` green after **each** task, not just at the end.

---

## 8. Colour science — what this does and does not touch

Calibration is a **device-response** step, not a colorimetric one: `printcal` linearises per channel from a single-channel ramp, before any profile exists. It changes no illuminant, no rendering intent and no gamut computation. D50, the intents and ΔE are untouched by everything in this plan. The one honest statement to keep in the help text is that a calibration makes the printer *repeatable*, which is what makes a profile stay true — not that it improves colour accuracy on its own.

---

## 9. Rating

**Correctness 9 · Robustness 9 · Maintainability 9 · Efficiency 9.**

Every behaviour is specified with both a read site and an act site; the risky parts (R1-R10) each name the test that catches them; nothing deletes user work; nothing needs migrating. Held at 9 rather than 10 by the one thing no plan can retire: the bar is shared, and shared state is where #130's bugs lived. The mitigation is the one that worked there — decisions in pure functions, tabs left to rendering, and the finished thing driven on screen.

---

## 10. Open questions

**None.** All nine design decisions are answered. Three assumptions are stated above — **A1** (one calibration per project, so `profile_run` is fixed and untouched), **A2** (restore means tick *and* value, snapshotted once per transition), **A3** (an unknown or disabled run type coerces to Profiling) — each of which follows from the code cited beside it. If any is wrong, say which and the affected table rows change; nothing else does.

**Ready to implement.** Start at T1.

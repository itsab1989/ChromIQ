# Checkpoint 01 (Agent 2): the five high findings re-tested, mechanisms named

Time: 09:50 to 10:10. Drivers: Review/Test Runs/drivers/r_lib.py (own library), r01_f001_f003.py, r02_f007_f018.py, r02b_guided_p3.py, r03_f024_gamut.py. Logs and JSON: Review/Test Runs/logs/r01_results.json, r02_results.json, r02b_results.json, r03_results.json, *.log. Shots: Review/Screenshots/R01-f001-f003, R02-f007-f018, R03-f024-gamut. All unattended; every dialog was answered by the armed watcher after matching its text ("quite fill" -> OK, "already" -> Continue this project); no unexpected dialog, no ERROR or CRITICAL log record in any run. Projects created: R2-High, R2-Guided (in /Users/Basti/ChromIQ-assessment).

Sandbox: app built as main() does, settings = the sandbox ini, presets = the sandbox copy, projects = /Users/Basti/ChromIQ-assessment (logged at the top of every run).

## Verdicts so far
| F | verdict | one line |
|---|---|---|
| F-001 | CONFIRMED | 418 built, 425 estimated, hint "107 more (525 in total)", .ti1 400 / .ti2 418, on a fresh project with my own steps; patch-first -f 300: total 315 both, fill-up 0 estimated vs 15 built |
| F-003 | CONFIRMED, mechanism found (Agent 1 had it INFERRED unknown) | see below |
| F-007 | CONFIRMED | Preferences T 38 -> 50, OK: panel 38, estimate 621 unchanged; build Top 38.9 flagged against 50; re-tick picks up 50; restore to 38 leaves the panel at 50 |
| F-018 | PARTLY RIGHT | the p3 A4 landscape red verdict is exact (L 26 < 28, T 33.4 < 40) but the cause and the scope are wrong: no clamp exists on the Guided path and three more defaults are red |
| F-024 | CONFIRMED and extended | leak survives run switch, run type switch, clicking the greyed button and opening another project; what gave Generate back was visiting the gamut module on a run WITH a profile |
| F-023 | CONFIRMED | Stop visible, in-flight True, runner not running, on every screen after the leak |
| F-002 | CONFIRMED (New run instance) | New run under Profiling: "Margins: OK" and 240 on screen while the preview is empty |

## F-003: the writer, named
Trace (r01 log 10:01:46, stack captured on every set_value of the -L / -a / -m / -r widgets):
`_on_generate` (tab_chart.py:13250) -> `_align_current_run_to_target` -> `proj.new_run()` -> `_adopt_new_run_settings` (copies the New-run seed block into runs/run2/meta.json create_chart_settings) -> `ctl.set_profile_run(run2)` -> MainWindow `_save_settings_of_visible_tab` (1626) then `_load_settings_of_visible_tab` (1646) -> `load_target_settings` -> `per_target_settings.apply` writes -L True, -a 0.95, -m 10, -r False onto the widgets; then `_on_target_changed` (16892) loads them a second time. `_collect_params` ran at 13183, BEFORE all this, so the creator received disable_left_border=False, patch_scale=1.0 and executed `printtarg -ii1 -pA4 -t300 -m10 -M10 -c R2-High` (the user's command; the sheet has the clip band and 8.0 mm patches). W1 at `_on_generate_finished` (17302) then stored the flipped widgets: meta.json printtarg-L True / -a 0.95; sidecar printtarg_fields -L True / -a 0.95; sidecar create_chart_settings (written by the creator from params) -L False / -a 1.0.
The values come from the New-run seed block (§4a): it was captured when "New run" was selected while run1 (an engine build, printtarg rows hidden at their defaults) was loaded, and it is never updated by the user's later edits; `_adopt_new_run_settings` adopts THAT block, not the screen. Spec §4a (Knut, quoted): the block "can be modified by user to what is desired for the new run. Then when Generate Chart is pressed, all these settings are copied into the new runs parameter slot". The code copies the pre-edit block, so this is a spec violation, not only a clobber.
Agent 1's second variant (D05b: the EXECUTED command also carried -L) did not reproduce here: in both my Generate presses the executed command matched the preview and the panel. Variant B (overwrite the same run, no target change, -L unticked again): no flip, executed `-a0.95 -m10 -M10`, panel stays as set; so the fault is confined to a Generate that CREATES the run.

## F-018: what is really there
- `ChartCreator._apply_margin_thresholds` has NO caller (grep ui/ workflow/ core/ main.py: only its definition). `tests/test_chart_creator_engine.py::test_guided_does_not_enforce_margin_thresholds` pins the opposite of Agent 1's "expected": "Guided mode (no recipe) does NOT clamp to the margin thresholds ... Guided behaves like before the #93 threshold feature". So Agent 1's "the clamp works for i1 and CM" is wrong; no clamp line appeared in any of my nine Guided builds and every recipe carries 6/6/6/6.
- Guided defaults red under the shipped seeds, all OBSERVED (R2-Guided, nothing changed but instrument, paper, 1 page): p3 A4 landscape (L 26 < 28, T 33.4 < 40; 112 patches, Agent 1's case), p3 A4 PORTRAIT (L 26 < 28, R 8.0 < 9; 99 patches), i1 A4 LANDSCAPE (T 29.5 < 38; 544), i1 Letter LANDSCAPE (T 27.2 < 38; 544). Green: i1 A4 portrait (484), i1 A4 portrait 2 pages (968), CM A4 portrait (105), CM A4 landscape (100).
- Severity stays high for the user-visible effect (a first Guided chart flagged red with no control to fix it) but the question is a design one: the code and the test say Guided ignores the table on purpose; the seeds say the sheet is unreadable. Owner decision.

## F-024: extra facts
- After the leak, `_chart_build_in_flight()` returns True with `_runner.is_running` False on every screen (it reads the disabled button, tab_chart.py:18581), which is why Stop shows.
- Re-enabled by: visiting FROM PROFILE GAMUT on run2 (has a profile) -> `_refresh_gamut_state` sets Generate on. Not re-enabled by: Guided, Manual, Run type Profiling, run switch, project switch, clicking the button.
- The leak crossed into A1-EngineVsPrinttarg (a plain profiling project with a chart): Generate greyed and STOP shown on open (shot R03/06).

## Next
Checkpoint 02: the engine (estimate vs render on my own sample, fixed counts, furniture accounting incl. strip labels off, F-005/F-006/F-008/F-012/F-021/F-019/F-025), then presets/built-ins (F-015/F-016/F-017/F-027), calibration (F-029), the gaps list, first-time-user probes.

# AGENT2 review report: independent verification of Agent 1's Create Chart assessment (ChromIQ 4.2.0, master 80975e65)

Reviewer: Agent 2, sceptical second opinion. Repo read-only throughout. Everything below was done in the real app on the real screen, built the way main() builds it, with the owner's look (neutral, English, log hidden) from the sandbox settings file, the sandbox presets copy and the projects folder /Users/Basti/ChromIQ-assessment. Every modal was answered by a watcher that matched the dialog's text first and clicked a named button; every run was unattended (two of my own drivers blocked and were killed by me or by a shell watchdog; no human clicked anything in the app). Grades: OBSERVED / PARTIAL / INFERRED / UNKNOWN. Verdicts: CONFIRMED / NOT REPRODUCED / WRONG / PARTLY RIGHT. No em dash in anything I wrote. Paths are relative to /Users/Basti/Desktop/Create Chart Assessment/.

Deliverables: Review/checkpoint-01..03, Review/R-*.md (one per reviewed finding or new item, 25 files), Review/Test Runs/drivers (r_lib.py plus r01..r08), Review/Test Runs/logs (every app log record of every run plus *_results.json), Review/Screenshots (eight folders, about 60 shots), this report.

## 1. What I re-tested and how

Time 09:50 to 11:00. Ten drivers, all my own (r_lib.py is my library; I read Agent 1's cc_lib for the widget names and wrote my own steps). Projects created: R2-High, R2-Guided, R2-Engine; Demo-Full-RGB, A1-EngineVsPrinttarg and R2-High were also written to by the tests. About 45 chart builds by the app, 2 Preferences round trips through the real dialog, 4 built-in presets, 1 external patch set load, 1 calibration Generate (calibration mode on for that session only, switched off again), 3 project switches through the real Open Project route and 6 through the session-restore route.

Weighting: about 60 % on the engine (F-001, F-003, F-005 to F-008, F-012, F-014, F-018 to F-021, F-025, an own estimate-versus-render sample, furniture accounting, expert rows, Save as Defaults, the Guided clamp question), 40 % on the rest (F-002, F-004, F-009, F-011, F-015 to F-017, F-022 to F-024, F-026, F-027, F-029, the refinement row, removed files, focus order, first-time-user probes, the sandbox).

Instrumentation that Agent 1 did not use: a stack trace on every write to the -L / -a / -m / -r widgets and on `ChartCreator.generate` (r01), which is how F-003's writer was named; file listings by NAME before and after a failed build (r05), which is how the exports/ loss was seen.

## 2. Verdict table (every Agent 1 finding)

| F | Agent 1 sev | verdict | one line why | R file |
|---|---|---|---|---|
| F-001 | high | CONFIRMED | 418 built / 425 estimated / hint "107 more of 525", .ti1 400, .ti2 418, on my own project; the fix pattern (`area_target_count`) already exists in the same file for the helper-marker overlay | R-001 |
| F-002 | medium | CONFIRMED | New run: empty preview, frames "Margins: OK" and run2's 240; also under removed files (R-108) | R-002 |
| F-003 | high | CONFIRMED, mechanism found; second variant NOT REPRODUCED | `_align_current_run_to_target` adopts the New-run seed block and `set_profile_run` reloads it over the user's edits, twice, before W1 stores it; the executed command was the user's in both my presses | R-003, R-105 |
| F-004 | low | CONFIRMED | engine on unticks Stamp; coupling in code | R-004 |
| F-005 | medium | CONFIRMED | clip Off gains nothing with instrument margins (525/525); with own 10 mm margins it gains 58 | R-005 |
| F-006 | medium | CONFIRMED | i1 A3: no verdict at all, notes live only in the (i) hover | R-006 |
| F-007 | high | CONFIRMED | panel 38 after T 50 saved; build 38.9 flagged against 50; restore leaves the panel at 50 | R-007 |
| F-008 | medium | CONFIRMED | area-first cap 200: 43 per strip; patch-first: 18 | R-008 |
| F-009 | low | CONFIRMED | SS: ticked, four boxes locked, no tooltip | R-009 |
| F-010 | low | not retested; code agrees | `_chart_own_margins` has no ruler key | R-009 |
| F-011 | low | PARTLY RIGHT | one OK button: yes; "text replaced": no, OK acts as No, the example table cannot be loaded over existing text | R-011 |
| F-012 | medium | CONFIRMED (baseline supplied) | valid tokens expand; one bad token leaves all literal; the panel's live preview warns nothing | R-012 |
| F-013 | low | not retested; code agrees | image branch overlays the text | R-009 |
| F-014 | medium | PARTLY RIGHT | Create Chart never runs preflight: true; "no caller in ui/": false, Preferences > Chart Layout runs `preflight.check` and `indicator_width_warning` | R-014 |
| F-015 | medium | CONFIRMED | printtarg line under a CM A3+ prebuilt chart and under an engine built-in | R-015-016-017 |
| F-016 | low | CONFIRMED | prebuilt: engine on -> off silently; "none" keeps the built-in's 200 dpi and margins | R-015-016-017 |
| F-017 | medium | CONFIRMED, broader | a ColorMunki A3+ "by Pharmacist" built-in is red against the CM seeds (5.3 < 6 mm), not only the i1Pro ones | R-015-016-017 |
| F-018 | high | PARTLY RIGHT | the red p3 A4 landscape verdict is exact; the cause ("the clamp works for i1 and CM, overridden here") is wrong: no clamp runs on the Guided path, `_apply_margin_thresholds` has no caller and a shipped test pins that Guided does not clamp; three more defaults are red (p3 A4 portrait, i1 A4 landscape, i1 Letter landscape) | R-018, R-101 |
| F-019 | medium | CONFIRMED, fact added | the app logs "engine patch estimate failed" before it launches targen | R-019 |
| F-020 | medium | not retested (6 min); ranges confirmed in code | | R-009 |
| F-021 | medium | CONFIRMED | after a 22-page build and a real re-open: panel 1, hidden spin 20 | R-021 |
| F-022 | low | CONFIRMED (items 1, 2, 5 checked at source) | printtarg.c: 240 - lcar - tspa unless -P | R-022 |
| F-023 | low | CONFIRMED | same defect as F-024, fold | R-023 |
| F-024 | high | CONFIRMED, extended | leak survives run switch, type switch and project switch; only a gamut visit on a run WITH a profile gives Generate back | R-024 |
| F-025 | medium | PARTLY RIGHT | preview blank until a round trip: yes; "stale Margins: OK": no (placeholders, also in Agent 1's own shot); and the failed build deleted exports/ (R-102) | R-025 |
| F-026 | low | CONFIRMED | 135 px needed / 132 available; 234 / 132 | R-026 |
| F-027 | medium | PARTLY RIGHT | the arming and its effect within the project: yes; the cross-project build through the real Open Project route: NOT REPRODUCED (armed path cleared, only a stale override row); through the session-restore path it does happen (R-104) | R-027, R-104 |
| F-028 | low | not retested | | R-009 |
| F-029 | medium | CONFIRMED | the question shows, the DEBUG "could not list runs built on the calibration" fires | R-029 |

Counts: CONFIRMED 20 (F-001, 002, 003, 004, 005, 006, 007, 008, 009, 012, 015, 016, 017, 019, 021, 022, 023, 024, 026, 029); PARTLY RIGHT 5 (F-011, 014, 018, 025, 027); NOT REPRODUCED as a whole 0 (two sub-claims: F-003's executed-command variant, F-027's cross-project build via Open Project); WRONG as a whole 0 (wrong parts inside F-011, F-014, F-018, F-025); not retested 4 (F-010, 013, 020, 028), code read agrees with each.

## 3. New findings (Agent 2)

| # | finding | grade | severity | file |
|---|---|---|---|---|
| N-1 | a failed build deletes the previous chart's exports/ sidecars and does not restore them (9 files -> 6, by name) | OBSERVED | medium | R-102 |
| N-2 | Generate from "New run" adopts the pre-edit seed block and reloads it over the user's screen (F-003's cause; violates per_target_settings.md §4a as written) | OBSERVED (stack) | high | R-105, R-003 |
| N-3 | `_apply_margin_thresholds` is dead code promising a Guided clamp; a test pins the opposite | INFERRED + OBSERVED | low (misled F-018) | R-101 |
| N-4 | Guided defaults red under the shipped seeds: p3 A4 portrait, i1 A4 landscape, i1 Letter landscape (plus Agent 1's p3 A4 landscape) | OBSERVED | high (design question) | R-018 |
| N-5 | the F-024 leak crosses into other projects (Generate greyed and STOP shown on opening A1-EngineVsPrinttarg) | OBSERVED | folded into F-024 | R-024 |
| N-6 | a run's attached patch set survives a project change through the session-restore path (foreign 304-set laid out into R2-Engine without targen); the real route clears it but leaves the override row | OBSERVED | medium / low | R-104 |
| N-7 | the last-page hint has no escape button; it holds `chart_finished` until clicked (watchdog releases the lock) | OBSERVED | low | R-106 |
| N-8 | Guided "Refinement profile" ticked with no file builds a plain chart silently | OBSERVED | low | R-107 |
| N-9 | "Show strip indicators" off frees no space | OBSERVED | low | R-103 |
| N-10 | the example-table clip mode is unreachable while the Text box holds text (the one-button box is read as No) | OBSERVED | medium | R-011 |
| N-11 | frames keep a vanished chart's numbers when .tif or .ti2 are removed by hand; the notice text itself is good | OBSERVED | low | R-108 |
| N-12 | the pre-targen "engine patch estimate failed" warning is not used to refuse the build | OBSERVED (log) | folded into F-019 | R-019 |
| N-13 | the CM A3+ TC9.18 built-in fails the CM seeds by 0.7 mm although the seeds were derived from the CM presets | OBSERVED | folded into F-017 | R-015-016-017 |

Ten distinct new items (N-1, 2, 3, 4, 6, 7, 8, 9, 10, 11); three folded into Agent 1's findings.

## 4. False positives and misreadings

- F-018's causal story (a clamp that works for i1 and CM and is overridden for p3 landscape) is false: nothing clamps on the Guided path, by design and by test. i1 A4 portrait and CM A4 pass by arithmetic (10 mm / 6 mm border plus the label band exceed the seeds). The finding's "expected" contradicts `tests/test_chart_creator_engine.py::test_guided_does_not_enforce_margin_thresholds`.
- F-014's "imported only by tests" and "no caller in ui/" are false (Preferences > Chart Layout, settings_dialog.py:5652).
- F-025's "the margin frame keeps a stale verdict" is false; both frames show placeholders, including in Agent 1's own screenshot A10-extremes/x10-after-failed-build.png. The driver read a hidden label's text.
- F-011's "the text was replaced" is false; nothing is replaced, which is a worse defect than the one filed.
- F-003's second reproduction (the executed command carrying -L) did not reproduce in two attempts; the mechanism I traced cannot produce it because `_collect_params` runs before the reload. Graded UNKNOWN; it may depend on a state Agent 1's session had (a route that changes the target before line 13183), not identified.
- F-027's cross-project build was inferred ("Generate was not pressed"); through the real Open Project route it does not happen. What Agent 1 photographed (the override row, the greyed toggle) is the stale presentation of R-104.
- F-029's premise that Demo-Full-RGB run1 carries `calibration_used` did not hold on the copy I read (all four runs empty); the defect stands regardless.
- Checkpoint 08's "files identical before and after the failure (set-aside works)" is false for exports/ (R-102).
- Not a false positive but a grade note: Agent 1's F-001 "Grade: OBSERVED + INFERRED" and F-003 "exact writer INFERRED unknown" were honest; F-021 and F-027 mixed observation with inference in the body text more than their grade lines admit.

## 5. Severity corrections

| F | Agent 1 | Agent 2 | why |
|---|---|---|---|
| F-003 | high | high, re-typed as spec conflict (§4a) | the store contradicts the chart on every per-target row of a run created by Generate from New run, and the spec already says the screen wins |
| F-011 | low | medium | a shipped mode that cannot be entered from the common state |
| F-014 | medium | low (feature request) | the module runs; what is missing is a Create Chart badge |
| F-018 | high | high, but a design decision, not a bug | code and test say Guided ignores the table on purpose |
| F-023 | low | fold into F-024 | one defect (`_chart_build_in_flight` reads the button) |
| F-025 | medium | medium, for a different reason | the blank preview is cosmetic; the exports/ loss (R-102) is the real content |
| F-027 | medium | low | within the project the armed set is the run's own (design); the wrong info line and the stale override row remain |
| F-017 | medium | medium, wider | CM built-ins too |

## 6. Coverage gaps found and closed

From Agent 1's own "not reached" list: expert targen/printtarg rows (closed, work; -A suppressed by -n per its tooltip), Save as Defaults (closed, works silently), Refinement profile row (closed, works with a file; silent without one, R-107), preset reveal (closed, works), run folder with hand-removed files (closed, R-108), keyboard focus order (closed, sane, help buttons unreachable), F-027 completion (closed in-project; cross-project not reproduced via the real route; R-104), F-003's mechanism (closed, R-003/R-105), scanner path from a hex chart (NOT closed: needs a measured .ti3; UNKNOWN by design of the feature).

Against the brief's coverage list (A1 to A13, B), rows without evidence in Agent 1's inventory that I also did not reach: A12's PDF content on a kept build beyond Agent 1's offline check; A13 end to end; B2.3 expert rows now covered; B12.3 now covered; B13 now covered. Still without on-screen evidence anywhere: the hex .cht path, German at other sizes than the two tried, the light/dark readability audit (screenshots only, both agents), a legacy v2 project (Demo-Legacy-v2 was never opened by either agent), a run folder made read-only, a missing Argyll binary at Generate time. These are named so nobody counts them as covered.

First-time-user probes (eight, all OBSERVED, checkpoint 03): empty name with no project (good dialog); another existing project's name (silent switch and overwrite, the deferred ruling reaches across projects); -f 0 (accepted, 22-patch chart); fixed count with Pages (greyed, fine); double click (one build); preset "+" (Save Preset dialog); Escape on the hint (ignored, N-7); delete the only run (good three-way dialog).

## 7. Independent regression baseline (works today; must survive any of the proposed changes)

Engine (all OBSERVED by me):
- Auto-count estimate equals the built chart on i1 A4 clip, p3 A3 landscape, CM high A4 landscape, SS hex A4, CR30 flat 200 x 200, i1 Letter (6/6), and on Agent 1's 55. Pinned by tests/test_layout_info_prediction.py, test_chart_layout_info_panel.py, test_layout_geometry.py, test_layout_permutation.py, test_engine_info_line*.py.
- Clip on/off with own margins changes capacity as the label says (609 / 667). Tests: test_layout_instrument_margins.py, test_clip_says_when_it_is_overridden.py.
- Instrument margins tick restores the table (38/9/19/26 for i1 A4) and re-tick picks up a changed table. Tests: test_layout_instrument_margins.py, test_layout_margin_thresholds.py.
- Max strip honoured in patch-first (18 per strip at 200 mm on A3). No test found that pins the area-first behaviour either way.
- Sheet-text tokens expand ({project}, {date}, {patchcount}). Tests: test_layout_raster.py (partly). No test pins the one-bad-token behaviour.
- Fixed counts build (400, 9500 = 22 pages); the hint appears when the last page is at least half full and not full. Tests: test_knut_beta118_partial_page_hint.py.
- Impossible layouts fail without a crash, chart files restored (exports/ not: R-102). Tests: test_chart_creator.py (stash), test_a_calibration_rebuild_keeps_what_is_not_the_chart.py (cal side).
- Save as Defaults writes `manual_engine_recipe` and a fresh panel seeds from it (Agent 1 A8.5). Test: test_layout_presets.py, test_layout_named_preset_roundtrip.py.
- Built-ins load and build (TC9.18 CM A3+, i1 162p) and the engine toggle follows the kind. Tests: test_colormunki_builtin_presets.py, test_i1pro_w8_builtin_presets.py, test_cr30_builtin_presets.py, test_knut_spyderprint_presets.py, test_backing_out_of_a_preset_changes_nothing.py.
- Guided headline equals the built count (9/9 here), Guided always uses the engine, -L/-P boxes move the headline (484 / 550 / 528). Tests: test_guided_always_uses_the_engine.py, test_guided_manual_transfer.py, test_a_guided_chart_is_judged_against_its_jig.py, test_guided_does_not_enforce_margin_thresholds (in test_chart_creator_engine.py).
- Preferences > Chart Layout shows the preflight verdict (code; not driven).

The rest:
- New-run seeding from the loaded run (§4a) and the seed block consumed on Generate (N-3 of the spec): observed (cache/new_run.json gone after the build). Tests: test_a_preset_is_not_a_target_with_nothing_stored.py; scripts/drive_new_run_seeding.py.
- Typed-name route switches projects and seeds the run; the "Give this project a name" dialog with no project; the four-way Rename dialog for a new name (Agent 1); umlauts accepted (Agent 1).
- Open Project (manifest route) clears the armed patch set (R06). No test pins this; test_a_loaded_patch_set_is_the_one_built.py pins the arming itself.
- Calibration target: fixed bar, cal/ location, replace question with Cancel default. Tests: test_calibration_run_type_bar.py, test_calibration_run_type_chart.py, test_calibration_keeps_only_measured.py.
- Gamut module: empty state without a profile, options with one (R03). Tests: test_gamut_module_tab.py.
- Delete run: three-way dialog for the only run. Tests: core.run_delete tests (grep tests/ for run_delete).
- Removed files: no crash, explicit notice.
- Focus order top-down in both modules.
- Session restore opens the remembered project on its current run (Agent 1 and R03).

Behaviour with NO test found (grep tests/): the post-Preferences panel sync (F-007); the Generate-enabled rule across module switches (F-024); exports/ survival on a failed build (R-102); the New-run adoption using the screen rather than the block (R-105); the hint dialog's escape route (R-106); Open Project clearing the armed set and the override row (R-104); the frames clearing on an empty preview (F-002/R-108).

For each of Agent 1's proposed changes, what to retest and what could break:
- F-001 A (feed `area_target_count` into the estimate and the hint): retest the Auto-count matrix (must be unchanged), fixed-count area-first, by-grid and patch-first, the Guided headline (it feeds from the same predictor), the CR30/CM presets' estimate (Basti's 4.1.5-beta.11 case in the docstring). Risk: the helper-marker overlay already does this and agrees with the render; copy that, do not invent a second count source.
- F-003/R-105 (adopt the screen, not the block): retest drive_new_run_seeding (N-1 to N-6), the P-1/P-2 preset-creates-target rule, Overwrite run N (must not change), the calibration N-6 rule (no block into cal/). Risk: the seed block also protects against a stale New-run copy; adopting the screen must still clear the block.
- F-007 A (sync after Preferences): retest own margins remembered while the box is ticked (`_saved_margins`), instrument change, preset load after Preferences. Risk: low.
- F-018 (any option): changes shipped Guided geometry or shipped seeds; the test named above must be inverted or kept; Guided parity with printtarg (Agent 1 A1.6, 4 combos) is the net.
- F-024 A + C (central enabled rule, explicit in-flight flag): retest gamut with and without a profile, S4 question flow, Stop during a build, the live preview's in-flight guard (it reads the same function). Risk: medium; thirteen `setEnabled` sites.
- R-102 (stash exports/ and cache/): retest a successful rebuild (exports must be the NEW chart's), a Stop, a failure, the calibration stash. Risk: low.
- F-011 (two-button box): new message text goes to §M-PROPOSED first.
- F-005/F-008 text-only options: translations (13 catalogues).

## 8. Spec-agreement table (per_target_settings.md, verification_printing_and_target.md, calibration_run_type.md, dev_margin_inspector.md, dev_builtin_presets.md, §M)

| finding | spec rule | agrees with Agent 1? |
|---|---|---|
| F-003 / R-105 | per_target §4a (Knut: modified settings are copied on Generate), §0 one writer, §2.1 write-then-load | spec DISAGREES with the code and supports Agent 1's expectation; code/spec conflict for the owner to approve before a fix (CLAUDE.md rule 2), the ruling text already exists |
| F-004 | per_target §1.2 (stamp is per target) | silent on the toggle; owner question stands |
| F-007 | per_target §4c D-1, §1.1 (Preferences is the seed) | agrees: refreshing locked boxes is a default setting a value nobody chose |
| F-016 | dev_builtin_presets.md ("Leaving a preset reverts its forced printtarg flags"; "The Manual info box says which mode it's in") | partly: the info-box promise is broken (F-015); silent on moving the toggle |
| F-017 / N-13 | dev_margin_inspector.md (CM seeds derived from the shipped CM presets so they read OK out of the box) | DISAGREES with the observed CM A3+ built-in (5.3 < 6) |
| F-018 / N-4 | dev_margin_inspector.md (#171 known gap, Guided barely checked, decided 2026-08-26); tests pin no clamp | DISAGREES with Agent 1's expectation; decision for the owner |
| F-024 / F-023 | #133 agreed wording (Guided/Manual "You can go ahead and create the chart"); verification_printing_and_target.md silent on the button outside the module | agrees with Agent 1 |
| F-029 | calibration_run_type.md §4.4 | agrees |
| F-002 / F-025 / R-108 | dev_margin_inspector.md: the frame shows the measured page | agrees |
| F-027 / R-104 | per_target §2 L2 (a project change replaces the target) | agrees in spirit; the real route obeys it except for the override row |
| F-011, F-019 dialogs | CLAUDE.md: new message text goes to §M-PROPOSED first | applies to every new window proposed by either agent |
| F-005, F-008, F-009, F-010, F-020, F-021 | no spec covers them | silent |

## 9. Questions for the owner (Agent 2's own list)

1. Guided and the seed table: four default Guided sheets are red under the shipped minimums (p3 A4 landscape and portrait, i1 A4 and Letter landscape) and the code plus a test say Guided ignores the table on purpose. Honour the table in Guided, revise those seed rows, or make the Guided verdict advisory?
2. The New-run block: per_target §4a says the settings the user modified on screen are copied into the new run on Generate. Confirm that reading, so the F-003 fix goes to `_adopt_new_run_settings` and not to a printtarg-only patch.
3. exports/ on a failed build: should the hand-off sidecars come back with the chart (stash them), or is "derived, rebuilt next time" acceptable?
4. The preflight verdict that Preferences > Chart Layout already shows: should Create Chart show the same lines for the chart being built (this is what F-014 and F-020 ask for, and it needs no new module)?
5. The ColorMunki A3+ TC9.18 built-in fails the ColorMunki seeds by 0.7 mm: seed or preset?
6. The last-page hint: may it get an escape route (Escape, close button), and should it be shown after `chart_finished` rather than inside the finish?
7. Refinement profile ticked with no file: refuse, ask, or untick with a log line?
8. Open Project leaves the "Edit patch recipe (override preset)" row visible from the previous project: clear it with the rest of the state?
9. The typed-name route switches projects and overwrites the other project's chart-only run with no window (twice observed; consistent with the deferred chart-overwrite ruling): does the ruling extend across projects, or is a project change worth one sentence?
10. F-024: approve a central rule for Generate's enabled state and an explicit in-flight flag (the same flag guards the live preview), or keep the module-local fix?

Agent 1's sixteen questions stand where they are not superseded: Q1 is answered by §4a (see question 2 above); Q3 becomes question 1 above; Q6 becomes question 4; Q12 becomes question 5 plus the CM built-ins.

## 10. Evidence index

Review/Screenshots/R01-f001-f003 (5): 01 F-001 after Generate (418/425), 02 patch-first -f 300, 03 F-003 before Generate (-L off, 1,000), 04 after (ticked, 0,950, clip band on the sheet), 05 variant B.
Review/Screenshots/R02-f007-f018 (10 + 2 prefs): Guided i1 A4, i1 A4R (red), CM A4, p3 A4R (red), p3 A4 (red), CM A4R, F-007 before and after Generate, the two Preferences dialogs.
Review/Screenshots/R03-f024-gamut (9): the ordered F-024 sequence, the leak on A1-EngineVsPrinttarg, gamut with a profile, New run frames.
Review/Screenshots/R04-engine (17): six matrix builds, labels off, F-005 both ways, F-006 frame, F-012 crops (valid and bad token), F-021, after the failed build.
Review/Screenshots/R05-files-presets-cal (10): after the failed build and the round trip, F-021 after re-open (the armed foreign estimate), four built-ins, the armed states, calibration selected.
Review/Screenshots/R06-crossproject-probes (4): empty-name dialog state, R2-Guided after Demo (override row), after Generate, typed-name result.
Review/Screenshots/R07-gaps (7): expert rows, refinement empty and with .icc, four removed-file states.
Review/Screenshots/R08-lows (2): SS margins group, 1280 x 800.
Logs: Review/Test Runs/logs/r01..r08*.log (every app record plus my lines), r01..r05, r07, r08 _results.json (r06 partial in its log, r06b partial in its log).
Drivers: Review/Test Runs/drivers/r_lib.py, r01_f001_f003.py, r02_f007_f018.py, r02b_guided_p3.py, r03_f024_gamut.py, r04_engine.py, r05_files_presets_cal.py, r06_crossproject_probes.py, r06b_probes.py, r07_gaps.py, r08_lows.py.
Projects written: /Users/Basti/ChromIQ-assessment/R2-High, R2-Guided, R2-Engine (new); Demo-Full-RGB (run3/run4 rebuilt, calibration question cancelled), A1-EngineVsPrinttarg (opened only), R2-High run2 overwritten by the typed-name probe.

## 11. Sandbox proof (11:00, no driver running; rule 2 of Agent 1's brief)

```
$ diff <(find ~/ChromIQ -maxdepth 1 | sort) "Evidence/baseline-before-assessment/chromiq_home_dirs.txt"
(no output)  exit=0
$ defaults read com.chromiq.ChromIQ custom_output_path

exit=0   (empty string, as in the baseline)
$ diff -r -x .DS_Store ~/Library/Preferences/ChromIQ/presets "Evidence/baseline-before-assessment/presets"
(no output)  exit=0
$ cmp ~/Library/Preferences/com.chromiq.ChromIQ.plist Evidence/baseline-before-assessment/com.chromiq.ChromIQ.plist
identical
$ find ~/ChromIQ -newermt "2026-09-07 09:50" -type f | wc -l
0
$ find ~/Library/Preferences/ChromIQ -newermt "2026-09-07 09:50" -type f | wc -l
0
```
Every run logged its stores at start: settings = Test Runs/sandbox/chromiq-assessment.ini, presets = Test Runs/sandbox/presets, projects = /Users/Basti/ChromIQ-assessment. Calibration mode was switched on in the sandbox ini for one session (R05 E) and off again in the same run.

## 12. Three corrections that matter most, and the one thing I would fix first

1. F-018 is a design decision, not a broken clamp: nothing clamps in Guided, by test; four default sheets are red, not one.
2. F-003 has a named cause and a spec ruling behind it: `_adopt_new_run_settings` copies the pre-edit block (per_target §4a says the screen); the fix Agent 1 recommends (post-build re-seeding from the sidecar) would leave the store wrong on every other row.
3. F-025 undersells the failure path: the frames are fine (placeholders) but exports/ is destroyed and not restored; and F-014 oversells it: the preflight is wired, in Preferences.

First fix, if I could pick one: R-105 (the New-run adoption), because it corrupts the per-target store on the most ordinary route there is (New run, change something, Generate) and the spec already says what right looks like.

# Implementation-readiness package: Create Chart / layout engine

Purpose: make a LATER change easy and safe. Nothing here has been implemented.
Repository state at writing: master `80975e65` (4.2.0), working tree clean.
All line numbers were re-verified on 2026-09-07 against that commit; re-grep
before use, they drift. Agent 2's R-files quote different numbers for some of
the same functions (13250, 13183, 16892, 17302, 15840): those are call sites
inside the functions named here, not a different commit.

Companion documents: the decision file on the Desktop (its filename carries
the owner's own em dash), `Reports/AGENT1-final-assessment.md`,
`Review/AGENT2-review-report.md`, `Evidence/code-map-layout-engine.md`.

## 0. Ground rules for whoever implements (from CLAUDE.md and the memories)

1. One feature branch; never edit source while a gate runs.
2. Every item below: write the pinning test FIRST (most have none today), then
   the change, then the drivers named in "regression net", then `--runslow`.
3. New user-facing text: §M-PROPOSED in `docs/design/unified_measurement_management.md`
   first; then `tr()`; no em dash; then `python scripts/i18n_extract.py --missing de`
   and the 12 catalogues (`tests/test_i18n.py` fails on missing keys).
4. A code/spec conflict (P1) needs the owner's written approval before the
   change (CLAUDE.md, "design specifications are binding").
5. Drive on screen with the sandbox: `source "Test Runs/sandbox/env.sh"`.
   The assessment drivers in `Test Runs/drivers` (Agent 1: cc_lib.py, d00..d09)
   and `Review/Test Runs/drivers` (Agent 2: r_lib.py, r01..r08) are re-runnable
   before/after checks. Their JSON results in the `logs` folders are the
   "before" numbers.

## 1. The regression net (run BEFORE the first change, keep the numbers)

| net | what it pins | how to run |
|---|---|---|
| Instrument matrix | estimate == build for 55 instrument x mode x paper builds, 8-bit 300 dpi, page sizes exact | `Test Runs/drivers/d02_instrument_matrix.py` (compare `logs/d02_matrix.json`) |
| Layout modes | 11 modes, estimate == build | `d03_layout_modes_and_margins.py` |
| Guided parity | Guided headline == build (5), Guided geometry == printtarg for i1 A4 (1, 2 pages) and p3 A4R | `d06_guided_parity_transfer.py`, `logs/d01_parity_printtarg_by_hand.json` |
| Per-target seeding | New-run seeding N-1..N-6 (11 checks), per-target switching (74 checks) | `scripts/drive_new_run_seeding.py`, `scripts/drive_per_target_settings.py` (repo, already exist) |
| Presets | save / reload / overwrite / delete / restart | `d05_presets_editor_panels.py`, `d05b_presets_editor_recheck.py` |
| Unit tests | 220 layout + creator tests, plus the per-target and preset files | `QT_QPA_PLATFORM=offscreen pytest tests/test_layout_*.py tests/test_chart_creator_engine.py tests/test_per_target_settings*.py tests/test_layout_options_panel.py (the info-line tests live here) -n auto` |
| Release gate | everything | `QT_QPA_PLATFORM=offscreen pytest --runslow -n auto` |

## 2. Item by item

Format: what / where / how / test to write first / regression net / decision.

### P1 New run + Generate adopts the pre-edit seed block (F-003, R-105) HIGH, spec conflict
- Where: `ui/tabs/tab_chart.py`
  - `_on_generate` 12905 (collect at `_collect_params` 19062 happens BEFORE alignment, so the chart is right)
  - `_align_current_run_to_target` 16747 -> `_adopt_new_run_settings` 14720 (copies `cache/new_run.json` into the new run's `meta.json`)
  - `ctl.set_profile_run` -> `ui/main_window.py` `_load_settings_of_visible_tab` -> `load_target_settings` -> `workflow/per_target_settings.apply` (reload over the screen), then `_on_target_changed` 16828 loads again
  - W1 write at `_on_generate_finished` 17040 (`save_target_settings` 14295) persists the reloaded values
- How (option A, recommended): in `_adopt_new_run_settings`, adopt the on-screen snapshot (`per_target_settings.snapshot(self)` or the equivalent registry read) instead of the stored block, still clearing the block (N-3). Alternatively suppress the visible-tab reload during the alignment of a Generate-created run. Do NOT re-seed printtarg widgets from the sidecar afterwards (Agent 1's option A hides one row's symptom).
- Also fix in passing: the sidecar's `printtarg_fields` and `create_chart_settings` must come from one snapshot (they disagreed on disk).
- Test first: a per-target test that selects New run, changes one registry value on screen, presses Generate, and asserts the new run's `meta.json` and both sidecar records hold the changed value. No such test exists (`grep -rn "new_run.json" tests/` finds seeding tests only).
- Regression net: `scripts/drive_new_run_seeding.py` (11), `scripts/drive_per_target_settings.py` (74), `tests/test_per_target_settings*.py`, `tests/test_a_preset_is_not_a_target_with_nothing_stored.py` (P-1/P-2), calibration N-6 (no block into cal/), and a NEW unit test (not only a driver) that "Overwrite run N" stores exactly what ran (Agent 2 variant B, unchanged today). Spec note: §4a's prose (Knut) and its rule N-3 disagree; option A rewords N-3, and §4a is still "awaiting confirmation".
- Decision: 2 (confirm §4a).

### P2 Guided defaults red under the shipped seeds (F-018, R-018, R-101, N-4) HIGH, design
- Where: `workflow/chart_creator.py` `_apply_margin_thresholds` 1394 (dead, no caller), `_engine_build_kwargs` 1246 (Guided path, `thresholds=None`); `ui/tabs/tab_chart.py` `_engine_geom` 12236 (Guided estimate, `thresholds=None`); `core/settings.py` seed rows (`_I1P3_PRIMARY` 28/9/40/9 and the landscape rows); `tests/test_chart_creator_engine.py:232 test_guided_does_not_enforce_margin_thresholds` (pins NO clamp).
- How: Decision 1 A = call the existing clamp on the Guided path for BOTH estimate and build (they must move together, `geom_from_build_kwargs(kw, thresholds=...)` is the chokepoint), invert the test deliberately, re-run Guided parity (expect fewer strips on i1/p3 landscape; i1 A4 portrait must remain 484). Decision 1 B = edit seeds in `core/settings.py` with a settings-schema migration (see memory `project_settings_default_migration`). Decision 1 C = text only in `ui/margin_inspector_panel.py`.
- Also: delete or wire `_apply_margin_thresholds`; a docstring promising behaviour the app lacks misled the assessment once already.
- Test first: ONLY after Decision 1 is taken. A test asserting "every Guided default passes its table" encodes option A and contradicts the shipped test at line 232; until the decision, the four red combos are documented in the assessment, not in the suite.
- Regression net: Guided parity set, `tests/test_guided_always_uses_the_engine.py`, `test_a_guided_chart_is_judged_against_its_jig.py`, the memory ruling on the i1Pro 19 mm bottom (must stay).
- Decision: 1 (and 3).

### P3 Fixed-count estimate and hint disagree with the build (F-001, R-001) HIGH
- Where: `ui/tabs/tab_chart.py` ~5578 (`geom_from_build_kwargs(r.build_kwargs())` for the estimate), `_partial_last_page_blank` 18401, `_estimate_patch_total` 17350, `_onscreen_patch_total` 17404 (feeds the padded .ti2 total, not the designed .ti1 count). The correct pattern already exists at 18133..18144 (`kwargs["area_target_count"] = ...` for the helper-marker overlay). The build side: `workflow/layout_engine/chart.py:235`.
- How: pass the designed count (targen -f value, attached set size, or .ti1 NUMBER_OF_SETS) as `area_target_count` in the estimate and in the hint; make the on-screen total read the designed count. Auto-count paths must pass nothing (they are exact today).
- Test first: extend `tests/test_layout_info_prediction.py` / `test_chart_layout_info_panel.py` with a fixed-count area-first case asserting estimate == build; a hint test asserting no hint for a full area-first page (Decision 11 decides whether the hint exists at all for area-first).
- Regression net: instrument matrix (must be identical), layout modes, Guided headline, the CR30/CM preset estimate case named in `_estimate_patch_total`'s docstring.
- Decision: 11 only.

### P4 Instrument Limits change not applied to the panel (F-007) HIGH
- Where: `ui/main_window.py` `_open_settings` 2344 (refreshes instrument default margin, patch count, command preview, inspector settings; does not call the panel); `ui/dialogs/layout_options_panel.py` `_sync_instr_margins` 2914.
- How: after the dialog closes, if the panel's "Use instrument margins" is ticked, call `_sync_instr_margins` (through a public method on the panel) and re-run the estimate. Respect `_saved_margins` (the user's own margins remembered while ticked).
- Test first: a tab test that changes the thresholds table in settings, invokes the post-Preferences refresh, and asserts the four boxes and the estimate follow.
- Regression net: `tests/test_layout_instrument_margins.py`, `test_layout_margin_thresholds.py`, driver `d03b_thresholds_and_stripcap.py`.
- Decision: 15 (approval only).

### P5 Gamut visit disables Generate everywhere (F-024, F-023, N-5) HIGH
- Where: `ui/tabs/tab_chart.py` `_refresh_gamut_state` 15822 (`setEnabled(has and not running)`), `_switch_mode` 6721 (nothing symmetrical), `_chart_build_in_flight` 18581 (reads the button), the eventFilter that shows Stop (~13405), 12 `_generate_btn.setEnabled` sites.
- How (A + C): one `_refresh_generate_enabled()` computing the state from (mode, target, profile presence, runner running, armed set) called from `_switch_mode`, `_on_target_changed`, run-type change and `_refresh_gamut_state`; an explicit `_build_in_flight` flag set in `_on_generate` and cleared in `_on_generate_finished` (both branches) and used by `_chart_build_in_flight` and the Stop button. Memory `project_build_in_flight_clobber` warns that `_chart_build_in_flight` is true whenever the button is disabled for any other reason; the flag removes that class of fault.
- Test first: the ordered sequence (Verification, no profile: Guided enabled -> gamut disabled -> Guided enabled again -> Profiling enabled), and "Stop hidden at rest in every module".
- Regression net: `tests/test_gamut_module_tab.py`, the S4 question flow, Stop during a real build (driver), the live preview's in-flight guard (auto-update must still not fire during a build), a Tools-menu Argyll job holding the shared runner (Generate must be disabled for that reason alone, with no Stop). REWRITE, do not keep: `tests/test_a_build_can_be_stopped.py` and `tests/test_live_preview_does_not_replace_a_preset.py` simulate a build by disabling the button, and three tests read `_chart_build_in_flight`; with an explicit flag those simulations go inert and pass while testing nothing.
- Decision: 16.

### P6 Failed build deletes exports/ and leaves the preview blank (R-102, F-025) MEDIUM
- Where: `core/file_manager.py` `Run.reset_chart_artefacts` 2208 (rmtree exports/ and cache/ before targen, stashes chart files only), `settle_chart_stash` 924 / 2187; `workflow/chart_creator.py` `_finish` 787; `ui/tabs/tab_chart.py` `_show_restored_chart_after_a_stop` 17018 (the model for the failure branch).
- How: include exports/ in the stash and restore it on `built=False`. Do NOT stash cache/: it holds `cache/new_run.json`, the §4a seed block (rule N-4), which a build must consume (N-3); restoring it would resurrect a consumed block. On the failure branch call the same "show restored chart" step. Success path: exports must be the NEW chart's (write after build, as now).
- Test first: file-name listing before/after a failing build (unit level via `reset_chart_artefacts(stash=True)` + `settle_chart_stash(built=False)`), plus a tab test that the preview shows the restored chart after a failure.
- Regression net: `tests/test_chart_creator.py` (stash), `tests/test_a_calibration_rebuild_keeps_what_is_not_the_chart.py`, a Stop, a successful rebuild.
- Decision: 7.

### P7 Estimate reads the hidden printtarg Pages spin (F-021) MEDIUM
- Where: the estimate's page source in `tab_chart.py` (grep `pages` near 5578 / `_estimate_patch_total`), the panel's Pages control in `layout_options_panel.py`, the hidden printtarg `-Pages` ParameterWidget.
- How: one setter that writes both, or read the panel's Pages whenever the engine is on.
- Test first: set panel Pages 1 with the hidden spin at 20, assert estimate uses 1.
- Regression net: layout modes driver, `tests/test_layout_options_panel.py`. Decision: none.

### P8 Impossible layout not refused before Generate (F-019, N-12) MEDIUM
- Where: the estimate failure log "engine patch estimate failed" (grep in tab_chart.py) fires before targen; `_on_generate` 12905; the empty-preview caption.
- How: when the estimate returns nothing, grey Generate and print the engine's own reason in the estimate frame; on engine failure show the reason in the caption/status line. Guard against a transient estimate failure locking the button (recompute on every panel change). Text -> §M-PROPOSED.
- Test first: estimate None => Generate disabled and reason text present; estimate valid again => enabled.
- Decision: none (text approval via §M).

### P9 Preflight lines and a patch-size floor in Create Chart (F-020, F-014) MEDIUM
- Where: `workflow/layout_engine/preflight.py` (exists, tested), caller today only `ui/dialogs/settings_dialog.py:5652`; `ui/margin_inspector_panel.py` (third line), `ui/chart_layout_info_panel.py`.
- How: run `preflight.check` on the recipe/geometry after each estimate and each build; show green/amber lines; Decision 6 B adds a refusal below per-instrument floors (values from the owner); a targen time warning above ~5,000 patches with Cancel.
- Test first: a panel test that an under-floor patch shows the amber line; a refusal test if B.
- Decision: 6.

### P10 Margins family (F-005, R-103, F-008, F-009, F-010) MEDIUM/LOW
- F-005/R-103 (clip off frees nothing): `workflow/layout_engine/instruments.py` (clip-side margin floored to clip width), `margins_fit.py`, label/help in `layout_options_panel.py`. Decision 3 decides geometry (B) or text (A/C).
- F-008 (strip cap ignored in area-first): `geometry.py` ruler-cap line keyed on `fill_beyond_ruler` (see memory `project_layout_instrmargins_and_clip_example`); Decision 4 A = honour an explicit non-zero `max_strip` even when `fill_beyond_ruler`; B = grey the controls in `layout_options_panel.py` with tooltip. Test first either way (no test pins area-first cap behaviour today).
- F-009 (box ticked with no table): `_sync_instr_margins` 2914 fallback path; Decision 5.
- F-010 (ruler with own margins): `_chart_own_margins` has no ruler key (Agent 2); look the ruler up from the settings table regardless of margin choice in `workflow/margin_inspector.py`. No decision.
- Regression net: instrument matrix, `test_layout_instrument_margins.py`, `test_layout_geometry.py`, the CM/SS clip defaults (memory: clip OFF for CM/SS).

### P11 Built-ins (F-015, F-016, F-017, N-13) MEDIUM/LOW
- F-015 info line: `tab_chart.py` `_engine_info_line_from_recipe` / the Manual configuration line builder (grep `_refresh_manual_command_preview` 5249); when `_preset_ti1_path`/a built-in is active, describe the route. Pin with a substring test per built-in kind (`tests/test_layout_options_panel.py (the info-line tests live here)`, `docs/dev_builtin_presets.md` promises this line).
- F-016 toggle moves: `_on_preset_selected` 8655 (`setChecked(has layout_recipe)`), `_revert_preset_combo` 8020; Decision 9.
- F-017/N-13 red built-ins: seeds in `core/settings.py` vs the prebuilt pages in `assets/`; Decision 8. Test: every shipped built-in's built chart passes its own instrument table (this test would have caught both).

### P12 Smaller items
| item | where | test first |
|---|---|---|
| F-006 verdict hidden by a note | `ui/margin_inspector_panel.py` `_update_status` 512 (`if text_warnings: ... return` runs before OK) | status visible with a note present |
| F-002/R-108 frames not cleared | preview clear paths in `tab_chart.py` (`_margin_tiffs`/`_margin_ti2`), `page_changed` | frames show placeholder when preview empty |
| F-012 all-or-nothing tokens | `workflow/layout_engine/raster.py:1295` (`except (KeyError, IndexError, ValueError)` around one `.format`) | unknown token stays literal alone; live preview flags it |
| F-011/N-10 one-button question | `layout_options_panel.py` `_load_example_clip_table` | two buttons; OK replaces, Cancel reverts the combo |
| F-029 calibration runs list | `tab_chart.py:16446` `run.meta` -> use `run.meta_path` (`core/file_manager.py:2120`) | helper returns the run names for a run with `calibration_used`; log at WARNING on failure |
| F-027/R-104 armed set survives | `_preset_ti1_path` and the override row; clear in `_on_target_changed` unless the incoming sidecar arms one | Open Project and session restore both clear it |
| R-106 hint escape | the hint QMessageBox in `_on_generate_finished` path (`_partial_last_page_blank` caller) | Escape closes; `chart_finished` emitted before the hint |
| R-107 refinement ticked, no file | `_on_guided_precond_toggled` 7160 / `_collect_params` | Generate refused or asked (Decision 12) |
| F-004 stamp coupling | `_on_manual_engine_toggled` 5027 last line | per Decision 10 |
| F-013 image + caption | `raster.py` clip image branch | per Decision 14a |
| F-022 six help texts | `data/parameters.yaml`, Guided box labels in `_make_guided_panel` 3629 | `tests/test_i18n.py`, em-dash test; §M first |
| R-103 strip indicators off frees nothing | `raster.apply_furniture_reserves` / `GEOM_BUILD_KEYS` in `instruments.py` (the band is reserved regardless) | capacity test in `test_layout_geometry.py` per Decision 14g |
| Pages cap 20 | the Pages spin maximum in `layout_options_panel.py` | per Decision 14f |
| F-026/F-028 clipped labels | `ui/margin_inspector_panel.py` row labels, `ui/chart_layout_info_panel.py` header | width check at 1280x800 in en and de (driver `d09_german_pass.py`) |

## 3. What NOT to touch (rulings)
- Chart overwrite within a run (deferred 2026-09-02); helper-marker geometry; i1Pro 19 mm bottom on A4 portrait / A3 landscape; Guided always on the engine; page-label column reclaimed; every language's register.

## 4. Suggested branch plan
1. `assessment/regression-net`: no app code; add the missing pinning tests as `xfail(strict=True)` where they document a current fault, so the suite records the baseline before any fix. This is a repo change that enters the gate: ASK FIRST. And only for pure correctness items (P3, P4, P6, P7, F-012, F-029); never for option-encoding ones (P2, Decisions 3, 4, 9, 10), where an xfail would pre-empt the owner.
2. `fix/create-chart-step1a`: the no-decision, no-new-text items (P4, P7, F-006, F-002, F-012, F-010, F-015, F-029, F-027, F-026/28, preview reload), each turning its xfail green. `fix/create-chart-step1b`: items with new or changed user-facing text (P8, F-011, F-022) after §M-PROPOSED approval; the Guided box names in F-022 may be Knut's wording.
3. `fix/estimate-designed-count` (P3) and `fix/generate-enabled-rule` (P5).
4. `fix/new-run-adopts-the-screen` (P1) after Decision 2.
5. One branch per design decision (1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14).
6. Translations, `--runslow`, beta.

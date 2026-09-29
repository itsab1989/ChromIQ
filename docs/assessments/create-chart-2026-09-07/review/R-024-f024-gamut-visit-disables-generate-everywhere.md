# R-024 F-024 one visit to FROM PROFILE GAMUT without a profile disables Generate everywhere
Verdict: CONFIRMED and extended
Area: gamut / manual / guided / run bar
Grade: OBSERVED
Attended: unattended
Severity: high (agree)
Reproduced in order (Demo-Full-RGB run3, no .icc; Review/Test Runs/logs/r03_results.json, shots R03/00 to 06): Profiling Guided: Generate on. Verification Guided: on. FROM PROFILE GAMUT: off, Stop visible, `_chart_build_in_flight()` True with `_runner.is_running` False. Guided: still off. Manual: off. Run type Profiling: off. Run 2: off. Run 3 again: off. Click the greyed button: off. Open A1-EngineVsPrinttarg (an ordinary profiling project with a chart): Generate off and STOP shown on arrival (shot 06).
What gave it back: opening Demo-Full-RGB run2 (has a profile), Verification, FROM PROFILE GAMUT: `_refresh_gamut_state` (tab_chart.py:15840) enables it; Guided and Profiling then stay enabled.
Code: agree with Agent 1 (15840 disables; `_switch_mode` 6721 never recomputes; `_chart_build_in_flight` 18581 reads the button; the Stop button follows that).
Spec: memory of the agreed #133 wording (project_verification_no_profile_messages.md) and the Guided/Manual box text say "You can go ahead and create the chart"; the module empty state says "GUIDED and MANUAL can still build you a chart in the meantime". Both are contradicted on screen after the visit. verification_printing_and_target.md is silent on the button state outside the module.
Solution check: Agent 1's A (recompute on module and target change) plus C (track the build explicitly). C matters beyond this bug: `_chart_build_in_flight` also gates the live preview, so a wrongly disabled button also silences auto-update. Regression: tests/test_gamut_*.py and the S4 question flow; a central "enabled" rule must still keep Generate off while the runner runs and while the gamut module has no profile.

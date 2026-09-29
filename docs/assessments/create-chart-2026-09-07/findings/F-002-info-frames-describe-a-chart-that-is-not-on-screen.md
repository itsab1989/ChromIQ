# F-002 "Measured from Preview" and "Chart layout information" keep describing the previous chart while the preview says NO PREVIEW
Area: preview
Grade: OBSERVED
Attended: unattended
Type: bug
Severity: medium
Expected: When the preview shows "NO PREVIEW" / "No chart for this profile run yet", the two frames under it show their placeholder (or are hidden). The frame is titled "Measured from Preview", so it must describe what the preview shows.
Actual: Two cases, both app-built or app-navigated:
1. Profile run switched to "New run" (run3 of A1-EngineVsPrinttarg, folder empty). Preview: "NO PREVIEW", caption "No chart for this profile run yet." The frames still read Left 26.0 / Right 23.9 / Top 41.0 / Bottom 24.0, "Margins: OK", and on screen 420 / 20 fill-up / 21 per strip / 20 strips / 1 page, which are run2's printtarg chart.
2. Run type switched to Verification with no verification chart (Demo-Full-RGB run3, FROM PROFILE GAMUT). Preview: "NO PREVIEW", caption "No verification chart for this run yet." The frames still show the profiling chart's margins (6.0/8.0/33.0/25.0) and on screen 400.
3. The ESTIMATE column also keeps the previous target's prediction: after a From Profile Gamut build (estimate 75 / 11 fill-up / 15 per strip / 5 strips) the Run type was set to Calibration; the calibration chart (64 / 4 / 16 / 4) appeared in the on-screen column while the estimate column still read 75 / 11 / 15 / 5 (Screenshots/B4-calibration/c01-calibration-selected.png, D08 09:27). Under Verification on run3 (no verification chart) the frames showed run2's verification chart (75) with the estimate 484 (Screenshots/B3-gamut/g04-guided-verification-run3.png).
Why it matters: A green "Margins: OK" and a patch count sit under an empty preview. A user who has just created a new run, or switched to Verification, reads numbers that belong to another chart. The frame's own title promises the opposite.
Steps to reproduce (click by click): Open a project with a chart. In the Profile run pulldown choose "New run". Look under the preview. (Or: set Run type to Verification on a run without a verification chart.)
Evidence: Screenshots/A1-engine-vs-printtarg/05-engine-on-again.png (New run, NO PREVIEW, frames filled), Screenshots/00-launch/10-gamut-module.png (Verification, NO PREVIEW, frames filled), Test Runs/logs/d01_engine_vs_printtarg.log.
Spec or source cited: `docs/dev_margin_inspector.md` ("the 'Measured from Preview' frame under the preview shows ... " the measured page) and `tab_chart._update_margin_inspector` (measures `_margin_tiffs`, which is not cleared when the preview is cleared on a run change). Code ref: ui/tabs/tab_chart.py:17577 onwards; the placeholder path exists (`panel.show_placeholder()`) but is only reached when `_margin_tiffs` is empty.
Possible solutions (no code): A. Clear `_margin_tiffs` / `_margin_ti2` and call both panels' placeholder whenever the preview is cleared (run change, run-type change, project close). B. Hide both frames while the preview is empty. C. Keep the numbers but retitle the frame "Last chart" with the run it came from (weaker).
Regression risk if changed: Low. The measure is recomputed from the shown page on every `page_changed` and after every build; clearing on an empty preview cannot lose data.
Needs owner decision: no

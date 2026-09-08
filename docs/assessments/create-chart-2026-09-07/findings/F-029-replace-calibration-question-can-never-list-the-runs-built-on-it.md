# F-029 The "Replace the calibration" question can never list the runs built on the calibration: its helper raises AttributeError on every run and the error is swallowed at debug level
Area: calibration run type
Grade: OBSERVED (traceback in the app log during the on-screen step) + INFERRED (code)
Attended: unattended
Type: bug (latent; the feature it powers is silently absent)
Severity: medium
Expected: calibration_run_type.md section 4.4 protects cal/ like a run: before a measured calibration is replaced the window names what depends on it, including the runs whose profiles were built with it (`_runs_built_on_calibration` is called from the message builder at tab_chart.py:16363).
Actual: Pressing Generate on the Calibration target of Demo-Full-RGB (whose run1 meta.json carries `calibration_used`) showed "This project already has a finished calibration, and generating a new chart starts that work over" with Replace the calibration / Cancel, and the app log recorded, at DEBUG: "could not list runs built on the calibration" with `Traceback ... File ".../ui/tabs/tab_chart.py", line 16446, in _runs_built_on_calibration ... AttributeError: 'Run' object has no attribute 'meta'`. `Run` exposes `meta_path` (core/file_manager.py:2120), not `meta`, so the loop fails on the first run every time and the list is always empty. Two occurrences in D08b (both Generate presses on the Calibration target).
Why it matters: The one sentence that would tell a user "Run 1 and Run 2 were built with this calibration" never appears, and nothing signals it (a DEBUG line with the log hidden). The owner's D1 ruling ("regenerating a calibration chart deletes the calibration, silently") is only half fixed: the window exists, its most useful content does not.
Steps to reproduce (click by click): Preferences: enable the calibration mode. Open a project with a measured calibration and a run whose meta.json has calibration_used. Run type: Calibration. Generate Chart. Read the window: no run names. (Log at DEBUG shows the traceback.)
Evidence: Test Runs/logs/d08b_rest.log 09:37:46 (traceback), Test Runs/logs/d08b_results.json (cal-fresh-generate dialogs), Screenshots/B4-calibration/c10-fresh-session.png.
Spec or source cited: docs/design/calibration_run_type.md section 4.4 and D1; ui/tabs/tab_chart.py:16436-16450; core/file_manager.py Run.meta_path (2120).
Possible solutions (no code): read the run's meta.json through the Run's own loader (or `meta_path`) and let a unit test cover the helper with a run that has `calibration_used`; log the failure at WARNING at least.
Regression risk if changed: Low.
Needs owner decision: no

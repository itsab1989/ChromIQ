# F-025 After a failed build the previous chart's files are put back, but the preview stays at NO PREVIEW and the margin frame keeps a stale verdict
Area: preview / manual
Grade: OBSERVED
Attended: unattended
Type: bug (UX; no data loss)
Severity: medium
Expected: `ChartCreator._finish` documents that a build which did not finish puts the set-aside chart back "on exactly the paths that do not produce a new one". The screen should then show that chart again, as it does after a user Stop (`_show_restored_chart_after_a_stop`).
Actual: A5-Furniture run1 with a good 304-patch chart on screen. A build made to fail (60 mm patch on a 20 x 20 sheet): engine error in the log, no dialog (F-019). Afterwards the run folder holds exactly the files it held before (channels.json, .ti1, .ti2, .tif, meta.json), yet the preview shows 0 pages ("NO PREVIEW"), the Chart layout information frame is empty and the Measured from Preview frame still says "Margins: OK" from the previous chart. Switching to run2 and back to run1 shows the chart again (1 page, 304). The same blank state was seen after the D07b failures on A10-Extremes.
Why it matters: With the log hidden (the owner's setting) the user sees the chart vanish and no message; the data is safe but nothing on screen says so, and a green "Margins: OK" sits under an empty preview.
Steps to reproduce (click by click): Build any chart. Set Paper to Custom 20 x 20 and patch size 60 x 60. Generate. Look at the preview and the frames. Switch run and back.
Evidence: Test Runs/logs/d08b_results.json (failed-build-restore: files_before == files_after, preview_pages_after 0, frames_after [None, 'Margins: OK'], after_run_roundtrip preview 1 / 304), Screenshots/A10-extremes/x10-after-failed-build.png, x03-patch-bigger-than-page.png.
Spec or source cited: workflow/chart_creator.py:_finish docstring; ui/tabs/tab_chart.py:_on_generate_finished calls `_show_restored_chart_after_a_stop()` only on the user-cancel branch ("...AND THE PREVIEW HAS TO CATCH UP WITH THE FILES", written for Stop), not on the failure branch.
Possible solutions (no code): A. Run the same "show the restored chart" step on the failure branch. B. Print the engine's reason where the preview was (the empty preview already carries a caption line).
Regression risk if changed: Low.
Needs owner decision: no

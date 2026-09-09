# R-102 NEW a failed build deletes the previous chart's exports/ sidecars and does not put them back
Area: layout engine / run folder
Grade: OBSERVED (R04 and R05, file names before and after)
Attended: unattended
Type: bug (data safety)
Severity: medium
Expected: `ChartCreator._finish` / `settle_chart_stash` promise that a build which did not finish puts "every file back exactly where it was".
Actual: R2-Engine run1 with a good 525-patch chart: 9 files incl. exports/R2-Engine-colours.txt, -i1profiler.txt, -i1profiler.pxf. A build that fails in the engine (20 x 20 sheet, 60 mm patch): the chart files come back, the three exports/ files are gone (6 files). `Run.reset_chart_artefacts(stash=True)` rmtree's exports/ and cache/ before targen ("derived, go with the chart") and stashes only the chart files; the failure path restores the stash and nothing recreates exports/.
Why it matters: the exports are the hand-off files (i1Profiler .txt/.pxf, colours.txt) a user may already have copied elsewhere or may look for next; they vanish after a failed attempt that otherwise "changed nothing". Re-derivable by a successful rebuild, so no permanent loss.
Steps: build any engine chart; set Paper Custom 20 x 20 and Patch size 60 x 60; Generate; list exports/.
Evidence: Review/Test Runs/logs/r05_results.json A_failed_build (files_before / files_after / missing_after), r04_results.json f019 (9 -> 6), core/file_manager.py reset_chart_artefacts and settle_chart_stash.
Spec: dev_folder_layout.md lists exports/ as a run's hand-off sidecars; unified_measurement_management.md §4 "nothing is deleted" is about measurements; silent on exports. Correction to Agent 1's checkpoint 08 ("files identical before and after the failure").
Possible solutions (no code): A. stash exports/ and cache/ with the chart and restore them on failure. B. delete exports/ only when the new chart has been written. Regression risk: low; the stash already handles folders (reads/).
Needs owner decision: no.

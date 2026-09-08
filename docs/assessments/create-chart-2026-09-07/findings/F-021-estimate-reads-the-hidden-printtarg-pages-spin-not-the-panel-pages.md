# F-021 The estimate column takes its page count from the hidden printtarg "Pages" spin, which can drift from the ChromIQ layout panel's "Pages"; the estimate then assumed 20 pages while the build made 1
Area: layout engine (Chart layout information)
Grade: OBSERVED (symptom, three builds in a row); INFERRED (mechanism from code)
Attended: unattended
Type: bug
Severity: medium
Expected: With the engine on there is one Pages value (the layout panel's), and the estimate, the command line and the build all use it.
Actual: Project A10-Extremes, after a 36-page chart had been built in the run. Panel Pages set to 1 by the driver. Three consecutive builds: 100 x 100 mm at 72 dpi, estimate 1260 (9 x 7 x 20 pages) versus built 63 (1 page); at 1200 dpi, estimate 1600 (10 x 8 x 20 pages) versus built 80 (1 page); the 200 x 500 grid, estimate 991,800 (20 pages) versus built 49,590 (1 page). The next step set the panel's Pages to 20 explicitly (ColorMunki, 20 pages) and estimate and build agreed again (960 both), which is what a one-sided sync predicts.
Why it matters: The estimate is out by a factor of the stale page count, on the very panel the owner wants to trust; the mismatch is flagged only by bold digits, with no reason.
Steps to reproduce (click by click): Build a chart with more pages than the Pages box maximum allows (fixed -f giving 36 pages did it here). Then set Auto count on and the panel's Pages to 1 (if it already reads 1, nothing is sent to the twin spin). Read the estimate's Pages row (20) and Generate (1 page).
Evidence: Test Runs/logs/d07b_results.json (x-dpi-72, x-dpi-1200, x-grid-200x500: estimate pages 20, actual pages 1; x-pages-20-CM: 20 and 20), Screenshots/A10-extremes/x05-grid-200x500.png.
Spec or source cited: ui/tabs/tab_chart.py:5587 `pages_req = (self._manual_pages_spin.value() ...)` in the engine estimate, while `_collect_manual` (19255) builds with `self._manual_layout_panel.get_pages()`. The two spins are cross-synced on valueChanged (5218, 7131, 7154) but several restore paths write only the printtarg spin (8885, 8988 `setValue(int(data.get("pages", 1)))`, 6845), so a restored value (36 clamped to the spin's maximum 20) never reaches the panel, and setting the panel to a value it already shows emits nothing.
Possible solutions (no code): A. Make the estimate read the same control the build reads (the layout panel's Pages when the engine is on). B. Route every restore through one setter that writes both spins. C. Show the page count the estimate assumed in the info line so a mismatch is at least visible.
Regression risk if changed: Low for A.
Needs owner decision: no

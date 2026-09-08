# F-020 There is no floor on patch size: a 200 x 500 grid on A4 builds 49,590 one-millimetre patches without a warning, after blocking the window for minutes
Area: layout engine
Grade: OBSERVED
Attended: unattended (the build ran to completion; my driver's timeout expired while it ran)
Type: bug / missing guard
Severity: medium
Expected: The layout refuses, or at least warns, when the derived patch is smaller than any instrument can read (the engine's own preflight module defines a "patch-size reliability floor"), and a build that will take minutes says so before it starts.
Actual: Manual, engine on, i1Pro A4, area-first "By columns / rows", Strips 200, Rows 500, Auto patch count. The estimate showed 285 x 174 per page at 1.0 x 1.0 mm (991,800 for the 20 pages it assumed, see F-021). Generate ran targen for that count (over 6 minutes at 100 % of one core, window unresponsive to the driver) and then the engine drew 49,590 patches of 1.02 x 1.02 mm on one A4 page. No warning at any point, no refusal, the only note was the row-indicator margin widening. The values 200 and 500 are the spin boxes' own maxima, so the panel offers this range.
Why it matters: A slip in the grid boxes costs minutes of a frozen window and produces a sheet no instrument can read; the app knows the patch size (it prints it in the estimate) and has a module written to judge it (F-014).
Steps to reproduce (click by click): MANUAL, engine on, i1Pro A4, Create layout "Prioritise chart area", Calculation method "By columns / rows", Strips 200, Rows 500, Auto count on. Read the estimate (1.0 x 1.0 mm). Generate and wait.
Evidence: Test Runs/logs/d07b_results.json (x-grid-200x500: secs 410.5, estimate 991800 285x174 [1.0,1.0], actual 49590 285x174 1 page [1.02,1.02]), d07b_extremes_rest.log (targen run time), Screenshots/A10-extremes/x05-grid-200x500.png.
Spec or source cited: workflow/layout_engine/preflight.py docstring ("patch-size reliability floor"); layout_options_panel spin ranges area_cols 0..200, area_rows 0..500; instruments.py per-instrument patch sizes (i1Pro 8 x 10 mm base).
Possible solutions (no code): A. Refuse or warn when the derived patch is below a per-instrument floor (the engine knows the aperture: i1Pro 4.5 mm, CR30 4 mm window, etc.). B. Before a targen run above some count (say 5,000), show the expected time and offer to cancel. C. Cap the grid boxes by what the sheet can hold at the instrument's floor.
Regression risk if changed: Low for a warning; a hard refusal needs the floor values agreed with the owner.
Needs owner decision: yes (floor values per instrument, warn versus refuse).

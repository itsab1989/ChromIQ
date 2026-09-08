# R-001 F-001 estimate and hint disagree with a fixed-count area-first build
Verdict: CONFIRMED
Area: layout engine
Grade: OBSERVED
Attended: unattended
Type: bug
Severity: high (agree)
Reproduced: project R2-High, Manual, engine on, i1Pro, A4 portrait, clip on, area-first by width, instrument margins on, targen -f 400 (Auto off). Estimate before Generate 525 (capacity). Hint at Generate: "there's space for about 107 more patches on it (the page holds about 525 in total)". Built 418 (22 x 19, 9.23 x 9.82 mm), .ti1 400 sets, .ti2 418 sets. Estimate column after the build: 425 / 7 fill-up / 25 per strip / 17 strips / 8.33 x 8.56 mm. Screenshot Review/Screenshots/R01-f001-f003/01-f001-after-generate.png.
Second case: patch-first, -f 300: total 315 in both columns, fill-up 0 estimated vs 15 built (Agent 1 saw 11 vs 15; the number depends on the previous chart's total that the estimate feeds, which is itself the point).
Code check (agree with Agent 1's root cause): ui/tabs/tab_chart.py:5578 builds `geom_from_build_kwargs(r.build_kwargs())` without `area_target_count`; `_partial_last_page_blank` (18401) likewise; `chart.build_chart` (workflow/layout_engine/chart.py:235) passes `area_target_count=len(target.patches)`. Note the SAME file already does it right for the helper-marker overlay (tab_chart.py:18133 to 18144, with a comment explaining exactly this trap: "measured on a 480-patch ColorMunki sheet, 19 dashes at a 15.8 mm pitch here against 285 at 1.0 mm there"). So the fix pattern exists in the codebase; Agent 1's option A is that pattern.
Severity: high is right; the hint actively sends the user to the patch-set editor to fill a page that is full.
Regression net: tests/test_engine_info_line*.py, tests/test_layout_*.py, and the D02 matrix (Auto count exact 55/55). A change must keep Auto-count estimates identical (they do not pass a count) and only affect the fixed-count and on-screen-total branches.
Spec: none applies.

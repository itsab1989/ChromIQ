# R-101 NEW `ChartCreator._apply_margin_thresholds` is dead code whose docstring promises a Guided clamp
Area: layout engine / guided
Grade: INFERRED (code) + OBSERVED (nine Guided builds, no clamp note, recipes 6/6/6/6)
Type: inconsistency / regression risk
Severity: low as code hygiene; it misled Agent 1 into F-018's wrong cause and its solution A
Actual: workflow/chart_creator.py:1394 defines `_apply_margin_thresholds` ("Raise the layout's margins so the patch area meets the user's margin thresholds ... Applied at this one point so the capacity estimate and the real render agree"); grep over ui/, workflow/, core/ and main.py finds no caller. tests/test_chart_creator_engine.py::test_guided_does_not_enforce_margin_thresholds pins that Guided must NOT clamp; tests/test_layout_margin_thresholds.py tests `margins_fit.clamp_margins_to_thresholds` directly. So a reader of chart_creator believes Guided is clamped, a reader of the tests knows it is not, and the app does not.
Why it matters: the next person to "fix" F-018 will call this method and break the test, or delete the test and change every Guided sheet; either needs the owner (see R-018).
Possible solutions (no code): delete the method or make it the deliberate hook, after the owner's ruling on R-018.
Needs owner decision: yes, the same as R-018.

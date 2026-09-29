# R-004 F-004 the engine toggle flips "Stamp settings used on the chart"
Verdict: CONFIRMED
Grade: OBSERVED (R08): Stamp ticked, engine on. Engine off: Stamp still ticked. Engine on again: Stamp unticked, no message. Code agrees (tab_chart.py `_on_manual_engine_toggled` ends with `setChecked(not on)`).
Spec: per_target_settings.md §1.2 lists the stamp box as a per-target value and says nothing about the toggle owning it. Silent. Owner question stands. Severity low (agree).

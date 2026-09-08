# F-010 The strip-length limit typed in Instrument Limits is ignored when the chart uses its own margins
Area: layout engine / Preferences (Instrument Limits)
Grade: OBSERVED
Attended: unattended
Type: bug / inconsistency
Severity: low
Expected: The ruler limit is a property of the instrument, not of the margin choice; a chart that declines the instrument margins should still be checked against the configured ruler.
Actual: With Instrument Limits i1Pro / A4 Portrait ruler set to 200 mm (saved, read back), a build with "Use instrument margins" ON was noted "Strip length 238 mm exceeds the 200 mm instrument ruler" (correct). The next build with "Use instrument margins" OFF and own top/bottom margins of 6 mm (30 patches per strip, 283 mm) was noted "Strip length 283 mm exceeds the 240 mm instrument ruler": the engine's built-in 240 replaced the configured 200.
Why it matters: A user with a short ruler who sets the limit, then adjusts a margin by hand, loses the limit silently and gets the wrong number in the warning.
Steps to reproduce (click by click): Preferences > Instrument Limits > i1Pro / A4 Portrait, Maximum strip length 200, OK. MANUAL, engine on, i1Pro A4, untick "Use instrument margins", set Top and Bottom to 6, Generate. Read the note under the preview.
Evidence: Test Runs/logs/d03b_results.json (entry "ruler200_longstrip_notes"), Screenshots/A4-margins/t03-ruler200-long-strip.png.
Spec or source cited: ui/tabs/tab_chart.py:_update_margin_inspector around line 17650: `thresholds = self._chart_own_margins()` returns the chart's own four margins (no "ruler" key) when instrument margins are off, so `(thresholds or {}).get("ruler")` is empty and `_geom_ruler` (240) wins.
Possible solutions (no code): A. Look the ruler up from the Preferences table regardless of which margins were used. B. Copy the configured ruler into the chart's own-margin record when the chart is built.
Regression risk if changed: Low.
Needs owner decision: no

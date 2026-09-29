# R-106 NEW the "doesn't quite fill the last page" window cannot be dismissed with Escape, and it holds up the build's finish
Area: manual / layout engine
Grade: OBSERVED (R06b: Escape sent to the box with buttons OK and "Edit patch set..."; nothing happened; the driver waited on it until killed) + app log (R06: "Chart-build lock released by watchdog, no chart_finished arrived after the last tool ended" while the box was open)
Severity: low
Why it matters: a QMessageBox without a reject-role button ignores Escape and the window's close button; a keyboard user is stuck until they click OK. The box is exec'd inside the build's finish sequence, so `chart_finished` (which Print and Measure listen to) waits for the click; a watchdog releases the build lock after about 1.5 s, which is why nothing worse happens.
Possible solutions (no code): give the box an escape button (OK with RejectRole, or a Close), or show it after `chart_finished`.

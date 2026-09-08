# F-004 Clicking the engine toggle silently flips "Stamp settings used on the chart"
Area: manual
Grade: OBSERVED
Attended: unattended
Type: UX / unclear requirement
Severity: low
Expected: A checkbox in the Output group changes only when the user clicks it, or the change is announced.
Actual: In A1-EngineVsPrinttarg the Stamp box was ticked in run1 and run2. The driver unticked the engine toggle (run2) and re-ticked it (run3): the Stamp box came out unticked with no message. Code: `tab_chart._on_manual_engine_toggled` ends with `self._manual_stamp_cmd_check.setChecked(not on)` on a "real click" ("THE FIRST-TIME STAMP DEFAULT"), so engine ON sets stamp OFF and engine OFF sets stamp ON.
Why it matters: Stamp is a per-target setting (per_target_settings.md section 1.2, "stamp checkbox"). A person who wants the layout summary printed and switches engines loses it silently, and the sheet arrives without its record strip. The inverse also happens.
Steps to reproduce (click by click): MANUAL, tick "Stamp settings used on the chart", click "Use the ChromIQ layout engine instead of printtarg" once. Look at the Stamp box.
Evidence: Screenshots/A1-engine-vs-printtarg/04-printtarg-built-window.png (Stamp ticked, engine off), 05-engine-on-again.png (engine on again, Stamp unticked). Code ref ui/tabs/tab_chart.py:5090-5100.
Spec or source cited: per_target_settings.md section 1.2 lists the stamp checkbox as a per-target value; nothing in the specs says the engine toggle owns it.
Possible solutions (no code): A. Remove the coupling. B. Apply the "first-time default" only when the box has never been answered for this target (mirror `_layout_answered`). C. Keep it but say so in the toggle's help text.
Regression risk if changed: Low.
Needs owner decision: yes. Is the stamp meant to follow the engine toggle at all, and if so, in which direction?

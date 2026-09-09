# F-016 Picking a prebuilt-files built-in ("by Pharmacist") unticks "Use the ChromIQ layout engine" without saying so; picking a full-layout built-in ticks it back
Area: presets / layout engine toggle
Grade: OBSERVED
Attended: unattended
Type: UX / unclear requirement
Severity: low
Expected: The brief asks "built-in presets (do they switch the engine off, and do they say so?)". Either the toggle is left alone and the preset carries its own route, or the switch is announced (a line in the info box, a log line, or a note next to the toggle).
Actual: Engine on; pick "i1Pro A4-1160p-2pages TC9.18 extended greys by Pharmacist": the toggle unticks, the printtarg panel appears greyed under "Edit page layout (override preset)", the prebuilt chart loads. No dialog, no log line, no on-screen note; the only trace is the box itself and the panel swap. Pick "i1Pro A4-162p Full layout setup" next: the toggle ticks itself back on. Pick "none": the toggle stays on and the panel keeps the last preset's instrument (SpectroScan) and margins (8/4/4/4).
Why it matters: The engine toggle is a per-target setting (per_target_settings.md section 1.2) and the user's own choice; presets moving it silently is how the "Guided routed through printtarg" fault (#170) stayed invisible. The stored `engine_on` for the run now follows whichever preset was last clicked.
Steps to reproduce (click by click): MANUAL with the engine on; Presets: pick a "by Pharmacist" built-in; look at the engine box. Then pick a "Full layout setup" built-in; look again.
Evidence: Test Runs/logs/d05b_results.json (a8-builtin-tc918eg-a4-printtarg-kind engine_before True, engine_after False, dialogs []; a8-builtin-knut-i1-w75 engine False to True), Screenshots/A8-presets/q14-builtin-tc918eg-a4-printtarg-kind.png (box unticked, panel greyed).
Spec or source cited: docs/dev_builtin_presets.md ("Leaving a preset reverts its forced printtarg flags"); tab_chart.py:8776 `_set_engine_checked(engine_builtin)`.
Possible solutions (no code): A. One sentence in the Manual info line: "This preset re-imports a printtarg-built chart; the engine toggle is off while it is selected." B. Grey the toggle while a prebuilt preset is active so the change is visibly the preset's. C. Restore the user's toggle state when the preset is left ("none").
Regression risk if changed: Low.
Needs owner decision: yes (whether a preset may move the toggle at all).

# F-015 After a built-in preset loads, the Manual info line shows a printtarg command that neither the chart nor the panel used (including "printtarg -iCR30", which printtarg cannot run)
Area: presets / manual
Grade: OBSERVED
Attended: unattended (presets picked through the combo's activated signal)
Type: bug (stale / wrong status text)
Severity: medium
Expected: The "Manual mode, your current configuration" line under the panel describes what Generate would run now: for an engine-built preset the engine line, for a prebuilt one the files it re-imports.
Actual (project A5-Furniture, 08:52):
- "i1Pro A4-1160p-2pages TC9.18 extended greys by Pharmacist" (prebuilt files): the chart loaded correctly (2 pages A4 portrait, 1160 patches, ChromIQ strip) and the greyed printtarg panel showed A4 Portrait; the info line read `printtarg -ii1 -pA4R -t300 -L -m15 -M15 -n chart`, i.e. the previous panel state (my A4R / 15 mm / no-spacers recipe), not the preset.
- "i1Pro A4-162p-1page-Portrait-w7.5mm Full layout setup" (engine): engine box on, chart 162 (27x6) built by the engine, info line: "bundled 162-patch .ti1 (targen skipped). printtarg -ii1 -pA4 -t200 -L -m15 -M15 -n chart".
- "CR30 A4-153p-1page-Portrait-w18.0mm-Hexagonal Full layout setup": engine on, 153 hexagons; info line: `printtarg -iCR30 -pA4 -t200 -m15 -M15 chart`. printtarg has no CR30 instrument (chart_creator.ENGINE_ONLY_INSTRUMENTS raises for it).
- "Scanner A4-3430p-1page-Landscape" : engine on, 3430 patches; info line: `printtarg -iSS -pA4R -t300 -m15 -M15 chart`.
Why it matters: This line is the one place Manual says what it will do; for built-ins it names the wrong tool with leftover flags (-t200, -m15, -n) that came from earlier states. A user reading it would believe printtarg is about to run with a 200 dpi, 15 mm, spacer-less layout.
Steps to reproduce (click by click): MANUAL, engine on, set Paper A4 landscape, margins 15, spacers none. Presets: pick "CR30 A4-153p ... Hexagonal". Read the info line under the layout panel.
Evidence: Test Runs/logs/d05b_results.json (a8-builtin-* "info" fields), d05b_presets_editor_recheck.log 08:52:05 to 08:52:20, Screenshots/A8-presets/q14-builtin-*.png.
Spec or source cited: docs/dev_builtin_presets.md ("The Manual info box says which mode it's in"); tab_chart._refresh_manual_command_preview (line 5249) builds the printtarg line from the printtarg widgets even when the preset routes to the engine or to prebuilt files.
Possible solutions (no code): A. When a preset is active, describe the preset's route ("Re-imports the bundled chart files" / the engine line from its recipe) instead of the printtarg widgets. B. Never print a printtarg line for an engine-only instrument.
Regression risk if changed: Low (display only).
Needs owner decision: no

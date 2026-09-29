# F-008 "Max strip length" and "Don't cap strip length" have no effect in "Prioritise chart area" mode, and nothing says so
Area: layout engine
Grade: OBSERVED
Attended: unattended
Type: bug / inconsistency
Severity: medium
Expected: A strip-length cap typed by the user limits the strip in either layout mode, or the control is greyed with a reason when the mode ignores it (the panel already does this for helper markers on a honeycomb).
Actual: i1Pro, A3 portrait, instrument margins on. Patch-first: Max strip 0 (auto) -> 21 patches per strip (672 total); Max strip 200 mm -> 18 per strip (576): honoured. Area-first: Max strip 0 -> 43 per strip, 400 mm strips (1376); Max strip 200 -> still 43 per strip, 400 mm (1376); "Don't cap strip length" ticked -> same 43. The estimate and the built chart agree with each other in every case, so the control is simply not part of the area-first geometry. The only feedback is the inspector's note "Strip length 400 mm exceeds the 240 mm instrument ruler", which appears with or without the cap. The Max strip spinbox has no tooltip of its own (toolTip() empty; the help sits on the info button).
Why it matters: Area-first is the default mode for i1Pro, i1Pro 3+ and ColorMunki. A user who sees the ruler warning and types a cap gets no change and no explanation, on a paper the engine offers and Guided hides for exactly this reason.
Steps to reproduce (click by click): MANUAL, engine on, i1Pro, Paper A3 portrait, Create layout "Prioritise chart area", Max strip 200 -> estimate stays 43 per strip; Generate -> 43 per strip. Switch to "Prioritise patch size": 18 per strip.
Evidence: Test Runs/logs/d03b_results.json (a3 entries), d03_results.json (g06, g07, g08), Screenshots/A4-margins/s01-A3-patchfirst-maxstrip200.png, s02-A3-areafirst-maxstrip200.png.
Spec or source cited: workflow/layout_engine/instruments.py:geom_from_build_kwargs sets `fill_beyond_ruler=area_first` unconditionally, which is documented in code as the area-first intent ("the layout may fill beyond the ruler"); no spec text covers a user-typed cap in that mode.
Possible solutions (no code): A. Let an explicit Max strip (> 0) bound the area in area-first too (the ruler default stays ignored, the user's number is honoured). B. Grey Max strip and "Don't cap" in area-first with a reason in the tooltip and the info button, the way helper markers are greyed for hexagons. C. Add one line to the layout-mode help saying area-first ignores the ruler.
Regression risk if changed: A changes area-first geometry for anyone who has a non-zero cap stored in a recipe (rare; default 0). B and C are UI only.
Needs owner decision: yes. Should area-first respect a user-typed strip cap, or is "fill the area" absolute?

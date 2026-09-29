# F-005 "Clip border: Off, more patches" produces the identical chart on A4 (and Letter, A4 landscape, custom) when instrument margins are on
Area: layout engine
Grade: OBSERVED
Attended: unattended
Type: inconsistency / UX (label promises what the default settings cannot deliver)
Severity: medium
Expected: Per the mode's own label and the selector's help ("Turning it off frees that space for more patches"), Clip border Off should move the patch block into the clip band and fit more patches.
Actual: With "Use instrument margins" ticked (the default for a fresh i1Pro / i1Pro 3+ layout), the left margin is held at the instrument minimum: 26 mm for i1Pro, 28 mm for i1Pro 3+ on A4 and Letter, which is the clip band's width. Clip On and Clip Off therefore lay out the same block: i1 A4 525 patches (25 x 21) both ways, i1 A4R 544 both ways, i1 custom 200x200 420 both ways (Left 26.0 in every case); p3 A4 120 both ways, p3 A4R 128 both ways, p3 420x297 299 both ways. Only where the threshold's L is 9 mm (A3 portrait) does Off gain anything (i1 1376 -> 1462, p3 336 -> 357). Off merely blanks the notes box: the 26 mm band stays empty white paper.
Why it matters: A user who turns the clip border off to gain patches gets nothing and loses the notes strip, with no message. The selector's help text, the Preferences threshold and the layout disagree about who owns that 26 mm.
Steps to reproduce (click by click): MANUAL, engine on, i1Pro, A4 portrait, Auto patch count, Pages 1. Note the estimate (525). Set "Clip border" to "Off, more patches". The estimate stays 525; Generate; the chart has the same 25 x 21 and the left 26 mm is blank.
Evidence: Test Runs/logs/d02_matrix.json (i1-clip-A4 vs i1-noclip-A4, p3-clip-A4 vs p3-noclip-A4, all five papers), Screenshots/A2-instruments/i1-clip-A4-preview.png and i1-noclip-A4-preview.png.
Spec or source cited: layout_options_panel.mode_tooltip_for("i1") ("Turning it off frees that space for more patches"); core/settings.py _I1_PRIMARY L=26 / _I1P3_PRIMARY L=28; docs/dev_margin_inspector.md (the 26 mm left seed IS the clip border). The i1Pro seeds encode the clip band into the instrument margin, so the two features cannot both be right.
Possible solutions (no code): A. When Clip border is Off and instrument margins are on, use the instrument's cross-scan side minimum (9 mm, as on the right) for the left edge, since the ruler run-up is top/bottom in portrait. B. Keep the 26 mm but change the label to "Off" and the help to say the space is only freed when instrument margins are off or the left minimum is lowered. C. Show a one-line note under the selector when Off gains nothing.
Regression risk if changed: A changes the geometry of every future noclip i1/p3 chart and interacts with the settled i1Pro margin rulings (19 mm bottom, jig limits); needs the owner. B and C are text only.
Needs owner decision: yes. Is the 26 mm i1Pro left minimum a jig requirement independent of the clip border, or is it the clip border itself?

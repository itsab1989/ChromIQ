# F-017 A shipped built-in chart (TC9.18 extended greys, i1Pro A4) is flagged red by the shipped i1Pro A4 Portrait minimums
Area: presets / margin inspector
Grade: OBSERVED
Attended: unattended
Type: inconsistency / unclear requirement
Severity: medium
Expected: A chart ChromIQ ships as a built-in passes the thresholds ChromIQ ships for the same instrument and paper, or the built-in says why it does not.
Actual: "i1Pro A4-1160p-2pages TC9.18 extended greys by Pharmacist" loads its prebuilt pages; Measured from Preview: Left 31.5 / Right 11.7 / Top 36.3 / Bottom 11.7 against minimums 26 / 9 / 38 / 19; verdict in red: "Top margin 36.3 mm is below the 38 mm instrument minimum" and "Bottom margin 11.7 mm is below the 19 mm instrument minimum". Strip length 248.9 mm, above the 240 mm i1Pro ruler default (the ruler note is hidden behind the red verdict, F-006). The same is likely for the other "by Pharmacist" i1Pro built-ins (not all checked).
Why it matters: A first-time user who takes the recommended built-in sees the app reject its own preset. Either the seeds (38 top, 19 bottom, "deliberate" per the owner's i1Pro rulings) or the built-in are wrong for the i1Pro jig, and the app cannot say which.
Steps to reproduce (click by click): MANUAL, Presets: pick "i1Pro A4-1160p-2pages TC9.18 extended greys by Pharmacist". Read the red lines under the preview.
Evidence: Screenshots/A8-presets/q14-builtin-tc918eg-a4-printtarg-kind.png, Test Runs/logs/d05b_results.json (a8-builtin-tc918eg-a4-printtarg-kind margin_status).
Spec or source cited: core/settings.py _I1_PRIMARY (26/9/38/9) plus the 19 mm bottom on A4 portrait (memory: deliberate, jig 240 mm limit); docs/dev_margin_inspector.md ("Seed thresholds ... rounded just below the smallest known-good margin so those (practically-tested) presets read OK out of the box"), which was written for the ColorMunki presets, not these i1Pro built-ins.
Possible solutions (no code): A. Mark prebuilt built-ins that predate the seeds with their own thresholds (they carry no recipe, so the check falls back to the instrument table). B. Re-lay the "by Pharmacist" i1Pro sets with the engine under the current minimums. C. Show a note "prebuilt chart, laid out before the current instrument limits" instead of a red verdict.
Regression risk if changed: B changes shipped charts users may already have printed and measured; A and C are UI only.
Needs owner decision: yes. Are the "by Pharmacist" i1Pro built-ins still recommended as they are, given the current i1Pro A4 minimums?

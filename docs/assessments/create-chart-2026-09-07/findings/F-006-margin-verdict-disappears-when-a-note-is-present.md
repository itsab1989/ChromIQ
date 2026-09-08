# F-006 The margin verdict ("Margins: OK" or the red violation) is hidden whenever a text note (strip length, label overflow) is present
Area: preview (Measured from Preview frame)
Grade: OBSERVED
Attended: unattended
Type: UX / bug
Severity: medium
Expected: The margin verdict and any additional notes are shown together; a strip-length note must not remove the pass/fail answer for the four margins.
Actual: With own margins 6/6/6/6 (g01), 0/0/0/0 (g02), 20/20/20/5 (g04) and on every i1 A3 portrait build (g06 to g08), the status label is empty and invisible; only the notes label shows "Top margin is too small for the strip labels" and/or "Strip length N mm exceeds the 240 mm instrument ruler". In the A2 matrix the same happened for 13 combos (i1 A3, p3 A4, p3 A3, custom papers): a valid "Margins: OK" was suppressed. Code: `ui/margin_inspector_panel.py:_update_status`: `if text_warnings: self._status.setText(""); self._status.setVisible(False); return` runs before the OK / not-defined branches; a real violation still wins (T50 case showed the red line and the ruler note together, so both CAN be shown).
Why it matters: p3 on A4 portrait, the instrument's most ordinary sheet, gets no verdict at all because a note is present; a user cannot tell whether the four margins passed.
Steps to reproduce (click by click): MANUAL, engine on, i1Pro 3+, A4 portrait, defaults, Generate. Read the frame: no "Margins: OK", no red line. Or i1Pro, "Use instrument margins" off, margins 6 mm all round, Generate.
Evidence: Test Runs/logs/d03_results.json (margin_after.status '' and visible False with notes non-empty for g01, g02, g04, g06, g07, g08), d02_matrix.json (13 blank statuses), Screenshots/A4-margins/g01-own-6666-after.png, g06-A3-portrait-ruler-after.png.
Spec or source cited: docs/dev_margin_inspector.md: "a large green Margins: OK / red violation status" is the frame's purpose.
Possible solutions (no code): A. Always show the verdict; render notes under it (the violation case already does this). B. If space is the concern, fold the notes into the verdict line ("Margins: OK. Note: strip length 282 mm exceeds ...").
Regression risk if changed: Low; layout of one frame.
Needs owner decision: no

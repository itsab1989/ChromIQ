# R-006 F-006 the margin verdict disappears whenever a text note is present
Verdict: CONFIRMED
Grade: OBSERVED (R04 f006-A3-margin-panel.png: four numbers, no verdict; the notes sit in the (i) hover only).
Code: ui/margin_inspector_panel.py:_update_status, the `if text_warnings: self._status.setText(""); setVisible(False); return` branch comes before the OK branch. The notes moved into the (i) on 2026-09-04 ("The notices left the panel's surface"), so the hidden verdict now leaves the frame with no verdict AND no visible note. Severity medium is right, arguably higher since 2026-09-04.
Spec: dev_margin_inspector.md: "a large green Margins: OK / red violation status" is the frame's purpose. Agrees with Agent 1.

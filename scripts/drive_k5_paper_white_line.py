#!/usr/bin/env python3
"""K5 (Knut, beta 34): "White (1) - L* 100.0" beside a light blue swatch.

Driven as a user: open Report-Limits-Threshold-Series, Verification, run1,
Tools > Measurement Report, find "Paper white & darkest black" in the report
shown, photograph it. After the fix the line carries a* and b*, which is what
explains the blue: the demo's paper white is Lab 100.0 / -2.4 / -19.4.

    python scripts/drive_k5_paper_white_line.py <out-dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

NAME = "Report-Limits-Threshold-Series"


def script(d):
    d.open_project(NAME)
    d.set_bar(run_type="Verification", run="run1")
    yield 800
    d.launch_tool("measurement_report")
    yield 4000
    dlg = d.top_dialog("MeasurementReportDialog")
    d.note(f"report window open: {dlg is not None}")
    if dlg is None:
        return
    dlg.resize(1300, 1100)
    yield 800
    from PyQt6.QtWidgets import QCheckBox
    box = next(c for c in dlg.findChildren(QCheckBox)
               if c.text().startswith("Show detailed data"))
    if not box.isChecked():
        box.click()                 # what the user does: the section is in
    d.note(f"'Show detailed data for each run' ticked: {box.isChecked()}")
    yield 1500
    from PyQt6.QtWidgets import QPushButton
    gen = next(b for b in dlg.findChildren(QPushButton)
               if b.text().replace("&", "").lower() == "generate report")
    d.later(gen.click)              # it may open a modal: run it queued
    yield 300
    said = d.answer("update", name="K5-generate-question", within_ms=5000)
    d.record["generate_question"] = said
    yield 4000
    view = dlg._view
    from PyQt6.QtGui import QTextCursor
    view.moveCursor(QTextCursor.MoveOperation.End)
    view.moveCursor(QTextCursor.MoveOperation.Start)
    found = view.find("Paper white & darkest black")
    view.ensureCursorVisible()
    bar = view.verticalScrollBar()
    bar.setValue(bar.value() + view.viewport().height() // 2)
    yield 600
    plain = view.toPlainText()
    (d.out / "report-text.txt").write_text(plain, encoding="utf-8")
    i = plain.find("Paper white & darkest black")
    d.note(f"section found: {found}")
    d.note("section text: " + repr(plain[i:i + 140]) if i >= 0 else
           "section text: NOT IN THE REPORT")
    d.record["section_text"] = plain[i:i + 140] if i >= 0 else None
    d.shot(dlg, "K5-paper-white-line")
    dlg.close()
    yield 500


if __name__ == "__main__":
    out = Path(sys.argv[1])
    d = Drive(out, projects=[NAME])
    sys.exit(d.run(script))

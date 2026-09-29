#!/usr/bin/env python3
"""K3 (Knut, beta 34): run 3 of Report-Limits-Threshold-Series, Full colour
check against "Quick check", carried note 1) "The standard calls this metric
recommended rather than required" on the two grey balance rows, and no
standard is the reference there.

Driven as a user: Verification, run3, Tools > Measurement Report on the run's
saved report; the page text is searched for the note and for a bracketed
limit on the grey rows.

    python scripts/drive_k3_standard_note.py <out-dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

NAME = "Report-Limits-Threshold-Series"
NOTE = "The standard calls this metric recommended rather than required"


def script(d):
    from PyQt6.QtGui import QTextCursor
    d.open_project(NAME)
    d.set_bar(run_type="Verification", run="run3")
    yield 800
    d.launch_tool("measurement_report")
    yield 4500
    dlg = d.top_dialog("MeasurementReportDialog")
    d.note(f"Report shown: {dlg._saved_combo.currentText()!r}")
    # KNUT'S PAGE WAS WORKED OUT, NOT READ OFF THE RECORD: the saved record's
    # rows carry no notes, so a drive that only opens the window cannot show
    # his fault (the first cut of this one reported "no note" on beta 35 too).
    # Generate works the report out against the run's stored copy.
    import time
    from PyQt6.QtWidgets import QPushButton
    gen = next(b for b in dlg.findChildren(QPushButton)
               if b.text().replace("&", "").lower() == "generate report")
    n = dlg._saved_combo.count()
    d.later(gen.click)
    yield 300
    d.answer("create new", within_ms=4000)
    t0 = time.monotonic()
    while time.monotonic() - t0 < 20 and dlg._saved_combo.count() == n:
        yield 250
    yield 1500
    d.note(f"generated: {dlg._saved_combo.currentText()!r}")
    text = dlg._view.toPlainText()
    d.record["note_present"] = NOTE in text
    grey = [ln for ln in text.splitlines() if "Grey balance of the grey ramp" in ln]
    d.record["grey_lines"] = grey
    d.note(f"note present: {NOTE in text}")
    for ln in grey:
        d.note(f"   {ln.strip()}")
    v = dlg._view
    v.moveCursor(QTextCursor.MoveOperation.Start)
    v.find("Grey balance of the grey ramp")
    v.ensureCursorVisible()
    yield 600
    d.shot(dlg, "run3-quick-check-grey-rows")
    dlg.close()
    yield 500


if __name__ == "__main__":
    d = Drive(Path(sys.argv[1]), projects=[NAME])
    rc = d.run(script)
    ok = d.record.get("note_present") is False
    print("AS EXPECTED" if ok else "NOT AS EXPECTED")
    sys.exit(rc or (0 if ok else 1))

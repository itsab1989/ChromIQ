#!/usr/bin/env python3
"""R4 (Knut, 2026-09-22): the "different numbers of readings" note must be a
clear information note, not body text. Driven as a user: Verification run1,
Tools > Measurement Report, "Add profile's measurements..." one of run2's
(a different chart, so a different patch count), and the note photographed.

    python scripts/drive_r4_note_box.py <out-dir>
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

NAME = "Report-Limits-Threshold-Series"


def script(d):
    from PyQt6.QtGui import QTextCursor
    from PyQt6.QtWidgets import QPushButton
    d.open_project(NAME)
    # PROFILING: the three runs' sheets are three differently sized charts,
    # and a profiling document is not narrowed to one limit set (K16), so all
    # three are in it. (A verification of run1 plus run2's date is narrowed
    # to run1 alone, so no difference ever reaches the page.)
    d.set_bar(run_type="Profiling", run="run1")
    yield 800
    d.launch_tool("measurement_report")
    yield 4000
    dlg = d.top_dialog("MeasurementReportDialog")
    d.pick(dlg._saved_combo, "new report")
    yield 1200
    dlg._select_all_btn.click()
    yield 1200
    gen = next(b for b in dlg.findChildren(QPushButton)
               if b.text().replace("&", "").lower() == "generate report")
    n = dlg._saved_combo.count()
    d.later(gen.click)
    t0 = time.monotonic()
    while time.monotonic() - t0 < 20 and dlg._saved_combo.count() == n:
        yield 250
    yield 1500
    text = dlg._view.toPlainText()
    i = text.find("readings")
    d.note(f"document rows: {len(dlg._runs_for_document())}")
    d.note(f"note text near 'readings': {text[max(0, i - 160):i + 260]!r}"
           if i >= 0 else "note: NOT ON THE PAGE")
    d.record["note_on_page"] = i >= 0
    v = dlg._view
    v.moveCursor(QTextCursor.MoveOperation.Start)
    v.find("readings")
    v.ensureCursorVisible()
    bar = v.verticalScrollBar()
    bar.setValue(bar.value() + v.viewport().height() // 2)
    yield 800
    d.shot(dlg, "note-box")
    dlg.close()
    yield 500


if __name__ == "__main__":
    d = Drive(Path(sys.argv[1]), projects=[NAME])
    sys.exit(d.run(script))

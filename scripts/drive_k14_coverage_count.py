#!/usr/bin/env python3
"""K14 (Knut, beta 34): "This report covers 1 of the 18 measurements recorded
for this project" on a Printing record of a project with three profile runs.

Driven as a user on Report-Limits-Threshold-Series:
  A  Profiling, run1, New report..., only this run's sheet ticked: the Report
     Scope must say "1 of the 3 measurements recorded for this project's
     profile runs".
  B  Verification, run1, New report..., Select all: every date of the run is
     in the report, so there must be NO coverage sentence at all.

    python scripts/drive_k14_coverage_count.py <out-dir>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

NAME = "Report-Limits-Threshold-Series"
COVERS = re.compile(r"This report covers \d+ of the \d+ measurements[^.]*\.")


def _scope_sentence(dlg):
    text = dlg._view.toPlainText()
    m = COVERS.search(text)
    return m.group(0) if m else None


def _generate(d, dlg):
    """Press Generate report the way a user does, and wait for the page."""
    import time
    from PyQt6.QtWidgets import QPushButton
    gen = next(b for b in dlg.findChildren(QPushButton)
               if b.text().replace("&", "").lower() == "generate report")
    before = dlg._saved_combo.count()
    d.later(gen.click)
    t0 = time.monotonic()
    while time.monotonic() - t0 < 20 and dlg._saved_combo.count() == before:
        yield 250
    d.note(f"   generated: Report shown = {dlg._saved_combo.currentText()!r}")
    yield 1500


def _scroll_to(dlg, needle):
    from PyQt6.QtGui import QTextCursor
    v = dlg._view
    v.moveCursor(QTextCursor.MoveOperation.Start)
    if v.find(needle):
        v.ensureCursorVisible()


def script(d):
    from PyQt6.QtCore import Qt
    d.open_project(NAME)
    # A
    d.set_bar(run_type="Profiling", run="run1")
    yield 800
    d.launch_tool("measurement_report")
    yield 4000
    dlg = d.top_dialog("MeasurementReportDialog")
    d.pick(dlg._saved_combo, "new report")
    yield 1500
    here = dlg._run_key(dlg._report)
    for i, (kind, _si, key) in enumerate(dlg._list_rows):
        if kind == "run" and key is not None and key != here:
            dlg._profile_list.item(i).setCheckState(Qt.CheckState.Unchecked)
    yield 1500
    # TICKS WAIT FOR GENERATE (Knut's own rule), so the page is read after it.
    yield from _generate(d, dlg)
    s = _scope_sentence(dlg)
    d.note(f"A profiling, one ticked: type={dlg._type_combo.currentText()!r} "
           f"sentence={s!r}")
    d.record["A"] = s
    _scroll_to(dlg, "Report Scope")
    d.shot(dlg, "A-profiling-one-of-three")
    dlg.close()
    yield 800
    # B
    d.set_bar(run_type="Verification", run="run1")
    yield 800
    d.launch_tool("measurement_report")
    yield 4000
    dlg = d.top_dialog("MeasurementReportDialog")
    d.pick(dlg._saved_combo, "new report")
    yield 1500
    dlg._select_all_btn.click()
    yield 1500
    yield from _generate(d, dlg)
    s = _scope_sentence(dlg)
    d.note(f"B verification, all {len(dlg._runs_for_report())} ticked: "
           f"sentence={s!r}")
    d.record["B"] = s
    _scroll_to(dlg, "Report Scope")
    d.shot(dlg, "B-verification-all-dates")
    dlg.close()
    yield 500


if __name__ == "__main__":
    d = Drive(Path(sys.argv[1]), projects=[NAME])
    rc = d.run(script)
    ok = (d.record.get("A") == "This report covers 1 of the 3 measurements "
          "recorded for this project's profile runs." and d.record.get("B")
          is None)
    print("AS EXPECTED" if ok else "NOT AS EXPECTED")
    sys.exit(rc or (0 if ok else 1))

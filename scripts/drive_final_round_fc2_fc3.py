"""Final round before beta 36: FC-2 (a profiling sheet beside dated
verifications is refused, and says why), FC-3 (the guide explains no ChromIQ
mechanics) and FC-8 (Unlock after Clear list), on screen on the project Knut
uses. The sheet is added the way Add does after its file dialog.

    python scripts/drive_final_round_fc2_fc3.py <out-dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

NAME = "Report-Limits-Threshold-Series"
GONE = ("ChromIQ copied", "in Preferences", "the report window",
        "Save a report after", "ChromIQ converts", "Only unlocking")


def script(d):
    from PyQt6.QtGui import QTextCursor
    d.open_project(NAME)
    d.set_bar(run_type="Verification", run="run1")
    yield 800
    d.launch_tool("measurement_report")
    yield 4500
    dlg = d.top_dialog("MeasurementReportDialog")
    d.record["generate_before"] = dlg._generate_btn.isEnabled()
    d._flush()
    sheet = dlg._run_ctx.run.dir / f"{NAME}.ti3"
    d.note(f"adding the profiling sheet {sheet.name}")
    dlg._append_source(sheet, origin=sheet)
    dlg._rebuild_from_sources()
    yield 2500
    d.record["mixed"] = dlg._kinds_are_mixed()
    d.record["generate_after"] = dlg._generate_btn.isEnabled()
    d.record["generate_tip"] = dlg._generate_btn.toolTip()
    d.note(f"Generate enabled: {d.record['generate_before']} -> "
           f"{d.record['generate_after']}; tip: {d.record['generate_tip']!r}")
    d.shot(dlg, "fc2-profiling-sheet-added-generate-greyed")
    text = dlg._view.toPlainText()
    d.record["gone_still_there"] = [g for g in GONE if g in text]
    d.note(f"removed phrases still on the page: {d.record['gone_still_there']}")
    v = dlg._view
    v.moveCursor(QTextCursor.MoveOperation.Start)
    v.find("Bound, and locked.")
    v.ensureCursorVisible()
    yield 600
    d.shot(dlg, "fc3-bound-and-locked")
    dlg._on_clear_list()
    yield 1500
    d.record["unlock_tip"] = dlg._unlock_check.toolTip()
    d.note(f"Unlock after Clear list: {d.record['unlock_tip']!r}")
    d.shot(dlg, "fc8-after-clear-list")
    dlg.close()
    yield 500


if __name__ == "__main__":
    d = Drive(Path(sys.argv[1]), projects=[NAME])
    rc = d.run(script)
    r = d.record
    ok = (r.get("mixed") is True and r.get("generate_after") is False
          and "each has its own kind of report" in r.get("generate_tip", "")
          and not r.get("gone_still_there")
          and "No measurement is loaded yet." in r.get("unlock_tip", ""))
    print("AS EXPECTED" if ok else "NOT AS EXPECTED")
    sys.exit(rc or (0 if ok else 1))

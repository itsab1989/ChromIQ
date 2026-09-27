#!/usr/bin/env python3
"""B8-1500 and B8-1503 (Knut, #182 5857473253): a saved report is shown
exactly as it was saved; a new report works every date out again. Driven ON
SCREEN in the real app.

    CHROMIQ_DEMO_PACK=<folder holding Report-Limits-Evenness, saved by an
    earlier beta> CHROMIQ_LOG_DIR=<sandbox> \\
        python scripts/drive_b8_1500_saved_vs_new.py <out> <en|de> <light|dark>

What it photographs, on Report-Limits-Evenness run1 (four dated
verifications whose reports an earlier beta saved, before the filter):

* the report the window opens on, one of those saved reports: its evenness
  rows read the figures the file holds;
* a New report of every date, Generate pressed, Create New answered: the
  same rows read this version's working (the filter on);
* the notes under the Report Limits table: the Custom columns' sentence in
  Knut's accepted wording.

The record keeps, per date, the saved file's evenness figures, what the page
drew for the saved report, and what it drew for the new one. Every modal the
drive does not expect is photographed and cancelled by the watchdog (the
"Auto-update preview" question included); a deadline ends the run. The pack
is copied, never written; settings, presets and output are sandboxed by
`userdrive`, the log by CHROMIQ_LOG_DIR, the ISO file forced to the
repository's own.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

TREE = os.environ.get("CHROMIQ_TREE") or str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402
import drive_k45_pdf_layout as K45                             # noqa: E402

K36.DEADLINE_S = 900
PROJECT = "Report-Limits-Evenness"
ROWS = ("uniformity_sd", "uniformity_de00_max_from_mean")


def _evenness(rows) -> dict:
    """{date: {row: value}} of what the page drew."""
    from workflow.measurement_report import row_values
    out = {}
    for r in rows or []:
        cells = row_values(r)
        out[str(r.get("created") or "")[:19]] = {
            rid: (cells.get(rid) or {}).get("value") for rid in ROWS}
    return out


def _saved_files(run_dir: Path) -> dict:
    """{date: {row: value}} of what the saved one-date files hold."""
    from workflow.measurement_report import row_values
    out = {}
    for p in sorted(run_dir.glob("verifications/*/reports/report_*.json")):
        rep = json.loads(p.read_text(encoding="utf-8"))
        if (rep.get("document") or {}).get("role") == "document":
            continue
        cells = row_values(rep)
        out[str(rep.get("created") or "")[:19]] = {
            rid: (cells.get(rid) or {}).get("value") for rid in ROWS}
    return out


def _show_rows(d, dlg, tr, name):
    from PyQt6.QtGui import QTextCursor
    view = dlg._view
    view.moveCursor(QTextCursor.MoveOperation.Start)
    view.find(tr("Report Results"))
    found = view.find(tr("Maximum ΔE00, between two of the nine sheet areas"))
    cur = QTextCursor(view.textCursor())
    cur.clearSelection()
    view.setTextCursor(cur)
    view.ensureCursorVisible()
    sb = view.verticalScrollBar()
    sb.setValue(min(sb.maximum(), sb.value() + 260))
    d.shot(dlg, name)
    return bool(found)


def script(lang: str, look: str):
    def s(d):
        rec = d.record
        rec.update({"language": lang, "appearance": look,
                    "mode": "ON SCREEN"})
        assert os.environ.get("CHROMIQ_LOG_DIR"), "SANDBOX THE LOG FIRST"
        K36._install_watchdog(d, rec)
        from core.i18n import tr
        from ui.dialogs.thresholds_dialog import ThresholdsDialog
        import ui.dialogs.measurement_report_dialog as mrd
        yield 600

        # 1. THE SAVED REPORT THE WINDOW OPENS ON
        d.open_project(PROJECT)
        d.set_bar(run="run1", run_type="verification")
        d.pump(1200)
        run_dir = d.work / PROJECT / "runs" / "run1"
        d.launch_tool("measurement_report")
        yield 4500
        dlg = K36._wait(d, "MeasurementReportDialog")
        if dlg is None:
            rec["error"] = "no report window"
            return
        dlg.resize(1420, 980)
        yield 2500
        rec["run_dir"] = str(run_dir)
        rec["saved_files"] = _saved_files(run_dir)
        rec["opened_on"] = dlg._saved_combo.currentText()
        rec["saved_page"] = _evenness(dlg._runs_for_report())
        rec["saved_row_found"] = _show_rows(
            d, dlg, tr, f"{lang}-{look}-01-saved-report-as-saved")
        (d.out / f"{lang}-{look}-saved-report.txt").write_text(
            dlg._view.toPlainText(), encoding="utf-8")
        yield 800

        # 2. A NEW REPORT OF EVERY DATE, GENERATED
        K45._pick_data(dlg._saved_combo, mrd.NEW_REPORT_KEY)
        yield 2000
        rec["ticks"] = K45._tick(dlg, "all")
        yield 2500
        rec["new_page_before_generate"] = _evenness(dlg._runs_for_report())
        K36.EXPECTED.add("QMessageBox")
        d.later(dlg._generate_btn.click)
        yield 600
        rec["generate_question"] = d.answer(
            "neu" if lang == "de" else "new", f"{lang}-{look}-question",
            within_ms=4000)
        K36.EXPECTED.discard("QMessageBox")
        yield 12000
        rec["new_report_shown"] = dlg._saved_combo.currentText()
        rec["new_page"] = _evenness(dlg._runs_for_report())
        rec["new_row_found"] = _show_rows(
            d, dlg, tr, f"{lang}-{look}-02-new-report-worked-out-again")
        (d.out / f"{lang}-{look}-new-report.txt").write_text(
            dlg._view.toPlainText(), encoding="utf-8")
        # the files: every saved one-date report is untouched
        rec["saved_files_after"] = _saved_files(run_dir)
        dlg.close()
        yield 2000

        # 3. THE REPORT LIMITS NOTE
        td = ThresholdsDialog(d.settings, d.win)
        td.resize(1480, 960)
        td.show()
        td.raise_()
        yield 2200
        td._scroll.verticalScrollBar().setValue(
            td._scroll.verticalScrollBar().maximum())
        yield 900
        rec["note"] = td._notes_text()
        d.shot(td, f"{lang}-{look}-03-limits-note")
        td.close()
        yield 1200
    return s


def main() -> int:
    out = Path(sys.argv[1])
    lang, look = sys.argv[2], sys.argv[3]
    d = Drive(out, projects=[PROJECT], language=lang, appearance=look)
    rc = d.run(script(lang, look))
    (out / f"{lang}-{look}-record.json").write_text(
        json.dumps(d.record, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

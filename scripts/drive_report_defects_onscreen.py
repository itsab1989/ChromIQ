#!/usr/bin/env python3
"""Drive the two Measurement Report defects in the real widgets, on screen.

Both were found by the #182 design work and both make the report untrustworthy,
in opposite directions:

1. **A failed report was silent, and looked like a success.**
   `TabMeasure._maybe_save_measurement_report` sent every failure to
   `log.warning` and appended nothing to the screen — while the SUCCESS of the
   same operation announces itself in the measurement log. Here the failure is
   made REAL, not stubbed: the run folder is made read-only, so `save_report`
   raises a genuine `PermissionError` from the operating system.

2. **Saved reports were silently re-graded.** The Pass thresholds are a global
   setting and the verdict was worked out at DISPLAY time, so moving one spin
   box re-graded every historical report. Here two reports are put on disk —
   one saved WITH its verdict (the new behaviour) and one without (everything
   already on the user's disk) — the window is opened, the thresholds are
   loosened from 2.0/3.0 to 9.0/9.0, and the two reports are photographed
   before and after.

Sandbox the settings FIRST — this builds a real `AppSettings`::

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-agentAE.ini
    .venv/bin/python scripts/drive_report_defects_onscreen.py [outdir]

It also points `AppSettings._qs` at its own throwaway .ini, so the real
preferences cannot be reached even if the variable is forgotten.
"""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QSettings                          # noqa: E402
from PyQt6.QtGui import QFontDatabase                       # noqa: E402
from PyQt6.QtWidgets import QApplication                    # noqa: E402

from core.resource_path import resource_path                # noqa: E402

FAILURES: list[str] = []

_TI2 = """CTI1

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 4
BEGIN_DATA
1 "A1" 100 100 100 95.0 100.0 108.0
2 "A2" 0 0 0 1.0 1.0 1.0
3 "A3" 100 0 0 41.0 21.0 2.0
4 "A4" 0 100 0 36.0 71.0 12.0
END_DATA
"""
_TI3 = (_TI2.replace("CTI1", "CTI3")
            .replace("41.0 21.0 2.0", "36.0 18.0 3.0")
            .replace("36.0 71.0 12.0", "33.0 68.0 14.0"))


def check(what: str, ok: bool, detail: str = "") -> None:
    print(f"  {'OK  ' if ok else 'FAIL'} {what}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILURES.append(what)


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def scroll_to(dlg, needle: str, app) -> bool:
    """Put *needle* at the top of the report view, so the screenshot shows the
    part being talked about rather than page one."""
    from PyQt6.QtGui import QTextCursor
    view = dlg._view
    view.moveCursor(QTextCursor.MoveOperation.Start)
    found = view.find(needle)
    if found:
        c = view.textCursor()
        c.clearSelection()
        view.setTextCursor(c)
        # `find` leaves the match at the BOTTOM of the viewport; lift it to
        # the top so the screenshot shows what comes after it.
        bar = view.verticalScrollBar()
        bar.setValue(min(bar.maximum(),
                         bar.value() + view.cursorRect().top() - 16))
    pump(app, 200)
    return bool(found)


def shot(w, out: Path, name: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    p = out / name
    w.grab().save(str(p))
    print(f"       → {p}")


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1
               else "/Users/Basti/Desktop/beta 8/25-report-defects")
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    try:
        for fp in Path(resource_path("assets/fonts")).glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(fp))
    except Exception:      # noqa: BLE001
        pass
    from ui import styles
    app.setStyle(styles.WinButtonLayoutStyle("Fusion"))
    app.setPalette(styles.make_dark_palette())
    app.setStyleSheet(styles.APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_agentAE_drive_"))
    work = sandbox / "working"
    work.mkdir()

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager, Project
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_measure import TabMeasure
    from workflow import measurement_messages as M
    from workflow import measurement_report as mr

    settings = AppSettings()
    settings._qs = QSettings(str(sandbox / "drive.ini"),
                             QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(work))
    settings.set("save_measurement_report", True)
    settings.set("report_pass_threshold_avg", 2.0)
    settings.set("report_pass_threshold_max", 3.0)

    # ------------------------------------------------------------------
    print("\n== DEFECT 1 · a failed report is told on screen ==")
    fm = FileManager(settings)
    proj = Project.create(work / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    (run.dir / "P.ti2").write_text(_TI2, encoding="utf-8")
    ti3 = run.dir / "P.ti3"
    ti3.write_text(_TI3, encoding="utf-8")
    fm.set_target_name("P")

    tab = TabMeasure(ArgyllRunner(settings), settings)
    tab.set_target_controller(MeasurementTargetController(fm))
    tab.resize(1500, 1000)
    tab.show()
    pump(app, 500)

    # A REAL failure: the run folder cannot be written, so save_report's
    # reports/ mkdir raises PermissionError from the OS itself.
    before = run.dir.stat().st_mode
    os.chmod(run.dir, stat.S_IRUSR | stat.S_IXUSR)
    try:
        tab._maybe_save_measurement_report(ti3)
        pump(app, 400)
        text = tab._log.toPlainText()
        headline, _ = M.M_REPORT_NOT_SAVED.render()
        check("the measurement log names the failure", headline in text)
        check("…and says why, in the OS's own words",
              "denied" in text.lower() or "permission" in text.lower(),
              text.strip().splitlines()[-1][:70] if text.strip() else "(empty)")
        check("the status line under the buttons says it too",
              headline in tab._status_bar_lbl.text()
              and tab._status_bar_lbl.isVisibleTo(
                  tab._status_bar_lbl.parentWidget()))
        shot(tab, out, "01-measure-tab-report-failed.png")
    finally:
        os.chmod(run.dir, before)

    tab._log.clear()
    tab._maybe_save_measurement_report(ti3)
    pump(app, 300)
    ok_text = tab._log.toPlainText()
    check("a report that CAN be written still says only that",
          "Measurement report saved" in ok_text
          and M.M_REPORT_NOT_SAVED.render()[0] not in ok_text)
    shot(tab, out, "02-measure-tab-report-saved.png")
    saved = sorted((run.dir / "reports").glob("report_*.json"))
    check("…and the file it wrote carries its verdict",
          bool(saved) and mr.recorded_thresholds(
              json.loads(saved[-1].read_text(encoding="utf-8"))) == (2.0, 3.0))
    tab.hide()

    # ------------------------------------------------------------------
    print("\n== DEFECT 2 · a saved report keeps its verdict ==")
    p2 = Project.create(work / "Q", "Q")
    r2 = p2.current_run()
    r2.ensure_dir()
    (r2.dir / "Q.ti2").write_text(_TI2, encoding="utf-8")
    q_ti3 = r2.dir / "Q.ti3"
    q_ti3.write_text(_TI3, encoding="utf-8")
    reports = r2.dir / "reports"
    reports.mkdir(exist_ok=True)

    # One report as ChromIQ saves them from now on: judged, and the judgement
    # written down beside the numbers.
    graded = mr.build_report(q_ti3)
    graded["created"] = "2026-03-01T10:00:00"
    mr.stamp_verdict(graded, 2.0, 3.0)
    (reports / "report_2026-03-01_10-00-00.json").write_text(
        json.dumps(graded, indent=2), encoding="utf-8")
    # …and one exactly as every report already on the user's disk looks.
    old = mr.build_report(q_ti3)
    old["created"] = "2026-02-01T10:00:00"
    (reports / "report_2026-02-01_10-00-00.json").write_text(
        json.dumps(old, indent=2), encoding="utf-8")

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(settings, None, initial_ti3=q_ti3)
    dlg.resize(1250, 950)
    dlg.show()
    pump(app, 700)
    check("both dates are in the report",
          len(dlg._runs_for_report()) == 2,
          f"{len(dlg._runs_for_report())} runs")
    shot(dlg, out, "03-report-window-at-2.0-3.0.png")

    runs = dlg._runs_for_report()
    graded_run = next(r for r in runs if mr.recorded_thresholds(r))
    old_run = next(r for r in runs if not mr.recorded_thresholds(r))
    v_before = {x["key"]: x["pass"] for x in dlg._verdict_rows(graded_run)[0]}
    o_before = {x["key"]: x["pass"] for x in dlg._verdict_rows(old_run)[0]}
    html_before = dlg._report_results_html(runs)
    check("the grid names what each column was judged against",
          "2.0 / 3.0" in html_before and "not recorded" in html_before)
    scroll_to(dlg, "Report Results", app)
    shot(dlg, out, "03b-report-results-at-2.0-3.0.png")

    # THE COMPLAINT, DRIVEN: loosen the thresholds far enough that anything
    # judged live would flip to Pass.
    dlg._avg_thr_spin.setValue(9.0)
    dlg._max_thr_spin.setValue(9.0)
    pump(app, 700)
    scroll_to(dlg, "Report Results", app)
    shot(dlg, out, "04-report-results-after-thresholds-9.0.png")

    v_after = {x["key"]: x["pass"] for x in dlg._verdict_rows(graded_run)[0]}
    o_after = {x["key"]: x["pass"] for x in dlg._verdict_rows(old_run)[0]}
    check("the RECORDED verdict did not move", v_before == v_after,
          f"{v_before} → {v_after}")
    check("…and it is the verdict it was given, not a pass",
          v_after.get("avg_all") is False)
    check("the report with NO recorded verdict is still graded live",
          o_before.get("avg_all") is not o_after.get("avg_all"),
          f"{o_before.get('avg_all')} → {o_after.get('avg_all')}")

    # The detailed chapter, which is where the provenance sentence lives.
    dlg._detail_check.setChecked(True)
    pump(app, 700)
    scroll_to(dlg, "recorded when the report was saved", app)
    shot(dlg, out, "05-detail-recorded-verdict.png")
    scroll_to(dlg, "Nothing is wrong with this report", app)
    shot(dlg, out, "06-detail-no-recorded-verdict.png")
    body = dlg._report_body_html(runs, for_pdf=False)
    check("a recorded verdict says when it was recorded",
          "recorded when the report was saved" in body)
    check("an unrecorded one says the numbers are today's",
          "Nothing is wrong with this report" in body)

    # Nothing on disk was rewritten by looking at it.
    check("the saved files are untouched by the window",
          json.loads((reports / "report_2026-02-01_10-00-00.json")
                     .read_text(encoding="utf-8")) == old)
    dlg.close()

    print("\n" + ("ALL CHECKS PASSED" if not FAILURES
                  else f"{len(FAILURES)} FAILED: {FAILURES}"))
    print(f"screenshots: {out}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())

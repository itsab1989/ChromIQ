#!/usr/bin/env python3
"""Combined round 2: the seams round 1 did not reach.

Round 1 drove Generate, the report window and the selector on ONE project. It
did not drive two projects in one session, nor a report that appears on disk
while the window sits open, nor the one shape the "Saved reports" row is in
most of the time: a measurement with exactly ONE saved report, where "choosing
one shows that report" has nothing else to show.

Each seam is measured, not asserted: the document's own text is compared before
and after, and every mutation is read back off disk.
"""
from __future__ import annotations

import html as _html
import json
import os
import re
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

A = Path.home() / "ChromIQ" / "Demo-Switching"
B = Path.home() / "ChromIQ" / "Demo-Prefs-Speed"


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def text_of(h: str) -> str:
    s = re.sub(r"<[^>]+>", "\n", h or "")
    return "\n".join(l.strip() for l in _html.unescape(s).splitlines() if l.strip())


def shot(d) -> dict:
    return {
        "history": len(d._history),
        "sources": len(d._sources),
        "list_rows": [d._profile_list.item(i).text()
                      for i in range(d._profile_list.count())],
        "saved_combo": [d._saved_combo.itemText(i)
                        for i in range(d._saved_combo.count())],
        "saved_row_visible": d._saved_combo.isVisible(),
        "delete_enabled": d._delete_report_btn.isEnabled(),
        "trend_de_points": len(getattr(d._trend_de, "_series", []) or []),
        "document": text_of(d._view.toHtml()),
    }


def main() -> int:                                   # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    R: dict = {}
    crashes: list = []
    prev = sys.excepthook
    sys.excepthook = lambda t, e, tb: (
        crashes.append("".join(traceback.format_exception(t, e, tb))),
        prev(t, e, tb))

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r2s-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("restore_last_session", False)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    R["locked_at_start"] = session_is_locked()

    pa, pb = work / A.name, work / B.name
    shutil.copytree(A, pa, symlinks=True)
    shutil.copytree(B, pb, symlinks=True)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    MeasurementReportDialog._confirm = lambda self, t, b: True      # type: ignore
    apply_appearance(app, None, "dark")
    fm = FileManager(settings)
    del fm

    a_ti3 = pa / "runs" / "run1" / "Demo-Switching.ti3"
    assert a_ti3.is_file()

    d = MeasurementReportDialog(settings, None, initial_ti3=a_ti3)
    d.resize(1500, 1050)
    d.show()
    pump(app, 3000)

    # ---- SEAM 1: ONE saved report. What does choosing it do? --------------
    before = shot(d)
    R["seam1_before"] = {k: v for k, v in before.items() if k != "document"}
    R["seam1_combo_len"] = len(before["saved_combo"])
    # THE CALL, AND NOTHING ELSE. A first cut timed the pick together with
    # its own `pump(app, 2500)` and reported 2.57 s, which is the pump. What a
    # reader waits for is the blocking call on the GUI thread.
    d._saved_combo.setCurrentIndex(0)
    t0 = time.monotonic()
    d._on_saved_chosen(0)
    first_pick_s = time.monotonic() - t0
    pump(app, 2500)
    after = shot(d)
    t1 = time.monotonic()
    d._on_saved_chosen(0)
    second_pick_s = time.monotonic() - t1
    pump(app, 600)
    again = shot(d)
    R["seam1"] = {
        "reports_offered": len(before["saved_combo"]),
        "first_pick_ms": round(first_pick_s * 1000, 1),
        "second_pick_ms": round(second_pick_s * 1000, 1),
        "document_changed_by_first_pick":
            before["document"] != after["document"],
        "document_changed_by_second_pick":
            after["document"] != again["document"],
        "list_rows_changed": before["list_rows"] != after["list_rows"],
        "trend_points_changed":
            before["trend_de_points"] != after["trend_de_points"],
        "row_is_visible_with_one_report": before["saved_row_visible"],
    }
    print(f"    SEAM 1: {R['seam1']['reports_offered']} report offered; "
          f"first pick {R['seam1']['first_pick_ms']} ms, second "
          f"{R['seam1']['second_pick_ms']} ms; document changed: "
          f"{R['seam1']['document_changed_by_first_pick']}", flush=True)
    ok, why = capture_window(d, out / "S1-one-report-row.png")
    R["capture_S1"] = {"ok": ok, "why": why}

    # ---- SEAM 2: a SECOND project in the same window ----------------------
    import ui.dialogs.measurement_report_dialog as mrd
    b_ti3 = next(iter(sorted(pb.glob("runs/*/*.ti3"))), None)
    R["second_project_measurement"] = str(b_ti3)
    assert b_ti3 is not None, "no measurement in the second project"
    mrd.open_files_dialog = lambda *a, **k: [str(b_ti3)]
    d._on_add_project()
    pump(app, 4000)
    two = shot(d)
    R["seam2"] = {
        "sources": two["sources"],
        "history": two["history"],
        "list_rows": two["list_rows"],
        "saved_combo": two["saved_combo"],
        "delete_enabled": two["delete_enabled"],
        "trend_de_points": two["trend_de_points"],
        "both_project_names_in_list":
            all(any(n in r for r in two["list_rows"]) for n in (A.name, B.name)),
    }
    print(f"    SEAM 2: {two['sources']} sources, {two['history']} measurements, "
          f"both named: {R['seam2']['both_project_names_in_list']}", flush=True)
    print(f"            saved combo now: {two['saved_combo']}", flush=True)
    ok, why = capture_window(d, out / "S2-two-projects.png")
    R["capture_S2"] = {"ok": ok, "why": why}

    # ---- SEAM 3: a report lands on disk while the window is OPEN ----------
    # A measurement finishing elsewhere writes into reports/. The window is
    # already showing this run. Does the row notice?
    rdir = pa / "runs" / "run1" / "reports"
    rdir.mkdir(parents=True, exist_ok=True)
    src = next(iter(sorted(rdir.glob("report_*.json"))), None)
    assert src is not None, "no report to clone"
    clone = rdir / "report_2026-09-17_00-00-00.json"
    body = json.loads(src.read_text(encoding="utf-8"))
    body["created"] = "2026-09-17T00:00:00"
    clone.write_text(json.dumps(body, indent=2), encoding="utf-8")
    assert clone.is_file(), "the clone did not land"          # read it back
    R["seam3_clone_on_disk"] = clone.is_file()
    combo_before = [d._saved_combo.itemText(i)
                    for i in range(d._saved_combo.count())]
    pump(app, 2000)
    combo_idle = [d._saved_combo.itemText(i)
                  for i in range(d._saved_combo.count())]
    # …and after the one action a user would take next.
    d._saved_combo.setCurrentIndex(0)
    d._on_saved_chosen(0)
    pump(app, 2500)
    combo_after = [d._saved_combo.itemText(i)
                   for i in range(d._saved_combo.count())]
    R["seam3"] = {
        "combo_before_the_file_landed": combo_before,
        "combo_while_idle_after_it_landed": combo_idle,
        "combo_after_choosing_a_report": combo_after,
        "noticed_while_idle": combo_idle != combo_before,
        "noticed_after_an_action": combo_after != combo_before,
    }
    print(f"    SEAM 3: a report landed on disk. noticed while idle: "
          f"{R['seam3']['noticed_while_idle']}; after an action: "
          f"{R['seam3']['noticed_after_an_action']}", flush=True)
    ok, why = capture_window(d, out / "S3-report-landed-while-open.png")
    R["capture_S3"] = {"ok": ok, "why": why}
    d.close()
    pump(app, 800)

    # ---- SEAM 4: reopened from disk. Does it agree with what was shown? ---
    d2 = MeasurementReportDialog(settings, None, initial_ti3=a_ti3)
    d2.resize(1500, 1050)
    d2.show()
    pump(app, 3000)
    fresh = shot(d2)
    R["seam4"] = {
        "saved_combo": fresh["saved_combo"],
        "history": fresh["history"],
        "agrees_with_the_open_window": fresh["saved_combo"] == combo_after,
    }
    print(f"    SEAM 4: reopened; combo {fresh['saved_combo']}; agrees: "
          f"{R['seam4']['agrees_with_the_open_window']}", flush=True)
    ok, why = capture_window(d2, out / "S4-reopened.png")
    R["capture_S4"] = {"ok": ok, "why": why}
    d2.close()
    pump(app, 500)

    R["crashes"] = crashes
    (out / "seams-findings.json").write_text(
        json.dumps(R, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8")
    print(f"    crashes: {len(crashes)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

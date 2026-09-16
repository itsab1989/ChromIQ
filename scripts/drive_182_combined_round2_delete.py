#!/usr/bin/env python3
"""Combined round 2: what does a user lose when the only saved report of a
PROFILING measurement is deleted?

Round 1 raised this for judgement and did not settle it. The refusal in
`_saved_delete_refusal` covers only a DATED VERIFICATION; a profiling
measurement's last report may be deleted, and the confirmation
(`M-REPORT-DELETE`) promises *"The measurement it describes is not touched"*.

This drives a REAL window on a REAL two-run project and measures, at each
step, how many measurements the document covers, what the run list shows,
how many points the trend holds, and what is on disk. Then it re-opens the
window on the deleted measurement's OWN file, which is the only question that
decides whether "for good" is the right word.

Every mutation is read back off disk before anything is believed.
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

SOURCE = Path.home() / "ChromIQ" / "Demo-Switching"


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def text_of(h: str) -> str:
    s = re.sub(r"<[^>]+>", "\n", h or "")
    return "\n".join(l.strip() for l in _html.unescape(s).splitlines() if l.strip())


def snapshot(d) -> dict:
    """What the window is showing, measured off the widgets."""
    rows = []
    for i in range(d._profile_list.count()):
        it = d._profile_list.item(i)
        rows.append(it.text())
    combo = [d._saved_combo.itemText(i) for i in range(d._saved_combo.count())]
    trend = {}
    for nm, ch in (("de", d._trend_de), ("white", d._trend_white),
                   ("black", d._trend_black), ("corners", d._trend_corners)):
        trend[nm] = len(getattr(ch, "_series", []) or [])
    return {
        "history": len(d._history),
        "origins": sorted({Path(str(r.get("_origin_dir") or "")).name
                           for r in d._history}),
        "list_rows": rows,
        "saved_combo": combo,
        "saved_combo_index": d._saved_combo.currentIndex(),
        "delete_enabled": d._delete_report_btn.isEnabled(),
        "saved_note": d._saved_note_full,
        "trend_points": trend,
        "trend_visible": d._trend_tabs.isVisible(),
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r2d-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("restore_last_session", False)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    R["locked_at_start"] = session_is_locked()
    print(f"    screen locked at start: {R['locked_at_start']}", flush=True)

    proj = work / "Demo-Switching"
    shutil.copytree(SOURCE, proj, symlinks=True)

    prof_report = proj / "runs" / "run1" / "reports" / "report_2026-05-02_10-15-00.json"
    prof_ti3 = proj / "runs" / "run1" / "Demo-Switching.ti3"
    verif_ti3 = (proj / "runs" / "run2" / "verifications"
                 / "2026-06-24_164000" / "Demo-Switching-verify.ti3")
    verif_report = (proj / "runs" / "run2" / "verifications"
                    / "2026-06-24_164000" / "reports"
                    / "report_2026-06-24_16-40-00.json")
    for p in (prof_report, prof_ti3, verif_ti3, verif_report):
        assert p.is_file(), f"fixture missing: {p}"
    R["fixture"] = {
        "profiling_report": prof_report.name,
        "profiling_ti3_bytes": prof_ti3.stat().st_size,
        "verification_report": verif_report.name,
    }

    # The confirmation is RECORDED, not blanket-approved: its promise is part
    # of what is on trial.
    said: list = []
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    MeasurementReportDialog._confirm = (                      # type: ignore
        lambda self, t, b: (said.append({"title": t, "body": b}), True)[1])

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from core.file_manager import FileManager
    from ui.theme import apply_appearance
    apply_appearance(app, None, "dark")
    fm = FileManager(settings)
    del fm

    # ---- STAGE 1: open on the NEWEST dated verification. The window gathers
    #      the whole project, so run1's profiling measurement is in it via its
    #      single saved report.
    d = MeasurementReportDialog(settings, None, initial_ti3=prof_ti3)
    d.resize(1500, 1050)
    d.show()
    pump(app, 3000)
    R["stage1_open_on_the_profiling_run"] = snapshot(d)
    ok, why = capture_window(d, out / "01-opened-on-the-profiling-run.png")
    R["capture_01"] = {"ok": ok, "why": why}
    print(f"    capture 01: {ok} {why}", flush=True)
    print(f"    history={R['stage1_open_on_the_profiling_run']['history']} "
          f"origins={R['stage1_open_on_the_profiling_run']['origins']}", flush=True)
    print(f"    saved combo: {R['stage1_open_on_the_profiling_run']['saved_combo']}",
          flush=True)

    # ---- STAGE 2: pick the PROFILING measurement's only saved report.
    target = None
    for i in range(d._saved_combo.count()):
        data = d._saved_combo.itemData(i)
        if data and data[1] == prof_report.name:
            target = i
            break
    R["profiling_report_in_combo"] = target
    if target is None:
        R["FINDING_not_offered"] = (
            "run1's only saved report is not in the Saved reports pulldown")
    else:
        d._saved_combo.setCurrentIndex(target)
        d._on_saved_chosen(target)
        pump(app, 2500)
        R["stage2_profiling_selected"] = snapshot(d)
        ok, why = capture_window(d, out / "02-profiling-report-selected.png")
        R["capture_02"] = {"ok": ok, "why": why}
        print(f"    delete enabled on a PROFILING report: "
              f"{R['stage2_profiling_selected']['delete_enabled']}", flush=True)
        print(f"    note: {R['stage2_profiling_selected']['saved_note']!r}",
              flush=True)

    # ---- STAGE 3: pick a DATED VERIFICATION's only saved report, for contrast.
    dv = MeasurementReportDialog(settings, None, initial_ti3=verif_ti3)
    dv.resize(1500, 1050)
    dv.show()
    pump(app, 3000)
    vtarget = None
    for i in range(dv._saved_combo.count()):
        data = dv._saved_combo.itemData(i)
        if data and data[1] == verif_report.name:
            vtarget = i
            break
    if vtarget is not None:
        dv._saved_combo.setCurrentIndex(vtarget)
        dv._on_saved_chosen(vtarget)
        pump(app, 2000)
        R["stage3_verification_selected"] = snapshot(dv)
        ok, why = capture_window(dv, out / "03-verification-report-selected.png")
        R["capture_03"] = {"ok": ok, "why": why}
        print(f"    delete enabled on a DATED VERIFICATION report: "
              f"{R['stage3_verification_selected']['delete_enabled']}", flush=True)
        print(f"    note: {R['stage3_verification_selected']['saved_note']!r}",
              flush=True)
    dv.close()
    pump(app, 600)

    # ---- STAGE 4: back to the profiling report, and DELETE it.
    if target is not None:
        for i in range(d._saved_combo.count()):
            data = d._saved_combo.itemData(i)
            if data and data[1] == prof_report.name:
                d._saved_combo.setCurrentIndex(i)
                d._on_saved_chosen(i)
                break
        pump(app, 2000)
        assert prof_report.is_file(), "the report is gone before the delete"
        d._on_delete_report()
        pump(app, 3000)
        R["confirmation_shown"] = said[-1] if said else None
        # PROVE THE MUTATION LANDED, off disk.
        R["report_on_disk_after_delete"] = prof_report.is_file()
        R["ti3_on_disk_after_delete"] = prof_ti3.is_file()
        R["ti3_bytes_after_delete"] = (prof_ti3.stat().st_size
                                       if prof_ti3.is_file() else None)
        R["stage4_after_delete"] = snapshot(d)
        ok, why = capture_window(d, out / "04-after-delete.png")
        R["capture_04"] = {"ok": ok, "why": why}
        print(f"    report on disk after delete: "
              f"{R['report_on_disk_after_delete']}", flush=True)
        print(f"    measurement .ti3 still on disk: "
              f"{R['ti3_on_disk_after_delete']} "
              f"({R['ti3_bytes_after_delete']} bytes)", flush=True)
        print(f"    history now {R['stage4_after_delete']['history']} "
              f"origins={R['stage4_after_delete']['origins']}", flush=True)
    d.close()
    pump(app, 800)

    # ---- STAGE 5: REOPEN on the verification. Is the profiling measurement
    #      gone from this document for good?
    d2 = MeasurementReportDialog(settings, None, initial_ti3=prof_ti3)
    d2.resize(1500, 1050)
    d2.show()
    pump(app, 3000)
    R["stage5_reopened_on_the_profiling_run"] = snapshot(d2)
    ok, why = capture_window(d2, out / "05-reopened-on-the-profiling-run.png")
    R["capture_05"] = {"ok": ok, "why": why}
    print(f"    reopened on the profiling run: history="
          f"{R['stage5_reopened_on_the_profiling_run']['history']} "
          f"origins={R['stage5_reopened_on_the_profiling_run']['origins']}", flush=True)
    d2.close()
    pump(app, 800)

    # ---- STAGE 6: REOPEN on the DELETED measurement's OWN file. The fall-back
    #      in `_gather_runs` should build it fresh. This is what decides
    #      whether the measurement is lost or only its saved verdict is.
    old_ti3 = next(iter(sorted(
        (proj / "runs" / "run1" / "old").glob("*/Demo-Switching.ti3"))), None)
    R["archived_measurement"] = str(old_ti3) if old_ti3 else None
    if old_ti3 is None:
        R["stage6_reopened_on_the_measurement"] = "no archived measurement"
        (out / "delete-findings.json").write_text(
            json.dumps(R, indent=2, default=str), encoding="utf-8")
        return 0
    d3 = MeasurementReportDialog(settings, None, initial_ti3=old_ti3)
    d3.resize(1500, 1050)
    d3.show()
    pump(app, 3000)
    R["stage6_reopened_on_the_measurement"] = snapshot(d3)
    body = text_of(d3._view.toHtml())
    R["stage6_document_head"] = body[:1500]
    ok, why = capture_window(d3, out / "06-reopened-on-the-measurement.png")
    R["capture_06"] = {"ok": ok, "why": why}
    print(f"    reopened on the ARCHIVED measurement: history="
          f"{R['stage6_reopened_on_the_measurement']['history']} "
          f"origins={R['stage6_reopened_on_the_measurement']['origins']}",
          flush=True)
    d3.close()
    pump(app, 500)

    R["crashes"] = crashes
    (out / "delete-findings.json").write_text(
        json.dumps(R, indent=2, default=str), encoding="utf-8")
    print(f"    crashes: {len(crashes)}", flush=True)
    print(f"    written: {out / 'delete-findings.json'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

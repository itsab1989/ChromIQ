#!/usr/bin/env python3
"""The challenge round against B8-246: assume the one-limit-set fix broke
something a user can see, and try to prove it in a REAL window."""
from __future__ import annotations
import json, os, re, shutil, sys, tempfile, time
from pathlib import Path

ROOT = Path("/Users/Basti/develop/ChromIQ"); sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtCore import Qt                                    # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
from onscreen_capture import capture_window                     # noqa: E402

PACK = Path("/tmp/rep-demo")
OUT = Path(sys.argv[1])
RESULT: dict = {}


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def text_of(h: str) -> str:
    import html as _h
    s = re.sub(r"<[^>]+>", "\n", h)
    return "\n".join(l.strip() for l in _h.unescape(s).splitlines() if l.strip())


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    import traceback
    sys.excepthook = lambda t, v, tb: traceback.print_exception(t, v, tb)
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-chal-"))
    settings = AppSettings(); settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    src = PACK / "Report-Limits-Report-Types"
    dst = work / src.name; shutil.copytree(src, dst)
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    MeasurementReportDialog._confirm = (lambda self, t, x: True)  # type: ignore
    apply_appearance(app, None, "dark")
    fm = FileManager(settings); del fm

    ti3 = dst / "runs" / "run1" / "Report-Limits-Report-Types.ti3"
    assert ti3.is_file(), ti3
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1500, 1050); dlg.show(); dlg.raise_(); pump(app, 2500)
    print("window:", dlg.isVisible(), dlg.frameGeometry().width(), flush=True)

    # ---------------------------------------------------------------- C1
    d = dlg._report_dir()
    RESULT["C1_pdf_folder"] = str(d.relative_to(work))
    RESULT["C1_loaded"] = len(dlg._runs_for_report())
    RESULT["C1_in_document"] = len(dlg._runs_for_document())
    print("C1 pdf folder:", RESULT["C1_pdf_folder"],
          "loaded", RESULT["C1_loaded"], "in-doc", RESULT["C1_in_document"],
          flush=True)

    # ---------------------------------------------------------------- C2
    pdf = OUT / "C2-report.pdf"
    import ui.widgets as _w
    from PyQt6.QtGui import QDesktopServices
    _w.save_file_dialog = lambda *a, **k: str(pdf)
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
    dlg._pdf_btn.click()
    pump(app, 4000)
    RESULT["C2_pdf_written"] = pdf.exists() and pdf.stat().st_size
    print("C2 pdf:", RESULT["C2_pdf_written"], flush=True)

    # ---------------------------------------------------------------- C3
    combo = dlg._type_combo
    types = {}
    for i in range(combo.count()):
        tid = combo.itemData(i)
        if not tid or not combo.model().item(i).isEnabled():
            continue
        combo.setCurrentIndex(i); pump(app, 900)
        dlg._on_generate_report(); pump(app, 1500)
        body = text_of(dlg._view.toHtml())
        m = re.search(r"No\. of Measurements:\s*\n?(\d+)", body)
        types[combo.itemText(i)] = {
            "in_document": len(dlg._runs_for_document()),
            "scope_count": m.group(1) if m else None,
            "left_out_note": "judged against a different limit set" in body,
            "old_warning": "were not all judged against the same limit set" in body,
            "sets_named": sorted(set(re.findall(
                r"judged against (ChromIQ [a-z]+|Quick check|Custom ISO [\d\-]+)",
                body))),
        }
        print("C3", combo.itemText(i), types[combo.itemText(i)], flush=True)
        (OUT / f"C3-{combo.itemText(i).replace(' ', '-')}.txt").write_text(
            body, encoding="utf-8")
    RESULT["C3_types"] = types
    combo.setCurrentIndex(combo.findData("t2_full_colour_check"))
    dlg._on_generate_report(); pump(app, 1200)

    # ---------------------------------------------------------------- C4
    rows = [i for i, (kind, _si, key) in enumerate(dlg._list_rows)
            if kind == "run" and key]
    subject = dlg._run_key(dlg._report)
    sub_row = next((i for i, (k, _s, key) in enumerate(dlg._list_rows)
                    if k == "run" and key == subject), None)
    if sub_row is not None:
        dlg._profile_list.item(sub_row).setCheckState(Qt.CheckState.Unchecked)
        pump(app, 1500)
        body = text_of(dlg._view.toHtml())
        m = re.search(r"No\. of Measurements:\s*\n?(\d+)", body)
        RESULT["C4_subject_unticked"] = {
            "in_document": len(dlg._runs_for_document()),
            "scope_count": m.group(1) if m else None,
            "old_warning": "were not all judged against the same limit set" in body,
            "sets_named": sorted(set(re.findall(
                r"judged against (ChromIQ [a-z]+|Quick check|Custom ISO [\d\-]+)",
                body))),
        }
        print("C4", RESULT["C4_subject_unticked"], flush=True)
        (OUT / "C4-subject-unticked.txt").write_text(body, encoding="utf-8")
        ok, why = capture_window(dlg, OUT / "C4-subject-unticked.png")
        print("   photo:", ok, why, flush=True)
        dlg._profile_list.item(sub_row).setCheckState(Qt.CheckState.Checked)
        pump(app, 1200)

    # ---------------------------------------------------------------- C5
    body = text_of(dlg._view.toHtml())
    RESULT["C5_trend_complaint"] = [
        l for l in body.splitlines() if "trend graph needs" in l.lower()]
    RESULT["C5_trend_points"] = len(dlg._trend_series)
    print("C5 trend points:", RESULT["C5_trend_points"],
          "complaint:", RESULT["C5_trend_complaint"], flush=True)

    # ---------------------------------------------------------------- C6
    before = {p for p in dst.rglob("report_*.json")}
    dlg._on_generate_report(); pump(app, 2500)
    after = {p for p in dst.rglob("report_*.json")}
    added = sorted(str(p.relative_to(work)) for p in after - before)
    RESULT["C6_generated"] = added
    print("C6 generated:", added, flush=True)

    ok, why = capture_window(dlg, OUT / "C-final.png")
    print("final photo:", ok, why, flush=True)
    (OUT / "result.json").write_text(json.dumps(RESULT, indent=1),
                                     encoding="utf-8")
    dlg.close(); pump(app, 200)
    return 0


sys.exit(main())

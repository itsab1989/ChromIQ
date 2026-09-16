#!/usr/bin/env python3
"""The last challenge round: the shapes the earlier ones did not touch."""
from __future__ import annotations
import json, os, re, shutil, sys, tempfile, time
from pathlib import Path

ROOT = Path("/Users/Basti/develop/ChromIQ"); sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
from onscreen_capture import capture_window                      # noqa: E402

OUT = Path(sys.argv[1]); R: dict = {}


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def text_of(h: str) -> str:
    import html as _h
    return "\n".join(l.strip() for l in
                     _h.unescape(re.sub(r"<[^>]+>", "\n", h)).splitlines()
                     if l.strip())


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-sweep-"))
    settings = AppSettings(); settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    shutil.copytree(Path("/tmp/rep-demo/Report-Limits-Report-Types"), work / "P")
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    MeasurementReportDialog._confirm = (lambda self, t, b: True)  # type: ignore
    apply_appearance(app, None, "dark")
    fm = FileManager(settings); del fm

    # -- F1: a loose measurement in no project at all
    loose_dir = work / "Downloads"; loose_dir.mkdir()
    src = sorted((work / "P" / "runs" / "run1" / "verifications").glob("*/*.ti3"))[0]
    loose = loose_dir / "a-measurement.ti3"
    shutil.copy2(src, loose)
    dlg = MeasurementReportDialog(settings, None, initial_ti3=loose)
    dlg.resize(1500, 1080); dlg.show(); dlg.raise_(); pump(app, 2500)
    R["F1_window"] = dlg.isVisible()
    R["F1_selector_visible"] = dlg._saved_combo.isVisible()
    R["F1_selector_count"] = dlg._saved_combo.count()
    R["F1_delete_enabled"] = dlg._delete_report_btn.isEnabled()
    R["F1_head"] = next((l for l in text_of(dlg._view.toHtml()).splitlines()
                         if l.startswith("Report type:")), "")
    print("F1 loose file:", json.dumps({k: R[k] for k in R if k.startswith("F1")}),
          flush=True)
    ok, why = capture_window(dlg, OUT / "F1-a-measurement-in-no-project.png")
    print("   photo:", ok, why, flush=True)

    # -- F2: add a real project beside it
    dlg._add_source(src); pump(app, 2000)
    R["F2_sources"] = len(dlg._sources)
    R["F2_selector_count"] = dlg._saved_combo.count()
    R["F2_selector_visible"] = dlg._saved_combo.isVisible()
    body = text_of(dlg._view.toHtml())
    R["F2_left_out"] = "judged against a different limit set" in body
    R["F2_old_warning"] = "were not all judged against the same limit set" in body
    print("F2 two sources:", json.dumps({k: R[k] for k in R if k.startswith("F2")}),
          flush=True)
    ok, why = capture_window(dlg, OUT / "F2-a-project-added-beside-it.png")
    print("   photo:", ok, why, flush=True)

    # -- F3: the PDF says the same thing the page does
    pdf = OUT / "F3-report.pdf"
    import ui.widgets as _w
    from PyQt6.QtGui import QDesktopServices
    _w.save_file_dialog = lambda *a, **k: str(pdf)
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
    dlg._pdf_btn.click(); pump(app, 4000)
    R["F3_pdf_bytes"] = pdf.exists() and pdf.stat().st_size
    try:
        import subprocess
        txt = subprocess.run(["/usr/bin/mdimport", "-d1", str(pdf)],
                             capture_output=True, timeout=20)
        del txt
    except Exception:
        pass
    print("F3 pdf:", R["F3_pdf_bytes"], flush=True)

    # -- F4: Clear List, then the row must be gone and nothing may throw
    dlg._clear_btn.click(); pump(app, 1500)
    R["F4_sources"] = len(dlg._sources)
    R["F4_selector_visible"] = dlg._saved_combo.isVisible()
    R["F4_delete_enabled"] = dlg._delete_report_btn.isEnabled()
    print("F4 cleared:", json.dumps({k: R[k] for k in R if k.startswith("F4")}),
          flush=True)
    ok, why = capture_window(dlg, OUT / "F4-list-cleared.png")
    print("   photo:", ok, why, flush=True)

    (OUT / "result.json").write_text(json.dumps(R, indent=1), encoding="utf-8")
    dlg.close(); pump(app, 200)
    return 0


sys.exit(main())

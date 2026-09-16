#!/usr/bin/env python3
"""The challenge round against B8-250: assume the Saved reports row broke
something a user can see, in a REAL window."""
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-chal2-"))
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
    ti3 = sorted((work / "P" / "runs" / "run1" / "verifications").glob("*/*.ti3"))[0]
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1500, 1080); dlg.show(); dlg.raise_(); pump(app, 2500)
    print("window:", dlg.isVisible(), flush=True)
    c = dlg._saved_combo

    def shown():
        return str(dlg._report.get("_report_file") or "")

    # -- G1: pick an OLDER report of this measurement, then press Generate
    here = str(ti3.parent)
    mine = [i for i in range(c.count()) if here in c.itemData(i)[0]]
    print("G1 entries for this date:", len(mine), flush=True)
    if len(mine) > 1:
        c.setCurrentIndex(mine[-1])          # the oldest of them
        pump(app, 1500)
        R["G1_picked"] = c.currentData()[1]
        R["G1_showing_after_pick"] = shown()
        before = {p.name for p in (ti3.parent / "reports").glob("report_*.json")}
        dlg._on_generate_report()
        pump(app, 3000)
        after = {p.name for p in (ti3.parent / "reports").glob("report_*.json")}
        R["G1_written"] = sorted(after - before)
        R["G1_showing_after_generate"] = shown()
        R["G1_selector_after"] = c.currentData()[1] if c.currentData() else None
        R["G1_count_after"] = c.count()
        print("G1 picked", R["G1_picked"], "-> showing", R["G1_showing_after_pick"],
              flush=True)
        print("   generate wrote", R["G1_written"],
              "and the window now shows", R["G1_showing_after_generate"], flush=True)
        ok, why = capture_window(dlg, OUT / "G1-after-generate.png")
        print("   photo:", ok, why, flush=True)

    # -- G2: change the limit set (recalculates the run's dated reports)
    sc = dlg._set_combo
    R["G2_set_enabled"] = sc.isEnabled()
    if sc.isEnabled() and sc.count() > 1:
        was = sc.currentIndex()
        other = next(i for i in range(sc.count()) if i != was)
        picked_before = c.currentData()[1] if c.currentData() else None
        sc.setCurrentIndex(other)
        pump(app, 3000)
        R["G2_set"] = sc.currentText()
        R["G2_selector_count"] = c.count()
        R["G2_selector_kept"] = (c.currentData()[1] if c.currentData() else None)
        R["G2_was"] = picked_before
        R["G2_showing"] = shown()
        R["G2_labels"] = [c.itemText(i) for i in range(min(3, c.count()))]
        print("G2 set ->", R["G2_set"], "selector", R["G2_selector_count"],
              "kept", R["G2_selector_kept"] == picked_before, flush=True)
        for l in R["G2_labels"]:
            print("    ", l, flush=True)
        ok, why = capture_window(dlg, OUT / "G2-after-set-change.png")
        print("   photo:", ok, why, flush=True)

    # -- G3: with "Show all measurement runs" OFF
    dlg._all_runs_check.setChecked(False)
    pump(app, 1500)
    R["G3_selector_count"] = c.count()
    R["G3_delete_enabled"] = dlg._delete_report_btn.isEnabled()
    print("G3 show-all off: selector", R["G3_selector_count"],
          "delete", R["G3_delete_enabled"], flush=True)
    dlg._all_runs_check.setChecked(True)
    pump(app, 1200)

    # -- G4: the PDF still matches the page
    pdf = OUT / "G4-report.pdf"
    import ui.widgets as _w
    from PyQt6.QtGui import QDesktopServices
    _w.save_file_dialog = lambda *a, **k: str(pdf)
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
    dlg._pdf_btn.click(); pump(app, 4000)
    R["G4_pdf"] = pdf.exists() and pdf.stat().st_size
    print("G4 pdf:", R["G4_pdf"], flush=True)

    (OUT / "result.json").write_text(json.dumps(R, indent=1), encoding="utf-8")
    (OUT / "document.txt").write_text(text_of(dlg._view.toHtml()), encoding="utf-8")
    dlg.close(); pump(app, 200)
    return 0


sys.exit(main())

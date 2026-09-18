#!/usr/bin/env python3
"""B8-364 on screen: the PDF door closes while the red line is up.

Knut, 2026-09-18: *"After a setting is changed, giving the user a red text
notification that he should press Generate Report to apply the changes, then
the 'Print Report as PDF' button should be disabled until the Generate Report
button has been pressed. … So, as long as the settings for a loaded report is
untouched the PDF can be generated and printed."*

The guard that was written for it drives the dialog's own methods. This drives
the WINDOW: a real project, a real Measurement Report window, a real click on a
control, and a photograph of the greyed button with its tooltip at each step.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_b22_the_pdf_door_on_screen.py <project> <out>
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    src, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b22-pdf-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    dest = work / src.name
    shutil.copytree(src, dest)
    print(f"    project copied to {dest}", flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    MeasurementReportDialog._confirm = lambda self, *a, **k: True  # type: ignore
    apply_appearance(app, None, "dark")
    fm = FileManager(settings); del fm

    ti3 = None
    for d in sorted((dest / "runs").glob("run*/verifications/*")):
        g = sorted(d.glob("*.ti3"))
        if g:
            ti3 = g[0]
            break
    assert ti3 is not None, "no dated verification in this project"
    print(f"    opening on {ti3.relative_to(dest)}", flush=True)

    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1500, 1060)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 3500)
    print(f"    window on screen: {dlg.isVisible()}", flush=True)

    steps = []

    def state(tag: str, shot: str):
        red = bool(dlg._stale_label.isVisible())
        pdf_on = bool(dlg._pdf_btn.isEnabled())
        tip = dlg._pdf_btn.toolTip()
        line = dlg._stale_label.text()
        ok, why = capture_window(dlg, out / shot)
        print(f"    [{tag}] red line up: {red}   "
              f"Save report as PDF enabled: {pdf_on}", flush=True)
        print(f"        red line says : {line[:150]!r}", flush=True)
        print(f"        PDF tooltip   : {tip[:150]!r}", flush=True)
        print(f"        photograph    : {ok} {why}", flush=True)
        steps.append({"step": tag, "red_line_up": red, "pdf_enabled": pdf_on,
                      "red_line": line, "pdf_tooltip": tip,
                      "photo": shot, "captured": ok, "why": why})
        return red, pdf_on, tip

    state("1 as opened", "P1-as-opened.png")
    # THE USER'S OWN CLICK, on the control Knut was changing: the report type.
    combo = dlg._type_combo
    i = (combo.currentIndex() + 1) % max(1, combo.count())
    print(f"    clicking Report type: {combo.currentText()!r} -> "
          f"{combo.itemText(i)!r}", flush=True)
    combo.setCurrentIndex(i)
    pump(app, 2000)
    state("2 after changing Report type", "P2-red-line-up-pdf-greyed.png")
    # …and Generate opens it again.
    print("    clicking Generate report", flush=True)
    dlg._generate_btn.click()
    pump(app, 3500)
    state("3 after Generate report", "P3-after-generate-pdf-live.png")

    (out / "pdf-door.json").write_text(
        json.dumps({"project": str(src), "ti3": str(ti3), "steps": steps},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    dlg.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

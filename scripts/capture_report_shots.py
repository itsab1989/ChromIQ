"""Capture Measurement Report screenshots for the forum showcase.

Loads the demo profile set written by ``scripts/make_report_demo.py`` — one
printer and paper, three charts, fourteen dated measurements — into the real
Measurement Report window and grabs the shots the showcase post needs, plus the
full PDF.  Output → ~/Desktop/chromiq_report_shots/.

    python scripts/capture_report_shots.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.pop("QT_QPA_PLATFORM", None)   # force a real (onscreen) platform
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtCore import QRect  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication, QFileDialog, QFrame, QTextBrowser,
)

from scripts.capture_screens import build_app, pump  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.theme import apply_appearance  # noqa: E402

OUT = Path.home() / "Desktop" / "chromiq_report_shots"
DEMO = Path.home() / "Desktop" / "ChromIQ-Demo-PRO300"


def _save(widget, path: Path) -> None:
    pm = widget.grab()
    pm.save(str(path))
    print("  saved", path.name, pm.width(), "x", pm.height())


def _section_shot(html: str, start: str, end: "str | None", path: Path,
                  width: int = 1160) -> bool:
    """Render the report body at full height off-screen and crop one section.

    The window's own body pane is only a few hundred pixels tall, so a section
    that runs over several tables can't be shown in one shot from it. Laying the
    same HTML out at its natural height and cropping gives a clean, full-width
    picture of exactly one part of the report.
    """
    tb = QTextBrowser()
    tb.setFrameShape(QFrame.Shape.NoFrame)
    tb.setStyleSheet("QTextBrowser { background: #ffffff; border: none; }")
    tb.resize(width, 400)
    tb.setHtml(html)
    # Lay the document out at the target width so its natural height is known
    # before the widget is resized to it (the widget is never shown).
    tb.document().setTextWidth(width - 24)
    pump(250)
    height = int(tb.document().size().height()) + 40
    tb.resize(width, height)
    tb.document().setTextWidth(width - 24)
    pump(250)

    def y_of(text: str) -> "int | None":
        cur = tb.document().find(text)
        return None if cur.isNull() else tb.cursorRect(cur).top()

    y0 = y_of(start)
    if y0 is None:
        print("  section not found:", start)
        return False
    y1 = (y_of(end) if end else None) or height
    y0, y1 = max(0, y0 - 26), min(height, max(y1, y0 + 120))
    pm = tb.grab()
    dpr = pm.devicePixelRatio()
    crop = pm.copy(QRect(0, int(y0 * dpr), int(width * dpr),
                         int((y1 - y0) * dpr)))
    crop.setDevicePixelRatio(dpr)
    crop.save(str(path))
    print("  saved", path.name, crop.width(), "x", crop.height())
    return True


def main() -> int:
    if not DEMO.is_dir():
        print("demo set missing:", DEMO)
        print("run scripts/make_report_demo.py first")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    app = build_app()
    settings = AppSettings()
    apply_appearance(app, None, "light")     # clean light shots for the forum

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(settings)
    dlg.resize(1180, 1420)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(700)

    # One .ti3 per profile — the window then gathers that profile's whole
    # history by itself, exactly as it does for a user.
    for proj in sorted(p for p in DEMO.iterdir() if p.is_dir()):
        ti3 = next(iter(sorted((proj / "runs" / "run1").glob("*.ti3"))), None)
        if ti3 is None:
            continue
        try:
            dlg._append_source(ti3, origin=ti3)
            print("  loaded", proj.name)
        except Exception as exc:  # noqa: BLE001
            print("  load failed", proj.name, exc)
    if not dlg._sources:
        print("nothing loaded")
        return 1
    dlg._report = dlg._sources[0]["runs"][-1]
    # Reproducible shots: the published default limit set (#182), whatever
    # this machine has set.
    dlg._sync_limit_controls()
    _i = dlg._set_combo.findData("chromiq_default")
    if _i >= 0:
        dlg._set_combo.setCurrentIndex(_i)
        dlg._on_set_chosen(_i)
    dlg._all_runs_check.setChecked(True)
    dlg._rebuild_from_sources()
    pump(1500)

    _save(dlg, OUT / "01_window_overview.png")

    # Each trend tab on its own — the charts are the headline of the feature.
    for i, name in enumerate(("02_trend_accuracy", "03_trend_paper_white",
                              "04_trend_black", "05_trend_corners")):
        dlg._trend_tabs.setCurrentIndex(i)
        pump(500)
        _save(dlg._trend_tabs, OUT / f"{name}.png")
    dlg._trend_tabs.setCurrentIndex(0)
    pump(300)

    # Sections of the report body, cropped out of a full-height layout.
    runs = dlg._runs_for_report()
    body = dlg._report_body_html(runs, for_pdf=False)
    _section_shot(body, "Report Scope", "How to read this report",
                  OUT / "06_report_scope.png")
    _section_shot(body, "Report Results", "Overview of Measurement Metrics",
                  OUT / "07_results_grid.png")
    _section_shot(body, "Overview of Measurement Metrics", None,
                  OUT / "08_overview_metrics.png")

    # One run in full detail — cube corners and worst patches, with swatches.
    dlg._detail_check.setChecked(True)
    pump(400)
    one = dlg._report_body_html([runs[-1]], for_pdf=False)
    _section_shot(one, "Cube corners (the eight ink extremes)", None,
                  OUT / "09_detail_corners_worst_patches.png")

    # The PDF — the whole report, all fourteen runs, charts included.
    pdf_path = OUT / "ChromIQ_Measurement_Report_demo.pdf"
    QFileDialog.getSaveFileName = staticmethod(  # type: ignore[assignment]
        lambda *a, **k: (str(pdf_path), "PDF (*.pdf)"))
    try:
        from PyQt6.QtGui import QDesktopServices
        QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)  # type: ignore
        dlg._export_pdf()
        print("  saved", pdf_path.name)
    except Exception as exc:  # noqa: BLE001
        print("  pdf export failed:", exc)

    print("DONE →", OUT)
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

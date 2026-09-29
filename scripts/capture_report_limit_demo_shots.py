"""Open the limit demo projects in the REAL Measurement Report window and
photograph a crossed limit and the same row recovered on a later date (#182).

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-demo.ini
    .venv/bin/python scripts/capture_report_limit_demo_shots.py [projects folder]

Output goes to ~/Desktop/ChromIQ-beta3-proof/report-demo-projects/.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.pop("QT_QPA_PLATFORM", None)      # a real, on-screen platform
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtCore import QRect                                   # noqa: E402
from PyQt6.QtWidgets import QFrame, QTextBrowser                 # noqa: E402

from core.settings import AppSettings                            # noqa: E402
from scripts.capture_screens import build_app, pump              # noqa: E402
from ui.theme import apply_appearance                            # noqa: E402

OUT = Path.home() / "Desktop" / "ChromIQ-beta3-proof" / "report-demo-projects"
DEFAULT = Path(__file__).resolve().parents[1] / "demo-projects" / \
    "ChromIQ-Report-Limit-Demos"


def _save(widget, path: Path) -> None:
    pm = widget.grab()
    pm.save(str(path))
    print("  saved", path.name, pm.width(), "x", pm.height())


def _section(html: str, start: str, end: "str | None", path: Path,
             width: int = 1200) -> bool:
    tb = QTextBrowser()
    tb.setFrameShape(QFrame.Shape.NoFrame)
    tb.setStyleSheet("QTextBrowser { background: #ffffff; border: none; }")
    tb.resize(width, 400)
    tb.setHtml(html)
    tb.document().setTextWidth(width - 24)
    pump(250)
    height = int(tb.document().size().height()) + 40
    tb.resize(width, height)
    tb.document().setTextWidth(width - 24)
    pump(250)

    def y_of(text):
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


def main(argv=None) -> int:
    base = Path((argv or sys.argv[1:] or [str(DEFAULT)])[0]).resolve()
    if not base.is_dir():
        print("projects folder missing:", base)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    app = build_app()
    settings = AppSettings()
    apply_appearance(app, None, "light")

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog

    series = base / "Report-Limits-Threshold-Series" / "runs" / "run1"
    vdirs = sorted((series / "verifications").glob("20*_*"))
    if not vdirs:
        print("no dated verifications under", series)
        return 1

    dlg = MeasurementReportDialog(settings)
    dlg.resize(1200, 1440)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(700)
    for v in vdirs:
        ti3 = next(iter(sorted(v.glob("*.ti3"))), None)
        if ti3 is not None:
            dlg._append_source(ti3, origin=ti3)
    if not dlg._sources:
        print("nothing loaded")
        return 1
    dlg._report = dlg._sources[0]["runs"][-1]
    dlg._all_runs_check.setChecked(True)
    dlg._rebuild_from_sources()
    pump(1800)
    _save(dlg, OUT / "01_window_eleven_dates.png")

    runs = dlg._runs_for_report()
    body = dlg._report_body_html(runs, for_pdf=False)
    _section(body, "Report Results", "Overview of Measurement Metrics",
             OUT / "02_results_all_dates.png")
    _section(body, "Overview of Measurement Metrics", None,
             OUT / "03_metrics_all_dates.png")

    # The pair that makes the point: the date that crosses, and the next date
    # on which the same row is back inside its limit.
    by_date = {}
    for r in runs:
        by_date[str(r.get("created", ""))[:10]] = r
    for tag, day in (("04_crossed_2026-01-19", "2026-01-19"),
                     ("05_recovered_2026-02-02", "2026-02-02")):
        r = by_date.get(day)
        if r is None:
            print("  no run for", day)
            continue
        one = dlg._report_body_html([r], for_pdf=False)
        _section(one, "Report Results", "Overview of Measurement Metrics",
                 OUT / f"{tag}_results.png")
        _section(one, "Overview of Measurement Metrics", None,
                 OUT / f"{tag}_metrics.png")

    print("DONE ->", OUT)
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

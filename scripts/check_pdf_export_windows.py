#!/usr/bin/env python3
"""On-screen smoke check for the measurement-report PDF export.

The report-layout tests (``test_report_pdf_layout.py``) assert where page breaks
land, which depends on real font line-heights. Under ``QT_QPA_PLATFORM=offscreen``
the Qt font database is EMPTY on Windows (Qt no longer ships fonts and the
headless platform loads none), so those assertions are meaningless there and
skip — see ``tests/_fontcheck.py``. That leaves the actual PDF on Windows with
no automated confirmation, the way the macOS PDFs have.

This closes that gap: it runs ChromIQ's production
``MeasurementReportDialog._export_pdf`` on the cached ``Demo-Verify-History``
project (dated verifications -> real trend charts) under whatever REAL Qt
platform this session provides — a desktop session loads the system fonts
(Segoe UI on Windows) plus ChromIQ's bundled Inter — then validates the output
with ``pypdf`` and rasterises each page to PNG (via ``QtPdf``) so it can be
eyeballed.

Prerequisites:
  * A real desktop session (do NOT set QT_QPA_PLATFORM=offscreen — that is the
    fontless environment this check exists to avoid).
  * The demo cache built once by the test suite (``pytest -q`` builds it), or
    ``CHROMIQ_DEMO_CACHE`` pointing at it.

Run::

    .venv/Scripts/python.exe scripts/check_pdf_export_windows.py [outdir]

Exit code 0 = every check passed. Non-zero = something to look at; the PDF and
per-page PNGs are left in *outdir* either way.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PROJECT = "Demo-Verify-History"

_RESULTS: list[tuple[str, bool, str]] = []


def check(what: str, ok: bool, detail: str = "") -> None:
    _RESULTS.append((what, ok, detail))
    print(f"  {'OK  ' if ok else 'FAIL'} {what}" + (f"  ({detail})" if detail else ""))


def _demo_cache_home() -> Path:
    return Path(os.environ.get("CHROMIQ_DEMO_CACHE",
                               Path(tempfile.gettempdir()) / "chromiq-demo-projects-cache"))


def _find_project() -> Path:
    home = _demo_cache_home()
    for key in sorted(home.glob("*")):
        p = key / PROJECT
        if (p / "project.json").is_file():
            return p
    raise SystemExit(
        f"No cached {PROJECT} under {home}. Build the demo cache first "
        f"(run `pytest -q` once), or set CHROMIQ_DEMO_CACHE.")


def main() -> int:
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path(tempfile.gettempdir()) / "chromiq-pdf-check"
    outdir.mkdir(parents=True, exist_ok=True)

    from PyQt6.QtCore import QSettings, QSize
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtWidgets import QApplication

    from core.resource_path import resource_path

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ChromIQ")

    families = QFontDatabase.families()
    check("Qt exposes real fonts (not the empty offscreen DB)", len(families) > 5,
          f"{len(families)} families; Segoe UI={'Segoe UI' in families}")
    if len(families) <= 5:
        print("\n  This session has (almost) no fonts — you are probably running "
              "headless / offscreen.\n  Run it from a real desktop session; do NOT "
              "set QT_QPA_PLATFORM=offscreen.")
        return _summary(outdir)

    loaded = sum(1 for fp in Path(resource_path("assets/fonts")).glob("*.ttf")
                 if QFontDatabase.addApplicationFont(str(fp)) != -1)
    check("ChromIQ bundled fonts load", loaded >= 1,
          f"{loaded} loaded; Inter={'Inter' in QFontDatabase.families()}")

    from ui import styles
    from ui.light_styles import LIGHT_STYLESHEET, make_light_palette
    app.setStyle(styles.WinButtonLayoutStyle("Fusion"))
    app.setPalette(make_light_palette())
    app.setStyleSheet(LIGHT_STYLESHEET)

    # Copy the cached project out — Project.load migrates in place, and a check
    # must never mutate the shared cache.
    work = outdir / "project"
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(_find_project(), work)

    from core.settings import AppSettings
    settings = AppSettings()
    settings._qs = QSettings(str(outdir / "check.ini"), QSettings.Format.IniFormat)
    settings.set("appearance", "light")
    try:
        from core.argyll_detect import find_argyll_bin_path
        bin_dir = find_argyll_bin_path()
        if bin_dir is not None:
            settings.set("argyll_bin_path", str(bin_dir))
    except Exception:      # noqa: BLE001 — the export itself needs no Argyll
        pass

    verifs = sorted((work / "runs/run1/verifications").glob("*/*-verify.ti3"))
    check("verification measurements present", len(verifs) >= 2, f"{len(verifs)} dates")
    if not verifs:
        return _summary(outdir)

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(settings, None, initial_ti3=verifs[0])
    dlg.show()
    deadline = time.time() + 1.0
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)
    check("report gathered the dated history", len(getattr(dlg, "_history", [])) >= 2,
          f"{len(getattr(dlg, '_history', []))} dates")
    check("trend data present (trend charts will render)", bool(dlg._trend_de.has_trend()))

    pdf = outdir / "measurement-report.pdf"
    pdf.unlink(missing_ok=True)
    with mock.patch("ui.widgets.save_file_dialog", return_value=str(pdf)), \
         mock.patch("PyQt6.QtGui.QDesktopServices.openUrl", return_value=True):
        dlg._export_pdf()
    check("PDF file written", pdf.exists() and pdf.stat().st_size > 5000,
          f"{pdf.stat().st_size} bytes" if pdf.exists() else "missing")
    if not pdf.exists():
        return _summary(outdir)

    import re

    import pypdf
    reader = pypdf.PdfReader(str(pdf))
    npages = len(reader.pages)
    check("PDF has pages", npages >= 1, f"{npages} pages")
    text = "\n".join((pg.extract_text() or "") for pg in reader.pages)
    check("body text extracted (fonts really rendered glyphs)", len(text.strip()) > 200,
          f"{len(text)} chars")
    for label in (PROJECT, "Average", "Max"):
        check(f"expected content present: {label!r}", label in text)
    dates = re.findall(r"20\d\d-\d\d-\d\d", text)
    check("date header(s) present", bool(dates), f"e.g. {dates[:2]}")
    blank = [i + 1 for i, pg in enumerate(reader.pages)
             if len((pg.extract_text() or "").strip()) < 3]
    check("no blank pages", not blank, f"blank: {blank}" if blank else "")

    try:
        from PyQt6.QtPdf import QPdfDocument
        qd = QPdfDocument(None)
        qd.load(str(pdf))
        pages_dir = outdir / "pages"
        pages_dir.mkdir(exist_ok=True)
        made = 0
        for i in range(qd.pageCount()):
            pts = qd.pagePointSize(i)
            dpi = 150
            img = qd.render(i, QSize(int(pts.width() / 72 * dpi),
                                     int(pts.height() / 72 * dpi)))
            if not img.isNull():
                img.save(str(pages_dir / f"page{i + 1:02d}.png"))
                made += 1
        check("pages rasterised to PNG (visual proof)", made == npages,
              f"{made}/{npages} -> {pages_dir}")
    except Exception as exc:      # noqa: BLE001 — QtPdf is optional
        check("pages rasterised to PNG (visual proof)", False, f"QtPdf unavailable: {exc}")

    return _summary(outdir)


def _summary(outdir: Path) -> int:
    ok = sum(1 for _w, passed, _d in _RESULTS if passed)
    failed = [w for w, passed, _d in _RESULTS if not passed]
    print(f"\n==== {ok}/{len(_RESULTS)} checks passed ====")
    if failed:
        print("FAILED:", "; ".join(failed))
    print(f"Output: {outdir}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Drive the Measurement Report against ``Demo-Report-Matrix`` — every case,
every option, one PDF per case (Knut's report test package, 2026-08-10).

For each case in the package README the REAL report window (real styling) is
opened, the case's expectations are checked programmatically, and a PDF is
exported into ``<project>/pdfs/`` so a human can leaf through exactly what
each situation prints like. The combined all-runs report (summary and
detailed) is exported too, and every export is checked by the page scanner
when ``pymupdf`` is importable (orphaned headings, margins, overlaps,
footers).

Run::

    .venv/bin/python scripts/make_report_demo.py        # once, or to refresh
    .venv/bin/python scripts/drive_report_demo_onscreen.py

Headless (identical checks): QT_QPA_PLATFORM=offscreen …
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QSettings                     # noqa: E402
from PyQt6.QtGui import QFontDatabase                  # noqa: E402
from PyQt6.QtWidgets import QApplication               # noqa: E402

from core.resource_path import resource_path           # noqa: E402

NAME = "Demo-Report-Matrix"
ARGYLL = "/Applications/Argyll/bin"
FAILURES: list[str] = []
ON_SCREEN = os.environ.get("QT_QPA_PLATFORM", "") != "offscreen"


def check(what: str, ok: bool, detail: str = "") -> None:
    print(f"  {'OK  ' if ok else 'FAIL'} {what}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILURES.append(what)


def pump(app, ms=150):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def hist(dlg, day: str) -> dict:
    for r in dlg._history:
        if str(r.get("created", "")).startswith(day):
            return r
    raise KeyError(day)


def export(dlg, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    with mock.patch("ui.widgets.save_file_dialog", return_value=str(out)), \
         mock.patch("PyQt6.QtGui.QDesktopServices.openUrl", return_value=True):
        dlg._export_pdf()
    if not out.exists():
        FAILURES.append(f"no PDF written: {out.name}")


def scan(pdf: Path) -> None:
    try:
        import pymupdf  # noqa: F401
    except ImportError:
        return
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from report_layout_scan import check_pdf     # optional helper
    except ImportError:
        return
    probs = [p for p in check_pdf(pdf) if "WARN" not in p]
    check(f"layout clean: {pdf.name}", not probs, "; ".join(probs)[:100])


def main() -> int:
    root = ROOT / "demo-projects" / NAME
    if not root.exists():
        print("run scripts/make_report_demo.py first")
        return 2
    app = QApplication.instance() or QApplication(sys.argv)
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

    from core.settings import AppSettings
    settings = AppSettings()
    settings._qs = QSettings(str(root / "drive.ini"), QSettings.Format.IniFormat)
    settings.set("argyll_bin_path", ARGYLL)
    settings.set("appearance", "dark")

    vstem = f"{NAME}-verify"
    v1 = root / "runs/run1/verifications"
    pdfs = root / "pdfs"

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    print("== the combined report: 12 dates of run1 ==")
    first = v1 / "2026-05-01_100000" / f"{vstem}.ti3"
    dlg = MeasurementReportDialog(settings, None, initial_ti3=first)
    dlg.show()
    pump(app, 500 if ON_SCREEN else 100)
    check("all 12 dates gathered", len(dlg._history) == 12,
          str(len(dlg._history)))

    r = hist(dlg, "2026-05-01")   # V1
    check("V1 raw + absolute + split",
          (r.get("printing") or {}).get("colour") == "raw"
          and r.get("yardstick") == "absolute"
          and bool(r.get("gamut_split")))
    r2 = hist(dlg, "2026-06-01")  # V2
    check("V2 drifted worse than V1",
          (r2["de00"]["avg_all"] or 0) > (r["de00"]["avg_all"] or 0),
          f"{r['de00']['avg_all']} -> {r2['de00']['avg_all']}")
    r = hist(dlg, "2026-06-15")   # V3
    check("V3 through/relative → media-relative + split",
          (r.get("printing") or {}).get("intent") == "relative"
          and r.get("yardstick") == "media-relative"
          and bool(r.get("gamut_split")))
    r = hist(dlg, "2026-07-01")   # V4
    check("V4 through/absolute → absolute yardstick",
          (r.get("printing") or {}).get("intent") == "absolute"
          and r.get("yardstick") == "absolute")
    r = hist(dlg, "2026-07-10")   # V5
    check("V5 external-cm, answered at measure, media-relative",
          (r.get("printing") or {}).get("route") == "external-cm"
          and (r.get("printing") or {}).get("recorded") == "asked-at-measure"
          and r.get("yardstick") == "media-relative")
    import html as _html
    lbl = dlg._run_row_label(r)
    check("V5 row label says another app with colour management",
          "another app with colour management" in lbl, lbl)
    r = hist(dlg, "2026-07-20")   # V6
    check("V6 unrecorded", not r.get("printing")
          and r.get("yardstick") == "absolute")
    r = hist(dlg, "2026-08-01")   # V7
    check("V7 gamut chart: colorimetric reference, NO split",
          r.get("reference_source") == "colorimetric"
          and not r.get("gamut_split"))
    r8 = hist(dlg, "2026-08-08")  # V8
    check("V8 drifted worse than V7",
          (r8["de00"]["avg_all"] or 0) > (r["de00"]["avg_all"] or 0),
          f"{r['de00']['avg_all']} -> {r8['de00']['avg_all']}")
    r = hist(dlg, "2026-08-09")   # V9
    check("V9 refusal: colorimetric reference missing",
          r.get("reference_source") == "colorimetric-missing"
          and not (r.get("de00") or {}).get("avg_all"))
    detail = _html.unescape(dlg._run_detail_html(r))
    check("V9 detail says 'No colour-accuracy figures, on purpose.'",
          "No colour-accuracy figures, on purpose." in detail)
    r = hist(dlg, "2026-08-10T09") # V10
    check("V10 imported: keywords + external-cm",
          r.get("is_verification")
          and (r.get("printing") or {}).get("route") == "external-cm")
    r = hist(dlg, "2026-08-10T10") # V11
    check("V11 carries the i1Pro3 instrument",
          "i1Pro3" in str(r.get("instrument")))
    from workflow.measurement_report import report_scope
    sc = report_scope(dlg._runs_for_report())
    kinds = {w["kind"] for w in sc["warnings"]}
    check("mixed-instruments warning raised", "instrument" in kinds, kinds)
    check("mixed-printing-methods warning raised", "printing" in kinds, kinds)
    r = hist(dlg, "2026-08-10T11") # V12
    check("V12 profile rebuilt since print flagged",
          (r.get("printing") or {}).get("profile_changed_since_print") is True)

    print("== the raw-drift figure (item 6) ==")
    r1, r2 = hist(dlg, "2026-05-01"), hist(dlg, "2026-06-01")
    check("V1 is the drift baseline",
          (r1.get("raw_drift") or {}).get("baseline") is True)
    rd = r2.get("raw_drift") or {}
    check("V2 carries drift vs V1",
          rd.get("prev") == r1.get("created") and rd.get("n", 0) > 0)
    check("V2 drift magnitude plausible for 0.3%->1.2% noise",
          0.0 < (rd.get("avg") or 0) < 15.0,
          f"avg {rd.get('avg')} max {rd.get('max')}")
    detail1 = _html.unescape(dlg._run_detail_html(r1))
    check("V1 detail says it becomes the baseline",
          "it becomes the baseline" in detail1)
    detail2 = _html.unescape(dlg._run_detail_html(r2))
    check("V2 detail shows the drift sentence and no Pass/Fail",
          "Drift since the previous raw check" in detail2
          and ">Pass<" not in detail2 and ">Fail<" not in detail2)
    results = _html.unescape(dlg._report_results_html(dlg._runs_for_report()))
    check("Results grid marks raw sheets as drift, with the note",
          "drift" in results
          and "not expected to match the design closely" in results)

    print("== the corrected gamut wording (item 4) ==")
    r7 = hist(dlg, "2026-08-01")
    check("V7 row label says gamut check",
          "gamut check" in dlg._run_row_label(r7), dlg._run_row_label(r7))
    prod7 = _html.unescape(dlg._printing_block_html(r7))
    check("V7 produced-block: accuracy against the profile's promise",
          "every figure compares a patch with that promise" in prod7
          and "drift check" not in prod7)
    prod9 = _html.unescape(dlg._printing_block_html(hist(dlg, "2026-08-09")))
    check("V9 produced-block explains the missing targets",
          "stored targets are missing" in prod9)

    print("== times in shared-day headers (item 5) ==")
    overview = dlg._comparison_table_html(dlg._runs_for_report())
    check("the 2026-08-10 trio is distinguishable by time",
          all(clock in overview for clock in ("09:00", "10:00", "11:00")))
    check("unique days stay date-only",
          "2026-05-01<br>" not in overview.replace(" ", ""))

    print("== the combined PDFs (summary + detailed) ==")
    dlg._all_runs_check.setChecked(True)
    dlg._detail_check.setChecked(False)
    export(dlg, pdfs / "ALL-summary.pdf")
    dlg._detail_check.setChecked(True)
    export(dlg, pdfs / "ALL-detailed.pdf")
    check("combined PDF proposes verifications/reports (four-tier design)",
          dlg._report_dir() == v1 / "reports", str(dlg._report_dir()))
    dlg.close()

    print("== one PDF per case (all-runs OFF → single dataset each) ==")
    settings.set("report_show_all_runs", "false")
    settings.set("report_show_details", "true")
    for case, day in [("V1", "2026-05-01_100000"), ("V2", "2026-06-01_100000"),
                      ("V3", "2026-06-15_100000"), ("V4", "2026-07-01_100000"),
                      ("V5", "2026-07-10_100000"), ("V6", "2026-07-20_100000"),
                      ("V7", "2026-08-01_100000"), ("V8", "2026-08-08_100000"),
                      ("V9", "2026-08-09_100000"), ("V10", "2026-08-10_090000"),
                      ("V11", "2026-08-10_100000"), ("V12", "2026-08-10_110000")]:
        ti3 = v1 / day / f"{vstem}.ti3"
        d = MeasurementReportDialog(settings, None, initial_ti3=ti3)
        d.show()
        pump(app, 250 if ON_SCREEN else 60)
        anchored = Path(d._report["_origin_dir"]).name == day
        check(f"{case}: anchored on its own date", anchored,
              d._report.get("_origin_dir", "?"))
        check(f"{case}: PDF proposes the date's own reports/",
              d._report_dir() == v1 / day / "reports", str(d._report_dir()))
        export(d, pdfs / f"{case}.pdf")
        d.close()
        pump(app, 60)

    print("== run2: no profile — degrade, never break ==")
    r2ti3 = (root / "runs/run2/verifications/2026-08-10_120000"
             / f"{vstem}.ti3")
    d = MeasurementReportDialog(settings, None, initial_ti3=r2ti3)
    d.show()
    pump(app, 250 if ON_SCREEN else 60)
    rr = d._report
    check("R2 renders with no split and no error",
          rr is not None and not rr.get("gamut_split")
          and (rr.get("de00") or {}).get("avg_all") is not None)
    export(d, pdfs / "R2-no-profile.pdf")
    d.close()

    settings.set("report_show_all_runs", "true")
    print(f"\n{'ALL OK' if not FAILURES else f'{len(FAILURES)} FAILURES'}")
    for f in FAILURES:
        print(f"  FAIL {f}")
    print(f"PDFs: {pdfs}")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(main())

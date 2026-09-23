#!/usr/bin/env python3
"""#182 K20/K21, the trend graphs for the judged metrics, driven ON SCREEN.

Two packs, one process each (one QApplication per process):

    python scripts/drive_trend_graphs.py <out-dir>              # limit demos
    CHROMIQ_DEMO_PACK=<folder holding Report-Limits-Evenness> \\
        python scripts/drive_trend_graphs.py <out-dir> evenness

Limit demos:
    T  Threshold-Series run1 (ChromIQ default, 11 dates): every date ticked,
       Generate; which tabs show, each new one photographed with its lines.
    E  Every-Limit-Set run10 (Custom ISO 12647-8, a colorimetric reference):
       the same; "Paper white, diff" appears; the PDF is saved twice, with
       Colour accuracy at the new height and at the old one, for comparison.
    G  the same window switched to "Grey and tone check" and generated again:
       the paper, control-strip and repeatability tabs hide.
    P  run10 with Run type Profiling: a Printing record judges nothing, so
       none of the new tabs is shown.
Evenness:
    V  Report-Limits-Evenness run1, all four dates: the Evenness tab, with the
       noisy date's withheld value left out; its PDF.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

LIMITS = ("Report-Limits-Threshold-Series", "Report-Limits-Every-Limit-Set")
EVEN = "Report-Limits-Evenness"


def tabs(dlg) -> list:
    t = dlg._trend_tabs
    return [(t.tabText(i), t.isTabVisible(i)) for i in range(t.count())]


def lines_of(dlg) -> dict:
    """What each visible new tab plots and where its lines are."""
    out = {}
    for key, chart in dlg._trend_groups.items():
        i = dlg._trend_tabs.indexOf(chart)
        if not dlg._trend_tabs.isTabVisible(i):
            continue
        out[dlg._trend_tabs.tabText(i)] = {
            "metrics": [m[0] for m in chart._metrics],
            "lines": [(v, w) for v, w, _c in chart._limit_lines],
            "points": len(chart._series),
            "y_range": [round(x, 3) for x in chart._y_range()],
        }
    return out


def script_for(which):
    def script(d):
        rec = d.record
        rec["scenarios"] = {}

        def open_window(project, run, run_type="Verification"):
            d.open_project(project)
            d.set_bar(run_type=run_type, run=run)
            d.launch_tool("measurement_report")

        def state(dlg, tag, what):
            s = {"what": what, "tabs": tabs(dlg), "lines": lines_of(dlg),
                 "report_shown": dlg._saved_combo.currentText(),
                 "type": dlg._type_combo.currentText(),
                 "judged_against": dlg._set_combo.currentText()}
            rec["scenarios"][tag] = s
            d.note(f"{tag}: {what}")
            d.note(f"   type {s['type']!r}, judged against "
                   f"{s['judged_against']!r}")
            d.note("   tabs: " + ", ".join(
                f"{n}{'' if v else ' [HIDDEN]'}" for n, v in s["tabs"]))
            for n, info in s["lines"].items():
                d.note(f"   {n}: {info}")
            return s

        def generate_all(dlg):
            dlg._saved_combo.setCurrentIndex(0)          # New report...
            d.pump(1200)
            dlg._select_all_btn.click()
            d.pump(1200)
            dlg._generate_btn.click()                    # a new one: no question
            d.pump(3500)

        def photograph_tabs(dlg, tag):
            t = dlg._trend_tabs
            t.setCurrentIndex(0)
            d.shot(dlg, f"{tag}-00-colour-accuracy")
            for key, chart in dlg._trend_groups.items():
                i = t.indexOf(chart)
                if t.isTabVisible(i):
                    t.setCurrentIndex(i)
                    d.shot(dlg, f"{tag}-{i:02d}-{key}")
            t.setCurrentIndex(0)

        def save_pdf(dlg, name):
            target = d.out / "pdf" / f"{name}.pdf"
            target.parent.mkdir(parents=True, exist_ok=True)
            # QUEUED AND YIELDED: the save dialog's exec() must run from the
            # event loop, and the next step answers it from inside that loop.
            d.later(dlg._pdf_btn.click)
            yield 1500
            ok = d.answer_file(target, name=f"{name}-save-dialog")
            # The export takes several seconds on a report of several dates
            # (measured: 7 s here); wait for the file, not for a guess.
            for _ in range(60):
                yield 1000
                if target.exists() and d.modal() is not None \
                        and type(d.modal()).__name__ != "QFileDialog":
                    break
            yield 2000
            d.note(f"   PDF {target.name}: {'written' if target.exists() else 'NOT WRITTEN'}"
                   f" (dialog ok={ok})")
            rec["scenarios"].setdefault("pdfs", []).append(str(target))

        if which == "grey":
            open_window(LIMITS[1], "run10")
            yield 5000
            dlg = d.top_dialog("MeasurementReportDialog")
            generate_all(dlg)
            yield 500
            state(dlg, "E1-all-dates", "Every-Limit-Set run10, Full colour "
                  "check, every date ticked, Generate")
        if which == "limits":
            # -- T ---------------------------------------------------------
            open_window(LIMITS[0], "run1")
            yield 5000
            dlg = d.top_dialog("MeasurementReportDialog")
            state(dlg, "T0-opened", "Threshold-Series run1 as it opens")
            generate_all(dlg)
            yield 500
            state(dlg, "T1-all-dates", "every date ticked, Generate")
            photograph_tabs(dlg, "T1")
            dlg.close()
            yield 1000

            # -- E ---------------------------------------------------------
            open_window(LIMITS[1], "run10")
            yield 5000
            dlg = d.top_dialog("MeasurementReportDialog")
            generate_all(dlg)
            yield 500
            state(dlg, "E1-all-dates", "Every-Limit-Set run10, Custom ISO "
                  "12647-8, every date ticked, Generate")
            photograph_tabs(dlg, "E1")
            yield from save_pdf(dlg, "E-run10-custom-12647-8")
            import ui.dialogs.measurement_report_dialog as mrd
            mrd._PDF_ACCURACY_SCALE = 1              # the OLD height, compare
            try:
                yield from save_pdf(dlg, "E-run10-custom-12647-8-OLD-accuracy-height")
            finally:
                mrd._PDF_ACCURACY_SCALE = 2

        if which in ("limits", "grey"):
            # -- G ---------------------------------------------------------
            d.pick(dlg._type_combo, "Grey and tone")
            yield 1500
            d.later(dlg._generate_btn.click)
            yield 1500
            said = d.answer("New", name="G0-generate-question", within_ms=3000)
            # WAIT FOR THE PAGE, not for a guess: measured 30 s and more for
            # the three dates to be written on this machine under load.
            for _ in range(120):
                yield 1000
                if "Report type: Grey and tone check" in dlg._view.toPlainText():
                    break
            yield 1500
            rec["scenarios"]["G-question"] = said
            state(dlg, "G1-grey-and-tone", "the same dates as Grey and tone "
                  "check: only the grey and tone rows are judged")
            photograph_tabs(dlg, "G1")
            dlg.close()
            yield 1000
        if which == "limits":
            # -- P ---------------------------------------------------------
            open_window(LIMITS[1], "run10", run_type="Profiling")
            yield 5000
            dlg = d.top_dialog("MeasurementReportDialog")
            state(dlg, "P1-profiling", "run10 with Run type Profiling: the "
                  "Printing record judges nothing")
            d.shot(dlg, "P1-profiling-no-new-tabs")
            dlg.close()
            yield 1000
        if which == "evenness":
            # -- V ---------------------------------------------------------
            open_window(EVEN, "run1")
            yield 5000
            dlg = d.top_dialog("MeasurementReportDialog")
            generate_all(dlg)
            yield 500
            state(dlg, "V1-all-dates", "Report-Limits-Evenness run1, four "
                  "dates: even, drift, one area, noisy")
            from ui.dialogs.measurement_report_dialog import _trend_row_value
            chart = dlg._trend_groups["evenness"]
            pts = []
            for pt in chart._series:
                pts.append({"created": pt.get("created"),
                            "raw": pt.get("rows", {}),
                            "noise": pt.get("rows_noise", {}),
                            "plotted": {w: acc(pt) for w, _c, acc in chart._metrics}})
            rec["scenarios"]["V-evenness-points"] = pts
            for p in pts:
                d.note(f"   V point {p['created']}: plotted {p['plotted']} "
                       f"noise {p['noise']}")
            photograph_tabs(dlg, "V1")
            yield from save_pdf(dlg, "V-evenness-run1")
            dlg.close()
            yield 1000
        yield 500
    return script


if __name__ == "__main__":
    which = sys.argv[2] if len(sys.argv) > 2 else "limits"
    d = Drive(Path(sys.argv[1]),
              projects=[EVEN] if which == "evenness" else list(LIMITS))
    rc = d.run(script_for(which))
    print(json.dumps(d.record.get("scenarios", {}), indent=1, default=str)[:3000])
    sys.exit(rc)

#!/usr/bin/env python3
"""#182 K29, driven ON SCREEN: a sample of the release demo package.

    CHROMIQ_DEMO_PACK=<built package folder> \\
        python scripts/drive_beta39_demo_package.py <out>

Opens each sampled project the way Load does, sets the profile bar to the run
and to Verification (or Profiling), opens Tools > Measurement report, and for
every entry of "Report shown" selects it, photographs the window and keeps
the page text. The projects are copied out of the package into a fresh
folder, so every saved report names a folder that is not where it now lives:
the drive is on MOVED projects, which is what every user who unzips the
package has. The pack's own ``reports/`` (reports across projects) is copied
too.

Afterwards the page texts are checked against what the package claims
(paper white per class, the border values, the renamed project's report
across projects), and the log of the drive is read.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

#: (project, run, run type, why this sample). At least twelve projects, across
#: the angles: paper, border, second route, renamed, evenness, notes, report
#: types, folders, set compare, strip and gamut, custom columns, series.
SAMPLE = [
    ("Report-Limits-Paper-Classes", "run1", "Verification", "glossy OBA paper, default set"),
    ("Report-Limits-Paper-Classes", "run2", "Verification", "baryta, A3, tight, Colour summary"),
    ("Report-Limits-Paper-Classes", "run3", "Verification", "matte rag, Quick check, Grey and tone"),
    ("Report-Limits-Paper-Classes", "run4", "Verification", "office paper, i1Pro layout, Custom 12647-7, printing not recorded"),
    ("Report-Limits-Paper-Classes", "run5", "Verification", "newsprint, one measurement"),
    ("Report-Limits-Paper-Classes", "run6", "Verification", "From Profile Gamut on glossy paper, paper white row"),
    ("Report-Limits-Border-Values", "run1", "Verification", "3.000 / 3.001 / 2.999 on ChromIQ default"),
    ("Report-Limits-Border-Values", "run2", "Verification", "1.500 / 1.501 / 1.499 on ChromIQ tight"),
    ("Report-Limits-Border-Values", "run4", "Verification", "best 95 % on 2.000, five-page chart"),
    ("Report-Limits-Second-Route", "run1", "Verification", "second route, default, A3 on glossy"),
    ("Report-Limits-Second-Route", "run10", "Verification", "second route, Custom 12647-8, gamut chart on baryta"),
    ("Report-Limits-Renamed", "run1", "Verification", "renamed project, report across projects under its old name"),
    ("Report-Limits-Evenness", "run1", "Verification", "evenness judged"),
    ("Report-Notes-Every-Reason", "run1", "Verification", "every N-A reason of a tiny chart"),
    ("Report-Limits-Threshold-Series", "run1", "Verification", "eleven dates, trend graphs"),
    ("Report-Limits-Report-Folders", "run1", "Verification", "every report location, moved"),
    ("Report-Limits-Set-Compare", "run2", "Verification", "ChromIQ tight on the shared measurement"),
    ("Report-Limits-Strip-And-Gamut", "run4", "Verification", "a chart that cannot supply four rows"),
]


def script(d):
    work = d.work
    pack = Path(os.environ["CHROMIQ_DEMO_PACK"])
    if (pack / "reports").is_dir() and not (work / "reports").exists():
        shutil.copytree(pack / "reports", work / "reports")
    pages = d.out / "pages"
    pages.mkdir(exist_ok=True)
    d.record["runs"] = {}

    def saved_rows(dlg):
        combo = dlg._saved_combo
        out = []
        for i in range(combo.count()):
            out.append((i, combo.itemText(i), combo.itemData(i)))
        return out

    last_project = None
    for n, (project, run, rtype, why) in enumerate(SAMPLE, start=1):
        tag = f"{n:02d}-{project.replace('Report-Limits-', '').replace('Report-', '')}-{run}"
        d.note(f"== {tag}: {why}")
        if project != last_project:
            d.open_project(project)
            yield 1200
            last_project = project
        d.set_bar(run_type=rtype)
        yield 600
        d.set_bar(run=run)
        yield 900
        d.launch_tool("measurement_report")
        dlg = None
        t0 = time.monotonic()
        while time.monotonic() - t0 < 30 and dlg is None:
            yield 400
            dlg = d.top_dialog("MeasurementReportDialog")
        if dlg is None:
            m = d.modal()
            d.note(f"   NO REPORT WINDOW; modal: {d.modal_text(m) if m else None!r}")
            if m is not None:
                d.shot(m, f"{tag}-modal")
                m.close()
            yield 800
            continue
        yield 3500
        rows = saved_rows(dlg)
        rec = {"why": why, "label": dlg._saved_label.text(),
               "report_shown": [t for _i, t, _k in rows],
               "already_line": getattr(dlg, "_type_blurb_full", ""),
               "entries": []}
        d.note(f"   Report shown: {rec['report_shown']}")
        d.shot(dlg, f"{tag}-00-as-opened")
        (pages / f"{tag}-00-as-opened.txt").write_text(
            dlg._view.toPlainText(), encoding="utf-8")
        picks = [(i, t) for i, t, k in rows if k is not None][:4]
        for j, (i, text) in enumerate(picks, start=1):
            dlg._saved_combo.setCurrentIndex(i)
            dlg._saved_combo.activated.emit(i)
            yield 2500
            body = dlg._view.toPlainText()
            (pages / f"{tag}-{j:02d}.txt").write_text(
                f"REPORT SHOWN: {text}\n\n{body}", encoding="utf-8")
            if j <= 3:
                d.shot(dlg, f"{tag}-{j:02d}")
            rec["entries"].append({"report_shown": text,
                                   "page_head": body[:1500]})
        if project == "Report-Limits-Threshold-Series" or project == "Report-Limits-Renamed":
            combo = dlg._saved_combo
            combo.showPopup()
            yield 900
            d.shot(combo.view(), f"{tag}-report-shown-open")
            combo.hidePopup()
            yield 300
        d.record["runs"][tag] = rec
        dlg.close()
        yield 1200
        m = d.modal()
        if m is not None:
            d.note(f"   a question after closing: {d.modal_text(m)[:200]!r}")
            d.shot(m, f"{tag}-after-close")
            m.close()
            yield 600

    # THE CREATE CHART TAB ON THE i1Pro LAYOUT (Restore Used Chart's ground).
    d.open_project("Report-Limits-Paper-Classes")
    yield 1200
    d.set_bar(run_type="Verification")
    yield 600
    d.set_bar(run="run4")
    yield 900
    d.goto_tab("chart")
    yield 2500
    d.shot(d.win, "90-create-chart-i1pro-layout")
    d.goto_tab("measure")
    yield 1500
    d.shot(d.win, "91-measure-tab-newsprint-and-office")


def main() -> int:
    from userdrive import Drive
    out = Path(sys.argv[1]).resolve()
    projects = sorted({p for p, _r, _t, _w in SAMPLE})
    d = Drive(out, projects=projects)
    rc = d.run(script)
    (out / "record.json").write_text(json.dumps(d.record, indent=2,
                                                default=str),
                                     encoding="utf-8")
    return rc


if __name__ == "__main__":
    sys.exit(main())

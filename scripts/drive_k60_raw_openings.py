#!/usr/bin/env python3
"""K60 (Knut, #182 5850164956, D1 to D3): the raw openings and a raw
sheet's repeatability rows. Driven ON SCREEN, real windows, photographs by
`onscreen_capture`.

    CHROMIQ_DEMO_PACK=<pack> python drive_k60_raw_openings.py <out> <en|de> <case> ...

Cases, all on Report-Limits-Border-Conditions (Run type Verification, run3,
both of whose sheets were printed raw), each a "New report…" of type Full
colour check with every date ticked, Detailed data on, Generate report
("New"), then the page photographed where it says what K60 changed, the
repeatability graph brought to the front, and the PDF saved through
ChromIQ's own file dialog:

* ``NOPROF7``    run3's profile moved out of the run and its dates' saved
                 reports removed (no profile can be read, so the paper and
                 solid rows read N-A), ISO 12647-7:2016 values: D1's sentence,
                 a column that judged nothing;
* ``NOPROFC7``   the same, Custom ISO 12647-7 (the repeatability rows are
                 limited too): D1's sentence beside judged repeatability rows;
* ``RAWCQ``      run3 as it is, ChromIQ default: D3, the repeatability rows
                 judged, and no opening claims the paper or the solids;
* ``MULTI``      run3 and run1, both of run1's sheets recorded as printed raw,
                 ISO 12647-7:2016 values: the plural opening with its clause;
* ``MULTICQ``    the same, ChromIQ default: the plural opening without it;
* ``MIXEDRUNS``  run3 and run1 as they are (run1 printed through its profile),
                 ISO 12647-7:2016 values: D2's sentence.

Every question the drive expects it answers itself; a watchdog photographs
and cancels anything else; a deadline ends the run. `QDesktopServices.openUrl`
is replaced so a saved PDF is not opened in a viewer. The pack is copied,
never written; settings, presets and output are sandboxed by `userdrive`.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

TREE = os.environ.get("CHROMIQ_TREE") or str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
HERE = str(Path(__file__).resolve().parent)
if HERE not in sys.path:
    sys.path.append(HERE)
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402
import drive_k45_pdf_layout as K45                             # noqa: E402
from drive_k59_raw_sheets import _record, _top                 # noqa: E402

K36.DEADLINE_S = 2400
PROJECT = "Report-Limits-Border-Conditions"
CASES = {
    "NOPROF7": {"set": "iso_12647_7", "prep": "noprof"},
    "NOPROFC7": {"set": "custom_iso_12647_7", "prep": "noprof"},
    "RAWCQ": {"set": "chromiq_default"},
    "MULTI": {"set": "iso_12647_7", "prep": "multi", "add": True},
    "MULTICQ": {"set": "chromiq_default", "prep": "multi", "add": True},
    "MIXEDRUNS": {"set": "iso_12647_7", "prep": "fresh", "add": True},
}


def _no_profile(root: Path) -> "list[str]":
    """Move run3's profile out of the run, and remove its dates' saved
    reports, so the window works each sheet out with no profile to read."""
    run = root / "runs" / "run3"
    done = []
    for icc in run.glob("*.icc"):
        shutil.move(str(icc), str(root / ("moved-away-" + icc.name)))
        done.append(f"moved {icc.name} out of runs/run3")
    for rep in (run / "verifications").glob("*/reports"):
        shutil.rmtree(rep, ignore_errors=True)
        done.append(f"removed {rep.parent.name}/reports")
    return done


def _show_after(dlg, anchor: str, needle: str) -> bool:
    """Scroll to the first *needle* after the first *anchor*, no selection."""
    from PyQt6.QtGui import QTextCursor
    view = dlg._view
    view.moveCursor(QTextCursor.MoveOperation.Start)
    if anchor and not view.find(anchor):
        return False
    found = view.find(needle)
    cur = QTextCursor(view.textCursor())
    cur.clearSelection()
    view.setTextCursor(cur)
    view.ensureCursorVisible()
    return bool(found)


def script(tags, lang):
    def s(d):
        rec = d.record
        rec.update({"language": lang, "tree": TREE, "mode": "ON SCREEN",
                    "cases": {}})
        K36._install_watchdog(d, rec)
        from PyQt6.QtGui import QDesktopServices
        QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
        import ui.dialogs.measurement_report_dialog as mrd
        from core.i18n import tr
        from workflow import measurement_messages as M
        yield 500
        root = d.work / PROJECT
        for tag in tags:
            c = dict(CASES[tag], tag=tag)
            name = f"{lang}-{tag}"
            cr = rec["cases"].setdefault(tag, dict(c))
            d.note(f"== case {name}: {c}")
            # a fresh copy of the project for every case, so no case sees
            # another's records or saved reports
            from userdrive import DEMO_PACK
            shutil.rmtree(root, ignore_errors=True)
            shutil.copytree(DEMO_PACK / PROJECT, root)
            if c.get("prep") == "noprof":
                cr["prep"] = _no_profile(root)
            elif c.get("prep") == "multi":
                cr["prep"] = [_record(root, "run1", dt, "raw")
                              for dt in ("2026-12-01_100000",
                                         "2026-12-15_100000")]
            d.open_project(PROJECT)
            d.set_bar(run="run3", run_type="verification")
            d.pump(1200)
            d.launch_tool("measurement_report")
            yield 4500
            dlg = K36._wait(d, "MeasurementReportDialog")
            if dlg is None:
                cr["error"] = "no report window"
                d.note("NO REPORT WINDOW")
                continue
            dlg.resize(1400, 980)
            yield 1500
            K45._pick_data(dlg._saved_combo, mrd.NEW_REPORT_KEY)
            yield 2000
            if c.get("add"):
                K36.EXPECTED.add("QFileDialog")
                d.later(dlg._add_btn.click)
                yield 800
                ti3 = sorted((root / "runs/run1/verifications").glob(
                    "*/*.ti3"))[0]
                cr["added"] = d.answer_file(ti3, f"{name}-00-add-run1",
                                            within_ms=8000)
                K36.EXPECTED.discard("QFileDialog")
                yield 3000
            cr["type_set"] = K45._pick_data(dlg._type_combo,
                                            "t2_full_colour_check")
            yield 1500
            cr["set_set"] = K45._pick_data(dlg._set_combo, c["set"])
            yield 1500
            cr["ticks"] = K45._tick(dlg, "all")
            yield 1500
            if not dlg._detail_check.isChecked():
                dlg._detail_check.setChecked(True)
                yield 800
            K36.EXPECTED.add("QMessageBox")
            d.later(dlg._generate_btn.click)
            yield 600
            cr["generate_question"] = d.answer(
                "neu" if lang == "de" else "new", f"{name}-question",
                within_ms=4000)
            K36.EXPECTED.discard("QMessageBox")
            yield 9000
            cr["state"] = {"type": dlg._type_combo.currentText(),
                           "set": dlg._set_combo.currentText(),
                           "shown": dlg._saved_combo.currentText()}
            text = dlg._view.toPlainText()
            (d.out / f"{name}-page.txt").write_text(text, encoding="utf-8")
            lines = [ln.strip() for ln in text.splitlines()]
            cr["opening"] = [ln for ln in lines if ln.startswith(
                ("This report", "Dieser Bericht"))][:1]
            # the results grid: every row from the repeatability rows to
            # "Judged against", with the words under each
            try:
                i0 = lines.index(tr("Report Results"), 5)
            except ValueError:
                i0 = 0
            grid = lines[i0:i0 + 160]
            def _after(label, n):
                try:
                    k = grid.index(label)
                except ValueError:
                    return None
                return grid[k + 1:k + 1 + n]
            ncol = 2 if not c.get("add") else 4
            cr["grid"] = {lbl: _after(tr(lbl), ncol) for lbl in (
                "Maximum ΔE00, repeat patches on one sheet",
                "Maximum ΔE00, the same chart measured again",
                "ΔE00, paper white against the reference paper",
                "Maximum ΔE00, solid colours", "Overall", "Judged against")}
            said = {m.id: tr(m.body)[:60] in text for m in (
                M.M_REPORT_RAW_RESULTS_JUDGED, M.M_REPORT_RAW_RESULTS_SOME,
                M.M_REPORT_RAW_RESULTS, M.M_REPORT_RAW_GUIDE_JUDGED,
                M.M_REPORT_RAW_GUIDE, M.M_REPORT_RAW_NOT_JUDGED,
                M.M_REPORT_MIXED_OPENING_RUNS)}
            cr["messages_on_page"] = said
            # -- the photographs, each where the page says it
            _top(dlg)
            yield 900
            d.shot(dlg, f"{name}-p0-opening")
            marks = [
                ("p1-results", "", tr("Report Results")),
                ("p2-repeat-rows", tr("Report Results"),
                 tr("Maximum ΔE00, repeat patches on one sheet")),
                ("p3-overall", tr("Report Results"), tr("Judged against")),
                ("p4-under-results", "",
                 tr(M.M_REPORT_RAW_RESULTS.body)[:40]),
                ("p5-guide", "", tr(M.M_REPORT_RAW_GUIDE.body)[:40]),
            ]
            done = set()
            for key, anchor, needle in marks:
                if _show_after(dlg, anchor, needle):
                    done.add(key)
                    yield 900
                    d.shot(dlg, f"{name}-{key}")
            cr["photographed"] = sorted(done)
            _top(dlg)
            chart = (getattr(dlg, "_trend_groups", {}) or {}).get("repeat")
            if chart is not None and K45._tab_to(dlg, chart):
                yield 1200
                d.shot(dlg, f"{name}-g-repeat")
                cr["repeat_graph"] = True
            pdf = d.out / f"{name}.pdf"
            pdf.unlink(missing_ok=True)
            K36.EXPECTED.add("QFileDialog")
            d.later(dlg._pdf_btn.click)
            yield 800
            cr["pdf_chosen"] = d.answer_file(pdf, f"{name}-99-pdf-dialog",
                                             within_ms=8000)
            yield 7000
            K36.EXPECTED.discard("QFileDialog")
            cr["pdf"] = pdf.name if pdf.is_file() else None
            d.note(f"   pdf {pdf.name}: "
                   f"{'written' if pdf.is_file() else 'MISSING'}")
            dlg.close()
            yield 2000
        (d.out / f"{lang}-cases.json").write_text(
            json.dumps(rec["cases"], indent=2, ensure_ascii=False,
                       default=str), encoding="utf-8")
    return s


def main() -> int:
    out = Path(sys.argv[1])
    lang = sys.argv[2]
    tags = sys.argv[3:]
    d = Drive(out, projects=[PROJECT], language=lang)
    rc = d.run(script(tags, lang))
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

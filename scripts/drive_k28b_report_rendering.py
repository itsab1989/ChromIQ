#!/usr/bin/env python3
"""#182 K28b (beta 39): the report-rendering half of Knut's K28 rulings,
driven ON SCREEN.

    CHROMIQ_DEMO_PACK=<pack> python scripts/drive_k28b_report_rendering.py \\
        <out> <en|de> [scene ...]

The pack is `~/Desktop/ChromIQ-beta39-proof/k28-b/pack/`, built by
`make_dash_demo.py` beside it: Report-Limits-Threshold-Series whose run1
leaves "Average ΔE00, all patches" and "Average ΔE00, highest 5 %" at "–"
(every dated record recalculated), the two Report-Folders projects of the
beta 38 K26 pack, and the notes demo of G12.

scenes:
    full      run1 of the "–" demo, every date, Full colour check, detail on:
              the grid, How to read, the Overview, the detailed tables, the
              Colour accuracy graph and the Report Limits window
    onepage   the same run on its within-gamut date as the one-page summary
    runs      Report-Folders, Profiling: the Printing record of two runs
    projects  Report-Folders run1 verification + Report-Folders-Second added
    notes     the notes demo: run1 (first measurement), run5 (an empty
              ninth), run7 Printing record (no device values)

Every scene photographs the real window and saves a PDF whose pages are
rendered; `k28b-found.json` records what the window text and the PDF text
hold for each check.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402
from drive_g12_notes import pdf_pages_text, render_pdf        # noqa: E402

DASH = "Report-Limits-Threshold-Series"
FOLDERS = "Report-Limits-Report-Folders"
SECOND = "Report-Limits-Report-Folders-Second"
NOTES = "Report-Notes-Every-Reason"
ALL = ("full", "onepage", "runs", "projects", "notes")


def _flat(s: str) -> str:
    return " ".join(str(s).split())


def script_for(scenes, language):
    def script(d):
        from core.i18n import tr
        rec = d.record
        rec["language"] = language
        rec["checks"] = {}

        def check(scene, what, ok, detail=""):
            rec["checks"].setdefault(scene, []).append(
                {"what": what, "ok": bool(ok), "detail": detail})
            d.note(f"   {'OK  ' if ok else 'FAIL'} {what} {detail}")

        def wait_dialog():
            for _ in range(80):
                dlg = d.top_dialog("MeasurementReportDialog")
                if dlg is not None:
                    return dlg
                d.pump(250)
            return None

        def open_window(project, run, run_type, verification=None):
            d.open_project(project)
            d.set_bar(run_type=run_type, run=run, verification=verification)
            d.pump(900)
            d.launch_tool("measurement_report")

        def new_report(dlg, detail=True):
            from PyQt6.QtCore import Qt
            dlg._saved_combo.setCurrentIndex(0)
            dlg._saved_combo.activated.emit(0)
            d.pump(1200)
            lst = dlg._profile_list
            for i in range(lst.count()):
                it = lst.item(i)
                if it.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    it.setCheckState(Qt.CheckState.Checked)
                    d.pump(120)
            if detail != dlg._detail_check.isChecked():
                dlg._detail_check.click()
            d.pump(2000)

        def pick_type(dlg, tid):
            i = dlg._type_combo.findData(tid)
            if i >= 0:
                dlg._type_combo.setCurrentIndex(i)
                dlg._type_combo.activated.emit(i)
            d.pump(2000)
            return i >= 0

        def scroll_to(dlg, text, occurrence=0):
            view = dlg._view
            doc = view.document()
            start, cur = 0, None
            for _ in range(occurrence + 1):
                c = doc.find(text, start)
                if c.isNull():
                    return False
                cur, start = c, c.selectionEnd()
            from PyQt6.QtGui import QTextCursor
            plain = QTextCursor(cur)
            plain.setPosition(cur.selectionStart())
            view.setTextCursor(plain)
            sb = view.verticalScrollBar()
            sb.setValue(max(0, sb.value() + view.cursorRect(plain).top() - 30))
            d.pump(500)
            return True

        def shoot_at(dlg, text, name, occurrence=0):
            if scroll_to(dlg, text, occurrence):
                d.shot(dlg, name)
                return True
            d.note(f"   (not on the page: {text!r})")
            return False

        def save_pdf(dlg, name):
            target = d.out / "pdf" / f"{name}.pdf"
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target.unlink()
            d.later(dlg._pdf_btn.click)
            yield 1500
            d.answer_file(target, name=None)
            for _ in range(120):
                yield 1000
                if target.exists():
                    break
            yield 3000
            pages, text = [], []
            if target.exists():
                pages_dir = d.out / "pdf-pages"
                pages_dir.mkdir(exist_ok=True)
                pages = render_pdf(target, pages_dir)
                text = pdf_pages_text(target)
                (pages_dir / f"{name}.txt").write_text(
                    "\n\f\n".join(text), encoding="utf-8")
            d.note(f"   PDF {target.name}: {len(pages)} pages")
            rec.setdefault("pdfs", {})[name] = {"pdf": str(target),
                                                "pages": pages}
            dlg.raise_()
            return text

        def both(scene, what, window, pdf_text, needle, present=True):
            flat_pdf = _flat(" ".join(pdf_text))
            w = _flat(needle) in window
            p = _flat(needle) in flat_pdf
            check(scene, f"{what} [window]", w is present, repr(needle))
            check(scene, f"{what} [PDF]", p is present, repr(needle))

        L = lambda s: tr(s)                                     # noqa: E731
        names = [L("Average ΔE00, all patches"),
                 L("Average ΔE00, lowest 95 %"),
                 L("Average ΔE00, highest 5 %"),
                 L("Maximum ΔE00, all patches"),
                 L("Maximum ΔE00, lowest 95 % (95th percentile)")]
        info = L("For information (no limit applies)")
        tag = language

        # ---------------------------------------------------------------
        if "full" in scenes:
            sc = "full"
            d.note(f"[{sc}] {DASH} run1, every date, detail on")
            open_window(DASH, "run1", "Verification")
            yield 3500
            dlg = wait_dialog()
            new_report(dlg)
            from workflow.measurement_report import REPORT_TYPE_FULL
            pick_type(dlg, REPORT_TYPE_FULL)
            yield 1500
            text = _flat(dlg._view.toPlainText())
            dlg._view.verticalScrollBar().setValue(0)
            d.shot(dlg, f"{tag}-full-01-top")
            shoot_at(dlg, L("Report Results"), f"{tag}-full-02-results")
            shoot_at(dlg, L("How to read this report"), f"{tag}-full-03-guide")
            shoot_at(dlg, L("The five verdict words."), f"{tag}-full-04-words")
            shoot_at(dlg, L("Overview of Measurement Metrics"),
                     f"{tag}-full-05-overview")
            shoot_at(dlg, info, f"{tag}-full-06-overview-info", 0)
            shoot_at(dlg, L("Detailed data per measurement run"),
                     f"{tag}-full-07-detail")
            shoot_at(dlg, info, f"{tag}-full-08-detail-info", 2)
            # the Colour accuracy graph, its tab in front
            tabs = dlg._trend_tabs
            tabs.setCurrentIndex(tabs.indexOf(dlg._trend_de))
            d.pump(800)
            d.shot(dlg, f"{tag}-full-09-graph")
            legend = [m[0] for m in dlg._trend_configs()[0][2]]
            rec["full_legend"] = legend
            check(sc, "graph legend is the ROWS names minus the two '–' rows",
                  legend == [names[1], names[3], names[4]], repr(legend))
            thr = dlg._accuracy_thresholds()
            check(sc, "no Avg limit line for a '–' average",
                  thr[0] is None and thr[1] is not None, repr(thr))
            pdf = yield from save_pdf(dlg, f"{tag}-full")
            for n in (names[1], names[3], names[4]):
                both(sc, "a limited row is named", text, pdf, n)
            for n in (names[0], names[2]):
                both(sc, "a '–' row is gone", text, pdf, n, present=False)
            both(sc, "the no-limit heading", text, pdf, info)
            both(sc, "the INFO cause 'no limit' is gone", text, pdf,
                 L("puts no limit on the row"), present=False)
            # the Report Limits window, from "Show limits…"
            d.later(dlg._limits_btn.click)
            yield 2500
            m = d.modal()
            if m is not None and m is not dlg:
                d.shot(m, f"{tag}-full-10-report-limits")
                from PyQt6.QtWidgets import QLabel, QScrollArea
                # scrolled down to the five rows, as a user scrolls to them
                hit = next((w for w in m.findChildren(QLabel)
                            if w.text().startswith(names[0])), None)
                area = next((a for a in m.findChildren(QScrollArea)
                             if hit is not None and a.isAncestorOf(hit)), None)
                if area is not None:
                    area.ensureWidgetVisible(hit, 50, 250)
                    d.pump(600)
                    d.shot(m, f"{tag}-full-11-report-limits-five-rows")
                labels = {w.text() for w in m.findChildren(QLabel)}
                for n in names:
                    check(sc, "Report Limits window names the row", n in labels
                          or any(n in t for t in labels), repr(n))
                m.close()
                d._modal_closed()
            else:
                check(sc, "Report Limits window opened", False)
            yield 1200
            dlg.close()
            yield 1200

        # ---------------------------------------------------------------
        if "onepage" in scenes:
            sc = "onepage"
            d.note(f"[{sc}] {DASH} run1, 2026-01-19 (within-gamut split)")
            open_window(DASH, "run1", "Verification", verification="2026-01-19")
            yield 3500
            dlg = wait_dialog()
            new_report(dlg, detail=False)
            # one date ticked, the one-page type, Generate: what a user does
            # to make the page that goes with a job
            from PyQt6.QtCore import Qt
            lst = dlg._profile_list
            for i in range(lst.count()):
                it = lst.item(i)
                if (it.flags() & Qt.ItemFlag.ItemIsUserCheckable
                        and it.text().strip()[:4].isdigit()):
                    it.setCheckState(Qt.CheckState.Checked
                                     if "2026-01-19" in it.text()
                                     else Qt.CheckState.Unchecked)
                    d.pump(120)
            from workflow.measurement_report import REPORT_TYPE_SUMMARY
            pick_type(dlg, REPORT_TYPE_SUMMARY)
            yield 1000
            d.later(dlg._generate_btn.click)
            yield 800
            d.answer("Create", name=f"{tag}-onepage-00-generate",
                     within_ms=3000)
            yield 4000
            text = _flat(dlg._view.toPlainText())
            dlg._view.verticalScrollBar().setValue(0)
            d.shot(dlg, f"{tag}-onepage-01-top")
            shoot_at(dlg, L("Result"), f"{tag}-onepage-02-result")
            pdf = yield from save_pdf(dlg, f"{tag}-onepage")
            check(sc, "one A4 page", len(pdf) == 1, f"{len(pdf)} pages")
            both(sc, "the within-gamut sentence", text, pdf,
                 L("The judged figures are those of the patches within the "
                   "profile's gamut."))
            both(sc, "the maximum is named by its one name", text, pdf,
                 names[3] + ":")
            both(sc, "the '–' average is not printed", text, pdf,
                 names[0] + ":", present=False)
            both(sc, "corners under the no-limit heading", text, pdf,
                 L("Cube corners, for information (no limit applies)"))
            dlg.close()
            yield 1200

        # ---------------------------------------------------------------
        if "runs" in scenes:
            sc = "runs"
            d.note(f"[{sc}] {FOLDERS}, Profiling: two profile runs")
            open_window(FOLDERS, "run1", "Profiling")
            yield 3500
            dlg = wait_dialog()
            new_report(dlg, detail=False)
            yield 1500
            text = _flat(dlg._view.toPlainText())
            dlg._view.verticalScrollBar().setValue(0)
            shoot_at(dlg, L("Report Scope"), f"{tag}-runs-01-scope")
            pdf = yield from save_pdf(dlg, f"{tag}-runs")
            both(sc, "the several-runs notice", text, pdf,
                 L("This report includes measurements from several runs, so no "
                   "single run description is given. The list below shows the "
                   "measurements included."))
            rec["runs_members"] = [str(r.get("_origin_dir"))
                                   for r in dlg._runs_for_report()]
            dlg.close()
            yield 1200

        # ---------------------------------------------------------------
        if "projects" in scenes:
            sc = "projects"
            d.note(f"[{sc}] {FOLDERS} run1 + {SECOND} added")
            open_window(FOLDERS, "run1", "Verification")
            yield 3500
            dlg = wait_dialog()
            new_report(dlg, detail=False)
            other = sorted((d.work / SECOND / "runs" / "run1" /
                            "verifications").glob("*/*.ti3"))
            d.later(dlg._add_btn.click)
            yield 1200
            d.answer_file(other[0], name=f"{tag}-projects-00-add")
            yield 3500
            new_report(dlg, detail=False)
            yield 1500
            text = _flat(dlg._view.toPlainText())
            shoot_at(dlg, L("Report Scope"), f"{tag}-projects-01-scope")
            pdf = yield from save_pdf(dlg, f"{tag}-projects")
            both(sc, "the several-projects notice", text, pdf,
                 L("This report includes measurements from several projects, "
                   "so no single run description is given. The list below "
                   "shows the measurements included from each project."))
            dlg.close()
            yield 1200

        # ---------------------------------------------------------------
        if "notes" in scenes:
            sc = "notes"
            for run, rtype, label, reason in (
                    ("run1", "Verification", "first", "no_earlier_measurement"),
                    ("run5", "Verification", "ninth", "evenness_empty_area"),
                    ("run7", "Profiling", "nodevice", "no_device_values")):
                d.note(f"[{sc}] {NOTES} {run} {rtype}")
                open_window(NOTES, run, rtype)
                yield 3500
                dlg = wait_dialog()
                new_report(dlg, detail=True)
                yield 1500
                text = _flat(dlg._view.toPlainText())
                sentences = set()
                for r in dlg._runs_for_report():
                    rows, _ = dlg._verdict_rows(r)
                    for x in rows:
                        if x.get("reason") == reason:
                            sentences.add(dlg._reason_sentence(reason, r, x))
                rec.setdefault("notes_sentences", {})[reason] = sorted(sentences)
                check(sc, f"{reason} reached", bool(sentences))
                head = (L("Notes on the values above:") if rtype == "Profiling"
                        else L("Notes on the verdicts above:"))
                shoot_at(dlg, head, f"{tag}-notes-{label}-01")
                if reason == "no_earlier_measurement":
                    shoot_at(dlg, L("How to read this report"),
                             f"{tag}-notes-{label}-00-guide")
                pdf = yield from save_pdf(dlg, f"{tag}-notes-{label}")
                for s in sentences:
                    both(sc, f"{reason} sentence", text, pdf, s)
                if reason == "no_earlier_measurement":
                    both(sc, "no ChromIQ explanation", text, pdf,
                         "second measurement onward", present=False)
                dlg.close()
                yield 1200

        (d.out / "k28b-found.json").write_text(
            json.dumps(rec.get("checks"), indent=2, ensure_ascii=False),
            encoding="utf-8")
    return script


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    out, language = Path(sys.argv[1]), sys.argv[2]
    scenes = tuple(sys.argv[3:]) or ALL
    d = Drive(out, projects=[DASH, FOLDERS, SECOND, NOTES],
              language=language)
    sys.exit(d.run(script_for(scenes, language)))

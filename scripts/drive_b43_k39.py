#!/usr/bin/env python3
"""K39 (Knut, #182 5831246553), driven ON SCREEN, on any tree.

    CHROMIQ_DEMO_PACK=<pack> CHROMIQ_TREE=<tree> \\
        python drive_b43_k39.py <out> <en|de> <scene> [project run [date]]

Scenes:

  old    <project> <run> <date> (default Report-Limits-Second-Route run2
         2029-03-26), Verification: the saved report of that date, which an
         earlier version worked out. Report
         Scope photographed at M-REPORT-WORKED-OUT-EARLIER (K39-1); Generate
         report pressed with nothing changed and the question photographed
         and cancelled (K39-2); Save report as PDF and its Report Scope read
         back.
  fresh  <project> <run> (the same default): "New report…" chosen with the
         mouse over the saved
         report (K39-3: the page, the red line, the defaults, Delete);
         "Show detailed data" moved; the previous report chosen again (its
         own settings back); "New report…" chosen with the keyboard; Generate
         report (the new report drawn); Generate report again with nothing
         changed (the approved unchanged question, cancelled).
  empty  Report-Limits-Border-Conditions, run1, its saved reports removed from the
         drive's copy: the first page on "New report…", then "New report…"
         chosen again.
  cal    Report-Limits-Report-Types, Run type Calibration: "New report…" over
         the calibration's saved report.
  text   Report texts the K39-1 audit reworded, where the pack reaches them:
         Report-Limits-Paper-Classes, run6 (a verification across several
         profile runs) Report Scope, and a Paper white graph with fewer than
         two values (Report-Limits-Strip-And-Gamut, run4).

**NOBODY HAS TO CLICK.** Every question is answered by the drive; a watchdog
cancels anything else after three seconds and photographs it; a deadline ends
the run whatever happens. The pack is copied, never written.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

TREE = os.environ.get("CHROMIQ_TREE") or str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402

K36.DEADLINE_S = 900
OLD = ("Report-Limits-Second-Route", "run2", "2029-03-26")
_WORDS = re.compile(r"\b(PASS|FAIL|COND|INFO|N-A)\b")


def _tr(s: str) -> str:
    from core.i18n import tr
    return tr(s)


def _state(dlg) -> dict:
    return {"report_shown": dlg._saved_combo.currentText(),
            "type": dlg._type_combo.currentText(),
            "set": dlg._set_combo.currentText(),
            "detail": dlg._detail_check.isChecked(),
            "red_line_visible": dlg._stale_label.isVisible(),
            "red_line": dlg._stale_label.text(),
            "delete_enabled": dlg._delete_report_btn.isEnabled(),
            "generate_enabled": dlg._generate_btn.isEnabled()}


def _page(dlg) -> str:
    return K36._view_text(dlg)


def _pdf_text(path: Path) -> str:
    from pypdf import PdfReader
    t = "\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)
    return re.sub(r"[ \t\xa0]+", " ", t)


def _save_pdf(d, dlg, rec, tag):
    pdf = d.out / f"{tag}.pdf"
    K36.EXPECTED.add("QFileDialog")
    d.later(dlg._pdf_btn.click)
    yield 800
    rec["pdf_chosen"] = d.answer_file(pdf, f"{tag}-pdf-dialog", within_ms=8000)
    yield 6000
    K36.EXPECTED.discard("QFileDialog")
    if pdf.is_file():
        t = _pdf_text(pdf)
        (d.out / f"{tag}.pdf.txt").write_text(t, encoding="utf-8")
        rec["pdf_text_file"] = f"{tag}.pdf.txt"


def _press_generate_and_answer(d, dlg, rec, tag, answer):
    """Generate report, the question photographed, *answer* pressed."""
    K36.EXPECTED.add("QMessageBox")
    d.later(dlg._generate_btn.click)
    yield 600
    said = d.answer(answer, f"{tag}-question", within_ms=15000)
    rec[f"{tag}_question"] = said
    yield 4000
    K36.EXPECTED.discard("QMessageBox")


def _pick_key(dlg, key) -> bool:
    combo = dlg._saved_combo
    i = combo.findData(key)
    if i < 0:
        return False
    combo.setCurrentIndex(i)
    combo.activated.emit(i)
    return True


def _open_window(d, project, run, run_type="Verification"):
    d.open_project(project)
    if run_type == "Calibration":
        from core import measurement_target as MT
        b = d.bar
        i = b._type_combo.findData(MT.RUN_TYPE_CALIBRATION)
        if i >= 0:
            b._type_combo.setCurrentIndex(i)
            b._type_combo.activated.emit(i)
    else:
        d.set_bar(run=run, run_type=run_type)
    d.pump(1200)
    d.launch_tool("measurement_report")


def script(scene, language, args=()):
    project, run, date = (tuple(args) + OLD[len(args):])[:3]
    def s(d):
        rec = d.record
        rec.update({"scene": scene, "language": language, "tree": TREE,
                    "mode": "ON SCREEN"})
        K36._install_watchdog(d, rec)
        from PyQt6.QtGui import QDesktopServices
        QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
        tag = f"{language}-{scene}"
        rec.update({"project": project, "run": run, "date": date})
        if scene in ("old", "fresh"):
            _open_window(d, project, run)
        elif scene == "empty":
            for p in (d.work / "Report-Limits-Border-Conditions" / "runs" / "run1"
                      ).rglob("report_*.json"):
                p.unlink()
            _open_window(d, "Report-Limits-Border-Conditions", "run1")
        elif scene == "cal":
            d.settings.set("calibration_mode", True)
            d.win._apply_calibration_mode()
            yield 1000
            _open_window(d, "Report-Limits-Report-Types", None, "Calibration")
        elif scene == "text":
            _open_window(d, "Report-Limits-Paper-Classes", "run6")
        yield 4500
        dlg = K36._wait(d, "MeasurementReportDialog")
        if dlg is None:
            d.note("NO REPORT WINDOW")
            return
        dlg.resize(1400, 950)
        yield 1500
        combo = dlg._saved_combo
        rec["saved_list"] = [combo.itemText(i) for i in range(combo.count())]
        d.note(f"saved list: {rec['saved_list']}")
        rec["open"] = _state(dlg)
        d.note(f"open: {rec['open']}")

        if scene == "old":
            idx = next((i for i in range(combo.count())
                        if date in combo.itemText(i)), None)
            if idx is None:
                d.note(f"no saved report of {date}")
                return
            combo.setCurrentIndex(idx)
            combo.activated.emit(idx)
            yield 3500
            page = _page(dlg)
            (d.out / "old-page.txt").write_text(page, encoding="utf-8")
            from workflow import measurement_messages as M
            title, body = M.M_REPORT_WORKED_OUT_EARLIER.render()
            rec["worked_out_earlier_on_page"] = " ".join(body.split()) in \
                " ".join(page.split())
            i = page.find(title)
            rec["scope_note"] = page[i:i + 400] if i >= 0 else None
            d.note(f"scope note: {rec['scope_note']!r}")
            if K36._scroll_to(dlg, title):
                yield 900
            d.shot(dlg, f"{tag}-01-report-scope")
            yield from _save_pdf(d, dlg, rec, f"{tag}-saved")
            yield from _press_generate_and_answer(d, dlg, rec, f"{tag}-02",
                                                  _tr("Cancel"))
            rec["after_cancel_page_kept"] = _page(dlg) == page
            d.shot(dlg, f"{tag}-03-after-cancel")

        elif scene == "fresh":
            import ui.dialogs.measurement_report_dialog as mrd
            old_key = dlg._loaded_doc_id
            page = _page(dlg)
            rec["old_key"] = old_key
            rec["old_settings"] = _state(dlg)
            d.shot(dlg, f"{tag}-01-saved-report")
            # K39-3, the mouse
            _pick_key(dlg, mrd.NEW_REPORT_KEY)
            yield 2500
            rec["new_mouse"] = _state(dlg)
            rec["new_mouse"]["page_kept"] = _page(dlg) == page
            d.note(f"New report (mouse): {rec['new_mouse']}")
            d.shot(dlg, f"{tag}-02-new-report-mouse")
            # a setting moved, then the previous report chosen again
            dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
            yield 1500
            rec["new_touched"] = _state(dlg)
            d.shot(dlg, f"{tag}-03-new-report-setting-moved")
            _pick_key(dlg, old_key)
            yield 3500
            rec["reselected"] = _state(dlg)
            rec["reselected"]["page_is_the_report"] = _page(dlg) == page
            d.note(f"re-selected: {rec['reselected']}")
            d.shot(dlg, f"{tag}-04-previous-report-again")
            # K39-3, the keyboard
            from PyQt6.QtCore import Qt
            from PyQt6.QtTest import QTest
            combo.setFocus()
            for _ in range(combo.count()):
                if combo.currentData() == mrd.NEW_REPORT_KEY:
                    break
                QTest.keyClick(combo, Qt.Key.Key_Up)
                yield 700
            yield 2000
            rec["new_keyboard"] = _state(dlg)
            rec["new_keyboard"]["page_kept"] = _page(dlg) == page
            d.note(f"New report (keyboard): {rec['new_keyboard']}")
            d.shot(dlg, f"{tag}-05-new-report-keyboard")
            # Generate: the new report
            dlg._select_all_btn.click()
            yield 1500
            d.later(dlg._generate_btn.click)
            yield 9000
            rec["generated"] = _state(dlg)
            rec["generated"]["page_changed"] = _page(dlg) != page
            d.note(f"generated: {rec['generated']}")
            d.shot(dlg, f"{tag}-06-generated")
            # Generate again, nothing changed: the approved question
            yield from _press_generate_and_answer(d, dlg, rec, f"{tag}-07",
                                                  _tr("Cancel"))

        elif scene in ("empty", "cal"):
            import ui.dialogs.measurement_report_dialog as mrd
            page = _page(dlg)
            d.shot(dlg, f"{tag}-01-first-page")
            _pick_key(dlg, mrd.NEW_REPORT_KEY)
            yield 2500
            rec["new"] = _state(dlg)
            rec["new"]["page_kept"] = _page(dlg) == page
            d.note(f"New report: {rec['new']}")
            d.shot(dlg, f"{tag}-02-new-report")
            if scene == "cal":
                d.settings.set("calibration_mode", False)

        elif scene == "text":
            import ui.dialogs.measurement_report_dialog as mrd
            _pick_key(dlg, mrd.NEW_REPORT_KEY)
            yield 1500
            dlg._select_all_btn.click()
            yield 1500
            d.later(dlg._generate_btn.click)
            yield 9000
            page = _page(dlg)
            (d.out / "text-page.txt").write_text(page, encoding="utf-8")
            i = page.find(_tr("Report Scope"))
            rec["scope"] = page[i:i + 900] if i >= 0 else None
            if K36._scroll_to(dlg, _tr("Report Scope")):
                yield 900
            d.shot(dlg, f"{tag}-01-report-scope")
            tabs = dlg._trend_tabs
            chart = getattr(dlg, "_trend_white", None)
            if chart is not None:
                tabs.setCurrentIndex(tabs.indexOf(chart))
                yield 1200
                rec["white_graph_reason"] = chart.empty_reason()
                d.shot(dlg, f"{tag}-02-paper-white-graph")
        dlg.close()
        yield 1500
    return s


def main() -> int:
    out = Path(sys.argv[1])
    lang, scene = sys.argv[2:4]
    args = sys.argv[4:]
    first = args[0] if args else OLD[0]
    projects = {"old": [first], "fresh": [first],
                "empty": ["Report-Limits-Border-Conditions"],
                "cal": ["Report-Limits-Report-Types"],
                "text": ["Report-Limits-Paper-Classes"]}[scene]
    d = Drive(out, projects=projects, language=lang)
    rc = d.run(script(scene, lang, args))
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""K59 (Knut, #182 5849392788): sheets printed raw, option C, and no "drift".
Driven ON SCREEN, real windows, photographs by `onscreen_capture`.

    CHROMIQ_DEMO_PACK=<pack> python drive_k59_raw_sheets.py <out> <en|de> <case> ...

Cases, all on Report-Limits-Border-Conditions (Run type Verification), each a
"New report…" of type Full colour check with every date ticked, Detailed
data on, Generate report ("New"), then the page photographed where it says
the things K59 changed, every trend tab brought to the front, and the PDF
saved through ChromIQ's own file dialog:

* ``RAWISO``   run3 (both sheets raw), ISO 12647-7:2016 values;
* ``RAWISO8``  the same, ISO 12647-8:2021 values (the paper row only limited);
* ``RAWCQ``    the same, ChromIQ default (nothing limited on those rows);
* ``MIXED``    run3 with its 2026-12-17 sheet recorded as printed THROUGH the
               profile (its print record rewritten and its saved reports
               removed, in the drive's own copy): a document of both kinds;
* ``MULTI``    run3 and run1, both of run1's sheets recorded as printed raw
               (the same way), run1 added with "Add Profile's Measurements…";
* ``SAVED``    no New report: the saved report whose name holds "12647-7" is
               chosen in "Report shown" (for a project saved by beta 43).

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

K36.DEADLINE_S = 2400
PROJECT = "Report-Limits-Border-Conditions"
TABS = ("de", "white", "paper_diff", "black", "corners", "solids",
        "solid_hue", "grey", "tone", "strip", "gamut_edge", "repeat",
        "evenness")
CASES = {
    "RAWISO": {"run": "run3", "set": "iso_12647_7"},
    "RAWISO8": {"run": "run3", "set": "iso_12647_8"},
    "RAWCQ": {"run": "run3", "set": "chromiq_default"},
    "MIXED": {"run": "run3", "set": "iso_12647_7", "prep": "mixed"},
    "MULTI": {"run": "run3", "set": "iso_12647_7", "prep": "multi"},
    "SAVED": {"run": "run3", "saved": "12647-7"},
}
STEM = "Report-Limits-Border-Conditions-verify"


def _record(root: Path, run: str, date: str, colour: str) -> str:
    """Rewrite one date's print record, and remove that date's saved reports
    so the window works the sheet out from the record (what a user who
    corrected a record would have)."""
    d = root / "runs" / run / "verifications" / date
    rec = {"printed_at": date[:10] + "T10:00:00", "colour": colour,
           "intent": "relative" if colour == "through-profile" else "",
           "route": "chromiq", "source_profile": "",
           "profile": ("Report-Limits-Border-Conditions.icc"
                       if colour == "through-profile" else "")}
    (d / "chart").mkdir(parents=True, exist_ok=True)
    (d / "chart" / f"{STEM}.print.json").write_text(
        json.dumps(rec, indent=2), encoding="utf-8")
    shutil.rmtree(d / "reports", ignore_errors=True)
    return f"{run}/{date}: recorded {colour}, saved reports removed"


def _show(dlg, text: str) -> bool:
    """Scroll *text* into view, leaving no selection (B8-1278)."""
    from PyQt6.QtGui import QTextCursor
    view = dlg._view
    view.moveCursor(QTextCursor.MoveOperation.Start)
    found = view.find(text)
    cur = QTextCursor(view.textCursor())
    cur.clearSelection()
    view.setTextCursor(cur)
    view.ensureCursorVisible()
    return bool(found)


def _top(dlg) -> None:
    from PyQt6.QtGui import QTextCursor
    dlg._view.moveCursor(QTextCursor.MoveOperation.Start)
    dlg._view.verticalScrollBar().setValue(0)


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
            # a fresh copy of the project for a case that rewrites records
            if c.get("prep"):
                shutil.rmtree(root, ignore_errors=True)
                from userdrive import DEMO_PACK
                shutil.copytree(DEMO_PACK / PROJECT, root)
            if c.get("prep") == "mixed":
                cr["prep"] = [_record(root, "run3", "2026-12-17_100000",
                                      "through-profile")]
            elif c.get("prep") == "multi":
                cr["prep"] = [_record(root, "run1", dt, "raw")
                              for dt in ("2026-12-01_100000",
                                         "2026-12-15_100000")]
            d.open_project(PROJECT)
            d.set_bar(run=c["run"], run_type="verification")
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
            if c.get("saved"):
                combo = dlg._saved_combo
                items = [combo.itemText(i) for i in range(combo.count())]
                cr["report_shown_items"] = items
                i = next((i for i, t in enumerate(items)
                          if c["saved"] in t), -1)
                cr["picked"] = items[i] if i >= 0 else None
                if i >= 0:
                    combo.setCurrentIndex(i)
                    combo.activated.emit(i)
                yield 5000
                if not dlg._detail_check.isChecked():
                    dlg._detail_check.setChecked(True)
                    yield 1500
            else:
                K45._pick_data(dlg._saved_combo, mrd.NEW_REPORT_KEY)
                yield 2000
                if c.get("prep") == "multi":
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
                (tr("This report follows the printer"),
                 "This report", "Dieser Bericht"))][:2]
            cr["overall"] = [ln for ln in lines if ln.startswith(
                (tr("Overall"),))][:2]
            cr["judged_against"] = [ln for ln in lines if ln.startswith(
                tr("Judged against"))][:3]
            cr["drift_in_page"] = [ln for ln in lines
                                   if "drift" in ln.lower()]
            # -- the photographs, each where the page says it
            _top(dlg)
            yield 900
            d.shot(dlg, f"{name}-p0-page-top")
            def _m(attr, part="body", n=40):
                # a tree before K59 has none of these; it is photographed at
                # the same places by their old words
                msg = getattr(M, attr, None)
                return tr(getattr(msg, part))[:n] if msg else ""
            marks = [
                ("p1-results", tr("Report Results")),
                ("p2-judged-against", tr("Judged against")),
                ("p3-under-results", _m("M_REPORT_RAW_RESULTS")),
                ("p3-under-results", tr("Columns marked “drift”")),
                ("p4-notes", "1) "),
                ("p5-guide", _m("M_REPORT_RAW_GUIDE")),
                ("p5-guide", tr("A column read as a drift check")),
                ("p6-change", _m("M_REPORT_RAW_CHANGE", "title", 60)),
                ("p6-change", tr("Drift since the previous raw check")),
                ("p6-baseline", _m("M_REPORT_RAW_BASELINE")),
            ]
            done = set()
            for key, needle in marks:
                if key in done or not needle:
                    continue
                if _show(dlg, needle):
                    done.add(key)
                    yield 900
                    d.shot(dlg, f"{name}-{key}")
            cr["photographed"] = sorted(done)
            _top(dlg)
            # -- the graphs
            tabs = dlg._trend_tabs
            cr["graphs"] = {}
            for k, key in enumerate(TABS, 1):
                chart = (getattr(dlg, {"de": "_trend_de",
                                       "white": "_trend_white",
                                       "black": "_trend_black",
                                       "corners": "_trend_corners"}.get(
                    key, "-"), None)
                    or (getattr(dlg, "_trend_groups", {}) or {}).get(key))
                if chart is None or not K45._tab_to(dlg, chart):
                    continue
                yield 1200
                try:
                    said = [t for _k, _c, t in chart.descriptions()]
                except Exception as exc:          # noqa: BLE001 — older tree
                    said = [f"(not read: {exc!r})"]
                cr["graphs"][key] = {
                    "title": tabs.tabText(tabs.indexOf(chart)),
                    "descriptions": said}
                d.shot(dlg, f"{name}-g{k:02d}-window-{key}")
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

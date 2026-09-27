#!/usr/bin/env python3
"""K61 (Knut, #182 5851645723): every metric name the Measurement Report
quotes is EXACTLY the name the Report Limits window shows, and "within
gamut" stands outside it. Driven ON SCREEN, on any tree, so the same steps
run before and after the change.

    CHROMIQ_DEMO_PACK=<pack> CHROMIQ_TREE=<tree> \\
        python drive_k61_report_labels.py <out> <en|de>

Knut's own report: Report-Limits-Evenness, Run type Verification, run1, a
"New report…" of type Full colour check judged against Custom ISO 12647-7,
every date ticked, Detailed data on, Generate report ("New"). Then:

* the page photographed at Report Results, How to read, the Overview and the
  notes, where the judged names are printed;
* the Colour accuracy and Evenness graphs brought to the front, with the key
  under each (the sentences Knut quoted);
* the PDF saved through ChromIQ's own file dialog, and every line of it that
  names a metric in quotation marks recorded (``<lang>-quoted.json``).

Every question the drive expects it answers itself; a watchdog photographs
and cancels anything else; a deadline ends the run. `QDesktopServices.openUrl`
is replaced so a saved PDF is not opened in a viewer. The pack is copied,
never written; settings, presets and output are sandboxed by `userdrive`.
"""
from __future__ import annotations

import json
import os
import re
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

K36.DEADLINE_S = 900
PROJECT = "Report-Limits-Evenness"


def _top(dlg) -> None:
    from PyQt6.QtGui import QTextCursor
    dlg._view.moveCursor(QTextCursor.MoveOperation.Start)
    dlg._view.verticalScrollBar().setValue(0)


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


def _quoted_lines(text: str) -> "list[str]":
    """Every quoted stretch that names a metric (it carries a Δ unit)."""
    flat = re.sub(r"\s+", " ", text)
    out = []
    for m in re.finditer(r"[“„]([^”“]*)[”“]", flat):
        if "Δ" in m.group(1):
            out.append(m.group(1))
    return out


def script(lang):
    def s(d):
        rec = d.record
        rec.update({"language": lang, "tree": TREE, "mode": "ON SCREEN"})
        K36._install_watchdog(d, rec)
        from PyQt6.QtGui import QDesktopServices
        QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
        import ui.dialogs.measurement_report_dialog as mrd
        from core.i18n import tr
        yield 500
        d.open_project(PROJECT)
        d.set_bar(run="run1", run_type="verification")
        d.pump(1200)
        d.launch_tool("measurement_report")
        yield 4500
        dlg = K36._wait(d, "MeasurementReportDialog")
        if dlg is None:
            rec["error"] = "no report window"
            d.note("NO REPORT WINDOW")
            return
        dlg.resize(1400, 980)
        yield 1500
        K45._pick_data(dlg._saved_combo, mrd.NEW_REPORT_KEY)
        yield 2000
        rec["type_set"] = K45._pick_data(dlg._type_combo,
                                         "t2_full_colour_check")
        yield 1500
        rec["set_set"] = K45._pick_data(dlg._set_combo, "custom_iso_12647_7")
        yield 1500
        rec["ticks"] = K45._tick(dlg, "all")
        yield 1500
        if not dlg._detail_check.isChecked():
            dlg._detail_check.setChecked(True)
            yield 800
        K36.EXPECTED.add("QMessageBox")
        d.later(dlg._generate_btn.click)
        yield 600
        rec["generate_question"] = d.answer(
            "neu" if lang == "de" else "new", f"{lang}-question",
            within_ms=4000)
        K36.EXPECTED.discard("QMessageBox")
        yield 9000
        rec["state"] = {"type": dlg._type_combo.currentText(),
                        "set": dlg._set_combo.currentText(),
                        "shown": dlg._saved_combo.currentText()}
        text = dlg._view.toPlainText()
        (d.out / f"{lang}-page.txt").write_text(text, encoding="utf-8")
        name = tr("Average ΔE00, all patches")
        marks = [
            ("p1-results", "", tr("Report Results")),
            ("p2-results-rows", tr("Report Results"), name),
            ("p3-guide", tr("How to read this report"), name),
            ("p4-evenness-guide", tr("How to read this report"),
             tr("Maximum ΔE00, between two of the nine sheet areas")),
            ("p5-overview", tr("Overview of Measurement Metrics"), name),
            ("p6-notes", tr("Report Results"), "1) "),
        ]
        done = []
        for key, anchor, needle in marks:
            if _show_after(dlg, anchor, needle):
                done.append(key)
                yield 900
                d.shot(dlg, f"{lang}-{key}")
        rec["photographed"] = done
        _top(dlg)
        keys = {}
        for gkey, chart in (("accuracy", getattr(dlg, "_trend_de", None)),
                            ("evenness", (getattr(dlg, "_trend_groups", {})
                                          or {}).get("evenness"))):
            if chart is not None and K45._tab_to(dlg, chart):
                yield 1500
                keys[gkey] = K45._key_text(dlg)
                d.shot(dlg, f"{lang}-g-{gkey}")
        rec["graph_keys"] = keys
        pdf = d.out / f"{lang}-report.pdf"
        pdf.unlink(missing_ok=True)
        K36.EXPECTED.add("QFileDialog")
        d.later(dlg._pdf_btn.click)
        yield 800
        rec["pdf_chosen"] = d.answer_file(pdf, f"{lang}-99-pdf-dialog",
                                          within_ms=8000)
        yield 8000
        K36.EXPECTED.discard("QFileDialog")
        rec["pdf"] = pdf.name if pdf.is_file() else None
        quoted = {"page": _quoted_lines(text),
                  "keys": [q for v in keys.values() if v
                           for q in _quoted_lines(v)]}
        if pdf.is_file():
            try:
                import pymupdf
                doc = pymupdf.open(str(pdf))
                ptxt = "\n".join(p.get_text() for p in doc)
                (d.out / f"{lang}-report-pdf.txt").write_text(
                    ptxt, encoding="utf-8")
                quoted["pdf"] = _quoted_lines(ptxt)
                # the pages that carry a limit-line key, as pictures
                shots = d.out / "pdf-pages"
                shots.mkdir(exist_ok=True)
                want = ("the limit for “", "Grenzwert für „")
                for i, page in enumerate(doc):
                    if any(w in page.get_text() for w in want):
                        page.get_pixmap(dpi=110).save(
                            str(shots / f"{lang}-pdf-page-{i + 1:02d}.png"))
            except Exception as exc:                  # noqa: BLE001
                rec["pdf_read_error"] = str(exc)
        from workflow.compliance_sets import ROWS
        labels = {tr(r.label) for r in ROWS}
        rec["quoted_not_a_label"] = sorted(
            {q for v in quoted.values() for q in v if q not in labels})
        (d.out / f"{lang}-quoted.json").write_text(
            json.dumps(quoted, indent=2, ensure_ascii=False),
            encoding="utf-8")
        d.note(f"   quoted names that are not a Report Limits label: "
               f"{rec['quoted_not_a_label']}")
        dlg.close()
        yield 2000
    return s


def main() -> int:
    out = Path(sys.argv[1])
    lang = sys.argv[2]
    d = Drive(out, projects=[PROJECT], language=lang)
    rc = d.run(script(lang))
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

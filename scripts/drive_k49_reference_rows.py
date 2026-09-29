#!/usr/bin/env python3
"""K49 (Knut, #182 5841092535): the paper row and the two solid rows compared
with the profile ((b2)), and a graph of a row with values but no limit shown
with its own sentence. Driven ON SCREEN, on any tree, so the same cases run
before and after the change.

    CHROMIQ_DEMO_PACK=<pack> CHROMIQ_TREE=<tree> \\
        python drive_k49_reference_rows.py <out> <en|de> <case> [<case> ...]

A case is ``tag:project:run:runtype:type_id:set_id:ticks`` as in
`drive_k45_pdf_layout.py`, whose steps this reuses: the report window from
the Tools menu entry, "New report…", the type, the set and the ticks,
Generate report. Then:

* the page is scrolled to the paper row, the solid rows and the notes, and
  the window photographed at each; the words, values and note numbers of the
  three rows, and every note, are read off the page as it is shown;
* every trend tab that is shown is brought to the front and photographed,
  with the sentence under the graph recorded;
* the PDF is saved through ChromIQ's own file dialog as ``<out>/<lang>-<tag>.pdf``.

**NOBODY HAS TO CLICK.** Every question the drive expects it answers itself; a
watchdog photographs and cancels anything else after three seconds; a deadline
ends the run whatever happens. The one thing replaced is
``QDesktopServices.openUrl``, so a saved PDF is not opened in a viewer. The
pack is copied, never written.
"""
from __future__ import annotations

import json
import os
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

K36.DEADLINE_S = 1500

#: The tabs photographed, by the dialog's own attribute or group key.
TABS = ("de", "white", "paper_diff", "black", "corners", "solids",
        "solid_hue", "grey", "tone", "strip", "gamut_edge", "repeat",
        "evenness")
#: The rows (b2) is about.
ROWS = ("substrate_de00_max", "solids_de00_max", "cmy_solids_dhab_max")


def _chart_for(dlg, key):
    fixed = {"de": "_trend_de", "white": "_trend_white",
             "black": "_trend_black", "corners": "_trend_corners"}
    if key in fixed:
        return getattr(dlg, fixed[key], None)
    return (getattr(dlg, "_trend_groups", {}) or {}).get(key)


def _key_text(dlg) -> "str | None":
    key = getattr(dlg, "_trend_key", None)
    return key.text() if key is not None and key.isVisible() else None


_ROW_WORDS = ("PASS", "FAIL", "N-A", "INFO", "–", "BESTANDEN",
              "NICHT BESTANDEN")


def _show_without_selection(view, cur) -> None:
    """Scroll *cur* into view and leave NO selection on the page.

    Challenge 2 of beta 44, finding 6 (B8-1278): `QTextBrowser.find()`
    selects what it finds, and this driver photographed the page with that
    selection on it, so the K49 pictures showed a blue highlight the app
    never makes. The cursor keeps its place; only the selection goes."""
    from PyQt6.QtGui import QTextCursor
    cur = QTextCursor(cur)
    cur.clearSelection()
    view.setTextCursor(cur)
    view.ensureCursorVisible()


def _scroll_to(dlg, text: str, row: bool = False) -> bool:
    """Bring the place *text* is printed on the page into view: the first,
    or with *row* the first in a results-table row (its cell carries a
    verdict word or a number), not the guide's list of metrics above it.
    The page is left with no selection (B8-1278)."""
    import re
    from PyQt6.QtGui import QTextCursor
    view = dlg._view
    view.moveCursor(QTextCursor.MoveOperation.Start)
    first = None
    while view.find(text):
        cur = view.textCursor()
        block = cur.block().text()
        table = cur.currentTable() is not None
        if first is None:
            first = QTextCursor(cur)
        if not row or (table and (any(w in block for w in _ROW_WORDS)
                                  or re.search(r"\d", block.replace(text, "")))):
            _show_without_selection(view, cur)
            return True
    if first is not None:
        _show_without_selection(view, first)
        return True
    _show_without_selection(view, view.textCursor())
    return False


def _page_lines(dlg, needles) -> "list[str]":
    """The lines of the page as shown that carry any of *needles*."""
    text = dlg._view.toPlainText()
    return [ln.strip() for ln in text.splitlines()
            if any(n and n in ln for n in needles)]


def script(cases, lang):
    def s(d):
        rec = d.record
        rec.update({"language": lang, "tree": TREE, "mode": "ON SCREEN",
                    "cases": {}})
        K36._install_watchdog(d, rec)
        from PyQt6.QtGui import QDesktopServices
        QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
        import ui.dialogs.measurement_report_dialog as mrd
        from core.i18n import tr
        from workflow.compliance_sets import ROW_BY_ID
        labels = {rid: tr(ROW_BY_ID[rid].label) for rid in ROWS}
        yield 500
        for c in cases:
            tag = f"{lang}-{c['tag']}"
            cr = rec["cases"].setdefault(c["tag"], dict(c))
            d.note(f"== case {tag}: {c}")
            d.open_project(c["project"])
            d.set_bar(run=c["run"], run_type=c["runtype"])
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
            cr["type_set"] = K45._pick_data(dlg._type_combo, c["type"])
            yield 1500
            if c["set"]:
                cr["set_set"] = K45._pick_data(dlg._set_combo, c["set"])
                yield 1500
            cr["ticks"] = K45._tick(dlg, c["ticks"])
            yield 1500
            if not dlg._detail_check.isChecked():
                dlg._detail_check.setChecked(True)
                yield 800
            K36.EXPECTED.add("QMessageBox")
            d.later(dlg._generate_btn.click)
            yield 600
            cr["generate_question"] = d.answer(
                "neu" if lang == "de" else "new", f"{tag}-question",
                within_ms=4000)
            K36.EXPECTED.discard("QMessageBox")
            yield 9000
            cr["state"] = {"type": dlg._type_combo.currentText(),
                           "set": dlg._set_combo.currentText(),
                           "shown": dlg._saved_combo.currentText()}
            # -- the three rows, on the page as shown
            cr["row_lines"] = {rid: _page_lines(dlg, [labels[rid]])
                               for rid in ROWS}
            n = 0
            for rid in ROWS:
                if _scroll_to(dlg, labels[rid], row=True):
                    yield 900
                    n += 1
                    d.shot(dlg, f"{tag}-r{n}-page-{rid}")
            # -- the notes under the table (their heading is the one place
            # the page lists them); photographed where the first one sits
            note_words = ("profile", "Profil")
            cr["note_lines"] = [ln for ln in _page_lines(dlg, note_words)
                                if ln[:3].strip().rstrip(")").isdigit()]
            if cr["note_lines"] and _scroll_to(dlg, cr["note_lines"][0][:40]):
                yield 900
                d.shot(dlg, f"{tag}-r9-page-notes")
            # -- the graphs
            tabs = dlg._trend_tabs
            cr["tabs_shown"] = [tabs.tabText(i) for i in range(tabs.count())
                                if tabs.isTabVisible(i)]
            cr["graphs"] = {}
            for k, key in enumerate(TABS, 1):
                chart = _chart_for(dlg, key)
                if chart is None or not K45._tab_to(dlg, chart):
                    continue
                yield 1200
                g = cr["graphs"].setdefault(key, {})
                g["title"] = tabs.tabText(tabs.indexOf(chart))
                g["legend"] = [lbl for lbl, _c, _a in chart._metrics]
                g["lines"] = [[v, w] for v, w, _c, _n in chart._lines()]
                g["descriptions"] = [[kind, t] for kind, _c, t
                                     in chart.descriptions()]
                g["window_key"] = _key_text(dlg)
                d.shot(dlg, f"{tag}-g{k:02d}-window-{key}")
            pdf = d.out / f"{tag}.pdf"
            pdf.unlink(missing_ok=True)
            K36.EXPECTED.add("QFileDialog")
            d.later(dlg._pdf_btn.click)
            yield 800
            cr["pdf_chosen"] = d.answer_file(pdf, f"{tag}-99-pdf-dialog",
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
    cases = K45._cases(sys.argv[3:])
    projects = sorted({c["project"] for c in cases})
    d = Drive(out, projects=projects, language=lang)
    rc = d.run(script(cases, lang))
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""B8-1476 (Knut, #182 5855259490 and 5855780690): the evenness filter, the
new limits, the converted ISO figures and their note, the help texts and the
presets window's "can be judged" line, driven ON SCREEN in the real app.

    CHROMIQ_DEMO_PACK=<folder holding Report-Limits-Evenness> \\
    CHROMIQ_LOG_DIR=<sandbox> \\
        python scripts/drive_b8_1476_evenness.py <out> <en|de> <light|dark>

What it photographs:

* the Report Limits window, scrolled to the evenness rows (the raised ⁴ on
  the two read-only ISO columns' cells) and to the notes under the table (the
  ⁴ note naming both standards' figures), opened as the window itself;
* the (i) of "Maximum ΔE00, between two of the nine sheet areas", clicked
  like a user clicks it (its own exec() runs), top and bottom of its text;
* a New report of Report-Limits-Evenness run1, Full colour check, ChromIQ
  default, every date: the two evenness rows in Report Results;
* "Which presets can be used for verification?" with Knut's 648-patch
  preset selected: the "This chart can be judged" line.

Every modal the drive does not expect is photographed and cancelled by the
watchdog; a deadline ends the run. The pack is copied, never written;
settings, presets and output are sandboxed by `userdrive`, the log by
CHROMIQ_LOG_DIR, the ISO file forced to the repository's own.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

TREE = os.environ.get("CHROMIQ_TREE") or str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402
import drive_k45_pdf_layout as K45                             # noqa: E402

K36.DEADLINE_S = 900
PROJECT = "Report-Limits-Evenness"
KNUTS_648 = "648p"


def script(lang: str, look: str):
    def s(d):
        rec = d.record
        rec.update({"language": lang, "appearance": look,
                    "mode": "ON SCREEN"})
        assert os.environ.get("CHROMIQ_LOG_DIR"), "SANDBOX THE LOG FIRST"
        K36._install_watchdog(d, rec)
        from core.i18n import tr
        from PyQt6.QtCore import Qt
        from ui.tooltip_button import TooltipButton
        from ui.dialogs.thresholds_dialog import ThresholdsDialog
        yield 600

        # 1. REPORT LIMITS: the window itself, on screen
        td = ThresholdsDialog(d.settings, d.win)
        td.resize(1480, 960)
        td.show()
        td.raise_()
        yield 2200
        lab = td._row_labels["uniformity_sd"]
        td._scroll.ensureWidgetVisible(lab, 0, 260)
        yield 900
        cells = {c: td._cells[(c, r)].text()
                 for c in ("iso_12647_7", "iso_12647_8")
                 for r in ("uniformity_sd",)}
        rec["iso_cells"] = cells
        d.shot(td, f"{lang}-{look}-01-limits-evenness-rows")
        td._scroll.verticalScrollBar().setValue(
            td._scroll.verticalScrollBar().maximum())
        yield 900
        rec["note"] = td._notes_text().split(ThresholdsDialog.CONVERTED_MARK
                                              + " ", 1)[-1][:900]
        d.shot(td, f"{lang}-{look}-02-limits-notes")

        # 2. THE (i) OF THE PAIRWISE ROW, clicked as a user clicks it
        td._scroll.ensureWidgetVisible(lab, 0, 260)
        yield 600
        btn = lab.parent().findChildren(TooltipButton)[0]
        K36.EXPECTED.add("_InfoDialog")
        d.later(btn.click)
        yield 1800
        info = d.modal()
        rec["info_open"] = type(info).__name__ if info else None
        if info is not None:
            info.resize(info.width(), 960)
            yield 700
            d.shot(info, f"{lang}-{look}-03-help-top")
            from PyQt6.QtWidgets import QScrollArea
            for sa in info.findChildren(QScrollArea):
                sb = sa.verticalScrollBar()
                sb.setValue(sb.maximum() // 2)
                yield 600
                d.shot(info, f"{lang}-{look}-04-help-middle")
                sb.setValue(sb.maximum())
                yield 600
                d.shot(info, f"{lang}-{look}-05-help-bottom")
                break
            info.close()
        K36.EXPECTED.discard("_InfoDialog")
        yield 800
        td.close()
        yield 800

        # 3. THE REPORT: run1, ChromIQ default, every date
        import ui.dialogs.measurement_report_dialog as mrd
        d.open_project(PROJECT)
        d.set_bar(run="run1", run_type="verification")
        d.pump(1200)
        d.launch_tool("measurement_report")
        yield 4500
        dlg = K36._wait(d, "MeasurementReportDialog")
        if dlg is None:
            rec["error"] = "no report window"
            return
        dlg.resize(1420, 980)
        yield 1500
        K45._pick_data(dlg._saved_combo, mrd.NEW_REPORT_KEY)
        yield 2000
        rec["type_set"] = K45._pick_data(dlg._type_combo,
                                         "t2_full_colour_check")
        yield 1200
        rec["set_set"] = K45._pick_data(dlg._set_combo, "chromiq_default")
        yield 1200
        rec["ticks"] = K45._tick(dlg, "all")
        yield 1500
        K36.EXPECTED.add("QMessageBox")
        d.later(dlg._generate_btn.click)
        yield 600
        rec["generate_question"] = d.answer(
            "neu" if lang == "de" else "new", f"{lang}-{look}-question",
            within_ms=4000)
        K36.EXPECTED.discard("QMessageBox")
        yield 9000
        from PyQt6.QtGui import QTextCursor
        view = dlg._view
        view.moveCursor(QTextCursor.MoveOperation.Start)
        view.find(tr("Report Results"))
        found = view.find(tr("Maximum ΔE00, between two of the nine sheet areas"))
        cur = QTextCursor(view.textCursor())
        cur.clearSelection()
        view.setTextCursor(cur)
        view.ensureCursorVisible()
        # the found row lands at the bottom edge, under the fade: bring it up
        sb = view.verticalScrollBar()
        sb.setValue(min(sb.maximum(), sb.value() + 260))
        rec["report_row_found"] = bool(found)
        yield 1000
        d.shot(dlg, f"{lang}-{look}-06-report-evenness-rows")
        text = view.toPlainText()
        (d.out / f"{lang}-{look}-report.txt").write_text(text, encoding="utf-8")
        dlg.close()
        yield 2000

        # 4. THE PRESETS WINDOW: Knut's 648-patch page
        d.goto_tab("chart")
        tab = d.win._tab_chart
        K36.EXPECTED.add("PresetVerificationDialog")
        d.later(tab._preset_verify_btn.click)
        yield 6000
        pv = K36._wait(d, "PresetVerificationDialog")
        if pv is None:
            rec["error_presets"] = "no presets window"
            return
        pv.resize(1450, 960)
        yield 1500
        tree = pv._tree
        target = None
        for i in range(tree.topLevelItemCount()):
            top = tree.topLevelItem(i)
            for j in range(top.childCount()):
                it = top.child(j)
                if KNUTS_648 in it.text(0) and "1page" in (
                        it.text(0).replace(" ", "").replace("-", "")):
                    target = it
                    break
            if target is None and KNUTS_648 in top.text(0):
                target = top
            if target is not None:
                break
        rec["preset"] = target.text(0) if target is not None else None
        if target is not None:
            tree.setCurrentItem(target)
            tree.scrollToItem(target)
        yield 4000
        from PyQt6.QtWidgets import QLabel
        pane = [w.text() for w in pv._detail.findChildren(QLabel)]
        rec["pane"] = pane
        judged = [t for t in pane if t.startswith(tr(
            "This chart can be judged on these metrics.").split(".")[0])]
        rec["judged_line"] = judged
        for w in pv._detail.findChildren(QLabel):
            if w.text() in judged:
                pv._detail_scroll.ensureWidgetVisible(w, 0, 120)
        yield 900
        d.shot(pv, f"{lang}-{look}-07-presets-window")
        pv.close()
        K36.EXPECTED.discard("PresetVerificationDialog")
        yield 1500
    return s


def main() -> int:
    out = Path(sys.argv[1])
    lang, look = sys.argv[2], sys.argv[3]
    d = Drive(out, projects=[PROJECT], language=lang, appearance=look)
    rc = d.run(script(lang, look))
    (out / f"{lang}-{look}-record.json").write_text(
        json.dumps(d.record, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

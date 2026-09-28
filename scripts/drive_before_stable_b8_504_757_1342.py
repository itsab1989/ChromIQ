#!/usr/bin/env python3
"""Before 4.3.0 stable: B8-504, B8-757 and B8-1342, driven ON SCREEN.

    CHROMIQ_DEMO_PACK=<pack> CHROMIQ_LOG_DIR=<sandbox> \\
        python scripts/drive_before_stable_b8_504_757_1342.py widths <lang> <out>
    CHROMIQ_DEMO_PACK=<pack> CHROMIQ_LOG_DIR=<sandbox> \\
        python scripts/drive_before_stable_b8_504_757_1342.py scenes <out>

``widths`` (one process per language, so every module-level string is in that
language from the start):

* B8-757: the main window at 1280 x 800, Create Chart in Manual with the
  ChromIQ layout engine's panel on screen and every section open. Every
  button, check box, radio button and single-line label whose own size hint
  is wider than the width it was given is recorded. Photographed.
* B8-504: the Measurement Report opened FRESH at 1000, 1200 and 1500 px wide
  (a new window each time, which is what a reader gets), and its minimum
  width read. Photographed at 1000.

``scenes`` (English):

* B8-1342: Report-Limits-Border-Conditions run3, a new report of ONE of its
  two raw checks, Generate: the Report Scope sentence, photographed.
* B8-711 / B8-724: the one-page summary (Colour summary) of the same run,
  generated and photographed at its Result sentence, and its PDF saved.

Every modal the drive does not expect is photographed and cancelled by the
watchdog. The pack is copied, never written.
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
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402
import drive_k45_pdf_layout as K45                             # noqa: E402

K36.DEADLINE_S = 900
K36.OURS = {n for n in K36.OURS if n != "_InfoDialog"}
BORDER = "Report-Limits-Border-Conditions"


def _clipped(root) -> list:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QCheckBox, QLabel, QPushButton, QRadioButton,
                                 QToolButton)
    out = []
    for w in root.findChildren((QPushButton, QToolButton, QCheckBox,
                                QRadioButton, QLabel)):
        if not w.isVisible() or w.width() <= 0:
            continue
        if isinstance(w, QToolButton) and \
                w.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly:
            continue
        text = (w.text() or "").replace("&", "")
        if not text or "\n" in text or "<" in text:
            continue
        if isinstance(w, QLabel):
            if w.wordWrap() or w.pixmap() is not None and not w.pixmap().isNull():
                continue
            hint = w.sizeHint().width()
        else:
            hint = w.minimumSizeHint().width()
        if hint > w.width() + 1:
            out.append({"type": type(w).__name__, "text": text,
                        "short_by": hint - w.width()})
    return out


def _widths_script(lang: str):
    def s(d):
        rec = d.record
        K36._install_watchdog(d, rec)
        from PyQt6.QtWidgets import QApplication
        yield 800
        # ---- B8-757: Create Chart Manual at 1280 x 800 --------------------
        print("step: goto chart", flush=True)
        d.goto_tab("chart")
        yield 800
        tab = d.win._tab_chart if hasattr(d.win, "_tab_chart") else None
        if tab is None:
            from ui.tabs.tab_chart import TabChart
            tab = next(iter(d.win.findChildren(TabChart)), None)
        print("step: manual", flush=True)
        tab._switch_mode("manual")
        box = getattr(tab, "_manual_engine_check", None)
        if box is not None:
            if not box.isChecked():
                box.setChecked(True)
            else:
                tab._on_manual_engine_toggled(True)
        yield 1500
        # i18n_onscreen_audit's open_every_section, inlined: that module
        # enables faulthandler on import, which a redirected run refuses.
        print("step: sections", flush=True)
        from ui.widgets import CollapsibleGroupBox
        for _ in range(4):
            shut = [g for g in tab.findChildren(CollapsibleGroupBox)
                    if g.isVisible() and g.is_collapsed()]
            for g in shut:
                g.set_collapsed(False)
            yield 600
            if not shut:
                break
        yield 1500
        panel = getattr(tab, "_manual_layout_panel", None)
        rec["engine_panel_on_screen"] = bool(panel is not None
                                             and panel.isVisible())
        rec["window_size"] = [d.win.width(), d.win.height()]
        print("step: measure", flush=True)
        rec["create_chart_clipped"] = _clipped(d.win)
        d.shot(d.win, f"757-{lang}-create-chart-manual-1280x800")
        # ---- B8-504: the report window, fresh at three widths -------------
        print("step: report", flush=True)
        d.open_project(BORDER)
        d.set_bar(run="run3", run_type="verification")
        yield 1500
        rec["report_min_width"] = {}
        for width in (1000, 1200, 1500):
            print("step: report", width, flush=True)
            d.launch_tool("measurement_report")
            yield 4500
            dlg = K36._wait(d, "MeasurementReportDialog")
            if dlg is None:
                rec["report_min_width"][str(width)] = "no window"
                continue
            dlg.resize(width, 860)
            yield 2500
            rec["report_min_width"][str(width)] = {
                "minimum": dlg.minimumSizeHint().width(),
                "actual": dlg.width(),
                "clipped": _clipped(dlg)}
            if width == 1000:
                d.shot(dlg, f"504-{lang}-report-window-1000")
            dlg.close()
            yield 1500
    return s


def _scenes_script():
    def s(d):
        rec = d.record
        K36._install_watchdog(d, rec)
        import ui.dialogs.measurement_report_dialog as mrd
        from PyQt6.QtCore import Qt
        yield 800
        d.open_project(BORDER)
        d.set_bar(run="run3", run_type="verification")
        yield 1500
        d.launch_tool("measurement_report")
        yield 4500
        dlg = K36._wait(d, "MeasurementReportDialog")
        if dlg is None:
            rec["error"] = "no report window"
            return
        dlg.resize(1420, 980)
        yield 2000
        # ---- B8-1342: a new report of ONE of the two raw checks -----------
        K45._pick_data(dlg._saved_combo, mrd.NEW_REPORT_KEY)
        yield 2000
        K45._pick_data(dlg._type_combo, "t2_full_colour_check")
        yield 1000
        rec["ticks_all"] = K45._tick(dlg, "all")
        yield 1000
        rows = [i for i, (kind, _si, _k) in enumerate(dlg._list_rows)
                if kind == "run"]
        rec["runs_listed"] = len(rows)
        if rows:
            dlg._profile_list.item(rows[0]).setCheckState(
                Qt.CheckState.Unchecked)
        yield 1500
        K36.EXPECTED.add("QMessageBox")
        d.later(dlg._generate_btn.click)
        yield 700
        rec["question"] = d.answer("new", None, within_ms=4000)
        K36.EXPECTED.discard("QMessageBox")
        yield 12000
        text = dlg._view.toPlainText()
        m = re.search(r"This report covers[^.]*\.", text)
        rec["scope_sentence"] = m.group(0) if m else None
        rec["says_covers_0"] = "covers 0 of" in text
        from drive_b8_1591_nothing_moves_before_generate import _scroll_to
        rec["scope_found"] = _scroll_to(d, dlg, "This report covers",
                                        "1342-raw-check-report-scope")
        # ---- B8-711 / B8-724: the one-page summary -------------------------
        K45._pick_data(dlg._type_combo, "t1_colour_summary")
        yield 1500
        K36.EXPECTED.add("QMessageBox")
        d.later(dlg._generate_btn.click)
        yield 700
        rec["summary_question"] = d.answer("new", None, within_ms=4000)
        K36.EXPECTED.discard("QMessageBox")
        yield 12000
        page = dlg._view.toPlainText()
        rec["summary_pointers"] = [p for p in ("listed below", "rows above",
                                               "note below") if p in page]
        d.shot(dlg, "711-724-one-page-summary")
        from drive_b8_1591_nothing_moves_before_generate import _pdf_text
        pdf = _pdf_text(d, dlg, "711-724-one-page-summary")
        rec["summary_pdf_written"] = bool(pdf)
        rec["summary_pdf_pointers"] = [p for p in ("listed below",
                                                   "rows above", "note below")
                                       if p in pdf]
        (d.out / "711-724-one-page-summary.txt").write_text(pdf,
                                                            encoding="utf-8")
        dlg.close()
        yield 2000
    return s


def main() -> int:
    mode = sys.argv[1]
    if mode == "widths":
        lang, out = sys.argv[2], Path(sys.argv[3])
        d = Drive(out, projects=[BORDER], language=lang, appearance="light",
                  size=(1280, 800))
        rc = d.run(_widths_script(lang))
    else:
        out = Path(sys.argv[2])
        d = Drive(out, projects=[BORDER], language="en", appearance="light")
        rc = d.run(_scenes_script())
    (out / "record.json").write_text(
        json.dumps(d.record, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

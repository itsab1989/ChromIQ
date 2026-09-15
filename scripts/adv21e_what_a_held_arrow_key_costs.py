#!/usr/bin/env python3
"""Adversary 21e — the cost of the rise walk with an arrow key HELD DOWN.

Round 10 measured the new ceiling walk at 29.5 ms and 45.2 ms by calling the
notice pass. This holds the "Bottom" spin box's up arrow down instead, at the
auto-repeat rate a key really produces, on the two sheets the brief names:

  * i1Pro, Custom 62 x 88 mm, patch-first, two lines at 36 pt over a 6 mm
    bottom margin -- the sheet where every one of the 120 grid points is
    probed, because the ceiling cannot be laid out;
  * Knut's CR30 Letter 792-patch straight preset.

Each step is timed twice: the notice pass on its own, and the whole
"Measured from Preview" refresh the app really runs for a turn of that box.

…and the second half is the state round 10's sweep did not cover: a PAPER
change that leaves the margins where they were.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtCore import Qt                                  # noqa: E402
from PyQt6.QtTest import QTest                               # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402
from onscreen_capture import capture_window                  # noqa: E402


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv21e-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)), ("language", "en"),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True),
                 ("auto_update_preview", True)):
        settings.set(k, v)
    QDialog.exec = lambda self: 1                    # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1620, 1080)
    win.show()
    win.raise_()
    pump(app, 2200)
    print("    window on screen:", win.isVisible(), flush=True)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 700)
    tab._user_switch_mode("manual")
    pump(app, 1400)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("adv21e")
    pump(app, 400)
    p = tab._manual_layout_panel

    def bottom_notice() -> str:
        got = [w for w in TabChart._engine_text_notes(tab)[1]
               if "into the patches" in w and "sheet text along the bottom" in w]
        return got[0] if got else ""

    results: dict = {}

    def hold_the_arrow(name: str, turns: int = 24) -> dict:
        """The up arrow, held. `QTest.keyClick` on the focused spin box is what
        an auto-repeat delivers; nothing here is cached between turns because
        every turn is a bottom margin the search has not seen."""
        p.margins["b"].setFocus()
        pump(app, 300)
        notes_ms, refresh_ms, seen = [], [], []
        for _i in range(turns):
            t0 = time.perf_counter()
            QTest.keyClick(p.margins["b"], Qt.Key.Key_Up)
            app.processEvents()
            t1 = time.perf_counter()
            n0 = time.perf_counter()
            said = bottom_notice()
            n1 = time.perf_counter()
            refresh_ms.append((t1 - t0) * 1000.0)
            notes_ms.append((n1 - n0) * 1000.0)
            seen.append(bool(said))
        row = {
            "turns": turns,
            "margin now": float(p.margins["b"].value()),
            "the notice pass, ms": {
                "median": round(statistics.median(notes_ms), 1),
                "worst": round(max(notes_ms), 1)},
            "the whole key press, ms": {
                "median": round(statistics.median(refresh_ms), 1),
                "worst": round(max(refresh_ms), 1)},
            "warned on": sum(seen),
        }
        print(f"    {name}: {row}", flush=True)
        results[name] = row
        return row

    # --- P1: the 120-point sheet -------------------------------------------
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 800)
    ci = p.paper.findData("__custom__")
    p.paper.setCurrentIndex(ci)
    pump(app, 500)
    p.custom_w.setValue(62)
    p.custom_h.setValue(88)
    pump(app, 600)
    p.layout_mode.setCurrentIndex(p.layout_mode.findData("patch_first"))
    pump(app, 600)
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.setChecked(False)
        pump(app, 400)
    for k, v in (("t", 12.0), ("b", 6.0), ("l", 12.0), ("r", 12.0)):
        p.margins[k].setValue(v)
    p.helper_markers_cb.setChecked(True)
    p.helper_markers_top_bottom.setChecked(True)
    p.helper_marker_edge.setValue(4.0)
    p.helper_marker_len.setValue(2.0)
    p.text_edge.setValue(4.0)
    p.chart_text.setText("ChromIQ adversary twenty one")
    p.stamp_command.setChecked(True)
    p.chart_text_size.setValue(36.0)
    pump(app, 1600)
    print("    P1 62x88 the notice now:", bottom_notice()[:140], flush=True)
    hold_the_arrow("P1 custom 62 x 88, the ceiling cannot be built")

    # --- P2: Knut's CR30 Letter preset -------------------------------------
    names = [p.preset.itemText(i) for i in range(p.preset.count())] \
        if hasattr(p, "preset") else []
    print("    presets on the panel:", len(names), flush=True)
    hit = [n for n in names if "CR30" in n and "Letter" in n]
    print("    CR30 Letter presets:", hit, flush=True)
    if hit:
        p.preset.setCurrentIndex(names.index(hit[0]))
        pump(app, 2000)
        p.chart_text.setText("ChromIQ adversary twenty one")
        p.stamp_command.setChecked(True)
        p.chart_text_size.setValue(36.0)
        if p.use_instr_margins.isChecked():
            p.use_instr_margins.setChecked(False)
            pump(app, 400)
        p.margins["b"].setValue(8.0)
        pump(app, 1600)
        print("    P2 the notice now:", bottom_notice()[:140], flush=True)
        hold_the_arrow("P2 " + hit[0])
    else:
        # …the CR30 preset is not in this build's pulldown; drive the same
        # geometry by hand rather than report a number from a sheet nobody has.
        p.instr.setCurrentIndex(p.instr.findData("CR30"))
        pump(app, 900)
        j = p.paper.findData("Letter")
        if j >= 0:
            p.paper.setCurrentIndex(j)
        pump(app, 700)
        p.layout_mode.setCurrentIndex(p.layout_mode.findData("patch_first"))
        pump(app, 600)
        if p.use_instr_margins.isChecked():
            p.use_instr_margins.setChecked(False)
            pump(app, 400)
        for k, v in (("t", 12.0), ("b", 8.0), ("l", 12.0), ("r", 12.0)):
            p.margins[k].setValue(v)
        p.chart_text_size.setValue(36.0)
        pump(app, 1600)
        print("    P2 CR30 Letter by hand, the notice now:",
              bottom_notice()[:140], flush=True)
        hold_the_arrow("P2 CR30 Letter, patch-first, 36 pt")

    capture_window(win, out / "E1-after-the-held-arrow.png")

    # --- P3: the state nobody swept — a PAPER change, margins untouched -----
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 900)
    p.layout_mode.setCurrentIndex(p.layout_mode.findData("area_first"))
    pump(app, 600)
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.setChecked(False)
        pump(app, 400)
    for k, v in (("t", 12.0), ("b", 6.0), ("l", 12.0), ("r", 12.0)):
        p.margins[k].setValue(v)
    p.chart_text.setText("ChromIQ 21")
    p.stamp_command.setChecked(True)
    p.chart_text_size.setValue(30.0)
    paper_rows = []
    for code in ("A4", "A3", "Letter", "A2", "127x178"):
        j = p.paper.findData(code)
        if j < 0:
            continue
        p.paper.setCurrentIndex(j)
        pump(app, 900)
        said = bottom_notice()
        r = tab._current_layout_recipe()
        row = {"paper": code, "margins b": float(p.margins["b"].value()),
               "recipe paper": r.paper, "recipe margin_b": r.margin_bottom,
               "notice": said[:200]}
        paper_rows.append(row)
        print("    P3", row["paper"], "b=", row["margins b"], "->",
              (said[:130] or "<quiet>"), flush=True)
    results["P3 a paper change with the margins left alone"] = paper_rows
    capture_window(win, out / "E2-after-the-paper-changes.png")

    (out / "adv21e.json").write_text(json.dumps(results, indent=2,
                                                ensure_ascii=False),
                                     encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

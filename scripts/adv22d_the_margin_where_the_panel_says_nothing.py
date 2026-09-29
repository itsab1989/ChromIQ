#!/usr/bin/env python3
"""Adversary 22d — the right margins where the panel is silent and the sheet
still cuts the note, and the ones where its number is simply wrong.

22c photographed the fault: the sheet stamps `targen -d2 -f609 … adv22c` and
the panel predicts `Chart layout adv22c`, 23 characters shorter. This walks the
right margin and, at each step, reads the notice twice: once as shipped, and
once with `_active_layout_name` answering None, which is exactly what
`_on_generate` hands the build.
"""
from __future__ import annotations

import json
import os
import re
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
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
from onscreen_capture import capture_window                       # noqa: E402


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv22d-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)), ("language", "en"),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True),
                 ("auto_update_preview", False)):
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
    tab._manual_target_name_edit.setText("adv22d")
    pump(app, 400)
    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 900)
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.setChecked(False)
        pump(app, 300)
    for k, v in (("t", 12.0), ("b", 14.0), ("l", 12.0), ("r", 18.0)):
        p.margins[k].setValue(v)
    p.helper_markers_cb.setChecked(False)
    p.text_edge.setValue(4.0)
    p.chart_text.setText("")
    p.stamp_command.setChecked(False)
    p.chart_text_size.setValue(14.0)
    tab._manual_stamp_cmd_check.setChecked(True)
    tab._manual_chart_notes_edit.setText("Canon Pro-1000 / Photo Rag 308")
    pump(app, 1500)
    tab._generate_btn.click()
    for _ in range(900):
        pump(app, 200)
        if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 2500)
    print("    chart built:", bool(getattr(tab, "_margin_tiffs", None)), flush=True)

    def cut_notice():
        a, _ = TabChart._engine_text_notes(tab)
        for s in a:
            if "cut off and replaced" in s:
                return s
        return ""

    def n_of(s):
        m = re.search(r"last (\d+) characters", s or "")
        return int(m.group(1)) if m else 0

    real = TabChart._active_layout_name
    rows = []
    for r_mm in [x / 2 for x in range(60, 11, -1)]:
        p.margins["r"].setValue(r_mm)
        pump(app, 120)
        shipped = cut_notice()
        TabChart._active_layout_name = lambda self: None
        try:
            truth = cut_notice()
        finally:
            TabChart._active_layout_name = real
        rows.append({"right_mm": r_mm, "shipped_n": n_of(shipped),
                     "truth_n": n_of(truth),
                     "shipped_fires": bool(shipped), "truth_fires": bool(truth)})
    TabChart._active_layout_name = real

    silent_but_cut = [r for r in rows if r["truth_fires"] and not r["shipped_fires"]]
    wrong_number = [r for r in rows
                    if r["shipped_fires"] and r["truth_fires"]
                    and r["shipped_n"] != r["truth_n"]]
    print("    right margins swept:", len(rows), flush=True)
    print("    PANEL SILENT WHILE THE SHEET CUTS:", len(silent_but_cut),
          [r["right_mm"] for r in silent_but_cut], flush=True)
    print("    PANEL WARNS WITH THE WRONG NUMBER:", len(wrong_number), flush=True)
    for r in wrong_number[:6]:
        print("      right", r["right_mm"], "mm: panel says", r["shipped_n"],
              "the sheet cuts", r["truth_n"], flush=True)

    # park on the worst silent one for the photograph
    if silent_but_cut:
        p.margins["r"].setValue(silent_but_cut[0]["right_mm"])
    elif wrong_number:
        p.margins["r"].setValue(wrong_number[0]["right_mm"])
    pump(app, 1200)
    ok, why = capture_window(win, out / "D1-the-silent-margin.png")
    print("    photograph:", ok, why, flush=True)
    (out / "adv22d.json").write_text(json.dumps(
        {"rows": rows, "silent_but_cut": silent_but_cut,
         "wrong_number": wrong_number}, indent=2), encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

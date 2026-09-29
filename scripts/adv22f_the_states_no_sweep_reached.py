#!/usr/bin/env python3
"""Adversary 22f — the bottom-text warning in the states no sweep has reached.

Rounds 10 and 11 swept about 16,000 recipes through
`margin_rise_that_clears_mm` and found no bad rise and no false denial. This
does not repeat that. It drives the TRANSITIONS instead:

  * Guided — the guard says the notices must stay silent there. Does Guided
    even own the boxes the messages would name?
  * the paper changed while the warning is on screen;
  * the run type switched while it is on screen (which reloads the run's own
    stored Create Chart settings over the panel);
  * and after each one, the remedy the message names is TYPED IN and the
    warning has to clear.
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv22f-"))
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

    rec = {}

    # ---- Guided: is there anything there for a notice to name? -------------
    tab._user_switch_mode("guided")
    pump(app, 1600)
    a_g, b_g = TabChart._engine_text_notes(tab)
    p = tab._manual_layout_panel
    rec["guided"] = {
        "mode": tab._mode_name(), "notices": len(a_g), "overlaps": len(b_g),
        "manual layout panel visible": bool(p.isVisible()),
        "Margins Bottom visible": bool(p.margins["b"].isVisible()),
        "Sheet text visible": bool(p.chart_text.isVisible()),
        "Print helper markers visible": bool(p.helper_markers_cb.isVisible()),
    }
    print("    GUIDED:", rec["guided"], flush=True)
    ok0, why0 = capture_window(win, out / "F0-guided.png")

    tab._user_switch_mode("manual")
    pump(app, 1400)
    tab._manual_target_name_edit.setText("adv22f")
    pump(app, 400)
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 900)
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.setChecked(False)
        pump(app, 300)
    for k, v in (("t", 12.0), ("b", 6.0), ("l", 12.0), ("r", 12.0)):
        p.margins[k].setValue(v)
    p.helper_markers_cb.setChecked(True)
    p.helper_markers_top_bottom.setChecked(True)
    p.text_edge.setValue(4.0)
    p.chart_text.setText("ChromIQ 22f")
    p.chart_text_size.setValue(36.0)
    pump(app, 1500)
    tab._generate_btn.click()
    for _ in range(900):
        pump(app, 200)
        if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 2500)

    def bottom():
        _a, over = TabChart._engine_text_notes(tab)
        for s in over:
            if "sheet text along the bottom" in s:
                return s
        return ""

    def rise(msg):
        m = re.search(r"by about ([0-9.]+) mm", msg or "")
        return float(m.group(1)) if m else None

    def check(tag, extra=None):
        msg = bottom()
        r = rise(msg)
        row = {"warning": msg, "rise": r,
               "paper": tab._current_layout_recipe().paper,
               "bottom_box": float(p.margins["b"].value()),
               "size_pt": float(p.chart_text_size.value())}
        if extra:
            row.update(extra)
        if r is not None:
            was = float(p.margins["b"].value())
            p.margins["b"].setValue(was + r)
            pump(app, 900)
            after = bottom()
            row["cleared_by_the_stated_rise"] = (after == "")
            row["still_says"] = after[:140]
            # a hair less must NOT clear it, or the number is not the smallest
            p.margins["b"].setValue(was + max(0.0, r - 0.6))
            pump(app, 900)
            row["a_0_6mm_smaller_rise_still_warns"] = bool(bottom())
            p.margins["b"].setValue(was)
            pump(app, 700)
        rec[tag] = row
        print("   ", tag, json.dumps(row, ensure_ascii=False)[:320], flush=True)

    check("A4, as built")

    # ---- the paper changed while the warning is on screen ------------------
    idx = p.paper.findData("A3")
    if idx >= 0:
        p.paper.setCurrentIndex(idx)
        pump(app, 1800)
        check("paper switched to A3 with the warning up")
        p.paper.setCurrentIndex(p.paper.findData("A4"))
        pump(app, 1600)
        check("and back to A4")

    # ---- the run type switched while the warning is on screen --------------
    bar = win._target_bar
    from core.measurement_target import (RUN_TYPE_VERIFICATION,
                                         RUN_TYPE_PROFILING)
    bar._type_combo.setCurrentIndex(
        bar._type_combo.findData(RUN_TYPE_VERIFICATION))
    pump(app, 2200)
    check("run type -> Verification", {"mode": tab._mode_name()})
    bar._type_combo.setCurrentIndex(
        bar._type_combo.findData(RUN_TYPE_PROFILING))
    pump(app, 2200)
    check("run type -> Profiling", {"mode": tab._mode_name()})

    ok, why = capture_window(win, out / "F1-after-the-transitions.png")
    print("    photographs:", ok0, ok, why0, why, flush=True)
    (out / "adv22f.json").write_text(
        json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

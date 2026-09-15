#!/usr/bin/env python3
"""Adversary 20c, in a REAL window, PHOTOGRAPHED.

F1  "NO BOTTOM MARGIN THIS SHEET ALLOWS WILL CLEAR IT" -- AND 36.5 mm DOES.

    Create Chart / Manual / layout engine, i1Pro, Paper = Custom 62 x 88 mm,
    "Prioritise patch size", helper markers on for top and bottom, sheet text
    plus the settings stamp (two lines) at 36 pt, margins 12 / 6 / 12 / 12
    with "Use instrument margins" unticked.

    The panel prints:

      "... No bottom margin this sheet allows will clear it: "Bottom" under
       "Margins (mm)" stops at 60 mm and even that leaves the text in the
       patches. Make the sheet text smaller under "Sheet text", or switch one
       of the two lines off."

    Type 36.5 into that very box and the warning is gone, and stays gone all
    the way to 47.0 mm, on a sheet that still lays out.

    This script drives the real widgets and photographs the panel before and
    after.
"""
from __future__ import annotations

import json, os, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import (QApplication, QDialog,      # noqa: E402
                             QMessageBox, QAbstractScrollArea)
from onscreen_capture import capture_window              # noqa: E402


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN"
    out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv20c-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)), ("language", "en"),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True),
                 ("auto_update_preview", True)):
        settings.set(k, v)
    QDialog.exec = lambda self: 1                   # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings); win.resize(1620, 1080)
    win.show(); win.raise_(); pump(app, 2200)
    print("    window on screen:", win.isVisible(), flush=True)

    win._tabs.setCurrentWidget(win._tab_chart); tab = win._tab_chart
    pump(app, 700); tab._user_switch_mode("manual"); pump(app, 1400)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("adv20c")
    pump(app, 400)
    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData("i1")); pump(app, 800)
    ci = p.paper.findData("__custom__")
    p.paper.setCurrentIndex(ci); pump(app, 500)
    p.custom_w.setValue(62); p.custom_h.setValue(88); pump(app, 600)
    j = p.layout_mode.findData("patch_first")
    assert j >= 0, "no patch-first entry in the Create layout pulldown"
    p.layout_mode.setCurrentIndex(j); pump(app, 600)
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.setChecked(False); pump(app, 400)
    for k, v in (("t", 12.0), ("b", 6.0), ("l", 12.0), ("r", 12.0)):
        p.margins[k].setValue(v)
    pump(app, 400)
    p.helper_markers_cb.setChecked(True)
    p.helper_markers_top_bottom.setChecked(True)
    p.helper_marker_edge.setValue(4.0)
    p.helper_marker_len.setValue(2.0)
    p.text_edge.setValue(4.0)
    p.chart_text.setText("ChromIQ adversary twenty")
    p.stamp_command.setChecked(True)
    p.chart_text_size.setValue(36.0)
    pump(app, 1600)

    # BUILD THE SHEET, because the message field is part of "Measured from
    # Preview" and there is nothing measured until a chart exists.
    tab._generate_btn.click()
    for _ in range(900):
        pump(app, 200)
        if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 2500)
    print("    chart built:", bool(getattr(tab, "_margin_tiffs", None)),
          flush=True)

    def on_the_panel() -> str:
        mp = getattr(tab, "_margin_panel", None)
        return mp._status.text() if mp is not None else ""

    r = tab._current_layout_recipe()
    print("    recipe:", r.instrument, r.paper, r.layout_mode,
          "margin_bottom", r.margin_bottom, "stamp", r.stamp_command,
          flush=True)

    def bottom_notice():
        """THE HEIGHT NOTICE ONLY. The WIDTH one starts with the same seven
        words ("The sheet text along the bottom is too wide for the paper"),
        and a filter that takes the first match of that prefix reads one as the
        other."""
        got = [w for w in TabChart._engine_text_notes(tab)[1]
               if "into the patches" in w and "sheet text along the bottom" in w]
        return got[0] if got else ""

    def every_notice():
        a, b = TabChart._engine_text_notes(tab)
        return list(a) + list(b)

    before = bottom_notice()
    print("    BEFORE (Bottom = 6.0 mm):\n      ", before, flush=True)
    # bring the "Margins (mm)" row into the same picture as the message
    try:
        sa, w = None, p.margins["b"]
        while w is not None:
            if isinstance(w, QAbstractScrollArea):
                sa = w; break
            w = w.parentWidget()
        if sa is not None:
            sa.ensureWidgetVisible(p.margins["b"], 50, 240); pump(app, 700)
    except Exception as e:                            # noqa: BLE001
        print("    scroll failed:", e)
    print("    ON THE PANEL:\n      ",
          on_the_panel().replace("\n", "\n       "), flush=True)
    capture_window(win, out / "F1-before-no-margin-will-clear-it.png")

    p.margins["b"].setValue(36.5); pump(app, 3000)
    tab._auto_regenerate_preview(); pump(app, 3000)
    after = bottom_notice()
    print("    ON THE PANEL AFTER:\n      ",
          on_the_panel().replace("\n", "\n       "), flush=True)
    print("    AFTER  (Bottom = 36.5 mm):\n      ",
          after or "<the height warning is GONE>", flush=True)
    for m in every_notice():
        print("      still on the panel:", m[:110], flush=True)
    capture_window(win, out / "F1-after-36-5-mm-clears-it.png")

    # …and it is not a one-point island: every grid point to 47.0 clears.
    stable = []
    for k in range(0, 22):
        mb = round(36.5 + 0.5 * k, 1)
        p.margins["b"].setValue(mb); pump(app, 120)
        stable.append((mb, bool(bottom_notice())))
    print("    the run of clear margins:",
          [m for m, warn in stable if not warn], flush=True)
    (out / "adv20c.json").write_text(json.dumps(
        {"before": before, "after": after, "stable": stable,
         "window_on_screen": True}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

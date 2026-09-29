#!/usr/bin/env python3
"""
Adversary 21g — RETRACTED. The two-point island was my own arithmetic.

21f reported eleven states where "No bottom margin this sheet allows will clear
it" is printed and a margin the reader can type does clear it. This script was
written to photograph one, and it could not: the sheet it drove clears at 43.0
through 54.0 mm and the panel names a 37.0 mm rise, correctly.

The cause was in 21f, not in the app. It measured the bottom line's box with

    sheet_text_line_mm(size, "", False, False, 300.0)

where `_engine_text_notes` measures it with the recipe's own face,
`r.chart_text_font` ("Inter"). An empty family gets PIL's fallback, and at the
same Size the two differ by nearly two millimetres (21.167 mm against 19.473),
which is enough to turn a run of nine clearing margins into a run of two.

21f re-run with the recipe's font: **3,723 overlapping states, 435 denials,
and not one of them has any margin the box holds that clears it.** The round-10
fix holds.

The script is kept because the sweep it drives is still the right sweep, and
because a round that only files its hits is not measuring itself.
"""
from __future__ import annotations

import json
import os
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
from PyQt6.QtWidgets import (QApplication, QDialog,        # noqa: E402
                             QMessageBox, QAbstractScrollArea)
from onscreen_capture import capture_window                 # noqa: E402


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv21g-"))
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
        tab._manual_target_name_edit.setText("adv21g")
    pump(app, 400)
    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 800)
    p.paper.setCurrentIndex(p.paper.findData("__custom__"))
    pump(app, 500)
    p.custom_w.setValue(62)
    p.custom_h.setValue(88)
    pump(app, 600)
    p.layout_mode.setCurrentIndex(p.layout_mode.findData("area_first"))
    pump(app, 600)
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.setChecked(False)
        pump(app, 400)
    for k, v in (("t", 6.0), ("b", 6.0), ("l", 6.0), ("r", 6.0)):
        p.margins[k].setValue(v)
    p.helper_markers_cb.setChecked(True)
    p.helper_markers_top_bottom.setChecked(True)
    p.text_edge.setValue(4.0)
    p.chart_text.setText("ChromIQ 21")
    p.stamp_command.setChecked(True)
    p.chart_text_size.setValue(16.0 * 72.0 / 25.4)      # 16.0 mm of type
    pump(app, 1800)

    tab._generate_btn.click()
    for _ in range(900):
        pump(app, 200)
        if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 2500)
    print("    chart built:", bool(getattr(tab, "_margin_tiffs", None)),
          flush=True)

    def bottom_notice() -> str:
        got = [w for w in TabChart._engine_text_notes(tab)[1]
               if "into the patches" in w and "sheet text along the bottom" in w]
        return got[0] if got else ""

    def on_the_panel() -> str:
        mp = getattr(tab, "_margin_panel", None)
        return mp._status.text() if mp is not None else ""

    def scroll_into_view():
        try:
            sa, w = None, p.margins["b"]
            while w is not None:
                if isinstance(w, QAbstractScrollArea):
                    sa = w
                    break
                w = w.parentWidget()
            if sa is not None:
                sa.ensureWidgetVisible(p.margins["b"], 50, 240)
                pump(app, 600)
        except Exception as e:                          # noqa: BLE001
            print("    scroll failed:", e, flush=True)

    before = bottom_notice()
    print("    BEFORE (Bottom = 6.0 mm):\n      ", before, flush=True)
    scroll_into_view()
    ok1, _ = capture_window(win, out / "G1-no-margin-will-clear-it.png")

    # …and the whole box, one grid point at a time, read off the panel.
    sweep = []
    for k in range(0, 109):
        mb = round(0.0 + 0.5 * k, 1)
        if mb > 60.0:
            break
        p.margins["b"].setValue(mb)
        pump(app, 60)
        sweep.append((mb, not bottom_notice()))
    clear = [mb for mb, ok in sweep if ok]
    print("    every bottom margin the box holds that CLEARS it:", clear,
          flush=True)

    p.margins["b"].setValue(46.5)
    pump(app, 1500)
    tab._auto_regenerate_preview()
    for _ in range(900):
        pump(app, 200)
        if tab._generate_btn.isEnabled():
            break
    pump(app, 2500)
    after = bottom_notice()
    print("    AFTER (Bottom = 46.5 mm):\n      ",
          after or "<the height warning is GONE>", flush=True)
    print("    ON THE PANEL:\n      ",
          on_the_panel().replace("\n", "\n       ")[:1200], flush=True)
    scroll_into_view()
    ok2, _ = capture_window(win, out / "G2-46-5-mm-clears-it.png")
    print("    photographs:", ok1, ok2, flush=True)

    (out / "adv21g.json").write_text(json.dumps(
        {"before": before, "after": after, "clear margins": clear,
         "sweep": sweep}, indent=2, ensure_ascii=False), encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

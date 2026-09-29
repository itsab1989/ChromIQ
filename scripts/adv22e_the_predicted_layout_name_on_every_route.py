#!/usr/bin/env python3
"""Adversary 22e — the predicted stamp line, on every route Generate can take.

The fix has to be true in BOTH directions: a plain targen build must predict the
targen line (the fault 22c photographed), and a chart laid out from an armed
patch set must still predict "Chart layout <name>" (Knut's ColorMunki report,
2026-09-13, which is why the field was set here at all).
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv22e-"))
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
    from ui.tabs.tab_chart import TabChart, TC918_PRESET_KEY
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
    tab._manual_target_name_edit.setText("adv22e")
    pump(app, 400)
    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 900)
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.setChecked(False)
        pump(app, 300)
    for k, v in (("t", 12.0), ("b", 14.0), ("l", 12.0), ("r", 12.0)):
        p.margins[k].setValue(v)
    p.helper_markers_cb.setChecked(False)
    p.chart_text.setText("")
    p.chart_text_size.setValue(14.0)
    tab._manual_stamp_cmd_check.setChecked(True)
    tab._manual_chart_notes_edit.setText("Canon Pro-1000 / Photo Rag 308")
    pump(app, 1200)

    rec = {}

    def snap(tag):
        rec[tag] = {
            "_active_layout_name": tab._active_layout_name(),
            "_predicted_chart_layout_name":
                tab._predicted_chart_layout_name(),
            "_current_ti1_path": str(getattr(tab, "_current_ti1_path", None)),
            "tc918_active": bool(getattr(tab, "_tc918_active", False)),
            "knut_active": bool(getattr(tab, "_knut_active", False)),
            "preset_ti1_path": str(getattr(tab, "_preset_ti1_path", None)),
            "gamut_active": bool(getattr(tab, "_gamut_active", False)),
        }
        print("   ", tag, rec[tag], flush=True)

    snap("fresh, nothing built")
    tab._generate_btn.click()
    for _ in range(900):
        pump(app, 200)
        if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 2500)
    snap("after an ordinary targen build")

    # --- the TC9.18 built-in: an armed patch set, targen is not run ---------
    entries = [(i, tab._preset_combo.itemText(i), tab._preset_combo.itemData(i))
               for i in range(tab._preset_combo.count())]
    for e in entries:
        print("    preset entry:", e, flush=True)
    rec["preset_entries"] = [[i, t, str(d)] for i, t, d in entries]
    from ui.tabs.tab_chart import KNUT_PRESETS_BY_KEY
    pick = next((i for i, t, d in entries
                 if d is not None and str(d) in KNUT_PRESETS_BY_KEY), None)
    if pick is None:
        pick = next((i for i, t, d in entries if d == TC918_PRESET_KEY), None)
    print("    picking built-in index:", pick, flush=True)
    if pick is not None:
        tab._preset_combo.setCurrentIndex(pick)
        tab._on_preset_activated(pick)     # the combo's own `activated` slot
        pump(app, 3500)
        snap("a bundled patch-set preset selected")

    ok, why = capture_window(win, out / "E1-tc918-selected.png")
    print("    photograph:", ok, why, flush=True)
    (out / "adv22e.json").write_text(json.dumps(rec, indent=2),
                                     encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

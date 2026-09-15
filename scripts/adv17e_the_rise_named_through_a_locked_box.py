#!/usr/bin/env python3
"""Adversary 17e / P2: the rise is worked out in a state the reader must leave.

Round 4 added `_locked_margins_note`: with "Use instrument margins" ticked the
four margin boxes are read-only, so the message now appends *"Untick it to type
your own margins."*

Nothing asked what unticking DOES. `instruments.geom_from_build_kwargs` sets
``margins_are_law = area_first or use_instrument_margins``, so in patch-first
the tick is part of the geometry: the number `margin_rise_that_clears_mm`
found was measured on a sheet that stops existing the moment the reader does
what the sentence beside it tells them to do.

Driven here: read the rise while the box is locked, unlock, type it, look.
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
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window                      # noqa: E402

PRESET = ("__chromiq_knut_cr30_letter_792p_2pages_portrait"
          "_w11_0mm_hexagonal_straight__")

import os as _os
UNTOUCHED = _os.environ.get("ADV17E_UNTOUCHED") == "1"


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def said(tab):
    panel = getattr(tab, "_margin_panel", None)
    last = getattr(panel, "_last_status", None) if panel is not None else None
    msgs = [m for m in ((last[1].get("overlap_warnings") or []) if last else [])
            if "along the bottom" in m]
    return [m for m in msgs if "runs into the patches" in m
            or "run into the patches" in m]


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17e-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True),
                 ("margin_violation_notify", True)):
        settings.set(k, v)
    assert settings.get("custom_output_path", "") == str(work)
    QDialog.exec = lambda self: 1                  # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings); win.resize(1620, 1060)
    win.show(); win.raise_(); pump(app, 2500)
    onscreen = bool(win.isVisible())
    print(f"    window on screen: {onscreen}", flush=True)
    win._tabs.setCurrentWidget(win._tab_chart); tab = win._tab_chart
    pump(app, 800); tab._user_switch_mode("manual"); pump(app, 1500)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("test")
    combo = tab._preset_combo
    i = combo.findData(PRESET); assert i >= 0
    combo.setCurrentIndex(i); combo.activated.emit(i); pump(app, 1500)
    for _ in range(400):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 800)
    panel = tab._manual_layout_panel

    def refresh():
        pump(app, 240); tab._update_margin_inspector(); pump(app, 360)
        return said(tab)

    res = {"window_on_screen": onscreen, "cases": []}
    panel.chart_text.setText("test")
    panel.stamp_command.setChecked(False)
    for mode in ("patch_first", "area_first"):
        panel.layout_mode.setCurrentIndex(panel.layout_mode.findData(mode))
        for pt in (24.0, 28.0, 32.0, 36.0, 40.0):
            # --- the locked state, which is `LayoutRecipe`'s own default -----
            # RESET FIRST. Unticking restores the margins that were in the
            # boxes when the tick went on, so a case that leaves a raised
            # margin behind poisons the next one.
            panel.use_instr_margins.setChecked(False); pump(app, 400)
            panel.margins["b"].setValue(6.0); pump(app, 300)
            panel.use_instr_margins.setChecked(True); pump(app, 500)
            panel.chart_text_size.setValue(pt)
            msgs = refresh()
            if not msgs:
                continue
            m = msgs[0]
            g = re.search(r"by about ([0-9.,]+) mm", m)
            if not g:
                continue
            rise = float(g.group(1).replace(",", "."))
            locked_b = panel.margins["b"].value()
            locked_enabled = panel.margins["b"].isEnabled()
            # --- the reader does exactly what the sentence says -------------
            # THE UNTOUCHED STATE. A preset that ships with the tick on leaves
            # `_saved_margins` None, so unticking changes no value at all and
            # the only thing that moves is `margins_are_law`. Emulated here so
            # the two causes can be told apart.
            if UNTOUCHED:
                panel._saved_margins = None
            panel.use_instr_margins.setChecked(False); pump(app, 600)
            restored_b = panel.margins["b"].value()
            # (a) type locked_b + rise
            panel.margins["b"].setValue(round(locked_b + rise, 1))
            after_a = refresh()
            # (b) type restored_b + rise, which is what the box now shows
            panel.margins["b"].setValue(round(restored_b + rise, 1))
            after_b = refresh()
            row = {"mode": mode, "size_pt": pt, "named_rise_mm": rise,
                   "bottom_box_enabled_while_locked": locked_enabled,
                   "bottom_mm_while_locked": locked_b,
                   "bottom_mm_after_untick": restored_b,
                   "still_warns_at_locked_plus_rise": bool(after_a),
                   "still_warns_at_shown_plus_rise": bool(after_b),
                   "message": m[:420],
                   "after_a": (after_a[0][:300] if after_a else None)}
            res["cases"].append(row)
            print(f"    {mode:11s} {pt:4.0f}pt rise={rise:5.1f} "
                  f"locked_b={locked_b} (enabled={locked_enabled}) "
                  f"after_untick_b={restored_b} -> "
                  f"warns at locked+rise: {bool(after_a)}; "
                  f"at shown+rise: {bool(after_b)}", flush=True)
            if after_a:
                panel.margins["b"].setValue(round(locked_b + rise, 1))
                refresh()
                capture_window(
                    win, out / f"STILL-WARNS-{'untouched-' if UNTOUCHED else ''}{mode}-{pt:.0f}pt.png")
    (out / ("adv17e-locked-box-rise-untouched.json" if UNTOUCHED
         else "adv17e-locked-box-rise.json")).write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("    written", flush=True)
    win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Adversary 21d — FROM PROFILE GAMUT and the panel that goes silent.

`_engine_text_notes` opens with

    manual = (self._manual_btn is not None and self._manual_btn.isChecked())
    if not (manual and …): return warns, over

and `_switch_mode("gamut")` does `self._manual_btn.setChecked(False)`.

The FROM PROFILE GAMUT module IS the Manual page with the targen group swapped
out (#133 §10): "Margins (mm)", "Sheet text", "Text distance from edge" and the
helper-marker boxes are Manual's own live widgets, the auto-update preview runs
there, and `_on_generate_gamut` builds the sheet from them. So every
text-overlap warning in "Measured from Preview" -- the four bottom-height
wordings this change set added among them -- is silent there, on a sheet those
very boxes lay out.

`_helper_marker_lines_frac`, eighty lines away in the same file, documents this
exact trap in twelve lines of comment and keys on `_current_mode()` for it:
*"that module leaves the mode BUTTON unchecked, so keying on the button froze
the overlay"*.

This drives it: the same layout, the same preview, once in each module.
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
from PyQt6.QtWidgets import (QApplication, QDialog,       # noqa: E402
                             QMessageBox, QAbstractScrollArea)
from onscreen_capture import capture_window                # noqa: E402


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv21d-"))
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
        tab._manual_target_name_edit.setText("adv21d")
    pump(app, 400)
    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 800)

    def set_the_colliding_layout():
        """The same boxes, whichever module is showing them."""
        if p.use_instr_margins.isChecked():
            p.use_instr_margins.setChecked(False)
            pump(app, 300)
        for k, v in (("t", 12.0), ("b", 6.0), ("l", 12.0), ("r", 12.0)):
            p.margins[k].setValue(v)
        p.helper_markers_cb.setChecked(True)
        p.helper_markers_top_bottom.setChecked(True)
        p.text_edge.setValue(4.0)
        p.chart_text.setText("ChromIQ 21")
        p.stamp_command.setChecked(False)
        p.chart_text_size.setValue(36.0)
        pump(app, 1600)

    def on_the_panel() -> str:
        mp = getattr(tab, "_margin_panel", None)
        return mp._status.text() if mp is not None else ""

    def bottom_line(text: str) -> str:
        for ln in text.split("\n"):
            if "into the patches" in ln and "sheet text along the bottom" in ln:
                return ln.strip()
        return ""

    def scroll_the_margins_into_view():
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
        except Exception as e:                        # noqa: BLE001
            print("    scroll failed:", e, flush=True)

    set_the_colliding_layout()
    tab._generate_btn.click()
    for _ in range(900):
        pump(app, 200)
        if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 2500)
    print("    chart built:", bool(getattr(tab, "_margin_tiffs", None)),
          flush=True)
    a, b = TabChart._engine_text_notes(tab)
    manual_panel = on_the_panel()
    print("    MANUAL  mode:", tab._mode_name(),
          " manual_btn:", tab._manual_btn.isChecked(),
          " notices:", len(a), "/", len(b), flush=True)
    print("      on the panel:", bottom_line(manual_panel)[:220], flush=True)
    scroll_the_margins_into_view()
    ok1, why1 = capture_window(win, out / "D1-manual-the-warning-is-there.png")

    # --- the target becomes a Verification, which is what shows the module ---
    bar = win._target_bar
    from core.measurement_target import RUN_TYPE_VERIFICATION
    bar._type_combo.setCurrentIndex(
        bar._type_combo.findData(RUN_TYPE_VERIFICATION))
    pump(app, 1800)
    print("    FROM PROFILE GAMUT button visible:",
          tab._gamut_btn.isVisible(), flush=True)
    tab._gamut_btn.click()                       # exactly as a reader clicks it
    pump(app, 2200)
    print("    mode now:", tab._mode_name(),
          " manual_btn:", tab._manual_btn.isChecked(),
          " gamut_btn:", tab._gamut_btn.isChecked(), flush=True)
    # …and the module's own live layout half gets the SAME sheet.
    set_the_colliding_layout()
    # THE PANEL'S OWN CHECKBOX, which is the cheapest thing on screen that
    # makes the inspector recompute: `_on_margin_measured_guides_toggled`
    # calls `_update_margin_inspector`, the same refresh a new preview runs.
    # No profile is needed for it, and the chart under it does not change.
    tab._margin_panel._measured_check.setChecked(
        not tab._margin_panel._measured_check.isChecked())
    pump(app, 2500)
    a2, b2 = TabChart._engine_text_notes(tab)
    gamut_panel = on_the_panel()
    r = tab._current_layout_recipe()
    live = {"layout panel visible": bool(p.isVisible()),
            "Margins Bottom enabled": bool(p.margins["b"].isEnabled()),
            "Margins Bottom": float(p.margins["b"].value()),
            "Sheet text": p.chart_text.text(),
            "Size pt": float(p.chart_text_size.value())}
    print("    the module's live layout controls:", live, flush=True)
    print("    the recipe it would build:", r.paper, r.layout_mode,
          "margin_bottom", r.margin_bottom, "size_mm", r.chart_text_size_mm,
          flush=True)
    print("    GAMUT   notices:", len(a2), "/", len(b2), flush=True)
    print("      on the panel:",
          (bottom_line(gamut_panel) or "<nothing about the bottom text>")[:220],
          flush=True)
    scroll_the_margins_into_view()
    ok2, why2 = capture_window(win, out / "D2-gamut-the-warning-is-gone.png")

    # --- and back, to prove nothing but the module changed -------------------
    tab._manual_btn.click()
    pump(app, 2000)
    set_the_colliding_layout()
    tab._margin_panel._measured_check.setChecked(
        not tab._margin_panel._measured_check.isChecked())
    pump(app, 2500)
    a3, b3 = TabChart._engine_text_notes(tab)
    back_panel = on_the_panel()
    print("    BACK IN MANUAL  notices:", len(a3), "/", len(b3), flush=True)
    print("      on the panel:", bottom_line(back_panel)[:220], flush=True)
    ok3, why3 = capture_window(win, out / "D3-manual-again-the-warning-is-back.png")
    print("    photographs:", ok1, ok2, ok3, why1, why2, why3, flush=True)

    (out / "adv21d.json").write_text(json.dumps({
        "manual": {"mode": "manual", "notices": [len(a), len(b)],
                   "bottom_line": bottom_line(manual_panel)},
        "gamut": {"mode": tab._mode_name(), "notices": [len(a2), len(b2)],
                  "bottom_line": bottom_line(gamut_panel),
                  "live_controls": live,
                  "recipe": {"paper": r.paper, "mode": r.layout_mode,
                             "margin_bottom": r.margin_bottom,
                             "size_mm": r.chart_text_size_mm}},
        "back": {"notices": [len(a3), len(b3)],
                 "bottom_line": bottom_line(back_panel)}},
        indent=2, ensure_ascii=False), encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

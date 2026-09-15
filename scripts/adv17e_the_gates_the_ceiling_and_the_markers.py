#!/usr/bin/env python3
"""Adversary 17e / P4-P6, driven in a real window.

P4  THE LAZY GATES CANNOT CHANGE AN ANSWER. `_bottom_lever_note` now takes its
    two gates as callables and asks only the one its branch reads. Over every
    state this driver visits, the note is built twice from the panel's own
    recipe -- once the way the call site does it, once with both gates run
    first and handed over as plain bools -- and the two are compared.

P5  THE CEILING. `_MARGIN_BOX_MAX_MM` is 60.0, hard-coded to mirror
    `layout_options_panel.small_mm(top=60.0)`. Read the box's own maximum in
    every preset and instrument this driver touches and compare.

P6  THE MARKER RESERVE. `build_kwargs` sends `helper_marker_edge_mm or 2.0`
    and `helper_marker_len_mm or 2.0` to the engine, while the panel's own
    prediction reads the recipe fields raw. A typed 0 therefore means 2.0 mm
    on the sheet and 0.0 mm in the warning.
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
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window                      # noqa: E402

PRESET = ("__chromiq_knut_cr30_letter_792p_2pages_portrait"
          "_w11_0mm_hexagonal_straight__")


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17e4-"))
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
    import ui.tabs.tab_chart as tc
    from workflow import text_edge_fit as tef
    from workflow.layout_engine import instruments, raster
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
    panel.use_instr_margins.setChecked(False); pump(app, 400)
    panel.chart_text.setText("test"); pump(app, 300)

    def refresh():
        pump(app, 200); tab._update_margin_inspector(); pump(app, 300)
        return said(tab)

    res = {"window_on_screen": onscreen, "p4": [], "p5": [], "p6": []}

    def note_both_ways(r):
        """The lever note as the call site builds it, and with both gates run
        first — the same two answers, asked in the two orders."""
        nlines = (1 if r.chart_text else 0) + (1 if r.stamp_command else 0)
        try:
            line_mm = raster.sheet_text_line_mm(
                float(getattr(r, "chart_text_size_mm", 0.0) or 0.0),
                str(getattr(r, "chart_text_font", "") or ""),
                bool(r.chart_text_bold), bool(r.chart_text_italic),
                float(r.dpi or 300))
        except Exception:
            line_mm = tef.SHEET_TEXT_LINE_MM
        bot = float(getattr(r, "effective_text_edge_mm", 4.0) or 4.0)
        anchor = tef.sheet_text_bottom_mm(
            bot, bool(r.helper_markers),
            float(r.helper_marker_edge_mm or 0.0),
            float(r.helper_marker_len_mm or 0.0),
            bool(r.helper_markers_top_bottom))
        typed = float(getattr(r, "text_edge_mm", 0.0) or 0.0)
        lazy = tc._bottom_lever_note(
            bot, anchor, lambda: tc.lowering_b_clears(r, nlines, line_mm),
            typed, lambda: tc.markers_off_clears(r, nlines, line_mm))
        e1 = tc.lowering_b_clears(r, nlines, line_mm)
        e2 = tc.markers_off_clears(r, nlines, line_mm)
        eager = tc._bottom_lever_note(bot, anchor, e1, typed, e2)
        return lazy, eager, anchor, bot

    # ---------------- P4 + P5 ------------------------------------------------
    for mode in ("area_first", "patch_first"):
        panel.layout_mode.setCurrentIndex(panel.layout_mode.findData(mode))
        for markers in (True, False):
            panel.helper_markers_cb.setChecked(markers)
            for b in (0.0, 1.0, 4.0, 7.0, 12.0):
                panel.text_edge.setValue(b)
                for mb in (6.0, 12.0, 20.0, 40.0, 60.0):
                    panel.margins["b"].setValue(mb)
                    for pt in (0.0, 24.0, 40.0, 72.0):
                        panel.chart_text_size.setValue(pt)
                        pump(app, 60)
                        r = tab._current_layout_recipe()
                        lazy, eager, anchor, bot = note_both_ways(r)
                        if lazy != eager:
                            res["p4"].append(
                                {"mode": mode, "markers": markers, "B": b,
                                 "margin_b": mb, "size_pt": pt,
                                 "lazy": lazy, "eager": eager})
                            print(f"    P4 DIFFERS {mode} markers={markers} "
                                  f"B={b} mb={mb} {pt}pt", flush=True)
    res["p4_states_compared"] = 2 * 2 * 5 * 5 * 4
    res["p4_differences"] = len(res["p4"])
    print(f"    P4: {res['p4_states_compared']} states, "
          f"{res['p4_differences']} where the lazy and eager notes differ",
          flush=True)

    # P5: the box's own ceiling, per instrument
    for k in range(panel.instr.count()):
        code = panel.instr.itemData(k)
        panel.instr.setCurrentIndex(k); pump(app, 350)
        res["p5"].append({"instrument": code,
                          "bottom_box_max": panel.margins["b"].maximum(),
                          "constant": tc._MARGIN_BOX_MAX_MM})
    bad = [x for x in res["p5"] if abs(x["bottom_box_max"] - tc._MARGIN_BOX_MAX_MM) > 1e-9]
    print(f"    P5: {len(res['p5'])} instruments, "
          f"{len(bad)} whose bottom box does not stop at "
          f"{tc._MARGIN_BOX_MAX_MM}", flush=True)

    # ---------------- P6: a marker box typed 0 ------------------------------
    panel.instr.setCurrentIndex(panel.instr.findData("CR30")); pump(app, 500)
    panel.layout_mode.setCurrentIndex(panel.layout_mode.findData("area_first"))
    panel.helper_markers_cb.setChecked(True)
    panel.text_edge.setValue(1.0)
    for e, L in ((0.0, 0.0), (0.0, 2.0), (2.0, 0.0), (2.0, 2.0), (4.0, 2.0)):
        panel.helper_marker_edge.setValue(e)
        panel.helper_marker_len.setValue(L)
        pump(app, 200)
        r = tab._current_layout_recipe()
        kw = r.build_kwargs()
        panel_mm = tef.sheet_text_bottom_mm(
            float(getattr(r, "effective_text_edge_mm", 4.0) or 4.0),
            bool(r.helper_markers), float(r.helper_marker_edge_mm or 0.0),
            float(r.helper_marker_len_mm or 0.0),
            bool(r.helper_markers_top_bottom))
        engine_mm = tef.sheet_text_bottom_mm(
            float(kw.get("text_edge") or 0.0), bool(kw.get("helper_markers")),
            float(kw.get("helper_marker_edge") or 0.0),
            float(kw.get("helper_marker_len") or 0.0),
            bool(kw.get("helper_markers_top_bottom", True)))
        row = {"typed_edge": e, "typed_len": L,
               "panel_predicts_mm": round(panel_mm, 3),
               "engine_reserves_mm": round(engine_mm, 3),
               "differ": abs(panel_mm - engine_mm) > 1e-6}
        res["p6"].append(row)
        print(f"    P6 edge={e} len={L}: panel {panel_mm:.2f} mm vs "
              f"engine {engine_mm:.2f} mm"
              f"{'   <-- DIFFER' if row['differ'] else ''}", flush=True)
    capture_window(win, out / "P6-marker-boxes-typed-zero.png")

    (out / "adv17e-gates-ceiling-markers.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("    written", flush=True)
    win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

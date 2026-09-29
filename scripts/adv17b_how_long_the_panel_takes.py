#!/usr/bin/env python3
"""Adversary 17b: what the bisection costs while a spin box is being turned.

`margin_rise_that_clears_mm` rebuilds the whole geometry about a dozen times,
and it runs inside `_engine_text_notes`, which `_update_margin_inspector` calls
on EVERY panel change. This times the real method in a real window, in the
warning state and out of it, and times the bisection on its own.
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
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

PRESET = ("__chromiq_knut_cr30_letter_792p_2pages_portrait"
          "_w11_0mm_hexagonal_straight__")


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17bt-"))
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
    print(f"    window on screen: {win.isVisible()}", flush=True)
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
    if panel.use_instr_margins.isChecked():
        panel.use_instr_margins.setChecked(False); pump(app, 400)
    panel.chart_text.setText("a bottom line of sheet text")
    panel.margins["b"].setValue(11.0)
    pump(app, 600)

    def time_notes(n=15):
        ts = []
        for _ in range(n):
            t0 = time.perf_counter()
            TabChart._engine_text_notes(tab)
            ts.append((time.perf_counter() - t0) * 1000.0)
        return ts

    rows = {}
    for label, pt, mode in (("quiet (auto size)", 0.0, "patch_first"),
                            ("quiet (auto size), area_first", 0.0, "area_first"),
                            ("WARNING (40 pt)", 40.0, "patch_first"),
                            ("WARNING (40 pt), area_first", 40.0, "area_first")):
        j = panel.layout_mode.findData(mode)
        panel.layout_mode.setCurrentIndex(j)
        panel.chart_text_size.setValue(pt)
        pump(app, 600)
        warns, over = TabChart._engine_text_notes(tab)
        warning = any("into the patches" in m for m in over)
        ts = time_notes()
        rows[label] = {"warning_showing": warning,
                       "median_ms": round(statistics.median(ts), 1),
                       "max_ms": round(max(ts), 1),
                       "min_ms": round(min(ts), 1)}
        print(f"    {label:32s} warning={warning}  "
              f"median {rows[label]['median_ms']} ms, max {rows[label]['max_ms']} ms",
              flush=True)

    # …and the bisection on its own, on the same recipe
    from ui.tabs.tab_chart import margin_rise_that_clears_mm
    from workflow.layout_engine.raster import sheet_text_line_mm
    from workflow import text_edge_fit as tef
    r = panel.get_recipe()
    line = sheet_text_line_mm(r.chart_text_size_mm, r.chart_text_font,
                              r.chart_text_bold, r.chart_text_italic, r.dpi)
    be = tef.sheet_text_bottom_mm(r.effective_text_edge_mm, r.helper_markers,
                                  r.helper_marker_edge_mm, r.helper_marker_len_mm,
                                  r.helper_markers_top_bottom)
    ts = []
    for _ in range(10):
        t0 = time.perf_counter()
        margin_rise_that_clears_mm(r, None, be, 1, line)
        ts.append((time.perf_counter() - t0) * 1000.0)
    rows["margin_rise_that_clears_mm alone"] = {
        "median_ms": round(statistics.median(ts), 1),
        "max_ms": round(max(ts), 1)}
    print(f"    the bisection alone: median {statistics.median(ts):.1f} ms, "
          f"max {max(ts):.1f} ms", flush=True)

    ok, why = capture_window(win, out / "04-panel-latency.png")
    (out / "how-long-the-panel-takes.json").write_text(
        json.dumps({"rows": rows,
                    "photo": "04-panel-latency.png" if ok else f"REFUSED {why}",
                    "locked": session_is_locked()}, indent=2), encoding="utf-8")
    print(f"    photo: {'ok' if ok else 'REFUSED ' + str(why)}", flush=True)
    win.close(); pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

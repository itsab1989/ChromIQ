#!/usr/bin/env python3
"""Adversary 21i — is 21f's two-point island a sheet the PANEL can produce?

21h drove the same nine fields into the panel and got a different sheet: 35
clearing margins where `replace()` on the recipe gives two. Something outside
those nine fields differs, and a probe that reports a fault from a recipe the
app cannot build is reporting its own arithmetic.

So: dump every field of the swept recipe against every field of the panel's,
and say which ones differ and whether a user can reach them.
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv21i-"))
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
    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 900)
    base = tab._current_layout_recipe()
    swept = replace(base, paper="62x88", layout_mode="area_first",
                    margin_bottom=6.0, chart_text_size_mm=16.0,
                    helper_markers=True, helper_markers_top_bottom=True,
                    stamp_command=True, chart_text="ChromIQ 21",
                    use_instrument_margins=False)

    p.paper.setCurrentIndex(p.paper.findData("__custom__"))
    pump(app, 500)
    p.custom_w.setValue(62)
    p.custom_h.setValue(88)
    pump(app, 900)
    p.layout_mode.setCurrentIndex(p.layout_mode.findData("area_first"))
    pump(app, 700)
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.setChecked(False)
        pump(app, 400)
    for k, v in (("t", swept.margin_top), ("r", swept.margin_right),
                 ("b", 6.0), ("l", swept.margin_left)):
        p.margins[k].setValue(float(v))
    p.helper_markers_cb.setChecked(True)
    p.helper_markers_top_bottom.setChecked(True)
    p.chart_text.setText("ChromIQ 21")
    p.stamp_command.setChecked(True)
    p.chart_text_size.setValue(16.0 * 72.0 / 25.4)
    pump(app, 1800)
    live = tab._current_layout_recipe()

    diffs = []
    for f in dataclasses.fields(swept):
        a, b = getattr(swept, f.name), getattr(live, f.name)
        if isinstance(a, float) and isinstance(b, float):
            if abs(a - b) < 1e-6:
                continue
        elif a == b:
            continue
        diffs.append((f.name, a, b))
    print("    FIELDS THAT DIFFER (swept -> on the panel):", flush=True)
    for name, a, b in diffs:
        print(f"        {name}: {a!r}  ->  {b!r}", flush=True)

    # …and which of them is what moves the answer.
    from ui.tabs import tab_chart as tc
    from workflow import text_edge_fit as tef
    from workflow.layout_engine import instruments as im
    from workflow.layout_engine.raster import sheet_text_line_mm

    def clear_set(r, size_mm):
        line = sheet_text_line_mm(size_mm, "", False, False, 300.0)
        edge = tef.sheet_text_bottom_mm(r.effective_text_edge_mm, True,
                                        *tc._marker_reserve_args(r), True)
        got = []
        for k in range(0, 121):
            mb = round(0.5 * k, 1)
            c = replace(r, margin_bottom=mb)
            try:
                g = im.geom_from_build_kwargs(c.build_kwargs())
            except Exception:                             # noqa: BLE001
                continue
            b = tc.predicted_patch_bottom_mm(c, g)
            if b is None:
                continue
            if tef.bottom_text_block_overlap(float(b), edge, 2, line) is None:
                got.append(mb)
        return got

    print("    swept recipe clears at:", clear_set(swept, 16.0), flush=True)
    print("    panel recipe clears at:",
          clear_set(live, live.chart_text_size_mm), flush=True)
    # one field at a time, from the panel's recipe back toward the swept one
    for name, a, _b in diffs:
        try:
            trial = replace(live, **{name: a})
        except Exception:                                 # noqa: BLE001
            continue
        got = clear_set(trial, trial.chart_text_size_mm)
        if len(got) < 5:
            print(f"    putting {name} back to {a!r} collapses it to {got}",
                  flush=True)

    # --- AND WHAT PRESSING GENERATE CHART DOES TO IT ------------------------
    # 21h swept the same sheet AFTER building and got 35 clearing margins.
    # A build re-derives the area grid from the chart it actually laid out, so
    # the recipe under the panel is not the one that was on it.
    before_build = {f.name: getattr(live, f.name)
                    for f in dataclasses.fields(live)}
    tab._generate_btn.click()
    for _ in range(900):
        pump(app, 200)
        if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 2500)
    built = tab._current_layout_recipe()
    moved = []
    for f in dataclasses.fields(built):
        a, b = before_build[f.name], getattr(built, f.name)
        if isinstance(a, float) and isinstance(b, float):
            if abs(a - b) < 1e-6:
                continue
        elif a == b:
            continue
        moved.append((f.name, a, b))
    print("    GENERATE CHART moved these recipe fields:", flush=True)
    for name, a, b in moved:
        print(f"        {name}: {a!r}  ->  {b!r}", flush=True)
    print("    after the build it clears at:",
          clear_set(built, built.chart_text_size_mm), flush=True)
    print("    and the search then answers:",
          tc.margin_rise_that_clears_mm(
              built, None,
              tef.sheet_text_bottom_mm(built.effective_text_edge_mm, True,
                                       *tc._marker_reserve_args(built), True),
              2, sheet_text_line_mm(built.chart_text_size_mm, "", False,
                                    False, 300.0), hint_mm=1.0), flush=True)

    (out / "adv21i.json").write_text(json.dumps(
        {"diffs": [[n, repr(a), repr(b)] for n, a, b in diffs],
         "moved by the build": [[n, repr(a), repr(b)] for n, a, b in moved]}, indent=2),
        encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

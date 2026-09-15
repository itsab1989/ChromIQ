#!/usr/bin/env python3
"""
Adversary 21h — the state named exactly, and the error found in the prober.

21g could not reproduce 21f's two-point island, so this one writes out every
field of the swept recipe, drives the panel to match it field by field, and
compares. The nine fields matched; the answer still differed.

The difference was the FONT the prober measured the line with, not anything in
the app: see `adv21g`'s docstring and `adv21j`, which asks every margin on the
box for one of three answers instead of two. 21f re-run with the recipe's own
face finds no false denial in 435.

Kept as the record of how the retraction was reached.
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv21h-"))
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
        tab._manual_target_name_edit.setText("adv21h")
    pump(app, 400)
    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 900)
    base = tab._current_layout_recipe()

    from ui.tabs import tab_chart as tc
    from workflow import text_edge_fit as tef
    from workflow.layout_engine import instruments as im
    from workflow.layout_engine.raster import sheet_text_line_mm

    # THE STATE 21f FOUND, from the panel's own defaults, exactly as swept.
    r = replace(base, paper="62x88", layout_mode="area_first",
                margin_bottom=6.0, chart_text_size_mm=16.0,
                helper_markers=True, helper_markers_top_bottom=True,
                stamp_command=True, chart_text="ChromIQ 21",
                use_instrument_margins=False)
    print("    THE RECIPE, FIELD BY FIELD:", flush=True)
    for f in dataclasses.fields(r):
        v = getattr(r, f.name)
        if v not in (None, "", 0, 0.0, False):
            print(f"        {f.name} = {v!r}", flush=True)

    n = 2
    line = sheet_text_line_mm(16.0, "", False, False, 300.0)
    edge = tef.sheet_text_bottom_mm(r.effective_text_edge_mm, True,
                                    *tc._marker_reserve_args(r), True)

    def clears(mb):
        c = replace(r, margin_bottom=mb)
        try:
            g = im.geom_from_build_kwargs(c.build_kwargs())
        except Exception:                                # noqa: BLE001
            return None
        b = tc.predicted_patch_bottom_mm(c, g)
        if b is None:
            return None
        return tef.bottom_text_block_overlap(float(b), edge, n, line) is None

    grid = [round(0.5 * k, 1) for k in range(0, 121)]
    verdict = {mb: clears(mb) for mb in grid}
    clear = [mb for mb, v in verdict.items() if v is True]
    unbuildable = [mb for mb, v in verdict.items() if v is None]
    print("    line box:", round(line, 3), "mm   anchor:", round(edge, 3),
          "mm", flush=True)
    print("    margins that CLEAR it:", clear, flush=True)
    print("    margins the sheet cannot lay out:",
          unbuildable[:6], "…", len(unbuildable), flush=True)
    said = tc.margin_rise_that_clears_mm(
        r, None, edge, n, line,
        hint_mm=tef.bottom_text_block_overlap(
            float(tc.predicted_patch_bottom_mm(
                r, im.geom_from_build_kwargs(r.build_kwargs()))),
            edge, n, line).overlap_mm)
    print("    what the shipping search answers:", said, flush=True)

    # --- and now the same sheet in the panel, box by box --------------------
    p.paper.setCurrentIndex(p.paper.findData("__custom__"))
    pump(app, 500)
    p.custom_w.setValue(62)
    p.custom_h.setValue(88)
    pump(app, 700)
    p.layout_mode.setCurrentIndex(p.layout_mode.findData("area_first"))
    pump(app, 600)
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.setChecked(False)
        pump(app, 400)
    for k, v in (("t", r.margin_top), ("r", r.margin_right),
                 ("b", 6.0), ("l", r.margin_left)):
        p.margins[k].setValue(float(v))
    p.helper_markers_cb.setChecked(True)
    p.helper_markers_top_bottom.setChecked(True)
    p.helper_marker_edge.setValue(float(r.helper_marker_edge_mm or 0.0))
    p.helper_marker_len.setValue(float(r.helper_marker_len_mm or 0.0))
    p.text_edge.setValue(float(r.text_edge_mm or 0.0))
    p.chart_text.setText("ChromIQ 21")
    p.stamp_command.setChecked(True)
    p.chart_text_size.setValue(16.0 * 72.0 / 25.4)
    pump(app, 1800)
    on_panel = tab._current_layout_recipe()
    same = all(getattr(on_panel, k) == getattr(r, k) for k in
               ("paper", "layout_mode", "margin_bottom", "margin_top",
                "margin_left", "margin_right", "helper_markers",
                "helper_markers_top_bottom", "stamp_command",
                "use_instrument_margins"))
    print("    the panel's recipe matches the swept one:", same,
          " size_mm on the panel:", round(on_panel.chart_text_size_mm, 3),
          flush=True)

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
    ok1, _ = capture_window(win, out / "H1-no-margin-will-clear-it.png")

    sweep = []
    for k in range(0, 121):
        mb = round(0.5 * k, 1)
        if mb > 60.0:
            break
        p.margins["b"].setValue(mb)
        pump(app, 60)
        sweep.append((mb, not bottom_notice()))
    on_screen_clear = [mb for mb, ok in sweep if ok]
    print("    every bottom margin the box holds that CLEARS it, on screen:",
          on_screen_clear, flush=True)

    target = on_screen_clear[0] if on_screen_clear else 46.5
    p.margins["b"].setValue(target)
    pump(app, 1500)
    tab._auto_regenerate_preview()
    for _ in range(900):
        pump(app, 200)
        if tab._generate_btn.isEnabled():
            break
    pump(app, 2500)
    after = bottom_notice()
    print(f"    AFTER (Bottom = {target} mm):\n      ",
          after or "<the height warning is GONE>", flush=True)
    print("    ON THE PANEL:\n      ",
          on_the_panel().replace("\n", "\n       ")[:1000], flush=True)
    scroll_into_view()
    ok2, _ = capture_window(win, out / "H2-the-margin-that-clears-it.png")
    print("    photographs:", ok1, ok2, flush=True)

    (out / "adv21h.json").write_text(json.dumps(
        {"predicted clear": clear, "search answered": said,
         "on screen clear": on_screen_clear, "before": before,
         "after": after, "target": target}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

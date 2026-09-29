#!/usr/bin/env python3
"""The one state Knut describes: CR30 warns, SpectroScan says nothing.

A sweep of his own recipe over the top margin finds it at 10 mm and 12 mm: the
CR30's strip letters reach 12.4 mm down the page and the SpectroScan's reach
10.1 mm, because the two instruments carry a different strip-label text height
(7.0 mm against 5.0 mm), so at a 12 mm top margin one set of letters is on the
patches and the other is not.

WHETHER THAT IS A FAULT IS DECIDED BY THE INK, not by the arithmetic that
produced the notice. This builds both sheets in the real window and then
measures the rendered TIFF: where the letters' ink ends, where the patch ink
begins, and whether there is clear paper between them.
"""
from __future__ import annotations

import json
import os
import shutil
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
from onscreen_capture import capture_window                      # noqa: E402

CHART = Path.home() / "Desktop/ChromIQ-beta22-proof/knut-chart-warnings/chart"
TOP_MM = float(os.environ.get("B22_TOP_MM", "12.0"))
T_MM = float(os.environ.get("B22_T_MM", "4.0"))


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def ink_rows(tif: Path):
    """``(first inked row mm, the white gaps)`` down the top of the sheet."""
    import numpy as np
    import tifffile
    a = tifffile.imread(str(tif))
    if a.ndim == 3:
        a = a.min(axis=2)
    dpi = 200.0
    inked = (a < 250).any(axis=1)
    rows = np.flatnonzero(inked)
    if rows.size == 0:
        return None
    # every run of inked rows in the top third of the page
    runs, start = [], rows[0]
    for i in range(1, rows.size):
        if rows[i] != rows[i - 1] + 1:
            runs.append((start, rows[i - 1]))
            start = rows[i]
    runs.append((start, rows[-1]))
    return [(round(a0 * 25.4 / dpi, 3), round(a1 * 25.4 / dpi, 3))
            for a0, a1 in runs[:6]]


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    rec_d = json.loads((CHART / "meta.json").read_text(encoding="utf-8"))["create_chart_ui"]["engine_recipe"]
    rec_d = dict(rec_d, margin_top=TOP_MM, text_edge_top_mm=T_MM)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b22-div-"))
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
    from workflow.layout_engine.presets import LayoutRecipe
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1680, 1100)
    win.show()
    win.raise_()
    pump(app, 2400)
    print("    window on screen:", win.isVisible(), flush=True)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("knut-div")
    pump(app, 400)
    p = tab._manual_layout_panel
    p.set_recipe(LayoutRecipe.from_dict(rec_d))
    pump(app, 2000)
    tab._preset_ti1_path = CHART / "test.ti1"
    tab._preset_ti1_targen_sig = None
    pump(app, 400)

    result = {}
    for key in ("CR30", "SS"):
        p.instr.setCurrentIndex(p.instr.findData(key))
        pump(app, 1200)
        p.margins["t"].setValue(TOP_MM)
        p.text_edge_top.setValue(T_MM)
        pump(app, 900)
        tab._generate_btn.click()
        for _ in range(1200):
            pump(app, 200)
            if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
                break
        pump(app, 3000)
        warns, over = TabChart._engine_text_notes(
            tab, getattr(tab, "_margin_report", None))
        rep = getattr(tab, "_margin_report", None)
        tif = Path(list(getattr(tab, "_margin_tiffs", []) or [])[0])
        keep = out / f"{key}-top{TOP_MM:.0f}-T{T_MM:.0f}.tif"
        shutil.copy2(tif, keep)
        runs = ink_rows(keep)
        strip = [s for s in over if "strip letters" in s]
        print(f"    [{key}] top box {p.margins['t'].value()} mm  "
              f"measured top {rep.top_mm if rep else None} mm", flush=True)
        print(f"    [{key}] red notices: {len(over)}   strip-letter notice: "
              f"{'YES' if strip else 'NO'}", flush=True)
        if strip:
            print("        " + strip[0][:230], flush=True)
        print(f"    [{key}] ink runs down the page (mm, first six): {runs}",
              flush=True)
        ok, why = capture_window(win, out / f"D-{key}-top{TOP_MM:.0f}-T{T_MM:.0f}.png")
        result[key] = {"top_box": p.margins["t"].value(),
                       "measured_top": rep.top_mm if rep else None,
                       "strip_notice": strip[0] if strip else None,
                       "all_red": over, "ink_runs_mm": runs,
                       "tiff": str(keep), "captured": ok, "why": why}
    (out / "divergence.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

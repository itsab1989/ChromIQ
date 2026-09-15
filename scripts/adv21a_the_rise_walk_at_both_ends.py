#!/usr/bin/env python3
"""Adversary 21a — the rise search, attacked at BOTH ends, in a REAL window.

Round 10 taught `margin_rise_that_clears_mm` to walk the whole grid before it
denies. This script opens the real Create Chart panel on screen, takes the
panel's OWN recipe, and then asks the shipping function the four questions the
brief names:

  I1  a rise it names must really clear, on the sheet the reader will be on
      (the tick off, because the function itself unticks it).
  I2  a rise it names is never 0.0 mm, which is the wording the code says is
      "not one of the four cases".
  I3  when it denies ("No bottom margin this sheet allows will clear it"),
      brute-force every grid point from 0 to the cap and see whether one of
      them, with the same two-clear-points-above rule, clears.
  I4  a candidate margin the sheet CANNOT lay out must never be read as a
      success by `_bottom_clears_with`, `lowering_b_clears`,
      `markers_off_clears` or `_larger_paper_note`.

Everything is measured against the shipping functions, in the process that has
a real window on screen.
"""
from __future__ import annotations

import itertools
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
from onscreen_capture import capture_window                      # noqa: E402


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv21a-"))
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
    pump(app, 600)
    tab._user_switch_mode("manual")
    pump(app, 1400)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("adv21a")
    pump(app, 400)
    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 900)
    base = tab._current_layout_recipe()
    print("    base recipe:", base.instrument, base.paper, base.layout_mode,
          flush=True)
    ok, why = capture_window(win, out / "A-the-panel-on-screen.png")
    print("    photographed:", ok, why, flush=True)

    # --- the shipping functions, imported once ------------------------------
    from ui.tabs import tab_chart as tc
    from workflow import text_edge_fit as tef
    from workflow.layout_engine import instruments as instr_mod

    STEP = tc._MARGIN_STEP_MM
    CAP_BOX = tc._MARGIN_BOX_MAX_MM

    def notice_inputs(r):
        """Exactly what `_engine_text_notes` computes before the height check."""
        nlines = (1 if r.chart_text else 0) + (1 if r.stamp_command else 0)
        from workflow.layout_engine.raster import sheet_text_line_mm
        line_mm = sheet_text_line_mm(
            float(getattr(r, "chart_text_size_mm", 0.0) or 0.0),
            str(getattr(r, "chart_text_font", "") or ""),
            bool(getattr(r, "chart_text_bold", False)),
            bool(getattr(r, "chart_text_italic", False)),
            float(getattr(r, "dpi", 300) or 300))
        b_edge = tef.sheet_text_bottom_mm(
            r.effective_text_edge_mm,
            bool(getattr(r, "helper_markers", False)),
            *tc._marker_reserve_args(r),
            bool(getattr(r, "helper_markers_top_bottom", True)))
        return nlines, line_mm, b_edge

    def patch_bottom(r):
        try:
            geom = instr_mod.geom_from_build_kwargs(r.build_kwargs())
        except Exception:                              # noqa: BLE001
            return "unbuildable"
        return tc.predicted_patch_bottom_mm(r, geom)

    def clears_at(r_unlocked, asked, delta, reserve, nlines, line_mm):
        """Brute-force `clears` — the same arithmetic, no cache, no exception
        swallowing beyond what the shipping code does."""
        cand = replace(r_unlocked, margin_bottom=asked + delta)
        pb = patch_bottom(cand)
        if pb is None or pb == "unbuildable":
            return False
        return tef.bottom_text_block_overlap(
            float(pb), reserve, nlines, line_mm) is None

    def brute_answer(r, reserve, nlines, line_mm):
        """The whole grid, with the shipping stability rule."""
        ru = (replace(r, use_instrument_margins=False)
              if bool(getattr(r, "use_instrument_margins", False)) else r)
        asked = float(getattr(ru, "margin_bottom", 0.0) or 0.0)
        cap = min(60.0, CAP_BOX - asked)
        if cap <= 0:
            return None, []
        grid = [round(i * STEP, 1) for i in range(int(cap / STEP) + 1)]
        vals = [clears_at(ru, asked, d, reserve, nlines, line_mm) for d in grid]
        run = 0
        first = None
        for d, v in zip(grid, vals):
            if v:
                run += 1
                if run == 3 and first is None:
                    first = round(d - 2 * STEP, 1)
            else:
                run = 0
        return first, [d for d, v in zip(grid, vals) if v]

    # --- the sweep ----------------------------------------------------------
    papers = ["A4", "A4R", "Letter", "A3", "62x88", "127x178"]
    modes = ["patch_first", "area_first"]
    margins = [0.0, 2.0, 6.0, 12.0, 24.0, 40.0, 55.0, 58.0, 59.5, 60.0]
    sizes = [0.0, 3.2, 6.0, 9.0, 12.7, 25.4]
    markers = [(False, False), (True, False), (True, True)]
    stamps = [False, True]
    texts = ["ChromIQ adversary twenty one"]

    findings = {"I1": [], "I2": [], "I3": [], "I4": []}
    counts = {"states": 0, "overlap": 0, "rise": 0, "denied": 0}
    t0 = time.monotonic()
    combos = list(itertools.product(papers, modes, margins, sizes,
                                    markers, stamps, texts))
    print(f"    {len(combos)} states to sweep", flush=True)
    for i, (paper, mode, mb, size, (hm, htb), stamp, txt) in enumerate(combos):
        if i % 400 == 0:
            pump(app, 40)
            print(f"      … {i}/{len(combos)}  {time.monotonic()-t0:.0f}s",
                  flush=True)
        r = replace(base, paper=paper, layout_mode=mode, margin_bottom=mb,
                    chart_text_size_mm=size, helper_markers=hm,
                    helper_markers_top_bottom=htb, stamp_command=stamp,
                    chart_text=txt, use_instrument_margins=False)
        counts["states"] += 1
        nlines, line_mm, b_edge = notice_inputs(r)
        if nlines == 0:
            continue
        pb = patch_bottom(r)
        if pb is None or pb == "unbuildable":
            continue
        o = tef.bottom_text_block_overlap(float(pb), b_edge, nlines, line_mm)
        if o is None:
            continue
        counts["overlap"] += 1
        rise = tc.margin_rise_that_clears_mm(
            r, None, b_edge, nlines, line_mm, hint_mm=o.overlap_mm)
        state = dict(paper=paper, mode=mode, margin_bottom=mb, size=size,
                     markers=hm, top_bottom=htb, stamp=stamp,
                     nlines=nlines, line_mm=round(line_mm, 3),
                     b_edge=round(b_edge, 3), patch_bottom=round(float(pb), 3),
                     overlap=round(o.overlap_mm, 3))
        if rise is not None:
            counts["rise"] += 1
            if not clears_at(r, mb, rise, b_edge, nlines, line_mm):
                findings["I1"].append({**state, "rise": rise})
            if abs(rise) < 1e-9:
                findings["I2"].append({**state, "rise": rise})
        else:
            counts["denied"] += 1
            first, clear_list = brute_answer(r, b_edge, nlines, line_mm)
            if first is not None:
                findings["I3"].append({**state, "brute": first,
                                       "clear_points": clear_list[:12]})
    print("    counts:", counts, f"{time.monotonic()-t0:.0f}s", flush=True)
    for k, v in findings.items():
        print(f"    {k}: {len(v)}", flush=True)
        for row in v[:6]:
            print("      ", row, flush=True)
    (out / "adv21a.json").write_text(
        json.dumps({"counts": counts,
                    "findings": {k: v[:60] for k, v in findings.items()},
                    "window_on_screen": bool(win.isVisible())},
                   indent=2), encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

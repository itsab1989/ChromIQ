#!/usr/bin/env python3
"""Adversary 21c — the two lever gates, with the anchor MOVED.

21b's first pass reported 510 + 782 "offered but fails". It was measuring
itself: it asked whether the collision is gone with "B" lowered while still
holding the block at the OLD anchor, and lowering "B" is exactly what moves the
anchor. That is the naive predicate round 10 caught itself writing, and it is
recorded here rather than dropped.

This is the same sweep with the anchor recomputed for the changed recipe, which
is what `_bottom_clears_with` does and what the sheet does.
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv21c-"))
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
    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 900)
    base = tab._current_layout_recipe()

    from ui.tabs import tab_chart as tc
    from workflow import text_edge_fit as tef
    from workflow.layout_engine import instruments as instr_mod
    from workflow.layout_engine.raster import sheet_text_line_mm

    def anchor_of(r):
        return tef.sheet_text_bottom_mm(
            r.effective_text_edge_mm,
            bool(getattr(r, "helper_markers", False)),
            *tc._marker_reserve_args(r),
            bool(getattr(r, "helper_markers_top_bottom", True)))

    def clears(r, nlines, line_mm):
        """THE SHEET'S OWN QUESTION: the anchor is recomputed for *r*."""
        try:
            g = instr_mod.geom_from_build_kwargs(r.build_kwargs())
        except Exception:                               # noqa: BLE001
            return False
        pb = tc.predicted_patch_bottom_mm(r, g)
        if pb is None:
            return False
        return tef.bottom_text_block_overlap(
            float(pb), anchor_of(r), nlines, line_mm) is None

    f = {"lever_offered_but_fails": [], "lever_withheld_but_works": [],
         "markers_offered_but_fails": [], "markers_withheld_but_works": []}
    counts = {"states": 0, "overlap": 0}
    papers = ["A4", "Letter", "A3", "62x88", "127x178"]
    modes = ["patch_first", "area_first"]
    margins = [0.0, 3.0, 8.0, 20.0, 45.0]
    sizes = [0.0, 4.0, 9.0, 12.7, 25.4]
    markers = [(False, False), (True, False), (True, True)]
    edges = [0.0, 0.1, 2.0, 4.0, 9.0, 20.0]
    combos = list(itertools.product(papers, modes, margins, sizes, markers,
                                    edges, [True, False], [True, False]))
    print(f"    {len(combos)} states", flush=True)
    t0 = time.monotonic()
    for i, (paper, mode, mb, size, (hm, htb), edge, stamp,
            lock) in enumerate(combos):
        if i % 900 == 0:
            pump(app, 30)
            print(f"      … {i}/{len(combos)} {time.monotonic()-t0:.0f}s",
                  flush=True)
        r = replace(base, paper=paper, layout_mode=mode, margin_bottom=mb,
                    chart_text_size_mm=size, helper_markers=hm,
                    helper_markers_top_bottom=htb, stamp_command=stamp,
                    text_edge_mm=edge, chart_text="ChromIQ adversary 21",
                    use_instrument_margins=lock)
        counts["states"] += 1
        nlines = (1 if r.chart_text else 0) + (1 if r.stamp_command else 0)
        line_mm = sheet_text_line_mm(
            float(getattr(r, "chart_text_size_mm", 0.0) or 0.0),
            str(getattr(r, "chart_text_font", "") or ""), False, False,
            float(getattr(r, "dpi", 300) or 300))
        if clears(r, nlines, line_mm):
            continue                    # no warning, no offer to judge
        counts["overlap"] += 1
        state = dict(paper=paper, mode=mode, mb=mb, size=size, hm=hm, htb=htb,
                     edge=edge, stamp=stamp, lock=lock, nlines=nlines)
        offered = tc.lowering_b_clears(r, nlines, line_mm)
        truth = clears(replace(r, text_edge_mm=tc._MIN_TEXT_EDGE_MM),
                       nlines, line_mm)
        if offered and not truth:
            f["lever_offered_but_fails"].append(state)
        if truth and not offered:
            f["lever_withheld_but_works"].append(state)
        moff = tc.markers_off_clears(r, nlines, line_mm)
        mtruth = clears(replace(r, helper_markers=False,
                                text_edge_mm=tc._MIN_TEXT_EDGE_MM),
                        nlines, line_mm)
        if moff and not mtruth:
            f["markers_offered_but_fails"].append(state)
        if mtruth and not moff:
            f["markers_withheld_but_works"].append(state)
    print("    counts:", counts, f"{time.monotonic()-t0:.0f}s", flush=True)
    for k, v in f.items():
        print(f"    {k}: {len(v)}", flush=True)
        for row in v[:5]:
            print("      ", row, flush=True)
    capture_window(win, out / "C-the-panel-on-screen.png")
    (out / "adv21c.json").write_text(json.dumps(
        {"counts": counts, "findings": {k: v[:40] for k, v in f.items()}},
        indent=2), encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

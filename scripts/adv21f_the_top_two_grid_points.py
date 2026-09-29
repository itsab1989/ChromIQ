#!/usr/bin/env python3
"""
Adversary 21f — does any denial still have a clear margin under it? NO.

Round 10's fault was "No bottom margin this sheet allows will clear it" said
because the CEILING could not be laid out. The fix walks the whole grid, but it
keeps the two-clear-points-above stability rule everywhere, including the top of
the range where there is nothing above to click to. So a sheet whose only
clearing margins are a run of one or two would still be denied.

This asks every DENIED state whether ANY grid point clears, not just a
three-in-a-row one.

**FIRST RUN: eleven hits, and all eleven were this script.** It measured the
bottom line's box with `sheet_text_line_mm(size, "", …)` where the panel uses
the recipe's own face, `r.chart_text_font`. PIL's fallback and Inter differ by
nearly two millimetres at the same Size (21.167 against 19.473), which turns a
run of nine clearing margins into a run of two. Driven in the real window
(`adv21g`, `adv21h`, `adv21j`) the sheet clears at 43.0 through 47.0 mm and the
panel correctly names a 37.0 mm rise.

**RE-RUN WITH THE RECIPE'S FONT: 7,488 states, 3,723 with an overlap, 435
denials, and NOT ONE of them has a margin the box holds that clears it.**
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

ROOT = Path("/Users/Basti/develop/ChromIQ")
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv21f-"))
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
    from workflow.layout_engine import instruments as im
    from workflow.layout_engine.raster import sheet_text_line_mm
    STEP, BOX = tc._MARGIN_STEP_MM, tc._MARGIN_BOX_MAX_MM

    def pb(r):
        try:
            g = im.geom_from_build_kwargs(r.build_kwargs())
        except Exception:                                # noqa: BLE001
            return None
        return tc.predicted_patch_bottom_mm(r, g)

    def clears(ru, asked, d, reserve, n, line):
        b = pb(replace(ru, margin_bottom=asked + d))
        if b is None:
            return False
        return tef.bottom_text_block_overlap(float(b), reserve, n, line) is None

    findings, counts = [], {"states": 0, "overlap": 0, "denied": 0}
    papers = ["A4", "A4R", "Letter", "A3", "A2", "62x88", "127x178", "4x6",
              "203x254"]
    modes = ["patch_first", "area_first"]
    margins = [0.0, 1.0, 2.5, 4.0, 6.0, 9.0, 13.0, 18.0, 26.0, 35.0, 44.0,
               52.0, 57.0]
    sizes = [0.0, 5.0, 8.0, 10.0, 12.7, 16.0, 20.0, 25.4]
    markers = [(False, False), (True, True)]
    combos = list(itertools.product(papers, modes, margins, sizes, markers,
                                    [True, False]))
    print(f"    {len(combos)} states", flush=True)
    t0 = time.monotonic()
    for i, (paper, mode, mb, size, (hm, htb), stamp) in enumerate(combos):
        if i % 600 == 0:
            pump(app, 30)
            print(f"      … {i}/{len(combos)} {time.monotonic()-t0:.0f}s "
                  f"found {len(findings)}", flush=True)
        r = replace(base, paper=paper, layout_mode=mode, margin_bottom=mb,
                    chart_text_size_mm=size, helper_markers=hm,
                    helper_markers_top_bottom=htb, stamp_command=stamp,
                    chart_text="ChromIQ 21", use_instrument_margins=False)
        counts["states"] += 1
        n = (1 if r.chart_text else 0) + (1 if r.stamp_command else 0)
        # THE RECIPE'S OWN FACE. Passing "" here is what made this
        # script's first run report eleven two-point islands that do
        # not exist: `_engine_text_notes` measures the line with
        # `r.chart_text_font` ("Inter"), and an empty family gets PIL's
        # fallback, whose ascent plus descent is a different number
        # (21.167 mm against 19.473 mm at the same Size).
        line = sheet_text_line_mm(
            float(size or 0.0), str(getattr(r, "chart_text_font", "")
                                    or ""), False, False,
            float(getattr(r, "dpi", 300) or 300))
        b0 = pb(r)
        if b0 is None:
            continue
        o = tef.bottom_text_block_overlap(float(b0), 0.0, n, line)
        edge = tef.sheet_text_bottom_mm(
            r.effective_text_edge_mm, hm, *tc._marker_reserve_args(r), htb)
        o = tef.bottom_text_block_overlap(float(b0), edge, n, line)
        if o is None:
            continue
        counts["overlap"] += 1
        rise = tc.margin_rise_that_clears_mm(r, None, edge, n, line,
                                             hint_mm=o.overlap_mm)
        if rise is not None:
            continue
        counts["denied"] += 1
        cap = min(60.0, BOX - mb)
        if cap <= 0:
            continue
        pts = [round(k * STEP, 1) for k in range(int(cap / STEP) + 1)]
        got = [d for d in pts if clears(r, mb, d, edge, n, line)]
        if got:
            findings.append({"paper": paper, "mode": mode, "mb": mb,
                             "size": size, "markers": hm, "stamp": stamp,
                             "cap": cap, "clear points": got})
    print("    counts:", counts, f"{time.monotonic()-t0:.0f}s", flush=True)
    print("    DENIALS WITH A CLEAR MARGIN UNDER THEM:", len(findings),
          flush=True)
    for row in findings[:10]:
        print("      ", row, flush=True)
    capture_window(win, out / "F-the-panel-on-screen.png")
    (out / "adv21f.json").write_text(
        json.dumps({"counts": counts, "findings": findings[:80]}, indent=2),
        encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

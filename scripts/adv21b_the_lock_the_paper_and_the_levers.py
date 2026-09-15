#!/usr/bin/env python3
"""Adversary 21b — the tick, the paper sentence and the two levers.

In a REAL window, on the panel's own recipe.

  L1  With "Use instrument margins" TICKED the overlap is measured on the
      locked sheet and the rise on the unlocked one. Untick, type the rise:
      is the warning really gone? And is the rise ever 0.0 mm, which the code
      says is not one of the four cases?
  P1  `_larger_paper_note` denies a larger paper. Brute-force every larger
      paper in the same pulldown and see whether one of them clears.
  P2  …and is it silent where it should speak? (a denial withheld although no
      larger paper helps is a lost sentence, not a false one.)
  V1  `lowering_b_clears` / `markers_off_clears` — the offer must be true when
      made, and the route must really fail when it is withheld.
  X1  Does `instruments.geom_from_build_kwargs` ever RAISE on a candidate
      margin? `margin_rise_that_clears_mm.clears` does not catch it, so one
      raising candidate turns the whole search into "no margin will clear it".
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv21b-"))
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
    print("    base:", base.instrument, base.paper, base.layout_mode, flush=True)

    from ui.tabs import tab_chart as tc
    from workflow import text_edge_fit as tef
    from workflow.layout_engine import instruments as instr_mod
    from workflow.layout_engine import papers as paper_mod
    STEP, CAP_BOX = tc._MARGIN_STEP_MM, tc._MARGIN_BOX_MAX_MM

    raised: list = []

    def geom_of(r):
        try:
            return instr_mod.geom_from_build_kwargs(r.build_kwargs())
        except Exception as e:                          # noqa: BLE001
            raised.append((repr(e)[:90], r.paper, r.layout_mode,
                           r.margin_bottom))
            return None

    def notice_inputs(r):
        nlines = (1 if r.chart_text else 0) + (1 if r.stamp_command else 0)
        from workflow.layout_engine.raster import sheet_text_line_mm
        line_mm = sheet_text_line_mm(
            float(getattr(r, "chart_text_size_mm", 0.0) or 0.0),
            str(getattr(r, "chart_text_font", "") or ""), False, False,
            float(getattr(r, "dpi", 300) or 300))
        b_edge = tef.sheet_text_bottom_mm(
            r.effective_text_edge_mm,
            bool(getattr(r, "helper_markers", False)),
            *tc._marker_reserve_args(r),
            bool(getattr(r, "helper_markers_top_bottom", True)))
        return nlines, line_mm, b_edge

    def overlap_of(r, nlines, line_mm, b_edge):
        g = geom_of(r)
        if g is None:
            return "unbuildable"
        pb = tc.predicted_patch_bottom_mm(r, g)
        if pb is None:
            return None
        return tef.bottom_text_block_overlap(float(pb), b_edge, nlines, line_mm)

    f = {"L1_rise_does_not_clear": [], "L1_rise_zero": [],
         "P1_larger_paper_does_help": [], "P2_denial_withheld_wrongly": [],
         "V1_lever_offered_but_fails": [], "V1_lever_withheld_but_works": [],
         "V1_markers_offered_but_fails": [],
         "V1_markers_withheld_but_works": []}
    counts = {"states": 0, "overlap": 0, "locked_rise": 0, "denied": 0}

    papers = ["A4", "A4R", "Letter", "A3", "62x88", "127x178", "A2"]
    modes = ["patch_first", "area_first"]
    margins = [0.0, 3.0, 8.0, 15.0, 30.0, 50.0, 59.0]
    sizes = [0.0, 4.0, 9.0, 12.7, 25.4]
    markers = [(False, False), (True, False), (True, True)]
    edges = [0.0, 0.1, 4.0, 9.0]
    combos = list(itertools.product(papers, modes, margins, sizes, markers,
                                    edges, [True, False]))
    print(f"    {len(combos)} states", flush=True)
    t0 = time.monotonic()
    for i, (paper, mode, mb, size, (hm, htb), edge, stamp) in enumerate(combos):
        if i % 600 == 0:
            pump(app, 30)
            print(f"      … {i}/{len(combos)} {time.monotonic()-t0:.0f}s",
                  flush=True)
        r = replace(base, paper=paper, layout_mode=mode, margin_bottom=mb,
                    chart_text_size_mm=size, helper_markers=hm,
                    helper_markers_top_bottom=htb, stamp_command=stamp,
                    text_edge_mm=edge, chart_text="ChromIQ adversary 21",
                    use_instrument_margins=True)
        counts["states"] += 1
        nlines, line_mm, b_edge = notice_inputs(r)
        o = overlap_of(r, nlines, line_mm, b_edge)
        if o is None or o == "unbuildable":
            continue
        counts["overlap"] += 1
        rise = tc.margin_rise_that_clears_mm(
            r, None, b_edge, nlines, line_mm, hint_mm=o.overlap_mm)
        state = dict(paper=paper, mode=mode, mb=mb, size=size, hm=hm,
                     htb=htb, edge=edge, stamp=stamp, nlines=nlines,
                     overlap=round(o.overlap_mm, 3))
        if rise is not None:
            counts["locked_rise"] += 1
            # THE SHEET THE READER LANDS ON: the tick off, the rise typed.
            ru = replace(r, use_instrument_margins=False,
                         margin_bottom=mb + rise)
            o2 = overlap_of(ru, nlines, line_mm, b_edge)
            if o2 is not None and o2 != "unbuildable":
                f["L1_rise_does_not_clear"].append({**state, "rise": rise,
                                                    "left": round(o2.overlap_mm, 3)})
            if o2 == "unbuildable":
                f["L1_rise_does_not_clear"].append({**state, "rise": rise,
                                                    "left": "unbuildable"})
            if abs(rise) < 1e-9:
                f["L1_rise_zero"].append({**state, "rise": rise})
        else:
            counts["denied"] += 1
            # P1/P2 — the sentence, and the truth of it.
            note = tc._larger_paper_note(r, nlines, line_mm)
            here_w, here_h = paper_mod.dimensions_mm(paper)
            helps = []
            for code, _lab, dims in paper_mod.list_papers(
                    r.instrument or None, for_engine=True):
                if code == paper:
                    continue
                if (float(dims[0]) <= here_w + 1e-9
                        and float(dims[1]) <= here_h + 1e-9):
                    continue
                oo = overlap_of(replace(r, paper=code), nlines, line_mm, b_edge)
                if oo is None:
                    helps.append(code)
            if note and helps:
                f["P1_larger_paper_does_help"].append({**state,
                                                       "helps": helps[:5]})
            if not note and not helps:
                f["P2_denial_withheld_wrongly"].append(state)
        # V1 — the two levers, whatever the rise said.
        lever = tc.lowering_b_clears(r, nlines, line_mm)
        truth = overlap_of(replace(r, text_edge_mm=tc._MIN_TEXT_EDGE_MM),
                           nlines, line_mm, b_edge)
        truth_ok = truth is None
        if lever and not truth_ok:
            f["V1_lever_offered_but_fails"].append(state)
        if (not lever) and truth_ok:
            f["V1_lever_withheld_but_works"].append(state)
        mk = tc.markers_off_clears(r, nlines, line_mm)
        mt = overlap_of(replace(r, helper_markers=False,
                                text_edge_mm=tc._MIN_TEXT_EDGE_MM),
                        nlines, line_mm, b_edge)
        mt_ok = mt is None
        if mk and not mt_ok:
            f["V1_markers_offered_but_fails"].append(state)
        if (not mk) and mt_ok:
            f["V1_markers_withheld_but_works"].append(state)

    print("    counts:", counts, f"{time.monotonic()-t0:.0f}s", flush=True)
    for k, v in f.items():
        print(f"    {k}: {len(v)}", flush=True)
        for row in v[:5]:
            print("      ", row, flush=True)
    print("    X1 geom_from_build_kwargs raised:", len(raised), flush=True)
    for row in raised[:6]:
        print("      ", row, flush=True)
    capture_window(win, out / "B-the-panel-on-screen.png")
    (out / "adv21b.json").write_text(json.dumps(
        {"counts": counts, "findings": {k: v[:40] for k, v in f.items()},
         "geom_raised": raised[:40]}, indent=2), encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

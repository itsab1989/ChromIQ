#!/usr/bin/env python3
"""Adversary 20d, in a REAL window.

"A larger paper does not help" is a claim about the pulldown the reader is
looking at. Two questions round 9 did not ask:

  * on a LANDSCAPE sheet, is "larger on either side" the right test? The
    candidate that clears A2 landscape is A2 PORTRAIT, which is narrower and
    taller, and the loop skips only candidates smaller on BOTH sides, so it
    should still be tried.
  * does the loop walk the same list the panel's own Paper pulldown carries
    for THIS instrument? Read both off the live window and compare.

and then every state that makes the claim is falsified against every larger
paper, on every instrument.
"""
from __future__ import annotations

import json, os, sys, tempfile, time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
from onscreen_capture import capture_window                      # noqa: E402


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv20d-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)), ("language", "en"),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark")):
        settings.set(k, v)
    QDialog.exec = lambda self: 1                   # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart, _bottom_clears_with
    from ui.theme import apply_appearance
    apply_appearance(app, None, "dark")
    win = MainWindow(settings); win.resize(1620, 1080)
    win.show(); win.raise_(); pump(app, 2200)
    print("    window on screen:", win.isVisible(), flush=True)
    win._tabs.setCurrentWidget(win._tab_chart); tab = win._tab_chart
    pump(app, 600); tab._user_switch_mode("manual"); pump(app, 1300)
    base = tab._current_layout_recipe()
    p = tab._manual_layout_panel

    from workflow.layout_engine import papers as _papers
    from workflow.layout_engine import raster as _raster

    # 1. THE PULLDOWN THE READER SEES, off the live combo, against the list
    #    `_larger_paper_note` walks.
    mismatch = {}
    for instr in ("i1", "p3", "SS", "CR30", "CM"):
        i = p.instr.findData(instr)
        if i < 0:
            continue
        p.instr.setCurrentIndex(i); pump(app, 500)
        on_screen = [p.paper.itemData(k) for k in range(p.paper.count())]
        on_screen = [c for c in on_screen if c and c != "__custom__"]
        walked = [c for c, _l, _d in _papers.list_papers(instr,
                                                         for_engine=True)]
        if on_screen != walked:
            mismatch[instr] = {"pulldown": on_screen, "walked": walked}
        print(f"    [{instr}] pulldown {len(on_screen)} papers, the note walks "
              f"{len(walked)}: {'SAME' if on_screen == walked else 'DIFFERENT'}",
              flush=True)

    class _Btn:
        def __init__(self, on=True): self._on = on
        def isChecked(self): return self._on
    class _Edit:
        def text(self): return ""
    class _S:
        def get(self, k, d=None):
            return True if k == "use_chromiq_layout_engine" else d
    class _Tab:
        _manual_btn = _Btn(); _manual_layout_panel = object(); _settings = _S()
        def __init__(self, r):
            self._recipe = r; self._manual_chart_notes_edit = _Edit()
            self._manual_stamp_cmd_check = _Btn(False)
        def _current_layout_recipe(self): return self._recipe

    def notice(r):
        try:
            got = [w for w in TabChart._engine_text_notes(_Tab(r))[1]
                   if "sheet text along the bottom" in w
                   and "into the patches" in w]
        except Exception:                            # noqa: BLE001
            return ""
        return got[0] if got else ""

    # 2. EVERY STATE THAT MAKES THE CLAIM, falsified against every larger paper
    said, wrong, states, done, t0 = 0, [], 0, 0, time.monotonic()
    for instr in ("i1", "p3", "SS", "CR30"):
        codes = [c for c, _l, _d in _papers.list_papers(instr,
                                                        for_engine=True)]
        for paper in codes:
            for mode in ("area_first", "patch_first"):
                for nlines in (1, 2):
                    for size_pt in (48.0, 72.0):
                        for mb in (10.0, 40.0):
                            r = replace(
                                base, instrument=instr, paper=paper,
                                layout_mode=mode, use_instrument_margins=False,
                                helper_markers=False, margin_bottom=mb,
                                margin_top=12.0, margin_left=12.0,
                                margin_right=12.0, text_edge_mm=4.0,
                                stamp_command=(nlines == 2),
                                chart_text="ChromIQ adversary twenty",
                                chart_text_size_mm=size_pt * 25.4 / 72.0)
                            done += 1
                            if done % 100 == 0:
                                print(f"      {done} {time.monotonic()-t0:.0f}s "
                                      f"states={states} said={said} "
                                      f"wrong={len(wrong)}", flush=True)
                                app.processEvents()
                            msg = notice(r)
                            if not msg:
                                continue
                            states += 1
                            if "A larger paper does not help" not in msg:
                                continue
                            said += 1
                            lm = _raster.sheet_text_line_mm(
                                r.chart_text_size_mm, r.chart_text_font,
                                False, False, r.dpi)
                            w0, h0 = _papers.dimensions_mm(paper)
                            for c, _l, d in _papers.list_papers(
                                    instr, for_engine=True):
                                if c == paper:
                                    continue
                                if (d[0] <= w0 + 1e-9 and d[1] <= h0 + 1e-9):
                                    continue
                                if _bottom_clears_with(r, nlines, lm, paper=c):
                                    wrong.append((instr, paper, mode, nlines,
                                                  size_pt, mb, c))
                                    break
    print(f"    warning states {states}, of them the denial is made in {said}",
          flush=True)
    print(f"    falsified: {len(wrong)}", flush=True)
    for x in wrong[:10]:
        print("      ", x, flush=True)
    (out / "adv20d.json").write_text(json.dumps(
        {"pulldown_mismatch": mismatch, "states": states, "said": said,
         "falsified": [list(map(str, x)) for x in wrong]}, indent=2),
        encoding="utf-8")
    capture_window(win, out / "D0-the-paper-pulldown.png")
    win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

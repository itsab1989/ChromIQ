#!/usr/bin/env python3
"""Adversary 20a, in a REAL window.

The states rounds 4-9 did NOT sweep for the four bottom-text wordings:
two lines AND markers AND locked margins together, custom paper sizes, the
smallest papers each instrument offers, patch-first layouts, and every
instrument's own paper pulldown.

For every state that raises the bottom notice this asks the sheet whether the
message's own remedy finishes the job:

  * a message that names a rise  -> type the rise (untick "Use instrument
    margins" first when the message says to) and the notice must be gone.
  * "no bottom margin ... will clear it" -> the box really must not hold one,
    and "A larger paper does not help" must be true of the pulldown the
    reader sees for THIS instrument.
  * "lowering B buys the same room"  -> taking B to the bottom must clear it.
  * "switching Print helper markers off"  -> that route must clear it.
"""
from __future__ import annotations

import json, os, sys, tempfile, time
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
from onscreen_capture import capture_window                     # noqa: E402


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv20a-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)), ("language", "en"),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True)):
        settings.set(k, v)
    QDialog.exec = lambda self: 1                   # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings); win.resize(1620, 1080)
    win.show(); win.raise_(); pump(app, 2200)
    print("    window on screen:", win.isVisible(), flush=True)

    win._tabs.setCurrentWidget(win._tab_chart); tab = win._tab_chart
    pump(app, 700); tab._user_switch_mode("manual"); pump(app, 1400)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("adv20a")
    pump(app, 500)
    panel = tab._manual_layout_panel
    base = tab._current_layout_recipe()
    print("    base recipe from the live panel:", base.instrument, base.paper,
          base.layout_mode, flush=True)

    # the margin box's own ceiling, read off the live widget
    box_max = float(panel.margins["b"].maximum())
    from ui.tabs.tab_chart import _MARGIN_BOX_MAX_MM
    print(f"    the live 'Bottom' box maximum = {box_max}  "
          f"(the message says {_MARGIN_BOX_MAX_MM})", flush=True)

    from ui.tabs.tab_chart import (_bottom_clears_with, lowering_b_clears,
                                   markers_off_clears,
                                   margin_rise_that_clears_mm)
    from workflow.layout_engine import papers as _papers
    from workflow.layout_engine import raster as _raster

    class _Btn:
        def __init__(self, on=True): self._on = on
        def isChecked(self): return self._on
    class _Edit:
        def text(self): return ""
    class _Settings:
        def get(self, key, default=None):
            return True if key == "use_chromiq_layout_engine" else default
    class _Tab:
        _manual_btn = _Btn()
        _manual_layout_panel = object()
        _settings = _Settings()
        def __init__(self, r):
            self._recipe = r
            self._manual_chart_notes_edit = _Edit()
            self._manual_stamp_cmd_check = _Btn(False)
        def _current_layout_recipe(self): return self._recipe

    def notice(r):
        try:
            got = [w for w in TabChart._engine_text_notes(_Tab(r))[1]
                   if "sheet text along the bottom" in w]
        except Exception as e:                      # noqa: BLE001
            return f"<<RAISED {e!r}>>"
        return got[0] if got else ""

    def line_mm(r):
        return _raster.sheet_text_line_mm(r.chart_text_size_mm,
                                          r.chart_text_font, False, False,
                                          r.dpi)

    import re
    faults, states = [], 0
    t0 = time.monotonic()
    INSTR = ("i1", "p3", "SS", "CR30")

    def papers_for(instr):
        codes = [(c, d) for c, _l, d in
                 _papers.list_papers(instr, for_engine=True)]
        by_area = sorted(codes, key=lambda cd: cd[1][0] * cd[1][1])
        pick = [c for c, _d in by_area[:2]]            # the two smallest
        pick += [c for c, _d in by_area[-1:]]          # the largest
        for want in ("A4", "Letter"):
            if any(c == want for c, _d in codes) and want not in pick:
                pick.append(want)
        # two CUSTOM sizes, which the pulldown offers as "Custom…"
        pick += ["155x220", "62x88"]
        return pick

    combos = []
    for instr in INSTR:
        for paper in papers_for(instr):
            for mode in ("area_first", "patch_first"):
                for locked in (False, True):
                    for markers in (False, True):
                        for nlines in (1, 2):
                            for size_pt in (28.0, 48.0):
                                for mb in (8.0, 45.0):
                                    combos.append((instr, paper, mode, locked,
                                                   markers, nlines, size_pt,
                                                   mb))
    print(f"    combinations to try: {len(combos)}", flush=True)
    for n, (instr, paper, mode, locked, markers, nlines, size_pt, mb) in \
            enumerate(combos):
        if n % 100 == 0:
            print(f"      {n}/{len(combos)}  {time.monotonic()-t0:.0f}s  "
                  f"states={states} faults={len(faults)}", flush=True)
            app.processEvents()
        r = replace(base, instrument=instr, paper=paper, layout_mode=mode,
                    use_instrument_margins=locked, helper_markers=markers,
                    helper_markers_top_bottom=True,
                    helper_marker_edge_mm=4.0, helper_marker_len_mm=2.0,
                    margin_bottom=mb, margin_top=12.0, margin_left=12.0,
                    margin_right=12.0, text_edge_mm=4.0, stamp_command=False,
                    chart_text="ChromIQ adversary twenty",
                    chart_text_size_mm=size_pt * 25.4 / 72.0)
        if nlines == 2:
            r = replace(r, stamp_command=True)
        msg = notice(r)
        if not msg:
            continue
        states += 1
        key = (instr, paper, mode, locked, markers, nlines, size_pt, mb)
        if msg.startswith("<<RAISED"):
            faults.append(("RAISED",) + key + (msg,))
            continue
        lm = line_mm(r)
        m = re.search(r"by about ([0-9.]+) mm", msg)
        if m:
            rise = float(m.group(1))
            if rise <= 0.0:
                faults.append(("RISE-ZERO",) + key + (msg,))
            if mb + rise > box_max + 1e-9:
                faults.append(("RISE-PAST-BOX",) + key + (rise, msg))
            else:
                after = notice(replace(r, use_instrument_margins=False,
                                       margin_bottom=mb + rise))
                if after:
                    faults.append(("RISE-DOES-NOT-CLEAR",) + key + (rise, after))
        if "No bottom margin this sheet allows" in msg:
            probe = mb
            while probe < box_max - 1e-9:
                probe = round(min(probe + 0.5, box_max), 1)
                if not notice(replace(r, use_instrument_margins=False,
                                      margin_bottom=probe)):
                    faults.append(("CEILING-FALSE",) + key + (probe,))
                    break
            if "A larger paper does not help" in msg:
                w0, h0 = _papers.dimensions_mm(paper)
                for c, _l, d in _papers.list_papers(instr, for_engine=True):
                    if c == paper:
                        continue
                    if d[0] <= w0 + 1e-9 and d[1] <= h0 + 1e-9:
                        continue
                    if _bottom_clears_with(r, nlines, lm, paper=c):
                        faults.append(("LARGER-PAPER-DOES-HELP",) + key + (c,))
                        break
        if "buys the same room" in msg:
            if notice(replace(r, text_edge_mm=0.1)):
                faults.append(("LEVER-B-DOES-NOT-CLEAR",) + key)
        if "Print helper markers" in msg and "will not help" in msg:
            if notice(replace(r, helper_markers=False, text_edge_mm=0.1)):
                faults.append(("MARKERS-ROUTE-DOES-NOT-CLEAR",) + key)
    print(f"    warning states swept: {states}", flush=True)
    print(f"    faults: {len(faults)}", flush=True)
    seen = {}
    for f in faults:
        seen.setdefault(f[0], []).append(f)
    for k, v in seen.items():
        print(f"      {k}: {len(v)}   first: {v[0][1:9]}", flush=True)
    (out / "adv20a.json").write_text(json.dumps(
        {"box_max": box_max, "states": states,
         "faults": [list(map(str, f)) for f in faults]},
        indent=2, ensure_ascii=False), encoding="utf-8")
    capture_window(win, out / "A0-the-panel.png")
    win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

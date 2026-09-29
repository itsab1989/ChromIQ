#!/usr/bin/env python3
"""Adversary 20b, in a REAL window.

20a's "a margin between here and 60 clears it" probe read a LayoutError as a
cleared sheet: on a 62x88 custom card every margin above 25.0 mm destroys the
patch grid, the panel falls silent because there is no layout at all, and the
message is right. So the predicate is corrected here:

    cleared(margin) = the sheet still BUILDS  AND  the bottom notice is gone

and a candidate only counts when it is STABLE, the way
`margin_rise_that_clears_mm`'s own walk requires: it and the next two grid
points above it.

With that, two claims are asked of every warning state:

  * "No bottom margin this sheet allows will clear it" -- is there one?
  * "Raise Bottom by about X mm" -- does X really clear, on a sheet that
    still builds?
"""
from __future__ import annotations

import json, os, re, sys, tempfile, time
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv20b-"))
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
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    apply_appearance(app, None, "dark")
    win = MainWindow(settings); win.resize(1620, 1080)
    win.show(); win.raise_(); pump(app, 2200)
    print("    window on screen:", win.isVisible(), flush=True)
    win._tabs.setCurrentWidget(win._tab_chart); tab = win._tab_chart
    pump(app, 600); tab._user_switch_mode("manual"); pump(app, 1300)
    base = tab._current_layout_recipe()
    panel = tab._manual_layout_panel
    box_max = float(panel.margins["b"].maximum())

    from workflow.layout_engine import instruments, papers as _papers
    from workflow.layout_engine import geometry as _geom

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

    def builds(r) -> bool:
        try:
            g = instruments.geom_from_build_kwargs(r.build_kwargs())
            w, h = _papers.dimensions_mm(str(r.paper))
            _geom.compute(g, w, h, 120)
            return True
        except Exception:                            # noqa: BLE001
            return False

    def notice(r) -> str:
        """THE HEIGHT NOTICE, and only it. The WIDTH one opens with the same
        seven words ("The sheet text along the bottom is too wide for the
        paper"), so a filter on that prefix reads one as the other and a sheet
        whose height collision really did clear looks as if it never did."""
        try:
            got = [w for w in TabChart._engine_text_notes(_Tab(r))[1]
                   if "sheet text along the bottom" in w
                   and "into the patches" in w]
        except Exception as e:                       # noqa: BLE001
            return f"<<RAISED {e!r}>>"
        return got[0] if got else ""

    def cleared(r, mb: float) -> bool:
        c = replace(r, use_instrument_margins=False, margin_bottom=mb)
        return builds(c) and not notice(c)

    def stable_clear(r, mb: float) -> bool:
        return all(cleared(r, round(mb + k * 0.5, 1)) for k in (0, 1, 2)
                   if mb + k * 0.5 <= box_max + 1e-9)

    faults, states, t0 = [], 0, time.monotonic()
    combos = []
    for instr in ("i1", "p3", "SS", "CR30"):
        codes = [c for c, _l, _d in _papers.list_papers(instr,
                                                        for_engine=True)]
        for paper in codes + ["155x220", "62x88", "100x150", "180x240"]:
            for mode in ("area_first", "patch_first"):
                for markers in (False, True):
                    for nlines in (1, 2):
                        for size_pt in (20.0, 36.0, 60.0):
                            for mb in (6.0, 16.0, 30.0):
                                combos.append((instr, paper, mode, markers,
                                               nlines, size_pt, mb))
    print(f"    combinations: {len(combos)}", flush=True)
    for n, (instr, paper, mode, markers, nlines, size_pt, mb) in \
            enumerate(combos):
        if n % 200 == 0:
            print(f"      {n}/{len(combos)} {time.monotonic()-t0:.0f}s "
                  f"states={states} faults={len(faults)}", flush=True)
            app.processEvents()
        r = replace(base, instrument=instr, paper=paper, layout_mode=mode,
                    use_instrument_margins=False, helper_markers=markers,
                    helper_markers_top_bottom=True, helper_marker_edge_mm=4.0,
                    helper_marker_len_mm=2.0, margin_bottom=mb,
                    margin_top=12.0, margin_left=12.0, margin_right=12.0,
                    text_edge_mm=4.0, stamp_command=(nlines == 2),
                    chart_text="ChromIQ adversary twenty",
                    chart_text_size_mm=size_pt * 25.4 / 72.0)
        if not builds(r):
            continue
        msg = notice(r)
        if not msg:
            continue
        states += 1
        key = (instr, paper, mode, markers, nlines, size_pt, mb)
        if msg.startswith("<<RAISED"):
            faults.append(("RAISED",) + key + (msg,)); continue
        m = re.search(r"by about ([0-9.]+) mm", msg)
        if m:
            rise = float(m.group(1))
            cand = replace(r, margin_bottom=mb + rise)
            if rise <= 0.0:
                faults.append(("RISE-ZERO",) + key + (msg[:120],))
            elif mb + rise > box_max + 1e-9:
                faults.append(("RISE-PAST-BOX",) + key + (rise,))
            elif not builds(cand):
                faults.append(("RISE-BREAKS-THE-SHEET",) + key + (rise,))
            elif notice(cand):
                faults.append(("RISE-DOES-NOT-CLEAR",) + key + (rise,))
        if "No bottom margin this sheet allows" in msg:
            p = mb
            while p < box_max - 1e-9:
                p = round(min(p + 0.5, box_max), 1)
                if stable_clear(r, p):
                    faults.append(("CEILING-FALSE",) + key + (p,)); break
    print(f"    warning states swept: {states}", flush=True)
    print(f"    faults: {len(faults)}", flush=True)
    kinds: dict = {}
    for f in faults:
        kinds.setdefault(f[0], []).append(f)
    for k, v in kinds.items():
        print(f"      {k}: {len(v)}   first: {v[0][1:]}", flush=True)
    (out / "adv20b-after-the-fix.json").write_text(json.dumps(
        {"box_max": box_max, "states": states,
         "faults": [list(map(str, f)) for f in faults]}, indent=2,
        ensure_ascii=False), encoding="utf-8")
    capture_window(win, out / "B0-the-panel.png")
    win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

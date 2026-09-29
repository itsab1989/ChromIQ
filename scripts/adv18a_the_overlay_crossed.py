#!/usr/bin/env python3
"""Adversary round 18a, driven in a REAL window.

Round 17 fixed `_helper_marker_lines_frac` to read the two marker boxes the way
`LayoutRecipe.build_kwargs` does (`or 2.0`) and measured ONE state: boxes 0/0,
i1/A4, both combs on. This crosses it:

  * both combs, top+bottom only, sides only
  * markers per patch 2, 3, 5, 12
  * edge/length 0/0, 0/2, 2/0, 0.5/0.5, 2/2, 6/4
  * area_first and patch_first
  * a clip border on the left
  * the PENDING caption after a real Generate at 0/0
  * the Guided page and the FROM PROFILE GAMUT module

For every state it compares the overlay's segment list against
`geometry.helper_marker_lines_mm` fed the SAME geometry with the engine's own
`or 2.0` -- and, for the generated states, against the dash runs in the real
TIFF the app just wrote.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window                      # noqa: E402

PRESET = ("__chromiq_knut_cr30_letter_792p_2pages_portrait"
          "_w11_0mm_hexagonal_straight__")


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def sheet_lines(tab, panel, *, coerce=True):
    """What `geometry.helper_marker_lines_mm` draws for the panel's values on
    the geometry of the chart in the preview -- the engine's own reading."""
    from core.text_io import read_text
    from workflow.layout_engine import instruments, geometry, papers
    from workflow.layout_engine.presets import LayoutRecipe
    ch = Path(tab._margin_ti2).with_suffix(".channels.json")
    rec = LayoutRecipe.from_channels_json(ch)
    if rec is None:
        return None
    m = re.search(r"NUMBER_OF_SETS\s+(\d+)",
                  read_text(Path(tab._margin_ti2), lenient=True))
    n = int(m.group(1)) if m else 0
    kw = rec.build_kwargs(); kw["area_target_count"] = n
    g = instruments.geom_from_build_kwargs(kw)
    w, h = papers.dimensions_mm(rec.paper)
    lay = geometry.compute(g, w, h, n)
    e = float(panel.helper_marker_edge.value())
    l = float(panel.helper_marker_len.value())
    if coerce:
        e = e or 2.0
        l = l or 2.0
    return geometry.helper_marker_lines_mm(
        g, w, h, lay, edge_mm=e, length_mm=l,
        per_patch=int(panel.helper_marker_per_patch.value()),
        top_bottom=bool(panel.helper_markers_top_bottom.isChecked()),
        sides=bool(panel.helper_markers_sides.isChecked()))


def tiff_edge_runs(path, dpi, mm=6.0):
    """Dash runs in each of the four edge bands of a real TIFF."""
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(str(path)).convert("L"))
    px = int(mm / 25.4 * dpi)
    out = {}
    for name, band, axis in (("top", a[:px, :], 0), ("bottom", a[-px:, :], 0),
                             ("left", a[:, :px], 1), ("right", a[:, -px:], 1)):
        ink = (band < 200)
        v = ink.any(axis=axis).astype(int)
        out[name] = int(((v[1:] == 1) & (v[:-1] == 0)).sum() + v[0])
    return out


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv18a-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True),
                 ("margin_violation_notify", True)):
        settings.set(k, v)
    assert settings.get("custom_output_path", "") == str(work)
    QDialog.exec = lambda self: 1                  # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings); win.resize(1620, 1060)
    win.show(); win.raise_(); pump(app, 2500)
    onscreen = bool(win.isVisible())
    print(f"    window on screen: {onscreen}", flush=True)
    win._tabs.setCurrentWidget(win._tab_chart); tab = win._tab_chart
    pump(app, 800); tab._user_switch_mode("manual"); pump(app, 1500)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("adv18a")
    combo = tab._preset_combo
    i = combo.findData(PRESET); assert i >= 0, "Knut's preset is not in the list"
    combo.setCurrentIndex(i); combo.activated.emit(i); pump(app, 1500)
    for _ in range(500):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 1200)
    panel = tab._manual_layout_panel
    res = {"window_on_screen": onscreen, "states": [], "generated": [],
           "modes": {}}

    # A strip reader on A4, so BOTH combs are live (a honeycomb greys one).
    if panel.instr.findData("i1") >= 0:
        panel.instr.setCurrentIndex(panel.instr.findData("i1")); pump(app, 900)
    panel.paper.setCurrentIndex(panel.paper.findData("A4"))
    if panel.use_instr_margins.isChecked():
        panel.use_instr_margins.setChecked(False); pump(app, 400)
    for k, v in (("t", 20.0), ("b", 20.0), ("l", 20.0), ("r", 20.0)):
        panel.margins[k].setValue(v)
    panel.helper_markers_cb.setChecked(True); pump(app, 600)

    def probe(tag):
        pump(app, 150)
        tab._refresh_helper_marker_overlay(); pump(app, 250)
        got = tab._helper_marker_lines_frac()
        lines, pending = (got if got is not None else (None, False))
        n = 0 if not lines else len(lines)
        s = sheet_lines(tab, panel)
        ns = 0 if s is None else len(s)
        raw = sheet_lines(tab, panel, coerce=False)
        row = {"state": tag, "overlay": n, "engine": ns,
               "engine_if_read_raw": 0 if raw is None else len(raw),
               "pending": bool(pending), "match": n == ns}
        res["states"].append(row)
        flag = "" if n == ns else "   <<<< MISMATCH"
        print(f"    {tag:<58} overlay {n:>4}  engine {ns:>4}  "
              f"pending {str(bool(pending)):<5}{flag}", flush=True)
        return row

    # ---- the cross ---------------------------------------------------------
    for mode in ("area_first", "patch_first"):
        if panel.layout_mode.findData(mode) >= 0:
            panel.layout_mode.setCurrentIndex(panel.layout_mode.findData(mode))
            pump(app, 500)
        for tb, sd in ((True, True), (True, False), (False, True)):
            panel.helper_markers_top_bottom.setChecked(tb)
            panel.helper_markers_sides.setChecked(sd)
            pump(app, 200)
            for pp in (2, 3, 5, 12):
                panel.helper_marker_per_patch.setValue(pp)
                for e, l in ((0.0, 0.0), (0.0, 2.0), (2.0, 0.0),
                             (0.5, 0.5), (2.0, 2.0), (6.0, 4.0)):
                    panel.helper_marker_edge.setValue(e)
                    panel.helper_marker_len.setValue(l)
                    probe(f"{mode} tb={int(tb)} sides={int(sd)} pp={pp:<2} "
                          f"{e:.1f}/{l:.1f}")
    # a clip border on the left
    panel.helper_markers_top_bottom.setChecked(True)
    panel.helper_markers_sides.setChecked(True)
    panel.helper_marker_per_patch.setValue(3)
    if hasattr(panel, "clip_border_cb"):
        try:
            panel.clip_border_cb.setChecked(True)
        except Exception:
            pass
    if panel.clip_side.findData("left") >= 0:
        panel.clip_side.setCurrentIndex(panel.clip_side.findData("left"))
    panel.clip_width.setValue(26.0); pump(app, 400)
    for e, l in ((0.0, 0.0), (2.0, 2.0)):
        panel.helper_marker_edge.setValue(e); panel.helper_marker_len.setValue(l)
        probe(f"clip-border-left {e:.1f}/{l:.1f}")
    # markers off
    panel.helper_markers_cb.setChecked(False); pump(app, 300)
    probe("markers OFF")
    panel.helper_markers_cb.setChecked(True); pump(app, 300)

    # ---- a REAL Generate at 0/0, then the overlay against the TIFF ----------
    for e, l, pp, tb, sd in ((0.0, 0.0, 3, True, True),
                             (0.0, 0.0, 5, False, True),
                             (1.5, 0.5, 4, True, True)):
        panel.helper_marker_edge.setValue(e); panel.helper_marker_len.setValue(l)
        panel.helper_marker_per_patch.setValue(pp)
        panel.helper_markers_top_bottom.setChecked(tb)
        panel.helper_markers_sides.setChecked(sd)
        pump(app, 600)
        tab._generate_btn.click()
        for _ in range(900):
            pump(app, 200)
            if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
                break
        pump(app, 2500)
        tab._refresh_helper_marker_overlay(); pump(app, 800)
        got = tab._helper_marker_lines_frac()
        lines, pending = (got if got is not None else (None, False))
        tif = list(getattr(tab, "_margin_tiffs", []) or [])
        dpi = 300.0
        try:
            dpi = float(tab._current_layout_recipe().dpi or 300)
        except Exception:
            pass
        runs = tiff_edge_runs(tif[0], dpi) if tif else {}
        s = sheet_lines(tab, panel)
        row = {"state": f"GENERATED {e:.1f}/{l:.1f} pp={pp} tb={int(tb)} sides={int(sd)}",
               "overlay": 0 if not lines else len(lines),
               "engine": 0 if s is None else len(s),
               "pending": bool(pending), "tiff_edge_runs": runs,
               "tiff": str(tif[0]) if tif else ""}
        res["generated"].append(row)
        print(f"    GENERATED {e:.1f}/{l:.1f} pp={pp} tb={int(tb)} sides={int(sd)}: "
              f"overlay {row['overlay']}, engine {row['engine']}, "
              f"pending {row['pending']}, tiff runs {runs}", flush=True)
        capture_window(win, out / f"gen-{e:.0f}-{l:.0f}-pp{pp}-tb{int(tb)}"
                                  f"-sd{int(sd)}.png")

    # ---- Guided, and the FROM PROFILE GAMUT module -------------------------
    tab._user_switch_mode("guided"); pump(app, 1200)
    got = tab._helper_marker_lines_frac()
    res["modes"]["guided"] = {
        "current_mode": tab._current_mode(), "mode_name": tab._mode_name(),
        "overlay": 0 if not got or not got[0] else len(got[0]),
        "pending": bool(got[1]) if got else False}
    print(f"    guided: {res['modes']['guided']}", flush=True)
    capture_window(win, out / "guided.png")
    tab._user_switch_mode("manual"); pump(app, 900)
    try:
        tab._user_switch_mode("gamut"); pump(app, 1200)
        got = tab._helper_marker_lines_frac()
        s = sheet_lines(tab, panel)
        res["modes"]["gamut"] = {
            "current_mode": tab._current_mode(), "mode_name": tab._mode_name(),
            "overlay": 0 if not got or not got[0] else len(got[0]),
            "engine": 0 if s is None else len(s),
            "pending": bool(got[1]) if got else False}
        print(f"    gamut: {res['modes']['gamut']}", flush=True)
        capture_window(win, out / "gamut.png")
    except Exception as exc:                      # noqa: BLE001
        res["modes"]["gamut"] = {"error": repr(exc)}
        print(f"    gamut: {exc!r}", flush=True)

    bad = [r for r in res["states"] if not r["match"]]
    res["mismatches"] = bad
    (out / "adv18a.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\n    {len(res['states'])} states probed, {len(bad)} mismatches",
          flush=True)
    win.close(); pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

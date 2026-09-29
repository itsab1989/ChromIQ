#!/usr/bin/env python3
"""Adversary 18d, in a REAL window.

Two states no round has put the overlay in:

  * KNUT'S HONEYCOMB, left as it comes (CR30, Letter, hexagonal). One comb is
    greyed by `set_helper_markers_supported(one_axis_only=True)` while the
    engine draws the other, so the overlay's flags and the sheet's need not
    agree. Both marker boxes at 0.
  * A BUILD IN FLIGHT: the overlay read while Generate Chart is still running.
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


def sheet_lines(tab, panel):
    from core.text_io import read_text
    from workflow.layout_engine import instruments, geometry, papers
    from workflow.layout_engine.presets import LayoutRecipe
    ch = Path(tab._margin_ti2).with_suffix(".channels.json")
    rec = LayoutRecipe.from_channels_json(ch)
    if rec is None:
        return None, None
    m = re.search(r"NUMBER_OF_SETS\s+(\d+)",
                  read_text(Path(tab._margin_ti2), lenient=True))
    n = int(m.group(1)) if m else 0
    kw = rec.build_kwargs(); kw["area_target_count"] = n
    g = instruments.geom_from_build_kwargs(kw)
    w, h = papers.dimensions_mm(rec.paper)
    lay = geometry.compute(g, w, h, n)
    return rec, geometry.helper_marker_lines_mm(
        g, w, h, lay,
        edge_mm=(float(panel.helper_marker_edge.value()) or 2.0),
        length_mm=(float(panel.helper_marker_len.value()) or 2.0),
        per_patch=int(panel.helper_marker_per_patch.value()),
        top_bottom=bool(panel.helper_markers_top_bottom.isChecked()),
        sides=bool(panel.helper_markers_sides.isChecked()))


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv18d-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True)):
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
    print(f"    window on screen: {bool(win.isVisible())}", flush=True)
    win._tabs.setCurrentWidget(win._tab_chart); tab = win._tab_chart
    pump(app, 800); tab._user_switch_mode("manual"); pump(app, 1500)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("adv18d")
    combo = tab._preset_combo
    i = combo.findData(PRESET); assert i >= 0
    combo.setCurrentIndex(i); combo.activated.emit(i); pump(app, 1500)
    for _ in range(500):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 1200)
    panel = tab._manual_layout_panel
    res = {"window_on_screen": bool(win.isVisible())}
    grp = getattr(panel, "_helper_markers_grp", None)
    panel.helper_markers_cb.setChecked(True)
    panel.helper_markers_top_bottom.setChecked(True)
    panel.helper_markers_sides.setChecked(True)
    panel.helper_marker_per_patch.setValue(3)
    panel.helper_marker_edge.setValue(0.0)
    panel.helper_marker_len.setValue(0.0)
    pump(app, 900)
    res["honeycomb"] = {
        "group_enabled": bool(grp.isEnabled()) if grp else None,
        "one_axis_only": bool(getattr(panel, "_hm_one_axis_only", False)),
        "axis_is_top_bottom": bool(getattr(panel, "_hm_axis_is_top_bottom",
                                           False))}
    # the build, with the overlay read WHILE it runs
    tab._generate_btn.click()
    in_flight = []
    started = False
    for k in range(900):
        pump(app, 200)
        if not tab._generate_btn.isEnabled():
            started = True
        if k < 24:
            try:
                got = tab._helper_marker_lines_frac()
                in_flight.append({"tick": k,
                                  "lines": 0 if not got or not got[0] else len(got[0]),
                                  "pending": bool(got[1]) if got else None,
                                  "generate_enabled": bool(tab._generate_btn.isEnabled())})
            except Exception as exc:                 # noqa: BLE001
                in_flight.append({"tick": k, "error": repr(exc)})
        if started and tab._generate_btn.isEnabled() and getattr(
                tab, "_margin_tiffs", None):
            break
    pump(app, 2500)
    res["overlay_while_generating"] = in_flight
    res["build_was_seen_running"] = started
    print(f"    while generating: {in_flight}", flush=True)
    tab._refresh_helper_marker_overlay(); pump(app, 900)
    got = tab._helper_marker_lines_frac()
    lines, pending = (got if got is not None else (None, False))
    rec, sheet = sheet_lines(tab, panel)
    res["honeycomb"].update({
        "overlay": 0 if not lines else len(lines),
        "engine": 0 if sheet is None else len(sheet),
        "pending": bool(pending),
        "sheet_recipe_edge": float(getattr(rec, "helper_marker_edge_mm", -1)),
        "sheet_recipe_len": float(getattr(rec, "helper_marker_len_mm", -1)),
        "sheet_recipe_tb": bool(getattr(rec, "helper_markers_top_bottom", False)),
        "sheet_recipe_sides": bool(getattr(rec, "helper_markers_sides", False))})
    print(f"    honeycomb: {res['honeycomb']}", flush=True)
    capture_window(win, out / "honeycomb-0-0-after-Generate.png")
    (out / "adv18d.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    win.close(); pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

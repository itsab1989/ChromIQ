#!/usr/bin/env python3
"""Adversary 17f / P3b: the TOP strip-letter check with the marker boxes at 0.

`LayoutRecipe.build_kwargs` sends ``helper_marker_edge_mm or 2.0``, so a box
typed 0 draws a 2 mm marker and `geometry.strip_label_reserve_mm` puts the
label band 5.0 mm down the page. Round 5 put that fact in
`_marker_reserve_args` and swept the two BOTTOM checks with it; the top one was
left reading the recipe field raw, and asks for 0 + 0 + 1 mm.

Driven on an i1 sheet, where the patches are rectangles and the measured top is
the box, so what the panel is told and what the sheet does are comparable.
"""
from __future__ import annotations

import json
import os
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


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN"
    tag = sys.argv[2] if len(sys.argv) > 2 else "now"
    out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17f3-"))
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
    print(f"    window on screen: {win.isVisible()}", flush=True)
    win._tabs.setCurrentWidget(win._tab_chart); tab = win._tab_chart
    pump(app, 800); tab._user_switch_mode("manual"); pump(app, 1500)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("test")
    pump(app, 800)
    panel = tab._manual_layout_panel
    if panel.use_instr_margins.isChecked():
        panel.use_instr_margins.setChecked(False); pump(app, 500)
    if panel.instr.findData("i1") >= 0:
        panel.instr.setCurrentIndex(panel.instr.findData("i1")); pump(app, 900)
    panel.paper.setCurrentIndex(panel.paper.findData("A4"))
    panel.layout_mode.setCurrentIndex(panel.layout_mode.findData("area_first"))
    panel.margins["t"].setValue(8.0)
    panel.margins["b"].setValue(12.0)
    panel.margins["l"].setValue(12.0); panel.margins["r"].setValue(12.0)
    panel.text_edge_top.setValue(2.0)
    panel.helper_markers_cb.setChecked(True); pump(app, 400)
    panel.helper_markers_top_bottom.setChecked(True)
    panel.helper_marker_edge.setValue(0.0)
    panel.helper_marker_len.setValue(0.0)
    panel.chart_text.setText("test")
    pump(app, 800)
    tab._update_margin_inspector(); pump(app, 800)

    mp = getattr(tab, "_margin_panel", None)
    last = getattr(mp, "_last_status", None) if mp is not None else None
    msgs = list((last[1].get("overlap_warnings") or []) if last else [])
    said = [m for m in msgs if "strip letters are printed over the patches" in m]
    # …AND THE SAME METHOD WITH NO PREVIEW REPORT, which is what the ⓘ and a
    # driver get, and which asks the recipe's own "Top" rather than the ink
    # measured off a preview that may not be of this state yet.
    no_report = [m for m in tab._engine_text_notes()[1]
                 if "strip letters are printed over the patches" in m]

    from workflow.layout_engine import geometry as _g, instruments as _i
    from workflow.layout_engine import papers as _p
    r = tab._current_layout_recipe()
    g = _i.geom_from_build_kwargs(r.build_kwargs())
    w, h = _p.dimensions_mm(str(r.paper))
    pl = _g.placement(g, w, h, _g.compute(g, w, h, 100000))
    ink = float(getattr(g, "label_ink_bottom_mm", 0.0) or 0.0)
    res = {"tag": tag,
           "typed_marker_boxes": [float(panel.helper_marker_edge.value()),
                                  float(panel.helper_marker_len.value())],
           "engine_draws_markers_at": [
               float(getattr(g, "helper_marker_edge_mm", 0.0) or 0.0),
               float(getattr(g, "helper_marker_len_mm", 0.0) or 0.0)],
           "strip_label_reserve_mm": round(_g.strip_label_reserve_mm(g), 2),
           "label_band_top_mm": round(float(pl.leader_top), 2),
           "label_band_bottom_mm": round(float(pl.leader_top) + ink, 2),
           "first_patch_row_top_mm": round(float(pl.y0_first), 2),
           "letters_over_the_patches_mm": round(
               float(pl.leader_top) + ink - float(pl.y0_first), 2),
           "strip_letter_warning": said,
           "strip_letter_warning_without_a_preview_report": no_report,
           "all_notices": msgs}
    print(f"    [{tag}] band {res['label_band_top_mm']}..."
          f"{res['label_band_bottom_mm']} mm, first patch row "
          f"{res['first_patch_row_top_mm']} mm -> "
          f"{res['letters_over_the_patches_mm']} mm on the patches", flush=True)
    print(f"    [{tag}] the panel says: {said}", flush=True)
    print(f"    [{tag}] the same method with no preview report says: "
          f"{[m[:90] for m in no_report]}", flush=True)
    capture_window(win, out / f"P3b-{tag}.png")
    (out / f"P3b-{tag}.json").write_text(json.dumps(res, indent=2,
                                                    ensure_ascii=False),
                                         encoding="utf-8")
    win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

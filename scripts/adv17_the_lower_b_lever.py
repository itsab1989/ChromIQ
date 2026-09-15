#!/usr/bin/env python3
"""Adversary 17: does *"lower “B” under “Text distance from edge (mm)”"* work?

The bottom-text height warning offers two remedies. This measures the second
one, on the sheet, on Knut's own CR30 Letter preset.

Two ways it can fail to deliver:

* the block is anchored at ``sheet_text_bottom_mm`` = the LARGER of "B" and the
  helper markers' own reach, so with markers on, lowering "B" below that reach
  moves nothing at all;
* the engine's bottom reserve is ``that anchor + 4.2 x lines``, so lowering the
  anchor lowers the PATCHES by the same amount: the gap does not open.

It also records `predicted_patch_bottom_mm` beside the measured patch bottom in
BOTH layout modes, which is the number the new check is built on.
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
from onscreen_capture import capture_window, session_is_locked   # noqa: E402
from drive_182_knut_bottom_text_height import (on_screen, pump,  # noqa: E402
                                               text_ink_mm)

PRESET = "__chromiq_knut_cr30_letter_792p_2pages_portrait_w11_0mm_hexagonal_straight__"
TEXT = "test-{project}-page {page}-{date}-{paper}-{patchcount} patches"


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17b-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

    QDialog.exec = lambda self: 1                 # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart, predicted_patch_bottom_mm
    from ui.theme import apply_appearance
    from workflow import text_edge_fit as tef
    from workflow.layout_engine import instruments, raster
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1620, 1060)
    win.show(); win.raise_()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    combo = tab._preset_combo
    i = combo.findData(PRESET)
    assert i >= 0
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("test")
    combo.setCurrentIndex(i); combo.activated.emit(i)
    pump(app, 1500)
    for _ in range(400):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 800)
    panel = tab._manual_layout_panel
    if panel.use_instr_margins.isChecked():
        panel.use_instr_margins.setChecked(False); pump(app, 400)
    panel.chart_text.setText(TEXT)
    panel.margins["b"].setValue(11.0)
    panel.stamp_command.setChecked(False)
    pump(app, 600)
    r0 = panel.get_recipe()
    preset_facts = {
        "layout_mode": r0.layout_mode, "paper": r0.paper, "dpi": r0.dpi,
        "helper_markers": bool(r0.helper_markers),
        "helper_marker_edge_mm": float(r0.helper_marker_edge_mm or 0),
        "helper_marker_len_mm": float(r0.helper_marker_len_mm or 0),
        "B (text_edge_mm)": float(r0.text_edge_mm or 0),
        "anchor sheet_text_bottom_mm": round(tef.sheet_text_bottom_mm(
            float(r0.text_edge_mm or 0), bool(r0.helper_markers),
            float(r0.helper_marker_edge_mm or 0),
            float(r0.helper_marker_len_mm or 0),
            bool(r0.helper_markers_top_bottom)), 3),
    }
    print(json.dumps(preset_facts, indent=2), flush=True)

    ti1 = None
    for attr in ("_preset_ti1_path", "_builtin_ti1_path"):
        v = getattr(tab, attr, None)
        if v and Path(v).is_file():
            ti1 = Path(v); break
    assert ti1

    # --- part 1: the prediction against the sheet, in BOTH layout modes
    pred_rows = []
    for want in ("area_first", "patch_first"):
        j = panel.layout_mode.findData(want)
        panel.layout_mode.setCurrentIndex(j)
        pump(app, 700)
        for stamp in (False, True):
            panel.stamp_command.setChecked(stamp)
            panel.chart_text_size.setValue(0.0)
            pump(app, 700)
            tab._update_margin_inspector(); pump(app, 700)
            r = panel.get_recipe()
            kw = r.build_kwargs()
            geom = raster.apply_furniture_reserves(
                instruments.geom_from_build_kwargs(kw), kw)
            npat = (tab._onscreen_patch_total() or tab._estimate_patch_total())
            pred = predicted_patch_bottom_mm(r, geom, npat)
            ink = text_ink_mm(r, ti1, f"pred-{want}-{int(stamp)}")
            pred_rows.append({
                "layout_mode": r.layout_mode, "lines": 1 + int(stamp),
                "npat_from_tab": npat,
                "predicted_patch_bottom_mm": None if pred is None else round(pred, 2),
                "measured_patch_bottom_mm": ink.get("patch_bottom_up_mm"),
                "error_mm": (None if pred is None
                             or ink.get("patch_bottom_up_mm") is None
                             else round(pred - ink["patch_bottom_up_mm"], 2)),
            })
            print("    pred", pred_rows[-1], flush=True)

    # --- part 2: the "lower B" lever, in area_first where the warning lives
    j = panel.layout_mode.findData("area_first")
    panel.layout_mode.setCurrentIndex(j)
    panel.stamp_command.setChecked(False)
    panel.chart_text_size.setValue(28.0)          # a real collision
    pump(app, 800)
    b_rows = []
    for markers in (True, False):
        panel.helper_markers_cb.setChecked(markers)
        pump(app, 600)
        for b in (7.0, 5.0, 4.0, 3.0, 2.0, 1.0, 0.0):
            panel.text_edge.setValue(float(b))
            pump(app, 600)
            tab._update_margin_inspector(); pump(app, 800)
            r = panel.get_recipe()
            said = on_screen(tab)
            ink = text_ink_mm(r, ti1, f"b{b:g}-{int(markers)}")
            row = {"markers": markers, "B_typed": b,
                   "B_effective": float(r.text_edge_mm or 0),
                   "anchor_mm": round(tef.sheet_text_bottom_mm(
                       float(r.text_edge_mm or 0), bool(r.helper_markers),
                       float(r.helper_marker_edge_mm or 0),
                       float(r.helper_marker_len_mm or 0),
                       bool(r.helper_markers_top_bottom)), 2),
                   "patch_bottom_up_mm": ink.get("patch_bottom_up_mm"),
                   "text_top_up_mm": ink.get("text_top_up_mm"),
                   "text_bottom_up_mm": ink.get("text_bottom_up_mm"),
                   "gap_mm": ink.get("gap_patches_to_text_mm"),
                   "warn": len(said["height"])}
            b_rows.append(row)
            print(f"    markers={markers} B={b:4.1f} anchor={row['anchor_mm']:5.2f} "
                  f"patches->{row['patch_bottom_up_mm']} "
                  f"text_top={row['text_top_up_mm']} gap={row['gap_mm']} "
                  f"warn={row['warn']}", flush=True)

    ok, why = capture_window(win, out / "01-lower-b-lever.png")
    facts = {"preset": preset_facts, "prediction_vs_sheet": pred_rows,
             "lower_b_sweep": b_rows,
             "photo": "01-lower-b-lever.png" if ok else f"REFUSED {why}",
             "locked": session_is_locked()}
    (out / "lower-b-lever.json").write_text(
        json.dumps(facts, indent=2, ensure_ascii=False), encoding="utf-8")
    win.close(); pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

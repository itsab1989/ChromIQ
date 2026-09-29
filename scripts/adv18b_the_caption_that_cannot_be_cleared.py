#!/usr/bin/env python3
"""Adversary 18b, in a REAL window.

F1  THE "PRESS GENERATE CHART" CAPTION CANNOT BE CLEARED ON A SHEET WHOSE
    MARKER BOX WAS LEFT AT 0.

    Round 17 made the overlay read the two marker boxes the way the engine
    does (`value() or 2.0`) and left the other half of the same comparison
    reading the SHEET raw: `printed = tuple(getattr(rec, k) for k in
    _HM_KEYS)`, and `LayoutRecipe.to_dict` is `asdict`, so `channels.json`
    stores the 0.0 the user typed. 0.0 != 2.0, so `pending` is True on a sheet
    that carries exactly those dashes, the preview draws them in the accent
    colour under "Markers not on this sheet yet - press Generate Chart", and
    pressing Generate Chart writes 0.0 again.
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

PRESET = ("__chromiq_knut_cr30_letter_792p_2pages_portrait"
          "_w11_0mm_hexagonal_straight__")


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv18b-"))
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
    onscreen = bool(win.isVisible())
    print(f"    window on screen: {onscreen}", flush=True)
    win._tabs.setCurrentWidget(win._tab_chart); tab = win._tab_chart
    pump(app, 800); tab._user_switch_mode("manual"); pump(app, 1500)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("adv18b")
    combo = tab._preset_combo
    i = combo.findData(PRESET); assert i >= 0
    combo.setCurrentIndex(i); combo.activated.emit(i); pump(app, 1500)
    for _ in range(500):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 1200)
    panel = tab._manual_layout_panel
    if panel.instr.findData("i1") >= 0:
        panel.instr.setCurrentIndex(panel.instr.findData("i1")); pump(app, 900)
    panel.paper.setCurrentIndex(panel.paper.findData("A4"))
    if panel.use_instr_margins.isChecked():
        panel.use_instr_margins.setChecked(False); pump(app, 400)
    for k, v in (("t", 20.0), ("b", 20.0), ("l", 20.0), ("r", 20.0)):
        panel.margins[k].setValue(v)
    panel.helper_markers_cb.setChecked(True)
    panel.helper_markers_top_bottom.setChecked(True)
    panel.helper_markers_sides.setChecked(True)
    panel.helper_marker_per_patch.setValue(3)
    panel.helper_marker_edge.setValue(0.0)
    panel.helper_marker_len.setValue(0.0)
    pump(app, 800)

    res = {"window_on_screen": onscreen, "rounds": []}

    def generate():
        tab._generate_btn.click()
        for _ in range(900):
            pump(app, 200)
            if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
                break
        pump(app, 2500)

    def state(tag):
        tab._refresh_helper_marker_overlay(); pump(app, 600)
        got = tab._helper_marker_lines_frac()
        lines, pending = (got if got is not None else (None, False))
        from workflow.layout_engine.presets import LayoutRecipe
        ch = Path(tab._margin_ti2).with_suffix(".channels.json")
        rec = LayoutRecipe.from_channels_json(ch)
        prev = getattr(tab, "_preview", None)
        row = {"tag": tag,
               "box_edge": float(panel.helper_marker_edge.value()),
               "box_len": float(panel.helper_marker_len.value()),
               "sheet_recipe_edge": float(getattr(rec, "helper_marker_edge_mm", -1)),
               "sheet_recipe_len": float(getattr(rec, "helper_marker_len_mm", -1)),
               "overlay_dashes": 0 if not lines else len(lines),
               "pending_caption": bool(pending),
               "preview_pending_flag": bool(getattr(prev, "_helper_markers_pending", False))}
        res["rounds"].append(row)
        print(f"    {tag:<44} box {row['box_edge']:.1f}/{row['box_len']:.1f}  "
              f"sheet recipe {row['sheet_recipe_edge']:.1f}/"
              f"{row['sheet_recipe_len']:.1f}  overlay {row['overlay_dashes']}  "
              f"CAPTION {row['pending_caption']}", flush=True)
        return row

    generate(); state("after Generate at 0.0/0.0")
    capture_window(win, out / "F1-after-one-Generate-caption-still-on.png")
    generate(); state("after a SECOND Generate, nothing touched")
    capture_window(win, out / "F1-after-a-second-Generate-caption-still-on.png")
    for e, l in ((2.0, 2.0), (0.1, 0.1), (0.0, 2.0), (2.0, 0.0), (0.0, 0.0)):
        panel.helper_marker_edge.setValue(e); panel.helper_marker_len.setValue(l)
        pump(app, 400); state(f"box typed {e:.1f}/{l:.1f} (sheet unchanged)")
    # …and the control: a sheet generated with a box the engine reads as itself
    panel.helper_marker_edge.setValue(2.0); panel.helper_marker_len.setValue(2.0)
    pump(app, 400); generate(); state("CONTROL: generated at 2.0/2.0")
    capture_window(win, out / "F1-control-generated-at-2-2-no-caption.png")

    (out / "adv18b.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    win.close(); pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

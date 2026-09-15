#!/usr/bin/env python3
"""Adversary 18c, in a REAL window.

The overlay's GUIDED branch is not dead code. Build a chart in Manual with the
two marker boxes at 0, then press GUIDED: the chart stays in the preview, the
mode reads "guided", and `_helper_marker_lines_frac` takes its else-branch,
which reads the sheet's own recipe. `channels.json` stores the raw 0.0
(`to_dict` is `asdict`), so that branch is the one place left where
`_marker_reserve_args` decides whether the reader sees the sheet's dashes or
nothing at all.
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
    tag = sys.argv[2] if len(sys.argv) > 2 else "run"
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv18c-"))
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
        tab._manual_target_name_edit.setText("adv18c")
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
    tab._generate_btn.click()
    for _ in range(900):
        pump(app, 200)
        if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 2500)
    got = tab._helper_marker_lines_frac()
    manual_n = 0 if not got or not got[0] else len(got[0])
    # …and now GUIDED, with that same sheet still in the preview.
    tab._user_switch_mode("guided"); pump(app, 1500)
    tab._refresh_helper_marker_overlay(); pump(app, 800)
    got = tab._helper_marker_lines_frac()
    guided_n = 0 if not got or not got[0] else len(got[0])
    from workflow.layout_engine.presets import LayoutRecipe
    rec = LayoutRecipe.from_channels_json(
        Path(tab._margin_ti2).with_suffix(".channels.json"))
    res = {"tag": tag, "window_on_screen": bool(win.isVisible()),
           "mode": tab._current_mode(),
           "sheet_recipe_edge": float(getattr(rec, "helper_marker_edge_mm", -1)),
           "sheet_recipe_len": float(getattr(rec, "helper_marker_len_mm", -1)),
           "overlay_in_manual": manual_n, "overlay_in_guided": guided_n,
           "pending_in_guided": bool(got[1]) if got else False}
    print(f"    [{tag}] sheet recipe {res['sheet_recipe_edge']:.1f}/"
          f"{res['sheet_recipe_len']:.1f}  overlay in MANUAL {manual_n}  "
          f"in GUIDED {guided_n}", flush=True)
    capture_window(win, out / f"{tag}-guided-overlay-{guided_n}-dashes.png")
    (out / f"adv18c-{tag}.json").write_text(json.dumps(res, indent=2),
                                            encoding="utf-8")
    win.close(); pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

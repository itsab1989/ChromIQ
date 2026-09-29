#!/usr/bin/env python3
"""Adversary 18e, in a REAL window.

Unticking ONE EDGE of the ruler markers on a sheet that carries them raises the
proposal flag ("Markers not on this sheet yet - press Generate Chart"), which is
what `test_switching_an_edge_off_makes_it_a_proposal` pins. Unticking the MASTER
box, "Print helper markers", does not: `_helper_marker_lines_frac` returns None
before the comparison is made, the preview is told `pending=False`, and the
sheet in front of the reader goes on showing the dashes that are printed into
its ink with nothing to say the setting no longer describes it.
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv18e-"))
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
        tab._manual_target_name_edit.setText("adv18e")
    combo = tab._preset_combo
    i = combo.findData(PRESET); assert i >= 0
    combo.setCurrentIndex(i); combo.activated.emit(i); pump(app, 1500)
    for _ in range(500):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 1200)
    panel = tab._manual_layout_panel
    panel.helper_markers_cb.setChecked(True)
    panel.helper_markers_top_bottom.setChecked(True)
    panel.helper_markers_sides.setChecked(True)
    panel.helper_marker_per_patch.setValue(3)
    panel.helper_marker_edge.setValue(2.0)
    panel.helper_marker_len.setValue(4.0)
    pump(app, 800)
    tab._generate_btn.click()
    started = False
    for _ in range(900):
        pump(app, 200)
        if not tab._generate_btn.isEnabled():
            started = True
        if started and tab._generate_btn.isEnabled() and getattr(
                tab, "_margin_tiffs", None):
            break
    pump(app, 3000)

    def look(tag):
        tab._refresh_helper_marker_overlay(); pump(app, 700)
        got = tab._helper_marker_lines_frac()
        prev = getattr(tab, "_preview", None)
        row = {"tag": tag,
               "lines": 0 if not got or not got[0] else len(got[0]),
               "pending": bool(got[1]) if got else False,
               "preview_pending": bool(getattr(prev, "_helper_markers_pending",
                                               False))}
        print(f"    {tag:<44} dashes {row['lines']:>4}  CAPTION "
              f"{row['preview_pending']}", flush=True)
        return row

    res = {"window_on_screen": bool(win.isVisible()), "rounds": []}
    res["rounds"].append(look("as generated, markers on"))
    capture_window(win, out / "A-as-generated-black-dashes-no-caption.png")
    panel.helper_markers_sides.setChecked(False); pump(app, 500)
    res["rounds"].append(look("ONE EDGE off (sides)"))
    capture_window(win, out / "B-sides-off-caption-appears.png")
    panel.helper_markers_sides.setChecked(True); pump(app, 500)
    panel.helper_markers_cb.setChecked(False); pump(app, 700)
    res["rounds"].append(look("MASTER BOX off"))
    capture_window(win, out / "C-master-box-off-ink-remains-no-caption.png")
    (out / "adv18e.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    win.close(); pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

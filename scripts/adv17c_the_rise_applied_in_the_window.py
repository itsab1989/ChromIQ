#!/usr/bin/env python3
"""Adversary 17c: type the number the message names into the box it names.

`margin_rise_that_clears_mm` tests its answer against a PREDICTION of the patch
bottom, and that prediction is documented as running "1.42 mm low to 0.13 mm
high" in area_first. A remedy is a promise, so it is kept only if the warning
is gone after the reader does what it says -- in the real window, with the real
spin box, rounded the way the spin box rounds.
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
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

PRESET = ("__chromiq_knut_cr30_letter_792p_2pages_portrait"
          "_w11_0mm_hexagonal_straight__")
RISE = re.compile(r"by about ([0-9]+\.[0-9]) mm")


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def said(tab):
    panel = getattr(tab, "_margin_panel", None)
    last = getattr(panel, "_last_status", None) if panel is not None else None
    msgs = [m for m in ((last[1].get("overlap_warnings") or []) if last else [])
            if "along the bottom" in m]
    return [m for m in msgs if "runs into the patches" in m
            or "run into the patches" in m]


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17cr-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True),
                 ("margin_violation_notify", True)):
        settings.set(k, v)
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
    combo = tab._preset_combo
    i = combo.findData(PRESET); assert i >= 0
    combo.setCurrentIndex(i); combo.activated.emit(i); pump(app, 1500)
    for _ in range(400):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 800)
    panel = tab._manual_layout_panel
    if panel.use_instr_margins.isChecked():
        panel.use_instr_margins.setChecked(False); pump(app, 400)
    panel.chart_text.setText("test-{project}-page {page}-{paper}")
    mb_box = panel.margins["b"]
    print(f"    bottom-margin spin box: min={mb_box.minimum()} "
          f"max={mb_box.maximum()} step={mb_box.singleStep()} "
          f"decimals={mb_box.decimals()}", flush=True)

    def refresh():
        pump(app, 280); tab._update_margin_inspector(); pump(app, 400)
        return said(tab)

    rows = []
    shot = {"n": 0}
    for mode in ("area_first", "patch_first"):
        panel.layout_mode.setCurrentIndex(panel.layout_mode.findData(mode))
        for markers in (False, True):
            panel.helper_markers_cb.setChecked(markers)
            if markers:
                panel.helper_marker_edge.setValue(4.0)
                panel.helper_marker_len.setValue(2.0)
                panel.helper_markers_top_bottom.setChecked(True)
            for B in (0.5, 4.0, 9.0):
                panel.text_edge.setValue(B)
                for stamp in (False, True):
                    panel.stamp_command.setChecked(stamp)
                    for pt in (14.0, 20.0, 28.0, 40.0):
                        panel.chart_text_size.setValue(pt)
                        for mb in (8.0, 11.0):
                            mb_box.setValue(mb)
                            msgs = refresh()
                            if not msgs:
                                continue
                            m = RISE.search(msgs[0])
                            if not m:
                                rows.append({"mode": mode, "markers": markers,
                                             "B": B, "lines": 1 + int(stamp),
                                             "pt": pt, "margin_b": mb,
                                             "named_no_rise": True})
                                continue
                            rise = float(m.group(1))
                            mb_box.setValue(round(mb + rise, 1))
                            landed = mb_box.value()
                            gone = not refresh()
                            rows.append({"mode": mode, "markers": markers,
                                         "B": B, "lines": 1 + int(stamp),
                                         "pt": pt, "margin_b": mb,
                                         "advised_rise": rise,
                                         "box_landed_on": landed,
                                         "warning_gone": gone})
                            if not gone:
                                print(f"    KEPT UP {mode} mk={int(markers)} "
                                      f"B={B} lines={1+int(stamp)} {pt:.0f}pt "
                                      f"mb={mb} rise={rise} -> box={landed}",
                                      flush=True)
                                if shot["n"] == 0:
                                    ok, _w = capture_window(
                                        win, out / "04-the-rise-kept-it-up.png")
                                    shot["n"] = 1
                            mb_box.setValue(mb)

    tried = [x for x in rows if "advised_rise" in x]
    broken = [x for x in tried if not x["warning_gone"]]
    rounded = [x for x in tried
               if abs(x["box_landed_on"] - (x["margin_b"] + x["advised_rise"]))
               > 1e-6]
    verdict = {
        "warning states driven": len(rows),
        "…that named a rise": len(tried),
        "…where the rise left the warning up": len(broken),
        "…where the spin box could not hold the number named": len(rounded),
        "named no rise at all": len(rows) - len(tried),
        "locked": session_is_locked(),
    }
    (out / "the-rise-applied.json").write_text(json.dumps(
        {"verdict": verdict, "broken": broken, "rounded": rounded[:10],
         "rows": rows}, indent=2), encoding="utf-8")
    print(json.dumps(verdict, indent=2), flush=True)
    win.close(); pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

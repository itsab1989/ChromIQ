#!/usr/bin/env python3
"""Adversary 17b: where the lever IS still offered, pulling it must clear it.

The fix withholds "lowering B buys the same room" wherever the sheet says the
lever cannot finish the job. This is the other half of the proof: on every
state where the sentence is still offered, "B" is taken to the bottom of its
range in the real window and the warning has to be gone.
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

PRESET = ("__chromiq_knut_cr30_letter_792p_2pages_portrait"
          "_w11_0mm_hexagonal_straight__")


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
    out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17blk-"))
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
    pump(app, 300)

    rows = []
    for mode in ("area_first", "patch_first"):
        j = panel.layout_mode.findData(mode)
        panel.layout_mode.setCurrentIndex(j)
        for markers in (False, True):
            panel.helper_markers_cb.setChecked(markers)
            if markers:
                panel.helper_marker_edge.setValue(4.0)
                panel.helper_marker_len.setValue(2.0)
                panel.helper_markers_top_bottom.setChecked(True)
            for stamp in (False, True):
                panel.stamp_command.setChecked(stamp)
                for b in (4.0, 8.0, 12.0):
                    panel.text_edge.setValue(b)
                    for pt in (14.0, 20.0, 28.0, 40.0):
                        panel.chart_text_size.setValue(pt)
                        panel.margins["b"].setValue(11.0)
                        pump(app, 350)
                        tab._update_margin_inspector(); pump(app, 450)
                        msgs = said(tab)
                        if not msgs:
                            continue
                        m = msgs[0]
                        offered = "moves the text down" in m
                        if not offered:
                            rows.append({"mode": mode, "markers": markers,
                                         "lines": 1 + int(stamp), "B": b,
                                         "pt": pt, "offered": False})
                            continue
                        # pull it all the way down
                        panel.text_edge.setValue(0.1)
                        pump(app, 350)
                        tab._update_margin_inspector(); pump(app, 450)
                        gone = not said(tab)
                        panel.text_edge.setValue(b); pump(app, 200)
                        rows.append({"mode": mode, "markers": markers,
                                     "lines": 1 + int(stamp), "B": b, "pt": pt,
                                     "offered": True,
                                     "warning_gone_after_pulling_it": gone})
                        print(f"    {mode:11s} mk={int(markers)} "
                              f"lines={1+int(stamp)} B={b:4.1f} {pt:4.0f}pt "
                              f"offered -> cleared={gone}", flush=True)

    offered = [x for x in rows if x.get("offered")]
    broken = [x for x in offered if not x.get("warning_gone_after_pulling_it")]
    verdict = {"states that still offer the lever": len(offered),
               "states where pulling it does NOT clear the warning": len(broken),
               "every offer is honest": not broken,
               "warning states seen": len(rows)}
    ok, why = capture_window(win, out / "05-the-offer-is-kept.png")
    (out / "the-lever-offer-is-kept.json").write_text(json.dumps(
        {"rows": rows, "verdict": verdict, "broken": broken,
         "photo": "05-the-offer-is-kept.png" if ok else f"REFUSED {why}",
         "locked": session_is_locked()}, indent=2), encoding="utf-8")
    print(json.dumps(verdict, indent=2), flush=True)
    print(f"    photo: {'ok' if ok else 'REFUSED ' + str(why)}", flush=True)
    win.close(); pump(app, 400)
    return 0 if not broken else 1


if __name__ == "__main__":
    raise SystemExit(main())

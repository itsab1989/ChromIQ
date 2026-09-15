#!/usr/bin/env python3
"""Adversary 17c: the OTHER sentence in the same message, which nothing asks
the sheet about.

Round 2 made "lowering B buys the same room" conditional on
`lowering_b_clears`. The sentence beside it -- "the ruler helper markers hold
the text ... Switching “Print helper markers” off, or shortening them, hands
that distance back to “B”" -- is chosen by ONE comparison and names a route
that is never tried. This drives the route in the real window: switch the
markers off, take "B" to the bottom of its range, and see whether the warning
is gone.

And the third state nobody asks about: a box that READS 0 draws the text at
4.0 mm, so typing 0.1 into it moves the text 3.9 mm DOWN. The panel withholds
every word about that; this measures how often the keystroke would have
cleared the warning on its own.
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
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN"
    out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17c-"))
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
    print(f"    B spin box: minimum={panel.text_edge.minimum()} "
          f"step={panel.text_edge.singleStep()} "
          f"decimals={panel.text_edge.decimals()}", flush=True)

    def refresh():
        pump(app, 300); tab._update_margin_inspector(); pump(app, 420)
        return said(tab)

    gate1, gate2, gate3 = [], [], []
    photo_taken = {"g1": False, "g2": False}
    for mode in ("area_first", "patch_first"):
        j = panel.layout_mode.findData(mode)
        panel.layout_mode.setCurrentIndex(j)
        for mb in (8.0, 11.0, 14.0):
            panel.margins["b"].setValue(mb)
            for stamp in (False, True):
                panel.stamp_command.setChecked(stamp)
                for pt in (14.0, 24.0, 40.0):
                    panel.chart_text_size.setValue(pt)

                    # ---- GATE 1: the markers-off route ---------------------
                    panel.helper_markers_cb.setChecked(True)
                    panel.helper_marker_edge.setValue(4.0)
                    panel.helper_marker_len.setValue(2.0)
                    panel.helper_markers_top_bottom.setChecked(True)
                    panel.text_edge.setValue(4.0)
                    msgs = refresh()
                    if msgs and "will not help here" in msgs[0]:
                        # do exactly what the sentence names
                        panel.helper_markers_cb.setChecked(False)
                        panel.text_edge.setValue(0.1)
                        gone = not refresh()
                        row = {"mode": mode, "margin_b": mb,
                               "lines": 1 + int(stamp), "pt": pt,
                               "said": "markers hold it",
                               "warning_gone_after_the_named_route": gone}
                        gate1.append(row)
                        print(f"    G1 {mode:11s} mb={mb:4.1f} "
                              f"lines={1+int(stamp)} {pt:4.0f}pt -> "
                              f"route cleared={gone}", flush=True)
                        if not gone and not photo_taken["g1"]:
                            panel.helper_markers_cb.setChecked(True)
                            panel.text_edge.setValue(4.0)
                            refresh()
                            ok, why = capture_window(
                                win, out / "01-gate1-the-sentence.png")
                            panel.helper_markers_cb.setChecked(False)
                            panel.text_edge.setValue(0.1)
                            refresh()
                            ok2, why2 = capture_window(
                                win, out / "02-gate1-after-the-route.png")
                            photo_taken["g1"] = bool(ok and ok2)
                            row["photos"] = [str(ok), str(ok2), str(why),
                                             str(why2)]

                    # ---- GATE 2: a box that reads 0 -----------------------
                    panel.helper_markers_cb.setChecked(False)
                    panel.text_edge.setValue(0.0)
                    msgs = refresh()
                    if msgs and "moves the text down" not in msgs[0] \
                            and "will not help" not in msgs[0]:
                        before = msgs[0]
                        panel.text_edge.setValue(0.1)
                        gone = not refresh()
                        row = {"mode": mode, "margin_b": mb,
                               "lines": 1 + int(stamp), "pt": pt,
                               "said": "no word about B",
                               "typing_0_1_clears_it": gone,
                               "message": before[:120]}
                        gate2.append(row)
                        print(f"    G2 {mode:11s} mb={mb:4.1f} "
                              f"lines={1+int(stamp)} {pt:4.0f}pt -> "
                              f"0.1 clears={gone}", flush=True)
                        if gone and not photo_taken["g2"]:
                            panel.text_edge.setValue(0.0); refresh()
                            ok, why = capture_window(
                                win, out / "03-gate2-box-reads-zero.png")
                            photo_taken["g2"] = bool(ok)
                            row["photo"] = str(ok) or str(why)
                        panel.text_edge.setValue(0.0)

                    # ---- GATE 3: the offer is validated at 0.1, and the
                    #      spin box steps in 0.5 from a minimum of 0.0, so the
                    #      arrows can never stop there.
                    panel.text_edge.setValue(4.0)
                    msgs = refresh()
                    if msgs and "moves the text down" in msgs[0]:
                        panel.text_edge.setValue(0.1)
                        at_tenth = not refresh()
                        panel.text_edge.setValue(0.5)
                        at_half = not refresh()
                        panel.text_edge.setValue(0.0)
                        at_zero = not refresh()
                        gate3.append({"mode": mode, "margin_b": mb,
                                      "lines": 1 + int(stamp), "pt": pt,
                                      "clears_at_typed_0_1": at_tenth,
                                      "clears_at_arrow_0_5": at_half,
                                      "clears_at_arrow_0_0": at_zero})
                        print(f"    G3 {mode:11s} mb={mb:4.1f} "
                              f"lines={1+int(stamp)} {pt:4.0f}pt -> "
                              f"0.1={at_tenth} 0.5={at_half} 0.0={at_zero}",
                              flush=True)

    g1_bad = [x for x in gate1 if not x["warning_gone_after_the_named_route"]]
    g2_bad = [x for x in gate2 if x["typing_0_1_clears_it"]]
    verdict = {
        "gate-1 states (the markers-hold sentence)": len(gate1),
        "…where the route it names leaves the warning up": len(g1_bad),
        "gate-2 states (box reads 0, nothing said about B)": len(gate2),
        "…where typing 0.1 into B clears the warning on its own": len(g2_bad),
        "offers validated at a typed 0.1": len(gate3),
        "…that do NOT clear at 0.5, the lowest the arrows can reach":
            len([x for x in gate3 if x["clears_at_typed_0_1"]
                 and not x["clears_at_arrow_0_5"]]),
        "…that do NOT clear at 0.0, one click below 0.5":
            len([x for x in gate3 if x["clears_at_typed_0_1"]
                 and not x["clears_at_arrow_0_0"]]),
        "locked": session_is_locked(),
    }
    (out / "the-route-gate-one-names.json").write_text(json.dumps(
        {"verdict": verdict, "gate1": gate1, "gate2": gate2,
         "gate3": gate3,
         "B spin box": {"minimum": panel.text_edge.minimum(),
                        "step": panel.text_edge.singleStep(),
                        "decimals": panel.text_edge.decimals()}}, indent=2),
        encoding="utf-8")
    print(json.dumps(verdict, indent=2), flush=True)
    win.close(); pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

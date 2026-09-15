#!/usr/bin/env python3
"""Adversary 17d, probe 2: both new gates assume "B at the bottom of its range
is the best B", and the code's own docstring says it is not.

`markers_off_clears` and `lowering_b_clears` each ask the sheet ONE question:
rebuild with `text_edge_mm = 0.1`. `lowering_b_clears`'s own docstring says
that in patch-first, lowering "B" also lowers
`raster._furniture_reserves_mm`'s band and "can bring the patches down with it
and buy nothing at all" -- i.e. the predicate is NOT monotone in "B". The
margin search has a whole stability walk for exactly that property; these two
gates have a single probe at one end of the range.

So: sweep "B" across its whole range in the real window and find a state where
some reachable "B" clears the warning while 0.1 does not. There the sentence
is WITHHELD and the route it names would have worked -- the dual of the fault
round 3 fixed.

Also: does `_no_margin_clears_note` ever fire with Size on "auto", where
"Make the sheet text smaller" is not a lever the reader has?
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
B_SWEEP = [0.1, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 8.0,
           9.0, 10.0, 12.0, 15.0, 20.0]


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17d2-"))
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

    def refresh():
        pump(app, 240); tab._update_margin_inspector(); pump(app, 360)
        return said(tab)

    res = {"markers_route_withheld_but_works": [],
           "b_lever_withheld_but_works": [],
           "note_on_auto": [], "all": []}

    for mode in ("area_first", "patch_first"):
        j = panel.layout_mode.findData(mode)
        panel.layout_mode.setCurrentIndex(j)
        for mb in (6.0, 8.0, 11.0, 14.0, 18.0):
            panel.margins["b"].setValue(mb)
            for stamp in (False, True):
                panel.stamp_command.setChecked(stamp)
                for pt in (14.0, 20.0, 24.0, 28.0, 40.0):
                    panel.chart_text_size.setValue(pt)
                    tag = (f"{mode} mb={mb:4.1f} lines={1+int(stamp)} "
                           f"{pt:4.0f}pt")

                    # ---- A: the MARKERS route, with B swept -------------
                    panel.helper_markers_cb.setChecked(True)
                    panel.helper_marker_edge.setValue(4.0)
                    panel.helper_marker_len.setValue(2.0)
                    panel.helper_markers_top_bottom.setChecked(True)
                    panel.text_edge.setValue(4.0)
                    msgs = refresh()
                    if msgs:
                        offered = "will not help here" in msgs[0]
                        # do what the sentence names, markers off, and sweep B
                        panel.helper_markers_cb.setChecked(False)
                        works = []
                        for b in B_SWEEP:
                            panel.text_edge.setValue(b)
                            if not refresh():
                                works.append(b)
                        panel.helper_markers_cb.setChecked(True)
                        panel.text_edge.setValue(4.0)
                        row = {"state": tag, "mode": mode, "margin_b": mb,
                               "lines": 1 + int(stamp), "pt": pt,
                               "sentence_offered": offered,
                               "b_values_that_clear_with_markers_off": works,
                               "gate_probe_0_1_clears": (0.1 in works)}
                        res["all"].append(row)
                        if works and not offered:
                            res["markers_route_withheld_but_works"].append(row)
                            print(f"    !! WITHHELD-MARKERS {tag} -> the route "
                                  f"clears at B={works}", flush=True)
                        elif offered and not works:
                            print(f"    (offered, nothing clears) {tag}",
                                  flush=True)

                    # ---- B: the plain "lower B" lever, markers OFF ------
                    panel.helper_markers_cb.setChecked(False)
                    panel.text_edge.setValue(6.0)
                    msgs = refresh()
                    if msgs:
                        offered_b = "moves the text down" in msgs[0]
                        works_b = []
                        for b in B_SWEEP:
                            if b >= 6.0:
                                continue
                            panel.text_edge.setValue(b)
                            if not refresh():
                                works_b.append(b)
                        panel.text_edge.setValue(6.0)
                        rb = {"state": tag, "sentence_offered": offered_b,
                              "lower_b_values_that_clear": works_b,
                              "gate_probe_0_1_clears": (0.1 in works_b)}
                        if works_b and not offered_b:
                            res["b_lever_withheld_but_works"].append(rb)
                            print(f"    !! WITHHELD-B {tag} -> lowering B "
                                  f"clears at {works_b}", flush=True)

                    panel.helper_markers_cb.setChecked(True)
                    panel.text_edge.setValue(4.0)

    # ---- C: can the "no margin clears" note fire on auto? ---------------
    panel.helper_markers_cb.setChecked(True)
    panel.chart_text_size.setValue(0.0)          # auto
    for paper in ('4×6" (102 × 152 mm)', '5×7" (127 × 178 mm)',
                  'Letter (8.5 × 11") Portrait'):
        panel.paper.setCurrentText(paper)
        for mb in (6.0, 30.0, 50.0, 59.0, 60.0):
            panel.margins["b"].setValue(mb)
            for stamp in (False, True):
                panel.stamp_command.setChecked(stamp)
                msgs = refresh()
                if msgs and "cannot clear this one on its own" in msgs[0]:
                    res["note_on_auto"].append(
                        {"paper": paper, "margin_b": mb,
                         "lines": 1 + int(stamp), "message": msgs[0][:400]})
                    print(f"    !! NOTE-ON-AUTO {paper} mb={mb}", flush=True)

    res["summary"] = {
        "states measured": len(res["all"]),
        "markers sentence WITHHELD where the route works":
            len(res["markers_route_withheld_but_works"]),
        "B lever WITHHELD where lowering B works":
            len(res["b_lever_withheld_but_works"]),
        "the no-margin note firing on auto": len(res["note_on_auto"]),
    }
    print(json.dumps(res["summary"], indent=2), flush=True)
    (out / "adv17d-gates-monotonicity.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

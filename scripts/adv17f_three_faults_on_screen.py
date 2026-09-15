#!/usr/bin/env python3
"""Adversary 17f: three faults in the bottom/top sheet-text notice block,
driven in a REAL window.

P1  `_larger_paper_note` tries only papers LARGER BY AREA, and a bottom
    collision is decided by HEIGHT. On A2 landscape nothing in the pulldown is
    larger by area, so the loop tries nothing at all and the sentence is the
    unchecked assertion round 5 was made to remove.

P2  The WIDTH message offers *"lower "Clip" under "Text distance from edge
    (mm)""* with no gate. The side reserve is the LARGER of "Clip" and the
    ruler helper markers' own reach, so once the markers win, winding "Clip"
    down changes the room by nothing - the same "remedy that does not remedy"
    three sibling sentences in this very method were gated to stop making.

P3  The TOP strip-letter check reads the marker boxes RAW while the bottom
    checks read them as the engine does, so in one frame the bottom is right
    and the top is silent over letters that really are on the patches.
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


def notices(tab):
    panel = getattr(tab, "_margin_panel", None)
    last = getattr(panel, "_last_status", None) if panel is not None else None
    return list((last[1].get("overlap_warnings") or []) if last else [])


def bottom_height(msgs):
    return [m for m in msgs if "along the bottom" in m
            and ("runs into the patches" in m or "run into the patches" in m)]


def bottom_width(msgs):
    return [m for m in msgs if "too wide for the paper" in m]


def strip_letters(msgs):
    return [m for m in msgs if "strip letters are printed over the patches" in m]


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17f-"))
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
    onscreen = bool(win.isVisible())
    print(f"    window on screen: {onscreen}", flush=True)
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
    panel.chart_text.setText("test")
    pump(app, 300)

    def refresh():
        pump(app, 200); tab._update_margin_inspector(); pump(app, 320)
        return notices(tab)

    papers = [(panel.paper.itemText(k), panel.paper.itemData(k))
              for k in range(panel.paper.count())]
    res = {"window_on_screen": onscreen,
           "papers_in_the_pulldown": [p[1] for p in papers],
           "P1": {}, "P2": {}, "P3": {}}

    # ---------------------------------------------------------------- P1
    NOTE = "No bottom margin this sheet allows will clear it"
    DENY = "larger paper does not help"
    panel.stamp_command.setChecked(False)
    panel.helper_markers_cb.setChecked(False)
    pump(app, 300)
    found = None
    SIZES = (36.0, 48.0, 60.0, 72.0, 84.0, 96.0)
    for lines in (1, 2):
        panel.stamp_command.setChecked(lines == 2)
        for mode in ("patch_first", "area_first"):
            for mb in (60.0, 59.5, 55.0, 50.0, 45.0, 40.0, 30.0, 20.0):
                for pt in SIZES:
                    panel.paper.setCurrentIndex(panel.paper.findData("594x420"))
                    panel.layout_mode.setCurrentIndex(
                        panel.layout_mode.findData(mode))
                    panel.margins["b"].setValue(mb)
                    panel.chart_text_size.setValue(pt)
                    msgs = bottom_height(refresh())
                    if msgs and NOTE in msgs[0] and DENY in msgs[0]:
                        found = (mode, mb, pt, lines, msgs[0]); break
                if found: break
            if found: break
        if found: break
    if found:
        mode, mb, pt, lines, msg = found
        panel.stamp_command.setChecked(lines == 2)
        print(f"    P1 denial on A2 landscape: {mode} mb={mb} {pt}pt "
              f"{lines} line(s)", flush=True)
        capture_window(win, out / f"P1-A2-landscape-denies-{mode}-mb{mb}-{pt:.0f}pt.png")
        t0 = time.monotonic()
        for _ in range(5):
            tab._engine_text_notes()
        cost = round((time.monotonic() - t0) * 1000.0 / 5.0, 1)
        print(f"    P1 notice pass in this branch: {cost} ms", flush=True)
        cleared = []
        for _lab, code in papers:
            if code in (None, "", "594x420"):
                continue
            k = panel.paper.findData(code)
            if k < 0:
                continue
            panel.paper.setCurrentIndex(k)
            got = bottom_height(refresh())
            if not got:
                cleared.append(code)
                capture_window(win, out / f"P1-CLEARED-by-{code}.png")
        panel.paper.setCurrentIndex(panel.paper.findData("594x420"))
        refresh()
        res["P1"] = dict(state=dict(mode=mode, margin_b=mb, size_pt=pt,
                                    lines=lines),
                         message=msg, denies_a_larger_paper=True,
                         papers_that_clear_it=cleared,
                         notice_pass_ms=cost)
        print(f"    P1 papers in the SAME pulldown that clear it: {cleared}",
              flush=True)
    else:
        res["P1"] = {"note": "no denial reached on A2 landscape in this sweep"}
    panel.stamp_command.setChecked(False)

    # ---------------------------------------------------------------- P2
    # A strip reader, so BOTH marker combs are live (on a honeycomb the side
    # one is greyed and the side reserve is 0, which hides this entirely).
    if panel.instr.findData("i1") >= 0:
        panel.instr.setCurrentIndex(panel.instr.findData("i1")); pump(app, 900)
    panel.paper.setCurrentIndex(panel.paper.findData("A4"))
    panel.layout_mode.setCurrentIndex(panel.layout_mode.findData("area_first"))
    panel.margins["b"].setValue(12.0)
    panel.margins["l"].setValue(6.0); panel.margins["r"].setValue(6.0)
    panel.chart_text_size.setValue(0.0)      # auto
    panel.helper_markers_cb.setChecked(True); pump(app, 300)
    panel.helper_markers_sides.setChecked(True)
    panel.helper_markers_top_bottom.setChecked(True)
    panel.helper_marker_edge.setValue(4.0)
    panel.helper_marker_len.setValue(2.0)
    panel.text_edge_clip.setValue(4.0)
    panel.chart_text.setText("A" * 160)
    pump(app, 500)
    msgs = refresh()
    w = bottom_width(msgs)
    res["P2"] = {"instrument": panel.instr.currentData(),
                 "markers": [panel.helper_marker_edge.value(),
                             panel.helper_marker_len.value()],
                 "sides_live": panel.helper_markers_sides.isEnabled(),
                 "sides_on": panel.helper_markers_sides.isChecked(),
                 "clip_4_0": {"warned": bool(w), "message": w[0] if w else None}}
    if w:
        print("    P2 width warning at Clip 4.0 mm, markers 4+2 on the sides",
              flush=True)
        capture_window(win, out / "P2-width-warning-clip-4-0.png")
        room = re.search(r"there are (\d+) mm", w[0])
        res["P2"]["clip_4_0"]["room_mm"] = int(room.group(1)) if room else None
        res["P2"]["clip_4_0"]["offers_lower_clip"] = ("lower \u201cClip\u201d" in w[0])
        for v in (2.0, 1.0, 0.5, 0.1):
            panel.text_edge_clip.setValue(v)
            g2 = bottom_width(refresh())
            r2 = re.search(r"there are (\d+) mm", g2[0]) if g2 else None
            res["P2"][f"clip_{v}"] = {
                "warned": bool(g2),
                "room_mm": int(r2.group(1)) if r2 else None,
                "message": g2[0] if g2 else None}
            print(f"      Clip {v} mm -> warned={bool(g2)} "
                  f"room={r2.group(1) if r2 else None} mm", flush=True)
        capture_window(win, out / "P2-width-warning-clip-0-1-UNCHANGED.png")
        panel.text_edge_clip.setValue(4.0); refresh()

    # ---------------------------------------------------------------- P3
    panel.chart_text.setText("test")
    panel.chart_text_size.setValue(0.0)
    panel.paper.setCurrentIndex(panel.paper.findData("A4"))
    panel.layout_mode.setCurrentIndex(panel.layout_mode.findData("area_first"))
    panel.margins["t"].setValue(8.0)
    panel.text_edge_top.setValue(2.0)
    panel.helper_markers_cb.setChecked(True)
    panel.helper_marker_edge.setValue(0.0)      # the box accepts 0 …
    panel.helper_marker_len.setValue(0.0)       # … and the engine draws 2.0
    pump(app, 400)
    msgs = refresh()
    from workflow.layout_engine import geometry as _geom, instruments as _ins, papers as _pap
    from workflow import text_edge_fit as _tef
    from ui.tabs.tab_chart import _marker_reserve_args
    r = tab._current_layout_recipe()
    g = _ins.geom_from_build_kwargs(r.build_kwargs())
    _w, _h = _pap.dimensions_mm(str(r.paper))
    lay = _geom.compute(g, _w, _h, 100000)
    pl = _geom.placement(g, _w, _h, lay)
    band = float(getattr(g, "label_ink_bottom_mm", 0.0) or 0.0)
    res["P3"] = {
        "typed_marker_edge_mm": float(getattr(r, "helper_marker_edge_mm", 0.0) or 0.0),
        "typed_marker_len_mm": float(getattr(r, "helper_marker_len_mm", 0.0) or 0.0),
        "geom_marker_edge_mm": float(getattr(g, "helper_marker_edge_mm", 0.0) or 0.0),
        "geom_marker_len_mm": float(getattr(g, "helper_marker_len_mm", 0.0) or 0.0),
        "panel_reads_markers_as": list(_marker_reserve_args(r)),
        "strip_label_reserve_mm": round(_geom.strip_label_reserve_mm(g), 2),
        "label_band_top_mm": round(float(pl.leader_top), 2),
        "label_band_bottom_mm": round(float(pl.leader_top) + band, 2),
        "first_patch_row_top_mm": round(float(pl.y0_first), 2),
        "letters_over_the_patches_mm": round(
            float(pl.leader_top) + band - float(pl.y0_first), 2),
        "strip_letter_warning_on_screen": strip_letters(msgs),
        "bottom_warnings_on_screen": bottom_height(msgs),
        "all_notices": msgs}
    capture_window(win, out / "P3-markers-typed-zero-top-is-silent.png")
    print(f"    P3 engine draws the markers at "
          f"{res['P3']['geom_marker_edge_mm']}+{res['P3']['geom_marker_len_mm']} mm "
          f"from boxes typed {res['P3']['typed_marker_edge_mm']}/"
          f"{res['P3']['typed_marker_len_mm']}", flush=True)
    print(f"    P3 label band {res['P3']['label_band_top_mm']}..."
          f"{res['P3']['label_band_bottom_mm']} mm, first patch row at "
          f"{res['P3']['first_patch_row_top_mm']} mm -> "
          f"{res['P3']['letters_over_the_patches_mm']} mm of letter on the "
          f"patches", flush=True)
    print(f"    P3 strip-letter warning on screen: {strip_letters(msgs)}",
          flush=True)

    (out / "adv17f-three-faults.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("    written", flush=True)
    win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

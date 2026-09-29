#!/usr/bin/env python3
"""Adversary 17b: the two NEW sentences, driven in a real window.

Two questions the round that wrote them did not ask:

1. **The rise the message names.** `margin_rise_that_clears_mm` is a bisection
   over a predicate that may not be monotone. The message says "Raise Bottom by
   about X mm". This driver TYPES that X into the spin box and re-reads the
   panel: the warning must be gone.

2. **The lever sentence.** `_bottom_lever_note` offers "lower B" whenever the
   anchor equals the typed B. It never asks whether B CAN be lowered, nor by
   how much. Two states are driven:
   * "B" typed 0.0, markers off. The engine reads 0 as 4.0
     (`TEXT_EDGE_DEFAULT_MM`), the spin box's minimum IS 0, so there is nothing
     to lower, and the sentence offers it anyway.
   * "B" typed above the ruler helper markers' own reach. Lowering "B" buys
     only (B - reach) mm and then stops; the sentence promises "the same room".

Everything is read from the panel the WINDOW is showing (`_last_status`),
never by calling `_engine_text_notes` again.
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
TEXT = "test-{project}-page {page}-{date}-{paper}-{patchcount} patches"


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def said(tab) -> dict:
    panel = getattr(tab, "_margin_panel", None)
    last = getattr(panel, "_last_status", None) if panel is not None else None
    msgs = [m for m in ((last[1].get("overlap_warnings") or []) if last else [])
            if "along the bottom" in m]
    return {"height": [m for m in msgs
                       if "runs into the patches" in m
                       or "run into the patches" in m],
            "all": msgs}


RISE = re.compile(r"“Bottom”[^.]*?by about ([0-9.]+) mm")


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
    print(f"    sandbox: {work}", flush=True)

    QDialog.exec = lambda self: 1                 # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1620, 1060)
    win.show(); win.raise_()
    pump(app, 2500)
    print(f"    window on screen: {win.isVisible()}  locked={session_is_locked()}",
          flush=True)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("test")
    pump(app, 600)

    combo = tab._preset_combo
    i = combo.findData(PRESET)
    assert i >= 0, "his preset is not in the dropdown"
    combo.setCurrentIndex(i)
    combo.activated.emit(i)
    pump(app, 1500)
    for _ in range(400):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 800)
    print(f"    preview built: ti2={bool(getattr(tab,'_margin_ti2',None))} "
          f"tiffs={bool(getattr(tab,'_margin_tiffs',None))}", flush=True)

    panel = tab._manual_layout_panel
    if panel.use_instr_margins.isChecked():
        panel.use_instr_margins.setChecked(False)
        pump(app, 400)
    panel.chart_text.setText(TEXT)
    pump(app, 300)

    def refresh():
        tab._update_margin_inspector()
        pump(app, 500)
        return said(tab)

    def setup(*, mode, size_pt, mb, stamp, markers, b_mm,
              mk_edge=4.0, mk_len=2.0, top_bottom=True, sides=True):
        j = panel.layout_mode.findData(mode)
        assert j >= 0, mode
        panel.layout_mode.setCurrentIndex(j)
        panel.stamp_command.setChecked(stamp)
        panel.chart_text_size.setValue(float(size_pt))
        panel.helper_markers_cb.setChecked(markers)
        if markers:
            panel.helper_marker_edge.setValue(mk_edge)
            panel.helper_marker_len.setValue(mk_len)
            panel.helper_markers_top_bottom.setChecked(top_bottom)
            panel.helper_markers_sides.setChecked(sides)
        panel.text_edge.setValue(float(b_mm))
        panel.margins["b"].setValue(float(mb))
        pump(app, 500)

    rows = []

    # ---- 1. the rise the message names, applied ------------------------
    cases = [
        dict(tag="area-1line-18pt", mode="area_first", size_pt=18.0, mb=6.0,
             stamp=False, markers=False, b_mm=4.0),
        dict(tag="area-2line-14pt", mode="area_first", size_pt=14.0, mb=6.0,
             stamp=True, markers=False, b_mm=4.0),
        dict(tag="patch-2line-28pt", mode="patch_first", size_pt=28.0, mb=6.0,
             stamp=True, markers=False, b_mm=4.0),
        dict(tag="patch-1line-34pt", mode="patch_first", size_pt=34.0, mb=6.0,
             stamp=False, markers=False, b_mm=4.0),
        dict(tag="area-2line-auto", mode="area_first", size_pt=0.0, mb=5.0,
             stamp=True, markers=False, b_mm=4.0),
        dict(tag="area-1line-24pt-markers", mode="area_first", size_pt=24.0,
             mb=8.0, stamp=False, markers=True, b_mm=8.0),
    ]
    for c in cases:
        tag = c.pop("tag")
        setup(**c)
        s = refresh()
        if not s["height"]:
            rows.append({"case": tag, "warned": False}); 
            print(f"    {tag:26s} no warning", flush=True)
            continue
        msg = s["height"][0]
        m = RISE.search(msg)
        rise = float(m.group(1)) if m else None
        lever = ("will not help here" if "will not help here" in msg else
                 "moves the text down" if "moves the text down" in msg else None)
        after = None
        if rise is not None:
            panel.margins["b"].setValue(float(c["mb"]) + rise)
            pump(app, 500)
            after = refresh()
            panel.margins["b"].setValue(float(c["mb"]))
            pump(app, 300)
        rows.append({"case": tag, "warned": True, "rise_named_mm": rise,
                     "lever_sentence": lever,
                     "still_warns_after_the_rise":
                         bool(after and after["height"]),
                     "message": msg})
        print(f"    {tag:26s} rise={rise} lever={lever} "
              f"still_warns={bool(after and after['height'])}", flush=True)

    # ---- 2. "B" typed 0, markers off: a lever with nothing to pull ------
    setup(mode="area_first", size_pt=18.0, mb=6.0, stamp=False,
          markers=False, b_mm=0.0)
    s = refresh()
    r = panel.get_recipe()
    b0 = {"case": "B-typed-zero",
          "box_value": panel.text_edge.value(),
          "box_minimum": panel.text_edge.minimum(),
          "recipe_text_edge_mm": r.text_edge_mm,
          "effective_text_edge_mm": r.effective_text_edge_mm,
          "warned": bool(s["height"]),
          "says_lower_B": bool(s["height"] and
                               "moves the text down" in s["height"][0]),
          "says_will_not_help": bool(s["height"] and
                                     "will not help here" in s["height"][0]),
          "message": s["height"][0] if s["height"] else ""}
    rows.append(b0)
    print("    B=0:", json.dumps({k: v for k, v in b0.items()
                                  if k != "message"}), flush=True)

    # ---- 3. "B" above the markers' reach: how much does the lever buy? --
    setup(mode="area_first", size_pt=24.0, mb=8.0, stamp=False,
          markers=True, b_mm=9.0, mk_edge=4.0, mk_len=2.0)
    s = refresh()
    before = s["height"][0] if s["height"] else ""
    lever = ("will not help here" if "will not help here" in before else
             "moves the text down" if "moves the text down" in before else None)
    # pull the lever all the way down and see whether the warning goes
    panel.text_edge.setValue(0.0)
    pump(app, 400)
    s2 = refresh()
    r2 = panel.get_recipe()
    lev = {"case": "B-above-the-marker-reach",
           "B_typed": 9.0, "marker_reach_mm": 4.0 + 2.0 + 1.0,
           "lever_sentence": lever,
           "warned_before": bool(before),
           "B_after_pulling_all_the_way": panel.text_edge.value(),
           "effective_after": r2.effective_text_edge_mm,
           "still_warns_after_the_lever": bool(s2["height"]),
           "message_before": before}
    rows.append(lev)
    print("    B-over-markers:", json.dumps({k: v for k, v in lev.items()
                                             if not k.startswith("message")}),
          flush=True)

    ok, why = capture_window(win, out / "01-lever-and-rise.png")
    print(f"    photo: {'ok' if ok else 'REFUSED ' + str(why)}", flush=True)
    (out / "lever-and-rise.json").write_text(
        json.dumps({"rows": rows,
                    "photo": "01-lever-and-rise.png" if ok else f"REFUSED {why}",
                    "locked": session_is_locked()},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    win.close(); pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

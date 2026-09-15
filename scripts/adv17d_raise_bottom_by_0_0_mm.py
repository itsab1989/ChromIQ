#!/usr/bin/env python3
"""Adversary 17d, probe 3: two states the new ceiling created, photographed.

**A. "Raise 'Bottom' … by about 0.0 mm."** The fallback the caller uses when
`margin_rise_that_clears_mm` returns None is

    min(overlap, max(0.0, 60 - the margin now))

so at a bottom margin of 60 -- the top of the box, one arrow click above the
59.5 the app's own advice sends you to -- that is 0.0, and the message asks
the reader to raise a box by nothing. This walks the route a reader walks:
take the advice at 55, land on 60, read what the app says then.

**B. The margin boxes are LOCKED by default.** `LayoutRecipe` ships
`use_instrument_margins = True` and `layout_options_panel` does
`self.margins[k].setEnabled(not on)`, so with "Use instrument margins" ticked
the four boxes are read-only -- and the message still says "Raise 'Bottom'
under 'Margins (mm)' by about X mm", with nothing about the tick that has to
come off first. Every round so far unticked it before measuring.
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17d3-"))
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
    res = {"window_on_screen": bool(win.isVisible()),
           "use_instrument_margins_as_the_preset_loads_it":
               bool(panel.use_instr_margins.isChecked()),
           "margin_b_enabled_as_loaded": bool(panel.margins["b"].isEnabled())}
    print(f"    as loaded: use_instrument_margins="
          f"{res['use_instrument_margins_as_the_preset_loads_it']} "
          f"bottom box enabled={res['margin_b_enabled_as_loaded']}", flush=True)

    def refresh():
        pump(app, 260); tab._update_margin_inspector(); pump(app, 380)
        return said(tab)

    # ---- A: walk the route the message sends you on ----------------------
    if panel.use_instr_margins.isChecked():
        panel.use_instr_margins.setChecked(False); pump(app, 500)
    panel.chart_text.setText("test-{project}-page {page}-{paper}")
    j = panel.layout_mode.findData("area_first")
    panel.layout_mode.setCurrentIndex(j)
    panel.stamp_command.setChecked(True)
    panel.chart_text_size.setValue(72.0)
    walk = []
    for mb in (55.0, 59.5, 60.0):
        panel.margins["b"].setValue(mb)
        msgs = refresh()
        walk.append({"margin_b": panel.margins["b"].value(),
                     "message": msgs[0] if msgs else None})
        print(f"    A margin_b={panel.margins['b'].value():.1f} -> "
              f"{(msgs[0][:150] if msgs else 'silent')}", flush=True)
    panel.margins["b"].setValue(60.0); refresh()
    ok, why = capture_window(win, out / "A-raise-bottom-by-0-0-mm.png")
    res["A_the_route"] = walk
    res["A_photo"] = str(ok) if ok else str(why)

    # ---- A2: "print the chart on a larger paper" ------------------------
    # The note's second lever. At a bottom margin the box has room above,
    # sweep every paper ChromIQ offers and see whether ANY of them clears.
    panel.margins["b"].setValue(20.0)
    panel.chart_text_size.setValue(72.0)
    papers = [panel.paper.itemText(k) for k in range(panel.paper.count())]
    here = panel.paper.currentText()
    bigger = {}
    for label in papers:
        if label == here or label.startswith("Custom"):
            continue
        panel.paper.setCurrentText(label)
        got = refresh()
        bigger[label] = {"still_warns": bool(got),
                         "message": (got[0][:120] if got else None)}
        print(f"    A2 paper={label!r} still_warns={bool(got)}", flush=True)
    res["A2_a_larger_paper"] = {"from": here, "papers": bigger}
    # the largest sheet ChromIQ offers, photographed still warning
    biggest = "A2 (420 × 594 mm) Portrait"
    if biggest in bigger and bigger[biggest]["still_warns"]:
        panel.paper.setCurrentText(biggest); refresh()
        okp, whyp = capture_window(win, out / "A2-largest-paper-still-warns.png")
        res["A2_photo"] = str(okp) if okp else str(whyp)
    panel.paper.setCurrentText(here); refresh()

    # ---- B: the locked box, photographed with the box in the picture -----
    panel.chart_text_size.setValue(40.0)
    panel.stamp_command.setChecked(False)
    panel.margins["b"].setValue(6.0)
    panel.use_instr_margins.setChecked(True); pump(app, 700)
    msgs = refresh()
    res["B_locked"] = {
        "bottom_box_enabled": bool(panel.margins["b"].isEnabled()),
        "bottom_box_value": panel.margins["b"].value(),
        "message": msgs[0] if msgs else None,
        "the_message_names_the_margins_box": bool(
            msgs and "Margins (mm)" in msgs[0]),
        "the_message_says_anything_about_the_tick": bool(
            msgs and "instrument margins" in msgs[0]),
    }
    print(f"    B locked: box_enabled={panel.margins['b'].isEnabled()} "
          f"names_box={res['B_locked']['the_message_names_the_margins_box']} "
          f"mentions_the_tick="
          f"{res['B_locked']['the_message_says_anything_about_the_tick']}",
          flush=True)
    # scroll the panel so the LOCKED box and the warning are in one picture
    try:
        area = panel.parent()
        while area is not None and not hasattr(area, "verticalScrollBar"):
            area = area.parent()
        if area is not None:
            panel.margins["b"].parent()
            area.ensureWidgetVisible(panel.margins["b"], 50, 200)
            pump(app, 600)
    except Exception as exc:              # noqa: BLE001
        print(f"    (could not scroll to the box: {exc})", flush=True)
    ok2, why2 = capture_window(win, out / "B-the-locked-bottom-box.png")
    res["B_photo"] = str(ok2) if ok2 else str(why2)
    panel.use_instr_margins.setChecked(False); pump(app, 400)

    (out / "adv17d-raise-by-zero-and-the-locked-box.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("    written", flush=True)
    win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

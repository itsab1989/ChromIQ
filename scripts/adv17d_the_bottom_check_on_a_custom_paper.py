#!/usr/bin/env python3
"""Adversary 17d, probe 6: the bottom-text check on a CUSTOM paper.

`predicted_patch_bottom_mm` calls `papers.dimensions_mm(r.paper)`, which
RAISES on any code it does not recognise, and the whole function is wrapped in
`except Exception: return None`. Every consumer reads that None as "no
warning" (`_o` is None) and `_bottom_clears_with` reads it as "the offer is
withheld". So if a Custom paper ever reaches the recipe as anything but a
``WxH`` code, a whole check goes silent with nothing said.

Headless, first: `dimensions_mm("210x297")` is fine, `dimensions_mm("A4")` is
fine, and `dimensions_mm("__custom__")` raises ValueError. So the question is
what the PANEL actually puts in the recipe.

This drives it: pick "Custom…", type a sheet the same size as Letter, put a
sheet text on it that really does run into the patches, and compare what the
panel says against the same state on the named paper.
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17d6-"))
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
    j = panel.layout_mode.findData("area_first")
    panel.layout_mode.setCurrentIndex(j)
    panel.margins["b"].setValue(6.0)
    panel.chart_text_size.setValue(40.0)
    pump(app, 500)

    def refresh():
        pump(app, 260); tab._update_margin_inspector(); pump(app, 380)
        return said(tab)

    res = {"window_on_screen": bool(win.isVisible())}

    # --- the NAMED paper, as a control ---------------------------------
    named = "Letter (8.5 × 11\") Portrait"
    panel.paper.setCurrentText(named)
    msgs = refresh()
    r = tab._current_layout_recipe()
    res["named_paper"] = {
        "combo": panel.paper.currentText(),
        "recipe_paper": getattr(r, "paper", None),
        "warns": bool(msgs), "message": (msgs[0][:260] if msgs else None)}
    print(f"    named: paper={res['named_paper']['recipe_paper']!r} "
          f"warns={bool(msgs)}", flush=True)

    # --- the SAME SHEET as a Custom paper -------------------------------
    ci = panel.paper.findData("__custom__")
    assert ci >= 0, "no Custom… entry"
    panel.paper.setCurrentIndex(ci)
    pump(app, 400)
    try:
        panel.custom_w.setValue(215.9)
        panel.custom_h.setValue(279.4)
    except Exception as exc:                        # noqa: BLE001
        print(f"    (custom w/h boxes: {exc})", flush=True)
    pump(app, 600)
    msgs2 = refresh()
    r2 = tab._current_layout_recipe()
    from workflow.layout_engine import papers, instruments
    from ui.tabs.tab_chart import predicted_patch_bottom_mm
    dims, dims_err = None, None
    try:
        dims = papers.dimensions_mm(getattr(r2, "paper", ""))
    except Exception as exc:                        # noqa: BLE001
        dims_err = f"{type(exc).__name__}: {exc}"
    bottom = None
    try:
        geom = instruments.geom_from_build_kwargs(r2.build_kwargs())
        bottom = predicted_patch_bottom_mm(r2, geom)
    except Exception as exc:                        # noqa: BLE001
        bottom = f"RAISED {type(exc).__name__}: {exc}"
    res["custom_paper"] = {
        "combo": panel.paper.currentText(),
        "custom_w": getattr(panel, "custom_w", None) and panel.custom_w.value(),
        "custom_h": getattr(panel, "custom_h", None) and panel.custom_h.value(),
        "recipe_paper": getattr(r2, "paper", None),
        "dimensions_mm": dims, "dimensions_mm_error": dims_err,
        "predicted_patch_bottom_mm": bottom,
        "warns": bool(msgs2), "message": (msgs2[0][:260] if msgs2 else None)}
    print(f"    custom: paper={res['custom_paper']['recipe_paper']!r} "
          f"dims={dims} err={dims_err} bottom={bottom} "
          f"warns={bool(msgs2)}", flush=True)
    res["the_check_went_silent_on_a_custom_paper"] = bool(
        res["named_paper"]["warns"] and not res["custom_paper"]["warns"])
    ok, why = capture_window(win, out / "P6-custom-paper.png")
    res["photo"] = str(ok) if ok else str(why)

    (out / "adv17d-the-bottom-check-on-a-custom-paper.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    print(f"\n    went silent on Custom: "
          f"{res['the_check_went_silent_on_a_custom_paper']}", flush=True)
    win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

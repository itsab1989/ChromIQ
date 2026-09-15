#!/usr/bin/env python3
"""Adversary 22a — the FROM PROFILE GAMUT module now speaks; is it telling the
truth there?

Round 11 changed `_engine_text_notes` from `self._manual_btn.isChecked()` to
`self._current_mode() == "manual"`, so every "Measured from Preview" notice now
fires in the FROM PROFILE GAMUT module too. A warning that appears where it
never appeared before is only an improvement if it is TRUE there.

This drives the real window and asks, in the module itself:

  1. Does `_current_layout_recipe()` describe the sheet the module BUILDS?
     (paper, margins, sheet text, font, size, markers, layout mode, clip.)
  2. Is every control the messages name on screen and ENABLED?
  3. Does typing the remedy the message names really clear the notice?
  4. What else answers differently in this module than in MANUAL: the
     instrument the inspector judges against, the paper, the name field the
     Generate button reads, the patch total the stamp prediction uses.
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
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import (QApplication, QDialog,       # noqa: E402
                             QMessageBox, QAbstractScrollArea)
from onscreen_capture import capture_window                # noqa: E402


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv22a-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)), ("language", "en"),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True),
                 ("auto_update_preview", True)):
        settings.set(k, v)
    QDialog.exec = lambda self: 1                    # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1620, 1080)
    win.show()
    win.raise_()
    pump(app, 2200)
    print("    window on screen:", win.isVisible(), flush=True)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 700)
    tab._user_switch_mode("manual")
    pump(app, 1400)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("adv22a")
    pump(app, 400)
    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 800)

    def set_the_colliding_layout():
        if p.use_instr_margins.isChecked():
            p.use_instr_margins.setChecked(False)
            pump(app, 300)
        for k, v in (("t", 12.0), ("b", 6.0), ("l", 12.0), ("r", 12.0)):
            p.margins[k].setValue(v)
        p.helper_markers_cb.setChecked(True)
        p.helper_markers_top_bottom.setChecked(True)
        p.text_edge.setValue(4.0)
        p.chart_text.setText("ChromIQ 22")
        p.stamp_command.setChecked(False)
        p.chart_text_size.setValue(36.0)
        pump(app, 1600)

    def panel_text() -> str:
        mp = getattr(tab, "_margin_panel", None)
        return mp._status.text() if mp is not None else ""

    def recipe_snapshot():
        r = tab._current_layout_recipe()
        return {"paper": r.paper, "instrument": r.instrument,
                "layout_mode": r.mode(), "margin_t": r.margin_top,
                "margin_b": r.margin_bottom, "margin_l": r.margin_left,
                "margin_r": r.margin_right,
                "chart_text": r.chart_text,
                "chart_text_size_mm": r.chart_text_size_mm,
                "chart_text_font": getattr(r, "chart_text_font", ""),
                "helper_markers": bool(getattr(r, "helper_markers", False)),
                "helper_markers_top_bottom":
                    bool(getattr(r, "helper_markers_top_bottom", True)),
                "helper_markers_sides":
                    bool(getattr(r, "helper_markers_sides", True)),
                "text_edge_clip_mm": getattr(r, "text_edge_clip_mm", None),
                "clip_border": bool(getattr(r, "clip_border", False)),
                "clip_border_width_mm":
                    float(getattr(r, "clip_border_width_mm", 0.0) or 0.0),
                "pages": getattr(r, "pages", None)}

    def controls_snapshot():
        def vs(w):
            if w is None:
                return None
            return {"visible": bool(w.isVisible()),
                    "enabled": bool(w.isEnabled())}
        return {
            "Margins Bottom": vs(p.margins["b"]),
            "Margins Top": vs(p.margins["t"]),
            "Margins Left": vs(p.margins["l"]),
            "Margins Right": vs(p.margins["r"]),
            "Use instrument margins": vs(p.use_instr_margins),
            "Sheet text": vs(p.chart_text),
            "Sheet text Size": vs(p.chart_text_size),
            "Stamp layout summary": vs(p.stamp_command),
            "Text distance from edge (Clip)": vs(p.text_edge),
            "Print helper markers": vs(p.helper_markers_cb),
            "Markers top/bottom": vs(p.helper_markers_top_bottom),
            "Markers sides": vs(p.helper_markers_sides),
            "Paper": vs(p.paper),
            "Instrument": vs(p.instr),
            "Pages": vs(p.pages),
        }

    def probes():
        try:
            n, pages = tab._predicted_totals()
        except Exception as e:                        # noqa: BLE001
            n, pages = -1, -1
        fld = tab._active_name_field()
        return {"_current_mode": tab._current_mode(),
                "_mode_name": tab._mode_name(),
                "manual_btn.isChecked": bool(tab._manual_btn.isChecked()),
                "_active_instrument_flag": tab._active_instrument_flag(),
                "_active_paper_code": tab._active_paper_code(),
                "_estimate_patch_total": tab._estimate_patch_total(),
                "_predicted_totals": [n, pages],
                "current_margin_combo": tab.current_margin_combo(),
                "current_layout_combo": tab.current_layout_combo(),
                "_active_name_field is manual":
                    fld is getattr(tab, "_manual_target_name_edit", None),
                "_active_name_field text":
                    (fld.text() if fld is not None else None)}

    def refresh_panel():
        tab._margin_panel._measured_check.setChecked(
            not tab._margin_panel._measured_check.isChecked())
        pump(app, 2200)

    def scroll_margins():
        try:
            sa, w = None, p.margins["b"]
            while w is not None:
                if isinstance(w, QAbstractScrollArea):
                    sa = w
                    break
                w = w.parentWidget()
            if sa is not None:
                sa.ensureWidgetVisible(p.margins["b"], 50, 240)
                pump(app, 600)
        except Exception as e:                        # noqa: BLE001
            print("    scroll failed:", e, flush=True)

    rec: dict = {}

    # ---------------- MANUAL ------------------------------------------------
    set_the_colliding_layout()
    tab._generate_btn.click()
    for _ in range(900):
        pump(app, 200)
        if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 2500)
    print("    chart built:", bool(getattr(tab, "_margin_tiffs", None)), flush=True)
    a, b = TabChart._engine_text_notes(tab)
    rec["manual"] = {"notices": a, "overlaps": b, "recipe": recipe_snapshot(),
                     "controls": controls_snapshot(), "probes": probes(),
                     "panel": panel_text()}
    print("    MANUAL notices:", len(a), "overlaps:", len(b), flush=True)
    scroll_margins()
    ok1, why1 = capture_window(win, out / "A1-manual.png")

    # ---------------- FROM PROFILE GAMUT ------------------------------------
    bar = win._target_bar
    from core.measurement_target import RUN_TYPE_VERIFICATION
    bar._type_combo.setCurrentIndex(
        bar._type_combo.findData(RUN_TYPE_VERIFICATION))
    pump(app, 1800)
    print("    gamut button visible:", tab._gamut_btn.isVisible(), flush=True)
    tab._gamut_btn.click()
    pump(app, 2400)
    print("    mode now:", tab._mode_name(), flush=True)
    set_the_colliding_layout()
    refresh_panel()
    a2, b2 = TabChart._engine_text_notes(tab)
    rec["gamut"] = {"notices": a2, "overlaps": b2, "recipe": recipe_snapshot(),
                    "controls": controls_snapshot(), "probes": probes(),
                    "panel": panel_text()}
    print("    GAMUT notices:", len(a2), "overlaps:", len(b2), flush=True)
    for s in a2 + b2:
        print("      *", s.replace("\n", " ")[:200], flush=True)
    scroll_margins()
    ok2, why2 = capture_window(win, out / "A2-gamut.png")

    (out / "adv22a.json").write_text(
        json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    print("    photographs:", ok1, ok2, why1, why2, flush=True)
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

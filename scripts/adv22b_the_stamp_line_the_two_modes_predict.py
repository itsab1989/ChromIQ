#!/usr/bin/env python3
"""Adversary 22b — 33 characters in MANUAL, 55 in FROM PROFILE GAMUT, one sheet.

22a drove the identical layout in both modes: `_current_layout_recipe()` came
back byte-identical, and the "chart notes down the right edge are too long"
notice still said the last **33** characters are cut in MANUAL and the last
**55** in FROM PROFILE GAMUT. One of the two numbers is wrong, and the user can
see it.

This prints the pieces that number is made of, in each mode, and then applies
the remedy the bottom-text notice names inside the module to see whether it
clears.
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv22b-"))
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
        tab._manual_target_name_edit.setText("adv22b")
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

    def internals():
        pm = tab._collect_manual()
        pm.chart_notes = (tab._manual_chart_notes_edit.text() or "").strip()
        pm.stamp_commands = bool(tab._manual_stamp_cmd_check.isChecked())
        pm.chart_layout_name = tab._active_layout_name()
        np_ = tab._estimate_patch_total() or int(getattr(pm, "patches", 0) or 0)
        lines = tab._creator.stamp_lines(pm, int(np_))
        from workflow import tiff_metadata as _tmeta
        joined = _tmeta._JOIN.join(lines)
        return {"chart_layout_name": pm.chart_layout_name,
                "patches_param": getattr(pm, "patches", None),
                "np": np_,
                "stamp_commands": pm.stamp_commands,
                "chart_notes": pm.chart_notes,
                "stamp_lines": list(lines),
                "joined": joined,
                "joined_len": len(joined)}

    def notices():
        a, b = TabChart._engine_text_notes(tab)
        return a

    def bottom_line(ns):
        for s in ns:
            if "sheet text along the bottom" in s:
                return s
        return ""

    def notes_line(ns):
        for s in ns:
            if "chart notes down the right edge" in s:
                return s
        return ""

    rec = {}
    set_the_colliding_layout()
    tab._generate_btn.click()
    for _ in range(900):
        pump(app, 200)
        if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 2500)
    ns = notices()
    rec["manual"] = {"internals": internals(), "notes_line": notes_line(ns),
                     "bottom_line": bottom_line(ns)}
    print("    MANUAL joined:", rec["manual"]["internals"]["joined"], flush=True)
    print("    MANUAL notes :", rec["manual"]["notes_line"][:130], flush=True)

    bar = win._target_bar
    from core.measurement_target import RUN_TYPE_VERIFICATION
    bar._type_combo.setCurrentIndex(
        bar._type_combo.findData(RUN_TYPE_VERIFICATION))
    pump(app, 1800)
    tab._gamut_btn.click()
    pump(app, 2400)
    set_the_colliding_layout()
    tab._margin_panel._measured_check.setChecked(
        not tab._margin_panel._measured_check.isChecked())
    pump(app, 2200)
    ns2 = notices()
    rec["gamut"] = {"internals": internals(), "notes_line": notes_line(ns2),
                    "bottom_line": bottom_line(ns2)}
    print("    GAMUT  joined:", rec["gamut"]["internals"]["joined"], flush=True)
    print("    GAMUT  notes :", rec["gamut"]["notes_line"][:130], flush=True)
    print("    GAMUT  bottom:", rec["gamut"]["bottom_line"][:200], flush=True)

    # --- the remedy the bottom notice names, typed into the module ----------
    import re
    m = re.search(r"by about ([0-9.]+) mm", rec["gamut"]["bottom_line"] or "")
    if m:
        rise = float(m.group(1))
        was = float(p.margins["b"].value())
        p.margins["b"].setValue(was + rise)
        pump(app, 1800)
        tab._margin_panel._measured_check.setChecked(
            not tab._margin_panel._measured_check.isChecked())
        pump(app, 2200)
        ns3 = notices()
        rec["remedy"] = {"asked_rise_mm": rise, "bottom_from": was,
                         "bottom_to": float(p.margins["b"].value()),
                         "bottom_enabled": bool(p.margins["b"].isEnabled()),
                         "bottom_line_after": bottom_line(ns3),
                         "cleared": bottom_line(ns3) == ""}
        print("    REMEDY  rise", rise, "->",
              "CLEARED" if rec["remedy"]["cleared"] else
              rec["remedy"]["bottom_line_after"][:200], flush=True)

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
    except Exception:
        pass
    ok, why = capture_window(win, out / "B1-gamut-after-the-remedy.png")
    print("    photograph:", ok, why, flush=True)
    (out / "adv22b.json").write_text(
        json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

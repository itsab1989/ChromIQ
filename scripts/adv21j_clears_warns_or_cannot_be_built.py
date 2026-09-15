#!/usr/bin/env python3
"""Adversary 21j — three answers, not two, at every margin on the box.

21h read "no bottom warning" as "the margin clears it" and reported 35 clearing
margins where the arithmetic says two. That is the naive predicate this round
was briefed to look for, written by this round: a margin the sheet CANNOT be
laid out at produces no notices at all, because `_engine_text_notes` builds one
geometry at the top of its body and the whole method is inside one
`except Exception: pass`.

So every margin the box holds is asked for one of three answers, on the panel
and in the arithmetic side by side:

    CLEAR        the block does not reach the patches
    WARNS        it does, and the panel says so
    NO-LAYOUT    `geometry.compute` refuses the sheet, and the panel says
                 NOTHING AT ALL
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402
from onscreen_capture import capture_window                      # noqa: E402


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv21j-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)), ("language", "en"),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True),
                 ("auto_update_preview", False)):
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
        tab._manual_target_name_edit.setText("adv21j")
    pump(app, 400)
    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 900)
    p.paper.setCurrentIndex(p.paper.findData("__custom__"))
    pump(app, 500)
    p.custom_w.setValue(62)
    p.custom_h.setValue(88)
    pump(app, 900)
    p.layout_mode.setCurrentIndex(p.layout_mode.findData("area_first"))
    pump(app, 700)
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.setChecked(False)
        pump(app, 400)
    p.margins["b"].setValue(6.0)
    p.helper_markers_cb.setChecked(True)
    p.helper_markers_top_bottom.setChecked(True)
    p.chart_text.setText("ChromIQ 21")
    p.stamp_command.setChecked(True)
    p.chart_text_size.setValue(16.0 * 72.0 / 25.4)
    pump(app, 1800)

    from ui.tabs import tab_chart as tc
    from workflow import text_edge_fit as tef
    from workflow.layout_engine import instruments as im
    from workflow.layout_engine.raster import sheet_text_line_mm

    r0 = tab._current_layout_recipe()
    line = sheet_text_line_mm(r0.chart_text_size_mm, r0.chart_text_font or "",
                              False, False, 300.0)
    edge = tef.sheet_text_bottom_mm(r0.effective_text_edge_mm, True,
                                    *tc._marker_reserve_args(r0), True)
    print("    line box", round(line, 3), "mm   anchor", round(edge, 3), "mm",
          flush=True)

    def arithmetic(mb):
        c = replace(r0, margin_bottom=mb)
        try:
            g = im.geom_from_build_kwargs(c.build_kwargs())
        except Exception:                                 # noqa: BLE001
            return "NO-LAYOUT(geom)"
        b = tc.predicted_patch_bottom_mm(c, g)
        if b is None:
            return "NO-LAYOUT(compute)"
        o = tef.bottom_text_block_overlap(float(b), edge, 2, line)
        return "CLEAR" if o is None else f"WARNS({o.overlap_mm:.1f})"

    rows = []
    for k in range(0, 121):
        mb = round(0.5 * k, 1)
        p.margins["b"].setValue(mb)
        pump(app, 50)
        notes = TabChart._engine_text_notes(tab)
        said = [w for w in notes[1]
                if "into the patches" in w and "sheet text along the bottom" in w]
        rows.append({"mb": mb, "arithmetic": arithmetic(mb),
                     "panel notices": len(notes[0]),
                     "bottom warning": bool(said)})
    clear = [x["mb"] for x in rows if x["arithmetic"] == "CLEAR"]
    nolay = [x["mb"] for x in rows if x["arithmetic"].startswith("NO-LAYOUT")]
    silent = [x["mb"] for x in rows if x["panel notices"] == 0]
    print("    CLEAR at:", clear, flush=True)
    print("    NO-LAYOUT at:", nolay, flush=True)
    print("    the panel says NOTHING AT ALL at:", silent, flush=True)
    bad = [x for x in rows
           if x["arithmetic"].startswith("WARNS") and not x["bottom warning"]]
    print("    margins that overlap and the panel is silent about:",
          [x["mb"] for x in bad], flush=True)
    p.margins["b"].setValue(6.0)
    pump(app, 900)
    said0 = [w for w in TabChart._engine_text_notes(tab)[1]
             if "into the patches" in w]
    print("    at 6.0 mm the panel says:\n      ",
          (said0[0] if said0 else "<nothing>"), flush=True)
    print("    and the shipping search answers:",
          tc.margin_rise_that_clears_mm(r0, None, edge, 2, line, hint_mm=1.0),
          flush=True)
    capture_window(win, out / "J-the-panel-at-6mm.png")
    (out / "adv21j.json").write_text(json.dumps(
        {"rows": rows, "clear": clear, "no_layout": nolay, "silent": silent},
        indent=2), encoding="utf-8")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

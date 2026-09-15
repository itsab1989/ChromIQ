#!/usr/bin/env python3
"""Adversary 23h — the overlay's marker-reserve convention, photographed.

The change set makes every notice AND the live overlay read a helper-marker box
typed 0 as the 2.0 mm the engine substitutes. This drives the real window with
both boxes at 0, builds a real sheet, and compares:

* how many dashes the OVERLAY says it will draw, against
* how many marker runs the RENDERED sheet's own edges carry.

Photographed with the preview on screen.
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
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
from onscreen_capture import capture_window                      # noqa: E402


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def edge_runs(path: Path, mm: float = 6.0) -> dict:
    """How many separate ink runs the top and bottom edge bands carry."""
    import numpy as np
    from PIL import Image
    im = Image.open(str(path))
    dpi = float((im.info.get("dpi") or (300, 300))[0] or 300)
    a = np.asarray(im.convert("L"))
    px = max(1, int(mm / 25.4 * dpi))
    out = {}
    for name, band in (("top", a[:px, :]), ("bottom", a[-px:, :])):
        col = (band < 200).any(axis=0)
        runs, prev = 0, False
        for v in col:
            if v and not prev:
                runs += 1
            prev = bool(v)
        out[name] = runs
    return out


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN ONLY"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv23h-"))
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
    win.resize(1680, 1100)
    win.show()
    win.raise_()
    pump(app, 2400)
    print("    window on screen:", win.isVisible(), flush=True)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 700)
    tab._user_switch_mode("manual")
    pump(app, 1400)
    tab._manual_target_name_edit.setText("adv23h")
    pump(app, 400)
    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 900)
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.setChecked(False)
        pump(app, 400)
    p.paper.setCurrentIndex(p.paper.findData("A4"))
    for k, v in (("t", 14.0), ("l", 12.0), ("r", 12.0), ("b", 16.0)):
        p.margins[k].setValue(v)
    p.chart_text.setText("")
    p.stamp_command.setChecked(False)
    p.helper_markers_cb.setChecked(True)
    p.helper_markers_top_bottom.setChecked(True)
    p.helper_markers_sides.setChecked(False)
    pump(app, 1200)

    recs = []
    for tag, edge, length in (("A-both-boxes-0", 0.0, 0.0),
                              ("B-both-boxes-2", 2.0, 2.0),
                              ("C-edge-4-len-3", 4.0, 3.0)):
        p.helper_marker_edge.setValue(edge)
        p.helper_marker_len.setValue(length)
        pump(app, 1200)
        tab._generate_btn.click()
        for _ in range(900):
            pump(app, 200)
            if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
                break
        pump(app, 2600)
        tiff = Path(tab._margin_tiffs[0])
        got = tab._helper_marker_lines_frac()
        lines, pending = got if got is not None else (None, False)
        rec = {"tag": tag, "edge_box": edge, "len_box": length,
               "overlay_lines": (len(lines) if lines else 0),
               "overlay_pending": bool(pending),
               "sheet_edge_runs": edge_runs(tiff),
               "tiff": str(tiff)}
        recs.append(rec)
        print(f"  {tag}: overlay draws {rec['overlay_lines']} lines "
              f"(pending={rec['overlay_pending']}), the sheet's own edges carry "
              f"{rec['sheet_edge_runs']}", flush=True)
        ok, why = capture_window(win, out / f"H-{tag}.png")
        rec["photo"] = f"{ok} {why}"

    same = (recs[0]["overlay_lines"] == recs[1]["overlay_lines"]
            and recs[0]["sheet_edge_runs"] == recs[1]["sheet_edge_runs"])
    print(f"    a box typed 0 and a box typed 2 give the SAME sheet and the "
          f"SAME overlay: {same}", flush=True)
    (out / "adv23h.json").write_text(
        json.dumps(recs, indent=2, ensure_ascii=False), encoding="utf-8")
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

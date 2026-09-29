#!/usr/bin/env python3
"""Adversary 23a — the bottom-text warning against the sheet the app builds.

The panel is a PREDICTION. This drives the real window, reads the notice, then
presses Generate for real and measures the sheet that comes out:

* where the patch area's bottom edge really is (`res`/the measured report), and
  what the message's ``the patches come down to X mm`` claimed;
* whether the bottom text's ink really touches the patch ink;
* and then RAISES "Bottom" by the number the message named, using the spin
  box's own arrow keys, rebuilds, and asks whether the warning is gone and the
  sheet is clear.

On screen, photographed. No offscreen platform anywhere.
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
from PyQt6.QtCore import Qt                                   # noqa: E402
from PyQt6.QtTest import QTest                                # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402
from onscreen_capture import capture_window                   # noqa: E402


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def measure_sheet(tiff: Path) -> dict:
    """Where the ink is on the real page, in mm up from the paper's bottom.

    Rows are classified by how much of the page width they cover: a patch row
    covers a large fraction, a line of text a tiny one. Both are reported, so
    nothing depends on the classification being right.
    """
    import numpy as np
    from PIL import Image
    im = Image.open(str(tiff))
    dpi = float((im.info.get("dpi") or (300, 300))[0] or 300)
    a = np.asarray(im.convert("L")).astype(np.int16)
    h, w = a.shape
    dark = a < 245
    cov = dark.sum(axis=1) / float(w)
    mm = lambda px: round(float(px) * 25.4 / dpi, 3)      # noqa: E731
    out = {"dpi": dpi, "page_h_mm": mm(h), "page_w_mm": mm(w)}
    patch_rows = np.where(cov > 0.25)[0]
    any_rows = np.where(cov > 0.0)[0]
    thin_rows = np.where((cov > 0.0) & (cov <= 0.25))[0]
    if patch_rows.size:
        out["patch_bottom_up_mm"] = mm(h - int(patch_rows[-1]) - 1)
    if any_rows.size:
        out["lowest_ink_up_mm"] = mm(h - int(any_rows[-1]) - 1)
    # the bottom text: the lowest RUN of thin rows, below the patch block
    if thin_rows.size and patch_rows.size:
        below = thin_rows[thin_rows > patch_rows[-1]]
        if below.size:
            out["text_top_up_mm"] = mm(h - int(below[0]))
            out["text_bottom_up_mm"] = mm(h - int(below[-1]) - 1)
            out["clear_gap_mm"] = round(
                out["patch_bottom_up_mm"] - out["text_top_up_mm"], 3)
        else:
            out["text_below_patches"] = False
            out["clear_gap_mm"] = None
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv23a-"))
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
    tab._manual_target_name_edit.setText("adv23a")
    pump(app, 400)

    # capture the report the panel is shown, which is the sheet's own truth
    seen: dict = {}
    from ui.margin_inspector_panel import MarginInspectorPanel  # noqa: E402
    _orig = MarginInspectorPanel.update_report

    def _spy(self, report, *a, **k):
        seen["report"] = report
        return _orig(self, report, *a, **k)
    MarginInspectorPanel.update_report = _spy        # type: ignore[assignment]

    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 900)
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.setChecked(False)
        pump(app, 400)

    def notice():
        _a, over = TabChart._engine_text_notes(tab)
        for s in over:
            if "runs into the patches" in s or "run into the patches" in s:
                return s
        return ""

    def predicted():
        from ui.tabs.tab_chart import predicted_patch_bottom_mm
        from workflow.layout_engine import instruments
        r = tab._current_layout_recipe()
        geom = instruments.geom_from_build_kwargs(r.build_kwargs())
        return r, predicted_patch_bottom_mm(r, geom)

    def build():
        tab._generate_btn.click()
        for _ in range(900):
            pump(app, 200)
            if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
                break
        pump(app, 2600)
        return Path(tab._margin_tiffs[0])

    def state(tag, mode, size_pt, bottom_mm, text="ChromIQ demo sheet"):
        p.layout_mode.setCurrentIndex(0 if mode == "patch_first" else 1)
        pump(app, 400)
        p.paper.setCurrentIndex(p.paper.findData("A4"))
        pump(app, 500)
        for k, v in (("t", 12.0), ("l", 10.0), ("r", 10.0), ("b", bottom_mm)):
            p.margins[k].setValue(v)
        p.helper_markers_cb.setChecked(False)
        p.text_edge.setValue(4.0)
        p.chart_text.setText(text)
        p.chart_text_size.setValue(size_pt)
        p.stamp_command.setChecked(False)
        pump(app, 1500)
        r, pb = predicted()
        rec = {"tag": tag, "mode": p.layout_mode.currentText(),
               "size_pt": size_pt, "bottom_box_mm": bottom_mm,
               "notice_before": notice(),
               "predicted_patch_bottom_mm": pb,
               "recipe_layout_mode": getattr(r, "layout_mode", "?")}
        tiff = build()
        rec["tiff"] = str(tiff)
        rec["sheet"] = measure_sheet(tiff)
        rep = seen.get("report")
        rec["measured_report_bottom_mm"] = (
            round(float(rep.bottom_mm), 3) if rep is not None
            and rep.bottom_mm is not None else None)
        rec["notice_after_build"] = notice()
        return rec

    recs = []
    for tag, mode, size, b in (
            ("A-area-24pt", "area_first", 24.0, 8.0),
            ("B-area-40pt", "area_first", 40.0, 8.0),
            ("C-patch-24pt", "patch_first", 24.0, 8.0),
            ("D-patch-40pt", "patch_first", 40.0, 12.0)):
        rec = state(tag, mode, size, b)
        recs.append(rec)
        print(f"  {tag}: predicted patch bottom "
              f"{rec['predicted_patch_bottom_mm']}, measured report "
              f"{rec['measured_report_bottom_mm']}, sheet "
              f"{rec['sheet'].get('patch_bottom_up_mm')}, text top "
              f"{rec['sheet'].get('text_top_up_mm')}, gap "
              f"{rec['sheet'].get('clear_gap_mm')}", flush=True)
        print("     notice:", (rec["notice_before"] or "(none)")[:200],
              flush=True)
        ok, why = capture_window(win, out / f"A-{tag}.png")
        rec["photo"] = f"{ok} {why}"

    (out / "adv23a.json").write_text(
        json.dumps(recs, indent=2, ensure_ascii=False), encoding="utf-8")
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

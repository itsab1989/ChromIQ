#!/usr/bin/env python3
"""Adversary 23c — the bottom text's own ink on the sheet the app built.

The chart is re-randomised on every Generate, so two builds cannot be
differenced. This drives the real window, lets the app build the sheet, and
then re-renders THE SAME `.ti1` with THE SAME recipe twice, once with the text
and once with a single space. The first re-render is compared pixel for pixel
with the app's own TIFF: while they are identical, the difference of the two
re-renders is the text's ink on the app's sheet and nothing else.

Then the rise the message names is applied with the "Bottom" box's own arrow
keys, the app builds again, and the same measurement is repeated.
"""
from __future__ import annotations

import json
import os
import re
import shutil
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

RISE = re.compile(r"by about ([0-9.]+) mm")


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def rerender(ti1: Path, recipe, text: str, tag: str):
    """The same recipe and the same .ti1, with a PINNED seed so the two
    re-renders differ in the text and in nothing else."""
    from dataclasses import replace
    from workflow.layout_engine.chart import build_from_recipe
    base = Path(tempfile.mkdtemp(prefix=f"adv23c-{tag}-"))
    res, _ = build_from_recipe(str(ti1), str(base / "s"),
                               replace(recipe, chart_text=text,
                                       seed_fixed=True, seed=987654321))
    return sorted(base.glob("s*.tif"))[0], res


def measure(app_tiff: Path, mine: Path, blank: Path, res) -> dict:
    import numpy as np
    from PIL import Image
    im = Image.open(str(app_tiff))
    dpi = float((im.info.get("dpi") or (300, 300))[0] or 300)
    A = np.asarray(im.convert("RGB"))
    M = np.asarray(Image.open(str(mine)).convert("RGB"))
    out = {"dpi": dpi}
    out["same_page_size"] = (A.shape == M.shape)
    if A.shape != M.shape:
        out["why"] = f"shape {A.shape} vs {M.shape}"
        return out
    G = np.asarray(Image.open(str(mine)).convert("L")).astype(np.int16)
    B = np.asarray(Image.open(str(blank)).convert("L")).astype(np.int16)
    if G.shape != B.shape:
        out["error"] = "blank geometry moved"
        return out
    h = G.shape[0]
    mm = lambda px: round(float(px) * 25.4 / dpi, 3)          # noqa: E731
    out["page_h_mm"] = mm(h)
    d = np.abs(G - B) > 30
    rows = np.where(d.any(axis=1))[0]
    if rows.size:
        out["text_ink_top_up_mm"] = mm(h - int(rows[0]))
        out["text_ink_bottom_up_mm"] = mm(h - int(rows[-1]) - 1)
        out["text_ink_height_mm"] = mm(int(rows[-1]) + 1 - int(rows[0]))
        cols = np.where(d.any(axis=0))[0]
        out["text_ink_width_mm"] = mm(int(cols[-1]) + 1 - int(cols[0]))
    rects = [r for r in (getattr(res, "strip_rects", None) or [])
             if int(r.get("page", 0)) == 0]
    if rects:
        y1 = max(int(r["y"]) + int(r["h"]) for r in rects)
        out["patch_rect_bottom_up_mm"] = mm(h - y1)
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv23c-"))
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
    tab._manual_target_name_edit.setText("adv23c")
    pump(app, 400)
    p = tab._manual_layout_panel
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    pump(app, 900)
    if p.use_instr_margins.isChecked():
        p.use_instr_margins.setChecked(False)
        pump(app, 400)

    seen: dict = {}
    from ui.margin_inspector_panel import MarginInspectorPanel
    _orig = MarginInspectorPanel.update_report

    def _spy(self, report, *a, **k):
        seen["report"] = report
        return _orig(self, report, *a, **k)
    MarginInspectorPanel.update_report = _spy        # type: ignore[assignment]

    def notice():
        _a, over = TabChart._engine_text_notes(tab)
        for s in over:
            if "runs into the patches" in s or "run into the patches" in s:
                return s
        return ""

    def build():
        tab._generate_btn.click()
        for _ in range(900):
            pump(app, 200)
            if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
                break
        pump(app, 2400)
        return Path(tab._margin_tiffs[0])

    def look(tag):
        """Build on screen, then measure the text's ink on that exact sheet."""
        tiff = build()
        r = tab._current_layout_recipe()
        ti1 = tiff.parent / f"{tiff.stem.rsplit('_', 1)[0]}.ti1"
        if not ti1.is_file():
            cands = sorted(tiff.parent.glob("*.ti1"))
            ti1 = cands[0] if cands else ti1
        mine, res = rerender(ti1, r, p.chart_text.text(), f"{tag}-t")
        blank, _res2 = rerender(ti1, r, " ", f"{tag}-b")
        m = measure(tiff, mine, blank, res)
        m["ti1"] = ti1.name
        rep = seen.get("report")
        m["measured_report_bottom_mm"] = (
            round(float(rep.bottom_mm), 3) if rep is not None
            and rep.bottom_mm is not None else None)
        if "text_ink_top_up_mm" in m and m.get("patch_rect_bottom_up_mm"):
            m["clear_gap_mm"] = round(
                m["patch_rect_bottom_up_mm"] - m["text_ink_top_up_mm"], 3)
            m["ink_reaches_patch_area"] = m["clear_gap_mm"] < 0
            m["rect_agrees_with_report"] = (
                m["measured_report_bottom_mm"] is not None
                and abs(m["patch_rect_bottom_up_mm"]
                        - m["measured_report_bottom_mm"]) < 0.2)
        shutil.copy2(tiff, out / f"C-{tag}.tif")
        return m

    recs = []

    def run(tag, mode_idx, size_pt, bottom_mm, markers=False, two_lines=False,
            text="ChromIQ demo sheet", size_auto=False):
        p.layout_mode.setCurrentIndex(mode_idx)
        pump(app, 400)
        p.paper.setCurrentIndex(p.paper.findData("A4"))
        pump(app, 500)
        for k, v in (("t", 12.0), ("l", 10.0), ("r", 10.0), ("b", bottom_mm)):
            p.margins[k].setValue(v)
        p.helper_markers_cb.setChecked(markers)
        p.text_edge.setValue(4.0)
        p.chart_text.setText(text)
        p.chart_text_size.setValue(p.chart_text_size.minimum() if size_auto
                                   else size_pt)
        p.stamp_command.setChecked(two_lines)
        pump(app, 1600)
        rec = {"tag": tag, "mode": p.layout_mode.currentText(),
               "size_box": p.chart_text_size.text(), "two_lines": two_lines,
               "markers": markers, "b_before": p.margins["b"].value(),
               "notice_before": notice()}
        m = RISE.search(rec["notice_before"] or "")
        rec["rise_named_mm"] = float(m.group(1)) if m else None
        rec["before"] = look(f"{tag}-before")
        print(f"  {tag}: {(rec['notice_before'] or '(no notice)')[:180]}",
              flush=True)
        print(f"      before: {json.dumps(rec['before'])}", flush=True)
        if rec["rise_named_mm"] is not None:
            box = p.margins["b"]
            box.setFocus(Qt.FocusReason.MouseFocusReason)
            pump(app, 300)
            steps = int(round(rec["rise_named_mm"] / float(box.singleStep())))
            for _ in range(steps):
                QTest.keyClick(box, Qt.Key.Key_Up)
                pump(app, 40)
            pump(app, 1600)
            rec["b_after"] = box.value()
            rec["notice_after"] = notice()
            rec["warning_gone"] = not rec["notice_after"]
            rec["after"] = look(f"{tag}-after")
            print(f"      after {steps} x Up -> box {rec['b_after']}, "
                  f"warning gone {rec['warning_gone']}", flush=True)
            print(f"      after: {json.dumps(rec['after'])}", flush=True)
            ok, why = capture_window(win, out / f"C-{tag}-after.png")
            rec["photo"] = f"{ok} {why}"
        recs.append(rec)

    run("S1-area-24pt", 0, 24.0, 8.0)
    run("S2-area-40pt", 0, 40.0, 12.0)
    run("S3-area-18pt-two-lines", 0, 18.0, 8.0, two_lines=True)
    run("S4-area-auto", 0, 0.0, 8.0, size_auto=True)
    run("S5-patch-40pt", 1, 40.0, 8.0)

    (out / "adv23c.json").write_text(
        json.dumps(recs, indent=2, ensure_ascii=False), encoding="utf-8")
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

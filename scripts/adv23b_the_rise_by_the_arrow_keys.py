#!/usr/bin/env python3
"""Adversary 23b — the rise the message names, typed with the ARROW KEYS.

For each colliding state:

1. read the notice and pull the rise out of it;
2. measure the sheet the app builds RIGHT NOW, isolating the bottom text's own
   ink by building the same recipe twice (text, then a single space) and
   differencing the two pages, so nothing depends on guessing which rows are
   patches;
3. put the keyboard focus in the "Bottom" box and press Up the number of times
   the rise takes at the box's own 0.5 mm step;
4. read the notice again, build again, and measure again.

The claim under attack: the warning goes away, and the sheet really is clear.
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


def diff_ink(with_text: Path, blank: Path) -> dict:
    """The bottom text's own ink, from the difference of two real pages."""
    import numpy as np
    from PIL import Image
    a = Image.open(str(with_text))
    dpi = float((a.info.get("dpi") or (300, 300))[0] or 300)
    A = np.asarray(a.convert("L")).astype(np.int16)
    B = np.asarray(Image.open(str(blank)).convert("L")).astype(np.int16)
    if A.shape != B.shape:
        return {"error": f"geometry moved {A.shape} vs {B.shape}"}
    h = A.shape[0]
    mm = lambda px: round(float(px) * 25.4 / dpi, 3)          # noqa: E731
    d = np.abs(A - B) > 30
    rows = np.where(d.any(axis=1))[0]
    out = {"dpi": dpi, "page_h_mm": mm(h)}
    if rows.size:
        out["text_ink_top_up_mm"] = mm(h - int(rows[0]))
        out["text_ink_bottom_up_mm"] = mm(h - int(rows[-1]) - 1)
    # the patch block: the page WITHOUT the text, lowest non-white row
    inkB = np.where((B < 245).any(axis=1))[0]
    if inkB.size:
        out["patch_ink_bottom_up_mm"] = mm(h - int(inkB[-1]) - 1)
    if "text_ink_top_up_mm" in out and "patch_ink_bottom_up_mm" in out:
        out["clear_gap_mm"] = round(
            out["patch_ink_bottom_up_mm"] - out["text_ink_top_up_mm"], 3)
        out["ink_collides"] = out["clear_gap_mm"] < 0
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv23b-"))
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
    tab._manual_target_name_edit.setText("adv23b")
    pump(app, 400)
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

    def build(dest: Path) -> Path:
        tab._generate_btn.click()
        for _ in range(900):
            pump(app, 200)
            if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
                break
        pump(app, 2400)
        src = Path(tab._margin_tiffs[0])
        shutil.copy2(src, dest)
        return dest

    def sheet(tag: str) -> dict:
        """Two real builds: the text, then a single space. Their difference is
        the text's ink and nothing else."""
        keep = p.chart_text.text()
        a = build(out / f"{tag}-with-text.tif")
        p.chart_text.setText(" ")
        pump(app, 900)
        b = build(out / f"{tag}-blank.tif")
        p.chart_text.setText(keep)
        pump(app, 900)
        return diff_ink(a, b)

    recs = []

    def run(tag, mode_idx, size_pt, bottom_mm, markers, text, two_lines=False,
            text_edge=4.0):
        p.layout_mode.setCurrentIndex(mode_idx)
        pump(app, 400)
        p.paper.setCurrentIndex(p.paper.findData("A4"))
        pump(app, 500)
        for k, v in (("t", 12.0), ("l", 10.0), ("r", 10.0), ("b", bottom_mm)):
            p.margins[k].setValue(v)
        p.helper_markers_cb.setChecked(markers)
        p.text_edge.setValue(text_edge)
        p.chart_text.setText(text)
        p.chart_text_size.setValue(size_pt)
        p.stamp_command.setChecked(two_lines)
        pump(app, 1600)
        rec = {"tag": tag, "mode": p.layout_mode.currentText(),
               "size_pt": size_pt, "b_box_before": p.margins["b"].value(),
               "markers": markers, "two_lines": two_lines,
               "text_edge": text_edge,
               "notice_before": notice()}
        m = RISE.search(rec["notice_before"] or "")
        rec["rise_named_mm"] = float(m.group(1)) if m else None
        rec["before"] = sheet(f"B-{tag}-before")
        print(f"  {tag}: {rec['notice_before'][:170] or '(no notice)'}",
              flush=True)
        print(f"      ink before: {rec['before']}", flush=True)
        if rec["rise_named_mm"] is None:
            recs.append(rec)
            return rec
        # ---- THE RISE, BY THE BOX'S OWN ARROW KEYS ----
        box = p.margins["b"]
        box.setFocus(Qt.FocusReason.MouseFocusReason)
        pump(app, 300)
        steps = int(round(rec["rise_named_mm"] / float(box.singleStep())))
        rec["step_mm"] = float(box.singleStep())
        rec["arrow_presses"] = steps
        for _ in range(steps):
            QTest.keyClick(box, Qt.Key.Key_Up)
            pump(app, 40)
        pump(app, 1600)
        rec["b_box_after"] = box.value()
        rec["notice_after"] = notice()
        rec["warning_gone"] = not rec["notice_after"]
        rec["after"] = sheet(f"B-{tag}-after")
        print(f"      after {steps} x Up ({rec['step_mm']} mm): box "
              f"{rec['b_box_after']}, warning gone {rec['warning_gone']}",
              flush=True)
        if not rec["warning_gone"]:
            print(f"      STILL: {rec['notice_after'][:170]}", flush=True)
        print(f"      ink after: {rec['after']}", flush=True)
        ok, why = capture_window(win, out / f"B-{tag}-after.png")
        rec["photo"] = f"{ok} {why}"
        recs.append(rec)
        return rec

    run("C1-area-24pt", 0, 24.0, 8.0, False, "ChromIQ demo sheet")
    run("C2-area-40pt", 0, 40.0, 12.0, False, "ChromIQ demo sheet")
    run("C3-area-24pt-markers", 0, 24.0, 8.0, True, "ChromIQ demo sheet")
    run("C4-area-18pt-two-lines", 0, 18.0, 8.0, False, "ChromIQ demo sheet",
        two_lines=True)
    run("C5-patch-40pt", 1, 40.0, 8.0, False, "ChromIQ demo sheet")

    (out / "adv23b.json").write_text(
        json.dumps(recs, indent=2, ensure_ascii=False), encoding="utf-8")
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Combined round 1: every remedy the bottom-text notices name, APPLIED.

A message is a promise. Each case sets the state the panel complains about,
reads the sentence, applies the remedy the sentence names through the widget a
person would use, presses Generate Chart again and reads the sentence again —
and the SHEET THE APP ITSELF RENDERED is measured each time, because the panel's
own number is the thing under test.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-b20r1.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-b20r1-presets \\
        python scripts/drive_182_combined_round1_promises.py <out-dir>
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
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


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def check(app, box, want: bool) -> None:
    if bool(box.isChecked()) != bool(want):
        box.click()
    pump(app, 200)


def install_excepthook() -> list:
    seen: list = []
    prev = sys.excepthook

    def hook(t, e, tb):
        seen.append("".join(traceback.format_exception(t, e, tb)))
        prev(t, e, tb)

    sys.excepthook = hook
    return seen


def measure_generated(tab, tag: str, out: Path) -> dict:
    """THE SHEET THE APP RENDERED, not one this script builds.

    `tab._margin_tiffs` are the TIFFs Generate Chart just wrote; the bottom
    text is printed on every page, so page 0 is measured.
    """
    import numpy as np
    from PIL import Image
    tiffs = list(getattr(tab, "_margin_tiffs", []) or [])
    if not tiffs:
        return {"error": "no generated TIFF"}
    im = Image.open(tiffs[0]).convert("RGB")
    (out / "sheets").mkdir(parents=True, exist_ok=True)
    im.save(out / "sheets" / f"{tag}.png")
    a = np.asarray(im).astype(int)
    dpi = float(im.info.get("dpi", (300, 300))[0] or 300)
    px2mm = 25.4 / dpi
    h, w = a.shape[0], a.shape[1]
    mx, mn = a.max(2), a.min(2)
    black = (mx < 100) & ((mx - mn) < 30)
    coloured = (a.sum(2) < 720) & ((mx - mn) > 25)
    d = {"sheet": f"sheets/{tag}.png", "dpi": dpi,
         "paper_w_mm": round(w * px2mm, 2), "paper_h_mm": round(h * px2mm, 2)}
    if not coloured.any():
        d["error"] = "no patches"
        return d
    crows = np.where(coloured.any(1))[0]
    patch_bottom_mm = float(h - crows[-1] - 1) * px2mm
    d["patch_bottom_mm"] = round(patch_bottom_mm, 3)
    # The bottom text band: black ink BELOW the last patch row.
    below = black[crows[-1] + 1:, :]
    rows = np.where(below.any(1))[0]
    if len(rows):
        top_abs = crows[-1] + 1 + rows[0]
        d["text_ink_top_mm_from_bottom"] = round(
            float(h - top_abs - 1) * px2mm, 3)
        d["clear_paper_between_mm"] = round(
            patch_bottom_mm - float(h - top_abs - 1) * px2mm, 3)
        band = black[top_abs:, :]
        cols = np.where(band.any(0))[0]
        d["text_ink_left_mm"] = round(float(cols[0]) * px2mm, 3)
        d["text_ink_right_mm_from_right"] = round(
            float(w - cols[-1] - 1) * px2mm, 3)
        d["text_ink_width_mm"] = round(float(cols[-1] - cols[0] + 1) * px2mm, 3)
        # RUNNING OFF THE PAPER is ink in the first or last column.
        d["ink_touches_left_edge"] = bool(band[:, 0].any())
        d["ink_touches_right_edge"] = bool(band[:, -1].any())
    else:
        d["text_ink_top_mm_from_bottom"] = None
    # Black ink drawn INSIDE the patch block: the collision itself.
    d["black_rows_inside_patches"] = int(
        black[crows[0]:crows[-1] + 1, :].any(1).sum())
    return d


def main() -> int:                                  # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    crashes = install_excepthook()

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r1p-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    sandbox: {work}", flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1680, 1060)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    print(f"    window on screen: {win.isVisible()}", flush=True)

    panel = tab._manual_layout_panel
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("B20R1Promise")
    pump(app, 400)
    check(app, panel.use_instr_margins, False)

    rows: list = []

    def generate(tag: str) -> None:
        tab._margin_report = None
        tab._generate_btn.click()
        for _ in range(1200):
            pump(app, 120)
            if getattr(tab, "_margin_report", None) is not None:
                break

    def notice(tag: str, photograph: bool = False) -> dict:
        pump(app, 500)
        tab._update_margin_inspector()
        pump(app, 700)
        r = panel.get_recipe()
        warns, over = TabChart._engine_text_notes(
            tab, getattr(tab, "_margin_report", None))
        rep = getattr(tab, "_margin_report", None)
        row = {
            "case": tag,
            "chart_text_size_mm": getattr(r, "chart_text_size_mm", None),
            "chart_text_align": getattr(r, "chart_text_align", None),
            "text_edge_clip_mm": getattr(r, "text_edge_clip_mm", None),
            "measured": (None if rep is None else
                         {k: round(float(getattr(rep, k)), 3)
                          for k in ("left_mm", "right_mm", "top_mm",
                                    "bottom_mm")}),
            "warnings": list(over),
            "ink": measure_generated(tab, tag, out),
        }
        if photograph:
            shot = out / f"{tag}.png"
            ok, why = capture_window(win, shot)
            row["photograph"] = str(shot) if ok else None
            row["photograph_refused"] = None if ok else why
            print(f"      photograph: {'OK' if ok else 'REFUSED: ' + why}",
                  flush=True)
        rows.append(row)
        print(f"    [{tag}] {len(over)} warning(s); ink={row['ink']}",
              flush=True)
        for m in over:
            print(f"        {m[:260]}", flush=True)
        return row

    # ---- The state: a 20 pt bottom line that is far too wide --------------
    panel.layout_mode.setCurrentIndex(
        max(0, panel.layout_mode.findData("area_first")))
    pump(app, 400)
    for k, v in (("b", 22.0), ("t", 10.0), ("l", 10.0), ("r", 10.0)):
        panel.margins[k].setValue(v)
    panel.chart_text.setText("Combined round one bottom text that is long")
    panel.chart_text_size.setValue(20.0)
    check(app, panel.stamp_command, False)
    panel.text_edge.setValue(4.0)
    pump(app, 500)
    generate("B1")
    b1 = notice("B1-too-wide-at-20pt", photograph=True)

    # ---- REMEDY 1: "Set Size to auto under Sheet text and it shrinks to fit"
    wide = [m for m in b1["warnings"] if "too wide for the paper" in m]
    if wide:
        print("    applying the remedy the sentence names: Size = auto",
              flush=True)
        panel.chart_text_size.setValue(0.0)      # 0 == auto in this box
        pump(app, 400)
        print(f"    size box now reads {panel.chart_text_size.text()!r} "
              f"value={panel.chart_text_size.value()}", flush=True)
        generate("B2")
        b2 = notice("B2-size-auto", photograph=True)
        b2["remedy"] = "Size = auto"
        b2["cleared"] = not any("too wide for the paper" in m
                                for m in b2["warnings"])
        print(f"    [B2] too-wide cleared: {b2['cleared']}", flush=True)

    # ---- REMEDY 2: another Alignment, at a fixed size ---------------------
    panel.chart_text_size.setValue(20.0)
    pump(app, 300)
    generate("B3")
    b3 = notice("B3-back-to-20pt")
    for i in range(panel.chart_text_align.count()):
        panel.chart_text_align.setCurrentIndex(i)
        pump(app, 300)
        generate(f"B4-align{i}")
        row = notice(f"B4-align{i}-{panel.chart_text_align.currentText()}")
        row["remedy"] = f"Alignment = {panel.chart_text_align.currentText()}"
        row["cleared"] = not any("too wide for the paper" in m
                                 for m in row["warnings"])

    (out / "promises.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "crashes-promises.txt").write_text("\n\n".join(crashes) or "none",
                                              encoding="utf-8")
    print(f"    crashes: {len(crashes)}", flush=True)
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Combined round 1: the chart panel's bottom-text promise, driven on screen.

Generate, read the notice, APPLY THE RISE IT NAMES, generate again, and measure
the rendered sheet each time. The panel's own sentence is not evidence; the ink
is.

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-b20r1.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-b20r1-presets \\
        python scripts/drive_182_combined_round1_chart.py <out-dir>

**Never set QT_QPA_PLATFORM=offscreen for this.**
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
    assert bool(box.isChecked()) is bool(want), f"{box.text()!r} -> {want}"


def install_excepthook() -> list:
    seen: list = []
    prev = sys.excepthook

    def hook(t, e, tb):
        seen.append("".join(traceback.format_exception(t, e, tb)))
        prev(t, e, tb)

    sys.excepthook = hook
    return seen


def sheet_ink(recipe, ti1: Path, tag: str, out: Path) -> "dict | None":
    """Measure the RENDERED sheet: where the patches stop and where the bottom
    text's ink begins, both in mm from the paper edge."""
    import numpy as np
    from PIL import Image
    from workflow.layout_engine import chart as _chart
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r1-ink-"))
    try:
        _chart.build_from_recipe(recipe, ti1, str(work / "sheet"))
        tif = sorted(work.glob("sheet*.tif"))
        if not tif:
            return {"error": "no sheet"}
        im = Image.open(tif[0]).convert("RGB")
        (out / "sheets").mkdir(parents=True, exist_ok=True)
        im.save(out / "sheets" / f"{tag}.png")
        a = np.asarray(im).astype(int)
        dpi = float(getattr(recipe, "dpi", 300) or 300)
        px2mm = 25.4 / dpi
        h = a.shape[0]
        mx, mn = a.max(2), a.min(2)
        black = (mx < 100) & ((mx - mn) < 30)
        coloured = (a.sum(2) < 720) & ((mx - mn) > 25)
        if not coloured.any():
            return {"error": "no patches"}
        crows = np.where(coloured.any(1))[0]
        patch_bottom_mm = float(h - crows[-1] - 1) * px2mm
        # The bottom text's ink: the deepest BLACK rows BELOW the patches.
        below = black[crows[-1] + 1:, :]
        rows = np.where(below.any(1))[0]
        d = {"sheet": f"sheets/{tag}.png",
             "paper_h_mm": round(float(h) * px2mm, 2),
             "patch_bottom_mm": round(patch_bottom_mm, 3)}
        if len(rows):
            top_abs = crows[-1] + 1 + rows[0]
            bot_abs = crows[-1] + 1 + rows[-1]
            d["text_ink_top_mm_from_bottom"] = round(
                float(h - top_abs - 1) * px2mm, 3)
            d["text_ink_bottom_mm_from_bottom"] = round(
                float(h - bot_abs - 1) * px2mm, 3)
            d["clear_paper_between_mm"] = round(
                patch_bottom_mm - float(h - top_abs - 1) * px2mm, 3)
        else:
            d["text_ink_top_mm_from_bottom"] = None
            d["clear_paper_between_mm"] = None
        # Does any black ink sit INSIDE the patch block's rows? That is the
        # collision the notice is about, measured rather than predicted.
        d["black_rows_inside_patches"] = int(
            black[crows[0]:crows[-1] + 1, :].any(1).sum())
        return d
    except Exception as exc:                       # noqa: BLE001
        return {"error": repr(exc)}
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r1-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
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
    print(f"    window on screen: {win.isVisible()} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}",
          flush=True)

    panel = tab._manual_layout_panel
    assert panel is not None, "no ChromIQ layout panel"
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("B20R1Chart")
    pump(app, 400)
    check(app, panel.use_instr_margins, False)

    rows: list = []

    def generate(tag: str) -> float:
        tab._margin_report = None
        t0 = time.monotonic()
        tab._generate_btn.click()
        for _ in range(1200):
            pump(app, 120)
            if getattr(tab, "_margin_report", None) is not None:
                break
        wall = time.monotonic() - t0
        rep = getattr(tab, "_margin_report", None)
        if rep is None:
            print(f"    [{tag}] GENERATE produced no measurement", flush=True)
            return wall
        print(f"    [{tag}] measured L/R/T/B = {rep.left_mm:.2f}/"
              f"{rep.right_mm:.2f}/{rep.top_mm:.2f}/{rep.bottom_mm:.2f} mm "
              f"({wall:.1f} s)", flush=True)
        return wall

    def notice(tag: str, photograph: bool = False) -> dict:
        pump(app, 500)
        t0 = time.monotonic()
        tab._update_margin_inspector()
        inspector_ms = (time.monotonic() - t0) * 1000.0
        pump(app, 700)
        r = panel.get_recipe()
        warns, over = TabChart._engine_text_notes(
            tab, getattr(tab, "_margin_report", None))
        rep = getattr(tab, "_margin_report", None)
        row = {
            "case": tag,
            "layout_mode": r.layout_mode,
            "margin_bottom": r.margin_bottom,
            "chart_text": r.chart_text,
            "chart_text_size_mm": getattr(r, "chart_text_size_mm", None),
            "stamp_command": bool(getattr(r, "stamp_command", False)),
            "text_edge_mm": getattr(r, "text_edge_mm", None),
            "inspector_ms": round(inspector_ms, 1),
            "measured": (None if rep is None else
                         {k: round(float(getattr(rep, k)), 3)
                          for k in ("left_mm", "right_mm", "top_mm",
                                    "bottom_mm")}),
            "warnings": list(over),
            "notes": [w for w in warns if w not in over],
        }
        if photograph:
            shot = out / f"{tag}.png"
            ok, why = capture_window(win, shot)
            row["photograph"] = str(shot) if ok else None
            row["photograph_refused"] = None if ok else why
            print(f"      photograph: {'OK' if ok else 'REFUSED: ' + why}",
                  flush=True)
        rows.append(row)
        print(f"    [{tag}] inspector {inspector_ms:.0f} ms, "
              f"{len(over)} warning(s)", flush=True)
        for m in over:
            print(f"        {m[:220]}", flush=True)
        return row

    # ----------------------------------------------------------------
    # Chart-first ("Prioritise chart area"), where a margin value is law
    # and the bottom-text notice is allowed to name a rise.
    # ----------------------------------------------------------------
    panel.layout_mode.setCurrentIndex(
        max(0, panel.layout_mode.findData("area_first")))
    pump(app, 500)
    panel.margins["b"].setValue(4.0)
    panel.margins["t"].setValue(10.0)
    panel.margins["l"].setValue(10.0)
    panel.margins["r"].setValue(10.0)
    panel.chart_text.setText("Combined round 1 bottom text")
    panel.chart_text_size.setValue(20.0)
    check(app, panel.stamp_command, True)
    panel.text_edge.setValue(4.0)
    pump(app, 500)

    generate("A1")
    row = notice("A1-overlap", photograph=True)
    ti1 = getattr(tab, "_manual_ti1_path", None) or getattr(
        tab, "_last_ti1", None)

    # The sheet the panel is talking about, measured.
    recipe = panel.get_recipe()
    ti1_path = None
    for cand in (getattr(tab, "_margin_ti2", None),):
        if cand:
            p = Path(cand).with_suffix(".ti1")
            if p.is_file():
                ti1_path = p
    if ti1_path is not None:
        row["ink"] = sheet_ink(recipe, ti1_path, "A1-overlap", out)
        print(f"    [A1] ink: {row['ink']}", flush=True)

    # ---- APPLY THE RISE THE NOTICE NAMES -----------------------------
    import re as _re
    rise = None
    for m in row["warnings"]:
        if "runs into the patches" in m or "run into the patches" in m:
            mm = _re.search(r"Raise “Bottom” under “Margins \(mm\)” by about "
                            r"([0-9.]+) mm", m)
            if mm:
                rise = float(mm.group(1))
    row["named_rise_mm"] = rise
    print(f"    [A1] the notice names a rise of {rise} mm", flush=True)

    if rise is not None:
        panel.margins["b"].setValue(round(4.0 + rise, 1))
        pump(app, 400)
        generate("A2")
        row2 = notice("A2-after-the-rise", photograph=True)
        recipe2 = panel.get_recipe()
        if ti1_path is not None:
            row2["ink"] = sheet_ink(recipe2, ti1_path, "A2-after-the-rise", out)
            print(f"    [A2] ink: {row2['ink']}", flush=True)
        row2["applied_rise_mm"] = rise
        row2["bottom_notice_cleared"] = not any(
            "into the patches" in m for m in row2["warnings"])
        print(f"    [A2] bottom notice cleared: "
              f"{row2['bottom_notice_cleared']}", flush=True)

    # ---- THE COST OF THE FRAME, ON A SHEET THAT STILL WARNS -----------
    # Back to the overlapping state, and time ten repaints of the frame:
    # every page turn pays this, and so does every Generate.
    panel.margins["b"].setValue(4.0)
    pump(app, 300)
    generate("A3")
    times = []
    for _ in range(10):
        t0 = time.monotonic()
        tab._update_margin_inspector()
        times.append(round((time.monotonic() - t0) * 1000.0, 1))
        pump(app, 120)
    times.sort()
    print(f"    [A3] ten frame repaints, ms: {times}", flush=True)
    rows.append({"case": "A3-frame-repaint-cost-ms", "times_ms": times,
                 "median_ms": times[len(times) // 2]})

    (out / "chart-notices.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "crashes.txt").write_text("\n\n".join(crashes) or "none",
                                     encoding="utf-8")
    print(f"    crashes: {len(crashes)}", flush=True)
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

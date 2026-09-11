#!/usr/bin/env python3
"""On-screen reproduction / proof for Knut's #182 comment of 2026-09-11T21:23:10Z.

Drives the REAL ChromIQ window, on screen, against a sandboxed settings file, a
sandboxed presets folder and a sandboxed working folder, using KNUT'S OWN
project (``test``, the two-run project in his ``test.zip``) and his own numbers.

It answers, for each item:

  F1  Right margin 32.5 mm and 32.0 mm, clip border 24 mm on the right, run 1's
      recipe, Chart Notes "test text". What does the "Measured from Preview"
      message field say, and WHERE does the note's ink actually land on the
      sheet the app writes?  Measured in pixels off that TIFF and converted
      with the sheet's own resolution, the way he measured his.
  F2  Run 2's recipe with the Sheet text Size on "auto": what size is the note
      printed at, and is any of it lost off the sheet?
  F3  Run 1's clip border narrowed until the clip text stops shrinking: how
      close to the paper edge does the band's text get, and what is said?

Usage:

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-sheettext.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-sheettext-presets
    python scripts/drive_182_sheet_text_fit.py --out DIR [--tag before]
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QTimer                                  # noqa: E402
from PyQt6.QtGui import QFontDatabase                            # noqa: E402
from PyQt6.QtWidgets import QApplication                         # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                       # noqa: E402
from onscreen_capture import capture_window, session_is_locked    # noqa: E402

WORK = Path("/tmp/chromiq-sheettext-work")
KNUT = Path("/tmp/chromiq-sheettext-proof/knut/project")
PROJECT = "test"

modals: list[dict] = []
_timers: list = []


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def install_modal_watchdog(app):
    def check():
        w = app.activeModalWidget()
        if w is None:
            return
        title = w.windowTitle()
        text = ""
        for attr in ("text", "toPlainText"):
            f = getattr(w, attr, None)
            if callable(f):
                try:
                    text = str(f())
                    break
                except Exception:
                    pass
        modals.append({"title": title, "text": text[:400]})
        print(f"    !! modal: {title!r} -> closing")
        try:
            w.reject()
        except Exception:
            w.close()
    t = QTimer()
    t.setInterval(400)
    t.timeout.connect(check)
    t.start()
    _timers.append(t)


def wait_for_build(app, tab, timeout=300) -> bool:
    end = time.time() + timeout
    pump(app, 800)
    while time.time() < end:
        app.processEvents()
        time.sleep(0.05)
        if tab._generate_btn.isEnabled() and not tab._runner.is_running:
            pump(app, 1500)
            if tab._generate_btn.isEnabled() and not tab._runner.is_running:
                return True
    return False


# --------------------------------------------------------------------------
# HIS RULER, ON THE APP'S OWN SHEET.
# --------------------------------------------------------------------------

def _read_gray(path: Path):
    import numpy as np
    import tifffile
    with tifffile.TiffFile(str(path)) as tf:
        page = tf.pages[0]
        arr = np.array(page.asarray())
        try:
            xres = page.tags["XResolution"].value
            dpi = float(xres[0]) / float(xres[1])
            # ResolutionUnit 3 is CENTIMETRES, and the engine writes that.
            if int(page.tags["ResolutionUnit"].value) == 3:
                dpi *= 2.54
        except Exception:
            dpi = 200.0
    return (arr.min(axis=2) if arr.ndim == 3 else arr), dpi


#: A column is "patch area" when this share of its rows is inked. The stamper's
#: own threshold (`tiff_metadata._PATCH_COL_DENSITY_THRESHOLD`), so the ruler
#: finds the same right edge the note was placed against.
PATCH_COL_DENSITY = 0.5


def right_side_map(path: Path) -> dict:
    """Every run of ink to the right of the patch block, in mm from ITS edge.

    This is the measurement Knut made by eye on his own TIFF: "39 pixels from
    the patch area right edge to the top of the 't'". Reported in pixels AND in
    millimetres converted with the sheet's own resolution, plus the same
    distances from the paper's right edge, because the warning's own numbers
    are measured from there.
    """
    import numpy as np
    g, dpi = _read_gray(path)
    H, W = g.shape[:2]
    full = 65535 if g.dtype.itemsize == 2 else 255
    ink = g < int(0.94 * full)
    density = ink.sum(axis=0) / max(1, H)
    patch = np.flatnonzero(density >= PATCH_COL_DENSITY)
    if not len(patch):
        return {"dpi": round(dpi, 2), "error": "no patch block"}
    patch_right = int(patch[-1])
    mm = 25.4 / dpi
    cols = ink.any(axis=0)
    runs = []
    start = None
    for x in range(patch_right + 1, W):
        if cols[x] and start is None:
            start = x
        elif not cols[x] and start is not None:
            runs.append((start, x - 1))
            start = None
    if start is not None:
        runs.append((start, W - 1))
    return {
        "dpi": round(dpi, 2),
        "page_w_px": int(W),
        "page_w_mm": round(W * mm, 2),
        "patch_right_px": patch_right,
        "patch_right_from_paper_edge_mm": round((W - 1 - patch_right) * mm, 2),
        "ink_right_of_patches": [
            {
                "x0": a, "x1": b,
                "from_patch_edge_px": [a - patch_right, b - patch_right],
                "from_patch_edge_mm": [round((a - patch_right) * mm, 2),
                                       round((b - patch_right) * mm, 2)],
                "from_paper_edge_mm": [round((W - 1 - a) * mm, 2),
                                       round((W - 1 - b) * mm, 2)],
                "rows_inked_max": int(ink[:, a:b + 1].sum(axis=0).max()),
            }
            for a, b in runs
        ],
    }


def note_diff(before: Path, after: Path) -> dict:
    """The ink two otherwise identical sheets differ by: the note itself."""
    import numpy as np
    a, dpi = _read_gray(before)
    b, _ = _read_gray(after)
    if a.shape != b.shape:
        return {"error": f"shape {a.shape} vs {b.shape}"}
    H, W = a.shape[:2]
    diff = (a.astype(int) != b.astype(int))
    cols = diff.any(axis=0)
    rows = diff.any(axis=1)
    if not cols.any():
        return {"dpi": round(dpi, 2), "changed": False}
    xi = np.flatnonzero(cols)
    yi = np.flatnonzero(rows)
    mm = 25.4 / dpi
    full = 65535 if a.dtype.itemsize == 2 else 255
    ink = b < int(0.94 * full)
    density = ink.sum(axis=0) / max(1, H)
    patch = np.flatnonzero(density >= PATCH_COL_DENSITY)
    pr = int(patch[-1]) if len(patch) else -1
    return {
        "dpi": round(dpi, 2),
        "changed": True,
        "note_width_px": int(xi[-1] - xi[0] + 1),
        "note_width_mm": round((xi[-1] - xi[0] + 1) * mm, 3),
        "note_width_pt": round((xi[-1] - xi[0] + 1) * 72.0 / dpi, 2),
        "note_from_paper_edge_mm": [round((W - int(xi[0])) * mm, 2),
                                    round((W - int(xi[-1])) * mm, 2)],
        "note_from_patch_edge_mm": ([round((int(xi[0]) - pr) * mm, 2),
                                     round((int(xi[-1]) - pr) * mm, 2)]
                                    if pr >= 0 else None),
        # DOWN the sheet, which is the axis a long note runs off.
        "note_top_px": int(yi[0]),
        "note_bottom_px": int(yi[-1]),
        "note_length_mm": round((yi[-1] - yi[0] + 1) * mm, 2),
        "page_h_mm": round(H * mm, 2),
        "clear_of_top_mm": round(int(yi[0]) * mm, 2),
        "clear_of_bottom_mm": round((H - 1 - int(yi[-1])) * mm, 2),
    }


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-sheettext-proof/onscreen")
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "run"
    out.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    res: dict = {"tag": tag, "modals": modals,
                 "screen_locked": session_is_locked()}
    print(f"00 screen locked: {res['screen_locked']}")

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from core.resource_path import resource_path
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))

    from core.settings import AppSettings
    settings = AppSettings()
    WORK.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(WORK))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("appearance", "dark")
    from ui import theme as ui_theme
    ui_theme.apply_appearance(app, None, "dark")
    assert settings.get("custom_output_path", "") == str(WORK), "SANDBOX FAILED"
    print(f"00 sandbox: settings {os.environ['CHROMIQ_SETTINGS_FILE']}, work {WORK}")

    src = KNUT / PROJECT
    dst = WORK / PROJECT
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"00 staged Knut's project at {dst}")

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1620, 1060)
    win.show()
    pump(app, 1200)
    install_modal_watchdog(app)

    tab = win._tab_chart

    picked = False
    w = getattr(tab, "_target_combo", None)
    if w is not None:
        for i in range(w.count()):
            if w.itemText(i).strip() == PROJECT:
                w.setCurrentIndex(i)
                picked = True
                break
    pump(app, 900)
    res["target_picked_from_combo"] = picked

    if tab._current_mode() != "manual":
        tab._switch_mode("manual")
    pump(app, 600)
    if not picked:
        tab._manual_target_name_edit.setText(PROJECT)
        pump(app, 600)

    panel = tab._manual_layout_panel
    panel._expert_frame.set_collapsed(False)
    pump(app, 500)

    meta1 = json.loads((src / "runs/run1/meta.json").read_text(encoding="utf-8"))
    meta2 = json.loads((src / "runs/run2/meta.json").read_text(encoding="utf-8"))
    rec1 = meta1["create_chart_ui"]["engine_recipe"]
    rec2 = meta2["create_chart_ui"]["engine_recipe"]
    res["run2_chart_notes"] = meta2["chart_notes"]

    from workflow.layout_engine.presets import LayoutRecipe

    steps: list[dict] = []
    state = {"notes": ""}

    def apply(base, **over):
        r = LayoutRecipe.from_dict({**base, "randomize": True,
                                    "seed_fixed": True, "seed": 4242, **over})
        panel.set_recipe(r)
        pump(app, 900)

    def build():
        for t in dst.rglob("*.tif"):
            t.unlink()
        tab._generate_btn.click()
        okb = wait_for_build(app, tab)
        pump(app, 1500)
        return okb, sorted(dst.rglob("*.tif"))

    def snapshot(name: str, comment: str, generate: bool = False,
                 measure_note: bool = False) -> dict:
        pump(app, 700)
        st: dict = {"step": name, "comment": comment}
        r = panel.get_recipe()
        st["margin_right_mm"] = round(float(r.margin_right), 2)
        st["margin_left_mm"] = round(float(r.margin_left), 2)
        st["text_edge_clip_mm"] = round(float(r.text_edge_clip_mm), 2)
        st["clip_border_on"] = bool(r.clip_border)
        st["clip_border_width_mm"] = round(float(r.clip_border_width_mm), 2)
        st["clip_side"] = r.clip_side
        st["clip_content_mode"] = r.clip_content_mode
        st["chart_notes"] = state["notes"]
        st["chart_text_size_pt"] = round(float(panel.chart_text_size.value()), 2)
        st["clip_text_size_pt"] = round(float(panel.clip_text_size.value()), 2)
        try:
            warns, over = type(tab)._engine_text_notes(tab)
        except Exception as exc:                                   # noqa: BLE001
            warns, over = [f"<raised {exc!r}>"], []
        st["all_notices"] = warns
        st["overlap_notices"] = over

        if generate:
            baseline = None
            if measure_note:
                tab._manual_chart_notes_edit.setText("")
                tab._manual_stamp_cmd_check.setChecked(False)
                pump(app, 600)
                _ok0, tifs0 = build()
                if tifs0:
                    baseline = out / f"{tag}_{name}__baseline.tif"
                    shutil.copy(tifs0[0], baseline)
                tab._manual_chart_notes_edit.setText(state["notes"])
                pump(app, 600)
            st["build_finished"], tifs = build()
            st["tifs"] = [t.name for t in tifs]
            if tifs:
                shutil.copy(tifs[0], out / f"{tag}_{name}__sheet.tif")
                st["right_side"] = right_side_map(tifs[0])
                if baseline is not None:
                    st["note"] = note_diff(baseline, tifs[0])
        ok, why = capture_window(win, out / f"{tag}_{name}.png")
        st["shot"] = f"{tag}_{name}.png" if ok else ""
        st["shot_refused"] = why
        steps.append(st)
        print(f"  {name}: right={st['margin_right_mm']} clip={st['text_edge_clip_mm']} "
              f"band={st['clip_border_width_mm']} -> {len(over)} overlap notice(s)")
        for line in over:
            print("     RED: " + line.replace("\n", " "))
        if st.get("note"):
            print("     NOTE INK: " + json.dumps(st["note"]))
        if st.get("right_side"):
            print("     RIGHT OF PATCHES: "
                  + json.dumps(st["right_side"]["ink_right_of_patches"]))
        return st

    only = sys.argv[sys.argv.index("--only") + 1].split(",") \
        if "--only" in sys.argv else None

    def want(k: str) -> bool:
        return only is None or k in only

    # ---- F1: his two sheets, his numbers, his notes text. -----------------
    if want("f1"):
        state["notes"] = "test text"
        tab._manual_chart_notes_edit.setText("test text")
        tab._manual_stamp_cmd_check.setChecked(False)
        pump(app, 500)
        for mr in (32.5, 32.0):
            apply(rec1, margin_right=mr, chart_text_size_mm=10.0 * 25.4 / 72.0)
            snapshot(f"f1_right{str(mr).replace('.', '_')}",
                     f"F1: his own sheet at right margin {mr} mm",
                     generate=True, measure_note=True)

    # ---- F2: run 2's long note, Sheet text Size on auto. ------------------
    if want("f2"):
        state["notes"] = meta2["chart_notes"]
        tab._manual_chart_notes_edit.setText(meta2["chart_notes"])
        tab._manual_stamp_cmd_check.setChecked(False)
        pump(app, 500)
        apply(rec2, chart_text_size_mm=0.0)
        snapshot("f2_run2_auto", "F2: run 2, Sheet text Size = auto",
                 generate=True, measure_note=True)
        apply(rec2, chart_text_size_mm=7.0 * 25.4 / 72.0)
        snapshot("f2_run2_7pt", "F2: run 2, Sheet text Size = 7 pt",
                 generate=True, measure_note=True)

    # ---- F3: the clip band too narrow for its own text. -------------------
    if want("f3"):
        state["notes"] = ""
        tab._manual_chart_notes_edit.setText("")
        tab._manual_stamp_cmd_check.setChecked(False)
        pump(app, 500)
        for band in (24.0, 16.0, 12.0):
            apply(rec1, clip_border_width_mm=band,
                  margin_right=max(32.0, band + 8), clip_text_size_mm=0.0)
            snapshot(f"f3_band{int(band)}",
                     f"F3: clip band {band} mm, clip text size auto",
                     generate=True)

    res["steps"] = steps
    (out / f"{tag}_result.json").write_text(json.dumps(res, indent=1),
                                            encoding="utf-8")
    print(f"\nwrote {out / (tag + '_result.json')}")
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

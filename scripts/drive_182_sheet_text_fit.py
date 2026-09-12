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


#: A patch counts as touched when this share of its pixels changed between the
#: sheet with the clip content off and the sheet with it on. One pixel of a
#: 200 dpi patch is 0.016 mm2, and a stray antialiasing pixel is not a fault;
#: anything a measuring instrument can see is far above this.
TOUCHED_FRAC = 0.0005


def patches_under_the_text(baseline: Path, after: Path, recipe) -> dict:
    """Which PATCHES the clip band's text is printed on top of, and how hard.

    The two sheets differ only in the clip content, so every changed pixel is
    the band's own ink. The patch rectangles come from the engine that drew
    them (`geometry.patch_rects_px`), not from image detection, so a patch that
    is covered is named exactly.

    **This is the question underneath Knut's ruling**, not a detail of it: a
    patch with ink on it is still measured, and what the instrument reads is
    the patch and the ink together.
    """
    import numpy as np
    from workflow.layout_engine import geometry as _geom
    from workflow.layout_engine import instruments as _inst
    from workflow.layout_engine import papers as _papers
    a, dpi = _read_gray(baseline)
    b, _ = _read_gray(after)
    if a.shape != b.shape:
        return {"error": f"shape {a.shape} vs {b.shape}"}
    changed = (a.astype(int) != b.astype(int))
    kw = recipe.build_kwargs()
    g = _inst.geom_from_build_kwargs(kw)
    pw, ph = _papers.dimensions_mm(str(recipe.paper))
    npat = int(kw.get("npat") or 0) or int(
        (recipe.area_cols or 0) * (recipe.area_rows or 0)) or 600
    lay = _geom.compute(g, pw, ph, npat)
    rects = _geom.patch_rects_px(g, pw, ph, lay, int(recipe.dpi))
    H, W = a.shape[:2]
    hit = []
    for r in rects:
        x0, y0 = max(0, int(r["x"])), max(0, int(r["y"]))
        x1, y1 = min(W, x0 + int(r["w"])), min(H, y0 + int(r["h"]))
        if x1 <= x0 or y1 <= y0:
            continue
        sub = changed[y0:y1, x0:x1]
        n = int(sub.sum())
        area = sub.size
        if area and n / area > TOUCHED_FRAC:
            hit.append({"loc": r.get("loc"), "covered_frac": round(n / area, 4),
                        "covered_px": n, "patch_px": int(area)})
    hit.sort(key=lambda d: -d["covered_frac"])
    return {
        "dpi": round(dpi, 2),
        "patches_total": len(rects),
        "patches_touched": len(hit),
        "worst": hit[:12],
        "max_covered_frac": (hit[0]["covered_frac"] if hit else 0.0),
    }


def left_side_map(recipe) -> dict:
    """Every boundary on the LEFT of the sheet, in order, from the GEOMETRY.

    Knut, #182, 2026-09-12 (the edited post): *"If clip-border text starts
    overlapping with the row labels (if enabled), the warning shall occur too,
    because the row labels are left of the patch area edges …"*

    So the left is a three-way squeeze, and every boundary is taken from the
    engine that draws it rather than from ink detection: where the clip content
    starts, where its band ends, how far its text reaches past that, the row
    labels' floor and band, where the label ink actually starts, and the patch
    area's left edge.
    """
    from workflow import text_edge_fit as _tef
    from workflow.layout_engine import instruments as _inst
    from workflow.layout_engine.raster import clip_text_lines
    g = _inst.geom_from_build_kwargs(recipe.build_kwargs())
    clip_w = float(g.lbord) + float(g.border)
    inset = _tef.clip_content_inset_mm(clip_w, g.text_edge_clip_mm)
    lines = len(clip_text_lines(getattr(recipe, "clip_text", "") or ""))
    size_pt = float(getattr(recipe, "clip_text_size_mm", 0.0) or 0.0) * 72.0 / 25.4
    over = _tef.clip_text_overhang_mm(clip_w, g.text_edge_clip_mm, lines, size_pt)
    floor = float(getattr(g, "row_label_floor", 0.0) or 0.0)
    band = float(getattr(g, "rlwi", 0.0) or 0.0)
    margin_l = float(g.margin_l)
    band_right = min(floor + band, margin_l - 1.0) if floor > 0 else margin_l - 1.0
    label_x = max(floor, band_right - max(0.0, band - 1.0))
    return {
        "clip_side": recipe.clip_side,
        "row_indicators": bool(recipe.show_row_indicators),
        "clip_content_starts_mm": round(inset, 2),
        "clip_band_inner_edge_mm": round(clip_w, 2),
        "clip_text_lines": lines,
        "clip_text_overhang_mm": round(over, 2),
        "clip_text_reaches_mm": round(clip_w + over, 2),
        "row_label_floor_mm": round(floor, 2),
        "row_label_band_mm": round(band, 2),
        "row_label_ink_starts_mm": round(label_x, 2),
        "row_label_band_right_mm": round(band_right, 2),
        "patch_area_left_edge_mm": round(margin_l, 2),
        "hits_row_labels_by_mm": round(max(0.0, clip_w + over - label_x), 2),
        "hits_patch_area_by_mm": round(max(0.0, clip_w + over - margin_l), 2),
    }


def left_ink(before: Path, after: Path, recipe) -> dict:
    """What the clip text's ink lands on down the LEFT of the sheet.

    The control is the same chart with the clip TEXT blanked, so the geometry
    is identical and every changed pixel is that text's own ink.
    """
    import numpy as np
    a, dpi = _read_gray(before)
    b, _ = _read_gray(after)
    if a.shape != b.shape:
        return {"error": f"shape {a.shape} vs {b.shape}"}
    geo = left_side_map(recipe)
    mm = 25.4 / dpi
    changed = (a.astype(int) != b.astype(int))
    cols = np.flatnonzero(changed.any(axis=0))
    if not len(cols):
        return {**geo, "changed": False}
    lo_mm, hi_mm = float(cols.min()) * mm, float(cols.max()) * mm
    lx = int(round(geo["row_label_ink_starts_mm"] / mm))
    rx = int(round(geo["row_label_band_right_mm"] / mm))
    full = 65535 if a.dtype.itemsize == 2 else 255
    cut = int(0.6 * full)
    label_before = int((a[:, lx:rx] < cut).sum()) if rx > lx else 0
    label_after = int((b[:, lx:rx] < cut).sum()) if rx > lx else 0
    return {
        **geo,
        "changed": True,
        "clip_ink_from_paper_edge_mm": [round(lo_mm, 2), round(hi_mm, 2)],
        "row_label_window_px": [lx, rx],
        "label_ink_px_before": label_before,
        "label_ink_px_after": label_after,
        "label_ink_kept_frac": (round(label_after / label_before, 4)
                                if label_before else None),
        "clip_ink_in_label_window_px": (int(changed[:, lx:rx].sum())
                                        if rx > lx else 0),
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
                 measure_note: bool = False, measure_clip: bool = False,
                 measure_left: bool = False) -> dict:
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
            if measure_clip:
                # The SAME chart with the clip band's TEXT blanked, so every
                # pixel the two differ by is that text's own ink and can be
                # asked which patch it landed on.
                #
                # NOT `clip_content_mode: "off"`, which was the first control
                # and was wrong: a ColorMunki has no native clip border, so its
                # notes band exists only while clip content is ON. Switching
                # the mode off removed the band, the patch block slid 1 px, and
                # the diff then reported 346 of 374 patches "touched" by a
                # one-pixel edge. Blanking the text leaves the geometry alone.
                cur = panel.get_recipe().to_dict()
                panel.set_recipe(LayoutRecipe.from_dict(
                    {**cur, "clip_text": ""}))
                pump(app, 800)
                _ok0, tifs0 = build()
                if tifs0:
                    baseline = out / f"{tag}_{name}__baseline.tif"
                    shutil.copy(tifs0[0], baseline)
                panel.set_recipe(LayoutRecipe.from_dict(cur))
                pump(app, 800)
            st["build_finished"], tifs = build()
            st["tifs"] = [t.name for t in tifs]
            if tifs:
                shutil.copy(tifs[0], out / f"{tag}_{name}__sheet.tif")
                st["right_side"] = right_side_map(tifs[0])
                if baseline is not None and measure_note:
                    st["note"] = note_diff(baseline, tifs[0])
                if baseline is not None and measure_clip:
                    st["patches"] = patches_under_the_text(
                        baseline, tifs[0], panel.get_recipe())
                if measure_left:
                    st["left"] = (left_ink(baseline, tifs[0],
                                           panel.get_recipe())
                                  if baseline is not None
                                  else left_side_map(panel.get_recipe()))
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
        if st.get("left"):
            print("     LEFT SIDE: " + json.dumps(st["left"]))
        if st.get("patches"):
            print("     PATCHES UNDER THE TEXT: " + json.dumps(st["patches"]))
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

    # ---- F4: what the clip text does to the PATCHES it is printed over. ---
    #
    # Knut, 2026-09-12, correcting himself: *"The text on each of the 4 sides
    # shall NOT cross the text-edge distance limit on every side. If the patch
    # area with its margins are pushing against these limits, the text shall
    # overlap in the other direction, inward and over the edges of the patch
    # area instead."* So the band that cannot hold its lines prints them ON the
    # patches, and a patch with ink on it is still measured. This step names
    # which patches, and how much of each is covered.
    if want("f4"):
        state["notes"] = ""
        tab._manual_chart_notes_edit.setText("")
        tab._manual_stamp_cmd_check.setChecked(False)
        pump(app, 500)
        # THE MARGIN HAS TO BE AT THE BAND, or the overflow lands on clear
        # paper and no patch is touched. `instruments.geom_from_build_kwargs`
        # raises the clip-side margin to the band and never above it, so
        # margin == band is the ordinary clip chart; Knut's own run 1 has a
        # 24 mm band and a 24 mm right margin. A first pass ran these with the
        # margin at 32 mm and measured zero patches inked, which was true of
        # that sheet and not of the case his ruling is about.
        _long = "\n".join(["a line of clip text %d" % i for i in range(1, 9)])
        for band, margin, txt, tag2 in (
                (12.0, 12.0, None, ""), (16.0, 16.0, None, ""),
                (12.0, 32.0, None, ""),
                # The worst case the spin boxes allow: the narrowest band
                # (10 mm), the margin against it, and eight lines.
                (10.0, 10.0, _long, "_8lines")):
            _over = dict(clip_border_width_mm=band, margin_right=margin,
                         clip_text_size_mm=0.0)
            if txt is not None:
                _over["clip_text"] = txt
            apply(rec1, **_over)
            snapshot(f"f4_band{int(band)}_margin{int(margin)}{tag2}",
                     f"F4: clip band {band} mm, right margin {margin} mm",
                     generate=True, measure_clip=True)

    # ---- F5: the LEFT side, where the row labels are (Knut, 2026-09-12). ---
    #
    # *"If clip-border text starts overlapping with the row labels (if
    # enabled), the warning shall occur too, because the row labels are left of
    # the patch area edges and any clip-border text that does not have space
    # enough to fit between the clip text-edge distance setting and the patch
    # area left edge or the row labels to its left, will overflow and overlap
    # towards the row label or the left edge of the patch area (left margin).
    # This situation must be caught."*
    #
    # Run 2's recipe already puts the band on the LEFT. The row indicators are
    # switched on, and the band is narrowed until its text runs past it.
    if want("f5"):
        state["notes"] = ""
        tab._manual_chart_notes_edit.setText("")
        tab._manual_stamp_cmd_check.setChecked(False)
        pump(app, 500)
        _clip4 = "\n".join("clip text line %d" % i for i in range(1, 5))
        _clip8 = "\n".join("clip text line %d" % i for i in range(1, 9))
        # THE BAND MUST BE WIDER THAN THE PATCH BORDER or there is no band at
        # all: `instruments` stores `lbord = clip_border_width - border`, and
        # `geometry.clip_area_mm` returns None when `lbord <= 0`, so nothing is
        # drawn. Run 2's border is 10 mm, which is why the 10 mm case below
        # renders no clip text whatever and is kept: the panel warns about it
        # in red anyway.
        for band, rows, txt, tag2 in (
                (26.0, True, _clip4, "_fits"),
                (12.0, True, _clip4, "_rows_on"),
                (12.0, False, _clip4, "_rows_off"),
                (16.0, True, _clip8, "_deep"),
                (10.0, True, _clip8, "_noband")):
            apply(rec2, clip_side="left", clip_content_mode="text",
                  clip_text=txt, clip_border_width_mm=band,
                  clip_text_size_mm=0.0, show_row_indicators=rows,
                  margin_left=band)
            snapshot(f"f5_band{int(band)}{tag2}",
                     f"F5: LEFT band {band} mm, row indicators {rows}",
                     generate=True, measure_clip=True, measure_left=True)

    # ---- F6: the audit's two findings, on this edge. ---------------------
    #
    # 1. "Clip" is capped at a fifth of the band, so on a narrow band the ink
    #    comes closer to the paper edge than the box asks, while the message
    #    says the distance "is a limit and is never crossed".
    # 2. The panel predicts an overhang for the image and branding content
    #    modes; the renderer only produces one for plain text.
    if want("f6"):
        state["notes"] = ""
        tab._manual_chart_notes_edit.setText("")
        tab._manual_stamp_cmd_check.setChecked(False)
        pump(app, 500)
        _c4 = "\n".join("clip text line %d" % i for i in range(1, 5))
        for band in (40.0, 26.0, 16.0, 12.0):
            apply(rec2, clip_side="left", clip_content_mode="text",
                  clip_text=_c4, clip_border_width_mm=band,
                  clip_text_size_mm=0.0, show_row_indicators=False,
                  margin_left=band, text_edge_clip_mm=4.0)
            snapshot(f"f6_clipcap_band{int(band)}",
                     f"F6: Clip 4 mm on a {band} mm band, where does the ink go",
                     generate=True, measure_clip=True, measure_left=True)
        for mode in ("branding", "image"):
            apply(rec2, clip_side="left", clip_content_mode=mode,
                  clip_text=_c4, clip_border_width_mm=12.0,
                  clip_text_size_mm=0.0, show_row_indicators=False,
                  margin_left=12.0, text_edge_clip_mm=4.0)
            snapshot(f"f6_mode_{mode}",
                     f"F6: content mode {mode} on a 12 mm band",
                     generate=True, measure_clip=True, measure_left=True)

    res["steps"] = steps
    (out / f"{tag}_result.json").write_text(json.dumps(res, indent=1),
                                            encoding="utf-8")
    print(f"\nwrote {out / (tag + '_result.json')}")
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

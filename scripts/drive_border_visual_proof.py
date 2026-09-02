#!/usr/bin/env python3
"""Visual proof for the content-aware preview frame, at every point it touches.

The preview adds a white display frame (_BORDER) around the image. printtarg's
TIFFs put ink hard against the sheet edge, which is what the frame is for; a
ChromIQ layout-engine chart brings its own paper border and was getting both.
The frame is now only the shortfall — so these are the places where it could go
wrong, each photographed and, where a picture alone could lie, checked by number:

  1  printtarg chart      the frame must STAY
  2  engine chart         the frame must GO, paper edge = sheet edge
  3  measure overlay      the patch highlight must still land on its ink
  4  strip highlight      the stripe overlay uses the same geometry
  5  soft-proof           tinted frame stays, and zoom keeps its anchor

    python scripts/drive_border_visual_proof.py

"Before" is produced by the same code with the measurement forced to zero, so
the two halves differ in one number and nothing else.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import Qt                                   # noqa: E402
from PyQt6.QtGui import QColor, QFontDatabase                 # noqa: E402
from PyQt6.QtWidgets import QApplication                      # noqa: E402

from core.resource_path import resource_path                  # noqa: E402


def _printtarg_tif(sandbox: Path) -> "Path | None":
    """A real printtarg raster — the flush-to-the-edge case — or None."""
    import os
    import shutil
    import subprocess
    override = os.environ.get("CHROMIQ_PRINTTARG_TIF")
    if override and Path(override).is_file():
        return Path(override)
    binroot = Path(os.environ.get("CHROMIQ_ARGYLL_BIN", "/Applications/Argyll/bin"))
    targen, printtarg = binroot / "targen", binroot / "printtarg"
    if not (targen.is_file() and printtarg.is_file()):
        print("printtarg not found — its half of the proof is skipped")
        return None
    d = sandbox / "printtarg"
    d.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run([str(targen), "-d2", "-f60", "t"], cwd=d, check=True,
                       capture_output=True, timeout=120)
        subprocess.run([str(printtarg), "-iCM", "-pA4", "-t150", "t"], cwd=d,
                       check=True, capture_output=True, timeout=120)
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"printtarg raster could not be made ({exc}) — half the proof is skipped")
        return None
    _ = shutil
    tif = d / "t.tif"
    return tif if tif.is_file() else None


def pump(app, ms=600):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def build_chart(work: Path, name: str, mark: int, border: float) -> Path:
    """A real engine chart with ONE magenta patch, so the overlay can be judged
    by colour instead of by eye — the trick that caught a ring sitting on the
    wrong hexagon (2026-08-21)."""
    from workflow.layout_engine import chart as le_chart
    work.mkdir(parents=True, exist_ok=True)
    n = 120
    lines = ["CTI1", "", f'DESCRIPTOR "{name}"', 'ORIGINATOR "ChromIQ"',
             'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(n):
        r, g, b = (100.0, 0.0, 100.0) if i == mark else (78.0, 78.0, 78.0)
        lines.append(f"{i+1} {r} {g} {b} 40.0 45.0 50.0")
    lines += ["END_DATA", ""]
    ti1 = work / f"{name}.ti1"
    ti1.write_text("\n".join(lines), encoding="utf-8")
    stem = work / name
    le_chart.build_chart(ti1, stem, instrument="i1", paper="A4", pscale=1.0,
                         border=border, dpi=200, randomize=False)
    # THE WHOLE strips.json, not just the patches: the app reads `strips` and
    # `label_band_bottom_px` from here, and a sidecar carrying only patches
    # makes the scan arrow anchor to the top of the first patch instead of
    # hanging under the strip labels — which is what my first proof did, and
    # what Basti spotted in the screenshot.
    strips = json.loads(stem.with_suffix(".strips.json").read_text(encoding="utf-8"))
    layout = dict(strips)
    layout.update({"engine": "chromiq", "dpi": 200, "paper_mm": [210.0, 297.0]})
    (work / f"{name}.channels.json").write_text(json.dumps({
        "ink_channels": ["r", "g", "b"], "layout": layout}), encoding="utf-8")
    return stem


def shot(w, out: Path, name: str):
    w.grab().save(str(out / f"{name}.png"))
    return out / f"{name}.png"


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_borderproof_"))
    out = sandbox / "shots"
    out.mkdir()
    MARK = 40
    stem = build_chart(sandbox / "work", "EngineChart", MARK, border=6.0)

    from ui.tiff_preview import TiffPreview, _BORDER
    ok = True

    # ---- 1 & 2: the two chart sources, before and after -------------------
    # printtarg's own TIFF, made here rather than pointed at: a path under
    # /private/tmp is swept nightly, and a proof that quietly skips half its
    # cases is not a proof. $CHROMIQ_PRINTTARG_TIF overrides.
    printtarg = _printtarg_tif(sandbox)
    cases = [("engine", stem.with_suffix(".tif"))]
    if printtarg.is_file():
        cases.append(("printtarg", printtarg))
    for label, path in cases:
        for tag, force_zero in (("before", True), ("after", False)):
            w = TiffPreview()
            w.resize(680, 880)
            w.show()
            w.load_tiff([path])
            pump(app, 900)
            if force_zero:
                w._own_margin_frac = 0.0        # the old, unconditional frame
                w._repaint_label()
                pump(app, 400)
            shot(w, out, f"{tag}_{label}")
            print(f"{tag:6s} {label:10s} own_frac={w._own_margin_frac:.4f} "
                  f"border={w._paint_border}px")
            if not force_zero:
                # Asked of the widget, not hard-coded: the frame is the
                # SHORTFALL, so on a small window even the engine chart is owed
                # some. A literal 0 here passed at 680x880 and failed at 400x600.
                want = w._border_px(w._paint_geom[0] * min(w._pixmap.width(),
                                                           w._pixmap.height()))
                good = w._paint_border == want
                ok &= good
                print(f"       -> expected {want}px  {'OK' if good else 'WRONG'}")
            w.close()
            pump(app, 200)

    # ---- 3 & 4: the overlay must still land on its ink --------------------
    import numpy as np
    from PIL import Image
    page = np.asarray(Image.open(stem.with_suffix(".tif")).convert("RGB")).astype(int)
    strips = json.loads((sandbox / "work" / "EngineChart.channels.json").read_text(encoding="utf-8"))
    patches = strips["layout"]["patches"]

    boxes = {p["loc"]: p for p in patches if p.get("page", 0) == 0}
    # The magenta patch, found in the SHEET rather than trusted from the list.
    def is_magenta(px):
        r, g, b = px
        return r > 120 and b > 120 and g < 90
    target = None
    for loc, p in boxes.items():
        cx, cy = int(p["x"] + p["w"] / 2), int(p["y"] + p["h"] / 2)
        if is_magenta(page[cy, cx]):
            target = (loc, p)
            break
    if target is None:
        print("!! no magenta patch found on the sheet")
        return 2
    loc, p = target
    from PyQt6.QtCore import QPointF, QRect
    rect = QRect(int(p["x"]), int(p["y"]), int(p["w"]), int(p["h"]))
    # THE APP'S OWN STRIP GEOMETRY, through the app's own helper: the rect is
    # grown up to the label band so the arrow hangs beneath the labels, and the
    # helper decides the arrow mode. Building it from patch boxes instead put
    # the arrow inside the first patch.
    from ui.tabs.tab_measure import engine_strip_rects_from_sidecar
    sidecar = sandbox / "work" / "EngineChart.channels.json"
    engine = engine_strip_rects_from_sidecar(sidecar, 1)
    if engine is None:
        print("!! no engine strip geometry in the sidecar")
        return 2
    strip_rects, _counts, arrow_mode = engine
    strip_i = min(range(len(strip_rects[0])),
                  key=lambda i: abs(strip_rects[0][i].center().x() - (p["x"] + p["w"] / 2)))
    print(f"strips: {len(strip_rects[0])}, arrow_mode={arrow_mode!r}, "
          f"patch strip index {strip_i}")

    print()
    for tag, force_zero in (("before", True), ("after", False)):
        w = TiffPreview()
        w.resize(900, 1100)
        w.show()
        w.load_tiff([stem.with_suffix(".tif")])
        pump(app, 700)
        if force_zero:
            # The old, unconditional frame: silence the measurement rather than
            # zeroing the value, which a later refresh re-computes.
            w._measure_own_margin = lambda *a, **k: None
            w._own_margin_frac = 0.0
            w._repaint_label()
        w.set_page_patch_boxes({0: [rect]})
        w.highlight_patch(0, rect)
        pump(app, 800)
        shot(w, out, f"{tag}_overlay_patch")

        # Judged by NUMBER as well: the patch centre, pushed through the same
        # _paint_geom the overlay uses, must come back as the same pixel.
        scale, ox, oy = w._paint_geom
        cx_img, cy_img = p["x"] + p["w"] / 2, p["y"] + p["h"] / 2
        lx, ly = cx_img * scale + ox, cy_img * scale + oy
        back = w._image_px_at(QPointF(lx, ly))
        good = (back is not None and abs(back[0] - cx_img) <= 2
                and abs(back[1] - cy_img) <= 2)
        ok &= good
        print(f"{tag:6s} overlay border={w._paint_border:2d}px  patch {loc} "
              f"{int(cx_img)},{int(cy_img)} -> label {lx:.1f},{ly:.1f} -> "
              f"back {back}  {'OK' if good else 'WRONG'}")

        # The patch ring and the strip highlight are different modes — spot
        # reading versus strip reading — and the app never lights both. Clear
        # it before the strip shot; leaving it on was the second fault Basti
        # saw in the first proof.
        w.highlight_patch(0, None)
        w.set_stripe_rects(strip_rects[0], arrow_mode)
        w.highlight_stripe(strip_i)
        pump(app, 700)
        shot(w, out, f"{tag}_overlay_stripe")
        w.close()
        pump(app, 200)

    # ---- 5: soft-proof keeps its tinted frame ----------------------------
    w = TiffPreview()
    w.resize(680, 880)
    w._interactive = True
    w.show()
    w.load_tiff([stem.with_suffix(".tif")])
    w.set_frame_color(QColor(236, 228, 209))       # a warm paper white
    pump(app, 900)
    shot(w, out, "softproof_frame")
    kept = w._paint_border
    print(f"\nsoft-proof tinted frame border={kept}px  "
          f"{'OK' if kept == _BORDER else 'WRONG — the paper simulation lost its frame'}")
    ok &= kept == _BORDER
    w._apply_zoom(2.0)
    pump(app, 600)
    shot(w, out, "softproof_zoomed")
    print(f"soft-proof zoomed border={w._paint_border}px")
    w.close()

    print(f"\nshots: {out}")
    print("VERDICT:", "as designed" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

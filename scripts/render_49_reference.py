#!/usr/bin/env python3
"""Render one FIXED TiffPreview scene to a PNG, so the same scene can be
rendered from two commits and diffed. Imports only ui.tiff_preview, so it runs
unchanged inside a git worktree of an older commit.

    python scripts/render_49_reference.py <out.png> <chart.ti2> [--no-strips]
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRect, Qt          # noqa: E402
from PyQt6.QtGui import QColor              # noqa: E402
from PyQt6.QtWidgets import QApplication    # noqa: E402


def main() -> int:
    out = Path(sys.argv[1])
    ti2 = Path(sys.argv[2])
    no_strips = "--no-strips" in sys.argv
    app = QApplication.instance() or QApplication(sys.argv[:1])
    from ui.tiff_preview import TiffPreview
    lay = json.loads(ti2.with_suffix(".channels.json").read_text())["layout"]
    tif = sorted(ti2.parent.glob(f"{ti2.stem}*.tif"))
    pv = TiffPreview()
    w, h = 900, 900
    if "--size" in sys.argv:
        w, h = (int(v) for v in sys.argv[sys.argv.index("--size") + 1].split("x"))
    pv.resize(w, h)
    pv.load_tiff([tif[0]])
    app.processEvents()
    pats = [p for p in lay["patches"] if p.get("page", 0) == 0]
    items = []
    for i, p in enumerate(pats):
        box = QRect(int(p["x"]), int(p["y"]), int(p["w"]), int(p["h"]))
        e = QColor((i * 37) % 256, (i * 91) % 256, (i * 53) % 256)
        m = QColor((i * 53) % 256, (i * 37) % 256, (i * 91) % 256)
        items.append((box, e, m, i % 97 == 0))
    pv.set_patch_overlay(0, items, replace_page=True)
    if not no_strips:
        strips = [s for s in (lay.get("strips") or []) if int(s["page"]) == 0]
        pv.set_stripe_rects([QRect(int(s["x"]), int(s["y"]),
                                   int(s["w"]), int(s["h"])) for s in strips])
    if "--rich" in sys.argv:
        # every other overlay that shares this canvas, all on at once
        boxes = [QRect(int(x["x"]), int(x["y"]), int(x["w"]), int(x["h"]))
                 for x in pats]
        pv.set_page_patch_boxes({0: boxes})
        pv.set_edge_spacer_px(6)
        pv.set_bidirectional(True)
        pv.highlight_stripe(3)
        pv.set_stripe_click_enabled(True)
        pv._hover_stripe = 5
        locs = {str(x.get("loc", i)): QRect(
            int(x["x"]), int(x["y"]), int(x["w"]), int(x["h"]))
            for i, x in enumerate(pats)}
        pv.set_patch_click_enabled(True, [locs])
        pv._hover_patch_loc = list(locs)[40]
        pv._active_patch_box = boxes[80]
        pv._active_patch_page = 0
        if hasattr(pv, "set_aim_overlay") and "--no-aim" not in sys.argv:
            pv.set_aim_overlay(True, aperture_px=47.0, body_px=390.0)
        pv.set_show_only_measured(True)
        pv.set_stripe_read_map({i: (i % 3 == 0) for i in range(24)})
    if "--mode" in sys.argv:
        pv.set_overlay_mode(sys.argv[sys.argv.index("--mode") + 1])
    pv.show()
    for _ in range(40):
        app.processEvents()
    pv._repaint_label()
    for _ in range(20):
        app.processEvents()
    pv._img_label.grab().save(str(out))
    print(f"{out}  legend_rect={pv._legend_rect} "
          f"stripe_rects={len(pv._stripe_rects)} items={len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

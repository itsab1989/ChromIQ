#!/usr/bin/env python3
"""What "the normal distance between two lines" is, from the renderer's font.

Three candidate answers at each size, so the report does not have to pick one
on a hunch:

* the renderer's own stacking pitch, ``1.2 * size`` (`raster._vtext` line_h and
  `text_edge_fit.CLIP_LINE_SPACING`);
* the font's own default line spacing (ascent + descent, PIL/FreeType);
* the ink height of a line of the clip text at that size.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DPI = 200.0
SAMPLE = "Top margin: 34 mm to avoid knobs underneath"


def main() -> int:
    from PIL import Image, ImageDraw
    from workflow import text_edge_fit as tef
    from workflow.layout_engine import raster

    d = ImageDraw.Draw(Image.new("L", (8, 8)))
    print(f"{'pt':>6} {'1.2em mm':>9} {'font mm':>9} {'ink mm':>8} "
          f"{'note ink mm':>12}")
    for pt in (7.0, 8.0, 10.0, 12.0, 14.0):
        px = tef.pt_to_px(pt, DPI)
        f = raster._font(px, "Inter")
        asc, desc = f.getmetrics()
        bbox = d.textbbox((0, 0), SAMPLE, font=f)
        ink = bbox[3] - bbox[1]
        print(f"{pt:6.1f} {tef.CLIP_LINE_SPACING * tef.pt_to_mm(pt):9.3f} "
              f"{(asc + desc) * 25.4 / DPI:9.3f} {ink * 25.4 / DPI:8.3f} "
              f"{'':>12}")
    # And the note, which is drawn by the stamper's own picker, at its floor.
    from workflow import tiff_metadata as tm
    for pt in (0.0, 12.0):
        px = tef.pt_to_px(tef.text_floor_pt(pt), DPI)
        f = tm._pick_font(px, "Inter")
        bbox = d.textbbox((0, 0), "Canon PRO-1000 / Photo Rag 308", font=f)
        print(f"note at {'auto' if not pt else f'{pt:.0f} pt'}: font {px} px, "
              f"ink {(bbox[3] - bbox[1]) * 25.4 / DPI:.3f} mm thick")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

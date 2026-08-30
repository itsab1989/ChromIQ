#!/usr/bin/env python3
"""Render Basti's area-first CR30 hex chart at a range of LEFT margins and crop
the left edge, so the clamped row numbers can be looked at.

    python scripts/probe_50_row_numbers.py <out_dir> <chart.ti1>
"""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image                                        # noqa: E402
from workflow.layout_engine import chart, geometry, instruments, papers  # noqa: E402

BASE = dict(instrument="CR30", paper="A4", hflag=True, dpi=300,
            spacer_on=False, spacer_mode="none", layout_mode="area_first",
            area_method="by_grid", area_cols=26, area_rows=44, area_ratio=1.0,
            nolimit=True, randomize=True)


def main() -> int:
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    ti1 = Path(sys.argv[2])
    tiles = []
    for L in (0.0, 1.0, 2.0, 2.5, 3.0, 4.0):
        kw = {**BASE, "margins": (6.0, 2.0, 1.0, L), "border": L}
        g = instruments.geom_from_build_kwargs(kw, thresholds=None)
        pw, ph = papers.dimensions_mm("A4")
        lay = geometry.compute(g, pw, ph, 1144)
        pl = geometry.placement(g, pw, ph, lay)
        res = chart.build_chart(ti1, out / f"rows_L{L:g}", seed=999, **kw)
        tif = Path(res.tiff_paths[0])
        im = Image.open(tif).convert("RGB")
        dpi = 300.0
        px = lambda mm: int(round(mm * dpi / 25.4))
        # a tall slice of the left edge: 0 .. x0 + 3 patch widths
        w = px(pl.x0 + 3 * pl.pwid)
        top = px(pl.y0_first - 2)
        h = px(6 * pl.plen)
        crop = im.crop((0, max(0, top), min(im.width, w),
                        min(im.height, max(0, top) + h)))
        sc = 3
        crop = crop.resize((crop.width * sc, crop.height * sc), Image.NEAREST)
        crop.save(out / f"rownum_L{L:g}.png")
        print(f"L={L:5.1f} mm  x0={pl.x0:7.3f} mm  pwid={pl.pwid:6.3f}  "
              f"rlwi={g.rlwi}  n/page={lay.patches_per_page}  "
              f"crop {crop.width}x{crop.height} -> rownum_L{L:g}.png")
        tiles.append((L, crop))
    # one contact sheet
    W = max(t[1].width for t in tiles)
    H = sum(t[1].height for t in tiles) + 12 * len(tiles)
    sheet = Image.new("RGB", (W, H), (30, 30, 30))
    y = 0
    for L, c in tiles:
        sheet.paste(c, (0, y)); y += c.height + 12
    sheet.save(out / "rownum_contact_sheet.png")
    print("contact sheet -> rownum_contact_sheet.png (L = 0, 1, 3, 5, 7.5, 12 mm, top to bottom)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

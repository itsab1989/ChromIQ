#!/usr/bin/env python3
"""Count the chart left showing inside a column the user was told is hidden.

Reads the photographs `scripts/drive_b21_show_only_measured.py` takes. The page
carries colour only in the patches, so inside an UNREAD strip every coloured
pixel is a piece of chart that "Show only measured patches" promised to blank
and did not.

The strip's place on screen is computed from the IMAGE's own grid (the page is
scaled to `canvas - 2*border` and drawn at the border), which is deliberately
not the arithmetic under test.

    python scripts/analyse_b21_show_only_measured.py [proof-folder]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image

OUT = Path.home() / "Desktop" / "ChromIQ-beta21-proof" / "show-only-measured"
PATCH = (255, 0, 255)


def tinted(p, tol=20):
    return max(p) - min(p) > tol and p[1] < p[0] - 15 and p[1] < p[2] - 15


def one(folder: Path) -> "tuple[int, int]":
    if not (folder / "blanked.png").is_file():
        # A refused capture is reported, never counted as a clean result.
        return -3, -3
    g = json.loads((folder / "facts.json").read_text(encoding="utf-8"))
    im = Image.open(folder / "blanked.png").convert("RGB")
    px = im.load()
    W, H = im.size
    read = {int(k): v for k, v in g["read_map"].items()}
    # The page's device rect, found from the photograph: the colour that is
    # left belongs to READ strips, so its bounding box plus the chart's own
    # grid gives the mapping without using the widget's numbers.
    xs = [x for x in range(W) for y in range(0, H, 3) if tinted(px[x, y])]
    ys = [y for y in range(H) for x in range(0, W, 3) if tinted(px[x, y])]
    if not xs or not ys:
        # No colour anywhere: every strip was blanked, read ones included, or
        # the page never painted. Either is a finding, not a zero.
        return -2, -2
    boxes = [tuple(b) for b in g["boxes"]]
    strips = [tuple(s) for s in g["strips"]]
    # image px -> photograph px, fitted from the read strips' own extent
    read_boxes = [b for i, b in enumerate(boxes)
                  if any(read.get(k) and s[0] <= b[0] + b[2] / 2 <= s[0] + s[2]
                         for k, s in enumerate(strips))]
    if not read_boxes:
        return -1, -1
    ix0 = min(b[0] for b in read_boxes)
    ix1 = max(b[0] + b[2] for b in read_boxes)
    iy0 = min(b[1] for b in read_boxes)
    iy1 = max(b[1] + b[3] for b in read_boxes)
    sx = (max(xs) + 1 - min(xs)) / (ix1 - ix0)
    sy = (max(ys) + 1 - min(ys)) / (iy1 - iy0)
    ox = min(xs) - ix0 * sx
    oy = min(ys) - iy0 * sy

    leaked = 0
    for k, s in enumerate(strips):
        if read.get(k):
            continue
        for b in boxes:
            if not (s[0] <= b[0] + b[2] / 2 <= s[0] + s[2]):
                continue
            x0 = math.ceil(b[0] * sx + ox)
            x1 = math.floor((b[0] + b[2]) * sx + ox)
            y0 = math.ceil(b[1] * sy + oy)
            y1 = math.floor((b[1] + b[3]) * sy + oy)
            for y in range(max(0, y0), min(H, y1)):
                for x in range(max(0, x0), min(W, x1)):
                    if tinted(px[x, y]):
                        leaked += 1
    return leaked, len(strips)


def main(root: Path) -> int:
    total = 0
    for chart in sorted(p for p in root.iterdir() if p.is_dir()):
        for size in sorted(p for p in chart.iterdir() if p.is_dir()):
            n, strips = one(size)
            note = {-3: "NO PHOTOGRAPH (capture refused)",
                    -2: "no chart colour anywhere",
                    -1: "no read strip to fit the mapping from"}.get(n)
            total += max(0, n)
            print(f"{chart.name:<16}{size.name:>10}  "
                  + (note or f"chart pixels left inside an UNREAD strip: {n}"))
    print(f"\nTOTAL {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT))

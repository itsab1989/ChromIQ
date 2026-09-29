#!/usr/bin/env python3
"""Basti's detector: with a monochrome chart and a grey overlay, colour = leak.

The driver photographs a page whose ONLY colour is in the patches, with the
split drawn in two greys. So there is nothing to model and nothing to classify:
every saturated pixel left inside the patch grid is a piece of chart the
overlay was supposed to cover and did not.

Writes a leak map beside each photograph, with the leaked pixels marked, so the
result can be looked at as well as counted.

    python scripts/analyse_b21_mono_leak.py <proof-folder> [more folders...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image


PATCH_COLOURS = ((255, 0, 255), (0, 255, 255))


def saturated(p, thr=60):
    return max(p) - min(p) > thr


def untouched(p, tol=36):
    """Pure patch colour: the overlay did not reach this pixel at all.

    A pixel that is PART chart and part overlay is the antialiased edge of the
    split and is not a leak -- it is what a hard edge on a fractional boundary
    looks like. Only a pixel the overlay never touched counts.
    """
    return any(max(abs(p[i] - c[i]) for i in range(3)) <= tol
               for c in PATCH_COLOURS)


def one(folder: Path) -> tuple[int, int, int]:
    g = json.loads((folder / "geometry.json").read_text(encoding="utf-8"))
    off, on = (folder / n for n in g["mono_shots"])
    A = Image.open(off).convert("RGB")
    Bi = Image.open(on).convert("RGB")
    a, b = A.load(), Bi.load()
    W, H = A.size
    xs = [x for x in range(W) for y in range(0, H, 4) if saturated(a[x, y])]
    ys = [y for y in range(H) for x in range(0, W, 4) if saturated(a[x, y])]
    if not xs or not ys:
        print(f"{folder.name}: no colour in the overlay-off photograph")
        return 0, 0, 0
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    leaks = [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)
             if untouched(b[x, y])]
    rows = len({y for _, y in leaks})
    if leaks:
        m = Bi.copy()
        mp = m.load()
        for x, y in leaks:
            mp[x, y] = (255, 0, 0)
        m.save(folder / "C-leak-map.png")
    print(f"{folder.name:>12}  grid {x1 - x0 + 1}x{y1 - y0 + 1} px  "
          f"coloured pixels left under the overlay: {len(leaks):>6}  "
          f"on {rows} rows")
    return len(leaks), rows, (x1 - x0 + 1) * (y1 - y0 + 1)


def main(roots) -> int:
    for root in roots:
        root = Path(root)
        folders = sorted(p for p in root.iterdir()
                         if p.is_dir() and (p / "geometry.json").is_file())
        print(f"\n== {root.name}")
        tot = 0
        for f in folders:
            tot += one(f)[0]
        print(f"   TOTAL coloured pixels left showing: {tot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["."]))

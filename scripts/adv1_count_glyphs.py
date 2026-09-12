#!/usr/bin/env python3
"""Count the glyphs actually printed in a band, off the sheet the app wrote.

Used to prove that a clip-border line longer than the page is CUT rather than
shrunk: the text is a run of identical "X" characters, so the number of ink
runs along the strip is the number of characters that reached paper.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import tifffile


def read(path: Path):
    with tifffile.TiffFile(str(path)) as tf:
        page = tf.pages[0]
        arr = np.array(page.asarray())
        try:
            xres = page.tags["XResolution"].value
            dpi = float(xres[0]) / float(xres[1])
            if int(page.tags["ResolutionUnit"].value) == 3:
                dpi *= 2.54
        except Exception:
            dpi = 200.0
    return (arr.min(axis=2) if arr.ndim == 3 else arr), dpi


def main() -> int:
    ctrl, dpi = read(Path(sys.argv[1]))
    sheet, _ = read(Path(sys.argv[2]))
    d = (ctrl.astype(np.int32) - sheet.astype(np.int32)) > 8
    ys, xs = np.where(d)
    if not len(ys):
        print("no difference")
        return 1
    x0, x1 = int(xs.min()), int(xs.max())
    band = d[:, x0:x1 + 1]
    rows = band.any(axis=1)                       # inked rows down the strip
    runs = 0
    prev = False
    for v in rows:
        if v and not prev:
            runs += 1
        prev = bool(v)
    H = d.shape[0]
    print(f"dpi={dpi:g} band x {x0}..{x1}  ink rows {int(ys.min())}..{int(ys.max())}"
          f"  page height {H} px")
    print(f"glyph runs along the strip: {runs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

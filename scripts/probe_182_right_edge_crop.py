#!/usr/bin/env python3
"""Crop the right-hand band of a chart TIFF to a PNG so it can be LOOKED at.

Usage: probe_182_right_edge_crop.py <tif> <out.png> [mm_from_right] [rows]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image


def main() -> int:
    tif = Path(sys.argv[1])
    out = Path(sys.argv[2])
    mm = float(sys.argv[3]) if len(sys.argv) > 3 else 34.0
    rows = int(sys.argv[4]) if len(sys.argv) > 4 else 1400
    dpi = float(sys.argv[5]) if len(sys.argv) > 5 else 200.0
    arr = tifffile.imread(str(tif))
    px = int(round(mm * dpi / 25.4))
    h = arr.shape[0]
    y0 = max(0, h // 2 - rows // 2)
    crop = arr[y0:y0 + rows, arr.shape[1] - px:, ...]
    if crop.ndim == 3 and crop.shape[2] > 3:
        crop = crop[:, :, :3]
    img = Image.fromarray(np.asarray(crop))
    img = img.rotate(-90, expand=True)     # read it the way the strip reads
    img.save(out)
    print(f"{out}  {img.size[0]}x{img.size[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Which column `_detect_writable_band` believes the patch area ends at.

It calls the stamper's own threshold (`_PATCH_COL_DENSITY_THRESHOLD`) on the
page the app wrote, and prints the rightmost column that passes it, in
millimetres from the right page edge, beside where the patch block really ends.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import tifffile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from workflow import tiff_metadata as tm
    dpi = 200.0
    for name in sys.argv[1:]:
        p = Path(name)
        arr = tifffile.imread(str(p))
        if arr.ndim == 2:
            arr = arr[..., None]
        H, W = arr.shape[:2]
        max_val = np.iinfo(arr.dtype).max
        cut = int(max_val * 240 / 255)
        mask = (arr < cut).any(axis=2)
        dens = mask.sum(axis=0) / max(1, H)
        cols = np.where(dens >= tm._PATCH_COL_DENSITY_THRESHOLD)[0]
        last = int(cols[-1]) if len(cols) else -1
        print(f"{p.name}")
        print(f"   rightmost column at or over the "
              f"{tm._PATCH_COL_DENSITY_THRESHOLD} density threshold: x={last} "
              f"= {(W - 1 - last) * 25.4 / dpi:.3f} mm from the right edge "
              f"(density {dens[last]:.3f})")
        # the same, restricted to columns that are unambiguously patches
        band = tm._detect_writable_band(
            arr, keep_out_px=int(round(23.944 * dpi / 25.4)),
            pad_px=tm._safety_pad_px(dpi))
        if band:
            print(f"   _detect_writable_band -> {band} = "
                  f"{(W - 1 - band[0]) * 25.4 / dpi:.3f} .. "
                  f"{(W - 1 - band[1]) * 25.4 / dpi:.3f} mm from the right edge")
        else:
            print("   _detect_writable_band -> None")
        # the five densest columns in the right 40 mm, for the record
        lim = int(round(40 * dpi / 25.4))
        sub = [(float(dens[x]), (W - 1 - x) * 25.4 / dpi)
               for x in range(W - lim, W)]
        sub.sort(reverse=True)
        print("   densest columns in the right 40 mm: "
              + ", ".join(f"{d:.2f}@{mm:.2f}mm" for d, mm in sub[:6]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

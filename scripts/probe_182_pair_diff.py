#!/usr/bin/env python3
"""How two chart pages differ, column by column. Used to check that a
control/variant pair really differs by one thing only."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import tifffile

DPI = 200.0


def main() -> int:
    a = tifffile.imread(sys.argv[1])
    b = tifffile.imread(sys.argv[2])
    print(Path(sys.argv[1]).name, a.shape, "vs", Path(sys.argv[2]).name, b.shape)
    if a.shape != b.shape:
        return 1
    fa = a.min(axis=2) if a.ndim == 3 else a
    fb = b.min(axis=2) if b.ndim == 3 else b
    ch = fa.astype(int) != fb.astype(int)
    w = ch.shape[1]
    cols = np.nonzero(ch.any(axis=0))[0]
    print(f"  changed pixels: {int(ch.sum())} in {cols.size} columns")
    if cols.size:
        print(f"  changed columns span {(w - 1 - int(cols[-1])) * 25.4 / DPI:.2f}"
              f" .. {(w - 1 - int(cols[0])) * 25.4 / DPI:.2f} mm from the right")
        # contiguous runs of changed columns
        runs, start, prev = [], int(cols[0]), int(cols[0])
        for c in cols[1:]:
            c = int(c)
            if c != prev + 1:
                runs.append((start, prev))
                start = c
            prev = c
        runs.append((start, prev))
        for lo, hi in runs[-12:]:
            print(f"    run {(w - 1 - hi) * 25.4 / DPI:8.3f} .. "
                  f"{(w - 1 - lo) * 25.4 / DPI:8.3f} mm   "
                  f"changed={int(ch[:, lo:hi + 1].sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

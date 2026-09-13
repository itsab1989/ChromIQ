#!/usr/bin/env python3
"""What the chart note would look like if the band detector saw the real gap.

A MEASUREMENT, not a fix: `tiff_metadata._detect_writable_band` is replaced for
the length of one call with a function that returns the white run the sheet
actually has between the patch block and the clip text's reach, and the app's
own `_stamp_one` is then run on the control page with the app's own arguments.
The ink is measured before and after, so the cost of the detector's answer can
be read in millimetres instead of argued about.

Run after `probe_182_note_gap_internals.py`.
"""
from __future__ import annotations

import json
import logging
import shutil
import sys
from pathlib import Path

import numpy as np
import tifffile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = Path.home() / "Desktop" / "chromiq-182-right-edge"
DPI = 200.0


def ink_cols(path: Path, thresh: int = 250):
    arr = tifffile.imread(str(path))
    flat = arr.min(axis=2) if arr.ndim == 3 else arr
    lim = int(thresh * 257) if flat.dtype == np.uint16 else thresh
    ink = flat < lim
    counts = ink.sum(axis=0)
    w = ink.shape[1]
    out = []
    x = w - 1
    while x >= 0:
        if counts[x] > 0:
            end = x
            while x >= 0 and counts[x] > 0:
                x -= 1
            out.append((round((w - 1 - end) * 25.4 / DPI, 3),
                        round((w - 1 - x - 1) * 25.4 / DPI, 3)))
        else:
            x -= 1
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="LOG %(levelname)s %(name)s: %(message)s")
    from workflow import tiff_metadata as tm

    d = json.loads((OUT / "k1-k5.json").read_text(encoding="utf-8"))
    rows = []
    for st in d["k5"]["states"]:
        if not st["with_note"]:
            continue
        tag = st["tag"]
        ctrl = OUT / f"k5-{tag.rsplit('-note', 1)[0]}-control-page1.tif"
        call = st["stamp_calls"][0]
        args = [eval(a) for a in call["args"]]
        reach_mm = float(args[4])
        gap_mm = float(args[5])

        arr = tifffile.imread(str(ctrl))
        H, W = arr.shape[:2]
        keep_px = int(round(reach_mm * DPI / 25.4))
        # Where the PATCH BLOCK really ends: the rightmost column whose ink
        # runs the height of the sheet, taken outside the clip band so the
        # user's own lines cannot be mistaken for it.
        mask = (arr < 240).any(axis=2) if arr.ndim == 3 else arr < 240
        dens = mask.sum(axis=0) / H
        limit = W - keep_px - 1
        cols = [x for x in range(0, limit) if dens[x] >= 0.30]
        patch_right = (cols[-1] if cols else 0) + 4
        true_band = (patch_right, W - keep_px - 4)

        work = OUT / f"whatif-{tag}.tif"
        shutil.copy2(ctrl, work)
        orig = tm._detect_writable_band
        tm._detect_writable_band = lambda *a, **k: true_band
        try:
            tm._stamp_one(work, call["text"], *args)
        finally:
            tm._detect_writable_band = orig

        got = ink_cols(work)
        note = [g for g in got if reach_mm - 1.0 < g[0] < reach_mm + 12.0]
        real = ink_cols(OUT / f"k5-{tag}-page1.tif")
        real_note = [g for g in real if reach_mm - 1.0 < g[0] < reach_mm + 12.0]
        row = {
            "tag": tag, "reach_mm": reach_mm, "gap_mm": gap_mm,
            "band_the_app_used_mm_from_right": [3.429, 0.254],
            "band_the_sheet_has_mm_from_right": [
                round((W - 1 - true_band[0]) * 25.4 / DPI, 3),
                round((W - 1 - true_band[1]) * 25.4 / DPI, 3)],
            "note_ink_as_shipped": real_note,
            "note_ink_with_the_true_band": note,
        }
        rows.append(row)
        print("=" * 74)
        print(tag)
        print(f"   reach {reach_mm} mm, leading passed in {gap_mm} mm")
        print(f"   band as shipped : 3.429 .. 0.254 mm from the right edge")
        print(f"   band the sheet has: {row['band_the_sheet_has_mm_from_right']}")
        print(f"   note ink as shipped      : {real_note}")
        print(f"   note ink with the true band: {note}")
    (OUT / "note-gap-whatif.json").write_text(
        json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n   wrote {OUT / 'note-gap-whatif.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

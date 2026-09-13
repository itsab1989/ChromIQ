#!/usr/bin/env python3
"""Where `tiff_metadata._stamp_one` actually puts the chart note, and why.

Run AFTER `scripts/drive_182_right_edge_k1_k5.py --phase k5`. It takes the
CONTROL page that run wrote (the same sheet without the note), calls the app's
OWN `_stamp_one` on a copy of it with the app's OWN arguments (recorded by the
driver's spy), and reads the function's own local variables out of its frame
with `sys.settrace` -- so `band_left`, `strip_w`, `x0` and `_overlaps` are the
stamper's numbers, not a re-derivation of them.

The reproduction is then CHECKED against the app's real note page: the ink
columns must match, or nothing here may be believed.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import tifffile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = Path.home() / "Desktop" / "chromiq-182-right-edge"
WANT = ("band_left", "band_right", "strip_w", "strip_h", "x0", "y0",
        "_right_limit", "_gap_px", "_pack", "_overlaps", "_pad", "_pad_t",
        "_pad_b", "_keep_out_mm", "_floor_px", "W", "H", "_dpi")


def ink_cols(path: Path, dpi=200.0, thresh=250):
    arr = tifffile.imread(str(path))
    flat = arr.min(axis=2) if arr.ndim == 3 else arr
    lim = int(thresh * 257) if flat.dtype == np.uint16 else thresh
    ink = flat < lim
    counts = ink.sum(axis=0)
    w = ink.shape[1]
    groups = []
    x = w - 1
    while x >= 0:
        if counts[x] > 0:
            end = x
            while x >= 0 and counts[x] > 0:
                x -= 1
            start = x + 1
            groups.append((round((w - 1 - end) * 25.4 / dpi, 3),
                           round((w - 1 - start) * 25.4 / dpi, 3),
                           int(ink[:, start:end + 1].sum())))
        else:
            x -= 1
    return groups


def main() -> int:
    from workflow import tiff_metadata as tm

    d = json.loads((OUT / "k1-k5.json").read_text(encoding="utf-8"))
    states = {s["tag"]: s for s in d["k5"]["states"]}
    rows = []
    for tag, st in states.items():
        if not st["with_note"]:
            continue
        base = tag.rsplit("-note", 1)[0] + "-control"
        ctrl = OUT / f"k5-{base}-page1.tif"
        real = OUT / f"k5-{tag}-page1.tif"
        if not ctrl.is_file():
            print(f"    no control for {tag}")
            continue
        call = st["stamp_calls"][0]
        args = [eval(a) for a in call["args"]]        # the app's own arguments
        work = OUT / f"repro-{tag}.tif"
        shutil.copy2(ctrl, work)

        grabbed: dict = {}

        def tracer(frame, event, arg):
            if frame.f_code is tm._stamp_one.__code__:
                if event == "call":
                    return tracer
                if event == "line":
                    for k in WANT:
                        if k in frame.f_locals:
                            v = frame.f_locals[k]
                            grabbed[k] = v if isinstance(
                                v, (int, float, bool, str)) else repr(v)
            return None

        sys.settrace(tracer)
        try:
            tm._stamp_one(work, call["text"], *args)
        finally:
            sys.settrace(None)

        dpi = float(grabbed.get("_dpi") or 200.0)
        W = int(grabbed.get("W") or 0)

        def mm_from_right(x):
            return round((W - 1 - x) * 25.4 / dpi, 3)

        got = ink_cols(work, dpi)
        want = ink_cols(real, dpi)
        rows.append({
            "tag": tag, "args": call["args"], "locals": dict(grabbed),
            "band_mm_from_right": [mm_from_right(grabbed.get("band_left", 0)),
                                   mm_from_right(grabbed.get("band_right", 0))],
            "x0_mm_from_right": mm_from_right(grabbed.get("x0", 0)),
            "strip_mm": round(float(grabbed.get("strip_w", 0)) * 25.4 / dpi, 3),
            "right_limit_mm_from_right": mm_from_right(
                grabbed.get("_right_limit", 0)),
            "gap_px": grabbed.get("_gap_px"),
            "gap_mm": round(float(grabbed.get("_gap_px", 0)) * 25.4 / dpi, 3),
            "reproduction_matches_the_app": got == want,
        })
        print("=" * 74)
        print(tag, "  reproduction matches the app's page:", got == want)
        print("  args (text_edge, band, font, size_pt, clip_reach, gap_mm, "
              "edge_t, edge_b):", call["args"])
        for k in WANT:
            if k in grabbed:
                print(f"    {k:>18} = {grabbed[k]}")
        print(f"    band  mm from right edge: "
              f"{mm_from_right(grabbed.get('band_left', 0))} .. "
              f"{mm_from_right(grabbed.get('band_right', 0))}")
        print(f"    _right_limit mm from right edge: "
              f"{mm_from_right(grabbed.get('_right_limit', 0))}")
        print(f"    x0 (patch side of the strip) mm from right edge: "
              f"{mm_from_right(grabbed.get('x0', 0))}")
        print(f"    the note's ink, app page : "
              f"{[g for g in want if g[0] > 20][:3]}")
        print(f"    the note's ink, this repro: "
              f"{[g for g in got if g[0] > 20][:3]}")
    (OUT / "note-gap-internals.json").write_text(
        json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n    wrote {OUT / 'note-gap-internals.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

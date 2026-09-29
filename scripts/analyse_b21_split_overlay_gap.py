#!/usr/bin/env python3
"""Measure the split overlay against the chart image it is drawn on.

For each window size photographed by `scripts/drive_b21_split_overlay_gap.py`:

  * the box the overlay PAINTED is walked out of the photographs, from the
    patch's centre, using the patch's own marker pair (neighbours carry the
    other pair, so a walk stops at the real edge);
  * the box the CHART occupies is computed from the drawn image's own grid:
    Qt scales the page pixmap to `canvas - 2*border` device pixels and draws it
    at the border, so source row `y` lands at `y * scaled_h / page_h`. That is
    not the overlay's arithmetic, which is the point.

A FULL chart row (or column) inside the patch that carries no overlay is a
leak: the thin line the tester photographed. The diagonal of every patch is
then traced and the rows where it fails to advance are counted.

    python scripts/analyse_b21_split_overlay_gap.py [proof-folder]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image

OUT = Path.home() / "Desktop" / "ChromIQ-beta21-proof" / "split-overlay-gap"


def dist(p, q):
    return max(abs(int(p[i]) - int(q[i])) for i in range(3))


def near_pair(px, pair, tol=48):
    return min(dist(px, pair[0]), dist(px, pair[1])) <= tol


def analyse_one(folder: Path) -> dict:
    """Chart pixels the overlay never touched, inside patches it was given."""
    g = json.loads((folder / "geometry.json").read_text(encoding="utf-8"))
    A = Image.open(folder / "A-no-overlay.png").convert("RGB")
    a = A.load()
    W, H = A.size
    b = [Image.open(folder / n).convert("RGB").load() for n in g["shots"]]
    boxes = {k: tuple(v) for k, v in g["boxes"].items()}

    dpr = g["dpr"]
    pw, ph = g["page_px"]
    cw, ch = g["canvas_px"]
    bd = g["border_B"] * dpr
    sw, sh = cw - 2 * bd, ch - 2 * bd
    s_ov = g["paint_geom"][0] * dpr          # the one scale the overlay uses

    def touched(x, y):
        return b[0][x, y] != a[x, y] or b[1][x, y] != a[x, y]

    # WHERE THE DRAWN PAGE IS, MEASURED. The driver stamps a 6 px block into
    # each corner of the page it loads, so the image's first and last device
    # row and column can be read straight out of the photograph. Deriving them
    # instead (label centring + canvas border + title bar) puts three separate
    # half-pixel roundings in front of a one-pixel measurement.
    org = tuple(g["corner_colours"]["origin"])
    far = tuple(g["corner_colours"]["far"])

    def blob(colour):
        hits = [(x, y) for y in range(H) for x in range(W)
                if dist(a[x, y], colour) <= 40]
        if not hits:
            raise SystemExit(f"{folder.name}: corner marker {colour} not found")
        return (min(h[0] for h in hits), min(h[1] for h in hits),
                max(h[0] for h in hits), max(h[1] for h in hits))

    ox0, oy0, _, _ = blob(org)
    _, _, ox1, oy1 = blob(far)
    off_x, off_y = ox0, oy0
    sx_img, sy_img = (ox1 + 1 - ox0) / pw, (oy1 + 1 - oy0) / ph

    # HOW BIG EACH PAINTED BOX CAME OUT. Two patches the same size on the page
    # must be the same size on screen: a box one device pixel taller than its
    # neighbour rasterises its diagonal differently, and that difference is the
    # "step" a tester saw on some patches and not others.
    pairs = [tuple(tuple(c) for c in q) for q in g["pairs"]]
    parity = g["parity"]

    def is_mix(px, pair, tol=26):
        c0, c1 = pair
        k = max(range(3), key=lambda i: abs(c0[i] - c1[i]))
        span = c1[k] - c0[k]
        if span == 0:
            return dist(px, c0) <= tol
        t = (px[k] - c0[k]) / span
        if not -0.12 <= t <= 1.12:
            return False
        t = min(1.0, max(0.0, t))
        return all(abs(px[i] - (c0[i] + t * (c1[i] - c0[i]))) <= tol
                   for i in range(3))

    sizes = {}

    res = {"window": g["window"], "canvas": g["canvas_px"],
           "scale_image_x": sx_img, "scale_image_y": sy_img,
           "scale_overlay": s_ov,
           "drift_px_at_page_foot": round(ph * (s_ov - sy_img), 3),
           "patches": len(boxes), "untouched_px": 0, "patches_leaking": 0,
           "leak_bottom": 0, "leak_top": 0, "leak_right": 0, "leak_left": 0,
           "examples": []}

    for loc, (x, y, w, h) in sorted(boxes.items()):
        t = math.ceil(y * sy_img) + off_y
        bt = math.floor((y + h) * sy_img) + off_y
        ll = math.ceil(x * sx_img) + off_x
        rr = math.floor((x + w) * sx_img) + off_x
        if not (0 <= t < bt <= H and 0 <= ll < rr <= W):
            continue
        rows_missed, cols_missed = [], []
        n = 0
        for yy in range(t, bt):
            miss = sum(1 for xx in range(ll, rr) if not touched(xx, yy))
            n += miss
            if miss > (rr - ll) * 0.8:
                rows_missed.append(yy)
        for xx in range(ll, rr):
            miss = sum(1 for yy in range(t, bt) if not touched(xx, yy))
            if miss > (bt - t) * 0.8:
                cols_missed.append(xx)
        res["untouched_px"] += n
        # the painted box, walked out of the photographs
        p0 = pairs[parity[loc]]
        p1 = pairs[(parity[loc] + 1) % 2]

        def mine(px, py):
            if not (0 <= px < W and 0 <= py < H):
                return False
            return is_mix(b[0][px, py], p0) and is_mix(b[1][px, py], p1)

        xm, ym = (ll + rr) // 2, (t + bt) // 2
        if mine(xm, ym):
            pt = pb = ym
            pl = pr = xm
            while mine(xm, pt - 1):
                pt -= 1
            while mine(xm, pb + 1):
                pb += 1
            while mine(pl - 1, ym):
                pl -= 1
            while mine(pr + 1, ym):
                pr += 1
            sizes.setdefault((w, h), []).append((pr - pl + 1, pb - pt + 1))
        if rows_missed or cols_missed:
            res["patches_leaking"] += 1
            for yy in rows_missed:
                if yy >= (t + bt) // 2:
                    res["leak_bottom"] += 1
                else:
                    res["leak_top"] += 1
            for xx in cols_missed:
                if xx >= (ll + rr) // 2:
                    res["leak_right"] += 1
                else:
                    res["leak_left"] += 1
            if len(res["examples"]) < 6:
                res["examples"].append(
                    {"loc": loc, "chart_rows": [t, bt - 1],
                     "chart_cols": [ll, rr - 1],
                     "rows_with_no_overlay": rows_missed,
                     "cols_with_no_overlay": cols_missed})
    for (iw, ih), got in sizes.items():
        ws = sorted({q[0] for q in got})
        hs = sorted({q[1] for q in got})
        res.setdefault("box_sizes", []).append(
            {"image_wh": [iw, ih], "n": len(got),
             "painted_widths": ws, "painted_heights": hs})
    return res


def main(root: Path) -> int:
    folders = sorted(p for p in root.iterdir()
                     if p.is_dir() and (p / "geometry.json").is_file())
    if not folders:
        print(f"no photographs under {root}")
        return 2
    tot = {}
    print(f"{'window':>10} {'patches':>8} {'leaking':>8} {'bottom':>7} "
          f"{'top':>5} {'right':>6} {'left':>5} {'untouched':>10} {'drift':>7}")
    for f in folders:
        r = analyse_one(f)
        tot[f.name] = r
        print(f"{f.name:>10} {r['patches']:>8} {r['patches_leaking']:>8} "
              f"{r['leak_bottom']:>7} {r['leak_top']:>5} {r['leak_right']:>6} "
              f"{r['leak_left']:>5} {r['untouched_px']:>10} "
              f"{r['drift_px_at_page_foot']:>7}")
    print(f"\nTOTAL patches photographed .... "
          f"{sum(r['patches'] for r in tot.values())}")
    print(f"TOTAL patches leaking ......... "
          f"{sum(r['patches_leaking'] for r in tot.values())}")
    for name, r in tot.items():
        for e in r["examples"][:3]:
            print(f"  {name} {e}")
    (root / "analysis.json").write_text(json.dumps(tot, indent=1),
                                       encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT))

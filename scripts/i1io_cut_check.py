#!/usr/bin/env python3
"""Is a printed i1iO sheet to scale, and do its pieces lie where the side file says?

    python scripts/i1io_cut_check.py PAGE --side CHART.i1io.json [--mm W H] [--tolerance 0.1]

INDEPENDENT OF THE LAYOUT CODE: nothing of ChromIQ is imported. PAGE is what would be printed (a
sheet or page TIFF / PNG, or a PDF page, e.g. a capture queue's, rendered to pixels here). By image
analysis only the script

1. finds the grey CUT LINES (40 % black, thin, right across the paper) and the paper's edges, and
   divides the page into pieces;
2. in every piece finds the three aiming CROSSES (a 6 mm cross in a 5 mm square, thin black lines),
   measures the distances between them, and from them where the piece's four edges must be: every
   edge must be a cut line or the paper's edge;
3. finds the PATCH edges along and across the strips where the side file has them;
4. looks into EVERY patch: it must be one colour all over (a patch that lies a little off holds a
   part of its neighbour or a spacer), and the patches' colours must follow the chart's own in
   order (the `.ti2` beside the side file: a chart one pitch or one strip off does not);

and compares all of it with the millimetres of the side file (`paper_mm`, `aim_points`, `strips`,
`patch_mm`): a difference above the tolerance (0.1 mm, and what the pixels of the picture add) is
named and the exit status is 1. It also says how the pieces lie on the sheet (as they are, or
turned), so a wrong turn is seen.

With several pieces the pages are taken in the order the pieces stand on the sheet (reading order)
unless --pages says otherwise ("--pages 3 4"). Every page asked for must be there: a piece left
blank is a fault.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np


# ---- the page as pixels ---------------------------------------------------------------------

def load(path: Path, size_mm=None, page: int = 0, dpi: float = 600.0):
    """``(grey 0..255 array, rgb array, mm per px x, mm per px y)``."""
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        import pypdfium2
        doc = pypdfium2.PdfDocument(str(path))
        pg = doc[page]
        w_pt, h_pt = pg.get_size()
        img = pg.render(scale=dpi / 72.0).to_pil().convert("RGB")
        size_mm = size_mm or (w_pt * 25.4 / 72.0, h_pt * 25.4 / 72.0)
    else:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        im = Image.open(path)
        im.seek(page)
        res = im.info.get("dpi")
        img = im.convert("RGB")
        if size_mm is None:
            if not res:
                raise SystemExit("the image names no resolution: give --mm W H")
            size_mm = (img.width / float(res[0]) * 25.4, img.height / float(res[1]) * 25.4)
    rgb = np.asarray(img)
    grey = rgb.astype(np.float32).mean(axis=2)
    return grey, rgb, size_mm[0] / rgb.shape[1], size_mm[1] / rgb.shape[0]


# ---- the cut lines --------------------------------------------------------------------------

def cut_lines(rgb, mmx, mmy, along: str) -> "list[float]":
    """The middles (mm) of grey lines that run right across the page: neutral, 40 % black
    (125..180 of 255) on at least 60 % of the pixels of a column ("x") or row ("y")."""
    a = rgb.astype(np.int16)
    neutral = (np.abs(a[:, :, 0] - a[:, :, 1]) < 12) & (np.abs(a[:, :, 1] - a[:, :, 2]) < 12)
    grey = neutral & (a[:, :, 0] > 120) & (a[:, :, 0] < 185)
    share = grey.mean(axis=0 if along == "x" else 1)
    mm = mmx if along == "x" else mmy
    hit = share > 0.6
    out = []
    i = 0
    while i < len(hit):
        if hit[i]:
            j = i
            while j + 1 < len(hit) and hit[j + 1]:
                j += 1
            # a thin line only (under 1 mm): a grey patch is never page wide
            if (j - i + 1) * mm < 1.0:
                w = share[i:j + 1]
                out.append(float(((np.arange(i, j + 1) + 0.5) * w).sum() / w.sum()) * mm)
            i = j
        i += 1
    return out


def pieces(rgb, mmx, mmy) -> "list[tuple[float, float, float, float]]":
    """The rectangles (mm) the cut lines divide the page into that hold print, reading order."""
    H, W = rgb.shape[0] * mmy, rgb.shape[1] * mmx
    xs = [0.0] + cut_lines(rgb, mmx, mmy, "x") + [W]
    ys = [0.0] + cut_lines(rgb, mmx, mmy, "y") + [H]
    out = []
    for y0, y1 in zip(ys, ys[1:]):
        for x0, x1 in zip(xs, xs[1:]):
            if x1 - x0 < 40 or y1 - y0 < 40:
                continue                       # a trimmed strip
            out.append((x0, y0, x1, y1))
    return out


# ---- the crosses ----------------------------------------------------------------------------

def _components(mask: np.ndarray):
    """Connected dark regions as ``(y0, y1, x0, x1)`` boxes (8-connected, run based)."""
    parent: "list[int]" = []

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    boxes: "list[list[int]]" = []
    prev: "list[tuple[int, int, int]]" = []
    for y in range(mask.shape[0]):
        row = mask[y]
        d = np.flatnonzero(np.diff(np.concatenate(([0], row.view(np.int8), [0]))))
        now = []
        for x0, x1 in zip(d[::2], d[1::2]):
            lab = -1
            for (a, b, l_) in prev:
                if a <= x1 and b >= x0:
                    r = find(l_)
                    if lab < 0:
                        lab = r
                    elif r != lab:
                        parent[r] = lab
                        bx, by = boxes[lab], boxes[r]
                        bx[0], bx[1] = min(bx[0], by[0]), max(bx[1], by[1])
                        bx[2], bx[3] = min(bx[2], by[2]), max(bx[3], by[3])
            if lab < 0:
                lab = len(parent)
                parent.append(lab)
                boxes.append([y, y, int(x0), int(x1) - 1])
            else:
                bx = boxes[lab]
                bx[1] = y
                bx[2], bx[3] = min(bx[2], int(x0)), max(bx[3], int(x1) - 1)
            now.append((int(x0), int(x1), lab))
        prev = now
    return [tuple(boxes[i]) for i in range(len(parent)) if find(i) == i]


def crosses(grey, mmx, mmy, box) -> "list[tuple[float, float]]":
    """The middles (mm on the page) of the aiming crosses in *box* (mm): a connected dark shape
    about 6 x 6 mm whose middle row and middle column are dark from end to end, and whose
    corners (outside the 5 mm square, between the arms) are paper."""
    x0, y0, x1, y1 = box
    a, b = int(x0 / mmx), int(x1 / mmx)
    c, d = int(y0 / mmy), int(y1 / mmy)
    mask = grey[c:d, a:b] < 110
    out = []
    for (r0, r1, k0, k1) in _components(mask):
        h, w = (r1 - r0 + 1) * mmy, (k1 - k0 + 1) * mmx
        if not (5.6 < h < 6.5 and 5.6 < w < 6.5):
            continue
        sub = mask[r0:r1 + 1, k0:k1 + 1]
        n, m = sub.shape
        rows, cols = sub.mean(axis=1), sub.mean(axis=0)
        if rows[n // 2 - max(1, n // 12): n // 2 + max(2, n // 12)].max() < 0.95 \
                or cols[m // 2 - max(1, m // 12): m // 2 + max(2, m // 12)].max() < 0.95:
            continue
        if sub.mean() > 0.55:
            continue                           # a filled patch
        # the middle of the lines, by their dark share
        ry = np.flatnonzero(rows > 0.95)
        ry = ry[np.abs(ry - n / 2) < n / 4]
        rx = np.flatnonzero(cols > 0.95)
        rx = rx[np.abs(rx - m / 2) < m / 4]
        if not len(ry) or not len(rx):
            continue
        out.append(((a + k0 + rx.mean() + 0.5) * mmx, (c + r0 + ry.mean() + 0.5) * mmy))
    return out


# ---- the patches ----------------------------------------------------------------------------

def edges_along(rgb, mmx, mmy, p0, p1, half_mm=1.0) -> "tuple[np.ndarray, np.ndarray]":
    """``(positions mm from p0, step height)`` of the colour steps on the line p0 to p1 (mm)."""
    L = math.dist(p0, p1)
    step = min(mmx, mmy) / 2.0
    t = np.arange(0.0, L, step)
    ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
    prof = []
    for off in np.linspace(-half_mm, half_mm, 5):
        xs = p0[0] + ux * t - uy * off
        ys = p0[1] + uy * t + ux * off
        ix = np.clip((xs / mmx).astype(int), 0, rgb.shape[1] - 1)
        iy = np.clip((ys / mmy).astype(int), 0, rgb.shape[0] - 1)
        prof.append(rgb[iy, ix].astype(np.float32))
    p = np.mean(prof, axis=0)
    diff = np.abs(np.diff(p, axis=0)).max(axis=1)
    return t[1:], diff


def colours_of(ti2: Path) -> "dict[str, tuple[float, float, float]]":
    """``{location: RGB 0..255}`` of a chart's `.ti2` (RGB charts; else empty)."""
    out: "dict[str, tuple[float, float, float]]" = {}
    if not ti2.is_file():
        return out
    lines = ti2.read_text(encoding="utf-8", errors="replace").split("\n")
    try:
        names = lines[lines.index("BEGIN_DATA_FORMAT") + 1].split()
        a, b = lines.index("BEGIN_DATA"), lines.index("END_DATA")
        loc, rgb = names.index("SAMPLE_LOC"), [names.index(f"RGB_{c}") for c in "RGB"]
    except ValueError:
        return out
    for ln in lines[a + 1:b]:
        f = ln.split()
        if len(f) > max(rgb):
            out[f[loc].strip('"')] = tuple(float(f[k]) * 2.55 for k in rgb)
    return out


def rank_agreement(a, b) -> float:
    """Spearman's rank correlation (1.0 = the same order)."""
    def ranks(v):
        v = np.asarray(v, float)
        u, inv, n = np.unique(v, return_inverse=True, return_counts=True)
        start = np.cumsum(n) - n
        return (start + (n - 1) / 2.0)[inv]
    ra, rb = ranks(a), ranks(b)
    ra, rb = ra - ra.mean(), rb - rb.mean()
    d = math.sqrt(float((ra * ra).sum() * (rb * rb).sum()))
    return float((ra * rb).sum() / d) if d else 0.0


def check_piece(grey, rgb, mmx, mmy, box, side: dict, page: int, tol: float,
                colours: "dict | None" = None) -> dict:
    """The measured piece *box* against page *page* (0-based) of the side file."""
    want_pts = {a["number"]: a["page_mm"] for a in side["pages"][page]["aim_points"]}
    out = {"page": page + 1, "box_mm": [round(v, 3) for v in box], "problems": []}
    found = crosses(grey, mmx, mmy, box)
    out["crosses"] = [[round(v, 3) for v in f] for f in found]
    if side["pages"][page].get("aim") != "crosses":
        out["problems"].append("this page carries no crosses: nothing to measure from")
        return out
    if len(found) != 3:
        out["problems"].append(f"{len(found)} crosses found, not 3")
        return out
    # which found cross is which: by the side lengths (as it is, or turned any way)
    want = [want_pts[k] for k in (1, 2, 3)]
    best = None
    import itertools
    for perm in itertools.permutations(range(3)):
        g = [found[i] for i in perm]
        err = max(abs(math.dist(g[i], g[j]) - math.dist(want[i], want[j]))
                  for i, j in ((0, 1), (1, 2), (0, 2)))
        cross_w = ((want[1][0] - want[0][0]) * (want[2][1] - want[0][1])
                   - (want[1][1] - want[0][1]) * (want[2][0] - want[0][0]))
        cross_g = ((g[1][0] - g[0][0]) * (g[2][1] - g[0][1])
                   - (g[1][1] - g[0][1]) * (g[2][0] - g[0][0]))
        if cross_w * cross_g <= 0:
            continue                           # mirrored
        if best is None or err < best[0]:
            best = (err, g)
    if best is None:
        out["problems"].append("the crosses lie mirrored")
        return out
    err, g = best
    px = max(mmx, mmy)
    out["cross_error_mm"] = round(err, 4)
    out["distances_mm"] = {f"{i + 1}-{j + 1}": [round(math.dist(g[i], g[j]), 3),
                                               round(math.dist(want[i], want[j]), 3)]
                           for i, j in ((0, 1), (1, 2), (0, 2))}
    if err > tol:
        out["problems"].append(f"cross distances are off by {err:.3f} mm")
    # the turn of the piece on the sheet, from cross 1 to cross 2
    ang = math.degrees(math.atan2(g[1][1] - g[0][1], g[1][0] - g[0][0])
                       - math.atan2(want[1][1] - want[0][1], want[1][0] - want[0][0]))
    out["turned_deg"] = round((ang + 180) % 360 - 180, 2)
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))

    def to_page(p):
        dx, dy = p[0] - want[0][0], p[1] - want[0][1]
        return (g[0][0] + ca * dx - sa * dy, g[0][1] + sa * dx + ca * dy)
    # the piece's own edges against the cut lines and the paper's edges
    pw, ph = (float(v) for v in side["paper_mm"])
    ends = [to_page(q) for q in ((0.0, 0.0), (pw, 0.0), (0.0, ph), (pw, ph))]
    should = (min(e[0] for e in ends), min(e[1] for e in ends),
              max(e[0] for e in ends), max(e[1] for e in ends))
    offs = [a - b for a, b in zip(box, should)]
    out["edges_off_mm"] = [round(v, 3) for v in offs]
    if max(abs(v) for v in offs) > tol + 2 * px:
        out["problems"].append("a cut line or an edge of the paper lies "
                               f"{max(offs, key=abs):.3f} mm off the piece's edge")
    # the patch edges of three strips (along) and of three patches across the strips
    across, along = (float(v) for v in side["patch_mm"])
    strips = side["pages"][page]["strips"]
    worst, seen, expected = 0.0, 0, 0

    def look(p0, p1, places):
        """The colour steps near *places* (mm from p0) on the line p0 to p1 (page mm)."""
        nonlocal worst, seen, expected
        t, diff = edges_along(rgb, mmx, mmy, to_page(p0), to_page(p1))
        for e in places:
            near = np.abs(t - e) < 0.45
            expected += 1
            if not near.any() or diff[near].max() < 8:
                continue                       # neighbours of one colour: no edge to see
            seen += 1
            worst = max(worst, abs(float(t[near][int(np.argmax(diff[near]))]) - e))
    for s in sorted({0, len(strips) // 2, len(strips) - 1}):
        ys = [q["centre_mm"][1] for q in strips[s]["patches"]]
        top, x = min(ys) - along / 2 - 4.0, float(strips[s]["x_mm"])
        look((x, top), (x, max(ys) + along / 2 + 4.0),
             [y + d - top for y in ys for d in (-along / 2, along / 2)])
    n = len(strips[0]["patches"])
    for k in sorted({0, n // 2, n - 1}):
        row = [st["patches"][k]["centre_mm"] for st in strips if len(st["patches"]) > k]
        left, y = min(c[0] for c in row) - across / 2 - 4.0, row[0][1]
        look((left, y), (max(c[0] for c in row) + across / 2 + 4.0, y),
             [c[0] + d - left for c in row for d in (-across / 2, across / 2)])
    out["patch_edges"], out["patch_edges_expected"] = seen, expected
    out["patch_edge_error_mm"] = round(worst, 4)
    if seen < 0.6 * expected:
        out["problems"].append(f"only {seen} of {expected} patch edges found")
    if worst > tol + px:
        out["problems"].append(f"a patch edge is off by {worst:.3f} mm")
    # every patch: one colour all over, and the chart's colours in their order
    inset = tol + 2 * px
    hx, hy = across / 2 - inset, along / 2 - inset
    if abs(round(ang / 90.0)) % 2:
        hx, hy = hy, hx
    mixed, got, exp = [], [], []
    for st in strips:
        for q in st["patches"]:
            cx, cy = to_page(q["centre_mm"])
            a, b = int(math.ceil((cx - hx) / mmx)), int((cx + hx) / mmx)
            c, d = int(math.ceil((cy - hy) / mmy)), int((cy + hy) / mmy)
            cell = rgb[max(0, c):d, max(0, a):b].reshape(-1, 3).astype(np.int16)
            if not len(cell) or int((cell.max(axis=0) - cell.min(axis=0)).max()) > 12:
                mixed.append(q["loc"])
            elif colours and q["loc"] in colours:
                got.append(cell.mean(axis=0))
                exp.append(colours[q["loc"]])
    out["patches_of_more_than_one_colour"] = len(mixed)
    if mixed:
        out["problems"].append(f"{len(mixed)} patches hold more than one colour, "
                               f"the first is {mixed[0]}")
    if len(got) >= 8:
        g3, e3 = np.array(got), np.array(exp)
        out["colour_order"] = round(min(rank_agreement(g3[:, k], e3[:, k]) for k in range(3)), 4)
        if out["colour_order"] < 0.95:
            out["problems"].append("the colours are not this page's, or not in their places "
                                   f"(rank agreement {out['colour_order']:.2f})")
    return out


def check(path, side_path, size_mm=None, pages=None, tol=0.1, page_no=0, dpi=600.0,
          ti2=None) -> dict:
    side_path = Path(side_path)
    side = json.loads(side_path.read_text(encoding="utf-8"))
    if ti2 is None:
        ti2 = side_path.parent / (side_path.name.split(".i1io")[0] + ".ti2")
    colours = colours_of(Path(ti2))
    grey, rgb, mmx, mmy = load(Path(path), size_mm, page_no, dpi)
    boxes = pieces(rgb, mmx, mmy)
    printed = [b for b in boxes if crosses(grey, mmx, mmy, b)]
    problems = []
    if pages is None:
        # every piece of the sheet, as long as the chart has pages for them
        pages = list(range(1, min(len(boxes), len(side["pages"])) + 1))
    if len(printed) != len(pages):
        problems.append(f"{len(printed)} pieces with crosses found, {len(pages)} pages asked for")
    res = {"page_mm": [round(rgb.shape[1] * mmx, 3), round(rgb.shape[0] * mmy, 3)],
           "cut_x_mm": [round(v, 3) for v in cut_lines(rgb, mmx, mmy, "x")],
           "cut_y_mm": [round(v, 3) for v in cut_lines(rgb, mmx, mmy, "y")],
           "colours_known": len(colours), "problems": problems,
           "pieces": [check_piece(grey, rgb, mmx, mmy, b, side, p - 1, tol, colours)
                      for b, p in zip(printed or boxes[:1], pages)]}
    res["ok"] = (not problems and bool(res["pieces"])
                 and all(not p["problems"] for p in res["pieces"]))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("page")
    ap.add_argument("--side", required=True)
    ap.add_argument("--mm", nargs=2, type=float)
    ap.add_argument("--pages", nargs="*", type=int)
    ap.add_argument("--page-no", type=int, default=0)
    ap.add_argument("--dpi", type=float, default=600.0)
    ap.add_argument("--tolerance", type=float, default=0.1)
    ap.add_argument("--ti2", help="the chart's .ti2 (default: beside the side file)")
    a = ap.parse_args(argv)
    res = check(a.page, a.side, tuple(a.mm) if a.mm else None, a.pages, a.tolerance,
                a.page_no, a.dpi, a.ti2)
    print(json.dumps(res, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

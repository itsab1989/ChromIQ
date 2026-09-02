"""Empirical calibration of the scanner misalignment check (Knut, #119).

Answers, with numbers off Knut's two real 600 dpi IT8 scans:

  * what the page grain (noise) floor actually is, per patch and page-wide;
  * how big the smallest real edge between neighbouring patches is, split by
    patch character (dark / light / greyscale / colour-gradient), in each of
    the four directions;
  * what ``scanner_flank_limit`` and the new ``scanner_flank_min_boxes`` have
    to be so that an aligned grid stays silent while a small offset — in
    particular Knut's "one corner pulled inwards" case — is caught;
  * whether a denser ladder (24x5 % or 60x2 %) buys anything over 12x10 %.

The scans are not in the repo (they are large, and Knut's property). Point the
script at them::

    python scripts/scanner_edge_study.py --data-dir ~/it8-scans

expecting ``ScannedIT8WFTarget01-8bit.tiff`` + ``R230122W.cht`` +
``R230122W.txt`` and ``ScannedIT8LSTarget01-8bit.tif`` + ``ISO12641_2_1.cht``
+ ``R250715.cie`` somewhere beneath it.

The "aligned" grid is not guessed: it is ArgyllCMS ``scanin``'s own solved
placement, recovered from its verbose transform and checked patch-by-patch
against the ``.ti3`` scanin writes (agreement is ~0.2 % of device range).
"""
from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.proc_text import run_text
Image.MAX_IMAGE_PIXELS = None

from workflow.cht_parser import parse_cht                       # noqa: E402
from workflow.placement_probe import dense_placement_agreement   # noqa: E402

ARGYLL = Path("/Applications/Argyll/bin")
MAX_SIDE = 2200          # placement_probe's sampling resolution
SAMPLE_FRAC = 0.5


# --------------------------------------------------------------------------
# scanin's own placement
# --------------------------------------------------------------------------

def _scanin_transform(tif: Path, cht: Path, ref: Path):
    """(irot, xoff, yoff, xscale, yscale) for the rotation scanin chose."""
    r = run_text([str(ARGYLL / "scanin"), "-v", "-dipn",
                  tif.name, str(cht), str(ref)],
                 capture_output=True, cwd=tif.parent)
    txt = r.stdout + r.stderr
    m = re.search(r"Chosen rotation ([-\d.]+) deg", txt)
    if not m:
        raise SystemExit(f"scanin did not report a rotation for {tif.name}")
    chosen = float(m.group(1))
    for line in txt.splitlines():
        mm = re.match(r"cc = [\d.]+, irot = ([-\d.]+), xoff = ([-\d.]+), "
                      r"yoff = ([-\d.]+), xscale = ([\d.]+), yscale = ([\d.]+)",
                      line)
        if mm and abs(float(mm.group(1)) - chosen) < 1e-3:
            return tuple(float(g) for g in mm.groups())
    raise SystemExit(f"could not recover scanin's transform for {tif.name}")


def _cht_to_image(irot, xoff, yoff, xsc, ysc):
    a = math.radians(irot)
    ca, sa = math.cos(a), math.sin(a)

    def f(cx, cy):
        x, y = cx * xsc, cy * ysc
        return xoff + x * ca - y * sa, yoff + x * sa + y * ca
    return f


def _read_ti3(p: Path):
    txt = p.read_text(errors="ignore", encoding="utf-8")
    fmt = txt.split("BEGIN_DATA_FORMAT", 1)[1].split("END_DATA_FORMAT", 1)[0].split()
    body = txt.split("\nBEGIN_DATA\n", 1)[1].split("\nEND_DATA", 1)[0]
    xyz_i = [fmt.index(c) for c in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
    rgb_i = [fmt.index(c) for c in ("RGB_R", "RGB_G", "RGB_B")]
    xyz, rgb = {}, {}
    for line in body.strip().splitlines():
        t = line.split()
        if len(t) <= max(xyz_i + rgb_i):
            continue
        n = t[0].strip('"')
        xyz[n] = tuple(float(t[i]) for i in xyz_i)
        rgb[n] = tuple(float(t[i]) for i in rgb_i)
    return xyz, rgb


class _Box:
    __slots__ = ("x1", "y1", "x2", "y2", "name")

    def __init__(self, b):
        self.x1, self.y1, self.x2, self.y2, self.name = b.x1, b.y1, b.x2, b.y2, b.name


class Target:
    def __init__(self, name, tif, cht, ref):
        self.name, self.tif, self.cht, self.ref = name, tif, cht, ref
        tp = _scanin_transform(tif, cht, ref)
        self.geom = parse_cht(cht.read_text(errors="ignore", encoding="utf-8"))
        self.boxes = [_Box(b) for b in self.geom.patches]
        f = _cht_to_image(*tp)
        self.src_quad = (list(self.geom.fiducials)
                         if len(self.geom.fiducials) == 4 else None)
        quad = self.src_quad or self._bbox()
        self.corners = [f(x, y) for x, y in quad]
        ti3 = tif.with_suffix(".ti3")
        self.xyz, self.rgb = _read_ti3(ti3)
        self.expected = {n: v for n, v in self.xyz.items()}

    def _bbox(self):
        xs = [b.x1 for b in self.boxes] + [b.x2 for b in self.boxes]
        ys = [b.y1 for b in self.boxes] + [b.y2 for b in self.boxes]
        return [(min(xs), min(ys)), (max(xs), min(ys)),
                (max(xs), max(ys)), (min(xs), max(ys))]

    def verify(self):
        arr = np.asarray(Image.open(self.tif).convert("RGB"), dtype=float)
        H, W = arr.shape[:2]
        h = _homography_from(self._bbox() if self.src_quad is None
                             else self.src_quad, self.corners)
        errs = []
        for b in self.boxes:
            if b.name not in self.rgb:
                continue
            X, Y = _apply(h, (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2)
            xi, yi = int(round(X)), int(round(Y))
            if not (3 <= xi < W - 3 and 3 <= yi < H - 3):
                continue
            got = arr[yi - 2:yi + 3, xi - 2:xi + 3].reshape(-1, 3).mean(0) / 255 * 100
            errs.append(float(np.abs(got - np.array(self.rgb[b.name])).mean()))
        return float(np.mean(errs)), len(errs)


def _homography_from(src, dst):
    from workflow.placement_probe import _homography
    return _homography(list(src), list(dst))


def _apply(h, x, y):
    d = h[2, 0] * x + h[2, 1] * y + h[2, 2]
    return ((h[0, 0] * x + h[0, 1] * y + h[0, 2]) / d,
            (h[1, 0] * x + h[1, 1] * y + h[1, 2]) / d)


# --------------------------------------------------------------------------
# the probe's own planes, recomputed so we can look inside
# --------------------------------------------------------------------------

def _planes(tif: Path):
    img = Image.open(tif)
    img.load()
    if img.mode != "RGB":
        img = img.convert("RGB")
    scale = min(1.0, MAX_SIDE / max(img.size))
    if scale < 1.0:
        img = img.resize((max(1, int(img.width * scale)),
                          max(1, int(img.height * scale))))
    arr = np.asarray(img, dtype=np.float64)
    lum = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    chroma = [arr[..., 0] - arr[..., 2],
              arr[..., 0] + arr[..., 2] - 2.0 * arr[..., 1]]
    return lum, chroma, scale


def _cgrad(plane, k):
    g = np.zeros_like(plane)
    g[:, k:-k] = np.abs(plane[:, 2 * k:] - plane[:, :-2 * k])
    gy = np.abs(plane[2 * k:, :] - plane[:-2 * k, :])
    g[k:-k, :] = np.maximum(g[k:-k, :], gy)
    return g


def _grad(lum, chroma):
    g = None
    for plane in [lum] + chroma:
        gg = np.maximum(_cgrad(plane, 2), _cgrad(plane, 4))
        g = gg if g is None else np.maximum(g, gg)
    return g


def _category(t: Target, name: str) -> str:
    """Knut's four buckets, from the reference XYZ (Y is 0..100)."""
    if name.upper().startswith("GS"):
        return "greyscale"
    X, Y, Z = t.xyz[name]
    s = X + Y + Z
    if s <= 0:
        return "dark"
    x, y = X / s, Y / s
    neutral = abs(x - 0.3457) < 0.02 and abs(y - 0.3585) < 0.02
    if neutral:
        return "greyscale"
    if Y < 12:
        return "dark"
    if Y > 65:
        return "light"
    return "colour-gradient"


# --------------------------------------------------------------------------
# A. noise floor + B. neighbour edge heights
# --------------------------------------------------------------------------

def _grid_neighbours(t: Target):
    """(name -> {dir: neighbour}) from the .cht letter/number ids."""
    pos, rc = {}, {}
    for b in t.boxes:
        m = re.match(r"^([A-Za-z]+)(\d+)$", b.name)
        if not m:
            continue
        rc[b.name] = (m.group(1), int(m.group(2)))
    rows = sorted({r for r, _c in rc.values()})
    ridx = {r: i for i, r in enumerate(rows)}
    for n, (r, c) in rc.items():
        pos[(ridx[r], c)] = n
    out = {}
    for n, (r, c) in rc.items():
        i = ridx[r]
        out[n] = {"up": pos.get((i - 1, c)), "down": pos.get((i + 1, c)),
                  "left": pos.get((i, c - 1)), "right": pos.get((i, c + 1))}
    return out


def _patch_planes(t: Target, lum, chroma, scale):
    """Mean lum + chroma per patch, sampled at the aligned grid."""
    src = t.src_quad or t._bbox()
    dst = [(x * scale, y * scale) for x, y in t.corners]
    h = _homography_from(src, dst)
    H, W = lum.shape
    vals = {}
    for b in t.boxes:
        cx, cy = (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2
        hx, hy = (b.x2 - b.x1) * SAMPLE_FRAC / 2, (b.y2 - b.y1) * SAMPLE_FRAC / 2
        xa, ya = _apply(h, cx - hx, cy - hy)
        xb, yb = _apply(h, cx + hx, cy + hy)
        x0, x1 = sorted((int(round(xa)), int(round(xb))))
        y0, y1 = sorted((int(round(ya)), int(round(yb))))
        if x0 < 0 or y0 < 0 or x1 > W or y1 > H or x1 - x0 < 2 or y1 - y0 < 2:
            continue
        vals[b.name] = (float(lum[y0:y1, x0:x1].mean()),
                        float(chroma[0][y0:y1, x0:x1].mean()),
                        float(chroma[1][y0:y1, x0:x1].mean()))
    return vals, h


def study_target(t: Target, out):
    p = out.append
    p(f"\n{'=' * 78}\n{t.name}\n{'=' * 78}")
    err, n = t.verify()
    p(f"aligned grid = scanin's own placement; "
      f"reproduces its .ti3 on {n} patches to {err:.2f} % mean device error")

    lum, chroma, scale = _planes(t.tif)
    grad = _grad(lum, chroma)
    vals, h = _patch_planes(t, lum, chroma, scale)
    lum_range = max(v[0] for v in vals.values()) - min(v[0] for v in vals.values())
    p(f"sampling resolution {lum.shape[1]}x{lum.shape[0]} px "
      f"(scale {scale:.3f}); page luminance range {lum_range:.1f}")

    # --- A. noise floor: inner-9x9 cell gradient peaks on the aligned grid
    H, W = grad.shape
    per_patch_floor = {}
    all_cells = []
    for b in t.boxes:
        cx, cy = (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2
        hx, hy = (b.x2 - b.x1) * SAMPLE_FRAC / 2, (b.y2 - b.y1) * SAMPLE_FRAC / 2
        xa, ya = _apply(h, cx - hx, cy - hy)
        xb, yb = _apply(h, cx + hx, cy + hy)
        x0, x1 = sorted((int(round(xa)), int(round(xb))))
        y0, y1 = sorted((int(round(ya)), int(round(yb))))
        if x0 < 0 or y0 < 0 or x1 > W or y1 > H:
            continue
        cw, ch = (x1 - x0) / 9.0, (y1 - y0) / 9.0
        if cw < 1 or ch < 1:
            continue
        cells = []
        for j in range(9):
            for i in range(9):
                ax, bx = int(round(x0 + i * cw)), int(round(x0 + (i + 1) * cw))
                ay, by = int(round(y0 + j * ch)), int(round(y0 + (j + 1) * ch))
                if bx - ax < 1 or by - ay < 1:
                    continue
                cells.append(float(grad[ay:by, ax:bx].max()))
        if cells:
            per_patch_floor[b.name] = cells
            all_cells.extend(cells)
    a = np.array(all_cells)
    gfloor = float(np.percentile(a, 75))
    p(f"\n-- A. noise floor (inner 9x9 cell gradient peaks, aligned grid) --")
    p(f"   cells={a.size}  min={a.min():.2f}  mean={a.mean():.2f}  "
      f"max={a.max():.2f}")
    p(f"   P50={np.percentile(a,50):.2f}  P75={gfloor:.2f} (= grain floor)  "
      f"P99={np.percentile(a,99):.2f}")
    p(f"   as fraction of page luminance range: "
      f"min={a.min()/lum_range:.4f}  mean={a.mean()/lum_range:.4f}  "
      f"P75={gfloor/lum_range:.4f}  max={a.max()/lum_range:.4f}")
    pm = np.array([np.mean(v) for v in per_patch_floor.values()])
    p(f"   per-patch mean cell peak: min={pm.min():.2f}  "
      f"avg={pm.mean():.2f}  max={pm.max():.2f}   "
      f"(normalised {pm.min()/lum_range:.4f} / {pm.mean()/lum_range:.4f} / "
      f"{pm.max()/lum_range:.4f})")

    # --- B. neighbour edge heights per direction and category
    nb = _grid_neighbours(t)
    buckets: dict[tuple[str, str], list[float]] = {}
    for n, dirs in nb.items():
        if n not in vals:
            continue
        cat = _category(t, n)
        for d, m in dirs.items():
            if not m or m not in vals:
                continue
            dv = max(abs(vals[n][k] - vals[m][k]) for k in range(3))
            buckets.setdefault((cat, d), []).append(dv / lum_range)
    p(f"\n-- B. edge height to neighbouring patch "
      f"(max over lum + 2 opponent planes, as fraction of page lum range) --")
    p(f"   {'category':17s} {'dir':6s} {'n':>4s} {'min':>8s} {'p05':>8s} "
      f"{'median':>8s} {'max':>8s}")
    for cat in ("dark", "light", "greyscale", "colour-gradient"):
        for d in ("up", "down", "left", "right"):
            v = np.array(buckets.get((cat, d), []))
            if not v.size:
                continue
            p(f"   {cat:17s} {d:6s} {v.size:4d} {v.min():8.4f} "
              f"{np.percentile(v,5):8.4f} {np.median(v):8.4f} {v.max():8.4f}")
    allv = np.array([x for v in buckets.values() for x in v])
    p(f"   {'ALL':17s} {'':6s} {allv.size:4d} {allv.min():8.4f} "
      f"{np.percentile(allv,5):8.4f} {np.median(allv):8.4f} {allv.max():8.4f}")
    return lum_range, gfloor


# --------------------------------------------------------------------------
# C. flank response vs. offset  (the actual calibration)
# --------------------------------------------------------------------------

def _shift(corners, dx, dy):
    return [(x + dx, y + dy) for x, y in corners]


def _pull_corner(corners, i, frac):
    """Pull one corner towards the quad centre by ``frac`` of its distance to
    the centre. The local displacement at that corner is the largest on the
    page and decays to zero at the opposite corner."""
    cx = sum(c[0] for c in corners) / 4.0
    cy = sum(c[1] for c in corners) / 4.0
    out = list(corners)
    x, y = out[i]
    out[i] = (x + (cx - x) * frac, y + (cy - y) * frac)
    return out, math.hypot((cx - x) * frac, (cy - y) * frac)


def _flank_counts(t: Target, corners, limits, steps=12, step_frac=0.10):
    rep = dense_placement_agreement(
        t.tif, t.boxes, corners, t.expected, sample_frac=SAMPLE_FRAC,
        steps=steps, step_frac=step_frac, objective="response",
        src_quad=t.src_quad)
    if rep is None:
        return None, {}
    fv = rep.flank_by_patch
    return rep, {L: sum(1 for v in fv.values() if v > L) for L in limits}


def calibrate(t: Target, out, steps=12, step_frac=0.10):
    p = out.append
    limits = [0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30]
    pitch = min(b.x2 - b.x1 for b in t.boxes)
    # pixel pitch of one patch in the sampled image
    lum, _c, scale = _planes(t.tif)
    src = t.src_quad or t._bbox()
    h = _homography_from(src, [(x * scale, y * scale) for x, y in t.corners])
    b0 = t.boxes[0]
    x0, y0 = _apply(h, b0.x1, b0.y1)
    x1, y1 = _apply(h, b0.x2, b0.y2)
    px_patch = math.hypot(x1 - x0, y1 - y0) / math.sqrt(2)
    p(f"\n-- C. flank response (ladder {steps}x{step_frac:.0%}) --")
    p(f"   one patch is ~{px_patch:.1f} px at the probe's sampling "
      f"resolution -> a {step_frac:.0%} ladder step = "
      f"{px_patch*step_frac:.2f} px")

    # "must stay silent": aligned, plus shifts too small to put any sample-box
    # edge on a patch border (the box spans SAMPLE_FRAC of the pitch, so its
    # rim is (1-SAMPLE_FRAC)/2 = 25 % of the pitch away from the border).
    # "must be caught": shifts that do put box rims on borders, and Knut's
    # corner pull (#119) once its local displacement reaches that same 25 %.
    cases: list[tuple[str, list, bool | None]] = [("aligned", t.corners, False)]
    for f_ in (0.02, 0.05, 0.10):
        dx = f_ * px_patch / scale
        cases.append((f"shift x {f_:.0%} patch", _shift(t.corners, dx, 0), False))
    for f_ in (0.20, 0.30):
        dx = f_ * px_patch / scale
        cases.append((f"shift x {f_:.0%} patch", _shift(t.corners, dx, 0), True))
    for f_ in (0.10, 0.20):
        dy = f_ * px_patch / scale
        cases.append((f"shift y {f_:.0%} patch", _shift(t.corners, 0, dy), None))
    # A corner pull displaces only the patches NEAR that corner, decaying to
    # zero at the opposite one. A box rim reaches its border at 25 % of the
    # pitch, so at a local 25 % exactly one or two patches straddle — too few
    # to demand. Knut's case is "a few patches in that corner": require
    # detection from a local 50 %, and stay silent below 10 %.
    for f_ in (0.005, 0.01, 0.02, 0.03, 0.04, 0.06):
        cor, disp = _pull_corner(t.corners, 0, f_)
        local = disp * scale / px_patch      # in patch pitches, at that corner
        must = True if local >= 0.50 else (False if local < 0.10 else None)
        cases.append((f"corner pull {f_:.1%} (local {local:.0%} of patch)",
                      cor, must))

    p(f"\n   {'case':38s} {'flag':>4s} {'agree%':>7s} " +
      " ".join(f"{L:>5.2f}" for L in limits))
    rows = {}
    for label, cor, must in cases:
        rep, cnt = _flank_counts(t, cor, limits, steps, step_frac)
        if rep is None:
            p(f"   {label:38s}  (no report)")
            continue
        rows[label] = (cnt, must)
        tag = {True: "YES", False: "no", None: "—"}[must]
        p(f"   {label:38s} {tag:>4s} {rep.agreement_pct:7.2f} " +
          " ".join(f"{cnt[L]:5d}" for L in limits))
    p("   (columns = number of sample boxes whose flank value exceeds that limit)")
    p("   flag = must the page be reported misaligned?  '—' = don't care")
    return rows, limits


def recommend(rows, limits, out, label=""):
    """min_boxes must exceed every must-stay-silent count and not exceed any
    must-be-caught count."""
    p = out.append
    p(f"\n-- D. admissible (limit, min_boxes) pairs {label} --")
    silent = [k for k, (_c, m) in rows.items() if m is False]
    caught = [k for k, (_c, m) in rows.items() if m is True]
    best = []
    for L in limits:
        hi_silent = max(rows[k][0][L] for k in silent) if silent else 0
        lo_caught = min(rows[k][0][L] for k in caught) if caught else 10 ** 9
        lo, hi = hi_silent + 1, lo_caught
        if lo <= hi:
            best.append((L, hi_silent, lo_caught, lo, hi))
    if not best:
        p("   none — no single limit separates the silent cases from the "
          "caught ones")
    for L, hs, lc, lo, hi in best:
        p(f"   limit {L:.2f}: worst silent case = {hs:3d} boxes, weakest "
          f"caught case = {lc:4d} boxes  ->  min_boxes in [{lo}, {hi}]")
    return best


def combine(all_rows, limits, out):
    """Both targets at once — the shipped default has to hold for both."""
    merged: dict[str, tuple[dict, bool | None]] = {}
    for tname, rows in all_rows.items():
        for k, v in rows.items():
            merged[f"{tname} · {k}"] = v
    return recommend(merged, limits, out, label="ACROSS BOTH TARGETS")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True, type=Path)
    ap.add_argument("--ladder", default="12x0.10",
                    help="steps x step_frac, e.g. 24x0.05")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    steps, sf = a.ladder.split("x")
    steps, sf = int(steps), float(sf)

    d = a.data_dir.expanduser()

    def find(pat):
        hits = list(d.rglob(pat))
        if not hits:
            raise SystemExit(f"missing {pat} under {d}")
        return hits[0]

    targets = [
        Target("Wolf Faust IT8 (R230122W)", find("ScannedIT8WFTarget01-8bit.tiff"),
               find("R230122W.cht"), find("R230122W.txt")),
        Target("LaserSoft DC Pro Advanced (R250715)",
               find("ScannedIT8LSTarget01-8bit.tif"),
               find("ISO12641_2_1.cht"), find("R250715.cie")),
    ]
    out: list[str] = [f"ChromIQ scanner edge study — ladder {steps}x{sf:.0%}"]
    all_rows, limits = {}, None
    for t in targets:
        study_target(t, out)
        rows, limits = calibrate(t, out, steps, sf)
        recommend(rows, limits, out)
        all_rows[t.name.split(" (")[0]] = rows
    out.append(f"\n{'=' * 78}\nCOMBINED\n{'=' * 78}")
    combine(all_rows, limits, out)
    txt = "\n".join(out)
    print(txt)
    if a.out:
        a.out.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

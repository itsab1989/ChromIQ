"""Build the Auto-align CHALLENGE SET.

Every case is generated to EXPOSE a shortcoming, not to demonstrate success.
Each folder gets:

    scan.tif      the image the tool is given
    chart.cht     the chart reference geometry (shared, except the mismatch cases)
    chart.cie     the measured reference (shared)
    truth.json    ground-truth corners of the patch area in scan.tif, if known
    NOTE.txt      what this case is, how it was made, what should happen

Usage:  python scripts/make_scan_align_demos.py <outdir>
"""
from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from workflow.layout_engine.cht_writer import build_cht_text  # noqa: E402

RNG = np.random.default_rng(20260903)
DPI = 300
PAPER = (210.0, 297.0)


# --------------------------------------------------------------------------
# The chart itself: engine-style, patches edge-to-edge, strip labels printed
# --------------------------------------------------------------------------
def chart_geometry(cols=20, rows=26, patch_mm=7.0, margin_mm=12.0, dpi=DPI):
    s = dpi / 25.4
    rects, colors = [], {}
    for c in range(cols):
        for r in range(rows):
            loc = f"{chr(65 + c)}{r + 1:02d}"
            rects.append({
                "loc": loc,
                "x": int(round((margin_mm + c * patch_mm) * s)),
                "y": int(round((margin_mm + r * patch_mm) * s)),
                "w": int(round(patch_mm * s)),
                "h": int(round(patch_mm * s))})
            i = c * rows + r
            n = 6
            rr = (i % n) * 255 // (n - 1)
            gg = ((i // n) % n) * 255 // (n - 1)
            bb = ((i // (n * n)) % n) * 255 // (n - 1)
            if i % 17 == 0:
                v = (i * 13) % 256
                rr = gg = bb = v
            colors[loc] = (rr, gg, bb)
    return rects, colors


def render_clean(rects, colors, dpi=DPI, paper=PAPER, labels=True):
    s = dpi / 25.4
    W, H = int(round(paper[0] * s)), int(round(paper[1] * s))
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for r in rects:
        d.rectangle([r["x"], r["y"], r["x"] + r["w"] - 1, r["y"] + r["h"] - 1],
                    fill=colors[r["loc"]])
    if labels:
        # engine-style strip labels under the patch area + a title line above
        x0 = min(r["x"] for r in rects)
        x1 = max(r["x"] + r["w"] for r in rects)
        y0 = min(r["y"] for r in rects)
        y1 = max(r["y"] + r["h"] for r in rects)
        d.text((x0, max(0, y0 - int(9 * s / 3))), "ChromIQ auto-align challenge chart",
               fill=(0, 0, 0))
        for c in sorted({r["x"] for r in rects}):
            d.text((c + 2, y1 + 4), "|", fill=(0, 0, 0))
        d.line([x0, y1 + int(3 * s), x1, y1 + int(3 * s)], fill=(0, 0, 0), width=2)
    return img


def truth_quad(rects):
    x0 = min(r["x"] for r in rects)
    x1 = max(r["x"] + r["w"] for r in rects)
    y0 = min(r["y"] for r in rects)
    y1 = max(r["y"] + r["h"] for r in rects)
    return [(float(x0), float(y0)), (float(x1), float(y0)),
            (float(x1), float(y1)), (float(x0), float(y1))]


def xyz(c):
    rr, gg, bb = [v / 255.0 for v in c]
    return (41.24 * rr + 35.76 * gg + 18.05 * bb,
            21.26 * rr + 71.52 * gg + 7.22 * bb,
            1.93 * rr + 11.92 * gg + 95.05 * bb)


def write_reference(out: Path, rects, colors, dpi=DPI):
    sc = 25.4 / dpi
    boxes = [{"loc": r["loc"], "x": r["x"] * sc, "y": r["y"] * sc,
              "w": r["w"] * sc, "h": r["h"] * sc} for r in rects]
    exp = [(b["loc"], *xyz(colors[b["loc"]])) for b in boxes]
    (out / "chart.cht").write_text(build_cht_text(boxes, exp), encoding="utf-8")
    cie = ["CGATS.17", "NUMBER_OF_FIELDS 4", "BEGIN_DATA_FORMAT",
           "SAMPLE_ID XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
           f"NUMBER_OF_SETS {len(exp)}", "BEGIN_DATA"]
    cie += [f"{l} {x:.4f} {y:.4f} {z:.4f}" for l, x, y, z in exp]
    cie += ["END_DATA", ""]
    (out / "chart.cie").write_text("\n".join(cie), encoding="utf-8")


# --------------------------------------------------------------------------
# scan degradations
# --------------------------------------------------------------------------
def scanify(img, blur=1.0, noise=0.015, seed=None):
    """Blur sigma 1 + 1.5% noise -- the values ChromIQ's own demo scans use
    (#108 beta.138/142, measured off real Epson scans)."""
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    if noise:
        rng = np.random.default_rng(seed if seed is not None else 1)
        a = np.asarray(img, np.float64)
        a += rng.normal(0.0, noise * 255.0, a.shape)
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    return img


def rotate(img, quad, deg):
    """Rotate about the image centre, expanding the canvas; map the quad."""
    w, h = img.size
    out = img.rotate(deg, resample=Image.BICUBIC, expand=True,
                     fillcolor=(255, 255, 255))
    ow, oh = out.size
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)

    def m(p):
        x, y = p[0] - w / 2, p[1] - h / 2
        return (x * ca + y * sa + ow / 2, -x * sa + y * ca + oh / 2)
    return out, [m(p) for p in quad]


def perspective(img, quad, kx, ky):
    """Keystone: push the top edge in by kx and the left edge down by ky
    (fractions of the image size)."""
    w, h = img.size
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    dst = [(w * kx, h * ky), (w * (1 - kx * 0.3), 0), (w, h), (0, h * (1 - ky * 0.3))]
    # PIL wants the inverse map (dst -> src)
    a = []
    b = []
    for (sx, sy), (dx, dy) in zip(src, dst):
        a.append([dx, dy, 1, 0, 0, 0, -sx * dx, -sx * dy])
        b.append(sx)
        a.append([0, 0, 0, dx, dy, 1, -sy * dx, -sy * dy])
        b.append(sy)
    coef = np.linalg.solve(np.asarray(a, float), np.asarray(b, float))
    out = img.transform((w, h), Image.PERSPECTIVE, coef, Image.BICUBIC,
                        fillcolor=(255, 255, 255))
    # forward map src -> dst for the quad
    fa = []
    fb = []
    for (sx, sy), (dx, dy) in zip(src, dst):
        fa.append([sx, sy, 1, 0, 0, 0, -dx * sx, -dx * sy])
        fb.append(dx)
        fa.append([0, 0, 0, sx, sy, 1, -dy * sx, -dy * sy])
        fb.append(dy)
    f = np.linalg.solve(np.asarray(fa, float), np.asarray(fb, float))

    def m(p):
        x, y = p
        d = f[6] * x + f[7] * y + 1.0
        return ((f[0] * x + f[1] * y + f[2]) / d, (f[3] * x + f[4] * y + f[5]) / d)
    return out, [m(p) for p in quad]


def barrel(img, quad, k):
    """Lens distortion, the way a phone camera bends a flat sheet."""
    w, h = img.size
    a = np.asarray(img, np.float64)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    cx, cy = w / 2.0, h / 2.0
    nx, ny = (xx - cx) / cx, (yy - cy) / cy
    r2 = nx * nx + ny * ny
    f = 1 + k * r2
    sx = np.clip((nx * f * cx + cx), 0, w - 1).astype(int)
    sy = np.clip((ny * f * cy + cy), 0, h - 1).astype(int)
    out = Image.fromarray(a[sy, sx].astype(np.uint8))

    def inv(p):
        # forward: source (nx,ny) lands at nx/f' ... solve numerically
        x, y = p
        u, v = (x - cx) / cx, (y - cy) / cy
        lo, hi = 0.0, 2.0
        for _ in range(60):
            mid = (lo + hi) / 2
            s = math.hypot(u, v) * mid
            if s * (1 + k * s * s) < math.hypot(u, v):
                lo = mid
            else:
                hi = mid
        t = (lo + hi) / 2
        return (u * t * cx + cx, v * t * cy + cy)
    return out, [inv(p) for p in quad]


def uneven_light(img, strength=0.35, angle=25.0):
    a = np.asarray(img, np.float64)
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    ang = math.radians(angle)
    g = (xx * math.cos(ang) + yy * math.sin(ang))
    g = (g - g.min()) / (g.max() - g.min())
    vig = 1.0 - strength * ((xx - w / 2) ** 2 / (w / 2) ** 2
                            + (yy - h / 2) ** 2 / (h / 2) ** 2) / 2.0
    f = (1.0 - strength * g) * vig
    return Image.fromarray(np.clip(a * f[..., None], 0, 255).astype(np.uint8))


def dust(img, n=400, seed=3):
    rng = np.random.default_rng(seed)
    d = ImageDraw.Draw(img)
    w, h = img.size
    for _ in range(n):
        x, y = rng.integers(0, w), rng.integers(0, h)
        r = int(rng.integers(1, 6))
        v = int(rng.integers(0, 60))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(v, v, v))
    for _ in range(12):                 # hairs
        x, y = rng.integers(0, w), rng.integers(0, h)
        d.line([x, y, x + int(rng.integers(-90, 90)), y + int(rng.integers(-90, 90))],
               fill=(30, 30, 30), width=1)
    return img


def cast(img, gains):
    a = np.asarray(img, np.float64) * np.asarray(gains, float)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def blow(img, gain=1.55):
    a = np.asarray(img, np.float64) * gain
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# --------------------------------------------------------------------------
def emit(root: Path, name: str, img, quad, note: str, rects, colors,
         dpi=DPI, bits=8, own_reference=None, painted=None):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    if bits == 16:
        a = (np.asarray(img, np.float64) / 255.0 * 65535.0).astype(np.uint16)
        try:
            import tifffile
            tifffile.imwrite(d / "scan.tif", a)
        except ImportError:
            Image.fromarray(a).save(d / "scan.tif")
    else:
        img.save(d / "scan.tif", compression="tiff_lzw")
    if own_reference is None:
        write_reference(d, rects, colors, dpi=DPI)
    else:
        write_reference(d, *own_reference, dpi=DPI)
    (d / "truth.json").write_text(json.dumps(
        {"corners": quad, "dpi": dpi, "bits": bits}, indent=1), encoding="utf-8")
    if painted is not False:
        (d / "colors.json").write_text(json.dumps(colors if painted is None
                                                  else painted), encoding="utf-8")
    (d / "NOTE.txt").write_text(note.strip() + "\n", encoding="utf-8")
    sz = sum(f.stat().st_size for f in d.iterdir())
    print(f"  {name:28s} {img.size[0]}x{img.size[1]}  {sz/1e6:6.2f} MB")
    return d


def main(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    rects, colors = chart_geometry()
    clean = render_clean(rects, colors)
    q0 = truth_quad(rects)
    base = scanify(clean)

    print("Building the challenge set in", root)

    emit(root, "01-baseline-300dpi", base, q0, """
BASELINE, not a challenge. 300 dpi, sigma-1 blur, 1.5 % noise -- the
degradation ChromIQ's own demo scans use, measured off real Epson scans.
EXPECT: auto-align succeeds, corners within a fraction of a patch.
""", rects, colors)

    for deg, nm in ((90, "02-rotated-90"), (180, "03-rotated-180"),
                    (270, "04-rotated-270")):
        im, q = rotate(base, q0, deg)
        emit(root, nm, im, q, f"""
Scan placed on the glass {deg} degrees round. scanin's default is to try all
four chart angles; the EXPECTED-value correlation is what picks between them.
EXPECT: either a correct alignment, or a refusal. A 180-degree mistake reads
every patch as the wrong one and is the single most dangerous failure here.
""", rects, colors)

    for deg, nm in ((2.0, "05-skew-2deg"), (5.0, "06-skew-5deg"),
                    (0.4, "07-skew-0.4deg")):
        im, q = rotate(base, q0, deg)
        emit(root, nm, im, q, f"""
Sheet laid on the glass {deg} degrees off square -- the everyday case.
EXPECT: success. calc_rotation fits a robust mean line angle, so this is the
condition the recogniser is built for.
""", rects, colors)

    for kx, nm in ((0.02, "08-perspective-2pct"), (0.06, "09-perspective-6pct")):
        im, q = perspective(base, q0, kx, kx)
        emit(root, nm, im, q, f"""
Keystone: the sheet is not parallel to the sensor, top edge pushed in by
{kx*100:.0f} % of the width. ChromIQ runs scanin WITHOUT -p on the manual
path (measured: -p aborts 23 % of honeycomb reads and changes nothing else),
so the auto stage runs without it too and must cope through the four-corner
homography alone.
EXPECT: success at 2 %; 6 % is meant to break it. A refusal is the right
answer if the fit is poor.
""", rects, colors)

    # crop that loses an edge
    w, h = base.size
    x0, y0 = int(q0[0][0]), int(q0[0][1])
    x1, y1 = int(q0[2][0]), int(q0[2][1])
    cut = base.crop((0, 0, x1 - 40, h))
    emit(root, "10-crop-loses-right-edge", cut,
         [(p[0], p[1]) for p in q0], """
The scan lid was closed on a sheet wider than the glass: the right-hand
column of patches is cut off mid-patch.
EXPECT: a REFUSAL. The chart in the image is not the chart the .cht
describes, and any alignment found would silently read 20 wrong columns.
Ground truth here is the ORIGINAL quad -- it is not reachable, on purpose.
""", rects, colors)

    cut2 = base.crop((0, 0, w, y1 - 30))
    emit(root, "11-crop-loses-bottom", cut2, [(p[0], p[1]) for p in q0], """
Same idea on the other axis: the bottom row is cut through.
EXPECT: a refusal, for the same reason.
""", rects, colors)

    # dpi ladder
    for dpi, nm in ((150, "12-dpi-150"), (600, "13-dpi-600"), (1200, "14-dpi-1200")):
        f = dpi / DPI
        im = clean.resize((int(clean.width * f), int(clean.height * f)),
                          Image.BICUBIC)
        im = scanify(im, blur=max(0.5, 1.0 * f))
        q = [(p[0] * f, p[1] * f) for p in q0]
        emit(root, nm, im, q, f"""
The same chart scanned at {dpi} dpi. ChromIQ's own guidance is 600 ok,
1200 preferred, 300 too coarse; 150 is below anything sensible and is here to
find the floor. Per-pixel noise is flat across dpi, so higher dpi helps
REGISTRATION, not noise (measured, #108).
EXPECT: success from 300 up. 150 may fail; it should fail loudly.
""", rects, colors, dpi=dpi)

    emit(root, "15-sixteen-bit", base, q0, """
The identical baseline written as a 16-bit-per-channel TIFF. Qt's 256 MB
image allocation limit once nulled 16-bit A4 scans outright (#108 beta.114),
which is exactly how a silent misalignment got shipped before.
EXPECT: identical result to 01. Any difference is a bug in the reading path,
not in the alignment.
""", rects, colors, bits=16)

    emit(root, "16-colour-cast", scanify(cast(clean, (1.18, 1.0, 0.80))), q0, """
Warm colour cast, the kind an uncalibrated CCD lamp gives.
EXPECT: success. Recognition works off EDGES; the expected-value correlation
that picks the rotation is rank-based enough to survive a channel gain.
""", rects, colors)

    emit(root, "17-blown-highlight", scanify(blow(clean, 1.55)), q0, """
Exposure pushed until the light patches clip to paper white -- a whole
region of the chart becomes indistinguishable from the margin.
EXPECT: this is meant to hurt. Success is fine; a confident WRONG answer is
the failure to look for.
""", rects, colors)

    emit(root, "18-dark-scan", scanify(cast(clean, (0.38, 0.38, 0.38))), q0, """
Badly under-exposed scan: the whole sheet at 38 % brightness, so the
patch-to-patch steps that the edge detector needs are compressed.
EXPECT: success or a refusal.
""", rects, colors)

    emit(root, "19-dust-and-hairs", scanify(dust(render_clean(rects, colors))), q0, """
400 dust specks and a dozen hairs on the glass, some of them across patch
borders, plus the usual blur and noise.
EXPECT: success. Argyll's group detector ignores small blobs; ChromIQ's own
edge check separately treats 1-2 hot sub-cells as dust.
""", rects, colors)

    emit(root, "20-heavy-noise", scanify(clean, blur=1.0, noise=0.06, seed=9), q0, """
Four times the noise of a real scan (6 % vs the measured 1.5 %).
EXPECT: a refusal is an acceptable answer here.
""", rects, colors)

    # photographed
    ph, qph = barrel(scanify(clean, blur=1.4), q0, 0.12)
    ph = uneven_light(ph, 0.40, 25.0)
    ph, qph = rotate(ph, qph, 1.6)
    emit(root, "21-photographed", ph, qph, """
Photographed rather than scanned: 12 % barrel distortion, a 40 % lighting
gradient plus vignetting, 1.6 degrees of hand shake, softer optics.
EXPECT: this is the case most likely to fail. A homography cannot express
barrel distortion at all, so even a perfect corner fit leaves the middle of
the chart bowed. A refusal is the correct outcome; a confident acceptance is
a real fault.
""", rects, colors)

    ph2, qph2 = barrel(scanify(clean, blur=1.2), q0, 0.04)
    ph2 = uneven_light(ph2, 0.22, 25.0)
    emit(root, "22-photographed-mild", ph2, qph2, """
The same idea within reason: 4 % barrel, 22 % lighting gradient, no shake.
EXPECT: success, or a refusal. Not a wrong answer.
""", rects, colors)

    # wrong chart for the reference
    other_rects, other_colors = chart_geometry(cols=16, rows=22, patch_mm=8.0)
    other = scanify(render_clean(other_rects, other_colors))
    emit(root, "23-wrong-chart", other, truth_quad(other_rects), """
A DIFFERENT chart (16x22 of 8 mm patches) handed in with the 20x26 / 7 mm
reference. This is the case that decides whether the feature is safe: there
is no correct answer, so anything except a refusal is a silent wrong read.
EXPECT: refusal.
""", rects, colors, painted=False)

    # two charts on one sheet
    two = Image.new("RGB", (clean.width, clean.height), (255, 255, 255))
    small = clean.resize((clean.width // 2, clean.height // 2), Image.BICUBIC)
    two.paste(small, (30, 30))
    two.paste(small, (clean.width // 2 - 10, clean.height // 2 + 40))
    two = scanify(two)
    q2 = [(p[0] / 2 + 30, p[1] / 2 + 30) for p in q0]
    emit(root, "24-two-charts-one-sheet", two, q2, """
Two copies of the chart on one sheet, at half size, overlapping in neither
row nor column band. The recogniser has to choose one, and either choice
reads correctly only if the .cht scale matches.
EXPECT: a refusal, or a correct lock onto ONE of them. Ground truth is the
upper-left copy; locking onto the lower-right one counts as a refusal-grade
outcome, not a success.
""", rects, colors, painted=False)

    # damaged registration: paint out a corner of the patch area
    dmg = render_clean(rects, colors)
    dd = ImageDraw.Draw(dmg)
    dd.rectangle([q0[1][0] - 260, q0[1][1] - 30, q0[1][0] + 30, q0[1][1] + 260],
                 fill=(255, 255, 255))
    emit(root, "25-damaged-corner", scanify(dmg), q0, """
The top-right corner of the patch area is missing -- a torn sheet, or a
print head that ran dry. ChromIQ charts carry no separate registration
marks, so the patch block's own corner IS the registration.
EXPECT: success (the edge lists are global, not corner-based) or a refusal.
""", rects, colors)

    fold = render_clean(rects, colors)
    fd = ImageDraw.Draw(fold)
    fd.line([0, int(q0[0][1]) + 700, clean.width, int(q0[0][1]) + 760],
            fill=(90, 90, 90), width=9)
    emit(root, "26-fold-line", scanify(fold), q0, """
A crease across the sheet: a grey line straight through the middle of a row
of patches, which the edge detector will see as a very strong horizontal
feature that belongs to no patch boundary.
EXPECT: success or refusal.
""", rects, colors)

    print("done")


if __name__ == "__main__":
    main(Path(sys.argv[1]))

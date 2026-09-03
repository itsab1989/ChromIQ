"""Cases 32-38: PHOTOGRAPHS, which are a different problem from scans.

A scan is flat, evenly lit, at a known resolution, with the chart filling the
frame. A photo has perspective, lens distortion, uneven light and shadow, an
unknown scale, and OTHER THINGS IN THE FRAME. These are the cases where a
detector confidently finds the wrong quadrilateral.

Each folder also carries `region.json`: the rough rectangle a user would drag
round the chart (the chart's bounding box grown by 12 % and jittered, so it is
loose the way a hand-drawn one is), for measuring whether narrowing the search
rescues the case.
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np                                            # noqa: E402
from PIL import Image, ImageDraw, ImageFilter                 # noqa: E402
from make_scan_align_demos import (barrel, chart_geometry, emit, perspective,  # noqa: E402
                       render_clean, rotate, scanify, truth_quad,
                       uneven_light)

RNG = random.Random(11)


def clutter(img, quad, n=14, seed=5):
    """Desk junk around the sheet: paper, a ruler, tools, a phone."""
    rng = random.Random(seed)
    d = ImageDraw.Draw(img)
    w, h = img.size
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    keep = (min(xs) - 20, min(ys) - 20, max(xs) + 20, max(ys) + 20)
    placed = 0
    tries = 0
    while placed < n and tries < 400:
        tries += 1
        bw = rng.randint(w // 12, w // 3)
        bh = rng.randint(h // 22, h // 5)
        x = rng.randint(0, max(1, w - bw))
        y = rng.randint(0, max(1, h - bh))
        if not (x + bw < keep[0] or x > keep[2] or y + bh < keep[1] or y > keep[3]):
            continue
        col = (rng.randint(30, 235), rng.randint(30, 235), rng.randint(30, 235))
        if rng.random() < 0.4:
            col = (rng.randint(150, 250),) * 3          # white-ish paper
        d.rectangle([x, y, x + bw, y + bh], fill=col,
                    outline=(60, 60, 60), width=2)
        if rng.random() < 0.35:                          # a ruled/gridded thing
            for k in range(0, bw, max(6, bw // 14)):
                d.line([x + k, y, x + k, y + bh], fill=(90, 90, 90), width=1)
        placed += 1
    return img


def desk(img, quad, tone=(120, 105, 90)):
    """Put the sheet on a desk instead of on a scanner bed."""
    w, h = img.size
    big = Image.new("RGB", (int(w * 1.7), int(h * 1.45)), tone)
    a = np.asarray(big, np.float64)
    rng = np.random.default_rng(2)
    a += rng.normal(0, 6, a.shape)
    big = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    ox, oy = int(w * 0.32), int(h * 0.2)
    big.paste(img, (ox, oy))
    return big, [(p[0] + ox, p[1] + oy) for p in quad]


def shadow(img, frac=0.45, depth=0.55):
    a = np.asarray(img, np.float64)
    h, w = a.shape[:2]
    xx = np.arange(w)[None, :]
    edge = w * frac
    f = np.where(xx < edge, 1.0 - depth * (1.0 - xx / edge), 1.0)
    f = np.repeat(f, h, axis=0)
    soft = Image.fromarray((f * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(w * 0.05))
    f = np.asarray(soft, np.float64) / 255.0
    return Image.fromarray(np.clip(a * f[..., None], 0, 255).astype(np.uint8))


def rough_region(quad, size, grow=0.12, jitter=0.05, seed=7):
    rng = random.Random(seed)
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    x0 = min(xs) - w * (grow + rng.uniform(-jitter, jitter))
    x1 = max(xs) + w * (grow + rng.uniform(-jitter, jitter))
    y0 = min(ys) - h * (grow + rng.uniform(-jitter, jitter))
    y1 = max(ys) + h * (grow + rng.uniform(-jitter, jitter))
    return [max(0.0, x0), max(0.0, y0),
            min(float(size[0]), x1), min(float(size[1]), y1)]


def emit_photo(root, name, img, quad, note, rects, colors):
    d = emit(root, name, img, quad, note, rects, colors)
    (d / "region.json").write_text(json.dumps(
        {"rough": rough_region(quad, img.size)}, indent=1), encoding="utf-8")
    return d


def main(root: Path):
    rects, colors = chart_geometry()
    clean = render_clean(rects, colors)
    q0 = truth_quad(rects)

    # 32 handheld, keystone + a little barrel + shake
    im, q = perspective(scanify(clean, blur=1.3), q0, 0.035, 0.03)
    im, q = barrel(im, q, 0.05)
    im, q = rotate(im, q, 2.2)
    im = uneven_light(im, 0.28, 20.0)
    emit_photo(root, "32-photo-handheld", im, q, """
Handheld photograph: 3.5 % keystone, 5 % barrel distortion, 2.2 degrees of
shake, a 28 % lighting gradient. Nothing else in the frame.
EXPECT: this is the baseline photograph. Success or a refusal, not a wrong
answer.
""", rects, colors)

    # 33 on a desk with things around it
    im, q = desk(scanify(clean, blur=1.3), q0)
    im, q = perspective(im, q, 0.03, 0.025)
    im = clutter(im, q, n=16)
    im = uneven_light(im, 0.3, 35.0)
    emit_photo(root, "33-photo-cluttered-desk", im, q, """
The chart on a desk with sixteen other rectangular things round it -- paper,
a ruled pad, tools, a phone. This is the case the owner asked about by name:
other elements in the frame that might confuse the detection.
EXPECT: the interesting one. If the recogniser locks onto a notebook instead of
the chart, the checks must catch it. `region.json` holds a rough rectangle
round the chart for measuring whether narrowing the search rescues it.
""", rects, colors)

    # 34 mixed lighting, one side in shadow
    im, q = desk(scanify(clean, blur=1.2), q0)
    im = shadow(im, 0.45, 0.6)
    emit_photo(root, "34-photo-half-in-shadow", im, q, """
One side of the sheet in shadow, 60 % down at the edge, softly graded. Nothing
else in the frame. The patches on the dark side read as much darker versions of
themselves, which is what a page-wide response model is supposed to absorb.
EXPECT: success or refusal.
""", rects, colors)

    # 35 at a real angle
    im, q = perspective(scanify(clean, blur=1.3), q0, 0.10, 0.08)
    im, q = desk(im, q)
    im = uneven_light(im, 0.3, 15.0)
    emit_photo(root, "35-photo-steep-angle", im, q, """
Photographed from well off to one side: 10 % keystone. A homography CAN express
keystone exactly -- but the affine scanin prints cannot, and ChromIQ runs the
recogniser without -p for measured reasons.
EXPECT: a refusal is the honest answer. A rough selection does not fix a
projective problem, so this case also tests whether the fallback oversells.
""", rects, colors)

    # 36 something else colourful in the frame
    im, q = desk(scanify(clean, blur=1.3), q0)
    d = ImageDraw.Draw(im)
    bw = int(im.width * 0.22)
    bh = int(im.height * 0.30)
    bx, by = int(im.width * 0.03), int(im.height * 0.55)
    for i in range(6):
        for j in range(8):
            d.rectangle([bx + i * bw // 6, by + j * bh // 8,
                         bx + (i + 1) * bw // 6, by + (j + 1) * bh // 8],
                        fill=(40 + i * 35, 200 - j * 22, 60 + j * 20))
    emit_photo(root, "36-photo-second-colour-grid", im, q, """
A SECOND grid of colour patches in the frame, smaller and unrelated -- a paint
swatch card, a colour wheel, another target. The recogniser has two grids to
choose from and only one of them is this chart.
EXPECT: it must not read the wrong grid. This is the sharpest version of the
owner's question.
""", rects, colors)

    # 37 chart small in a large frame
    small = scanify(clean, blur=1.2).resize(
        (clean.width // 3, clean.height // 3), Image.BICUBIC)
    qs = [(p[0] / 3, p[1] / 3) for p in q0]
    im, q = desk(small, qs, tone=(150, 148, 145))
    im = clutter(im, q, n=10, seed=9)
    im = uneven_light(im, 0.25, 40.0)
    emit_photo(root, "37-photo-chart-small-in-frame", im, q, """
The chart occupies about a fifth of the frame, with clutter round it. Patches
are ~28 px across instead of ~83.
EXPECT: this is where a rough selection should help most, because the search
space is mostly not-the-chart.
""", rects, colors)

    # 38 a clean photo, no clutter, mild everything -- the best case
    im, q = perspective(scanify(clean, blur=1.2), q0, 0.015, 0.012)
    im = uneven_light(im, 0.18, 25.0)
    emit_photo(root, "38-photo-careful", im, q, """
A careful photograph: square-on to the sheet, 1.5 % residual keystone, gentle
lighting gradient, no clutter. The best a phone on a tripod would do.
EXPECT: success. If this one fails, photographs are out of reach altogether.
""", rects, colors)
    print("done")


if __name__ == "__main__":
    main(Path(sys.argv[1]))

#!/usr/bin/env python3
"""Generate A3 i1Pro test charts whose patches secretly spell a word (pixel art).

These are *screenshot props*, not real profiling targets: they look like an
ordinary non-randomised ArgyllCMS chart (a field of OFPS colour patches with
B&W reader spacers), except a block of patches in the middle spells a word in
black-on-white "pixel art".

How it works
------------
* On A3, ``printtarg -ii1 -L -P`` lays patches out in a fixed **35 strips x 35
  patches = 1225** grid. Strips are vertical columns (A..AI, left->right);
  position runs top->bottom within a column.
* With ``-r`` (don't randomise) the .ti1 data order maps straight onto that
  grid: data index ``col*35 + row``. So we let ``targen`` build a real
  1225-patch .ti1 (authentic colours + valid 3-table structure), then rewrite
  only the table-1 RGB values: keep targen's colours everywhere, paint a white
  "card" in the middle, and stamp black letter-patches onto it.
* ``-b`` (black/white spacers, not the default coloured ones) keeps the reader
  spacers from slicing the letters with garish colour — letters stay readable
  and the sheet still looks like a legitimate i1 chart.

Usage
-----
    python scripts/make_screenshot_charts.py [-o OUTDIR] [--dpi 300]
    python scripts/make_screenshot_charts.py --word Hello --name hello

With no ``--word`` it builds the two defaults: ChromIQ and Argyll.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ARGYLL = "/Applications/Argyll/bin"
N = 35  # A3 / i1 / -L / -P grid is N strips x N patches
FONT = "/System/Library/Fonts/Supplemental/Arial Black.ttf"  # heavy -> crisp at low res


# --------------------------------------------------------------------------- #
# Text -> boolean pixel mask
# --------------------------------------------------------------------------- #
def word_mask(word: str, wmax: int, hmax: int) -> list[list[bool]]:
    """Render *word* to a crisp boolean mask (rows x cols), fit within wmax/hmax."""
    big = ImageFont.truetype(FONT, 400)
    bb = big.getbbox(word)
    img = Image.new("L", (bb[2] - bb[0] + 40, bb[3] - bb[1] + 40), 0)
    ImageDraw.Draw(img).text((20 - bb[0], 20 - bb[1]), word, fill=255, font=big)
    img = img.crop(img.getbbox())
    s = min(wmax / img.width, hmax / img.height)
    small = img.resize(
        (max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS
    )
    px = small.load()
    return [[px[c, r] >= 110 for c in range(small.width)] for r in range(small.height)]


# --------------------------------------------------------------------------- #
# sRGB (0..100) -> XYZ (0..100), D65. Only cosmetic — the .ti2 carries it.
# --------------------------------------------------------------------------- #
def srgb_to_xyz(r: float, g: float, b: float) -> tuple[float, float, float]:
    def lin(c: float) -> float:
        c /= 100.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    R, G, B = lin(r), lin(g), lin(b)
    X = (0.4124 * R + 0.3576 * G + 0.1805 * B) * 100
    Y = (0.2126 * R + 0.7152 * G + 0.0722 * B) * 100
    Z = (0.0193 * R + 0.1192 * G + 0.9505 * B) * 100
    return X, Y, Z


# --------------------------------------------------------------------------- #
# .ti1 table-1 read / rewrite
# --------------------------------------------------------------------------- #
def _table1_bounds(lines: list[str]) -> tuple[int, int]:
    bi = ei = None
    for i, l in enumerate(lines):
        if l.strip() == "BEGIN_DATA" and bi is None:
            bi = i
        elif l.strip() == "END_DATA" and bi is not None:
            ei = i
            break
    if bi is None or ei is None:
        raise ValueError("no BEGIN_DATA/END_DATA table in .ti1")
    return bi, ei


def read_base_rgb(path: Path) -> tuple[list[str], int, int, list[tuple[float, float, float]]]:
    lines = path.read_text(encoding="utf-8").split("\n")
    bi, ei = _table1_bounds(lines)
    rgb = [
        (float(p[1]), float(p[2]), float(p[3]))
        for p in (row.split() for row in lines[bi + 1 : ei])
    ]
    return lines, bi, ei, rgb


def write_ti1(lines, bi, ei, colors, dst: Path) -> None:
    out = []
    for row, (R, G, B) in zip(lines[bi + 1 : ei], colors):
        sid = row.split()[0]
        X, Y, Z = srgb_to_xyz(R, G, B)
        out.append(f"{sid} {R:.5f} {G:.5f} {B:.5f} {X:.4f} {Y:.4f} {Z:.4f} ")
    dst.write_text("\n".join(lines[: bi + 1] + out + lines[ei:]), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Build one chart
# --------------------------------------------------------------------------- #
def build(word: str, name: str, outdir: Path, dpi: int, wmax: int, hmax: int, pad: int) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    # Run the tools *inside* outdir with bare stems so the name printtarg stamps
    # onto the sheet (and the output filenames) is the clean chart name, not a path.
    base = f"{name}_base"

    subprocess.run(
        [f"{ARGYLL}/targen", "-d2", f"-f{N*N}", base],
        cwd=outdir, check=True, capture_output=True,
    )
    lines, bi, ei, bg = read_base_rgb(outdir / f"{base}.ti1")

    mask = word_mask(word, wmax, hmax)
    mh, mw = len(mask), len(mask[0])
    cw, ch = mw + 2 * pad, mh + 2 * pad
    c0, r0 = (N - cw) // 2, (N - ch) // 2
    if c0 < 0 or r0 < 0:
        raise SystemExit(f"'{word}' mask {mw}x{mh}+pad doesn't fit {N}x{N}; lower wmax/hmax")

    # grid[row][col]; start from targen's real colours (authentic chart look)
    grid = [[bg[c * N + r] for c in range(N)] for r in range(N)]
    for rr in range(ch):                       # white card
        for cc in range(cw):
            grid[r0 + rr][c0 + cc] = (100.0, 100.0, 100.0)
    for r in range(mh):                        # black letter patches
        for c in range(mw):
            if mask[r][c]:
                grid[r0 + pad + r][c0 + pad + c] = (0.0, 0.0, 0.0)

    # back to .ti1 data order (column-major: index = col*N + row)
    colors = [grid[r][c] for c in range(N) for r in range(N)]
    write_ti1(lines, bi, ei, colors, outdir / f"{name}.ti1")

    subprocess.run(
        [f"{ARGYLL}/printtarg", "-ii1", "-pA3", "-L", "-P", "-r", "-b", f"-t{dpi}", name],
        cwd=outdir, check=True, capture_output=True,
    )
    (outdir / f"{base}.ti1").unlink(missing_ok=True)
    tifs = sorted(outdir.glob(f"{name}*.tif"))
    print(f"  {word!r:12} -> {', '.join(t.name for t in tifs)}  (letters {mw}x{mh})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--outdir", default="screenshot_charts", type=Path)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--word", help="single custom word (else builds ChromIQ + Argyll)")
    ap.add_argument("--name", help="output stem for --word (default: lowercased word)")
    ap.add_argument("--wmax", type=int, default=31, help="max letter-block width in patches")
    ap.add_argument("--hmax", type=int, default=6, help="max letter-block height in patches")
    ap.add_argument("--pad", type=int, default=2, help="white card padding in patches")
    args = ap.parse_args()

    if not Path(ARGYLL, "printtarg").exists():
        print(f"ArgyllCMS not found at {ARGYLL}", file=sys.stderr)
        return 1

    jobs = ([(args.word, args.name or args.word)]
            if args.word else [("ChromIQ", "ChromIQ"), ("Argyll", "Argyll")])
    print(f"Writing A3 i1Pro pixel-art charts to {args.outdir}/  @ {args.dpi} dpi")
    for word, name in jobs:
        build(word, name, args.outdir, args.dpi, args.wmax, args.hmax, args.pad)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

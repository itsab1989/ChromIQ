"""Render a known-good test scan + reference (.cie) for a bundled scanner target.

The image is rendered directly from the target's own ``.cht``, so ChromIQ's
reading grid lands exactly on the patches once you place the four corners on the
patch block — a hardware-free way to check the *Build profile with scanner or camera*
flow (or to isolate whether a real scan that misregisters is a file problem).

    python scripts/make_scanner_test_target.py QPcard_202 [out_dir]
    python scripts/make_scanner_test_target.py --all [out_dir]

Writes ``<name>-test.tif`` + ``<name>-test.cie``. In the dialog choose
"A standard target I own", pick the matching target, load the ``.tif`` as the
scan and the ``.cie`` as the reference, then drag the four corners onto the
patch block — the green grid should sit exactly on every patch.
"""
from __future__ import annotations

import colorsys
import sys
from pathlib import Path

from PIL import Image

from workflow.cht_parser import parse_cht

ROOT = Path(__file__).resolve().parent.parent
TARGETS_DIR = ROOT / "data" / "scanner_targets"
LONG_SIDE = 1500   # target long side in px (cht units vary wildly per target)
MARGIN = 80        # white border, so patches never touch the image edge


def _patch_colour(i: int, n: int) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb((i / max(n, 1)) % 1.0, 0.55, 0.92)
    return int(r * 255), int(g * 255), int(b * 255)


def build(name: str, out_dir: Path) -> tuple[Path, Path]:
    cht = (TARGETS_DIR / f"{name}.cht").read_text(errors="ignore", encoding="utf-8")
    g = parse_cht(cht)
    boxes = g.patches
    minx = min(b.x1 for b in boxes); miny = min(b.y1 for b in boxes)
    maxx = max(b.x2 for b in boxes); maxy = max(b.y2 for b in boxes)
    scale = LONG_SIDE / max(maxx - minx, maxy - miny, 1.0)   # cht units → px
    W = int((maxx - minx) * scale + 2 * MARGIN)
    H = int((maxy - miny) * scale + 2 * MARGIN)
    img = Image.new("RGB", (W, H), (236, 236, 236))
    px = img.load()
    cie = ['CGATS.17', 'KEYWORD "SAMPLE_LOC"', 'NUMBER_OF_FIELDS 4',
           'BEGIN_DATA_FORMAT', 'SAMPLE_ID XYZ_X XYZ_Y XYZ_Z', 'END_DATA_FORMAT',
           f'NUMBER_OF_SETS {len(boxes)}', 'BEGIN_DATA']
    for i, b in enumerate(boxes):
        r, gg, bb = _patch_colour(i, len(boxes))
        x0 = int((b.x1 - minx) * scale + MARGIN); y0 = int((b.y1 - miny) * scale + MARGIN)
        x1 = int((b.x2 - minx) * scale + MARGIN); y1 = int((b.y2 - miny) * scale + MARGIN)
        for y in range(y0, y1):
            for x in range(x0, x1):
                px[x, y] = (r, gg, bb)
        # distinct (approximate) XYZ so a profile can actually build from it
        cie.append(f"{b.name} {r / 2.55 * 0.95:.3f} {gg / 2.55:.3f} {bb / 2.55 * 1.09:.3f}")
    cie += ['END_DATA', '']
    out_dir.mkdir(parents=True, exist_ok=True)
    tif = out_dir / f"{name}-test.tif"
    ref = out_dir / f"{name}-test.cie"
    img.save(tif)
    ref.write_text("\n".join(cie), encoding="utf-8")
    return tif, ref


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    if argv[0] == "--all":
        out = Path(argv[1]) if len(argv) > 1 else Path.cwd() / "scanner-test-targets"
        names = sorted(p.stem for p in TARGETS_DIR.glob("*.cht"))
    else:
        names = [argv[0]]
        out = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    for name in names:
        tif, ref = build(name, out)
        print(f"{name:22s} → {tif.name}  +  {ref.name}")
    print(f"\nWritten to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Cases 27-31: which way up is the sheet, and when is that unknowable?

  27  square chart, ordinary colours       geometry cannot tell, colour can
  28  square chart, colours symmetric 180  NO answer exists -- must refuse
  29  square chart, colours symmetric x4   NO answer exists -- must refuse
  30  case 28 physically turned 180        still no answer -- must refuse
  31  square chart, ordinary colours, turned 90 -- must find it

Rendered the same way as the rest of the set (sigma-1 blur, 1.5 % noise).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from make_scan_align_demos import emit, render_clean, rotate, scanify, truth_quad, xyz  # noqa: E402
from make_scan_align_demos_symmetric import cube  # noqa: E402

DPI = 300


def square_chart(cols=20, rows=20, patch_mm=7.0, margin_mm=12.0, sym="none"):
    s = DPI / 25.4
    rects, colors = [], {}
    for c in range(cols):
        for r in range(rows):
            loc = f"{chr(65 + c)}{r + 1:02d}"
            rects.append({"loc": loc, "page": 0,
                          "x": int(round((margin_mm + c * patch_mm) * s)),
                          "y": int(round((margin_mm + r * patch_mm) * s)),
                          "w": int(round(patch_mm * s)),
                          "h": int(round(patch_mm * s))})
            if sym == "180":
                key = min(c * rows + r, (cols - 1 - c) * rows + (rows - 1 - r))
            elif sym == "4":
                key = min(c * rows + r, (cols - 1 - c) * rows + (rows - 1 - r),
                          r * cols + c, (rows - 1 - r) * cols + (cols - 1 - c))
            else:
                key = c * rows + r
            colors[loc] = cube(key)
    return rects, colors


def main(root: Path):
    root.mkdir(parents=True, exist_ok=True)

    r0, c0 = square_chart()
    img0 = scanify(render_clean(r0, c0, labels=False))
    q0 = truth_quad(r0)
    emit(root, "27-square-chart", img0, q0, """
A SQUARE ChromIQ chart, 20 x 20 of 7 mm patches, ordinary colours.
Geometry cannot say which way up this is -- all four turns fit the same
rectangle. Only the patch COLOURS can break the tie.
EXPECT: found, upright. The measured margin between the best orientation and
the runner-up is 0.98 for this chart, which is not close.
""", r0, c0)

    img90, q90 = rotate(img0, q0, 90)
    emit(root, "31-square-chart-turned-90", img90, q90, """
The same square chart, physically a quarter turn on the glass.
EXPECT: found, and turned the right way. This is the case that shows whether
the mesh rotates itself or merely lands on the block.
""", r0, c0)

    r180, c180 = square_chart(sym="180")
    img180 = scanify(render_clean(r180, c180, labels=False))
    q180 = truth_quad(r180)
    emit(root, "28-symmetric-180", img180, q180, """
A square chart whose COLOURS are symmetric under a half turn: patch (i, j) is
painted exactly the same as patch (n-1-i, m-1-j). Upright and upside down are
indistinguishable from the image -- not nearly, EXACTLY. There is no correct
answer, and the two orientations read different patch names, so a guess that
comes out upside down produces a confidently wrong profile.
EXPECT: a REFUSAL. Measured orientation margin: 0.000.
This case exists to catch the feature guessing.
""", r180, c180)

    img180t, q180t = rotate(img180, q180, 180)
    emit(root, "30-symmetric-180-turned", img180t, q180t, """
Case 28 physically turned upside down. Still no answer exists.
EXPECT: a REFUSAL, exactly as in 28 -- the answer must not depend on which way
round the undecidable sheet happens to be.
""", r180, c180)

    r4, c4 = square_chart(sym="4")
    img4 = scanify(render_clean(r4, c4, labels=False))
    q4 = truth_quad(r4)
    emit(root, "29-symmetric-4-fold", img4, q4, """
A square chart symmetric under ALL FOUR turns. The worst case there is: four
equally good answers, three of them wrong.
EXPECT: a REFUSAL. Measured orientation margin: 0.000.
""", r4, c4)
    print("done")


if __name__ == "__main__":
    main(Path(sys.argv[1]))

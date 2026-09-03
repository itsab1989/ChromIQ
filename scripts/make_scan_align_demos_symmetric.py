"""Charts built to have NO answer, so the rotation check can be caught guessing.

  chromiq-20x26       an ordinary ChromIQ chart: rectangular, colour-cube walk
  chromiq-20x20       square, so geometry cannot tell 90 from 0 -- only colour can
  chromiq-sym180      square AND the colours are symmetric under 180 degrees:
                      patch (i,j) is painted the same as patch (n-1-i, m-1-j)
  chromiq-sym4        square AND symmetric under all four turns

The last two have no correct answer. Anything except a refusal is a guess.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from workflow.layout_engine.cht_writer import build_cht_text   # noqa: E402


def cube(i, n=6):
    r = (i % n) * 255 // (n - 1)
    g = ((i // n) % n) * 255 // (n - 1)
    b = ((i // (n * n)) % n) * 255 // (n - 1)
    return (r, g, b)


def build(out: Path, name: str, cols: int, rows: int, sym: str = "none",
          patch_mm: float = 7.0):
    boxes, colors = [], {}
    for c in range(cols):
        for r in range(rows):
            loc = f"{chr(65 + c)}{r + 1:02d}"
            boxes.append({"loc": loc, "x": c * patch_mm, "y": r * patch_mm,
                          "w": patch_mm, "h": patch_mm})
            if sym == "180":
                key = min(c * rows + r, (cols - 1 - c) * rows + (rows - 1 - r))
            elif sym == "4":
                key = min(c * rows + r, (cols - 1 - c) * rows + (rows - 1 - r),
                          r * cols + c, (rows - 1 - r) * cols + (cols - 1 - c))
            else:
                key = c * rows + r
            colors[loc] = cube(key)

    def xyz(v):
        rr, gg, bb = [x / 255.0 for x in v]
        return (41.24 * rr + 35.76 * gg + 18.05 * bb,
                21.26 * rr + 71.52 * gg + 7.22 * bb,
                1.93 * rr + 11.92 * gg + 95.05 * bb)
    exp = [(b["loc"], *xyz(colors[b["loc"]])) for b in boxes]
    d = out / name
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.cht").write_text(build_cht_text(boxes, exp), encoding="utf-8")
    cie = ["CGATS.17", "NUMBER_OF_FIELDS 4", "BEGIN_DATA_FORMAT",
           "SAMPLE_ID XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
           f"NUMBER_OF_SETS {len(exp)}", "BEGIN_DATA"]
    cie += [f"{l} {x:.4f} {y:.4f} {z:.4f}" for l, x, y, z in exp]
    cie += ["END_DATA", ""]
    (d / f"{name}.cie").write_text("\n".join(cie), encoding="utf-8")
    print(f"  {name}: {len(boxes)} patches, {cols}x{rows}, symmetry {sym}")
    return d / f"{name}.cht"


if __name__ == "__main__":
    out = Path(sys.argv[1])
    build(out, "chromiq-20x26", 20, 26)
    build(out, "chromiq-20x20", 20, 20)
    build(out, "chromiq-sym180", 20, 20, sym="180")
    build(out, "chromiq-sym4", 20, 20, sym="4")

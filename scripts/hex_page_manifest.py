#!/usr/bin/env python3
"""Hash every rendered page of a hexagon matrix, so pooling can be proved inert.

Run on the tree BEFORE a change and again AFTER, then `diff` the two manifests.
A single differing line is a pixel that moved.

BYTES, NOT GEOMETRY ROWS, and the distinction is the whole point. `raster.py`
is the only hexagon site whose output reaches ink, and it is the only one that
rounds its vertices. A pooled function that returns ints for everybody would
leave every geometry-row assertion in the suite green while moving the Measure
overlay half a pixel and the printed page not at all. Only the page bytes see
the renderer's rounding, and only the equivalence test in
`tests/test_the_hexagon_is_drawn_from_one_place.py` sees the Qt paths. Both are
needed; neither substitutes for the other.

    python scripts/hex_page_manifest.py > before.txt
    ...apply the change...
    python scripts/hex_page_manifest.py > after.txt
    diff before.txt after.txt && echo "not one pixel moved"
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np                                          # noqa: E402

from workflow.layout_engine import chart as le_chart        # noqa: E402

PAPERS = ("A4", "A4R", "A3", "Letter")


def _ti1(path: Path, n: int) -> Path:
    lines = ["CTI1", "", 'DESCRIPTOR "hex manifest"', 'ORIGINATOR "ChromIQ"',
             'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(n):
        # A SPREAD OF COLOURS, not one flat grey: the contrast spacer picks its
        # fill from the pair it sits between, so a flat sheet would render every
        # spacer the same colour and hide a change in that path.
        r = (i * 37) % 101
        g = (i * 71) % 101
        b = (i * 13) % 101
        lines.append(f"{i+1} {r}.0 {g}.0 {b}.0 40.0 45.0 50.0")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="hexmanifest-"))
    ti1 = _ti1(tmp / "m.ti1", 400)
    rows = 0
    for instr in ("CR30", "SS"):
        for paper in PAPERS:
            for dpi in (300, 600):
                for spacers in ("none", "colored"):
                    tag = f"{instr}/{paper}/{dpi}dpi/spacers-{spacers}"
                    out = tmp / tag.replace("/", "_")
                    out.mkdir(parents=True, exist_ok=True)
                    try:
                        res = le_chart.build_chart(
                            ti1, out / "c", instrument=instr, paper=paper,
                            hflag=True, dpi=dpi, randomize=False,
                            spacer_mode=spacers)
                    except Exception as exc:      # noqa: BLE001
                        print(f"{tag:44} REFUSED {type(exc).__name__}")
                        continue
                    tifs = sorted(out.glob("*.tif"))
                    for i, t in enumerate(tifs):
                        import tifffile
                        a = np.asarray(tifffile.imread(str(t)))
                        d = hashlib.sha256(a.tobytes()).hexdigest()[:32]
                        print(f"{tag}/page{i+1:02} {a.shape} {d}")
                        rows += 1
                    print(f"{tag}/LAYOUT patches={res.layout.total_patches} "
                          f"strips={res.layout.passes} "
                          f"steps={res.layout.steps_in_pass} "
                          f"pages={res.layout.pages}")
    print(f"# {rows} pages hashed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Challenge 2, target 1: the turned strip letter, measured across the matrix.

Every render below goes through `workflow.layout_engine.chart.build_chart`,
which is the function `workflow.chart_creator.ChartCreator` calls for the
Manual "Generate Chart" button. It is NOT `LayoutRecipe.build_kwargs()` handed
to `render_pages`: `build_chart` assembles its own geometry dict by hand, and
that difference has hidden a fault three times on this issue.

For every case it records, per page:

* an md5 of the RGB page bytes, so two builds can be compared byte for byte;
* the "ink" in the strip-label band (sum of 255 - level over pixels < 250) and
  the pixel count, which is what a washed-out antialiased edge loses;
* the same two numbers over the WHOLE page, so a label that fell outside the
  band is still counted.

Run it once on the tree as it is and once with `raster.py` mutated back to the
paste, and diff the JSON.

    python scripts/probe_182_c2_raster_matrix.py --out /tmp/x.json [--quick]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np                                              # noqa: E402
from PIL import Image                                           # noqa: E402

from workflow.layout_engine import chart, geometry, instruments, papers  # noqa: E402

TI1 = ROOT / "tests" / "fixtures" / "charts" / "cm_a4_480p_2pages.ti1"


def _band_rows(instrument: str, paper: str, dpi: int, npatch: int) -> int:
    """Rows above the first patch row, from the SAME geometry chokepoint."""
    w_mm, h_mm = papers.dimensions_mm(paper)
    geom = instruments.build(instrument)
    lay = geometry.compute(geom, w_mm, h_mm, npatch)
    place = geometry.placement(geom, w_mm, h_mm, lay)
    return max(0, int(place.y_of(0) / 25.4 * dpi))


def _measure(paths: list[Path], band_rows: int) -> list[dict]:
    out = []
    for p in sorted(paths):
        im = Image.open(p)
        im.load()
        rgb = im.convert("RGB")
        arr = np.asarray(rgb)
        g = np.asarray(rgb.convert("L")).astype(int)
        band = g[:band_rows] if band_rows > 0 else g[:0]
        bmark = band < 250
        pmark = g < 250
        out.append({
            "file": p.name,
            "size": list(im.size),
            "md5": hashlib.md5(arr.tobytes()).hexdigest(),
            "band_rows": band_rows,
            "band_ink": int((255 - band[bmark]).sum()) if bmark.any() else 0,
            "band_px": int(bmark.sum()),
            "page_ink": int((255 - g[pmark]).sum()) if pmark.any() else 0,
            "page_px": int(pmark.sum()),
        })
    return out


def _cases(quick: bool) -> list[dict]:
    base = dict(instrument="CM", paper="A4", dpi=150, seed=7, randomize=True,
                draw_indicators=True, indicator_size_mm=0.0)
    cs: list[dict] = []
    # 1. the full cross: rotation x alignment x underline mode
    for rot in (0, 90, 180, 270):
        for align in ("left", "center", "right"):
            for um in ("off", "segments", "cycle", "black"):
                cs.append(dict(base, name=f"cross-r{rot}-{align}-{um}",
                               indicator_rotation=rot, indicator_align=align,
                               underline_mode=um))
    if quick:
        return cs
    # 2. underline thickness, at every rotation
    for rot in (0, 90, 180, 270):
        for th in (0.1, 0.5, 2.0, 5.0):
            cs.append(dict(base, name=f"thick-r{rot}-{th}",
                           indicator_rotation=rot, indicator_align="center",
                           underline_mode="cycle", underline_thickness_mm=th))
    # 3. multi-letter labels: enough strips that the labeller runs past Z
    for rot in (0, 90, 180, 270):
        cs.append(dict(base, name=f"multiletter-r{rot}", paper="A2", dpi=150,
                       ti1=str(ROOT / "tests/fixtures/charts/cm_a3_1575p_3pages.ti1"),
                       indicator_rotation=rot, indicator_align="center",
                       underline_mode="cycle"))
    # 4. the label driven OFF THE PAGE, both ways (the offset spin is -50..50)
    for rot in (0, 90, 180, 270):
        for off in (-50.0, -12.0, 12.0, 50.0):
            cs.append(dict(base, name=f"offpage-r{rot}-{off:+.0f}",
                           indicator_rotation=rot, indicator_align="center",
                           underline_mode="cycle", strip_label_offset_mm=off))
    # 5. the largest sheet ChromIQ offers, at a real print resolution
    for rot in (0, 90):
        cs.append(dict(base, name=f"a2-600-r{rot}", paper="A2", dpi=600,
                       indicator_rotation=rot, indicator_align="center",
                       underline_mode="cycle"))
    # 6. a big font, so the tile is wider than its strip and neighbours touch
    for rot in (0, 90, 180, 270):
        cs.append(dict(base, name=f"bigfont-r{rot}", indicator_size_mm=9.0,
                       indicator_rotation=rot, indicator_align="center",
                       underline_mode="cycle"))
    # 7. bold + italic, which changes the glyph's antialiasing
    for rot in (0, 90, 180, 270):
        cs.append(dict(base, name=f"bolditalic-r{rot}", indicator_bold=True,
                       indicator_italic=True, indicator_rotation=rot,
                       indicator_align="center", underline_mode="segments"))
    # 8. row indicators on as well, so two label routes share the overlay
    for rot in (0, 90, 180, 270):
        cs.append(dict(base, name=f"rowind-r{rot}", instrument="SS",
                       row_indicators=True, indicator_rotation=rot,
                       indicator_align="center", underline_mode="cycle"))
    return cs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    cases = _cases(a.quick)
    if a.only:
        want = set(a.only.split(","))
        cases = [c for c in cases if c["name"] in want]
    rows: dict = {}
    tmp = Path(tempfile.mkdtemp(prefix="chromiq-c2-raster-"))
    for i, c in enumerate(cases, 1):
        c = dict(c)
        name = c.pop("name")
        ti1 = c.pop("ti1", str(TI1))
        t0 = time.time()
        outdir = tmp / name
        outdir.mkdir(parents=True, exist_ok=True)
        try:
            res = chart.build_chart(ti1, outdir / "chart", **c)
        except Exception as e:                                  # noqa: BLE001
            rows[name] = {"error": f"{type(e).__name__}: {e}"}
            print(f"[{i}/{len(cases)}] {name}: ERROR {e}", flush=True)
            continue
        tifs = list(outdir.glob("*.tif"))
        npatch = len(getattr(res, "target").patches) if hasattr(res, "target") else 480
        br = _band_rows(c.get("instrument", "CM"), c.get("paper", "A4"),
                        c.get("dpi", 150), npatch)
        rows[name] = {"pages": _measure(tifs, br),
                      "secs": round(time.time() - t0, 2)}
        print(f"[{i}/{len(cases)}] {name}: {len(tifs)} page(s) "
              f"{rows[name]['secs']}s", flush=True)
        shutil.rmtree(outdir, ignore_errors=True)
    Path(a.out).write_text(json.dumps(rows, indent=1, sort_keys=True))
    shutil.rmtree(tmp, ignore_errors=True)
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

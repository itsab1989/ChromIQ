#!/usr/bin/env python3
"""Challenge 2: is a TURNED strip letter really the same ink as an upright one?

`tests/test_a_turned_strip_letter_keeps_all_its_ink.py` asserts one invariant:
a rotation by a multiple of 90 degrees is a lossless transpose, so the same
glyph must print the same ink. It measures ONE geometry (i1, A4, 120 patches,
one page, no underline, auto font size) and only the band above the patches.

THE GEOMETRY MUST BE HELD FIXED FOR THAT COMPARISON TO MEAN ANYTHING, and it is
easy to get wrong: `indicator_rotation` is one of `instruments.GEOM_BUILD_KEYS`,
so a chart built through `chart.build_chart` at 90 degrees has a DIFFERENT label
band and therefore different patch positions than the same chart at 0. Diffing
two such sheets measures the layout, not the letters. So this probe does what
the shipped test does: computes the geometry once, then renders it at each
rotation through `raster.render_pages`.

It widens the test in every direction the brief names: instruments, papers,
patch counts, font sizes, bold/italic, underline mode and thickness, the label
offset that drives the band off the top of the page, multi-letter labels, and
the largest sheet.

Two numbers per case:

* ``band`` -- ink strictly above the first patch row, the shipped test's metric;
* ``page`` -- ink over the WHOLE sheet, which also catches a letter that fell
  outside the band, plus ``below`` = how many differing pixels are at or under
  the first patch row (a label sitting on the patches, where an ink comparison
  is no longer fair and is reported rather than asserted).

    python scripts/probe_182_c2_rotation_ink.py --out /tmp/x.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np                                              # noqa: E402

from workflow.layout_engine import geometry, instruments, papers, raster  # noqa: E402
from workflow.layout_engine.ti1_reader import ColorTarget       # noqa: E402


def _target(n: int) -> ColorTarget:
    patches = [((float(i * 9 % 100), float(i * 17 % 100), float(i * 5 % 100)),
                (40.0, 45.0, 50.0)) for i in range(n)]
    return ColorTarget(color_rep="iRGB",
                       device_fields=["RGB_R", "RGB_G", "RGB_B"],
                       patches=patches)


def _render(instrument: str, paper: str, n: int, dpi: int, rot: int,
            **kw) -> tuple[list[np.ndarray], int]:
    w_mm, h_mm = papers.dimensions_mm(paper)
    geom = instruments.build(instrument)
    lay = geometry.compute(geom, w_mm, h_mm, n)
    place = geometry.placement(geom, w_mm, h_mm, lay)
    band = max(0, int(place.y_of(0) / 25.4 * dpi))
    res = raster.render_pages(_target(n), lay, geom, seed=7, paper_w_mm=w_mm,
                              paper_h_mm=h_mm, dpi=dpi,
                              indicator_rotation=rot, **kw)
    return [np.asarray(im.convert("L")).astype(int) for im in res.images], band


def _ink(a: np.ndarray, rows: slice | None = None) -> tuple[int, int]:
    g = a if rows is None else a[rows]
    m = g < 250
    return int((255 - g[m]).sum()), int(m.sum())


CASES: list[tuple[str, dict]] = []
for _inst in ("i1", "CM", "SS", "CR30", "p3", "41", "51"):
    CASES.append((f"{_inst}-A4-120", dict(instrument=_inst, paper="A4",
                                          n=120, dpi=150)))
for _paper in ("A3", "A2", "Letter", "A4R", "4x6"):
    CASES.append((f"i1-{_paper}-120", dict(instrument="i1", paper=_paper,
                                           n=120, dpi=150)))
for _n in (24, 120, 600, 1500):
    CASES.append((f"i1-A4-{_n}", dict(instrument="i1", paper="A4", n=_n,
                                      dpi=150)))
for _um in ("off", "segments", "cycle", "black"):
    for _th in (0.1, 0.5, 2.0, 5.0):
        CASES.append((f"i1-ul-{_um}-{_th}",
                      dict(instrument="i1", paper="A4", n=120, dpi=150,
                           underline_mode=_um, underline_thickness_mm=_th)))
for _al in ("left", "center", "right"):
    CASES.append((f"i1-align-{_al}", dict(instrument="i1", paper="A4", n=120,
                                          dpi=150, indicator_align=_al)))
for _sz in (1.5, 3.0, 6.0, 12.0):
    CASES.append((f"i1-size-{_sz}", dict(instrument="i1", paper="A4", n=120,
                                         dpi=150, indicator_size_mm=_sz)))
for _b, _i in ((True, False), (False, True), (True, True)):
    CASES.append((f"i1-bold{int(_b)}-ital{int(_i)}",
                  dict(instrument="i1", paper="A4", n=120, dpi=150,
                       indicator_bold=_b, indicator_italic=_i)))
for _off in (-50.0, -20.0, -6.0, 6.0, 20.0, 50.0):
    CASES.append((f"i1-offset{_off:+.0f}",
                  dict(instrument="i1", paper="A4", n=120, dpi=150,
                       strip_label_offset_mm=_off)))
for _f in ("Inter", "JetBrains Mono", "Helvetica"):
    CASES.append((f"i1-font-{_f.replace(' ', '')}",
                  dict(instrument="i1", paper="A4", n=120, dpi=150,
                       indicator_font=_f)))
CASES.append(("i1-A2-1200-120", dict(instrument="i1", paper="A2", n=120,
                                     dpi=1200)))
CASES.append(("CM-A2-3000", dict(instrument="CM", paper="A2", n=3000,
                                 dpi=150)))



def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    cases = CASES
    if a.only:
        want = set(a.only.split(","))
        cases = [c for c in CASES if c[0] in want]
    out: dict = {}
    bad: list[str] = []
    for name, kw in cases:
        kw = dict(kw)
        inst, paper, n, dpi = (kw.pop("instrument"), kw.pop("paper"),
                               kw.pop("n"), kw.pop("dpi"))
        try:
            base, band = _render(inst, paper, n, dpi, 0, **kw)
        except Exception as e:                                  # noqa: BLE001
            out[name] = {"error": f"{type(e).__name__}: {e}"}
            print(f"{name}: ERROR {e}", flush=True)
            continue
        row: dict = {"band_rows": band, "pages": len(base), "rot": {}}
        row["rot"]["0"] = [{"band": _ink(p, slice(0, band)),
                            "page": _ink(p)} for p in base]
        for rot in (90, 180, 270):
            turned, _ = _render(inst, paper, n, dpi, rot, **kw)
            per = []
            for p0, pr in zip(base, turned):
                d = p0 != pr
                per.append({"band": _ink(pr, slice(0, band)),
                            "page": _ink(pr),
                            "diff_px": int(d.sum()),
                            "below": int(d[band:].sum())})
            row["rot"][str(rot)] = per
            for i, (p, q) in enumerate(zip(row["rot"]["0"], per)):
                # THE WHOLE PAGE, not the band. The band is where a label is
                # SUPPOSED to be, and Knut's 2026-09-13 ruling lets it cross
                # onto the patches, so a band-only count reports a label that
                # merely moved as a label that lost ink. Over the whole sheet,
                # with the geometry held fixed, a lossless transpose has to
                # come out equal.
                if p["page"] != q["page"]:
                    bad.append(f"{name} rot={rot} page{i + 1}: page "
                               f"{q['page']} vs {p['page']} upright"
                               f" (band {q['band']} vs {p['band']}, "
                               f"below={q['below']})")
        out[name] = row
        flag = "" if not any(b.startswith(name + " ") for b in bad) else "  <-- DIFFERS"
        print(f"{name}: band_rows={band} pages={len(base)}{flag}", flush=True)
    Path(a.out).write_text(json.dumps({"cases": out, "mismatches": bad},
                                      indent=1, sort_keys=True),
                           encoding="utf-8")
    print(f"\n{len(bad)} band-ink mismatches")
    for b in bad:
        print("  " + b)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

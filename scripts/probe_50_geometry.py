#!/usr/bin/env python3
"""Engine geometry facts for a set of cases, so two commits can be compared.
`margins` is (top, right, bottom, left) -- instruments.build's own order."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from workflow.layout_engine import geometry, instruments, papers  # noqa: E402

BASTI = dict(instrument="CR30", paper="A4", hflag=True, dpi=300,
             spacer_on=False, spacer_mode="none", layout_mode="area_first",
             area_method="by_grid", area_cols=26, area_rows=44, area_ratio=1.0,
             margins=(6.0, 2.0, 1.0, 1.0), border=1.0, nolimit=True)

CASES = {
 "guided_i1":   dict(instrument="i1", paper="A4", border=10.0, dpi=300,
                     spacer_on=True, spacer_mode="colored", edge_spacers=True),
 "guided_cr30": dict(instrument="CR30", paper="A4", border=6.0, dpi=300,
                     spacer_on=False, spacer_mode="none"),
 "guided_cm":   dict(instrument="CM", paper="A4", border=6.0, dpi=300,
                     spacer_on=True, spacer_mode="colored", edge_spacers=True),
 "guided_p3":   dict(instrument="p3", paper="A4", border=10.0, dpi=300,
                     spacer_on=True, spacer_mode="colored", edge_spacers=True),
 "BASTI_area_cr30_hex_T6R2B1L1": BASTI,
}
for L in (0.0, 1.0, 3.0, 5.0, 7.5, 10.0, 20.0):
    CASES[f"area_cr30_L{L:g}"] = {**BASTI, "margins": (6.0, 2.0, 1.0, L),
                                  "border": L}
    CASES[f"patchfirst_cr30_L{L:g}"] = dict(
        instrument="CR30", paper="A4", dpi=300, spacer_on=False,
        spacer_mode="none", margins=(6.0, 2.0, 1.0, L), border=L)


def main() -> int:
    npat = int(sys.argv[1]) if len(sys.argv) > 1 else 1144
    out = {}
    for name, kw in CASES.items():
        try:
            g = instruments.geom_from_build_kwargs(kw, thresholds=None)
            pw, ph = papers.dimensions_mm(kw["paper"])
            lay = geometry.compute(g, pw, ph, npat)
            pl = geometry.placement(g, pw, ph, lay)
            out[name] = {
                "rlwi": round(g.rlwi, 3),
                "fill_beyond_ruler": bool(g.fill_beyond_ruler),
                "margins_are_law": bool(g.margins_are_law),
                "margin_l": round(g.margin_l, 3),
                "x0_mm": round(pl.x0, 3),
                "y0_first_mm": round(pl.y0_first, 3),
                "pwid_mm": round(pl.pwid, 4),
                "plen_mm": round(pl.plen, 4),
                "patches_per_page": lay.patches_per_page,
                "steps_in_pass": lay.steps_in_pass,
            }
        except Exception as exc:   # noqa: BLE001
            out[name] = {"ERROR": f"{type(exc).__name__}: {exc}"}
    bad = [k for k, v in out.items() if "ERROR" in v]
    if bad:
        print("PROBE BROKEN for:", bad, file=sys.stderr)
    print(json.dumps(out, indent=1, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

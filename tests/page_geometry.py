"""Write where a synthetic chart's patch block sits on its page (#182 E2).

Since the page-coverage floor, the evenness rows need to know how much of each
page the patches cover, and a real chart always carries that: an engine
chart's ``channels.json``, a printtarg chart's page TIFFs, or the DERIVED
rectangles a prebuilt bundle ships. A test's hand-written ``.ti2`` has none of
the three, so this writes the third kind beside it: one rectangle per slot, a
regular grid centred on the page and sized so the block covers exactly the
share asked for. Nothing but the block's bounding box is read.
"""
from __future__ import annotations

import json
import math
from pathlib import Path


def write_page_geometry(ti2: Path, pages, rows: int, coverage=0.85,
                        paper_mm=(210.0, 297.0), dpi: int = 100,
                        spans=None) -> Path:
    """``<stem>.channels.json`` beside *ti2* with a derived layout.

    *coverage* is one share for every page or a list, one per page; the
    block keeps the paper's own proportions, so each side is ``sqrt(share)``
    of the paper's. *spans* (4.3.10, the spread rule) instead gives each
    page's (width share, height share) directly: one pair for every page or
    a list of pairs."""
    w, h = float(paper_mm[0]), float(paper_mm[1])
    k = dpi / 25.4
    if spans is not None:
        sides = (list(spans) if isinstance(spans[0], (list, tuple))
                 else [tuple(spans)] * len(pages))
    else:
        shares = (list(coverage) if isinstance(coverage, (list, tuple))
                  else [float(coverage)] * len(pages))
        sides = [(math.sqrt(float(x)), math.sqrt(float(x))) for x in shares]
    rects = []
    for pg, (n_strips, (fw, fh)) in enumerate(zip(pages, sides)):
        bw, bh = w * float(fw), h * float(fh)
        x0, y0 = (w - bw) / 2.0, (h - bh) / 2.0
        pw, ph = bw / n_strips, bh / rows
        for s in range(int(n_strips)):
            for r in range(int(rows)):
                rects.append({"loc": f"{s}:{r}", "page": pg,
                              "x": (x0 + s * pw) * k, "y": (y0 + r * ph) * k,
                              "w": pw * k, "h": ph * k})
    doc = {"layout": {"engine": "derived", "patches": rects, "dpi": dpi,
                      "paper_mm": [w, h]}}
    out = ti2.with_suffix(".channels.json")
    out.write_text(json.dumps(doc), encoding="utf-8")
    return out

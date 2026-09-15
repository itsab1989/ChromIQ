#!/usr/bin/env python3
"""Adversary 17: the new height term in the auto-shrink loop can never be true.

`render_pages` now breaks the "Size auto" shrink loop only when BOTH the width
and the LINE BOX fit::

    _fits_h = sheet_text_line_mm(...) <= _tef.SHEET_TEXT_LINE_MM

`sheet_text_line_mm` rounds through whole pixels at *dpi* and its own floor is
``round(4.2 * dpi / 25.4)`` px read back as millimetres. At 150, 240, 300 and
360 dpi that floor is **4.2333 mm**, which is larger than the 4.2 mm it is
compared against, so `_fits_h` is False for EVERY size at those resolutions
and the loop runs to the 7 pt floor on every chart.

300 dpi is `LayoutRecipe`'s default.

This renders one real sheet and reports the ink height of the bottom line and
the page's own numbers. Run it in this tree and in a HEAD worktree and compare.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def ink(recipe, ti1: Path, tag: str) -> dict:
    import numpy as np
    from PIL import Image
    from workflow.layout_engine.chart import build_from_recipe

    def render(text, suffix):
        base = Path(tempfile.mkdtemp(prefix=f"adv17-{tag}-{suffix}-"))
        res, _used = build_from_recipe(
            str(ti1), str(base / "s"),
            replace(recipe, chart_text=text, randomize=True,
                    seed_fixed=True, seed=123456789))
        page = sorted(base.glob("s*.tif"))[0]
        return np.asarray(Image.open(page).convert("L")).astype(np.int16), res

    on, res = render(recipe.chart_text, "on")
    off, _ = render(" ", "off")
    dpi = float(recipe.dpi or 300)
    mm = lambda px: round(float(px) * 25.4 / dpi, 3)            # noqa: E731
    out = {"paper_h_mm": mm(on.shape[0]), "dpi": recipe.dpi}
    if on.shape != off.shape:
        out["error"] = "geometry moved"
        return out
    diff = np.abs(on - off) > 30
    rows = np.where(diff.any(axis=1))[0]
    cols = np.where(diff.any(axis=0))[0]
    if rows.size:
        out["text_top_up_mm"] = mm(on.shape[0] - int(rows[0]))
        out["text_bottom_up_mm"] = mm(on.shape[0] - int(rows[-1]) - 1)
        out["text_ink_height_mm"] = mm(int(rows[-1]) + 1 - int(rows[0]))
        out["text_ink_width_mm"] = mm(int(cols[-1]) + 1 - int(cols[0]))
    rects = [r for r in (res.strip_rects or []) if int(r.get("page", 0)) == 0]
    if rects:
        y1 = max(int(r["y"]) + int(r["h"]) for r in rects)
        out["patch_bottom_up_mm"] = mm(on.shape[0] - y1)
    return out


def main() -> int:
    out_dir = Path(sys.argv[1]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # no window is opened
    from workflow.layout_engine import raster
    from workflow.layout_engine.presets import LayoutRecipe
    from workflow import text_edge_fit as tef

    ti1 = ROOT / "tests/fixtures/charts/cm_a4_480p_2pages.ti1"
    assert ti1.is_file(), ti1

    facts = {"ti1": str(ti1.relative_to(ROOT)),
             "SHEET_TEXT_LINE_MM": tef.SHEET_TEXT_LINE_MM,
             "SHEET_TEXT_DEFAULT_MM": tef.SHEET_TEXT_DEFAULT_MM,
             "AUTO_SHRINK_FLOOR_PT": tef.AUTO_SHRINK_FLOOR_PT,
             "line_box_at_auto": {}, "sheets": {}}
    for d in (150, 200, 300, 600):
        facts["line_box_at_auto"][d] = {
            "auto_3.2mm": round(raster.sheet_text_line_mm(0.0, "", False,
                                                          False, d), 4),
            "floor_7pt": round(raster.sheet_text_line_mm(
                tef.pt_to_mm(7.0), "", False, False, d), 4),
        }

    for d in (300, 200):
        r = LayoutRecipe()
        r.instrument, r.paper = "i1", "A4"
        r.dpi = d
        r.layout_mode = "area_first"
        r.use_instrument_margins = False
        r.margin_top = r.margin_bottom = 14.0
        r.margin_left = r.margin_right = 10.0
        r.chart_text = "ChromIQ"        # SHORT: the width can never bind
        r.chart_text_size_mm = 0.0      # Size auto
        r.stamp_command = False
        facts["sheets"][d] = ink(r, ti1, f"dpi{d}")
        print(d, json.dumps(facts["sheets"][d]), flush=True)

    (out_dir / f"auto-text-{os.environ.get('ADV17_TAG','tree')}.json").write_text(
        json.dumps(facts, indent=2), encoding="utf-8")
    print(json.dumps(facts["line_box_at_auto"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

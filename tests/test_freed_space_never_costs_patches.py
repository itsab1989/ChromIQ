"""Freed space may only help (Basti, 2026-10-25). Row labels may use the free
part of a clip border since 4.3.14 (`row_label_geometry.md` §R1.3a); no
default recipe, for any instrument, paper or class default, may fit fewer
patches on a page than in v4.3.13 because of it. The v4.3.13 counts are frozen
in `tests/data/patch_counts_v4_3_13.json` (written from the v4.3.13 tree by
agent44's `count_defaults.py`, 1,596 rows)."""
from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

from workflow.layout_engine import area_fit, geometry, instruments, papers  # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe, default_recipe   # noqa: E402

OLD = json.loads((Path(__file__).parent / "data" /
                  "patch_counts_v4_3_13.json").read_text(encoding="utf-8"))

VARIANTS = {
    "default": lambda i, p: default_recipe(i, p),
    "default_area": lambda i, p: default_recipe(i, p, mode="area_first"),
    "default_patch": lambda i, p: default_recipe(i, p, mode="patch_first"),
    "class_area": lambda i, p: LayoutRecipe(instrument=i, paper=p,
                                            layout_mode="area_first"),
    "class_area_grid": lambda i, p: LayoutRecipe(
        instrument=i, paper=p, layout_mode="area_first", area_method="by_grid",
        area_cols=15, area_rows=20),
    "class_area_width": lambda i, p: LayoutRecipe(
        instrument=i, paper=p, layout_mode="area_first", area_method="by_width",
        area_ratio=1.5, area_min_patch_mm=8.0),
    "class_patch": lambda i, p: LayoutRecipe(instrument=i, paper=p,
                                             layout_mode="patch_first"),
}


def _count(key: str) -> int:
    inst, paper, name, hx = key.split("|")
    r = VARIANTS[name](inst, paper)
    if hx == "hflag=True":
        r = dataclasses.replace(r, hflag=True)
    kw = r.build_kwargs()
    if kw.get("layout_mode") == "area_first":
        size = area_fit.derive_area_patch_size(kw)
        kw = {**kw, "patch_w": size[0], "patch_h": size[1]}
    g = instruments.geom_from_build_kwargs(kw)
    w, h = papers.dimensions_mm(r.paper)
    return geometry.compute(g, w, h, 100_000).patches_per_page


#: The everyday tier checks the rows that moved during the work (CR30 and
#: SpectroScan, row labels beside a notes band) on the common papers; the
#: slow tier checks all 1,596.
_EVERYDAY = sorted(k for k in OLD if k.split("|")[0] in ("CR30", "SS")
                   and k.split("|")[1] in ("A4", "Letter", "4x6", "10x15cm"))


@pytest.mark.parametrize("key", _EVERYDAY)
def test_no_fewer_patches_than_4_3_13(key):
    assert _count(key) >= OLD[key], key


@pytest.mark.slow
def test_no_default_recipe_anywhere_has_fewer_patches_than_4_3_13():
    fewer = [(k, OLD[k], n) for k in sorted(OLD) if (n := _count(k)) < OLD[k]]
    assert not fewer, fewer[:20]

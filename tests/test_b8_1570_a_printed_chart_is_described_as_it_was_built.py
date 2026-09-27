"""B8-1570: a chart printed before B8-1540 is described as it was BUILT.

`tests/data/b8_1570_beta44_chart/chart.channels.json` was generated with the
code of 6e7b13bb^ (the commit before B8-1540), in Knut's bug state (#182
5857405680): i1Pro, A4, 20 mm margins, "Prioritise chart area" by 8 columns and
12 rows, with 14 x 10 mm typed under "Prioritise patch size", patch scale 1.3
and a 6 / 6 mm chart offset left over. That build laid the sheet out WITH the
three (the bug), so the recorded patches are 14 x 10 mm, 22 to a strip, with a
15 px spacer between them, and the stored recipe says area-first all the same.

B8-1540 made area-first ignore the three for a NEW build. Every helper that
rebuilt geometry from the stored recipe through `build_kwargs()` then described
a different sheet (20.5 mm patches, 12 a strip, a 12 px spacer). The helpers
now go through `build_kwargs_as_built`, which reads a stored recipe written
before the fix by the old rule and everything else by today's.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

from workflow.layout_engine import instruments
from workflow.layout_engine.presets import (HIDES_PATCH_CONTROLS_KEY,
                                            HIDES_PATCH_CONTROLS_RULE,
                                            LayoutRecipe,
                                            build_kwargs_as_built)

DATA = Path(__file__).parent / "data" / "b8_1570_beta44_chart"
CHANNELS = DATA / "chart.channels.json"


def _layout() -> dict:
    return json.loads(CHANNELS.read_text(encoding="utf-8"))["layout"]


def _spacer_on_the_sheet_px() -> int:
    """The spacer the sheet really has: the commonest gap between two
    neighbouring patches of one strip, from the recorded rectangles."""
    col: "dict[int, list]" = defaultdict(list)
    for r in _layout()["patches"]:
        if int(r.get("page", 0)) == 0:
            col[r["x"]].append(r)
    gaps = []
    for rs in col.values():
        rs.sort(key=lambda r: r["y"])
        gaps += [b["y"] - (a["y"] + a["h"]) for a, b in zip(rs, rs[1:])]
    return max(set(gaps), key=gaps.count)


def test_the_fixture_is_a_chart_laid_out_with_the_leak():
    lay = _layout()
    rec = lay["recipe"]
    assert rec["layout_mode"] == "area_first"
    assert HIDES_PATCH_CONTROLS_KEY not in rec      # written before the fix
    first = lay["patches"][0]
    assert (first["w"], first["h"]) == (165, 119)   # 14 x 10 mm at 300 dpi
    assert _spacer_on_the_sheet_px() == 15


def test_the_stored_recipe_is_read_by_the_rule_it_was_built_with():
    kw = build_kwargs_as_built(_layout()["recipe"])
    assert (kw["patch_w"], kw["patch_h"]) == (14.0, 10.0)
    assert kw["pscale"] == pytest.approx(1.3)
    assert (kw["offset_x"], kw["offset_y"]) == (6.0, 6.0)
    geom = instruments.geom_from_build_kwargs(kw)
    assert round(geom.pspa * 300 / 25.4) == _spacer_on_the_sheet_px()


def test_the_measure_tab_edge_spacer_is_the_sheets(tmp_path):
    from ui.tabs.tab_measure import edge_spacer_px_from_sidecar
    (tmp_path / "chart.channels.json").write_bytes(CHANNELS.read_bytes())
    assert edge_spacer_px_from_sidecar(tmp_path / "chart.ti2") \
        == _spacer_on_the_sheet_px()


def test_the_margin_inspector_widens_by_the_sheets_spacer():
    from workflow.margin_inspector import engine_ink_bounds_px
    lay = _layout()
    rects = [r for r in lay["patches"] if int(r.get("page", 0)) == 0]
    _x0, _x1, y0, y1, _pw = engine_ink_bounds_px(rects, lay["recipe"], 300)
    sp = _spacer_on_the_sheet_px()
    assert y0 == min(r["y"] for r in rects) - sp
    assert y1 == max(r["y"] + r["h"] for r in rects) + sp


def test_a_recipe_written_now_is_read_by_todays_rule():
    """The same settings saved by this version: the hidden size and offset
    have no say, exactly as for the Generate that wrote them, and the patch
    scale, which the mode shows, has (B8-1590)."""
    rec = LayoutRecipe.from_dict(_layout()["recipe"])
    d = rec.to_dict()
    assert d[HIDES_PATCH_CONTROLS_KEY] == HIDES_PATCH_CONTROLS_RULE == 2
    assert build_kwargs_as_built(d) == rec.build_kwargs()
    assert build_kwargs_as_built(rec) == rec.build_kwargs()
    assert rec.build_kwargs()["patch_w"] is None


def test_a_patch_first_recipe_is_unchanged_either_way():
    d = dict(_layout()["recipe"], layout_mode="patch_first")
    rec = LayoutRecipe.from_dict(d)
    assert build_kwargs_as_built(d) == rec.build_kwargs()


def test_a_honeycomb_ring_is_the_one_it_was_built_with():
    """The hexagon ring cap reads the ring through the same door. A beta 45
    chart (mark ``True``) was laid out with the patch scale held back; every
    other one with it (B8-1590)."""
    from workflow.hex_support import ring_mm_of
    base = LayoutRecipe(instrument="CR30", paper="A4", layout_mode="area_first",
                        hflag=True, pscale=1.5, patch_w_mm=12.0,
                        patch_h_mm=12.0)
    beta45 = dict(base.to_dict(), **{HIDES_PATCH_CONTROLS_KEY: True})
    # What the beta 45 engine was handed, spelled out, not derived.
    b45_kw = dict(base.build_kwargs(), pscale=1.0)
    built = instruments.geom_from_build_kwargs(b45_kw).hex_ring_mm
    today = instruments.geom_from_build_kwargs(base.build_kwargs()).hex_ring_mm
    assert built != pytest.approx(today)            # the two rules differ here
    assert ring_mm_of(beta45) == pytest.approx(built)
    assert ring_mm_of(base.to_dict()) == pytest.approx(today)
    assert ring_mm_of(base) == pytest.approx(today)


def test_a_beta_45_chart_is_described_with_the_patch_scale_held_back():
    """B8-1590. Beta 45 wrote the mark as ``True`` and laid area-first charts
    out with the patch scale at 1.0; a chart it made is described so, while
    one written now (the mark 2) and one from before beta 45 (no mark) keep
    their scale."""
    base = LayoutRecipe(instrument="i1", paper="A4", layout_mode="area_first",
                        pscale=0.95)
    now = base.to_dict()
    b45 = dict(now, **{HIDES_PATCH_CONTROLS_KEY: True})
    before = {k: v for k, v in now.items() if k != HIDES_PATCH_CONTROLS_KEY}
    assert build_kwargs_as_built(b45)["pscale"] == 1.0
    assert build_kwargs_as_built(now)["pscale"] == 0.95
    assert build_kwargs_as_built(before)["pscale"] == 0.95

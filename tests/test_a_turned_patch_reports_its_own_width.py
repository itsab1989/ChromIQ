""""Patch width" is one number, and a turned honeycomb has to give the same one.

The margin panel's "Patch width (in strip reading direction)" row comes from
``margin_inspector.measure_from_engine``, which read it straight off the
recorded slot rectangle's ``w``. On a POINTY-top honeycomb that is right: the
hexagon's two flats are its left and right sides, so the slot's width IS the
patch, and the column pitch happens to be the same number.

On a FLAT-top one -- #159's "Straight strips" tick, which is the whole point of
Knut's six CR30 straight-strip charts (2026-09-12) -- the same hexagon is turned
30 degrees. The flats move to the top and bottom, the apexes to the sides, and
the three numbers come apart:

    column pitch      w           9.398 mm
    across the flats  h          10.922 mm   <- the patch
    across the points w * 4/3    12.531 mm

The panel showed the first of those. His A4 charts are named "w11.0mm" and were
reported at 9.4, understating the patch by 14 % on the one readout that tells a
CR30 owner whether its round head fits inside a patch. The inscribed circle is
the across-flats measure, so that is what the report carries in both
orientations.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from workflow.hex_support import recipe_is_flat_top  # noqa: E402
from workflow.layout_engine import geometry, instruments, papers  # noqa: E402
from workflow.layout_engine.hexagon import vertices  # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe  # noqa: E402
from workflow.margin_inspector import measure_from_engine  # noqa: E402

_DPI = 200
_MM = 25.4


def _lay_out(tmp_path, rec_d: dict, patches: int):
    """Build the sidecar `measure_from_engine` reads, the way the app writes it.

    `chart_creator._embed_layout_geometry` folds `strips.json` (the
    `patch_rects_px` output, the paper and the dpi) into `channels.json` and
    adds the engine marker and the recipe. Nothing here is hand-made geometry:
    a fixture that lays its own hexagons out cannot catch a layout that moves.
    """
    rec = LayoutRecipe.from_dict(rec_d)
    geom = instruments.geom_from_build_kwargs(
        {**rec.build_kwargs(), "area_target_count": patches})
    w_mm, h_mm = papers.dimensions_mm(rec_d["paper"])
    layout = geometry.compute(geom, w_mm, h_mm, patches)
    rects = geometry.patch_rects_px(geom, w_mm, h_mm, layout, _DPI)
    sc = tmp_path / "chart.channels.json"
    sc.write_text(json.dumps({"layout": {
        "engine": "chromiq", "dpi": _DPI, "paper_mm": [w_mm, h_mm],
        "patches": rects, "recipe": rec_d}}), encoding="utf-8")
    return sc, [r for r in rects if r["page"] == 0]


def _cr30_recipe(*, flat_top: bool) -> dict:
    """Knut's CR30 honeycomb, in whichever orientation is asked for.

    Taken from the shipped family base so this test cannot drift away from the
    charts it is about.
    """
    from ui.tabs.tab_chart import _CR30_BASE, _CR30_HEX, _CR30_STRAIGHT
    rec = dict(_CR30_BASE, paper="A4", area_cols=18, area_rows=28,
               area_min_patch_mm=0.0)
    rec.update(_CR30_HEX)
    if flat_top:
        rec.update(_CR30_STRAIGHT)
    return rec


def test_a_turned_hexagon_reports_the_distance_between_its_flats(tmp_path):
    rec_d = _cr30_recipe(flat_top=True)
    assert recipe_is_flat_top(rec_d), "the fixture must be the turned cut"
    sc, page0 = _lay_out(tmp_path, rec_d, 450)
    rep, _ = measure_from_engine(sc, 0)

    slot = page0[0]
    pitch_mm = slot["w"] * _MM / _DPI
    flats_mm = slot["h"] * _MM / _DPI
    assert flats_mm > pitch_mm, (
        "the fixture is not a turned honeycomb: its slot is not taller than wide")

    assert abs(rep.strip_width_mm - flats_mm) < 1e-6, (
        f"reported {rep.strip_width_mm:.3f} mm; the patch measures "
        f"{flats_mm:.3f} mm across its flats")
    assert abs(rep.strip_width_mm - pitch_mm) > 1.0, (
        "the column pitch is not the patch width, and here they differ by "
        f"{flats_mm - pitch_mm:.2f} mm")


def test_the_reported_width_is_the_biggest_circle_that_fits_the_drawn_patch(tmp_path):
    """Against the INK, not against the slot arithmetic a second time.

    `hexagon.vertices` is what the renderer fills, so the six corners it returns
    are where the ink is. The distance between the two parallel flats is the
    diameter of the inscribed circle, which is the reason this number is the
    one worth printing: it is what a round head has to land inside.
    """
    for flat_top in (False, True):
        rec_d = _cr30_recipe(flat_top=flat_top)
        sc, page0 = _lay_out(tmp_path, rec_d, 450)
        rep, _ = measure_from_engine(sc, 0)
        slot = page0[0]
        pts = vertices(0.0, 0.0, float(slot["w"]), float(slot["h"]),
                       flat_top=flat_top)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        # The flats are the pair of parallel sides; across them is the SHORTER
        # of the drawn hexagon's two spans, and across the points the longer.
        across_flats_px = min(max(xs) - min(xs), max(ys) - min(ys))
        assert abs(rep.strip_width_mm - across_flats_px * _MM / _DPI) < 0.02, (
            f"flat_top={flat_top}: reported {rep.strip_width_mm:.3f} mm against "
            f"{across_flats_px * _MM / _DPI:.3f} mm of drawn ink")


def test_an_upright_honeycomb_still_reports_what_it_always_did(tmp_path):
    """The fix must not move the eight hexagonal CR30 charts already shipped."""
    rec_d = _cr30_recipe(flat_top=False)
    sc, page0 = _lay_out(tmp_path, rec_d, 450)
    rep, _ = measure_from_engine(sc, 0)
    assert abs(rep.strip_width_mm - page0[0]["w"] * _MM / _DPI) < 1e-6


def test_a_rectangular_chart_is_untouched(tmp_path):
    """No hexagon, no orientation, no change: the slot IS the patch."""
    from ui.tabs.tab_chart import _CR30_BASE
    rec_d = dict(_CR30_BASE, paper="A4", area_cols=15, area_rows=24,
                 area_min_patch_mm=0.0)
    sc, page0 = _lay_out(tmp_path, rec_d, 360)
    rep, _ = measure_from_engine(sc, 0)
    assert abs(rep.strip_width_mm - page0[0]["w"] * _MM / _DPI) < 1e-6

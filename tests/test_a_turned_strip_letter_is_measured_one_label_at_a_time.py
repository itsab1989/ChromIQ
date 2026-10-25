"""A turned strip letter is measured one label at a time (Knut, forum 149832,
2026-10-25).

With the strip letters turned 90 degrees, the "Measured from Preview" panel
said on his "i1Pro-100x150mm-600p-5pages-Portrait-TEST" preset: *"They are held
5.0 mm from the paper edge by the ruler helper markers, they reach 47.9 mm down
the page"* at 7 pt (38.0 mm at 5 pt, 28.0 mm at 4 pt with Y -3.5), while the
letters end about 8 mm down. The ink probe ran every label together
("ABC...Z") and turned the whole word on its side, so its LENGTH was taken as
the letters' height. Each label is pasted as its own tile, and the probe now
measures them that way. The layout reserve is a different number and does not
move, so no chart changes; only the panel's prediction does.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np                                             # noqa: E402
import pytest                                                  # noqa: E402
from PIL import Image                                          # noqa: E402

from workflow import text_edge_fit                             # noqa: E402
from workflow.layout_engine import geometry, instruments       # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe        # noqa: E402

from tests.test_row_labels_use_the_free_part_of_the_clip_border import KNUT  # noqa: E402,E501

PT = 25.4 / 72.0


def _geom(size_pt, rot=90, align="right", y=0.0, x=0.0):
    r = LayoutRecipe.from_dict(dict(
        KNUT, clip_border_free_space=False, show_strip_indicators=True,
        indicator_size_mm=size_pt * PT, indicator_rotation=rot,
        indicator_align=align, strip_label_offset_mm=y,
        strip_label_offset_x_mm=x, helper_markers_top_bottom=True,
        margin_left=11.0, margin_top=17.0))
    kw = dict(r.build_kwargs(), area_target_count=600)
    return instruments.geom_from_build_kwargs(kw), r


@pytest.mark.parametrize("size_pt", [4.0, 5.0, 7.0])
@pytest.mark.parametrize("rot", [90, 270])
@pytest.mark.parametrize("align", ["left", "center", "right"])
def test_the_reach_is_one_label_long_not_twenty_six(size_pt, rot, align):
    g, _r = _geom(size_pt, rot, align)
    reach = float(g.label_ink_reach_mm)
    # "AX", the longest label on 50 strips, is two letters: well under 2 em
    assert 0.0 < reach < 2.0 * size_pt * PT + 0.5, reach
    # and before the fix it was the 26-letter word: 26.5 mm at 4 pt
    assert reach < 6.0


@pytest.mark.parametrize("size_pt,y", [(7.0, 0.0), (5.0, 0.0), (4.0, -3.5)])
def test_his_three_states_no_longer_say_the_letters_are_on_the_patches(
        size_pt, y):
    g, r = _geom(size_pt, y=y)
    # the same arguments the panel passes (tab_chart: `_drawn`, the band
    # without the offset), so this is the panel's own question
    drawn = float(g.label_ink_bottom_mm) - y
    ov = text_edge_fit.strip_label_overlap(
        17.0, r.text_edge_top_mm, drawn, y, True, r.helper_marker_edge_mm,
        r.helper_marker_len_mm, True,
        anchor_mm=geometry.strip_label_leader_top_mm(g),
        ink_reach_mm=float(g.label_ink_reach_mm))
    assert ov is None, ov


def _render(tmp_path, size_pt, align):
    from workflow.layout_engine.chart import build_chart
    _g, r = _geom(size_pt, 90, align)
    src = Path(__file__).parent / "data" / "knut_149832_test.ti1"
    ti1 = tmp_path / "c.ti1"
    shutil.copy(src, ti1)
    kwargs = dict(r.build_kwargs(), seed=1919062204, chart_date="2026-10-24")
    res = build_chart(ti1, tmp_path / "c", **kwargs)
    return res


@pytest.mark.parametrize("align", ["left", "right"])
def test_the_prediction_matches_the_ink_on_the_page(tmp_path, align):
    """Where the letters really end on the rendered sheet, against the panel's
    number: never short of the ink, and not more than half a millimetre past
    it."""
    res = _render(tmp_path, 7.0, align)
    g, _r = _geom(7.0, 90, align)
    predicted = geometry.strip_label_leader_top_mm(g) + g.label_ink_reach_mm
    mm = 25.4 / 200
    deepest = 0.0
    for path in res.tiff_paths:
        a = np.asarray(Image.open(path).convert("L"))
        # the band between the marker dashes (which end 4 mm down) and the
        # first patch row (17 mm), across the patch columns only
        top, bottom = int(4.5 / mm), int(16.5 / mm)
        x0, x1 = int(18.0 / mm), a.shape[1] - int(6.0 / mm)
        rows = np.nonzero((a[top:bottom, x0:x1] < 128).any(axis=1))[0]
        assert rows.size, "no strip letters found"
        deepest = max(deepest, (top + rows[-1] + 1) * mm)
    assert predicted >= deepest - mm, (predicted, deepest)
    assert predicted - deepest < 0.5, (predicted, deepest)

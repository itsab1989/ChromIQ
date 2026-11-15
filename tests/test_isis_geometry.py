"""Every number of an i1iSis chart against REQUIREMENTS v2 (the study of
2026-11-14), table-driven, to 0.01 mm.

The values are what i1Profiler 3.8.8 drew (V02 the default A4 chart, V07
tight margins, V06 the barcode, V08 / V17 the long headers, V18 the XL on
A3+), measured in its saved TIFFs at 0.25 mm per pixel, and X-Rite's chart
rules for what i1Profiler does not show (the cut rule's paper limits)."""
from __future__ import annotations

import pytest

from workflow.isis import chart as C
from workflow.isis import chart_facts as F


def _sheet(N=957, w=210.0, h=297.0, **kw):
    opts = C.options_from(kw)
    g = C.grid_for(N, w, h, opts)
    s = C.sheet_for(g, w, h, opts)
    C.check_sheet(s)
    return s


def _close(a, b):
    return abs(float(a) - float(b)) <= 0.01


# (case, kwargs, chart-relative element, expected mm) -- x from the chart's
# left edge, y from its leading edge, as REQUIREMENTS §4 measures them
CASES = [
    ("V02", {}, "width", 198.0), ("V02", {}, "height", 280.0),
    ("V02", {}, "bar_top", 32.5), ("V02", {}, "bar_bottom", 38.5),
    ("V02", {}, "bar_left", 15.0), ("V02", {}, "first_row", 44.5),
    ("V02", {}, "left_diamond", 5.0), ("V02", {}, "right_diamond_gap", 5.0),
    ("V02", {}, "trailer", 25.5), ("V02", {}, "grid", (28, 35, 1)),
    ("V07", {C.TIGHT_KEY: True}, "left_diamond", 4.0),
    ("V07", {C.TIGHT_KEY: True}, "bar_left", 12.0),
    ("V07", {C.TIGHT_KEY: True}, "right_diamond_gap", 3.0),
    ("V07", {C.TIGHT_KEY: True}, "grid", (29, 33, 1)),
    ("V07", {C.TIGHT_KEY: True}, "width", 198.0),
    ("V06", {C.BARCODE_KEY: True}, "first_row", 58.5),
    ("V06", {C.BARCODE_KEY: True}, "barcode_top", 41.5),
    ("V06", {C.BARCODE_KEY: True}, "grid", (27, 18, 2)),
    ("V06", {C.BARCODE_KEY: True}, "height", 192.0),
    ("V08", {C.HEADER_KEY: 80.0}, "bar_top", 80.5),
    ("V08", {C.HEADER_KEY: 80.0}, "grid", (27, 18, 2)),
    ("V17", {C.HEADER_KEY: 56.0}, "bar_top", 56.5),
    ("V17", {C.HEADER_KEY: 56.0}, "grid", (27, 18, 2)),
]


def _measure(s, what):
    o = s.opts
    return {
        "width": s.width, "height": s.height,
        "bar_top": s.bar_y - s.y0, "bar_bottom": s.bar_y - s.y0 + 6.0,
        "bar_left": s.grid_x - s.x0, "first_row": s.grid_y - s.y0,
        "left_diamond": s.left_diamond_x - s.x0,
        "right_diamond_gap": s.right_diamond_x - (s.grid_x + s.grid_w),
        "trailer": s.y0 + s.height - s.last_row_bottom,
        "barcode_top": s.barcode_y - s.y0,
        "grid": (s.grid.C, s.grid.R, s.grid.P),
    }[what]


@pytest.mark.parametrize("case,kw,what,want", CASES,
                         ids=[f"{c}-{w}" for c, _k, w, _v in CASES])
def test_the_element_is_where_i1profiler_draws_it(case, kw, what, want):
    s = _sheet(**kw)
    got = _measure(s, what)
    if isinstance(want, tuple):
        assert got == want
    else:
        assert _close(got, want), (case, what, got, want)


def test_the_bar_spans_every_column_and_a_diamond_pair_sits_on_every_row():
    # X02's split (two wholly empty columns on page 3), its rows asked for
    # with "Max strip length" (four rows of 20 mm)
    s = _sheet(N=100, w=240.0, h=200.0, patch_w=20, patch_h=20,
               margins=(0, 0, 0, 0), max_strip=80.0, **{C.MODEL_KEY: "xl"})
    assert (s.grid.C, s.grid.R, s.grid.P) == (9, 4, 3)    # X02's split
    assert _close(s.bar[2], 9 * 20.0)                     # all columns
    assert len(s.diamonds()) == 2 * 4
    for (x, y, w, h), r in zip(s.diamonds()[::2], range(4)):
        assert _close(y + h / 2, s.row_centre(r))
        assert (w, h) == (5.0, 2.5)


def test_the_xl_caps_at_318_mm_and_the_standard_at_218():
    xl = _sheet(w=329.0, h=483.0, **{C.MODEL_KEY: "xl"})       # V18
    assert (xl.grid.C, xl.grid.R) == (48, 20)
    assert _close(xl.width, 318.0)
    assert _close(xl.right_marker_edge, 318.0)                 # 5 + 318 - 5
    assert xl.fed_as_printed                                   # "within"
    std = _sheet(w=297.0, h=420.0)                              # V14
    assert std.grid.C == 31 and _close(std.width, 216.0)


def test_tight_caps_are_x_rites_marker_edge_rule():
    s = _sheet(N=957, w=300.0, h=297.0, margins=(0, 0, 0, 0),
               **{C.TIGHT_KEY: True})                           # W12
    assert s.grid.C == 33
    assert _close(s.right_marker_edge, 218.0)


def test_placement_is_top_left_inside_the_margins_and_alignment_moves_it():
    s = _sheet(margins=(7, 5, 5, 11))
    assert (_close(s.x0, 11.0), _close(s.y0, 7.0)) == (True, True)
    s2 = _sheet(N=300, margins=(5, 5, 5, 5), **{C.ALIGN_KEY: "bottom-right"})
    assert _close(s2.x0 + s2.width, 205.0)
    assert _close(s2.y0 + s2.height, 292.0)
    s3 = _sheet(N=300, offset_x=3.0, offset_y=4.0)
    assert (_close(s3.x0, 8.0), _close(s3.y0, 9.0)) == (True, True)


def test_the_shortest_chart_is_171_mm():
    s = _sheet(N=24, w=300.0, h=297.0, patch_w=8, patch_h=8,
               margins=(0, 0, 0, 0))                            # X07
    assert (s.grid.C, s.grid.R) == (12, 2)
    assert _close(s.height, 171.0)
    assert s.trailer > 25.5


def test_a_narrow_chart_is_drawn_60_mm_wide():
    s = _sheet(N=4, margins=(0, 0, 0, 0))                       # X08
    assert _close(s.nominal_width, 54.0)
    assert _close(s.width, 60.0)
    # the right markers stay where the grid puts them
    assert _close(s.right_diamond_x - s.x0, 15.0 + 24.0 + 5.0)


@pytest.mark.parametrize("kw,paper,fed", [
    ({}, (210.0, 297.0), True),                      # A4 default
    ({}, (215.9, 279.4), True),                      # Letter default
    ({C.MODEL_KEY: "xl"}, (329.0, 483.0), True),     # A3+ XL, 318.0 exactly
    ({}, (297.0, 420.0), False),                     # A3 on the standard model
    ({C.HEADER_KEY: 80.0}, (210.0, 297.0), False),   # bar 85.5 from paper
    ({"margins": (5, 5, 5, 1)}, (210.0, 297.0), True),  # Dist 1 = 6 mm
    ({"margins": (5, 5, 5, 0), C.TIGHT_KEY: True}, (210.0, 297.0), True),
])
def test_the_cut_rule(kw, paper, fed):
    s = _sheet(w=paper[0], h=paper[1], **kw)
    assert s.fed_as_printed is fed, s.cut_reasons


def test_marker_reach_needs_a_cut_when_the_margin_pushes_it_past_the_cap():
    s = _sheet(w=300.0, h=297.0, margins=(5, 0, 5, 20))         # W14
    assert s.grid.C == 31
    assert not s.fed_as_printed
    assert "marker_reach" in s.cut_reasons


@pytest.mark.parametrize("kw,paper,kind", [
    ({}, (40.0, 297.0), "narrow"),
    ({}, (210.0, 160.0), "short"),
    ({C.BARCODE_KEY: True, "patch_w": 6.1}, (210.0, 297.0), "barcode_size"),
])
def test_what_no_i1isis_can_read_is_refused(kw, paper, kind):
    with pytest.raises(C.IsisSheetRefused) as e:
        _sheet(w=paper[0], h=paper[1], **kw)
    assert e.value.kind == kind


def test_rows_and_patches_per_page_are_capped():
    s = _sheet(N=6000, w=329.0, h=700.0, **{C.MODEL_KEY: "xl"})
    assert s.grid.C * s.grid.R <= F.PATCHES_PER_PAGE_MAX.value
    assert s.height <= F.CHART_MAX_LENGTH_MM.value + 1e-9
    asked = _sheet(N=957, max_strip=60.0)
    assert asked.grid.R <= 10


def test_the_notes_band_lies_where_x_rite_allows_text():
    s = _sheet(**{C.BAND_KEY: True})
    assert _close(s.header, 56.0)
    x, y, w, h = s.header_band()
    assert _close(y - s.y0, 12.0) and _close(y + h, s.bar_y - 20.5)
    t = _sheet(**{C.BAND_KEY: True, C.BAND_PLACE_KEY: "trailer"})
    x, y, w, h = t.trailer_band()
    assert _close(y, t.last_row_bottom + 22.0)
    assert _close(h, 24.0)


def test_unused_cells_stay_white_padlrow_false():
    """i1Profiler leaves the cells after the last patch unprinted; every
    other engine instrument pads them with paper-white patches."""
    from workflow.isis import support
    from workflow.layout_engine import instruments
    support.set_enabled_for_this_process(True)
    try:
        assert instruments.build("XRISIS").padlrow is False
    finally:
        support.set_enabled_for_this_process(None)

"""The clip-border width is measured from the page edge, so 10 mm means
10 mm (Basti, 2026-10-25, from Knut's forum post 149832: "At 10.0mm the whole
clip border text disappears"). His 100 x 150 mm i1Pro card carries a base
margin of 10.0 mm, which is also the box's minimum; at exactly that width the
band used to be 0 wide. It is a real band now, and the red mark on the box is
left only where it is still true: a width below the base margin."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

from workflow.layout_engine import geometry, instruments       # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe        # noqa: E402

KNUT = dict(instrument="i1", paper="100x150", border=10.0, clip_border=True,
            clip_border_width_mm=11.0, clip_side="left",
            clip_content_mode="branding", margin_left=11.0, margin_top=17.0,
            margin_right=5.0, margin_bottom=13.0, layout_mode="area_first",
            area_cols=10, area_rows=12, show_row_indicators=True,
            text_edge_clip_mm=2.0, use_instrument_margins=False)


def _geom(width, **kw):
    r = LayoutRecipe.from_dict(dict(KNUT, clip_border_width_mm=width, **kw))
    return instruments.geom_from_build_kwargs(dict(r.build_kwargs()))


def test_ten_millimetres_is_a_band_of_ten_millimetres():
    g = _geom(10.0)
    assert g.lbord > 0.0
    area = geometry.clip_area_mm(g, 150.0, 100.0)
    assert area is not None, "the band and its content were gone"
    assert area[0] + area[2] == pytest.approx(10.0, abs=0.02)


def test_the_band_grows_with_the_width_from_the_page_edge():
    for w in (10.5, 11.0, 12.0):
        a = geometry.clip_area_mm(_geom(w), 150.0, 100.0)
        assert a[0] + a[2] == pytest.approx(w, abs=0.02), w


def _tip(qapp, width, border=10.0):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel()
    try:
        p.set_recipe(LayoutRecipe.from_dict(
            dict(KNUT, clip_border_width_mm=width, border=border)))
        p._update_clip_margin_conflict()
        return p.clip_width.toolTip()
    finally:
        p.deleteLater()


def test_no_red_mark_at_the_base_margin_any_more(qapp):
    assert "narrower than this chart's base margin" not in _tip(qapp, 10.0)


def test_the_mark_stays_where_it_is_true(qapp):
    tip = _tip(qapp, 10.5, border=12.0)
    assert "narrower than this chart's base margin of 12.0 mm" in tip, tip


def test_a_wider_margin_is_described_exactly(qapp):
    """It used to say this width "is ignored", and it is not."""
    tip = _tip(qapp, 10.5)
    assert "is ignored" not in tip
    assert "The patches start at the left margin, 11.0 mm" in tip, tip
    assert "stays 10.5 mm wide" in tip

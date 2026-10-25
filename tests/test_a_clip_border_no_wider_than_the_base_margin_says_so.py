"""A clip border no wider than the chart's base margin has no band at all,
and the "Clip border width" box says so (Knut, forum 149832, 2026-10-25: "At
10.0mm the whole clip border text disappears", on his 100 x 150 mm i1Pro
preset, whose base margin is 10.0 mm, the box's own minimum)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.layout_engine import instruments                 # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe        # noqa: E402

KNUT = dict(instrument="i1", paper="100x150", border=10.0, clip_border=True,
            clip_border_width_mm=11.0, clip_side="left",
            clip_content_mode="branding", margin_left=11.0, margin_top=17.0,
            margin_right=5.0, margin_bottom=13.0, layout_mode="area_first",
            area_cols=10, area_rows=12, show_row_indicators=True)


def _geom(width):
    r = LayoutRecipe.from_dict(dict(KNUT, clip_border_width_mm=width))
    return instruments.geom_from_build_kwargs(dict(r.build_kwargs()))


def test_the_band_is_gone_at_the_base_margin_and_back_above_it():
    """The fact the note reports, measured on the geometry."""
    assert _geom(10.0).lbord == 0.0
    assert _geom(10.5).lbord > 0.0
    assert _geom(11.0).row_label_floor == 11.0


def _tip(qapp, width):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel()
    try:
        p.set_recipe(LayoutRecipe.from_dict(dict(KNUT, clip_border_width_mm=width)))
        p._update_clip_margin_conflict()
        return p.clip_width.toolTip()
    finally:
        p.deleteLater()


def test_the_box_says_so_at_the_base_margin(qapp):
    tip = _tip(qapp, 10.0)
    assert "no room of its own" in tip, tip
    assert "10.0 mm" in tip and "10.5 mm" in tip


def test_the_box_is_quiet_above_it(qapp):
    assert "no room of its own" not in _tip(qapp, 11.0)
    assert "no room of its own" not in _tip(qapp, 10.5)

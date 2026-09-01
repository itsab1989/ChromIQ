"""Finding 5 — the left margin is raised for the row labels, and it was silent.

Measured on beta 6, in the real app: a typed left margin of 26 mm resolved to
33.03, 10 to 33.64, 6 to 14.38 and 4 to 8.95, with **no message anywhere**.
`docs/design/row_label_geometry.md` §R2 claimed "The panel says so", which was
not true of any panel.

Worse, the message that *did* fire was wrong on exactly those charts: with a
typed margin under 2 mm the inspector said *"the patches will cover part of
each one"* while the resolved margin was 8.95 / 14.38 / 33.03 mm and every
label printed cleanly.

Both halves are asserted here, against the real method — a stub stands in only
for the three widgets it reads (the Manual button, the layout panel and the
settings), never for the calculation.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_chart import TabChart                    # noqa: E402
from workflow.layout_engine import instruments            # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe   # noqa: E402


class _Btn:
    def isChecked(self):
        return True


class _Settings:
    def get(self, key, default=None):
        return True if key == "use_chromiq_layout_engine" else default


class _Tab:
    """Just enough TabChart for the method under test to run."""
    _manual_btn = _Btn()
    _manual_layout_panel = object()
    _settings = _Settings()

    def __init__(self, recipe):
        self._recipe = recipe

    def _current_layout_recipe(self):
        return self._recipe


def _recipe(*, margin_l: float, rows=True, mode="area_first", instrument="CM"):
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = instrument, "A4", mode
    r.show_strip_indicators, r.show_row_indicators = True, rows
    r.clip_border = False
    r.margin_top = r.margin_right = r.margin_bottom = 10.0
    r.margin_left = margin_l
    return r


def _warnings(r) -> "list[str]":
    return TabChart._engine_text_overflow_warnings(_Tab(r))


def _resolved(r) -> float:
    return instruments.geom_from_build_kwargs(r.build_kwargs()).margin_l


# ------------------------------------------------------------------ said ----
@pytest.mark.parametrize("mode", ["area_first", "patch_first"])
def test_a_raised_left_margin_is_reported(mode):
    r = _recipe(margin_l=4.0, mode=mode)
    got = _resolved(r)
    assert got > 4.05, (
        "the premise failed: this chart's left margin is not being raised, so "
        "there is nothing for the message to report")
    lines = [w for w in _warnings(r) if "left margin was widened" in w]
    assert lines, (
        f"the margin went from 4.0 to {got:.2f} mm and the panel said nothing: "
        f"{_warnings(r)}")
    assert "4.0 mm" in lines[0] and f"{got:.1f} mm" in lines[0], (
        f"the message does not carry both numbers: {lines[0]}")


def test_nothing_is_said_when_nothing_was_moved():
    r = _recipe(margin_l=40.0)
    assert abs(_resolved(r) - 40.0) < 0.05, "the premise failed"
    assert not [w for w in _warnings(r) if "left margin was widened" in w]


def test_nothing_is_said_when_there_are_no_row_labels():
    r = _recipe(margin_l=4.0, rows=False)
    assert not [w for w in _warnings(r) if "left margin was widened" in w]


# --------------------------------------------------------------- unsaid ----
def test_the_stale_warning_no_longer_fires_on_a_chart_that_prints_perfectly():
    """`tab_chart.py`'s "the patches will cover part of each one" was written
    for the days when the labels were clamped at the paper edge. The margin is
    raised now, so on these charts the labels print in full."""
    r = _recipe(margin_l=1.0)
    got = _resolved(r)
    assert got > 8.0, (
        f"the premise failed: a 1 mm margin resolved to {got:.2f} mm, so the "
        f"chart being described really is short of room")
    bad = [w for w in _warnings(r)
           if "cover part of each one" in w or "will not be printed" in w]
    assert not bad, (
        f"the inspector warns about labels that are printed cleanly at "
        f"{got:.2f} mm: {bad}")


def test_the_fill_the_page_warning_no_longer_denies_labels_that_print():
    """The third stale message, found on Knut's own flagship preset.

    `i1Pro-A4-162p-1page-Portrait-w7.5mm` fills the page, carries a 26 mm clip
    border on the left and prints notes in it, so the inspector said *"The row
    indicators will not appear on this chart… the clip border is printed over
    them."* Driven on screen, the labels print at 27.3 to 32.8 mm, clear of the
    26 mm border, because the band's floor is now the border's own width.
    """
    r = _recipe(margin_l=6.0, instrument="i1")
    r.clip_border = True
    r.clip_border_width_mm = 26.0
    r.clip_side = "left"
    r.clip_content_mode = "notes"
    r.fill_beyond_ruler = True
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    assert g.rlwi > 0 and g.fill_beyond_ruler and g.lbord > 0, (
        "the premise failed: this is not the chart the warning was written for")
    assert g.row_label_floor >= 26.0, (
        f"the floor is {g.row_label_floor:.2f} mm against a 26 mm border, so "
        f"the warning would be TRUE and must not be silenced")
    bad = [w for w in _warnings(r) if "will not appear on this chart" in w]
    assert not bad, f"the labels print at the floor, clear of the border: {bad}"

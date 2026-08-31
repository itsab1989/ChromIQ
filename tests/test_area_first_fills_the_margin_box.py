"""Prioritise chart area means the margins are the law — row labels or not.

Knut, #93: *"the whole patch area shall always follow the margins as law,
especially when Prioritise chart area"*. Switching row indicators on made the
block stop 7.45 mm short of the right margin while still starting at the left
one: `area_fit._usable` was the third site of the row-label subtraction and
the only one without the `fill_beyond_ruler` guard that `geometry.compute()`
and `geometry.placement()` both carry.
"""
import pytest

from workflow.layout_engine import area_fit, geometry, instruments

_W, _H = 210.0, 297.0


def _usable(rows_on: bool):
    g = instruments.build("i1", row_indicators=rows_on, fill_beyond_ruler=True)
    return area_fit._usable(g, _W, _H)[0], g


def test_row_indicators_do_not_shrink_the_area_first_block():
    off_w, g_off = _usable(False)
    on_w, g_on = _usable(True)
    assert g_on.rlwi > 0, "row indicators reserved no band, so nothing is tested"
    assert on_w == pytest.approx(off_w, abs=1e-9), (
        f"the usable width lost {off_w - on_w:.2f} mm to the row-label band "
        "while 'margins are the law' was in force")


def test_the_band_is_still_reserved_when_the_margins_are_not_the_law():
    """Patch-first is the other branch: there the band is real space."""
    g = instruments.build("i1", row_indicators=True, fill_beyond_ruler=False)
    plain = instruments.build("i1", row_indicators=False, fill_beyond_ruler=False)
    assert (area_fit._usable(g, _W, _H)[0]
            < area_fit._usable(plain, _W, _H)[0]), (
        "the row-label band stopped being reserved where it must be")


def test_area_first_matches_what_the_geometry_reserves():
    """All three sites must agree, which is the property that was broken."""
    for rows_on in (False, True):
        g = instruments.build("i1", row_indicators=rows_on,
                              fill_beyond_ruler=True)
        expected = (_W - g.margin_l - g.margin_r - 2.0 * g.hxew
                    - (g.pglth if g.dopglabel else 0.0))
        assert area_fit._usable(g, _W, _H)[0] == pytest.approx(expected,
                                                                 abs=1e-9)

"""#152 (Knut): printed dashes along the page edges, to lay a ruler against.

His specification, and his answers to the questions that decided the geometry:

* **Top and bottom** step ACROSS the page with the strips — the start and the
  middle of every strip, plus the end of the last one.
* **Left and right** step DOWN the page with the patches, in the same way.
* The rest of each edge is filled at that same spacing, out to the corners.
* **The ColorMunki stagger takes the first strip as its reference** — his
  ruling: *"the offset strip is always half a patch height offset, thus the
  markers land the correct place if you just use the first strip as the
  reference."*
* Overlapping other furniture is acceptable; the help text says how to adjust.
* Hexagonal SpectroScan charts are not supported.
* Black, about 0.2 mm, on every chart type.

The A4 example in the issue is the specification for the edge arithmetic and is
asserted here exactly: with 1 mm from the edge and 3 mm long, the left dashes run
1→4 mm and the right ones 206→209 mm on a 210 mm sheet.
"""
from __future__ import annotations

import pytest

from workflow.layout_engine import geometry as G, instruments as I

A4_W, A4_H = 210.0, 297.0


def _lines(key="CM", w=A4_W, h=A4_H, n=400, edge=1.0, length=3.0, **build):
    geom = I.build(key, **build)
    lay = G.compute(geom, w, h, n)
    return geom, lay, G.helper_marker_lines_mm(geom, w, h, lay,
                                               edge_mm=edge, length_mm=length)


def _verticals(lines):
    return sorted({round(a, 6) for a, b, c, d in lines if a == c})


def _horizontals(lines):
    return sorted({round(b, 6) for a, b, c, d in lines if b == d})


# --- his A4 worked example --------------------------------------------------

def test_the_a4_example_from_the_issue():
    """Left 1→4 mm, right 206→209 mm, top 1→4 mm, bottom 293→296 mm."""
    _, _, lines = _lines()
    tops = {(round(b, 3), round(d, 3)) for a, b, c, d in lines
            if a == c and b < A4_H / 2}
    bottoms = {(round(b, 3), round(d, 3)) for a, b, c, d in lines
               if a == c and b > A4_H / 2}
    lefts = {(round(a, 3), round(c, 3)) for a, b, c, d in lines
             if b == d and a < A4_W / 2}
    rights = {(round(a, 3), round(c, 3)) for a, b, c, d in lines
              if b == d and a > A4_W / 2}
    assert tops == {(1.0, 4.0)}
    assert bottoms == {(293.0, 296.0)}
    assert lefts == {(1.0, 4.0)}
    assert rights == {(206.0, 209.0)}


def test_the_distances_are_the_users_own():
    _, _, lines = _lines(edge=2.5, length=6.0)
    lefts = {(round(a, 3), round(c, 3)) for a, b, c, d in lines
             if b == d and a < A4_W / 2}
    assert lefts == {(2.5, 8.5)}


# --- what they line up with -------------------------------------------------

def test_a_dash_sits_on_every_strip_start_and_middle():
    geom, lay, lines = _lines()
    place = G.placement(geom, A4_W, A4_H, lay)
    xs = _verticals(lines)
    cols = lay.patches_per_page // lay.steps_in_pass
    for p in range(cols):
        for want in (place.x_of(p), place.x_of(p) + place.pwid / 2):
            assert any(abs(x - want) < 1e-6 for x in xs), (p, want)


def test_a_dash_sits_on_the_last_strips_end():
    geom, lay, lines = _lines()
    place = G.placement(geom, A4_W, A4_H, lay)
    cols = lay.patches_per_page // lay.steps_in_pass
    want = place.x_of(cols - 1) + place.pwid
    assert any(abs(x - want) < 1e-6 for x in _verticals(lines))


def test_a_dash_sits_on_every_patch_start_and_middle():
    """Exact even with a spacer between patches — the positions come from the
    patches themselves, not from a comb assumed to fit them."""
    geom, lay, lines = _lines()
    place = G.placement(geom, A4_W, A4_H, lay)
    ys = _horizontals(lines)
    for j in range(lay.steps_in_pass):
        for want in (place.y_of(j), place.y_of(j) + place.plen / 2):
            assert any(abs(y - want) < 1e-6 for y in ys), (j, want)


def test_the_edges_are_filled_out_to_the_corners():
    """His rule: the rest of each edge continues at the same spacing.

    Whether there is ROOM to continue depends on the chart. A ColorMunki's
    28 mm patches give a 14 mm spacing and its first strip starts 6 mm in, so
    there is no room for another dash to its left — and inventing one at a
    different spacing would break the rule rather than honour it. The i1Pro's
    8 mm patches leave plenty of room, so it is the honest case to assert on.
    """
    geom, lay, lines = _lines(key="i1", n=800)
    place = G.placement(geom, A4_W, A4_H, lay)
    xs, ys = _verticals(lines), _horizontals(lines)
    assert min(xs) < place.x_of(0), "nothing was filled left of the first strip"
    assert max(ys) > place.y_of(lay.steps_in_pass - 1) + place.plen, \
        "nothing was filled below the last patch"
    # And the continuation keeps the spacing the patches defined.
    step = place.pwid / 2
    below = sorted(x for x in xs if x < place.x_of(0))
    assert below, "expected dashes left of the first strip"
    assert abs((place.x_of(0) - max(below)) - step) < 1e-6


def test_the_fill_never_invents_a_closer_spacing():
    """Where a chart leaves no room, the edge simply stops — it does not squeeze
    an extra dash in at a spacing that no longer matches the patches."""
    geom, lay, lines = _lines()          # ColorMunki: no room to the left
    place = G.placement(geom, A4_W, A4_H, lay)
    xs = _verticals(lines)
    assert min(xs) == pytest.approx(place.x_of(0))


def test_every_dash_stays_on_the_sheet():
    _, _, lines = _lines()
    for a, b, c, d in lines:
        assert 0 <= a <= A4_W and 0 <= c <= A4_W, (a, c)
        assert 0 <= b <= A4_H and 0 <= d <= A4_H, (b, d)


# --- every paper, orientation and instrument --------------------------------

@pytest.mark.parametrize("w,h", [(210, 297), (297, 210), (216, 279),
                                 (297, 420), (420, 297), (330, 483)])
def test_any_paper_size_and_orientation(w, h):
    _, _, lines = _lines(w=float(w), h=float(h))
    assert lines
    for a, b, c, d in lines:
        assert 0 <= a <= w and 0 <= b <= h


@pytest.mark.parametrize("key", ["i1", "p3", "CM", "SS"])
def test_every_rectangular_instrument(key):
    _, _, lines = _lines(key=key, n=200)
    assert lines, key


def test_hexagonal_spectroscan_gets_no_markers():
    """A honeycomb has no straight rows for a ruler to follow, so rather than
    drawing something misleading it draws nothing."""
    _, _, lines = _lines(key="SS", n=200, hflag=True)
    assert lines == []


def test_a_flat_spectroscan_still_gets_them():
    _, _, lines = _lines(key="SS", n=200, hflag=False)
    assert lines


# --- the ColorMunki stagger, measured rather than assumed --------------------

def test_the_stagger_matches_the_marker_spacing_without_spacers():
    """Knut's reasoning holds exactly when there are no spacers: the offset is
    then precisely half a patch, which is the marker spacing."""
    geom = I.build("CM", cm_stagger=True, spacer_on=False)
    lay = G.compute(geom, A4_W, A4_H, 400)
    place = G.placement(geom, A4_W, A4_H, lay)
    assert geom.row_stagger_mm == pytest.approx(place.plen / 2)


def test_a_spacer_makes_the_stagger_a_quarter_spacer_deeper():
    """With spacers the engine staggers by ``0.5 * (plen + 0.5 * pspa)``, so the
    offset strips sit a quarter of a spacer below their markers. Recorded here
    because it is a real, measured discrepancy against his stated premise — and
    it is his call, not this test's, whether to change it."""
    geom = I.build("CM", cm_stagger=True, spacer_on=True)
    lay = G.compute(geom, A4_W, A4_H, 400)
    place = G.placement(geom, A4_W, A4_H, lay)
    drift = abs(geom.row_stagger_mm - place.plen / 2)
    assert drift == pytest.approx(place.pspa / 4)
    assert drift < 0.5, "a bigger drift than this would need telling him again"


# --- refusing to draw something silly ---------------------------------------

def test_markers_that_would_meet_in_the_middle_are_refused():
    """Nonsense settings draw nothing rather than covering the chart."""
    _, _, lines = _lines(edge=100.0, length=100.0)
    assert lines == []


def test_a_zero_length_marker_draws_nothing():
    _, _, lines = _lines(length=0.0)
    assert lines == []

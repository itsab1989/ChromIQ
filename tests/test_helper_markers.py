"""#152 (Knut): printed dashes along the page edges, to lay a ruler against.

**The rule changed after he saw them on a real sheet, and the new one is
simpler and stricter.** The first design placed a dash at the start and the
middle of every patch, plus one at the end of the last — which is what he
originally described. Measured on paper it did not hold up:

    *"it seems each marker for start and end of a patch row (vertical direction)
    is drawn twice … The calculation seems also to be off, as not every distance
    between markers are same. The distance between every single dash drawn shall
    be the same, and if they are not, then some calculation y-position is wrong.
    **This must be a criteria for test pass.**"*

He is right on both counts, and one cause explains both. Start→middle is half a
patch; middle→next start is half a patch **plus the spacer**. With a 1 mm spacer
on A4 that produced gaps of 5 mm, 6 mm, 5 mm, 6 mm… and the separate
end-of-last-patch dash landed one spacer width from the continued pattern,
putting two dashes 1 mm apart — the "drawn twice" he saw *"next to the bottom
spacer of the last row of patches"*.

So the geometry is now **one evenly-spaced comb per axis**, stepped at half the
patch pitch. Every gap is identical by construction, and there is no special
last-patch case to go wrong.

**Where the comb starts changed once more**, after he saw beta.7 on paper:

    *"the dashes at the start of each patch is positioned at the end of its above
    spacer. It would be better if the dash would be centred vertically to the
    centre of the spacer thickness (height) above each patch, either the spacer
    is wide, thin, thick or not existing. This would result in a centre to centre
    distance between spacers, and then the middle dash between them will always
    fall centred within in the patch height."*

Anchored on the patch boundary, the in-between dash lands half a spacer past the
middle of the patch. Anchored half a gap earlier — on the centre of the spacer —
the marks fall alternately on a spacer centre and a **patch centre**, still one
pitch/2 apart. Both properties hold at once, at any spacer width including zero.

The specification these tests hold the code to:

1. **Every gap between neighbouring dashes is the same** — his pass criterion,
   and the first thing asserted here.
2. A dash sits at the centre of every patch, and at the centre of every spacer.
3. The pitch is measured off the layout, so **any spacer width** is followed
   automatically: *"You have to dynamically include the spacers as part of the
   calculation, as the spacers can change in the create chart settings."*
4. **Corners are kept clear**: a dash is dropped where it would reach into the
   band the perpendicular edge's dashes occupy — his eight-case rule, which
   reduces to one symmetric test.
5. The ColorMunki stagger takes the first strip as its reference.
6. Hexagonal SpectroScan charts get no markers at all.
7. Defaults: 2.0 mm from the edge, 2.0 mm long, both the same.
"""
from __future__ import annotations

import pytest

from workflow.layout_engine import geometry as G, instruments as I

A4_W, A4_H = 210.0, 297.0


def _lines(key="CM", w=A4_W, h=A4_H, n=400, edge=2.0, length=2.0, **build):
    geom = I.build(key, **build)
    lay = G.compute(geom, w, h, n)
    return geom, lay, G.helper_marker_lines_mm(geom, w, h, lay,
                                               edge_mm=edge, length_mm=length)


def _verticals(lines):
    return sorted({round(a, 6) for a, b, c, d in lines if a == c})


def _horizontals(lines):
    return sorted({round(b, 6) for a, b, c, d in lines if b == d})


def _gaps(vals):
    return sorted({round(b - a, 4) for a, b in zip(vals, vals[1:])})


# --- 1. HIS PASS CRITERION: every gap the same ------------------------------

@pytest.mark.parametrize("key", ["i1", "p3", "CM", "SS"])
@pytest.mark.parametrize("spacer_mm", [0.0, 0.5, 1.0, 2.5, 5.0])
def test_every_gap_between_dashes_is_identical(key, spacer_mm):
    """*"The distance between every single dash drawn shall be the same."*

    Asserted on both axes, for every rectangular instrument, at every spacer
    width — because the old scheme passed on some of those combinations and
    failed on others, which is exactly how it survived a full test suite.
    """
    geom, lay, lines = _lines(key=key, n=800, spacer_on=spacer_mm > 0,
                              spacer_width=spacer_mm)
    for axis, vals in (("rows", _horizontals(lines)),
                       ("columns", _verticals(lines))):
        assert len(vals) > 2, f"{axis}: too few dashes to judge"
        assert len(_gaps(vals)) == 1, (
            f"{key}, {spacer_mm} mm spacer, {axis}: gaps are {_gaps(vals)}, "
            f"which must be a single value")


def test_no_two_dashes_are_nearly_on_top_of_each_other():
    """The 'drawn twice' he saw: the end-of-last-patch dash landing one spacer
    width from the continued pattern, 1 mm apart on his sheet."""
    geom, lay, lines = _lines(key="i1", n=800, spacer_on=True, spacer_width=1.0)
    for vals in (_horizontals(lines), _verticals(lines)):
        closest = min(b - a for a, b in zip(vals, vals[1:]))
        assert closest > 2.0, (
            f"two dashes are {closest:.2f} mm apart — close enough to read as "
            f"one marker drawn twice")


def test_the_ends_of_the_page_keep_the_same_gap_as_the_middle():
    """*"The distance between the first marker on top of page and the next
    marker, as well as the distance between the last marker on the bottom of the
    page and the previous dash, are different from other distances."*"""
    geom, lay, lines = _lines(key="i1", n=800, spacer_on=True, spacer_width=1.0)
    for vals in (_horizontals(lines), _verticals(lines)):
        gaps = [round(b - a, 4) for a, b in zip(vals, vals[1:])]
        assert gaps[0] == gaps[len(gaps) // 2] == gaps[-1], (
            f"first gap {gaps[0]}, middle {gaps[len(gaps)//2]}, last {gaps[-1]}")


# --- 2. what they line up with ----------------------------------------------

@pytest.mark.parametrize("spacer_mm", [0.0, 0.5, 1.0, 2.5, 5.0])
def test_a_dash_sits_at_the_centre_of_every_patch(spacer_mm):
    """The point of the whole feature, in the form Knut settled on after seeing
    beta.7 on paper:

        *"It would be better if the dash would be centred vertically to the
        centre of the spacer thickness (height) above each patch … then the
        middle dash between them will always fall centred within in the patch
        height."*

    Anchoring on the patch BOUNDARY put that in-between dash half a spacer past
    the patch centre. Anchoring on the centre of the gap puts it exactly on the
    centre, for any spacer width.
    """
    geom, lay, lines = _lines(key="i1", n=800, spacer_on=spacer_mm > 0,
                              spacer_width=spacer_mm)
    place = G.placement(geom, A4_W, A4_H, lay)
    ys = _horizontals(lines)
    band = 2.0 + 2.0            # the corner-clear band, where dashes are dropped
    for j in range(lay.steps_in_pass):
        want = place.y_of(j) + place.plen / 2.0
        if not (band < want < A4_H - band):
            continue            # inside a corner, deliberately not drawn
        assert any(abs(y - want) < 1e-4 for y in ys), (
            f"no dash at the centre of patch {j} ({want:.3f} mm) with a "
            f"{spacer_mm} mm spacer")


@pytest.mark.parametrize("spacer_mm", [0.5, 1.0, 2.5, 5.0])
def test_a_dash_sits_at_the_centre_of_every_spacer(spacer_mm):
    """The other half of his rule — the marks alternate spacer centre, patch
    centre, spacer centre — which is what keeps the spacing even."""
    geom, lay, lines = _lines(key="i1", n=800, spacer_on=True,
                              spacer_width=spacer_mm)
    place = G.placement(geom, A4_W, A4_H, lay)
    ys = _horizontals(lines)
    pitch = place.y_of(1) - place.y_of(0)
    band = 4.0
    for j in range(lay.steps_in_pass):
        want = place.y_of(j) - (pitch - place.plen) / 2.0
        if not (band < want < A4_H - band):
            continue
        assert any(abs(y - want) < 1e-4 for y in ys), (
            f"no dash at the centre of the spacer above patch {j} "
            f"({want:.3f} mm)")


def test_the_boundary_is_no_longer_where_a_dash_goes_when_there_is_a_spacer():
    """Guards the shape of his change: with a spacer the dashes must have MOVED
    off the patch edges, or the previous scheme is still in place."""
    geom, lay, lines = _lines(key="i1", n=800, spacer_on=True, spacer_width=3.0)
    place = G.placement(geom, A4_W, A4_H, lay)
    ys = _horizontals(lines)
    on_edge = [j for j in range(1, lay.steps_in_pass - 1)
               if any(abs(y - place.y_of(j)) < 1e-4 for y in ys)]
    assert not on_edge, f"dashes still sit on the patch edges of {on_edge[:5]}"


def test_a_dash_sits_at_the_centre_of_every_strip():
    """The same rule across the page, so both edges behave identically."""
    geom, lay, lines = _lines(n=800)
    place = G.placement(geom, A4_W, A4_H, lay)
    xs = _verticals(lines)
    band = 4.0
    cols = lay.patches_per_page // lay.steps_in_pass
    for p in range(cols):
        want = place.x_of(p) + place.pwid / 2.0
        if not (band < want < A4_W - band):
            continue
        assert any(abs(x - want) < 1e-4 for x in xs), (p, want)


def test_the_step_is_half_the_patch_pitch():
    """Which is what makes 'a dash at every patch centre' and 'every gap equal'
    hold at the same time — the two are otherwise incompatible with a spacer."""
    geom, lay, lines = _lines(key="i1", n=800, spacer_on=True, spacer_width=2.0)
    place = G.placement(geom, A4_W, A4_H, lay)
    pitch = place.y_of(1) - place.y_of(0)
    assert _gaps(_horizontals(lines)) == [round(pitch / 2, 4)]


# --- 3. the spacers are part of the sum -------------------------------------

def test_widening_the_spacer_widens_the_gap():
    """Nothing here hard-codes a spacer width; the layout is asked what the
    spacing actually came out as."""
    seen = {}
    for spacer in (0.0, 1.0, 3.0):
        geom, lay, lines = _lines(key="i1", n=800, spacer_on=spacer > 0,
                                  spacer_width=spacer)
        seen[spacer] = _gaps(_horizontals(lines))[0]
    assert seen[0.0] < seen[1.0] < seen[3.0], seen


# --- 4. corners stay clear (his eight-case rule) ----------------------------

@pytest.mark.parametrize("edge,length", [(1.0, 1.0), (2.0, 2.0), (5.0, 4.0),
                                         (10.0, 8.0), (25.0, 10.0)])
def test_the_dashes_never_meet_in_a_corner(edge, length):
    """*"When increasing the 'Distance from page edge' the dashes for the
    vertical and for the horizontal dashes cross paths in each corner."*

    He stated the fix as eight cases — top/bottom dashes suppressed near the left
    and right edges, left/right dashes suppressed near the top and bottom. All
    eight are the same rule seen from four sides: a dash is not drawn if it lands
    within, or beyond, the band the perpendicular edge's dashes occupy.
    """
    geom, lay, lines = _lines(key="i1", n=800, edge=edge, length=length)
    band = edge + length
    for x0, y0, x1, y1 in lines:
        if x0 == x1:                     # a top/bottom dash, at column x0
            assert band < x0 < A4_W - band, (
                f"a top/bottom dash at x={x0} reaches into the "
                f"left/right band (0-{band} mm)")
        else:                            # a left/right dash, at row y0
            assert band < y0 < A4_H - band, (
                f"a left/right dash at y={y0} reaches into the "
                f"top/bottom band (0-{band} mm)")


def test_clearing_the_corners_does_not_disturb_the_spacing():
    """The dashes that remain are still one even comb — suppression removes
    from the ends, it does not renumber what is left."""
    geom, lay, lines = _lines(key="i1", n=800, edge=15.0, length=10.0)
    assert len(_gaps(_horizontals(lines))) == 1


# --- 5. the edge arithmetic --------------------------------------------------

def test_the_a4_example_from_the_issue():
    """Left 1→4 mm, right 206→209 mm, top 1→4 mm, bottom 293→296 mm."""
    _, _, lines = _lines(edge=1.0, length=3.0)
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


def test_every_dash_stays_on_the_sheet():
    _, _, lines = _lines()
    for a, b, c, d in lines:
        assert 0 <= a <= A4_W and 0 <= c <= A4_W, (a, c)
        assert 0 <= b <= A4_H and 0 <= d <= A4_H, (b, d)


# --- 6. every paper, orientation and instrument -----------------------------

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


# --- 7. the ColorMunki stagger, measured rather than assumed ----------------

def test_the_stagger_matches_the_marker_spacing_without_spacers():
    """Knut's reasoning holds exactly when there are no spacers: the offset is
    then precisely half a patch, which is the marker spacing."""
    geom = I.build("CM", cm_stagger=True, spacer_on=False)
    lay = G.compute(geom, A4_W, A4_H, 400)
    place = G.placement(geom, A4_W, A4_H, lay)
    assert geom.row_stagger_mm == pytest.approx(place.plen / 2)


def test_a_spacer_makes_the_stagger_a_quarter_spacer_deeper():
    """With spacers the engine staggers by ``0.5 * (plen + 0.5 * pspa)``, so the
    offset strips sit a quarter of a spacer below their markers. Recorded
    because it is real and measured; Knut ruled that the first strip is the
    reference, so the markers do not chase it."""
    geom = I.build("CM", cm_stagger=True, spacer_on=True)
    lay = G.compute(geom, A4_W, A4_H, 400)
    place = G.placement(geom, A4_W, A4_H, lay)
    drift = abs(geom.row_stagger_mm - place.plen / 2)
    assert drift == pytest.approx(place.pspa / 4)
    assert drift < 0.5, "a bigger drift than this would need telling him again"


# --- 8. the defaults he asked for -------------------------------------------

def test_both_defaults_are_two_millimetres():
    """*"change the default value for the two spinboxes to 2.0 mm (same for
    both)"* — and they must agree across every layer that carries one, or a
    chart built from a stored recipe silently differs from the panel."""
    import inspect
    from core.settings import DEFAULTS
    from workflow.layout_engine.presets import LayoutRecipe
    from workflow.layout_engine.chart import build_chart
    from workflow.layout_engine.raster import render_pages

    assert DEFAULTS["helper_marker_edge_mm"] == 2.0
    assert DEFAULTS["helper_marker_len_mm"] == 2.0
    r = LayoutRecipe()
    assert r.helper_marker_edge_mm == 2.0
    assert r.helper_marker_len_mm == 2.0
    for fn, names in ((build_chart, ("helper_marker_edge", "helper_marker_len")),
                      (render_pages, ("helper_marker_edge_mm",
                                      "helper_marker_len_mm"))):
        params = inspect.signature(fn).parameters
        for n in names:
            assert params[n].default == 2.0, f"{fn.__name__}.{n}"


def test_the_geometry_defaults_match_too():
    import inspect
    p = inspect.signature(G.helper_marker_lines_mm).parameters
    assert p["edge_mm"].default == 2.0
    assert p["length_mm"].default == 2.0


# --- 9. refusing to draw something silly ------------------------------------

def test_markers_that_would_meet_in_the_middle_are_refused():
    """Nonsense settings draw nothing rather than covering the chart."""
    _, _, lines = _lines(edge=100.0, length=100.0)
    assert lines == []


def test_a_zero_length_marker_draws_nothing():
    _, _, lines = _lines(length=0.0)
    assert lines == []

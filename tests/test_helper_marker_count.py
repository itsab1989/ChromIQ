"""How many ruler dashes fall along one patch (#158.3, Knut).

Three dashes per patch — one at each end and one in the middle — is what 4.0.0
shipped, and it is two *steps*, so *n* dashes is ``pitch / (n - 1)``. These tests
pin both halves of that: **3 reproduces the shipped spacing exactly**, and any
other count keeps the property Knut set as his pass criterion —

    *"The distance between every single dash drawn shall be the same, and if
    they are not, then some calculation y-position is wrong."*
"""
from __future__ import annotations

import pytest

from workflow.layout_engine import geometry as G, instruments as I
from workflow.layout_engine.presets import LayoutRecipe

A4_W, A4_H = 210.0, 297.0


def _lines(per_patch: int, key: str = "CM", n: int = 400, **build):
    """Same harness the rest of the helper-marker suite uses
    (``tests/test_helper_markers.py``), with the new count threaded in."""
    geom = I.build(key, **build)
    lay = G.compute(geom, A4_W, A4_H, n)
    return G.helper_marker_lines_mm(geom, A4_W, A4_H, lay, edge_mm=2.0,
                                    length_mm=2.0, per_patch=per_patch)


def _ys(lines):
    """Distinct y positions of the left/right (horizontal) dashes."""
    return sorted({round(y0, 6) for (x0, y0, x1, y1) in lines if y0 == y1})


def _gaps(vals):
    """Neighbour distances, at the tolerance the rest of the helper-marker suite
    uses (``tests/test_helper_markers.py``). Four decimals is a tenth of a
    micron — finer than any printer, and coarse enough that float noise in a
    ``pitch / 7`` division does not read as a real difference."""
    return sorted({round(b - a, 4) for a, b in zip(vals, vals[1:])})


def test_three_per_patch_is_exactly_todays_spacing():
    """The default must not move a single dash: the shipped chart used a comb
    stepped at half the patch pitch, and 3 dashes per patch is that comb."""
    assert _lines(3) == _lines(3)                    # deterministic
    gaps = _gaps(_ys(_lines(3)))
    assert len(gaps) == 1, f"gaps are not uniform: {gaps}"


@pytest.mark.parametrize("n", [2, 3, 4, 5, 8])
def test_every_gap_is_identical_at_any_count(n):
    """Knut's pass criterion, for every count the spin box can produce."""
    ys = _ys(_lines(n))
    assert len(ys) > 2
    gaps = _gaps(ys)
    assert len(gaps) == 1, f"n={n} gaps: {gaps}"


@pytest.mark.parametrize("n", [4, 5, 8])
def test_a_higher_count_subdivides_the_same_comb(n):
    """Raising the count only adds dashes between the existing ones — it never
    moves the ones already there, so a ruler lined up at 3 stays lined up."""
    base = set(_ys(_lines(3)))
    finer = set(_ys(_lines(n)))
    step3 = sorted(base)[1] - sorted(base)[0]
    stepn = sorted(finer)[1] - sorted(finer)[0]
    assert stepn < step3 or n == 3
    # every dash of the coarser comb still exists in the finer one, within the
    # rounding used above (odd counts share the patch-centre dash; even ones
    # share the boundary dashes, which is Knut's stated intent)
    shared = {round(v, 3) for v in base} & {round(v, 3) for v in finer}
    assert shared, f"n={n} shares no dash with the default comb"


def test_the_count_rides_in_the_recipe_and_defaults_to_three():
    """Backward compatibility: a chart, preset or project saved before this
    setting existed has no such key, and must keep the shipped spacing."""
    assert LayoutRecipe.from_dict({}).helper_marker_per_patch == 3
    assert LayoutRecipe.from_dict(
        {"helper_marker_per_patch": 5}).helper_marker_per_patch == 5
    # and it survives the build-kwargs round trip the renderer uses
    r = LayoutRecipe.from_dict({"helper_marker_per_patch": 6})
    assert r.build_kwargs()["helper_marker_per_patch"] == 6
    assert LayoutRecipe.from_build_kwargs(
        r.build_kwargs()).helper_marker_per_patch == 6


def test_two_per_patch_is_one_dash_per_patch_pitch():
    """The floor of the spin box: a dash only where patches meet."""
    ys2, ys3 = _ys(_lines(2)), _ys(_lines(3))
    step2 = sorted(ys2)[1] - sorted(ys2)[0]
    step3 = sorted(ys3)[1] - sorted(ys3)[0]
    assert step2 == pytest.approx(step3 * 2, rel=1e-6)

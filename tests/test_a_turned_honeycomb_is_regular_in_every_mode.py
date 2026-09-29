"""A TURNED honeycomb is a regular honeycomb too, in every layout mode.

`tests/test_hex_aspect_is_regular.py` already holds the rule for a pointy-top
sheet: the slot must be ``pwid * sqrt(3)/2`` so the apexes interlock. The CR30
can be turned 30 degrees (Basti, 2026-09-09: *"the rotation should not stretch
them"*), and then the same hexagon sits the other way up -- across the flats
moves to the VERTICAL and the point-to-point width moves to the horizontal --
so the slot relation inverts to ``plen = pwid * 2/sqrt(3)``.

`area_fit.derive_area_patch_size` knew that when it set the solver's floor and
did NOT know it when it snapped the derived height back afterwards: the snap
spelled ``sqrt(3)/2`` out a second time, so a turned honeycomb was solved on
one relation and pinned onto the other, three quarters of the height it had
just earned. Measured on screen over six settings on 2026-09-11, the drawn
hexagon came out **1.535 to 1.549** wide for every 1 tall where a regular one
is 1.1547 -- exactly 4/3 too wide, and Knut reported it as "flattened".

The measurement here is the DRAWN hexagon, from `hexagon.vertices`, not the
slot: the slot is what the solver produces and the drawn shape is what the eye
judges, and on a flat-top sheet the two differ by the apex overhang that is
taken off the width.
"""
import math
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from workflow.layout_engine import area_fit, hexagon, instruments  # noqa: E402

#: A regular hexagon measured across its points against across its flats.
REGULAR = 2.0 / math.sqrt(3.0)          # 1.15470…

PAPERS = ("A4", "A3", "Letter")

#: Every way the area-first panel can describe a grid, including the two Knut
#: drove: "By patch width" at four widths and "By columns / rows".
RECIPES = [
    ("by_width-5.0", dict(area_method="by_width", area_min_patch=5.0)),
    ("by_width-7.0", dict(area_method="by_width", area_min_patch=7.0)),
    ("by_width-9.0", dict(area_method="by_width", area_min_patch=9.0)),
    ("by_width-12.0", dict(area_method="by_width", area_min_patch=12.0)),
    ("by_width-auto", dict(area_method="by_width", area_min_patch=0.0)),
    ("by_grid-12x18", dict(area_method="by_grid", area_cols=12, area_rows=18)),
    ("by_grid-15xauto", dict(area_method="by_grid", area_cols=15, area_rows=0)),
    ("by_grid-autox20", dict(area_method="by_grid", area_cols=0, area_rows=20)),
]


def _kw(paper="A4", *, hflag=True, flat_top=True, mode="area_first",
        instrument="CR30", ratio=100.0, **extra):
    kw = dict(instrument=instrument, paper=paper, spacer_on=True, pscale=1.0,
              margins=(6.0,) * 4, border=6.0, nolimit=False, hflag=hflag,
              hex_flat_top=flat_top, layout_mode=mode, area_ratio=ratio)
    kw.update(extra)
    return kw


def _geom(kw):
    return instruments.geom_from_build_kwargs(kw, thresholds=None)


def _drawn(geom):
    """(width, height) of the hexagon actually painted into *geom*'s slot."""
    pts = hexagon.vertices(0.0, 0.0, geom.pwid, geom.plen,
                           flat_top=bool(getattr(geom, "hex_flat_top", False)))
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return max(xs) - min(xs), max(ys) - min(ys)


# ---------------------------------------------------------------------------
# the fault
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("paper", PAPERS)
@pytest.mark.parametrize("tag,recipe", RECIPES, ids=[r[0] for r in RECIPES])
def test_a_turned_honeycomb_is_drawn_regular_under_area_first(paper, tag, recipe):
    g = _geom(_kw(paper, **recipe))
    assert g.hexagonal and g.hex_flat_top
    w, h = _drawn(g)
    assert abs(w / h - REGULAR) <= 0.01, (
        f"CR30 turned / {paper} / {tag}: drawn {w:.2f} x {h:.2f} mm = "
        f"{w / h:.4f} wide for every 1 tall, and a regular hexagon is "
        f"{REGULAR:.4f}. x{(w / h) / REGULAR:.3f} of regular.")


@pytest.mark.parametrize("paper", PAPERS)
@pytest.mark.parametrize("tag,recipe", RECIPES, ids=[r[0] for r in RECIPES])
def test_the_turned_slot_keeps_the_turned_relation(paper, tag, recipe):
    """The slot behind the drawn shape: turned, the long axis is the HEIGHT."""
    g = _geom(_kw(paper, **recipe))
    need = g.pwid * REGULAR
    assert abs(g.plen - need) <= 0.02, (
        f"CR30 turned / {paper} / {tag}: slot {g.pwid:.2f} x {g.plen:.2f}, a "
        f"turned regular hexagon needs plen {need:.2f}")


def test_patch_first_was_never_wrong_and_still_is_not():
    """The control Knut himself gave: "Prioritise patch size" looked right."""
    g = _geom(_kw(mode="patch_first"))
    w, h = _drawn(g)
    assert abs(w / h - REGULAR) <= 0.01


def test_the_mutation_lands():
    """The 4/3 stretch this file exists to catch, arithmetic and all.

    `derive_area_patch_size` used to snap a turned honeycomb's height onto the
    POINTY-top relation. That is the same as multiplying the right height by
    3/4, so rebuilding the geometry with that height must fail the check above
    -- otherwise the check is measuring nothing.
    """
    g = _geom(_kw(area_method="by_width", area_min_patch=7.0))
    import dataclasses
    hurt = dataclasses.replace(g, plen=g.plen * 3.0 / 4.0)
    w, h = _drawn(hurt)
    assert abs(w / h - REGULAR) > 0.01, (
        "a height 3/4 of the right one still measures regular, so the "
        "tolerance above is too loose to catch the bug")
    assert 1.53 < w / h < 1.55, (
        f"the bug's own signature is 1.535-1.549; this mutation gives {w / h:.4f}")


# ---------------------------------------------------------------------------
# …and the three things that must not have moved
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("paper", PAPERS)
@pytest.mark.parametrize("tag,recipe", RECIPES, ids=[r[0] for r in RECIPES])
def test_an_untured_honeycomb_is_unchanged(paper, tag, recipe):
    """Pointy-top hexagons were already right and must stay exactly as they
    were: `hex_ratio` is sqrt(3)/2 for them, which is what the snap always
    used."""
    g = _geom(_kw(paper, flat_top=False, **recipe))
    assert g.hexagonal and not g.hex_flat_top
    w, h = _drawn(g)
    assert abs(h / w - REGULAR) <= 0.01, (
        f"CR30 pointy / {paper} / {tag}: drawn {w:.2f} x {h:.2f} mm")
    assert abs(g.plen - g.pwid * math.sqrt(3) / 2.0) <= 0.02


@pytest.mark.parametrize("instrument", ["i1", "p3", "CM", "SS", "CR30"])
@pytest.mark.parametrize("paper", PAPERS)
@pytest.mark.parametrize("tag,recipe", RECIPES, ids=[r[0] for r in RECIPES])
def test_a_rectangular_chart_cannot_see_the_turn(instrument, paper, tag, recipe):
    """THE REGRESSION ARGUMENT, AND IT IS STRUCTURAL RATHER THAN STATISTICAL.

    The changed line is reached only when this recipe makes a honeycomb, and
    the value it now uses is decided by `hex_flat_top`. So the whole of the
    change is invisible to a rectangular chart, and the way to say that as a
    test is that flipping the turn moves a rectangular layout by nothing at
    all -- not "by little", by nothing.
    """
    off = area_fit.derive_area_patch_size(
        _kw(paper, hflag=False, flat_top=False, instrument=instrument, **recipe))
    on = area_fit.derive_area_patch_size(
        _kw(paper, hflag=False, flat_top=True, instrument=instrument, **recipe))
    assert off == on, (
        f"{instrument}/{paper}/{tag}: a rectangular chart changed size when the "
        f"hexagon turn was flipped: {off} -> {on}")


@pytest.mark.parametrize("tag,recipe", RECIPES, ids=[r[0] for r in RECIPES])
def test_the_spectroscan_is_never_turned(tag, recipe):
    """`hex_capable` is true for the SpectroScan, which is never offered the
    turn. Setting the flag on one must not invert its hexagons -- the same
    instrument-named gate the solver's floor already had."""
    a = _geom(_kw(instrument="SS", flat_top=False, **recipe))
    b = _geom(_kw(instrument="SS", flat_top=True, **recipe))
    assert (a.pwid, a.plen) == (b.pwid, b.plen)
    assert abs(a.plen - a.pwid * math.sqrt(3) / 2.0) <= 0.02

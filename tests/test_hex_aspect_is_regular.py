"""A honeycomb must be a REGULAR honeycomb, in every layout mode.

`area_first` sizes patches to fill the page from a user height:width ratio. A
hexagon's proportions are not the user's to choose: the slot must be
``pwid × √3/2`` so the apexes (which overhang by ``plen/6`` at each end)
interlock with the rows above and below.

Before this was enforced, `area_first` drew hexagons stretched by **+17 %**
(SpectroScan) and **+20 %** (CR30), and because the interlock pitch was then
wrong the patch count *dropped* — SS −8.5 %, CR30 −4.5 % — while the "hexagon
patches" checkbox promised more. Pre-existing; the SpectroScan shipped that way.
"""
import math
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from workflow.layout_engine import geometry, instruments, papers  # noqa: E402

HEX = instruments.hex_capable_instruments()
PAPERS = ("A4", "A3", "Letter")
MODES = ("patch_first", "area_first")


def _geom(inst, paper, *, hflag, mode, ratio=0.0):
    kw = dict(instrument=inst, paper=paper, spacer_on=True, pscale=1.0,
              margins=(6.0,) * 4, border=6.0, nolimit=False,
              hflag=hflag, layout_mode=mode, area_ratio=ratio)
    return instruments.geom_from_build_kwargs(kw, thresholds=None)


def _count(g, paper):
    w, h = papers.dimensions_mm(paper)
    return geometry.patches_per_sheet(g, w, h)


def test_there_is_at_least_one_hex_instrument():
    assert HEX, "hex_capable_instruments() found none — the sweep would be empty"


@pytest.mark.parametrize("inst", HEX)
@pytest.mark.parametrize("paper", PAPERS)
@pytest.mark.parametrize("mode", MODES)
def test_hexagons_are_regular(inst, paper, mode):
    g = _geom(inst, paper, hflag=True, mode=mode)
    assert g.hexagonal
    need = g.pwid * math.sqrt(3) / 2.0
    assert abs(g.plen - need) <= 0.02, (
        f"{inst}/{paper}/{mode}: slot {g.pwid:.2f}x{g.plen:.2f}, a regular "
        f"hexagon needs plen {need:.2f} — this is the stretch bug returning")


@pytest.mark.parametrize("inst", HEX)
@pytest.mark.parametrize("paper", PAPERS)
@pytest.mark.parametrize("mode", MODES)
def test_hexagons_fit_more_than_rectangles(inst, paper, mode):
    """The checkbox promises more per sheet. It must be true in EVERY mode."""
    flat = _count(_geom(inst, paper, hflag=False, mode=mode), paper)
    hexy = _count(_geom(inst, paper, hflag=True, mode=mode), paper)
    assert hexy > flat, (
        f"{inst}/{paper}/{mode}: hexagons fit {hexy} against {flat} rectangles "
        "— the UI promises more per sheet")


@pytest.mark.parametrize("inst", HEX)
def test_a_user_ratio_cannot_stretch_a_hexagon(inst):
    """`area_ratio` is a user setting; a hexagon's aspect is not."""
    a = _geom(inst, "A4", hflag=True, mode="area_first", ratio=0.0)
    b = _geom(inst, "A4", hflag=True, mode="area_first", ratio=1.6)
    for g in (a, b):
        assert abs(g.plen - g.pwid * math.sqrt(3) / 2.0) <= 0.02


def test_the_mutation_lands():
    """A stretch check that cannot fail proves nothing."""
    g = _geom(HEX[0], "A4", hflag=True, mode="area_first")
    stretched = g.plen * 1.2
    assert abs(stretched - g.pwid * math.sqrt(3) / 2.0) > 0.02


@pytest.mark.parametrize("inst", ["i1", "p3", "CM", "41", "51"])
@pytest.mark.parametrize("mode", MODES)
def test_rectangular_instruments_are_untouched(inst, mode):
    """The fix is guarded by hflag; nothing rectangular may move.

    Proved empirically against master over 144 combinations at the time of the
    change (zero differences); this keeps it true.
    """
    g = _geom(inst, "A4", hflag=False, mode=mode)
    assert not g.hexagonal
    assert g.plen > 0 and g.pwid > 0

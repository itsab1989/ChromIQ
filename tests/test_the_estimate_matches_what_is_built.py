"""The patch count the user is promised must be the one they get.

Guided offered 368 patches for a CR30 A4 sheet that holds 345 (Basti,
2026-09-01). The estimate assembles its build kwargs BY HAND
(`TabChart._engine_geom`) instead of going through a `LayoutRecipe`, so a key
it does not set reads as absent — and the row-label floor then computed a
10.43 mm left margin against the build's 14.43 mm.

This does not test the wording of an estimate: it lays out the same sheet both
ways and compares the numbers. The hand-built kwargs are the ones the tab
really uses, copied here, so if that call site grows a new key this test keeps
answering the same question.
"""
import pytest

from workflow.layout_engine import geometry, instruments, papers, presets

_PAPERS = ("A4", "Letter")


def _hand_built(instr: str, paper: str, *, spacers: bool):
    """What `TabChart._engine_geom` assembles for the capacity estimate."""
    kw = dict(instrument=instr, paper=paper, spacer_on=spacers,
              pscale=1.0, margins=(6.0,) * 4, border=6.0, nolimit=False)
    if not spacers:
        kw["spacer_mode"] = "none"
    if instr in ("i1", "p3", "CM"):
        kw["edge_spacers"] = True
    return instruments.geom_from_build_kwargs(kw, thresholds=None)


def _from_a_recipe(instr: str, paper: str, *, spacers: bool):
    r = presets.default_recipe(instr, paper)
    r.margin_top = r.margin_right = r.margin_bottom = r.margin_left = 6.0
    r.spacer_on = spacers
    if not spacers:
        r.spacer_mode = "none"
    return instruments.geom_from_build_kwargs(r.build_kwargs())


def test_a_guided_cr30_sheet_is_promised_what_it_holds():
    """The reported case: Guided offered 368 for a sheet that holds 345.

    Both sides here are the GUIDED chart — the estimate's hand-built kwargs and
    a recipe carrying the same Guided choices (no spacers, 6 mm margins). An
    earlier version of this test compared the estimate against the MANUAL
    default recipe, which is a different chart altogether (clip border, patch
    scale), and its 462-vs-682 failures said nothing about the fault.
    """
    w_mm, h_mm = papers.dimensions_mm("A4")
    est = _hand_built("CR30", "A4", spacers=False)
    real = _from_a_recipe("CR30", "A4", spacers=False)
    assert est.margin_l == pytest.approx(real.margin_l, abs=0.01), (
        f"the estimate lays out from a {est.margin_l:.2f} mm left margin and "
        f"the build from {real.margin_l:.2f} mm")
    a = geometry.patches_per_sheet(est, w_mm, h_mm)
    b = geometry.patches_per_sheet(real, w_mm, h_mm)
    assert a == b, (
        f"the estimate promises {a} patches per sheet and the build fits {b}")


def test_a_missing_text_distance_key_does_not_change_the_geometry():
    """The specific slip: an absent key must mean the recipe's default, not 0."""
    base = dict(instrument="CR30", paper="A4", spacer_on=False,
                spacer_mode="none", pscale=1.0, margins=(6.0,) * 4,
                border=6.0, nolimit=False)
    absent = instruments.geom_from_build_kwargs(dict(base), thresholds=None)
    spelled = instruments.geom_from_build_kwargs(
        dict(base, text_edge_clip=4.0), thresholds=None)
    assert absent.margin_l == pytest.approx(spelled.margin_l, abs=0.01), (
        "leaving the text-distance key out of the build kwargs produced a "
        "different left margin from spelling out its default")

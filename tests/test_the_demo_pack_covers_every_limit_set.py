"""B8-393: the demo package must exercise every judgeable row on EVERY set.

Knut, 2026-09-18, tightening his beta-22 release condition:

    *"those eleven can also be defined for all the Judge Against limit sets, so
    the demo data must verify that all thresholds can trigger correctly for
    every judged against limit set, not just test all the thresholds on one of
    the sets. Also, some tests require a test chart with From Profile Gamut,
    which must also be included."*

The pack itself is built by `scripts/make_report_limit_demos.py` and its own
`matrix_faults()` refuses to ship a pack with an incomplete cell, which is the
real guard: it runs on every rebuild with the real data in front of it. What
THIS file guards is the things a rebuild cannot notice, because they are about
the plan rather than the data:

* every selectable limit set has runs of its own;
* the FROM PROFILE GAMUT chart is in the package;
* the control strip in the package is the one CHROMIQ declares and not one
  this generator picked, and the package holds all three answers the app can
  give about a chart: a full strip, a strip too small for the 95th-percentile
  row, and a refusal;
* `fill_limits` never overwrites a number a set already ships, and never
  invents one for a row ChromIQ cannot measure.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = ROOT / "scripts" / "make_report_limit_demos.py"


@pytest.fixture(scope="module")
def gen():
    """The generator, imported as a module.

    It must be registered in ``sys.modules`` before it is executed: it defines
    dataclasses, and `dataclasses` resolves a string annotation by looking the
    class's own module up there. Loading it without that step fails with
    ``'NoneType' object has no attribute '__dict__'``, which says nothing about
    the cause.
    """
    spec = importlib.util.spec_from_file_location("_demo_gen_sets", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_demo_gen_sets"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    try:
        yield mod
    finally:
        sys.modules.pop("_demo_gen_sets", None)


def _plans(gen):
    return [(name, plan) for name, plans in gen.PROJECTS for plan in plans]


def test_every_selectable_limit_set_has_runs_of_its_own(gen):
    """Not "the sets we happened to use": the sets the WINDOW offers.

    MUTATION: drop one entry from `MATRIX_SETS` and this goes red, because a
    set the report window will offer then has no run in the package.
    """
    from workflow.compliance_sets import selectable_set_ids
    offered = set(selectable_set_ids({}))
    used = {plan.set_id for _n, plan in _plans(gen)}
    missing = sorted(offered - used)
    assert not missing, (
        f"the report window offers {sorted(offered)} and the package has no "
        f"run bound to {missing}, so those columns are never exercised")


def test_the_package_contains_a_from_profile_gamut_chart(gen):
    """Knut asked for one by name, and three rows depend on it.

    Paper white, Solid colours largest and CMY hue difference need
    ``reference_source == "colorimetric"``, which only a chart carrying a
    ``<stem>-reference.ti3`` produces. Before one was in the pack those three
    read `needs_reference_file` in 80 of 80 saved reports.
    """
    gamut = [(n, p) for n, p in _plans(gen)
             if isinstance(p.verify_chart, gen.GamutChartRecipe)]
    assert gamut, ("no run in the package verifies with a FROM PROFILE GAMUT "
                   "chart, so the three reference rows cannot be judged at all")
    assert len({n for n, _p in gamut}) >= 2, (
        "only one project uses a profile-gamut chart; the matrix needs one "
        "under every limit set as well as the isolation project")


def test_the_package_never_picks_its_own_control_strip(gen):
    """THE STRIP IN THE PACK MUST BE THE ONE CHROMIQ WRITES, not one this
    generator chose.

    Until 2026-09-19 the generator selected 24 patches of its own, because
    nothing in ChromIQ wrote a declaration at all (B8-405). That fixture
    demonstrated the fixture: it picked the OPPOSITE population to the one the
    app now writes (mid-gamut patches, deliberately no grey, no bare paper and
    no cube corner, against ChromIQ's substrate + corners + tints + greys), so
    every verdict it produced would have agreed with itself whatever the app
    did.

    MUTATION: give `declare_control_strip` a patch list of its own and this
    goes red, because the only selection allowed in this file is the app's.
    """
    import inspect
    src = inspect.getsource(gen.declare_control_strip)
    assert "declare_for_chart" in src, (
        "the generator no longer asks the app which patches make up the "
        "strip, so the package demonstrates its own selection rule")
    body = gen.declare_control_strip.__code__
    assert "sample_ids" not in body.co_names and "ids" not in body.co_consts, (
        "declare_control_strip appears to be choosing patches itself")
    whole = _SCRIPT.read_text(encoding="utf-8")
    assert "def control_strip_ids(" not in whole, (
        "the generator's own control-strip selection is back; the pack would "
        "then be evidence about this script and not about ChromIQ")


def test_the_pack_holds_a_chart_chromiq_refuses_a_strip_for(gen):
    """The half Knut asked to be able to watch: the refusal.

    A plan states what ChromIQ is expected to answer about its chart, and
    `build_run` stops the build when the answer differs, so this only has to
    check that both answers are claimed somewhere.
    """
    from workflow.control_strip import OUTCOME_TOO_FEW, OUTCOME_WRITTEN
    want = {p.expect_strip for _n, p in _plans(gen)}
    assert OUTCOME_WRITTEN in want, (
        "no run expects ChromIQ to declare a control strip, so the three "
        "strip rows are never judged anywhere in the package")
    assert OUTCOME_TOO_FEW in want, (
        "no run expects ChromIQ to REFUSE a control strip, so the package "
        "never shows a reader the report saying 'this chart declares no "
        "control strip'")


def test_the_pack_holds_a_strip_too_small_for_the_95th_percentile(gen):
    """The third state, which is neither of the other two.

    `CONTROL_STRIP_MIN` is 8 and `CONTROL_STRIP_P95_MIN` is 20, so a chart can
    declare a strip and still have the 95th-percentile row withheld. Measured
    2026-09-19: a 20-patch chart fills 8 rungs and a FROM PROFILE GAMUT chart
    fills 17, and both are in the package.
    """
    from workflow.control_strip import OUTCOME_WRITTEN
    small = [p for _n, p in _plans(gen)
             if p.expect_strip == OUTCOME_WRITTEN and not p.expect_strip_p95]
    assert small, (
        "every declared strip in the package reaches twenty rungs, so nothing "
        "shows the report withholding the 95th-percentile row with "
        "control_strip_too_small while the other two strip rows are judged")


def test_a_chart_that_cannot_supply_the_surface_row_is_in_the_package(gen):
    """The half Knut asked to watch: the report DETECTING a missing metric.

    Every targen chart is full of patches on the surface of the device cube
    (measured over this package's sizes: 21 of 30 up to 200 of 405), so the
    grid recipe is the only way to reach the state at all.
    """
    grids = [p for _n, p in _plans(gen)
             if isinstance(p.verify_chart, gen.GridChartRecipe)]
    assert grids, ("no run uses the mid-tone grid chart, so the package never "
                   "shows the report detecting a chart with no surface-gamut "
                   "population")
    for p in grids:
        assert all(min(v, 100.0 - v) > gen.SURFACE_TOL
                   for v in p.verify_chart.levels), (
            f"the grid chart's levels {p.verify_chart.levels} include one "
            f"within {gen.SURFACE_TOL} of an edge of the cube, so the chart "
            f"DOES have a surface population and the run proves nothing")


def test_fill_limits_never_overwrites_a_number_the_set_already_ships(gen):
    """A typed-in limit is for the rows the set leaves empty, and no others.

    MUTATION: drop the `is_numeric` guard in `fill_limits` and this goes red on
    ChromIQ tight, whose 1.0 would be replaced by ChromIQ default's 2.0.
    """
    from workflow.compliance_sets import factory_limits
    for sid in ("chromiq_default", "chromiq_tight", "chromiq_quick"):
        factory = factory_limits(sid)
        for rid in gen.fill_limits(sid):
            lim = factory.get(rid)
            assert lim is None or not lim.is_numeric, (
                f"fill_limits({sid!r}) puts a number on {rid}, which that set "
                f"already limits at {lim.number}; a demo run would then be "
                f"judged against a column the app does not ship")


def test_fill_limits_never_numbers_a_row_chromiq_cannot_measure(gen):
    """`effective_limits` drops such an override anyway; a plan that writes one
    is claiming a cell the app will silently refuse."""
    from workflow.compliance_sets import ROW_BY_ID
    for sid in ("chromiq_default", "chromiq_tight", "chromiq_quick"):
        for rid in gen.fill_limits(sid):
            row = ROW_BY_ID.get(rid)
            assert row is not None and row.status in ("now", "build", "ref"), (
                f"fill_limits({sid!r}) numbers {rid}, whose status is "
                f"{getattr(row, 'status', 'unknown')!r}; the app refuses that "
                f"override and the run would be judged without it")


def test_the_matrix_designs_cover_every_set_and_both_directions(gen):
    """One design that crosses and one that does not, for every set."""
    for sid in gen.MATRIX_SETS:
        assert sid in gen.MATRIX, f"no matrix designs for {sid}"
        over, inside = gen.MATRIX[sid]
        assert over.bulk > inside.bulk, (
            f"{sid}'s 'everything over' design is not worse than its "
            f"'everything inside' one, so the pair cannot show a threshold "
            f"triggering and releasing")


def test_the_generator_refuses_a_pack_with_an_incomplete_cell(gen):
    """The real guard is the generator's own, so it must actually fail.

    MUTATION: make `matrix_faults` return [] and this goes red.
    """
    faults = gen.matrix_faults({"matrix_cells": [
        {"set": "chromiq_tight", "row": "all_de00_max", "over": "",
         "inside": "x/y/z", "complete": False}]})
    assert faults and "never over its limit" in faults[0]
    assert gen.matrix_faults({"matrix_cells": [
        {"set": "s", "row": "r", "over": "a", "inside": "b",
         "complete": True}]}) == []


def test_the_generator_no_longer_works_around_the_gamut_device_fault(gen):
    """B8-398 is fixed in the app, so the workaround must be gone from here.

    `select_gamut_targets` used to hand back device values from xicclu's
    numeric inverse with nothing bounding them (measured: 17 of 200 over 100,
    the largest 107.69), and this generator clamped them for itself so the
    package could demonstrate the three reference rows at all. B8-398 chose to
    DROP such a colour instead, because a clamped patch keeps an aim the ink
    cannot make. Re-measured 2026-09-19 on the same selection: 0 of 200
    outside the cube.

    A demo package that keeps a workaround for a fault the product has fixed
    is a package that hides the product. So the clamp is gone and a refusal
    stands in its place.

    MUTATION: put the clamp back and this goes red.
    """
    import inspect
    assert gen.GAMUT_DEVICE_CLAMP is False
    src = inspect.getsource(gen.make_gamut_chart)
    assert "min(100.0, max(0.0," not in src, (
        "make_gamut_chart is clamping the module's device values again; if "
        "the app has regressed, fix the app")
    assert "B8-398" in src and "raise SystemExit" in src, (
        "make_gamut_chart no longer REFUSES a selection outside the device "
        "cube, so a regression in the app would be papered over in demo data")


def test_the_completeness_check_does_not_ask_a_chart_file_for_a_verdict(gen):
    """`verify_pack` called both shipped packs INCOMPLETE, and it was wrong.

    A FROM PROFILE GAMUT chart ships `<stem>-reference.ti3` beside itself: the
    chart's AIM values, written at build time. Nobody measures it, so there is
    no verdict to save beside it, and `_verdicts_missing` demanded one.
    Measured 2026-09-19: `--verify` on the beta.21-era archive prints
    INCOMPLETE with 23 of these and nothing else.

    It matters because `verify_pack` is the release step's own check, and its
    docstring is about exactly this: a pack once shipped with two projects
    missing because the check that should have caught it compared the wrong
    thing. A check that is always red is a check nobody reads.

    MUTATION: drop the `-reference` suffix rule and this goes red.
    """
    assert gen._is_intermediate(
        "P/runs/run1/verifications/2028-01-05_100000/chart/P-verify-reference.ti3")
    assert gen._is_intermediate("P/runs/run1/verifications/P-verify-reference.ti3")
    # …and a real measurement is still asked for its verdict.
    assert not gen._is_intermediate(
        "P/runs/run1/verifications/2028-01-05_100000/P-verify.ti3")
    assert not gen._is_intermediate("P/runs/run1/P.ti3")
    # the two rules that were already there
    assert gen._is_intermediate("P/runs/run1/reads/read1.ti3")
    assert gen._is_intermediate("P/runs/run1/merged.ti3")

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
* the FROM PROFILE GAMUT chart is in the package, and so is a chart that
  declares a control strip;
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


def test_the_package_declares_a_control_strip_somewhere(gen):
    """A chart declares its own strip or those three rows are never judged."""
    strips = [p for _n, p in _plans(gen) if p.control_strip]
    assert strips, ("no run declares a control strip, so all three "
                    "control-strip rows read no_control_strip on every date")
    names = {p.control_strip_name for p in strips}
    assert len(names) >= 2, (
        "every declared strip carries the same name, so nothing in the pack "
        "shows that the name is read off the chart rather than built in")


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


def test_the_generator_clamps_the_gamut_module_s_device_values_and_says_why(gen):
    """F1: the app does not clamp, and the package says so rather than hiding it.

    `select_gamut_targets` takes its device values from xicclu's numeric
    inverse and nothing clamps them: measured, 17 of 200 came back over 100 on
    a channel and 15 over 101, and `measurement_report._rgb_to_0_100` then
    rescales the WHOLE chart by 100/255. If the app ever clamps, this test's
    reason for existing goes with it and the constant should go too; until
    then the generator must keep clamping and must keep explaining.
    """
    assert gen.GAMUT_DEVICE_CLAMP is True
    src = (ROOT / "scripts" / "make_report_limit_demos.py").read_text(
        encoding="utf-8")
    assert "107.69" in src, (
        "the clamp's note no longer carries the measurement that justifies it")
    assert "write_gamut_ti1" in src.split("GAMUT_DEVICE_CLAMP")[0][-3000:], (
        "the clamp's note no longer says where the fix belongs in the app")

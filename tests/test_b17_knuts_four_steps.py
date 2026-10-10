"""Beta 17 (#182): the neighbour check is Knut's four steps, on every chart
type, with every parameter per chart type.

Knut, 6071673457 (the four steps), adopted in 6078174421: "I think the 4
steps should be used"; neighbours "from any strip"; 6082015002: "add
neighbour check for calibration charts", "All the parameters in the shown
table should be configurable, for all chart types"; 6085694445: the
colour-neighbour radius stays, "I do not want a solution that has hidden
thresholds that change behaviour"; 6070058549: verification patch error limit
5, and the check on verification charts.

Each test here fails on beta 16: there the rule was "readings further apart
than the expected colours by more than a buffer AND further off than the
neighbours", from other strips only, and only on profiling charts.
"""
from __future__ import annotations

import pytest

from tests.test_neighbour_check_in_the_measure_tab import (  # noqa: F401
    _flags, _info, _read_all, _red, _strip, _tab, qapp)
from workflow import misread_settings as MS
from workflow import patch_flags as pf
from workflow.neighbour_check import NeighbourCheck


def _nc(rows, **kw):
    nc = NeighbourCheck(**kw)
    for r in rows:
        nc.set_reading_lab(*r)
    nc.evaluate()
    return nc


# ---- the four steps ---------------------------------------------------------
def test_step_by_step():
    """Neighbour errors 2, 4, 6 and 30 (median 5); own error 16: 16 - 5 = 11
    is more than the limit 10, so red; at limit 11 it is not."""
    rows = [("P", (50, 0, 0), (50, 16, 0), "A")]
    errs = (2, 4, 6, 30)
    for i, e in enumerate(errs):
        exp = (50, 1 + i, 0)
        rows.append((f"N{i}", exp, (50 + e, 1 + i, 0), "B"))
    nc = _nc(rows, limit=10.0)
    f = nc.finding("P")
    assert f.own_de == pytest.approx(16.0)
    assert f.median_de == pytest.approx(5.0)       # one outlier among four
    assert f.further == pytest.approx(11.0)
    assert f.suspect
    assert not _nc(rows, limit=11.0).is_suspect("P")


def test_below_zero_is_closer():
    rows = [("P", (50, 0, 0), (51, 0, 0), "A")]
    rows += [(f"N{i}", (50, 1 + i, 0), (55, 1 + i, 0), "B") for i in range(3)]
    f = _nc(rows).finding("P")
    assert f.further == pytest.approx(-4.0)
    assert not f.suspect


def test_two_to_four_neighbours_never_more_never_fewer():
    base = [("P", (50, 0, 0), (80, 0, 0), "A")]
    one = base + [("N0", (50, 1, 0), (50, 1, 0), "B")]
    assert not _nc(one).finding("P").checked          # 1 is not enough
    two = one + [("N1", (50, 2, 0), (50, 2, 0), "C")]
    assert _nc(two).is_suspect("P")                   # 2 are
    many = base + [(f"N{i}", (50, 1 + i, 0), (50, 1 + i, 0), "B")
                   for i in range(9)]
    assert len(_nc(many).finding("P").compared) == 4  # never more than 4


def test_no_hidden_threshold_far_neighbours_are_never_taken():
    """No "always 4" and no "twice the limit": beyond the colour-neighbour
    radius a patch is simply not compared (Knut 6085694445)."""
    rows = [("P", (50, 0, 0), (80, 0, 0), "A"),
            ("N0", (50, 20, 0), (50, 20, 0), "B"),
            ("N1", (50, -20, 0), (50, -20, 0), "C")]
    assert not _nc(rows, radius=15.0).finding("P").checked
    assert _nc(rows, radius=30.0).is_suspect("P")


# ---- Preferences decide every value, per chart type --------------------------
def test_the_defaults_per_chart_type():
    s = {}
    assert [MS.patch_error_limit(s, k) for k in MS.KINDS] == [95, 20, 5, 95]
    assert [MS.strip_test_on(s, k) for k in MS.KINDS] == [True, True, False,
                                                         True]
    assert MS.neighbour_check_on(s) is True
    assert [MS.neighbour_limit(s, k) for k in MS.KINDS] == [10, 5, 3, 10]
    assert [MS.neighbour_radius(s, k) for k in MS.KINDS] == [15, 30, 30, 30]
    assert MS.same_reading_tolerance(s) == 3.0
    assert MS.KINDS == ("estimated", "accurate", "verification",
                        "calibration")


def test_which_chart_type_a_measurement_is():
    ck = MS.chart_kind
    assert ck(calibration=True, predicted=True, accurate=True) == "calibration"
    assert ck(calibration=False, predicted=True, accurate=True) == \
        "verification"
    assert ck(calibration=False, predicted=False, accurate=True) == "accurate"
    assert ck(calibration=False, predicted=False, accurate=False) == \
        "estimated"


@pytest.mark.parametrize("kind", ["estimated", "accurate", "verification",
                                  "calibration"])
def test_each_chart_type_takes_its_own_values(qapp, tmp_path, monkeypatch,
                                              kind):
    settings = {}
    for i, k in enumerate(MS.KINDS):
        settings[MS.PATCH_ERROR_LIMIT_KEYS[k]] = 61.0 + i
        settings[MS.NEIGHBOUR_LIMIT_KEYS[k]] = 6.0 + i
        settings[MS.NEIGHBOUR_RADIUS_KEYS[k]] = 21.0 + i
        settings[MS.STRIP_TEST_KEYS[k]] = (i % 2 == 0)
    folder = tmp_path / ("cal" if kind == "calibration" else "run1")
    tab = _tab(folder, accurate=(kind == "accurate"), settings=settings)
    if kind == "verification":
        monkeypatch.setattr(type(tab), "_expected_is_predicted",
                            lambda self: True)
    assert tab._chart_kind() == kind
    i = MS.KINDS.index(kind)
    assert tab._patch_warn_limit() == 61.0 + i
    assert tab._neighbour_parameters() == (6.0 + i, 21.0 + i)
    assert tab._use_outlier_fence() is (i % 2 == 0)
    _read_all(tab)
    assert tab._nb_check.limit == 6.0 + i and tab._nb_check.radius == 21.0 + i


def test_the_same_reading_tolerance_is_the_users(qapp, tmp_path):
    """A re-read 3.6 ΔE*ab from the misread, still a misread: a different
    colour at the default 3 (so not yellow), the same colour at 5 (yellow)."""
    lim = {MS.NEIGHBOUR_LIMIT_KEYS["estimated"]: 5.0}
    tab = _tab(tmp_path, settings=lim)
    _read_all(tab, {"D6": 0.55})
    tab._on_strip_measured(_strip("D", {"D6": 0.65}))
    assert _flags(tab)["D6"] is pf.FLAG_RED
    tab2 = _tab(tmp_path / "t2", settings={**lim, MS.SAME_READING_KEY: 5.0})
    _read_all(tab2, {"D6": 0.55})
    tab2._on_strip_measured(_strip("D", {"D6": 0.65}))
    assert _flags(tab2)["D6"] == pf.FLAG_CONFIRMED


# ---- red, yellow, green, and red again ---------------------------------------
def test_red_yellow_green_and_red_again(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55, "B4": 0.55})
    assert set(_red(tab)) == {"B4", "D6"}
    tab._on_strip_measured(_strip("D", {"D6": 0.55}))      # the same: yellow
    assert _flags(tab)["D6"] == pf.FLAG_CONFIRMED
    tab._on_strip_measured(_strip("B"))                   # fits: green
    assert _flags(tab)["B4"] == pf.FLAG_CORRECTED
    tab._on_strip_measured(_strip("B", {"B4": 0.3}))      # misread again: red
    assert _flags(tab)["B4"] is pf.FLAG_RED


def test_only_its_own_reread_turns_a_neighbour_suspect_yellow(qapp, tmp_path):
    """Two suspects expected alike and off alike would confirm each other
    under the patch error limit's rule; not under the neighbour check."""
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55, "C6": 0.55})
    assert {"C6", "D6"} <= set(_red(tab))
    assert all(_info(tab, x)["reread_only"] for x in ("C6", "D6"))

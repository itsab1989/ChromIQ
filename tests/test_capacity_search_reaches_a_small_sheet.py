"""`_binary_search` must be able to reach a sheet smaller than its own guess.

THE BUG THIS PINS, MEASURED. `ChartCreator._binary_search` seeded its search
window from `data.patch_db.query_patches`. For a paper with no measured row
that lookup returns None and the code fell back to a flat 400, so the window
started at `int(400 / patch_scale**2 * 0.5)` = 221 patches. Every probe below
that was never taken. On a sheet whose real capacity is 90 the loop therefore
never saw `pages == 1`, `best` stayed at its 0 sentinel, and the function
returned the 400-derived guess it had just failed to validate:

    100x150 mm, i1Pro, the app's own default (-a0.95 -m10):  returned 443, is 90
    130x180 mm, same:                                        returned 443, is 169

with nothing on screen and one `log.warning` nobody reads. It was reachable
before any preset needed it, through the layout panel's "Custom (enter
dimensions)" page size, and the two photo-card built-ins (10 x 15 cm and
13 x 18 cm) made it one override click away.

These tests drive the real method with a stubbed `_probe`, so they describe the
search itself rather than any particular sheet, and run in milliseconds instead
of shelling out to targen and printtarg a dozen times.
"""
from __future__ import annotations

import pytest

from workflow.chart_creator import ChartCreator, ChartParams


class _FakeSheet:
    """A sheet that holds `capacity` patches, counted in probes."""

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.probes: list[int] = []

    def __call__(self, _targen, _printtarg, n, _device, _args, _tmp) -> int:
        self.probes.append(n)
        return 1 if n <= self.capacity else 2


@pytest.fixture
def creator(tmp_path, monkeypatch):
    """A ChartCreator whose probe is a sheet of known size and whose Argyll
    binaries appear to exist (the search returns an estimate without them)."""
    cc = ChartCreator.__new__(ChartCreator)
    cc._settings = type("S", (), {"get": staticmethod(
        lambda k, d=None: str(tmp_path) if k == "argyll_bin_path" else d)})()
    monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
    monkeypatch.setattr(ChartCreator, "_build_printtarg_args",
                        lambda self, p: ["-ii1", "calc"])
    monkeypatch.setattr(ChartCreator, "_cleanup_probe",
                        lambda self, tmp: None)
    return cc


def _params(paper: str = "100x150") -> ChartParams:
    return ChartParams(instrument="i1", paper=paper,
                       patch_scale=0.95, margin_mm=10)


# DOWN TO ONE PATCH. A first version of this file stopped at 20, which was
# exactly where the fix stopped, so the list agreed with the bug instead of
# testing past it. A 60 x 90 mm sheet (the 2.4 x 3.5" wallet print) holds 16
# patches for an i1Pro, measured, and answered 443 until the floor came down.
@pytest.mark.parametrize("capacity", [1, 5, 12, 16, 19, 20, 45, 90, 169,
                                      300, 504])
def test_the_search_finds_the_capacity_it_is_given(creator, monkeypatch,
                                                   capacity):
    """Including the two that used to be unreachable: 90 and 169."""
    sheet = _FakeSheet(capacity)
    monkeypatch.setattr(ChartCreator, "_probe",
                        lambda self, *a: sheet(*a))
    assert creator._binary_search(_params()) == capacity


def test_a_small_sheet_no_longer_answers_with_the_guess_it_started_from(
        creator, monkeypatch):
    """The exact shape of the old failure: a real capacity far below the
    fallback estimate. 443 is what it used to answer for both sheets."""
    sheet = _FakeSheet(90)
    monkeypatch.setattr(ChartCreator, "_probe", lambda self, *a: sheet(*a))
    got = creator._binary_search(_params())
    assert got == 90
    assert got != 443, "the un-validated estimate is back"
    assert min(sheet.probes) <= 90, (
        "no probe ever went low enough to see a single page: the window's "
        f"lower bound is above the real capacity again (probed {sheet.probes})"
    )


def test_the_wider_window_costs_about_one_extra_probe(creator, monkeypatch):
    """A binary search over 20..1107 is one step longer than over 221..1107,
    and each step is a targen + printtarg run, so this is the price of the fix
    and it is worth knowing if it ever grows."""
    sheet = _FakeSheet(90)
    monkeypatch.setattr(ChartCreator, "_probe", lambda self, *a: sheet(*a))
    creator._binary_search(_params())
    assert len(sheet.probes) <= 12, \
        f"the search took {len(sheet.probes)} probes: {sheet.probes}"


def test_a_large_capacity_lands_exactly_and_not_one_short(creator, monkeypatch):
    """The search must return the LAST value that fits, not the first it tried.

    This says nothing about A4 or about `data/patch_db.py` — the probe here is a
    fake sheet, so the number is whatever this test put in it. An earlier
    docstring claimed it guarded the measured A4 capacity; it could not, and
    saying so was worse than not testing it. What it does guard is the loop's
    off-by-one: `best = mid; lo = mid + 1` must keep the largest single-page
    probe, and a boundary capacity (one below the window's own top) is where
    that goes wrong.
    """
    sheet = _FakeSheet(528)
    monkeypatch.setattr(ChartCreator, "_probe", lambda self, *a: sheet(*a))
    assert creator._binary_search(_params("A4")) == 528
    assert 529 in sheet.probes or max(sheet.probes) > 528, (
        "the search never probed above the capacity, so it cannot have proved "
        "528 is the last value that fits"
    )

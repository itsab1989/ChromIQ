"""A ONE-PIECE i1iO CHART IS THE CHART 4.3.65 MADE.

The new chart layout must not move a patch of a chart that fits the table in
one piece. Every case of `_i1io_baseline.cases` is built here and the digests
of its geometry files are compared with the stored ones of release 4.3.65
(``tests/data/i1io_baseline_4365.json``); ``CREATED`` and the side file's
``table_facts`` block are the only differences allowed, and what a font
decides is left out (fonts differ between machines).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import _i1io_baseline as base

STORED = json.loads((Path(__file__).parent / "data"
                     / "i1io_baseline_4365.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _on():
    from workflow.i1io import support
    was = support.i1io_enabled()
    support.set_enabled_for_this_process(True)
    yield
    support.set_enabled_for_this_process(was)


def test_the_stored_cases_are_the_cases():
    assert set(STORED["cases"]) == set(base.cases())


@pytest.mark.parametrize("name", sorted(base.cases()))
def test_the_chart_is_the_one_4365_made(name, tmp_path):
    stored = STORED["cases"][name]
    base.build_case(name, base.cases()[name], tmp_path / "c")
    got = {f: base.digest(tmp_path / "c" / f, fonts=False)
           for f in base.GEOMETRY_FILES}
    assert got == stored


def _unmarked(kw):
    """The kwargs of a layout 4.3.65 saved: no marker."""
    assert kw.pop("i1io_limits") == 2
    return kw


@pytest.mark.parametrize("name", sorted(base.cases()))
def test_the_same_layout_saved_by_4365_is_the_same_chart(name, tmp_path):
    """Without the marker (`i1io_limits`) every one of these is the chart
    4.3.65 made, and nothing is said about it: all of their sizes are ones
    an i1iO chart had."""
    from workflow.i1io import chart
    said = []
    real = chart.old_size_message
    chart.old_size_message = lambda kw: said.append(real(kw)) or said[-1]
    try:
        base.build_case(name, base.cases()[name], tmp_path / "c", _unmarked)
    finally:
        chart.old_size_message = real
    stored = STORED["cases"][name]
    for f in ("chart.ti2", "chart.i1io.json", "chart.strips.json"):
        assert base.digest(tmp_path / "c" / f, fonts=False) == stored[f], f
    assert said and not any(said)


def test_a_tenth_of_a_millimetre_is_seen(tmp_path):
    """The comparison can fail: one margin 0.1 mm larger."""
    def wider(kw):
        kw["margins"] = (kw["margins"][0] + 0.1,) + tuple(kw["margins"][1:])
        return kw
    base.build_case("manual_A4", base.cases()["manual_A4"], tmp_path / "c",
                    wider)
    assert (base.digest(tmp_path / "c" / "chart.i1io.json", fonts=False)
            != STORED["cases"]["manual_A4"]["chart.i1io.json"])

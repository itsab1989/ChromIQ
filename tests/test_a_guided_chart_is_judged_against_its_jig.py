"""A Guided chart is judged against the instrument's minimums, not 6 mm.

Guided has no margin boxes and no "use instrument margins" toggle, so the recipe
it records carries the dataclass defaults — 6/6/6/6 with
`use_instrument_margins: false`. On disk that is indistinguishable from a Manual
user who deliberately declined the instrument guideline, and
`TabChart._chart_own_margins` read it exactly that way: the sheet was then judged
against 6 mm on every edge instead of the jig's real minimums.

Measured when it was found: **112 of 384 Guided combinations** sit below their
instrument's minimum and reported "Margins: OK" in green. An i1Pro / US Letter
rotated sheet with a 27.2 mm top margin against a 38 mm ruler requirement said
nothing at all.

It became reachable in 4.1.3-beta.19: before that, Guided built through printtarg
and recorded no recipe, so the sheet was judged against the instrument.

The fix records PROVENANCE rather than different numbers. Two repairs that look
obvious were measured and are worse: writing the real margins into the recipe is
still silent AND breaks the rebuild round-trip (20 → 62 combinations rebuild a
different sheet), and setting `use_instrument_margins` true changes the geometry
Guided deliberately produces (20 → 74).
"""
from __future__ import annotations

import inspect
import json

import pytest

from workflow.chart_creator import ChartCreator


def test_a_guided_chart_records_that_it_did_not_choose_its_margins():
    """The producer side: the flag must be written, and written as False."""
    src = inspect.getsource(ChartCreator._embed_layout_geometry)
    assert '"margins_chosen_by_user"' in src, (
        "a Guided chart no longer records who chose its margins, so the jig "
        "check cannot tell a default from a decision")
    assert 'layout["margins_chosen_by_user"] = False' in src


@pytest.mark.parametrize("provenance,expect_own_margins", [
    (False, False),   # Guided — judged against the instrument
    (True, True),     # a real user decision — judged against their numbers
    (None, True),     # written by an older ChromIQ — behaviour unchanged
])
def test_the_reader_honours_the_provenance(tmp_path, provenance,
                                           expect_own_margins, monkeypatch):
    """The consumer side, against a real channels.json on disk.

    The `None` case is the backward-compatibility one and is deliberate: charts
    built before this flag existed carry no key, and must keep the behaviour
    they were built with rather than silently change judgement.
    """
    from ui.tabs.tab_chart import TabChart

    layout = {"engine": "chromiq",
              "recipe": {"use_instrument_margins": False,
                         "margin_left": 6.0, "margin_right": 6.0,
                         "margin_top": 6.0, "margin_bottom": 6.0}}
    if provenance is not None:
        layout["margins_chosen_by_user"] = provenance
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text("CTI2\n", encoding="utf-8")
    ti2.with_suffix(".channels.json").write_text(
        json.dumps({"layout": layout}), encoding="utf-8")

    tab = TabChart.__new__(TabChart)
    tab._margin_ti2 = ti2
    got = TabChart._chart_own_margins(tab)

    if expect_own_margins:
        assert got is not None, (
            "a chart whose margins the user DID choose is no longer judged "
            "against their own numbers")
        assert got["T"] == 6.0
    else:
        assert got is None, (
            "a Guided chart is still being judged against its own default "
            "6 mm margins instead of the instrument's minimums — the jig "
            "check is silent on 112 of 384 Guided combinations")

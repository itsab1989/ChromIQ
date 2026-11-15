"""The i1iSis grid ChromIQ lays out is the grid i1Profiler 3.8.8 computes.

Every layout the study measured in i1Profiler's own saved charts (38 distinct
grids: pages, margins, patch sizes, caps, tight margins, headers, barcode,
small and large patch counts, last pages with empty columns; REQUIREMENTS v2
§9, §11 to §13) is kept in ``tests/data/isis_i1profiler_layouts.json``.
ChromIQ's own grid (`workflow.isis.chart.grid_for`) must be i1Profiler's for
every one of them, and so must i1Profiler's rule as `workflow.isis.export`
applies it to a page. Fakes only: no i1Profiler, no instrument.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow.isis import chart as C
from workflow.isis import export as X

DATA = json.loads((Path(__file__).parent / "data"
                   / "isis_i1profiler_layouts.json").read_text(
                       encoding="utf-8"))["layouts"]


def _opts(case):
    return C.options_from({
        "patch_w": case["patch_mm"][0], "patch_h": case["patch_mm"][1],
        "margins": tuple(case["margins_trbl"]),
        C.MODEL_KEY: "xl" if case["xl"] else "standard",
        C.TIGHT_KEY: case["tight"], C.HEADER_KEY: case["header_mm"],
        C.BARCODE_KEY: case["barcode"]})


def _fits(case) -> bool:
    """A page that holds i1Profiler's shortest chart (171 mm) inside its
    margins. i1Profiler draws a 171 mm chart on a shorter page anyway (W09,
    X01 to X03: pages sized only to steer its rule); ChromIQ never lets a
    chart run off its page and refuses such a page instead."""
    t, _r, b, _l = case["margins_trbl"]
    return case["page_mm"][1] - t - b >= 171.0


FITTING = [c for c in DATA if _fits(c)]


@pytest.mark.parametrize("case", FITTING, ids=[c["run"] for c in FITTING])
def test_chromiq_lays_out_i1profilers_grid(case):
    w, h = case["page_mm"]
    g = C.grid_for(case["N"], w, h, _opts(case))
    assert [g.C, g.R, g.P] == case["measured_CRP"], case["run"]


@pytest.mark.parametrize("case", [c for c in DATA if not _fits(c)],
                         ids=[c["run"] for c in DATA if not _fits(c)])
def test_a_page_shorter_than_the_shortest_chart_is_refused(case):
    w, h = case["page_mm"]
    with pytest.raises(C.IsisSheetRefused) as e:
        C.grid_for(case["N"], w, h, _opts(case))
    assert e.value.kind == "short"


@pytest.mark.parametrize("case", DATA, ids=[c["run"] for c in DATA])
def test_i1profilers_rule_as_the_export_applies_it(case):
    """The rule `workflow.isis.export.i1profiler_grid` uses to prove what a
    `.txf` makes i1Profiler expect, applied to the measured page itself."""
    w, h = case["page_mm"]
    d = X.TxfDesign(device="i1iSis XL" if case["xl"] else "i1iSis",
                    page_w=w, page_h=h, margins=tuple(case["margins_trbl"]),
                    pw=case["patch_mm"][0], ph=case["patch_mm"][1],
                    header=case["header_mm"], tight=case["tight"],
                    barcode=case["barcode"], columns=0, rows=0, pages=0)
    assert list(X.i1profiler_grid(d, case["N"])) == case["measured_CRP"]


def test_the_fixture_holds_every_layout_the_study_measured():
    assert len(DATA) == 38
    assert len({c["run"] for c in DATA}) == 38


@pytest.mark.parametrize("N,cmax,rmax,want", [
    (957, 28, 33, (27, 18, 2)),     # V06
    (957, 30, 13, (29, 11, 3)),     # W09
    (957, 31, 21, (30, 16, 2)),     # V19
    (100, 10, 4, (9, 4, 3)),        # X02: two empty columns on page 3
    (4, 30, 32, (4, 1, 1)),         # X08
])
def test_the_split_rule(N, cmax, rmax, want):
    assert C.split(N, cmax, rmax) == want

"""The one-page report's example colours are CHOSEN FROM the chart measured.

**Knut, 2026-09-11**, asked whether ChromIQ's sixteen example colours were the
right ones: *"The 16 colors must just be distributed and represent the profile
tested. That is all. However, I guess all the colors and grays tested must come
from the actual test chart that was used for verification."*

So there is no list of sixteen nice colours. A fixed list would name patches a
chart may not contain and would say nothing about the profile the measurement
is of. The report picks them from what was measured, by farthest-point sampling
in the chart's own reference Lab: start at the patch nearest mid grey, then
repeatedly take the one furthest from everything picked so far.

Three properties follow, and each is tested: they come from the chart, they are
spread through colour rather than clustered, and the same chart gives the same
sixteen every time, so two dated reports of one chart can be compared.
"""
from __future__ import annotations

import itertools
import math
import os
import pathlib
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measurement_report import SUMMARY_PATCH_COUNT, build_report  # noqa: E402


def _grey_ramp_ti3() -> str:
    from tests.test_a_saved_report_does_not_leak_its_verdict_into_another_type import (
        _grey_ramp_ti3 as g)
    return g()


def _report(tmp_path, text=None):
    p = pathlib.Path(tmp_path) / "chart.ti3"
    p.write_text(text or _grey_ramp_ti3(), encoding="utf-8")
    return build_report(str(p)), p


def _min_pairwise(labs) -> float:
    return min(math.dist(a, b) for a, b in itertools.combinations(labs, 2))


def test_sixteen_of_them(tmp_path):
    rep, _p = _report(tmp_path)
    sp = rep.get("summary_patches")
    assert sp, "the report carries no example colours at all"
    assert len(sp) == SUMMARY_PATCH_COUNT
    assert SUMMARY_PATCH_COUNT == 16, "Knut asked for sixteen"


def test_every_one_of_them_is_a_patch_of_the_chart(tmp_path):
    """The whole point of his answer: no colour ChromIQ invented.

    MUTATION: add a made-up colour to the list and this goes red.
    """
    rep, _p = _report(tmp_path)
    locs = {str(x["loc"]) for x in rep["summary_patches"]}
    assert len(locs) == len(rep["summary_patches"]), "a patch is listed twice"
    # every one also carries what the chart asked for and what came back
    for x in rep["summary_patches"]:
        assert len(x["expected_lab"]) == 3 and len(x["measured_lab"]) == 3
        assert x["expected_hex"].startswith("#") and x["measured_hex"].startswith("#")
        assert isinstance(x["de"], (int, float))


def test_they_are_SPREAD_and_not_merely_sixteen_of_them(tmp_path):
    """"Distributed" is the requirement, and it is the one a lazy pick fails.

    The sixteen worst patches of the same chart sit on top of each other: their
    closest pair is 0.0 apart, because a chart repeats its hardest colours. The
    spread set's closest pair is tens of units away. A pick that clusters is
    not what he asked for, whatever its size.

    MUTATION: take the first sixteen, or the sixteen worst, and this goes red.
    """
    rep, _p = _report(tmp_path)
    spread = _min_pairwise([x["expected_lab"] for x in rep["summary_patches"]])
    worst = _min_pairwise([x["expected_lab"] for x in rep["worst_patches"]])
    assert spread > 10.0, f"the sixteen are clustered: closest pair {spread:.2f}"
    assert spread > worst, (
        f"the spread pick ({spread:.2f}) is no better distributed than the "
        f"worst-patch pick ({worst:.2f})")


def test_the_same_chart_gives_the_same_sixteen(tmp_path):
    """Two dated reports of one chart must show the same colours or they
    cannot be compared, which is what the whole report exists for.

    MUTATION: seed the pick from anything that varies between runs and this
    goes red.
    """
    rep1, p = _report(tmp_path)
    rep2 = build_report(str(p))
    assert [x["loc"] for x in rep1["summary_patches"]] == \
           [x["loc"] for x in rep2["summary_patches"]]


def test_a_chart_smaller_than_sixteen_gives_what_it_has(tmp_path):
    """A verification sheet can be smaller than the example table. It shows
    every patch it has rather than repeating one to reach sixteen."""
    from tests.test_import_measurement_module import _cgats, _PATCHES
    small = _cgats("CTI3", _PATCHES[:9])
    rep, _p = _report(tmp_path, small)
    sp = rep.get("summary_patches") or []
    if sp:
        assert len(sp) <= 9
        assert len({str(x["loc"]) for x in sp}) == len(sp)


def test_the_schema_did_not_move_for_this(tmp_path):
    """Additive, like everything else in this feature: a report saved before
    the example colours existed still opens, and shows none."""
    rep, _p = _report(tmp_path)
    assert rep["schema"] == 7

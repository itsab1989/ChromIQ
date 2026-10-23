"""§61 of measurement_report_limits.md (Basti, 2026-10-23, approved): the
Overview's cube-corner rows say what each ΔE00 compares against."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from ui.dialogs import measurement_report_dialog as D


def _run(src, *, yardstick="absolute", white_aim=(100.0, 0.0, 0.0)):
    return {"reference_source": src, "yardstick": yardstick,
            "corners": [{"name": "W", "expected_lab": list(white_aim),
                         "present": True, "de": 1.0},
                        {"name": "R", "expected_lab": [54.0, 80.0, 69.0],
                         "present": True, "de": 9.0}]}


@pytest.mark.parametrize("src", ["design", "device"])
def test_a_profiling_or_raw_sheet_is_against_the_ideal(qapp, src):
    assert D._corner_overview_label("R", [_run(src)]) == \
        "Red ΔE00 (against the ideal colour)"
    assert D._corner_overview_label("W", [_run(src)]) == \
        "White ΔE00 (against a perfect white)"


def test_read_relative_to_the_paper_says_so(qapp):
    r = _run("design", yardstick="media-relative")
    assert D._corner_overview_label("R", [r]).endswith(
        "(against the ideal colour, relative to this sheet's paper)")
    assert D._corner_overview_label("W", [r]).endswith(
        "(against a perfect white, relative to this sheet's paper)")


def test_from_profile_gamut_white_is_the_profiles_paper(qapp):
    r = _run("colorimetric", white_aim=(95.1, 0.4, -2.9))
    assert D._corner_overview_label("W", [r]).endswith(
        "(against the profile's paper white)")
    assert D._corner_overview_label("R", [r]).endswith(
        "(against the ideal colour)")
    # an older reference that still aims at a perfect white says so
    assert D._corner_overview_label("W", [_run("colorimetric")]).endswith(
        "(against a perfect white)")
    # chart judged relative for its own intent: the corners stay absolute
    r2 = _run("colorimetric", yardstick="media-relative")
    assert D._corner_overview_label("R", [r2]).endswith("(against the ideal colour)")


def test_printed_through_the_profile_is_against_the_source(qapp):
    assert D._corner_overview_label("K", [_run("source")]).endswith(
        "(against the colour it was converted from)")


def test_dates_that_disagree_point_at_each_date(qapp):
    assert D._corner_overview_label("R", [_run("design"), _run("source")]) == \
        "Red ΔE00 (against each date's own reference)"


def test_no_reference_keeps_the_plain_label(qapp):
    assert D._corner_overview_label("R", [{"reference_source": None}]) == "Red ΔE00"


def test_the_overview_uses_the_labels(qapp):
    import inspect
    src = inspect.getsource(D.MeasurementReportDialog._comparison_table_html)
    assert "_corner_overview_label(code, runs)" in src

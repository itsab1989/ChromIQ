"""A printed report must say which profile it judges, and from where.

Knut, 2026-09-20, correcting a release note: *"It is not the chart that is
verified, it is the profile that was made in the profile run that is verified
using a chart, printing it, and measuring it, then qualifying the measurements
quality using a set of metrics and methods compared against the chart data."*

And then, on the first draft, which named only "run 1": *"A person reading the
report as a document will not be able to trace back where this report comes
from, so the project name and run needs to be shown, as well as the included
measurement dates (which usually is in the report)."*

He approved the wording verbatim the same night. What this guard holds is the
three things that make the sentence worth having, because any of them could
fall out of a later edit and leave a sentence that still reads well:

* it names the PROJECT, not just a run number;
* it names the RUN;
* it does NOT repeat the dates, because Report Scope prints them four lines
  below and two copies of a date range can disagree.

And it holds the one place the sentence must not appear: a profiling
measurement is not a judgement of anything, it is the sheet a profile was built
FROM, and a report that said otherwise would be the sort of false claim this
window keeps having to have removed.
"""
from __future__ import annotations

import types

import pytest

pytest.importorskip("PyQt6")

from ui.dialogs.measurement_report_dialog import MeasurementReportDialog as M  # noqa: E402


def _runs(*, verification: bool, path: str = "/p/Demo-Paper/runs/run3/x.ti3"):
    return [{"chart": "Demo-Paper", "is_verification": verification,
             "ti3": path, "created": "2026-11-16T10:00:00"}]


def _host():
    host = types.SimpleNamespace()
    host._report_kind = types.MethodType(M._report_kind, host)
    host._report_profile_name = types.MethodType(M._report_profile_name, host)
    host._run_number_for = M._run_number_for
    host._what_this_report_judges = types.MethodType(
        M._what_this_report_judges, host)
    return host


def test_it_names_the_project_and_the_run():
    said = _host()._what_this_report_judges(_runs(verification=True))
    assert "Demo-Paper" in said, "the project is not named, so it traces back to nothing"
    assert "run 3" in said, "the run is not named"
    assert "judges the profile" in said, (
        "it must say the PROFILE is judged, not the chart")


def test_it_points_at_the_dates_rather_than_repeating_them():
    """Report Scope already prints the range; a second copy can disagree."""
    said = _host()._what_this_report_judges(_runs(verification=True))
    assert "Report Scope" in said
    assert "2026-11-16" not in said, "it repeats a date that is printed below"


def test_a_profiling_report_says_nothing_of_the_kind():
    assert _host()._what_this_report_judges(_runs(verification=False)) == ""


def test_a_run_it_cannot_place_is_named_without_a_run_number():
    """Better silent than "run 1" by default: a wrong run number in a document
    handed to somebody else is worse than an absent one."""
    said = _host()._what_this_report_judges(
        _runs(verification=True, path="/p/loose/measurement.ti3"))
    assert "Demo-Paper" in said and "run" not in said.split(".")[0]


def test_the_run_number_survives_a_windows_path():
    """A RAW string doubled every backslash and the first version of this test
    failed on its own fixture, not on the code: `r"a\\b"` is two characters,
    so the path it built was `runs\\\\run12` and nothing could match it."""
    win = "C:" + chr(92) + "Users" + chr(92) + "k" + chr(92) + "runs" \
        + chr(92) + "run12" + chr(92) + "x.ti3"
    assert M._run_number_for([{"ti3": win}]) == "12"

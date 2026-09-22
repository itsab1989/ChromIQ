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


def _runs(*, verification: bool,
          origin: str = "/p/Demo-Paper/runs/run3/verifications/2026-11-16_100000"):
    """THE SHAPE A REPORT REALLY HAS (round 3B, F5). This fixture used to put
    a whole path in ``ti3``, which `build_report` never does (it writes the
    file NAME), so every test here passed while every real report said "built
    in <chart stem>" and named no run. The folder is in ``_origin_dir``, and
    ``chart`` is the verification chart's stem, not the project."""
    return [{"chart": "Demo-Paper-verify", "is_verification": verification,
             "ti3": "Demo-Paper-verify.ti3", "_origin_dir": origin,
             "created": "2026-11-16T10:00:00"}]


def _host():
    host = types.SimpleNamespace()
    host._report_kind = types.MethodType(M._report_kind, host)
    host._report_profile_name = types.MethodType(M._report_profile_name, host)
    host._run_number_for = M._run_number_for
    host._project_name_for = M._project_name_for
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


def test_a_measurement_in_no_project_names_nothing():
    """Better silent than wrong (round 3B, F5): a loose file said "the profile
    built in loose-measurement", a file that holds no profile.

    MUTATION: fall back to `_report_profile_name` and this names the file.
    """
    said = _host()._what_this_report_judges(
        _runs(verification=True, origin="/p/loose"))
    assert said == ""


def test_it_names_the_project_not_the_chart_stem():
    """MUTATION: read the project from `_report_profile_name` again and this
    says "Demo-Paper-verify"."""
    said = _host()._what_this_report_judges(_runs(verification=True))
    assert "built in Demo-Paper, run 3." in said, said


def test_the_run_number_survives_a_windows_path():
    """A RAW string doubled every backslash and the first version of this test
    failed on its own fixture, not on the code: `r"a\\b"` is two characters,
    so the path it built was `runs\\\\run12` and nothing could match it."""
    win = "C:" + chr(92) + "Users" + chr(92) + "k" + chr(92) + "runs" \
        + chr(92) + "run12" + chr(92) + "x.ti3"
    assert M._run_number_for([{"ti3": win}]) == "12"
    assert M._run_number_for([{"_origin_dir": win.rsplit(chr(92), 1)[0]}]) == "12"
    assert M._project_name_for(
        [{"_origin_dir": win.rsplit(chr(92), 1)[0]}]) == "k"

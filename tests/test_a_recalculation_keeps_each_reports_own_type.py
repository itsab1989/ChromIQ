"""Changing the limit set must not change WHICH DOCUMENT a saved report is.

Knut, 2026-09-11: *"A user should be allowed to print several report types for a
run, as the user may have several uses for different reports."* So one run can
hold a Colour summary, a Full colour check and a Printing record of the same
measurement, and the window lists what it has.

A recalculation rewrote all of them with the run's current type. Measured by the
round that rebuilt the demo pack: one change of limit set, the type pulldown
never touched, turned those three into three Colour summaries, and the line
naming what the run holds read "Colour summary (4)".

The stamping was added deliberately by an earlier adversarial round, so that a
recalculated report could not claim a type the run no longer held. That was
right while a run had exactly one type. Both intentions survive: a report
generated AS a document keeps being that document, and a report with no type of
its own still follows the run, which is what it renders as anyway.
"""
from __future__ import annotations

import pytest

import workflow.measurement_report as mr


@pytest.mark.parametrize("saved_as", [mr.REPORT_TYPE_SUMMARY,
                                      mr.REPORT_TYPE_RECORD,
                                      mr.REPORT_TYPE_GREY])
def test_a_report_keeps_the_document_it_was_generated_as(saved_as):
    """The run is on one type; the report was generated as another."""
    rep = {"schema": mr.REPORT_SCHEMA}
    mr.set_report_type(rep, saved_as)
    before = dict(rep)
    _recalculate_stamp(rep, run_type=mr.REPORT_TYPE_FULL)
    assert mr.report_type(rep) == saved_as
    assert rep["report_type"] == before["report_type"]


def test_a_report_with_no_type_of_its_own_follows_the_run():
    """Everything saved before the types existed. It renders as the run's type
    anyway, so recording that loses nothing."""
    rep = {"schema": mr.REPORT_SCHEMA}
    assert "report_type" not in rep
    _recalculate_stamp(rep, run_type=mr.REPORT_TYPE_GREY)
    assert rep.get("report_type") == mr.REPORT_TYPE_GREY


def test_an_empty_string_counts_as_no_type():
    rep = {"schema": mr.REPORT_SCHEMA, "report_type": ""}
    _recalculate_stamp(rep, run_type=mr.REPORT_TYPE_RECORD)
    assert rep["report_type"] == mr.REPORT_TYPE_RECORD


def test_the_window_really_guards_it_this_way():
    """THE SOURCE, because the behaviour above is one `if` in a loop that needs
    a project, three dated verifications and a set change to reach. A test that
    only exercised the helper would pass with the guard deleted."""
    import inspect

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    src = inspect.getsource(MeasurementReportDialog)
    i = src.index("stamp_report_type(rep, ctx.run)", src.index("_recalculate_run"))
    window = src[max(0, i - 400):i]
    assert 'get("report_type")' in window, \
        "the recalculation stamps the type without asking whether the report has one"


def _recalculate_stamp(rep: dict, *, run_type: str) -> None:
    """What the recalculation loop does to one report, with the run's type."""
    if not (rep or {}).get("report_type"):
        mr.set_report_type(rep, run_type)

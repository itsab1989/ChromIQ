"""The guide is ONE list, and every name in it is a real metric's own name.

**Knut, 2026-09-20 (B8-592).** *"The report text section 'How to read this
report' lists all the metrics that a report uses, but it is not ONE list, but
split into TWO. Why? … Should this not be re-written to be ONE bullet list? Do
that.... Make sure all the correct names for each metric is used in the
description."*

What he was reading was four hand-written bullets, the line "Every metric this
report judges, and what it means:", and then one bullet per judged row. The
first four were not a second view of the other list:

* "Colour accuracy" and "Grey balance" are row GROUPS. Five rows stand behind
  the first and two behind the second, and all seven were already in the
  second list under their real names, so the same numbers were explained twice
  under two vocabularies.
* "Paper white & darkest black" and "Cube corners" are report SECTION
  headings, and neither is a row in `compliance_sets.ROWS` at all. They were
  written with no row group, so they survived every filter: a "Grey and tone
  check", which judges three grey and ramp rows and prints neither section,
  explained both of them.

This file used to pin that shape, including a test named
`test_the_bullets_about_data_every_type_carries_always_survive` which asserted
the last point as a FEATURE. It is retargeted rather than deleted, because the
thing worth guarding is unchanged and older than the fault: **a report must not
explain rows it deliberately left out.** "Grey and tone check" drops the five
colour-accuracy rows from the document, and the guide must drop them too.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import workflow.measurement_report as mr

#: A group name, not a metric. Must never appear as a bullet lead-in again.
_GROUP_NAMES = ("Colour accuracy: the", "Grey balance: how far")
#: Section headings that are not rows. Same.
_SECTION_NAMES = ("brightest and deepest",
                  "composite black and the six primary")


def _text(dlg) -> str:
    return " ".join(re.sub("<[^>]+>", " ", dlg._view.toHtml()).split())


def _guide(dlg) -> str:
    """The guide section's own HTML, so a phrase found in the results table
    cannot be counted as an explanation."""
    return dlg._how_to_read_html(
        dlg._rows_the_results_show(dlg._runs_for_report()))


def _metric_bullets(html: str) -> "list[str]":
    """The bullets of the METRICS list, which is the first <ul> in the guide.

    Scoped deliberately. The guide carries a second, unrelated list after it:
    one bullet per verdict word (PASS, FAIL, COND, INFO, N-A), which Knut did
    not object to and which is not a list of metrics. The first cut of this
    file asked "is every bullet named after a row?" of the whole section and
    failed on "PASS", which is a fact about the test and not about the guide.
    """
    first = re.search(r"<ul>(.*?)</ul>", html, re.S)
    if first is None:
        return []
    return [" ".join(re.sub("<[^>]+>", " ", b).split())
            for b in re.findall(r"<li>(.*?)</li>", first.group(1), re.S)]


@pytest.mark.parametrize("tid", [mr.REPORT_TYPE_FULL, mr.REPORT_TYPE_GREY,
                                 mr.REPORT_TYPE_RECORD])
def test_the_divider_between_the_two_lists_is_gone(a_run, qapp, tid):
    dlg, run = a_run
    _set(dlg, run, tid)
    assert "Every metric this report judges" not in _text(dlg), (
        "the line that divided the two lists is still there, so there are "
        "still two")


@pytest.mark.parametrize("tid", [mr.REPORT_TYPE_FULL, mr.REPORT_TYPE_GREY,
                                 mr.REPORT_TYPE_RECORD])
def test_no_bullet_names_a_group_or_a_section(a_run, qapp, tid):
    dlg, run = a_run
    _set(dlg, run, tid)
    t = _text(dlg)
    for bad in _GROUP_NAMES + _SECTION_NAMES:
        assert bad not in t, (
            f"the guide still explains {bad!r}, which is not a metric")


@pytest.mark.parametrize("tid", [mr.REPORT_TYPE_FULL, mr.REPORT_TYPE_GREY,
                                 mr.REPORT_TYPE_RECORD])
def test_every_bullet_is_named_after_a_real_row(a_run, qapp, tid):
    """*"Make sure all the correct names for each metric is used."* Each
    bullet's lead-in, up to its colon, must be the `label` of a row in the
    canonical table, and a row this document actually judges."""
    from workflow.compliance_sets import ROW_BY_ID
    dlg, run = a_run
    _set(dlg, run, tid)
    shown = dlg._rows_the_results_show(dlg._runs_for_report())
    labels = {ROW_BY_ID[r].label for r in shown if r in ROW_BY_ID}
    bullets = _metric_bullets(_guide(dlg))
    assert bullets, "no bullets at all"
    for b in bullets:
        lead = b.split(":")[0].strip()
        assert lead in labels, (
            f"{lead!r} is not the label of a row this report judges; "
            f"judged rows are {sorted(labels)}")


def test_grey_and_tone_stops_explaining_the_colour_rows(a_run, qapp):
    """The rule that predates the fault and outlives it."""
    from workflow.compliance_sets import ROW_BY_ID
    dlg, run = a_run
    _set(dlg, run, mr.REPORT_TYPE_GREY)
    leads = {b.split(":")[0].strip() for b in _metric_bullets(_guide(dlg))}
    colour_rows = {ROW_BY_ID[r].label for r in ROW_BY_ID
                   if ROW_BY_ID[r].group == "all_patches"}
    assert not (leads & colour_rows), (
        "a grey and tone check explains colour-accuracy rows it does not show")
    assert leads, "the rows it DOES show are still explained"


def test_the_gate_is_the_row_filter_and_nothing_else(a_run, qapp):
    """`_explained_row_groups` is None for a type that shows every row, and the
    surviving rows' own groups otherwise. Read from the row table, so a row that
    moves group cannot leave a bullet stranded."""
    dlg, run = a_run
    _set(dlg, run, mr.REPORT_TYPE_FULL)
    assert dlg._explained_row_groups() is None
    _set(dlg, run, mr.REPORT_TYPE_GREY)
    assert dlg._explained_row_groups() == {"grey_ramp", "selected"}


@pytest.fixture
def a_run(tmp_path, qapp):
    import sys
    from PyQt6.QtCore import QSettings

    from core.file_manager import Project
    from core.settings import AppSettings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from drive_one_page_report import _measurement_ti3

    work = tmp_path / "w"
    work.mkdir()
    st = AppSettings()
    st._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    st.set("custom_output_path", str(work))
    proj = Project.create(work / "G", "G")
    run = proj.current_run()
    run.ensure_dir()
    ti3 = run.dir / "G.ti3"
    _measurement_ti3(ti3)
    dlg = MeasurementReportDialog(st, None, initial_ti3=ti3)
    yield dlg, run
    dlg.close()


def _set(dlg, run, tid: str) -> None:
    from workflow.run_compliance import set_run_report_type
    set_run_report_type(run, tid)
    dlg._forget_limits()
    dlg._sync_limit_controls()
    dlg._refresh()


@pytest.fixture(autouse=True)
def _every_type_as_for_a_measurement_in_no_run(monkeypatch):
    """**K13 (Knut, beta 34) made the Printing record a profiling-only type**,
    and these checks drive every type on a VERIFICATION fixture, where T4
    would now fall back to T2 and each check would be asked of the fallback.
    What they test is how each type RENDERS, which is still reachable: a saved
    beta-34 Printing record of a verification is shown as recorded, and a
    measurement outside any project keeps every type. So the window is told
    it has no kind. K13's own rule is guarded in
    `tests/test_the_report_type_pulldown_stores_on_the_run.py`.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    monkeypatch.setattr(MeasurementReportDialog, "_window_kind",
                        lambda self: None)

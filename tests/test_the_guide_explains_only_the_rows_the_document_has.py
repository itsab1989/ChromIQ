"""A report must not explain rows it deliberately left out.

"Grey and tone check" is the neutral axis and the mid-tone ramps, on their own:
the five colour-accuracy rows are dropped from the document rather than shown as
not applicable, because a report whose subject is the neutral axis does not gain
by listing the colour rows it left out.

The guide above those rows went on saying "Colour accuracy: the ΔE00 across the
patches, split so you can see the bulk of the chart (all patches and the best
95 %) apart from the few hardest patches (the worst 5 %). Each row is judged
against the run's limit set." A reader looks for those rows and there are none.

This is the third time the same shape has been found in this window: a sentence
that was true of the full report, left standing over a document that is not the
full report. The note that told a user to add patches to a chart that already
had them was the first, one line lower was the second.

Bullets about data every type carries — paper white and the darkest black, the
cube corners — are not row-gated and must survive.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest

import workflow.measurement_report as mr

_COLOUR = "Colour accuracy: the"
_GREY = "Grey balance: how far"
_WHITE = "brightest and deepest"
_CORNERS = "composite black and the six primary"


def _text(dlg) -> str:
    return " ".join(re.sub("<[^>]+>", " ", dlg._view.toHtml()).split())


def test_grey_and_tone_stops_explaining_the_colour_rows(a_run, qapp):
    dlg, run = a_run
    _set(dlg, run, mr.REPORT_TYPE_GREY)
    t = _text(dlg)
    assert _COLOUR not in t
    assert _GREY in t, "the rows it DOES show are still explained"


def test_the_full_report_explains_everything(a_run, qapp):
    dlg, run = a_run
    _set(dlg, run, mr.REPORT_TYPE_FULL)
    t = _text(dlg)
    assert _COLOUR in t and _GREY in t


def test_the_printing_record_explains_everything_because_it_shows_everything(
        a_run, qapp):
    """T4 judges nothing, but it drops no row: every figure is there, reading
    INFO. Gating the guide on the VERDICT rather than on the rows would empty
    this one out."""
    dlg, run = a_run
    _set(dlg, run, mr.REPORT_TYPE_RECORD)
    t = _text(dlg)
    assert _COLOUR in t and _GREY in t


@pytest.mark.parametrize("tid", [mr.REPORT_TYPE_FULL, mr.REPORT_TYPE_GREY,
                                 mr.REPORT_TYPE_RECORD])
def test_the_bullets_about_data_every_type_carries_always_survive(a_run, qapp, tid):
    dlg, run = a_run
    _set(dlg, run, tid)
    t = _text(dlg)
    assert _WHITE in t and _CORNERS in t


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

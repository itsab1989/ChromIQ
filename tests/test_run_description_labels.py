"""#130 — the two Create Chart text fields say which chart they belong to.

Knut set the rules out in full in his beta.144 report, after finding that the
notes field kept saying "Run N Chart Notes:" whichever chart it was editing:

> *"When changing from Run type=Profiling to Verification, then the 'Run N Chart
> Notes:' label is not changed to 'Verification Chart Notes:'"*
>
> *"when i look at 'Location being edited' that updates to /run N+1/ in the
> path, to signify the expected new run number. This could be done also for the
> labels"*
>
> *"When 'Run type'='Calibration' I also said to Change 'Run N Chart Notes' to
> 'Calibration Chart Notes', which matches the 'Calibration Description' field."*
>
> *"each time the 'Profile run' and 'Run type' changes, the correct text field
> shall be shown, which is specific for the run's chart, the verification run's
> chart and the calibration's chart."*

These assert the label the WIDGET shows, not the string the source contains:
the fault he reported was a refresh that produced the right text for the wrong
selection, which a source-level test cannot see.
"""
from __future__ import annotations

import pytest

from core.argyll_runner import ArgyllRunner
from core.file_manager import FileManager
from core.measurement_target import (
    RUN_TYPE_CALIBRATION, RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION,
)
from ui.tabs.tab_chart import TabChart

from tests.conftest_calibration import CalSettings


@pytest.fixture
def chart_tab(cal_home, qapp):
    """Create Chart on a project with three runs, calibration options on."""
    settings = CalSettings(cal_home, calibration_mode=True)
    fm = FileManager(settings)
    fm.set_target_name("Label-Rules")
    project = fm.project()
    while project._next_run_index() <= 3:
        project.new_run()
    tab = TabChart(ArgyllRunner(settings), fm, settings)
    # The bar is what owns the selection; the tab only listens to it, exactly
    # as MainWindow wires the two together.
    from ui.measurement_target_bar import MeasurementTargetController

    ctl = MeasurementTargetController(fm)
    ctl.set_calibration_allowed(True)
    tab.set_target_controller(ctl)
    return tab, project


def _labels(tab):
    """What the two rows say on screen right now."""
    return (tab._manual_run_desc_lbl.text(), tab._manual_chart_notes_lbl.text())


def _select(tab, *, run: str, run_type: str) -> None:
    """Move the bar the way the user does — through the controller, so the
    tab's own `changed` handler is what re-labels the rows."""
    ctl = tab._target_ctl
    ctl.set_profile_run(run)
    ctl.set_run_type(run_type)


# ---- the table, row by row ----------------------------------------------
@pytest.mark.parametrize("run,run_type,expected", [
    ("run1", RUN_TYPE_PROFILING,
     ("Run 1 Description:", "Run 1 Chart Notes:")),
    ("run3", RUN_TYPE_PROFILING,
     ("Run 3 Description:", "Run 3 Chart Notes:")),
    # "New run" names the run it is about to create — run 4 here — because the
    # folder line right above already says /run4/.
    ("", RUN_TYPE_PROFILING,
     ("Run 4 Description:", "Run 4 Chart Notes:")),
    # A verification chart belongs to exactly one run, so its notes need no
    # number; the description still describes the run being verified.
    ("run2", RUN_TYPE_VERIFICATION,
     ("Run 2 Description:", "Verification Chart Notes:")),
    ("", RUN_TYPE_VERIFICATION,
     ("Run 4 Description:", "Verification Chart Notes:")),
])
def test_the_labels_name_the_chart_being_edited(chart_tab, run, run_type, expected):
    tab, _project = chart_tab
    _select(tab, run=run, run_type=run_type)
    assert _labels(tab) == expected


def test_calibration_says_calibration_on_both_rows(chart_tab):
    """Knut: the notes label must *match* the description label."""
    tab, _project = chart_tab
    _select(tab, run="run1", run_type=RUN_TYPE_CALIBRATION)
    assert _labels(tab) == ("Calibration Description:",
                            "Calibration Chart Notes:")


def test_the_notes_label_follows_a_run_type_change_with_no_tab_switch(chart_tab):
    """The reported fault, reproduced as its own case.

    Profiling → Verification → Profiling, all on the same run: the label must
    change each time, on the signal alone.
    """
    tab, _project = chart_tab
    _select(tab, run="run2", run_type=RUN_TYPE_PROFILING)
    assert _labels(tab)[1] == "Run 2 Chart Notes:"

    tab._target_ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert _labels(tab)[1] == "Verification Chart Notes:", (
        "switching to Verification left the run's own notes label in place — "
        "the field is editing the verification chart's notes"
    )

    tab._target_ctl.set_run_type(RUN_TYPE_PROFILING)
    assert _labels(tab)[1] == "Run 2 Chart Notes:"


def test_the_number_follows_the_profile_run(chart_tab):
    """A change of Profile run alone re-labels both rows."""
    tab, _project = chart_tab
    _select(tab, run="run1", run_type=RUN_TYPE_PROFILING)
    assert _labels(tab) == ("Run 1 Description:", "Run 1 Chart Notes:")

    tab._target_ctl.set_profile_run("run3")
    assert _labels(tab) == ("Run 3 Description:", "Run 3 Chart Notes:")


def test_new_run_agrees_with_the_folder_line(chart_tab):
    """N+1 must be the SAME N+1 the "Location being edited" line shows.

    Two independent derivations of "the next run" is how the label and the path
    come to disagree; this holds them to one source.
    """
    tab, project = chart_tab
    _select(tab, run="", run_type=RUN_TYPE_PROFILING)
    where = tab._target_ctl.location_being_edited()
    number = tab._manual_run_desc_lbl.text().split()[1]
    assert f"/run{number}/" in where, (
        f"the label says run {number} but the folder line says {where}"
    )
    assert number == str(project._next_run_index())


def test_the_guided_row_is_labelled_too(chart_tab):
    """Guided shows the description row as well, and must not lag behind."""
    tab, _project = chart_tab
    _select(tab, run="run3", run_type=RUN_TYPE_PROFILING)
    assert tab._guided_run_desc_lbl.text() == "Run 3 Description:"


def test_the_label_column_is_wide_enough_for_every_label(chart_tab):
    """A fixed-width column measured for one label clips the others.

    The description labels are pinned to one width so Guided and Manual line
    up; that width has to cover every label the row can ever show.
    """
    from PyQt6.QtWidgets import QLabel

    tab, _project = chart_tab
    width = tab._guided_run_desc_lbl.width() or tab._guided_run_desc_lbl.minimumWidth()
    for text in tab._target_text_label_candidates():
        assert QLabel(text).sizeHint().width() <= width, (
            f"{text!r} does not fit the {width} px label column"
        )

"""#130 — Knut's beta.147 report, one test per fault.

Six separate things went wrong, and five of them share a shape: something the
user typed or chose was thrown away, or a guard fired on a state it does not
apply to. Each test names the fault in his own words, because each of these
looks correct in the source and is only wrong in sequence.
"""
from __future__ import annotations

import json

import pytest

from core.argyll_runner import ArgyllRunner
from core.file_manager import FileManager
from core.measurement_target import (
    RUN_TYPE_CALIBRATION, RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION,
)
from ui.measurement_target_bar import MeasurementTargetController
from ui.tabs.tab_chart import TabChart

from tests.conftest_calibration import CalSettings


@pytest.fixture
def chart_tab(cal_home, qapp):
    settings = CalSettings(cal_home, calibration_mode=True)
    fm = FileManager(settings)
    fm.set_target_name("Beta147")
    project = fm.project()
    while project._next_run_index() <= 3:
        project.new_run()
    tab = TabChart(ArgyllRunner(settings), fm, settings)
    ctl = MeasurementTargetController(fm)
    ctl.set_calibration_allowed(True)
    tab.set_target_controller(ctl)
    return tab, ctl, project


def _type(tab, description, notes):
    """Type into both boxes the way the widgets deliver it."""
    tab._manual_run_desc_edit.setText(description)       # textChanged → saved
    tab._manual_chart_notes_edit.setText(notes)
    tab._manual_chart_notes_edit.editingFinished.emit()  # focus-out


# ---- "the Run Description and Run Chart Note was cleared in run 12" ------
def test_text_typed_for_a_new_run_lands_on_the_run_generate_creates(chart_tab):
    tab, ctl, project = chart_tab
    ctl.set_profile_run("")                     # "New run"
    ctl.set_run_type(RUN_TYPE_PROFILING)
    _type(tab, "Baryta gloss, new inks", "printed 6 Aug")

    tab._align_current_run_to_target()          # what Generate Chart does

    assert ctl.target.profile_run == "run4", "Generate should select the new run"
    meta = project.run("run4").load_meta()
    assert meta.description == "Baryta gloss, new inks"
    assert meta.chart_notes == "printed 6 Aug"
    # …and it must still be on screen, which is the half he saw.
    assert tab._manual_run_desc_edit.text() == "Baryta gloss, new inks"
    assert tab._manual_chart_notes_edit.text() == "printed 6 Aug"


def test_typing_for_a_new_run_never_writes_into_an_existing_one(chart_tab):
    """The other half of the same fault, and the worse one.

    `resolve_run` falls back to the project's CURRENT run when the selection
    names none, so every keystroke went into whichever run that was — silently
    overwriting a description the user had written for it.
    """
    tab, ctl, project = chart_tab
    ctl.set_profile_run("run2")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    _type(tab, "run 2's own text", "run 2's own notes")

    ctl.set_profile_run("")                     # "New run"
    _type(tab, "text for the run to come", "notes for the run to come")

    for rid in ("run1", "run2", "run3"):
        meta = project.run(rid).load_meta()
        assert meta.description != "text for the run to come", (
            f"{rid} was given text that was typed for a run that did not exist"
        )
    assert project.run("run2").load_meta().description == "run 2's own text"


def test_switching_to_new_run_keeps_what_is_on_screen(chart_tab):
    """§5 T5.1 — a New run carries the previous run's settings over, and the
    two text boxes are settings like any other."""
    tab, ctl, _project = chart_tab
    ctl.set_profile_run("run1")
    _type(tab, "carried over", "notes too")
    ctl.set_profile_run("")
    assert tab._manual_run_desc_edit.text() == "carried over"
    assert tab._manual_chart_notes_edit.text() == "notes too"


# ---- "the text in the two fields dissappeared" (calibration) -------------
def test_a_calibration_rebuild_keeps_its_description_and_notes(cal_home):
    """Knut: *"adding text in Calibration Description and Calibration Chart
    Notes, then Generate Chart. The chart was made, but the text … dissappeared."*

    Generating a calibration chart archives the previous calibration, and
    ``meta.json`` — the user's own words — was being MOVED out with it.
    """
    settings = CalSettings(cal_home, calibration_mode=True)
    fm = FileManager(settings)
    fm.set_target_name("Cal-Keeps-Text")
    cal = fm.project().calibration
    cal.ensure_dir()
    cal.cal_path.write_text("a calibration")
    meta = cal.load_meta()
    meta.description = "Canson Baryta, new ink set"
    meta.chart_notes = "calibration sheet, 6 Aug"
    cal.save_meta(meta)

    archive = cal.archive_to_old()

    assert archive is not None
    after = cal.load_meta()
    assert after.description == "Canson Baryta, new ink set"
    assert after.chart_notes == "calibration sheet, 6 Aug"
    # The archive documents itself with a COPY, so going back to it still says
    # what that calibration was.
    kept = json.loads((archive / "meta.json").read_text())
    assert kept["description"] == "Canson Baryta, new ink set"
    # …and the calibration itself did move.
    assert not cal.cal_path.exists()
    assert (archive / cal.cal_path.name).exists()


# ---- "This chart is loaded from elsewhere" after Duplicate ---------------
def test_a_run_in_this_project_is_not_a_chart_from_elsewhere(chart_tab, tmp_path):
    """Knut: *"I get a window 'This chart is loaded from elsewhere' … This is
    obviously wrong … I am not allowed to finish the Generate Chart."*

    Duplicate shows the copy through `reflect_loaded_chart`, which locked the
    tab into the read-only state that `_on_generate` refuses to work in.
    """
    tab, _ctl, project = chart_tab
    own = project.run("run2").chart_ti2
    outside = tmp_path / "somebody-elses.ti2"

    assert tab._chart_is_in_this_project(own) is True
    assert tab._chart_is_in_this_project(outside) is False


def test_reflecting_this_project_s_own_chart_leaves_generate_available(chart_tab):
    tab, _ctl, project = chart_tab
    run = project.run("run2")
    run.dir.mkdir(parents=True, exist_ok=True)
    run.chart_ti2.write_text("")
    tab._reflected_active = True                # as Duplicate used to leave it

    tab.reflect_loaded_chart(run.chart_ti2, [])

    assert tab._reflected_active is False, (
        "the run's own chart still puts the tab in the loaded-from-elsewhere "
        "state, where Generate Chart refuses to run"
    )


# ---- "Location being edited" under Run type = Calibration ---------------
def test_the_location_line_names_the_cal_folder(chart_tab):
    """Knut: *"With Run type = Calibration, the 'Location being edited' must
    show the path to the calibration folder project_name/cal/"*."""
    _tab, ctl, _project = chart_tab
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    where = ctl.location_being_edited()
    assert where.endswith("/Beta147/cal/"), where
    assert "/runs/" not in where


def test_the_location_line_still_names_runs_for_the_other_types(chart_tab):
    _tab, ctl, _project = chart_tab
    ctl.set_run_type(RUN_TYPE_PROFILING)
    ctl.set_profile_run("run3")
    assert ctl.location_being_edited().endswith("/runs/run3/")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert ctl.location_being_edited().endswith("/runs/run3/verifications/")


# ---- Give Up in strip mode ----------------------------------------------
class _RecordingRunner:
    """Just enough ArgyllRunner for the manager to write keys into."""

    is_running = True

    def __init__(self) -> None:
        self.writes: list[str] = []

    def write_stdin(self, text: str) -> None:
        self.writes.append(text)

    def abort(self) -> None:
        pass


def _manager_at_the_strip_menu(qapp):
    """A real manager, engine active, mid-session."""
    from workflow.measure_manager import MeasureManager

    runner = _RecordingRunner()
    manager = MeasureManager(runner)
    manager._engine_active = True
    manager._guided_state = "disabled"
    manager._handle_engine_line(
        '{"event": "session_start", "strips": [{"strip": "A", "read": false}]}',
        lambda _l: None)
    return manager, runner


def test_give_up_at_the_strip_menu_finishes_the_stop(qapp):
    """Knut: *"Now window goes away, but since I did not make any measurements,
    the measurement session should have stopped. It did not."*

    In strip mode a wrong-dial failure drops the reader back at the strip menu,
    so the quit interrupts the read instead of ending the session — and the
    give-up prompt that follows had nobody watching it.
    """
    manager, runner = _manager_at_the_strip_menu(qapp)
    manager.mark_stop_requested()
    runner.writes.clear()

    manager._handle_engine_line('{"event": "strip_interrupted"}', lambda _l: None)

    assert runner.writes == ['{"cmd": "quit"}\n'], (
        f"the reader came back at the give-up prompt and nothing answered it "
        f"(wrote {runner.writes!r})"
    )
    assert manager._stop_requested is False, "the second key must be spent once"


def test_an_interruption_the_user_did_not_ask_for_still_raises_its_window(qapp):
    """The guard must not swallow a genuine interruption."""
    manager, runner = _manager_at_the_strip_menu(qapp)
    seen: list[bool] = []
    manager.strip_interrupted.connect(lambda: seen.append(True))
    runner.writes.clear()

    manager._handle_engine_line('{"event": "strip_interrupted"}', lambda _l: None)

    assert runner.writes == []
    assert seen == [True]


def test_a_new_session_forgets_a_stop_chosen_in_the_last_one(qapp):
    """A leaked flag would quit the next session at its first interruption."""
    manager, runner = _manager_at_the_strip_menu(qapp)
    manager.mark_stop_requested()

    manager._handle_engine_line(
        '{"event": "session_start", "strips": [{"strip": "A", "read": false}]}',
        lambda _l: None)

    assert manager._stop_requested is False

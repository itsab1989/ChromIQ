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


# =========================================================================
# beta.148 report
# =========================================================================
def test_save_and_stop_from_a_failure_window_finishes_the_session(qapp):
    """Knut, beta.148: *"the window closes, but the measurement session does
    NOT end, and the instrument is unresponsive."*

    "Save and stop" marks the ending as answered so the reader's own report of
    it cannot raise a second window — and that guard was eating the very prompt
    the save chain was waiting for.
    """
    manager, runner = _manager_at_the_strip_menu(qapp)
    manager._engine_active = True
    manager._read_something = True
    manager.send_save_partial_and_quit()          # the first 'q'
    manager.mark_ending_answered()                # what "Save and stop" does
    runner.writes.clear()

    manager._handle_engine_line('{"event": "strip_interrupted"}', lambda _l: None)

    assert runner.writes == ['{"cmd": "quit"}\n'], (
        "the second key never went out, so chartread never wrote the .ti3"
    )
    assert manager._save_partial_state is None, "the chain must be spent once"


def test_a_run_type_calibration_location_is_the_cal_folder(chart_tab):
    """Already covered above for the label; this pins the FOLDER LINE, which is
    what Knut confirmed the rule for."""
    _tab, ctl, _project = chart_tab
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    assert ctl.location_being_edited().endswith("/cal/")


def test_generate_does_not_claim_a_calibration_chart_that_is_not_there(cal_home):
    """Knut, beta.148: with an empty ``cal/`` he was told *"You already made a
    calibration chart for this project"*.

    ``meta.json`` exists as soon as a Calibration Description is typed, and it
    was counting as a calibration file.
    """
    settings = CalSettings(cal_home, calibration_mode=True)
    fm = FileManager(settings)
    fm.set_target_name("Empty-Cal")
    cal = fm.project().calibration
    cal.ensure_dir()
    meta = cal.load_meta()
    meta.description = "typed before any chart existed"
    cal.save_meta(meta)

    assert cal.live_files() == [], (
        "the calibration's own description is being counted as a calibration"
    )
    cal.ti2.write_text("a real chart")
    assert [p.name for p in cal.live_files()] == [cal.ti2.name]


def test_duplicate_carries_the_description_across_marked_as_a_copy(chart_tab):
    """Knut, beta.148: *"The new run 4 created gets the 'Run 4 Description'
    cleared."* §5 T5.2 says copied, prefixed, and the prefix goes at the START
    where it can be seen without scrolling."""
    _tab, _ctl, project = chart_tab
    source = project.run("run2")
    meta = source.load_meta()
    meta.description = "PhotoRag Baryta, gloss"
    meta.chart_notes = "printed 6 Aug"
    source.save_meta(meta)

    copy = project.duplicate_run(source)

    assert copy.load_meta().description == "(copy) PhotoRag Baryta, gloss"
    assert copy.load_meta().chart_notes == "printed 6 Aug", (
        "the notes describe the chart, which was copied verbatim"
    )


def test_duplicating_an_undescribed_run_invents_nothing(chart_tab):
    _tab, _ctl, project = chart_tab
    copy = project.duplicate_run(project.run("run3"))
    assert copy.load_meta().description == "", '"(copy) " alone describes nothing'


def test_an_ending_the_user_chose_never_changes_tab():
    """Knut, beta.148: after Stop → Save and stop the app moved itself to the
    Calibration & Profiling tab. *"This is where user shall decide to change
    tab"* — and that place is the all-done window's accept button."""
    import inspect

    from ui.tabs.tab_measure import TabMeasure

    src = inspect.getsource(TabMeasure._end_session)
    assert "_auto_proceed = False" in src, (
        "an ending chosen through the Stop window can still carry the all-done "
        "window's earlier answer into a tab change"
    )


# ---- Restore Used Chart puts the notes back, for all three targets -------
def _chart_with_notes(tab, notes: str):
    """Write a real chart sidecar for whatever the bar points at, and give back
    its .ti2 — the argument the restore path takes."""
    from workflow.chart_slot import slot_for

    slot = slot_for(tab._target_ctl.restore_target()
                    or tab._target_ctl.project_or_none().calibration)
    slot.live_dir.mkdir(parents=True, exist_ok=True)
    ti2 = slot.live_dir / f"{slot.stem}.ti2"
    ti2.write_text("")
    (slot.live_dir / f"{slot.stem}.channels.json").write_text(
        json.dumps({"chart_notes": notes}))
    return ti2


@pytest.mark.parametrize("run_type", [RUN_TYPE_PROFILING,
                                      RUN_TYPE_VERIFICATION,
                                      RUN_TYPE_CALIBRATION])
def test_restore_puts_the_chart_notes_back_for_every_target(chart_tab, run_type):
    """Knut, beta.148, having watched it work on a run: *"Make sure this
    operation also works for verification run (run type=verification) and for a
    Calibration (run type=Calibration)."*"""
    tab, ctl, _project = chart_tab
    ctl.set_profile_run("run2")
    ctl.set_run_type(run_type)
    ti2 = _chart_with_notes(tab, "printed 5 Aug, tray 2")

    tab._manual_chart_notes_edit.setText("what I have typed today")
    tab._restore_chart_settings(ti2)

    assert tab._manual_chart_notes_edit.text() == "printed 5 Aug, tray 2"
    store = tab._target_text_store()
    assert store is not None
    assert getattr(store.load_meta(), tab._notes_attr()) == "printed 5 Aug, tray 2", (
        "the restored notes were shown but not written, so the next refresh "
        "reads the stale ones back"
    )


@pytest.mark.parametrize("run_type", [RUN_TYPE_PROFILING, RUN_TYPE_CALIBRATION])
def test_a_chart_with_no_notes_leaves_the_field_alone(chart_tab, run_type):
    """§4 T4.2 — restoring a chart that carries no notes must not blank text
    the user has for the chart they are about to make."""
    tab, ctl, _project = chart_tab
    ctl.set_profile_run("run2")
    ctl.set_run_type(run_type)
    ti2 = _chart_with_notes(tab, "")

    tab._manual_chart_notes_edit.setText("mine, not the chart's")
    tab._restore_chart_settings(ti2)

    assert tab._manual_chart_notes_edit.text() == "mine, not the chart's"


# =========================================================================
# beta.149 log: the readings were rejected because nothing calibrated
# =========================================================================
def test_guided_never_sends_a_flag_it_does_not_offer(qapp, tmp_path):
    """Knut, beta.148: every patch of a calibration chart came back *"Reading
    is inconsistent"*.

    His log has the cause, and it is neither of the two things I guessed. Every
    measurement from 09:46 carried **-N**, and ``cal_required`` — the
    instrument's white calibration — never appeared again after 08:41. A
    ColorMunki that is not calibrated drifts, and ArgyllCMS's own consistency
    check throws the readings out.

    "Skip initial calibration (-N)" is built in Guided and then hidden outright,
    but its value was still read, still sent and still remembered between
    sessions — so a stored setting ran every guided measurement uncalibrated
    with nothing on screen to say so.
    """
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure

    class _S(AppSettings):
        def get(self, key, default=None):
            if key == "custom_output_path":
                return str(tmp_path)
            if key == "measure_no_cal":
                return True             # …as it would be from an earlier session
            return super().get(key, default)

    tab = TabMeasure(ArgyllRunner(_S()), _S())
    assert tab._nocal_cb.isVisible() is False, (
        "the guided control is meant to be hidden — if it is offered now, this "
        "test is about the wrong thing"
    )
    tab._nocal_cb.setChecked(True)
    tab._ti1_path = tmp_path / "chart.ti1"

    params = tab._collect_guided()

    assert params.disable_initial_cal is False, (
        "guided is sending -N from a checkbox the user cannot see or untick"
    )


def test_the_manual_flag_still_works_because_it_is_visible(qapp, tmp_path):
    """The option is real and stays available where it is offered."""
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure

    class _S(AppSettings):
        def get(self, key, default=None):
            if key == "custom_output_path":
                return str(tmp_path)
            return super().get(key, default)

    tab = TabMeasure(ArgyllRunner(_S()), _S())
    tab._ti1_path = tmp_path / "chart.ti1"
    tab._m_nocal_cb.setChecked(True)
    assert tab._collect_manual().disable_initial_cal is True


def test_skipping_calibration_is_announced_in_the_log():
    """It changes every reading that follows and it persists between sessions,
    so it must never again be invisible."""
    import inspect

    from ui.tabs.tab_measure import TabMeasure

    src = inspect.getsource(TabMeasure)
    assert "if params.disable_initial_cal:" in src
    assert "Skip initial calibration (-N) is switched on" in src


# =========================================================================
# beta.150 report
# =========================================================================
def test_a_chart_missing_patches_is_not_called_complete(tmp_path):
    """Knut, beta.150: *"Started with a ti3 file that had one or a few patches
    missing in last strip … Finishing all strips, but the concluding 'All
    Strips Read' window with a Measurement Finished sound does NOT come."*

    The strip flags are per STRIP and the gap is per PATCH: a strip whose last
    patch is unread still comes back `read: true`. So the chart looked complete
    at session start, completion was "not news" for the whole session, and
    finishing every strip announced nothing.
    """
    from workflow.measure_manager import MeasureManager

    ti2 = tmp_path / "chart.ti2"
    ti2.write_text("NUMBER_OF_SETS 90\nBEGIN_DATA\nEND_DATA\n")
    ti3 = tmp_path / "chart.ti3"
    rows = "\n".join(f"{i} 10 10 10 5 5 5" for i in range(88))
    ti3.write_text(f"NUMBER_OF_SETS 88\nBEGIN_DATA\n{rows}\nEND_DATA\n")

    all_strips_read = [{"strip": s, "read": True} for s in "ABCDEF"]
    assert MeasureManager._measurement_was_complete(str(ti2), all_strips_read) is False, (
        "88 readings of 90 is not a complete chart, whatever the strip flags say"
    )


def test_a_chart_with_every_reading_is_still_called_complete(tmp_path):
    """The rule the suppression exists for must survive: re-reading a strip of
    a finished measurement completes nothing."""
    from workflow.measure_manager import MeasureManager

    ti2 = tmp_path / "chart.ti2"
    ti2.write_text("NUMBER_OF_SETS 3\nBEGIN_DATA\nEND_DATA\n")
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text("NUMBER_OF_SETS 3\nBEGIN_DATA\n"
                   "1 10 10 10 5 5 5\n2 20 20 20 6 6 6\n3 30 30 30 7 7 7\n"
                   "END_DATA\n")
    strips = [{"strip": "A", "read": True}]
    assert MeasureManager._measurement_was_complete(str(ti2), strips) is True


def test_with_no_chart_to_check_the_strip_flags_still_answer(tmp_path):
    from workflow.measure_manager import MeasureManager

    assert MeasureManager._measurement_was_complete(
        None, [{"strip": "A", "read": True}]) is True
    assert MeasureManager._measurement_was_complete(
        None, [{"strip": "A", "read": False}]) is False


def test_the_tab_name_on_a_button_shows_its_ampersand(qapp, tmp_path):
    """Knut, beta.150: the button read *"GO TO CALIBRATION _PROFILING TAB"*.

    Qt takes "&" in button text as the mnemonic marker — it eats the ampersand
    and underlines the next letter. Doubling it prints one.
    """
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure

    class _S(AppSettings):
        def get(self, key, default=None):
            if key == "custom_output_path":
                return str(tmp_path)
            if key == "calibration_mode":
                return True
            return super().get(key, default)

    tab = TabMeasure(ArgyllRunner(_S()), _S())
    assert tab._profile_tab_name() == "Calibration & Profiling"
    assert tab._profile_tab_name_btn() == "Calibration && Profiling"


def test_every_branch_of_the_completion_window_fills_its_placeholder():
    """A {tab} left unformatted prints the braces at the user.

    The strips branch carried the placeholder with no `.format()` while the
    calibration branch, whose text has no placeholder, had one.
    """
    import inspect
    import re as _re

    from ui.tabs.tab_measure import TabMeasure

    src = inspect.getsource(TabMeasure._show_all_stripes_done)
    for block in _re.findall(r'msg = QLabel\((.*?)\n\s*dlg,\n\s*\)', src, _re.S):
        if "{tab}" in block:
            assert ".format(tab=" in block, (
                "a completion message carries {tab} and never fills it"
            )
        else:
            assert ".format(tab=" not in block, (
                "a completion message formats a placeholder it does not have"
            )


def test_a_run_and_its_verification_keep_separate_chart_notes(chart_tab):
    """Knut, beta.150: *"If I try to modify the text in the verification run,
    and then go back to profiling run, the text changes there too. These fields
    must be separate."*

    A run has two charts — its own and its one verification chart — and they
    are different sheets of paper. The DESCRIPTION stays shared, because a
    verification belongs to the run it verifies.
    """
    tab, ctl, project = chart_tab
    ctl.set_profile_run("run2")

    ctl.set_run_type(RUN_TYPE_PROFILING)
    _type(tab, "run 2's description", "notes for the RUN's chart")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert tab._manual_chart_notes_edit.text() != "notes for the RUN's chart", (
        "the verification is showing the run chart's notes"
    )
    _type(tab, "run 2's description", "notes for the VERIFICATION chart")

    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert tab._manual_chart_notes_edit.text() == "notes for the RUN's chart"
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert tab._manual_chart_notes_edit.text() == "notes for the VERIFICATION chart"

    meta = project.run("run2").load_meta()
    assert meta.chart_notes == "notes for the RUN's chart"
    assert meta.verify_chart_notes == "notes for the VERIFICATION chart"
    assert meta.description == "run 2's description", "the description is shared"


def test_text_typed_for_a_new_run_survives_a_detour(chart_tab):
    """Knut, beta.150, step 15: *"when I go back to Profile run = New run the
    values I wrote down was NOT remembered."*"""
    tab, ctl, _project = chart_tab
    ctl.set_profile_run("")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    _type(tab, "for the run to come", "notes for the run to come")

    ctl.set_profile_run("run1")
    assert tab._manual_run_desc_edit.text() != "for the run to come"

    ctl.set_profile_run("")
    assert tab._manual_run_desc_edit.text() == "for the run to come"
    assert tab._manual_chart_notes_edit.text() == "notes for the run to come"


def test_restore_acts_on_the_calibration_when_that_is_what_is_selected(chart_tab):
    """`restore_state` already knew about calibration; `restore_target` did
    not, so the button could be offered for the calibration chart and then put
    the selected RUN's chart back — replacing the wrong sheet."""
    from core.file_manager import Calibration

    _tab, ctl, project = chart_tab
    cal = project.calibration
    cal.ensure_dir()
    ctl.set_profile_run("run2")
    ctl.set_run_type(RUN_TYPE_CALIBRATION)

    target = ctl.restore_target()
    assert isinstance(target, Calibration), (
        f"Restore would act on {type(target).__name__}, not the calibration"
    )
    slot = ctl.restore_slot_or_none()
    assert slot is not None and slot.live_dir == cal.dir


# ---- the No Instrument Found window, reworked to his instruction ---------
def test_the_no_instrument_window_carries_his_text():
    """Knut wrote the wording himself (beta.150) and asked for it to replace
    the original bullet list. It is used unedited."""
    from workflow.measurement_messages import CATALOGUE, M_NO_INSTRUMENT

    title, body = M_NO_INSTRUMENT.render(n=5)
    assert title == "No Instrument Found"
    assert "it has not replied for 5 seconds" in body
    assert "Unplug the instrument's USB cable and plug it back in." in body
    assert "M-NO-INSTRUMENT" in CATALOGUE


def test_the_ten_second_window_i_added_is_gone():
    """*"Then, remove the window 'Your instrument is not answering' that you
    added after 10 seconds."*"""
    import workflow.measurement_messages as M

    assert not hasattr(M, "M_INSTRUMENT_SILENT")
    assert "M-INSTRUMENT-SILENT" not in M.CATALOGUE


def test_the_window_no_longer_waits_for_the_process_to_exit():
    """*"move the time the 'No Instrument Found' window comes to arrive 5
    seconds after no instrument is detected, instead of the almost 20 seconds
    … Make sure this window uses the same detection logic as today, only
    change when the time that the message will arrive."*

    The detection is untouched — `_on_no_instrument`, from the same printed
    line — and it now arms a five-second timer instead of leaving the window
    for `_on_measure_done` to raise whenever chartread happens to exit.
    """
    import inspect

    from ui.tabs.tab_measure import TabMeasure

    assert TabMeasure._NO_INSTRUMENT_DELAY_S == 5
    detect = inspect.getsource(TabMeasure._on_no_instrument)
    assert "_arm_no_instrument_window" in detect


def test_its_ok_button_uses_the_one_ending_every_route_shares():
    """*"All messages that can arrive during measurement must exit in that safe
    manner, as a single exit strategy for all cases."*"""
    import inspect

    from ui.tabs.tab_measure import TabMeasure

    src = inspect.getsource(TabMeasure._show_no_instrument_window)
    assert "_confirm_end_of_session" in src and "_end_session" in src, (
        "OK must go through the same ending as Stop, so nothing read is lost "
        "and nothing is discarded without being offered"
    )


# ---- a loaded preset must be overridable, engine layout included ---------
def _chart_tab_plain(cal_home, qapp):
    settings = CalSettings(cal_home)
    fm = FileManager(settings)
    fm.set_target_name("Preset-Lock")
    return TabChart(ArgyllRunner(settings), fm, settings)


def test_the_engine_layout_panel_locks_with_the_rest_of_the_layout(cal_home, qapp):
    """Knut, beta.150, after loading the "by pharmacist" preset and changing
    Calculation method: *"it was not possible to press Generate Chart. It was
    locked … I should be able to override the loaded preset chart."*

    A prebuilt preset greys the layout controls until "Edit page layout
    (override preset)" is ticked — but the ChromIQ engine's panel was outside
    that list, so it stayed fully editable while having no effect at all.
    """
    tab = _chart_tab_plain(cal_home, qapp)
    assert tab._manual_layout_panel in tab._manual_printtarg_content, (
        "the engine's layout panel is not part of the layout lock, so a preset "
        "leaves it editable and ignores what it says"
    )


def test_an_engine_recipe_change_counts_as_a_layout_change(cal_home, qapp):
    """…and once unlocked, changing it must actually reach the chart.

    `printtarg_changed` decides whether Generate re-lays out the bundled .ti1
    or copies the preset's files back verbatim, and it is computed from the
    layout signature. The engine's recipe was not in that signature, so the
    answer was always "nothing changed".
    """
    tab = _chart_tab_plain(cal_home, qapp)
    if tab._manual_engine_check is None or tab._manual_layout_panel is None:
        pytest.skip("no engine panel in this build")
    tab._manual_engine_check.setChecked(True)
    keys = [x[0] for x in tab._printtarg_signature() if isinstance(x, tuple)]
    assert "engine" in keys, (
        "the engine's recipe is not in the layout signature, so a preset "
        "cannot tell that the layout was changed"
    )
    # …and a real change to it must move the signature.
    before = tab._printtarg_signature()
    recipe = tab._manual_layout_panel.get_recipe()
    recipe.patch_w_mm = float(getattr(recipe, "patch_w_mm", 8.0)) + 1.0
    tab._manual_layout_panel.set_recipe(recipe)
    assert tab._printtarg_signature() != before, (
        "changing the engine's layout leaves the signature identical, so "
        "Generate copies the preset's files back verbatim"
    )


# =========================================================================
# beta.155 rulings
# =========================================================================
def test_create_calibration_file_is_offered_only_for_a_calibration(cal_home, qapp):
    """Knut, beta.155: the module was reachable from every run type, so a
    profiling run could be showing printcal's "Description (-D)" where the user
    expects colprof's "Profile Description (-D)" — which is what step 5 of the
    demo walked into."""
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_profile import TabProfile

    settings = CalSettings(cal_home, calibration_mode=True)
    fm = FileManager(settings)
    fm.set_target_name("Cal-Module")
    fm.project()
    ctl = MeasurementTargetController(fm)
    ctl.set_calibration_allowed(True)
    tab = TabProfile(ArgyllRunner(settings), settings, None)
    tab.set_calibration_mode(True)
    tab.set_target_controller(ctl)
    ctl.set_profile_run("run1")

    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert tab._cal_create_btn.isVisibleTo(tab) is False
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert tab._cal_create_btn.isVisibleTo(tab) is False
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    assert tab._cal_create_btn.isVisibleTo(tab) is True


def test_abort_goes_through_the_one_ending():
    """Knut, beta.155: *"The 'Abort?' confirm should be replaced with calling
    the 'Keep what you have measured so far?' chain."*

    "y" is chartread's own answer and it discards the readings with no offer to
    keep them. chartread is told **no** instead, and our ending runs — which
    also answers his warning about the two modes, because this sends no
    mode-specific key of its own: `_end_session` delegates to the chain that
    already knows which mode and which reader it is in.
    """
    import inspect

    from ui.tabs.tab_measure import TabMeasure

    src = inspect.getsource(TabMeasure._on_abort_confirm)
    assert "_confirm_end_of_session" in src and "_end_session" in src
    assert 'self._send_failure_choice("n")' in src, (
        "chartread must be told no, or it aborts underneath our ending"
    )
    # …and only for the engine: stock chartread's chain is different and works.
    assert "engine_active" in src


def test_save_partial_and_quit_is_left_exactly_as_it_is():
    """His other ruling, and the reason for it: *"As long as 'Save Partial &
    Quit' calls the save chain directly, that is ok, since we know it works
    today. We do not want to touch anything what works right now, unless it is
    dangerous."*"""
    import inspect

    from ui.tabs.tab_measure import TabMeasure

    src = inspect.getsource(TabMeasure._on_strip_error)
    assert "send_save_partial_and_quit()" in src
    assert "_confirm_end_of_session" not in src, (
        "Save Partial & Quit was routed through the ending; he asked for it to "
        "be left alone"
    )

"""Build step 9: the Measure tab's table window (``ui/i1io_table_window.py``) against the
simulated table and the simulated helper (no USB, no instrument), pytest-qt.

Every button's call into the job, both report modes, every ending, an interrupted earlier
session, a Stop during a row, a failed row read again, the problem report with its note, the
one-time consent, no default button anywhere, and the USB library missing."""
from __future__ import annotations

import json

import pytest

from core.file_manager import Project
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_reading import small_sheet
from tests.i1io_table.window_person import WindowPerson
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W
from workflow.i1io.table import session_end as se
from workflow.measurement_state import Ti3State, classify

ASKING = pytest.mark.parametrize("asking", [True, False], ids=["asking", "quiet"])
ARGS = ["-v", "-c", "1", "-S", "-p", "chart"]


@pytest.fixture
def settings(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    s.set(W.CONSENT_KEY, 0)
    s.set(W.ASK_KEY, True)
    yield s
    s.set(W.CONSENT_KEY, 0)
    s.set(W.ASK_KEY, True)


def project(tmp_path, sheet, name="Table-Target"):
    proj = Project.create(tmp_path / name, name)
    run = proj.current_run()
    run.ensure_dir()
    run.chart_ti2.write_text(RS.chart_ti2_text(sheet), encoding="ascii")
    return proj, run


def open_window(qtbot, monkeypatch, tmp_path, settings, *, asking=True, sheet=None,
                consent=True, sim=None, args=None, stamp=RS.STAMP, run=None,
                replace_agreed=False, archive=None):
    sheet = sheet or small_sheet()
    if run is None:
        _proj, run = project(tmp_path, sheet)
    sim = sim or WindowSim()
    monkeypatch.setattr(W, "JOB_FACTORY", sim.factory)
    monkeypatch.setattr(W, "USB_STATUS", lambda: (True, ""))
    settings.set(W.ASK_KEY, asking)
    if consent:
        settings.set(W.CONSENT_KEY, W.CONSENT_VERSION)
    win = W.TableMeasureWindow(None, settings, sheet, run, args or ARGS, stamp=stamp,
                               replace_agreed=replace_agreed, archive=archive)
    qtbot.addWidget(win)
    saved, finished = [], []
    win.saved.connect(lambda p, d: saved.append((p, d)))
    win.finished_with.connect(finished.append)
    win.show()
    win.start()
    person = WindowPerson(win, sim, lambda c: qtbot.waitUntil(c, timeout=15000))
    return win, sim, run, person, saved, finished


def moves(sim):
    from tests.i1io_table.test_job_safety import moves as m
    return len(m(sim.sim.received))


# ---- the whole measurement, both modes ---------------------------------------------------

@ASKING
def test_a_whole_measurement_is_read_saved_and_the_arm_goes_home(qtbot, monkeypatch, tmp_path,
                                                                settings, asking):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=asking)
    assert p.drive_until("end_of_session") == "end_of_session"
    assert ("report_after_step" in p.seen) is asking
    assert p.labels() == ["Save and stop", "Discard and stop", "Keep measuring"]
    p.press("Save and stop")
    assert saved and saved[0][0] == run.measurement_ti3
    assert classify(run.measurement_ti3, run.chart_ti2).state is Ti3State.COMPLETE
    assert p.page() == "home_offered"
    n = moves(sim)
    p.press("Bring the arm home")
    assert p.page() == "go" and moves(sim) == n          # the homing asks GO first
    p.press("Go")
    assert p.page() == "done" and sim.jobs[0].at_rest()
    offer = bool(win._tick_widgets)
    assert offer is asking                                # the "do not ask again" offer
    if offer:
        win._tick_widgets[0].setChecked(True)
    p.press("Close")
    assert finished == ["ended"]
    assert W.ask_after_each_step(settings) is False     # ticked, or quiet already


def test_the_consent_is_asked_once_and_not_now_starts_nothing(qtbot, monkeypatch, tmp_path,
                                                             settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    consent=False)
    assert p.page() == "consent"
    go = [b for b in win._buttons if b.text() == "I understand, drive my table"][0]
    assert not go.isEnabled()                             # only after the tick
    p.press("Not now")
    assert finished == ["consent_declined"] and sim.jobs == []
    assert not W.consent_given(settings)


def test_the_consent_given_is_remembered(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    consent=False)
    p.answer_page("consent")
    assert W.consent_given(settings) and p.page() == "prepare"


def test_no_page_has_a_default_button(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    consent=False)
    from PyQt6.QtWidgets import QPushButton
    for _ in range(60):
        page = p.page()
        for b in win.findChildren(QPushButton):
            assert not b.isDefault() and not b.autoDefault(), (page, b.text())
        if page == "end_of_session":
            break
        p.answer_page(page)


def test_the_usb_library_missing_is_said_and_nothing_starts(qtbot, monkeypatch, tmp_path,
                                                           settings):
    monkeypatch.setattr(W, "USB_STATUS", lambda: (False, "M-I1IO-DRIVE-USB-MISSING"))
    sim = WindowSim()
    monkeypatch.setattr(W, "JOB_FACTORY", sim.factory)
    _proj, run = project(tmp_path, small_sheet())
    win = W.TableMeasureWindow(None, settings, small_sheet(), run, ARGS)
    qtbot.addWidget(win)
    win.start()
    assert win.pages_shown == ["usb_missing"] and sim.jobs == []
    from workflow import measurement_messages as M
    assert win._title.text() == M.M_I1IO_DRIVE_USB_MISSING.render(log="")[0]


def test_the_ask_tick_on_the_first_page_is_the_setting(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=True)
    assert p.page() == "prepare" and win._tick_widgets[0].isChecked()
    win._tick_widgets[0].setChecked(False)
    assert W.ask_after_each_step(settings) is False and sim.jobs[0].ask_after_each_step is False


# ---- the problem report, the note, Stop ------------------------------------------------------

@ASKING
def test_report_a_problem_stops_movement_but_the_homing_and_the_note_goes_to_the_log(
        qtbot, monkeypatch, tmp_path, settings, asking):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=asking)
    p.drive_until("check_mark")
    p.press("Yes, it is centred")
    p.drive_until(("report_after_step", "end_of_session") if asking else "end_of_session")
    assert win._problem_btn.isVisible() and win._stop_btn.isVisible()
    win._problem_btn.click()
    assert p.page() == "problem"
    p.press("Something looks or sounds wrong")
    assert win._note_box.isVisible() and sim.jobs[0].only_home
    win._note_edit.setPlainText("The arm\nscraped the paper")
    win._note_save.click()
    n = moves(sim)
    assert "Bring the arm home" in p.labels() and "Carry on" not in p.labels()
    p.press("Bring the arm home")
    assert p.page() == "go" and moves(sim) == n
    p.press("Go")
    job = sim.jobs[0]
    assert job.at_rest()
    log = run.i1io_table_log(RS.STAMP).read_text(encoding="utf-8")
    assert "The arm scraped the paper" in log


def test_stop_during_a_row_stops_before_the_next_move_and_carry_on_asks_go(
        qtbot, monkeypatch, tmp_path, settings):
    sim = WindowSim()
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False, sim=sim)
    p.drive_until("check_mark")
    sim.transport.delay_s = 0.02
    [b for b in win._buttons if b.text() == "Yes, it is centred"][0].click()
    qtbot.waitUntil(lambda: win._busy, timeout=5000)
    qtbot.wait(150)
    assert win._stop_btn.isVisible() and win._stop_btn.isEnabled()
    win._stop_btn.click()                                # while the row runs
    p.idle()
    sim.transport.delay_s = 0.0
    page = p.page()
    n = moves(sim)
    if page not in ("stopped_by_you", "refused"):
        # a question was shown (a first visit, say): the stop is honoured at its answer
        p.answer_page(page)
        page = p.page()
        assert moves(sim) == n
    assert page in ("stopped_by_you", "refused"), page
    qtbot.wait(100)
    assert moves(sim) == n                               # nothing more moved by itself
    p.press("Carry on")
    assert p.page() == "go" and moves(sim) == n          # hands-off GO before the next move
    assert p.drive_until("end_of_session") == "end_of_session"


def test_stop_now_ends_the_table_part_and_the_readings_can_still_be_saved(
        qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False, sheet=small_sheet([4, 4, 4]))
    p.drive_until("check_mark")
    p.press("Yes, it is centred")
    p.drive_until("end_of_session")
    p.press("Keep measuring")                             # nothing missing: ends again
    win._problem_btn.click()
    p.press("Stop now")
    job = sim.jobs[0]
    assert job.stopped_by_person and job.state().sending_closed
    assert p.page() in ("stopped", "end_of_session", "refused")


# ---- a failed row and "again" -------------------------------------------------------------

def test_a_failed_row_is_offered_again_with_go_first(qtbot, monkeypatch, tmp_path, settings):
    sim = WindowSim(faults={"read_loc": {"1-2": "dies"}})
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False, sim=sim)
    assert p.drive_until("row_failed") == "row_failed"
    assert p.labels() == ["Read it again", "Skip it", "Stop"]
    assert win._note_box.isVisible()
    sim.helper.faults = {}
    n = moves(sim)
    p.press("Read it again")
    assert p.page() == "go" and moves(sim) == n
    assert p.drive_until("end_of_session") == "end_of_session"
    p.press("Save and stop")
    assert classify(run.measurement_ti3, run.chart_ti2).state is Ti3State.COMPLETE


def test_a_skipped_row_is_saved_partial_and_resume_is_offered(qtbot, monkeypatch, tmp_path,
                                                             settings):
    sim = WindowSim(faults={"read_loc": {"1-2": "dies"}})
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=False, sim=sim,
    )
    p.script["row_failed"] = "Skip it"
    p.drive_until("end_of_session")
    p.press("Save and stop")
    assert saved[0][1]["resume_next"] is True
    assert classify(run.measurement_ti3, run.chart_ti2).state is Ti3State.PARTIAL


# ---- the endings ----------------------------------------------------------------------------

def test_discard_keeps_nothing_in_the_run_and_the_homing_is_offered(qtbot, monkeypatch,
                                                                   tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("end_of_session")
    p.press("Discard and stop")
    assert not run.measurement_ti3.exists() and saved == []
    assert p.page() == "home_offered"
    p.press("Leave it there")
    assert p.page() == "done"
    assert se.session_state(run.i1io_table_session_dir(RS.STAMP)) == se.DISCARDED


def test_end_measurement_before_any_reading_saves_nothing(qtbot, monkeypatch, tmp_path,
                                                         settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("go")
    win._end_btn.click()                                  # the GO is withdrawn with Back
    p.idle()
    assert p.page() in ("home_offered", "done"), p.page()
    assert not run.measurement_ti3.exists() and saved == []


def test_keep_measuring_reads_the_missing_row_after_go(qtbot, monkeypatch, tmp_path, settings):
    sim = WindowSim(faults={"read_loc": {"1-2": "dies"}})
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False, sim=sim)
    p.script["row_failed"] = "Skip it"
    p.drive_until("end_of_session")
    sim.helper.faults = {}
    n = moves(sim)
    p.press("Keep measuring")
    assert p.page() == "go" and moves(sim) == n
    p.drive_until("end_of_session")
    p.press("Save and stop")
    assert classify(run.measurement_ti3, run.chart_ti2).state is Ti3State.COMPLETE


def test_esc_on_the_ending_withdraws_it_and_nothing_moves(qtbot, monkeypatch, tmp_path,
                                                         settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("end_of_session")
    n = moves(sim)
    win.reject()                                          # Esc
    p.idle()
    assert p.page() == "ending_closed" and moves(sim) == n
    assert not run.measurement_ti3.exists()


def test_the_window_cannot_be_closed_while_the_table_is_open(qtbot, monkeypatch, tmp_path,
                                                             settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("go")
    win.close()                                           # the window's X: asks the ending
    p.idle()
    assert win.isVisible() and finished == []


# ---- an interrupted earlier session at START ---------------------------------------------

def _interrupted(qtbot, monkeypatch, tmp_path, settings):
    """A first session that read row 1 and was never ended (the window closed by force)."""
    sheet = small_sheet([4, 4, 4])
    _proj, run = project(tmp_path, sheet)
    win, sim, _r, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                   asking=False, sheet=sheet, run=run)
    p.drive_until("check_mark")
    sim.helper.faults = {"read_loc": {"1-0": "dies"}}
    p.press("Yes, it is centred")
    p.drive_until("row_failed")
    win._finished = True                                  # a crash: no ending at all
    sim.jobs[0].close()
    win.close()
    return sheet, run


@pytest.mark.parametrize("how", ["Complete it", "Discard it"])
def test_an_interrupted_session_is_offered_at_start(qtbot, monkeypatch, tmp_path, settings,
                                                   how):
    sheet, run = _interrupted(qtbot, monkeypatch, tmp_path, settings)
    win, sim, _r, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                   asking=False, sheet=sheet, run=run,
                                                   stamp="20261117-160000")
    assert p.page() == "earlier"
    p.press(how)
    assert p.page() == "prepare"
    job = sim.jobs[0]
    if how == "Complete it":
        assert job.only_locs is not None and all(not l.startswith("0-") for l in job.only_locs)
    else:
        assert job.only_locs is None
        assert se.session_state(run.i1io_table_session_dir(RS.STAMP)) == se.DISCARDED
    p.drive_until("end_of_session")
    p.press("Save and stop")
    assert classify(run.measurement_ti3, run.chart_ti2).state is Ti3State.COMPLETE


def test_a_field_option_after_adopting_is_said_and_the_rest_is_measured(qtbot, monkeypatch,
                                                                       tmp_path, settings):
    sheet, run = _interrupted(qtbot, monkeypatch, tmp_path, settings)
    win, sim, _r, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=False, sheet=sheet, run=run,
        stamp="20261117-160000", args=ARGS[:-1] + ["-n", "chart"])
    p.press("Complete it")
    assert p.page() == "options_fields"
    p.press("Measure the rest that way")
    p.drive_until("end_of_session")
    p.press("Save and stop")
    assert classify(run.measurement_ti3, run.chart_ti2).state is Ti3State.COMPLETE


def test_a_refused_option_starts_nothing(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, args=["-v", "-c", "1", "-F", "n", "chart"])
    assert p.page() == "option_refused" and sim.sim is not None and sim.sim.received == []
    p.press("Close")
    assert finished == ["not_started"]


def test_options_with_no_meaning_are_named_on_the_first_page(qtbot, monkeypatch, tmp_path,
                                                            settings):
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, args=["-v", "-c", "1", "-T", "0.7", "chart"])
    assert p.page() == "prepare"
    assert "(-T)" in win._text.text() and "patch by patch" in win._text.text()


# ---- what the window never does --------------------------------------------------------

def test_the_window_module_imports_no_table_code_at_module_level():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(W))
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [getattr(node, "module", "") or ""] + [a.name for a in node.names]
            assert not any("workflow.i1io.table" in n for n in names), names


def test_no_slot_is_a_lambda_on_a_childs_signal():
    import inspect
    import re
    src = inspect.getsource(W)
    assert not re.search(r"\.connect\(\s*lambda", src)


def test_stop_on_the_report_question_keeps_the_question_and_then_asks_go(
        qtbot, monkeypatch, tmp_path, settings):
    """Found on screen (run 3): Stop pressed while the asking mode's report question was shown
    must not hide the question; it is answered, then the stop acts before the next move."""
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=True)
    p.drive_until("check_mark")
    p.press("Yes, it is centred")
    assert p.drive_until("report_after_step") == "report_after_step"
    n = moves(sim)
    win._stop_btn.click()
    assert p.page() == "report_after_step"
    p.press("As described")
    assert p.page() == "stopped_by_you" and moves(sim) == n
    p.press("Carry on")
    assert p.page() == "go" and moves(sim) == n


def test_a_result_arriving_while_the_problem_page_is_open_waits_behind_it(
        qtbot, monkeypatch, tmp_path, settings):
    """Found on screen (run 9): a step's result must not replace the problem page."""
    sim = WindowSim()
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False, sim=sim)
    p.drive_until("check_mark")
    sim.transport.delay_s = 0.01
    [b for b in win._buttons if b.text() == "Yes, it is centred"][0].click()
    qtbot.waitUntil(lambda: win._busy, timeout=5000)
    win._problem_btn.click()
    assert win.pages_shown[-1] == "problem"
    qtbot.waitUntil(lambda: not win._busy, timeout=30000)
    sim.transport.delay_s = 0.0
    assert win.pages_shown[-1] == "problem"               # still there
    [b for b in win._buttons if b.text() == "Something looks or sounds wrong"][0].click()
    p.idle()
    assert sim.jobs[0].only_home and win.pages_shown[-1] in ("after_problem", "refused")

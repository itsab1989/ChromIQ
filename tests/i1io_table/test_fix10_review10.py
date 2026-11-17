"""Fix round 10: every finding of review 10 (B-1, M-1 to M-5, S-1 to S-4, S-6), each with a test
that failed before the fix. The reviewer's own probes (``review10/tree/tests/i1io_table/
test_review10_probes.py``) are taken over as P1 to P7, adapted where the chosen fix differs; the
planted faults that survived the window tests (S-3: F1, F1b, F3, F6, F7, F9, F11) each get the
test that catches them. Against the simulated table and helper: no USB, no instrument."""
from __future__ import annotations

import json

import pytest
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton

from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_reading import small_sheet
from tests.i1io_table.test_window import (ARGS, _interrupted, moves, open_window,  # noqa: F401
                                          project, settings)
from tests.i1io_table.test_window_in_the_measure_tab import (beta, start, tab,  # noqa: F401
                                                             table_run)
from tests.i1io_table.window_person import WindowPerson
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W
from workflow.measurement_state import Ti3State, classify


def _person(win, sim, qtbot):
    return WindowPerson(win, sim, lambda c: qtbot.waitUntil(c, timeout=15000))


# ---- B-1: quitting ChromIQ during a table session ------------------------------------------------

def test_p1_a_table_session_is_a_running_measurement(tab, beta, tmp_path, monkeypatch, qtbot):
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch)
    p = _person(tab._table_window, sim, qtbot)
    p.drive_until("go")
    assert sim.jobs[0].phase == "open"
    assert tab.a_measurement_is_running()


def test_b1_quit_asks_the_tables_ending_and_quits_only_after_the_job_let_go(
        tab, beta, tmp_path, monkeypatch, qtbot):
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch)
    win = tab._table_window
    reasons = []
    win.finished_with.connect(reasons.append)
    p = _person(win, sim, qtbot)
    p.drive_until("check_mark")
    p.press("Yes, it is centred")
    p.drive_until("end_of_session")
    p.press("Keep measuring")                            # nothing missing: asked again
    p.drive_until("end_of_session")
    win._on_close_pressed()                              # withdraw the ending (Esc's way)
    p.idle()
    n = moves(sim)
    # Cmd-Q / the close box: MainWindow.closeEvent asks this
    assert tab.confirm_quit_during_measurement() is False
    p.idle()
    assert p.page() == "end_of_session" and moves(sim) == n      # the same question, no move
    assert "quit" in win._status.text().lower()
    p.press("Save and stop")
    assert classify(run.measurement_ti3, run.chart_ti2).state is Ti3State.COMPLETE
    assert p.page() == "home_offered" and moves(sim) == n
    p.press("Leave it there")
    p.idle()
    job = sim.jobs[0]
    assert job.phase == "closed"                                  # close() ran: USB let go
    if p.page() == "done":
        # something is still to be said (the arm left out): the last page says it, and
        # ChromIQ closes when the person has read it
        assert "closes when you press Close" in win._status.text()
        p.press("Close")
    assert reasons == ["quit"]
    assert tab._table_window is None and not tab.a_measurement_is_running()
    assert tab.confirm_quit_during_measurement() is True          # the second close goes through
    marker = run.i1io_table_session_dir(job.stamp) / "TABLE_IN_USE.json"
    assert marker.is_file() and marker.with_suffix(".acknowledged.json").is_file()


def test_b1_keep_measuring_at_the_quit_cancels_the_quit(tab, beta, tmp_path, monkeypatch, qtbot):
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch)
    win = tab._table_window
    reasons = []
    win.finished_with.connect(reasons.append)
    p = _person(win, sim, qtbot)
    p.drive_until("check_mark")
    p.press("Yes, it is centred")
    p.drive_until("end_of_session")
    p.press("Keep measuring")
    p.drive_until("end_of_session")
    win._on_close_pressed()                              # withdrawn: a question is no longer open
    p.idle()
    assert tab.confirm_quit_during_measurement() is False
    assert p.page() == "end_of_session"
    p.press("Keep measuring")                            # the hand path's rule: no quit
    assert win._quit_wanted is False and reasons == []
    p.drive_until("end_of_session")
    assert tab.a_measurement_is_running()


def test_b1_quit_with_nothing_read_ends_and_quits(tab, beta, tmp_path, monkeypatch, qtbot):
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch)
    win = tab._table_window
    reasons = []
    win.finished_with.connect(reasons.append)
    p = _person(win, sim, qtbot)
    p.drive_until("go")
    n = moves(sim)
    assert tab.confirm_quit_during_measurement() is False
    qtbot.waitUntil(lambda: reasons == ["quit"], timeout=15000)
    assert moves(sim) == n and sim.jobs[0].phase == "closed"


def _into_a_running_row(win, sim, p, qtbot, delay):
    """From the check-mark question to a row being read with a slowed transport."""
    p.drive_until("check_mark")
    p.press("Yes, it is centred")
    sim.transport.delay_s = delay
    for _ in range(4):
        page = p.page()
        if page not in ("first_visit", "go"):
            break
        want = {"first_visit": "Make this move", "go": "Go"}[page]
        [b for b in win._buttons if b.text() == want][0].click()
        qtbot.wait(60)
        if win._busy:
            return
    raise AssertionError(("no row running", win.pages_shown[-4:]))


def test_b1_quit_while_a_row_runs_stops_at_the_next_pause_then_asks(
        tab, beta, tmp_path, monkeypatch, qtbot):
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch)
    win = tab._table_window
    p = _person(win, sim, qtbot)
    _into_a_running_row(win, sim, p, qtbot, delay=0.05)
    assert tab.confirm_quit_during_measurement() is False      # the worker is not killed
    p.idle()
    sim.transport.delay_s = 0.0
    n = moves(sim)
    page = p.page()
    if page not in ("end_of_session", "home_offered", "done"):
        p.answer_page(page)                              # a question shown: withdrawn first
        page = p.page()
    assert page in ("end_of_session", "home_offered", "done"), page
    assert moves(sim) == n and sim.jobs[0].stop_pressed


def test_b1_a_session_the_app_never_closed_asks_switched_off_and_on_at_the_next_start(
        qtbot, monkeypatch, tmp_path, settings):
    """The app killed (no close()): the write-ahead marker stays, and the next START asks
    "switched off and on" before anything is sent, with the words for this case."""
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("check_mark")
    win._finished = True                                 # killed: no ending, no close()
    win.close()
    marker = run.i1io_table_session_dir(RS.STAMP) / "TABLE_IN_USE.json"
    assert marker.is_file() and not marker.with_suffix(".acknowledged.json").exists()
    sim2 = WindowSim()
    win2, sim2, _r, p2, _s, _f = open_window(qtbot, monkeypatch, tmp_path, settings,
                                             asking=False, sim=sim2, run=run,
                                             stamp="20261117-160000")
    p2.drive_until("pending_marker")
    from workflow import measurement_messages as M
    assert win2._text.text() == M.M_I1IO_DRIVE_MARKER_APP_ENDED.render()[1]
    assert sim2.sim.received == []
    assert p2.labels() == ["I switched it off and on", "Not now"]
    p2.press("I switched it off and on")
    assert marker.with_suffix(".acknowledged.json").is_file()


def test_b1_the_app_level_marker_makes_another_project_ask_too(tmp_path):
    from tests.i1io_table import job_harness as H
    from core.file_manager import Project
    from workflow.i1io.table import job as J, session_end as se
    place = (tmp_path / "settings", "sandbox.i1io-table-move-may-be-pending-")
    sheet = small_sheet()
    proj = Project.create(tmp_path / "One", "One")
    run = proj.current_run()
    run.ensure_dir()
    run.chart_ti2.write_text(RS.chart_ti2_text(sheet), encoding="ascii")
    sim = WindowSim(app_marker_place=place)
    job = sim.factory(sheet, 0, run, "20261117-100000", False)
    p = H.Person(job, sim.sim)
    assert p.drive(job.open()).ok                        # killed afterwards: no close()
    assert [m.name for m in se.app_markers(*place)] == [
        se.app_in_use_name(place[1], "20261117-100000")]
    proj2 = Project.create(tmp_path / "Two", "Two")
    run2 = proj2.current_run()
    run2.ensure_dir()
    run2.chart_ti2.write_text(RS.chart_ti2_text(sheet), encoding="ascii")
    job2 = sim.factory(sheet, 0, run2, "20261117-110000", False)
    r = job2.open()
    assert r.confirm == J.Confirm.MARKER and r.detail["app_ended"] == r.detail["markers"] == 1
    assert sim.sim.received == []


# ---- M-1: the shortcuts while a table session is open -------------------------------------------

def test_p7_cmd_n_never_leaves_the_measure_tab_while_the_table_works(qapp):
    from types import SimpleNamespace
    from PyQt6.QtWidgets import QTabWidget, QWidget
    from ui.main_window import MainWindow
    t = QTabWidget()
    for i in range(3):
        t.addTab(QWidget(), str(i))
    t.setCurrentIndex(1)
    t.setTabEnabled(0, False)
    t.setTabEnabled(2, False)
    fake = SimpleNamespace(_tabs=t, _table_session_open=lambda: True)
    MainWindow._go_to_tab(fake, 2)
    assert t.currentIndex() == 1
    fake = SimpleNamespace(_tabs=t, _table_session_open=lambda: False)
    MainWindow._go_to_tab(fake, 2)                        # unchanged without a table session
    assert t.currentIndex() == 2


def test_m1_preferences_shortcut_opens_nothing_while_the_table_works(qapp, monkeypatch):
    from types import SimpleNamespace
    from ui.main_window import MainWindow
    touched = []
    fake = SimpleNamespace(_table_session_open=lambda: True,
                           _tab_chart=SimpleNamespace(
                               current_margin_combo=lambda: touched.append(1)))
    MainWindow._open_settings(fake)                      # returns before anything is built
    assert touched == []


@pytest.fixture
def main_window(qapp, tmp_path):
    from tests._cal_target_fixture import make_window
    w = make_window(qapp, tmp_path)
    w.show()
    yield w
    tw = getattr(w._tab_measure, "_table_window", None)
    if tw is not None:
        tw._finished = True
        tw.close()
        w._tab_measure._table_window = None
    w._closing = True
    w.hide()
    w.deleteLater()


def test_m1_every_shortcut_during_a_table_session_does_what_it_does_during_a_hand_reading(
        main_window, beta, tmp_path, monkeypatch, qtbot, qapp):
    """Every binding of ui.keyboard_help.BINDINGS while the table works: nothing hides the
    Measure tab, nothing opens a modal window. The hand path's set: its key filter takes the
    single keys (none of these carries none), the masthead's buttons are greyed and their
    shortcuts obey them (Cmd-O, Shift-Cmd-O, Cmd-T), Cmd-Return obeys the greyed START, Help
    (F1, Cmd-?) is not modal and stays, as Knut ruled for a hand measurement, Cmd-Y only changes
    the preview's view, Cmd-Q is the quit (B-1). Cmd-1..5 and Cmd-, are guarded for the table."""
    from PyQt6.QtWidgets import QApplication
    from ui.keyboard_help import BINDINGS
    w = main_window
    tm = w._tab_measure
    w._tabs.setCurrentWidget(tm)
    run, sheet = table_run(tmp_path / "tbl")
    sim = start(tm, run, monkeypatch)
    win = tm._table_window
    p = _person(win, sim, qtbot)
    p.drive_until("go")
    measure = w._tabs.indexOf(tm)
    opened = []
    monkeypatch.setattr("ui.dialogs.settings_dialog.SettingsDialog.exec",
                        lambda self: opened.append("prefs") or 0)
    monkeypatch.setattr("ui.tools_popup.ToolsPopup.show_under",
                        lambda self, *a: opened.append("tools"))
    monkeypatch.setattr(type(w._tab_chart), "_load_existing_profile",
                        lambda self: opened.append("project"))
    slots = {"preferences": w._open_settings, "tools": w._open_tools_menu,
             "open_project": w._on_masthead_load_project,
             "open_chart_file": w._on_masthead_load_ti2,
             "primary_action": w._trigger_primary_action,
             "primary_action_alt": w._trigger_primary_action}
    for i in range(w._tabs.count()):
        slots[f"tab_{i + 1}"] = (lambda i=i: w._go_to_tab(i))
    for action, slot in slots.items():
        assert action in BINDINGS
        shown = list(win.pages_shown)
        slot()
        qapp.processEvents()
        assert w._tabs.currentIndex() == measure, action
        assert QApplication.activeModalWidget() is None, action
        assert win.pages_shown == shown, action          # the panel's state is unchanged
    assert opened == []
    assert moves(sim) == 0


# ---- M-2 / M-3: the panel's layout ---------------------------------------------------------------

def _visible_buttons(win):
    return [b for b in win.findChildren(QPushButton) if b.isVisible()]


def _shown_rect(win, w):
    """Where *w* is seen in the panel: a widget inside the scroll area only as far as the
    scroll area's viewport shows it."""
    r = QRect(w.mapTo(win, w.rect().topLeft()), w.size())
    page = win._scroll.widget()
    if page is not None and page.isAncestorOf(w):
        vp = win._scroll.viewport()
        r = r.intersected(QRect(vp.mapTo(win, vp.rect().topLeft()), vp.size()))
    return r


def _check_layout(win, page):
    bs = [b for b in _visible_buttons(win) if not _shown_rect(win, b).isEmpty()]
    for i, a in enumerate(bs):
        ga = _shown_rect(win, a)
        assert a.height() >= a.minimumSizeHint().height() - 1, (page, a.text())
        assert a.width() >= a.minimumSizeHint().width() - 1, (page, a.text())
        for b in bs[i + 1:]:
            gb = _shown_rect(win, b)
            assert not ga.intersects(gb), (page, a.text(), b.text())
    # the text: shown whole in its scroll area (which scrolls if the page is longer), and
    # the area never squeezed to a sliver
    t = win._text
    assert t.height() >= t.heightForWidth(t.width()) - 1, page
    assert win._scroll.viewport().height() >= min(win._text_min_height(),
                                                  win.height() // 3) - 2, page
    stops = [b for b in bs if b.text().lower() == "stop"]
    assert len(stops) <= 1, (page, [b.text() for b in stops])


@pytest.mark.parametrize("size", [(560, 760), (420, 700), (330, 640)])
def test_m2_no_button_overlaps_and_no_text_is_cut_on_any_page(qtbot, monkeypatch, tmp_path,
                                                              settings, size):
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=True,
        sim=WindowSim(faults={"read_loc": {"1-2": "dies"}}))
    win.resize(*size)
    seen = set()
    for _ in range(200):
        page = p.page()
        qtbot.wait(5)
        _check_layout(win, page)
        seen.add(page)
        if page == "row_failed":
            win._problem_btn.click()
            _check_layout(win, "problem")
            p.press("Cancel")
            sim.helper.faults = {}
        if page == "end_of_session":
            break
        p.answer_page(page)
    assert {"prepare", "ready_to_open", "go", "row_failed", "end_of_session"} <= seen


def test_m3_exactly_one_stop_and_it_is_the_footers(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    for _ in range(200):
        page = p.page()
        stops = [b for b in _visible_buttons(win) if b.text() == "Stop"]
        assert all(b is win._stop_btn for b in stops), page
        assert not any(b.text() == "Stop" for b in win._buttons), page
        if page == "end_of_session":
            break
        p.answer_page(page)
    assert win._stop_btn.objectName() == "i1io_table_stop"
    assert "#c62828" in win._stop_btn.styleSheet()


def test_m3_the_state_counts_while_a_row_is_read(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False, sheet=small_sheet([6, 6]))
    _into_a_running_row(win, sim, p, qtbot, delay=0.02)
    seen = []
    for _ in range(800):
        qtbot.wait(10)
        if not win._busy and seen:
            break
        txt = win._state.text()
        if win._busy and "Now: reading row" in txt:
            seen.append(txt)
    sim.transport.delay_s = 0.0
    assert seen, "no live 'Now:' line while the row ran"
    counts = [int(t.split("Readings taken in this measurement: ")[1].split(" ")[0].rstrip("."))
              for t in seen if "Readings taken" in t]
    assert counts == sorted(counts) and counts[-1] > counts[0]


def test_m3_the_tabs_own_controls_make_room_and_come_back(tab, beta, tmp_path, monkeypatch,
                                                          qtbot):
    tab.show()
    before = (tab._left_buttons.isVisible(), tab._calm_outer.isVisible())
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch)
    win = tab._table_window
    assert not tab._left_buttons.isVisible() and not tab._calm_outer.isVisible()
    assert not tab._start_btn.isVisible() and not tab._stop_btn.isVisible()
    p = _person(win, sim, qtbot)
    p.drive_until("go")
    win._on_end_pressed()
    p.idle()
    while p.page() != "done":
        p.answer_page(p.page()) if p.page() != "home_offered" else p.press("Leave it there")
    p.press("Close")
    assert (tab._left_buttons.isVisible(), tab._calm_outer.isVisible()) == before


# ---- M-4: "Measure the rest that way" keeps the resume ------------------------------------------

def _partial_run(qtbot, monkeypatch, tmp_path, settings):
    sim = WindowSim(faults={"read_loc": {"1-2": "dies"}})
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False, sim=sim)
    p.script["row_failed"] = "End this step" if False else "Skip it"
    p.drive_until("end_of_session")
    p.press("Save and stop")
    assert classify(run.measurement_ti3, run.chart_ti2).state is Ti3State.PARTIAL
    p.drive_until("done")
    p.press("Close")
    return run


def test_p4_resume_with_a_field_option_measures_only_the_rest_and_saves(
        qtbot, monkeypatch, tmp_path, settings):
    run = _partial_run(qtbot, monkeypatch, tmp_path, settings)
    before = run.measurement_ti3.read_bytes()
    sim2 = WindowSim()
    win2, sim2, _r, p2, saved2, fin2 = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=False, sim=sim2, run=run,
        stamp="20261117-160000", args=ARGS[:-1] + ["-r", "-n", "chart"])
    assert p2.page() == "options_fields"
    p2.press("Measure the rest that way")
    job = sim2.jobs[0]
    assert job.only_locs is not None and job._resume_base is not None
    assert not job.options_report.options.no_spectral            # as the earlier readings
    assert job.options_report.options.suppress_warnings          # -S kept
    p2.drive_until("end_of_session")
    read = sum(1 for v in job.row_status.get(0, {}).values() if v == "read")
    assert read == 1                                             # only the missing row
    p2.press("Save and stop")
    assert run.measurement_ti3.read_bytes() != before
    assert classify(run.measurement_ti3, run.chart_ti2).state is Ti3State.COMPLETE


# ---- M-5: the hand path's guards that matter -----------------------------------------------------

@pytest.mark.parametrize("guard", ["_blocked_by_a_misfitting_measurement",
                                   "_blocked_by_i1pro2_lights_left_on"])
def test_p6_the_hand_guards_that_matter_also_hold_the_table(tab, beta, tmp_path, monkeypatch,
                                                           guard):
    run, sheet = table_run(tmp_path)
    called = []
    monkeypatch.setattr(tab, guard, lambda *a, **k: called.append(1) or True)
    start(tab, run, monkeypatch)
    assert called == [1] and getattr(tab, "_table_window", None) is None


def test_m5_the_lights_guard_is_asked_for_the_i1pro2_in_the_arm(tab, beta, tmp_path,
                                                                monkeypatch):
    from core import i1pro2_lights_marker as marker
    run, sheet = table_run(tmp_path)
    asked = []
    monkeypatch.setattr(marker, "option_on", lambda s: True)
    monkeypatch.setattr(marker, "left_on", lambda opt, fam: asked.append(fam) or True)
    monkeypatch.setattr(tab, "_i1pro2_lights_left_on_window", lambda: False)
    start(tab, run, monkeypatch)
    assert asked == [marker.CHART_FAMILY] and getattr(tab, "_table_window", None) is None


# ---- S-1: Esc ------------------------------------------------------------------------------------

def test_p2_a_real_esc_on_the_ending_withdraws_it(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("end_of_session")
    n = moves(sim)
    win.activateWindow()
    qtbot.waitUntil(lambda: QApplication.activeWindow() is win, timeout=3000)
    QTest.keyClick(QApplication.focusWidget() or win, Qt.Key.Key_Escape)
    p.idle()
    assert p.page() == "ending_closed" and moves(sim) == n


def test_s1_esc_at_the_go_question_moves_nothing(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("go")
    n = moves(sim)
    win.activateWindow()
    qtbot.waitUntil(lambda: QApplication.activeWindow() is win, timeout=3000)
    QTest.keyClick(QApplication.focusWidget() or win, Qt.Key.Key_Escape)
    p.idle()
    assert moves(sim) == n and p.page() in ("home_offered", "done", "end_of_session")


# ---- S-2: the replace archive only at Save -------------------------------------------------------

def _archive_spy(run):
    moved = []

    def archive():
        dest = run.dir / "old" / "x" / run.measurement_ti3.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        run.measurement_ti3.replace(dest)
        moved.append(dest)
    return archive, moved


def test_p5_complete_it_then_discard_leaves_the_runs_measurement_in_place(
        qtbot, monkeypatch, tmp_path, settings):
    sheet, run = _interrupted(qtbot, monkeypatch, tmp_path, settings)
    run.measurement_ti3.write_text("CTI3\nKEEP ME\n", encoding="ascii")
    archive, moved = _archive_spy(run)
    win, sim, _r, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=False, sheet=sheet, run=run,
        stamp="20261117-160000", replace_agreed=True, archive=archive)
    assert p.page() == "earlier"
    p.press("Complete it")
    assert not moved and p.page() == "prepare"
    p.drive_until("end_of_session")
    p.press("Discard and stop")
    assert not moved and run.measurement_ti3.read_text(encoding="ascii") == "CTI3\nKEEP ME\n"


def test_f11_complete_it_then_save_archives_at_the_save(qtbot, monkeypatch, tmp_path, settings):
    sheet, run = _interrupted(qtbot, monkeypatch, tmp_path, settings)
    run.measurement_ti3.write_text("CTI3\nKEEP ME\n", encoding="ascii")
    archive, moved = _archive_spy(run)
    win, sim, _r, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=False, sheet=sheet, run=run,
        stamp="20261117-160000", replace_agreed=True, archive=archive)
    p.press("Complete it")
    p.drive_until("end_of_session")
    assert not moved
    p.press("Save and stop")
    assert len(moved) == 1 and moved[0].read_text(encoding="ascii") == "CTI3\nKEEP ME\n"
    assert classify(run.measurement_ti3, run.chart_ti2).state is Ti3State.COMPLETE


def test_s2_a_failed_save_after_the_archive_puts_the_measurement_back(
        tab, beta, tmp_path, monkeypatch, qtbot):
    from workflow.i1io.table import measurement as ms
    run, sheet = table_run(tmp_path)
    run.measurement_ti3.write_text(RS.chart_ti2_text(sheet).replace("CTI2", "CTI3", 1),
                                   encoding="ascii")
    keep = run.measurement_ti3.read_bytes()
    monkeypatch.setattr(tab, "_confirm_replacing_measurement", lambda: True)
    monkeypatch.setattr(tab, "_measurement_at_risk", lambda: run.measurement_ti3)
    sim = start(tab, run, monkeypatch)
    win = tab._table_window
    p = _person(win, sim, qtbot)
    p.drive_until("end_of_session")

    def full_disk(*a, **k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(ms, "file_into_run", full_disk)
    p.press("Save and stop")
    assert p.page() == "refused" and "old folder" in win._text.text()
    assert not run.measurement_ti3.exists()              # archived for the Save that failed
    win._on_end_pressed()
    p.idle()
    if p.page() == "end_of_session":
        p.press("Discard and stop")
    while p.page() != "done":
        p.press("Leave it there")
    p.press("Close")
    assert run.measurement_ti3.read_bytes() == keep      # put back where it was


# ---- S-3: the planted faults that survived ------------------------------------------------------

def test_f7_end_measurement_at_go_answers_back_and_nothing_moves(qtbot, monkeypatch, tmp_path,
                                                                settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("go")
    n = moves(sim)
    answered = []
    real = sim.jobs[0].answer

    def spy(kind, value):
        answered.append((kind, value))
        return real(kind, value)
    sim.jobs[0].answer = spy
    win._end_btn.click()
    p.idle()
    assert answered and answered[0] == ("go", "back")
    assert moves(sim) == n and not run.measurement_ti3.exists()


def test_f7_every_withdrawal_is_an_answer_that_moves_nothing():
    no_move = {"back", "stop", "no", "i1profiler", "not sure"}
    assert set(W.WITHDRAW.values()) <= no_move, W.WITHDRAW
    from workflow.i1io.table import job as J
    for kind, value in W.WITHDRAW.items():
        assert value in J.CHOICES[kind], (kind, value)


@pytest.mark.parametrize("which", [0, 1])
def test_f1_both_ready_ticks_are_needed(qtbot, monkeypatch, tmp_path, settings, which):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("ready_to_open")
    win._tick_widgets[which].setChecked(True)
    go = [b for b in win._buttons if b.text() == "Start"][0]
    assert not go.isEnabled()
    shown = list(win.pages_shown)
    win._answer_yes()                                    # even called directly: nothing
    p.idle()
    assert win.pages_shown == shown and sim.sim.received == []


def test_f3_a_stale_result_is_ignored(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("go")
    shown = list(win.pages_shown)
    win._on_done(win._token - 1, win._last)
    assert win.pages_shown == shown


def _close_spy(job):
    got = []
    real = job.close

    def close():
        res = real()
        got.append(dict(res.detail))
        return res
    job.close = close
    return got


def test_f6_a_stop_takes_away_the_dont_ask_offer_window_and_job(qtbot, monkeypatch, tmp_path,
                                                                settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=True)
    p.drive_until("go")
    closed = _close_spy(sim.jobs[0])
    win._stop_btn.click()
    p.press("Go")
    if p.page() in ("stopped_by_you", "refused"):
        p.press("Carry on")
    p.drive_until("end_of_session")
    p.press("Save and stop")
    p.drive_until("done")
    assert win._tick_widgets == []                       # the window offers nothing
    assert sim.jobs[0].stop_pressed and closed and "offer" not in closed[0]   # nor does the job


def test_f9_the_tab_is_locked_while_the_table_works(tab, beta, tmp_path, monkeypatch, qtbot):
    run, sheet = table_run(tmp_path)
    active = []
    tab.measurement_active.connect(active.append)
    sim = start(tab, run, monkeypatch)
    assert active == [True]
    win = tab._table_window
    p = _person(win, sim, qtbot)
    p.drive_until("prepare")
    p.press("Not now")
    assert active == [True, False]


# ---- S-4: the ring is on the patch the arm goes to ----------------------------------------------

def test_s4_patch_next_comes_after_the_stop_check(tmp_path):
    from tests.i1io_table import job_harness as H
    sheet = small_sheet([4])
    proj = project(tmp_path, sheet)[1]
    sim = WindowSim()
    job = sim.factory(sheet, 0, proj, RS.STAMP, False)
    events = []
    p = H.Person(job, sim.sim)
    job.set_options(ARGS)
    assert p.drive(job.open()).ok

    def hook(ev):
        events.append(ev)
        if ev.get("event") == "patch_read" and ev.get("loc") == sheet["pages"][0]["strips"][0][
                "patches"][1]["loc"]:
            job.stop_at_next_pause()
    job.on_progress = hook
    for step in ("calibrate", "align", "check_move", "read_row"):
        res = p.drive(getattr(job, step)())
        if not res.ok:
            break
    nexts = [e["loc"] for e in events if e["event"] == "patch_next"]
    reads = [e["loc"] for e in events if e["event"] == "patch_read"]
    assert nexts == reads, (nexts, reads)        # never announced a patch it did not go to


# ---- S-6: the ending's words ---------------------------------------------------------------------

def test_s6_the_ending_names_no_window_and_has_no_em_dash(qtbot, monkeypatch, tmp_path,
                                                          settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("end_of_session")
    text = win._text.text()
    assert "window" not in text.lower() and "—" not in text


# ---- open point e: the job itself keeps the offer back --------------------------------------------

def test_e_a_clean_asking_measurement_still_offers(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=True)
    closed = _close_spy(sim.jobs[0]) if sim.jobs else None
    p.drive_until("go")
    closed = _close_spy(sim.jobs[0])
    p.drive_until("end_of_session")
    p.press("Save and stop")
    p.drive_until("done")
    assert closed and closed[0].get("offer") == "may_offer_do_not_ask_again"


def test_e_the_jobs_close_offers_nothing_after_a_failed_row(qtbot, monkeypatch, tmp_path,
                                                           settings):
    sim = WindowSim(faults={"read_loc": {"1-2": "dies"}})
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=True, sim=sim)
    p.drive_until("row_failed")
    closed = _close_spy(sim.jobs[0])
    sim.helper.faults = {}
    p.press("Read it again")
    p.drive_until("end_of_session")
    p.press("Save and stop")
    p.drive_until("done")
    assert win._tick_widgets == [] and sim.jobs[0]._a_row_failed()
    assert closed and "offer" not in closed[0]


# ---- S-7: the expected colour of a table reading -------------------------------------------------

def test_s7_a_table_reading_carries_the_charts_expected_colour(tab, beta, tmp_path, monkeypatch):
    got = []
    monkeypatch.setattr(tab, "_on_patch_measured", got.append)
    tab._table_expected = {"A1": [41.0, 21.0, 1.9]}
    tab._on_table_progress({"event": "patch_read", "loc": "A1", "xyz": [40.0, 21.0, 2.0],
                            "page": 1})
    tab._on_table_progress({"event": "patch_read", "loc": "A2", "xyz": [40.0, 21.0, 2.0],
                            "page": 1})
    assert got[0]["exyz"] == [41.0, 21.0, 1.9] and got[0]["de"] > 0
    assert "exyz" not in got[1]                          # none recorded: as before


def test_s7_the_expected_colours_are_read_from_the_chart(tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    run, sheet = table_run(tmp_path)
    exp = TabMeasure._table_chart_expected(run.chart_ti2)
    text = run.chart_ti2.read_text(encoding="ascii")
    if "XYZ_X" in text:
        assert exp and all(len(v) == 3 for v in exp.values())
    else:
        assert exp == {}


def test_m2_a_short_page_after_a_long_one_does_not_keep_the_long_height(
        qtbot, monkeypatch, tmp_path, settings):
    """Found on screen (fix round 10): QLabel's heightForWidth never answers less than the
    label's minimum, so the height of the first (long) page stuck to every later one."""
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=True)
    win.resize(560, 700)
    qtbot.wait(50)
    long_h = win._text.minimumHeight()
    win._show("x", "Short", "Two words.")
    qtbot.wait(50)
    assert win._text.minimumHeight() < long_h / 3
    assert win._scroll.verticalScrollBar().maximum() == 0


def test_m3_read_rows_get_a_margin_dot_not_an_outline(qapp, tmp_path):
    """The owner (on-screen runs): outlines on every read row looked messy; only the row being
    read is framed. Painted for real: the pixels over a read row's patches are untouched."""
    from PyQt6.QtCore import QRect
    from PyQt6.QtGui import QColor, QImage, QPainter
    from ui.tiff_preview import TiffPreview
    pv = TiffPreview()
    pv._current = 0
    rows = [[QRect(40 + 20 * c, 20 + 30 * r, 18, 18) for c in range(5)] for r in range(3)]
    pv.set_table_rows(0, rows, done={0}, active=1)
    img = QImage(200, 120, QImage.Format.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    pv._draw_table_rows(p, 1.0, 1.0, 0.0, 0.0)
    p.end()
    # the read row (0): nothing drawn over its patches, a dot left of it
    assert all(img.pixelColor(x, 29) == QColor("white") for x in range(40, 138))
    assert img.pixelColor(31, 29) != QColor("white")
    # the row being read (1): framed
    assert img.pixelColor(38, 59) != QColor("white")


def test_end_after_a_first_row_that_failed_can_end(qtbot, monkeypatch, tmp_path, settings):
    """Found on screen (fix round 10, German pass): the only row failed after one patch, the
    person ended the step and pressed End measurement: the job refused 'nothing_read' and the
    measurement could never end. It ends as one that kept nothing, and says why."""
    sim = WindowSim(faults={"read_loc": {"0-1": "dies"}})
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False, sim=sim)
    p.drive_until("row_failed")
    p.press("End this step")
    n = moves(sim)
    win._end_btn.click()
    p.idle()
    assert p.page() in ("home_offered", "done"), (p.page(), win._text.text()[:120])
    assert "cannot be kept" in win._text.text() and moves(sim) == n
    assert not run.measurement_ti3.exists()

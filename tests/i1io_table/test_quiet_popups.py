"""The quiet mode's presentation (the owner, 2026-11-18): with "ask after each step" OFF the Measure
tab keeps the hand measurement's own layout and the table asks through pop-up windows like the
other instruments; with it ON the reviewed panel is shown, unchanged.

The four conditions of the pop-ups (awaiting confirmation):

1. a normal, movable top-level dialog, application-modal (never a macOS sheet), opened over the
   tab's left column beside the chart preview, remembering where the person moved it;
2. open only while an answer is needed (never while a job call runs);
3. nothing moves while one is open, and each one of an open table offers a way to the ending;
4. the keys as in every other ChromIQ dialog (item 80, decided by Basti on 27 Nov 2026, "just
   allow it like for everything else"; it replaced "no default button"): Return and Enter press
   the filled answer and nothing else, Space only a button the person moved the focus to; Esc
   never answers with a move.

And the pop-ups are built through the app's shared dialog mechanisms (button roles ordered by the
application's style, ``tint_dialog_primary`` for the confirming answer, ``mark_destructive``), so
a later restyle of the app's dialogs carries over."""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialogButtonBox, QPushButton

from tests.i1io_table.test_job_reading import small_sheet
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (the fixture)
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W


@pytest.fixture(autouse=True)
def _first_time_on_new_ground(monkeypatch):
    """4.3.53 fix round (inventory A8): this walk is about every question's pop-up, the
    first-visit question included, so it keeps the first time on new ground
    (tests/i1io_table/test_4353_first_visit_once.py proves the new rule)."""
    from workflow.i1io.table import job as _J
    monkeypatch.setattr(_J.TableJob, "_known_ground", lambda self, p: False)

MOVES = ("m0", "m1", "m2", "i1", "i0")


def _moves(sim) -> int:
    return sum(1 for ln in sim.sim.received if ln[1:3] in MOVES)


def _quiet(qtbot, monkeypatch, tmp_path, settings, **kw):
    kw.setdefault("asking", False)
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings, **kw)
    return win, sim, run, p, saved, finished


class _MoveWatch:
    """Every movement line the simulated table receives, with whether a pop-up was open."""

    def __init__(self, win, sim):
        self.win, self.sim, self.bad, self.n = win, sim, [], 0
        real = sim.transport.write

        def write(data, *a, **k):
            open_before = win.popup_open()
            n = len(sim.sim.received)
            out = real(data, *a, **k)
            new = [ln for ln in sim.sim.received[n:] if ln[1:3] in MOVES]
            self.n += len(new)
            if new and (open_before or win.popup_open()):
                self.bad.append((win.pages_shown[-1:], new))
            return out
        sim.transport.write = write


# ---- which presentation ------------------------------------------------------------------------

def test_asking_on_keeps_the_panel_and_quiet_mode_uses_pop_ups(qtbot, monkeypatch, tmp_path,
                                                               settings):
    win, *_ = open_window(qtbot, monkeypatch, tmp_path / "a", settings, asking=True)
    assert win.presentation == W.PRESENTATION_PANEL and win.popup() is None
    win2, *_ = _quiet(qtbot, monkeypatch, tmp_path / "b", settings)
    assert win2.presentation == W.PRESENTATION_POPUPS and win2.popup() is not None
    monkeypatch.setattr(W, "QUIET_POPUPS", False)        # the one switch back to the panel
    assert W.presentation_for(settings) == W.PRESENTATION_PANEL


# ---- condition 1 and 4: the dialog itself ------------------------------------------------------

def test_the_pop_up_is_an_application_modal_top_level_dialog_never_a_sheet(
        qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings)
    p.page()
    pop = win.popup()
    assert pop.isVisible() and pop.isWindow()
    assert pop.windowModality() == Qt.WindowModality.ApplicationModal
    # a Dialog window, never a Sheet (a sheet is WindowModal on a child of the main window)
    assert (pop.windowFlags() & Qt.WindowType.WindowType_Mask) == Qt.WindowType.Dialog
    assert pop.windowModality() != Qt.WindowModality.WindowModal
    assert pop.parent() is win
    # the question area is the panel's own (one definition): the same title label
    assert win._title.window() is pop and win._buttons[0].window() is pop


def _defaults(win):
    return [b for b in win.popup().findChildren(QPushButton) if b.isDefault()]


def test_the_filled_answer_is_the_one_default_of_every_pop_up(qtbot, monkeypatch, tmp_path,
                                                              settings):
    """Item 80 (Basti, 27 Nov 2026): as in every other ChromIQ dialog, the button Return presses
    is the one drawn filled (K44), and only that one; a page without a filled answer has none.
    No button's default follows the focus (no autoDefault), and every answer can be reached with
    Tab, as in the other dialogs (the old rule took the focus away from them)."""
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings,
                                               consent=False)
    seen, with_default, without = set(), set(), set()
    for _ in range(80):
        page = p.page()
        seen.add(page)
        filled = W.filled_answer(win._answer_box)
        assert _defaults(win) == ([filled] if filled is not None else []), (page, [
            b.text() for b in _defaults(win)])
        (with_default if filled is not None else without).add(page)
        for b in win.popup().findChildren(QPushButton):
            assert not b.autoDefault(), (page, b.text())
            if b in win._buttons:
                assert b.focusPolicy() != Qt.FocusPolicy.NoFocus, (page, b.text())
        if page == "done":
            break
        if page == "end_of_session":
            p.press("Save and stop")
            continue
        p.answer_page(page)
    assert {"consent", "prepare", "go", "aimed", "end_of_session"} <= seen
    assert {"prepare", "go", "end_of_session"} <= with_default


@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Enter])
@pytest.mark.parametrize("page", ["go", "sheet_laid", "first_visit", "home_at_end",
                                  "end_of_session"])
def test_return_and_enter_press_the_filled_answer(qtbot, monkeypatch, tmp_path, settings, key,
                                                  page):
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings)
    try:
        p.drive_until(page)
    except AssertionError:
        pytest.skip(f"{page} is not asked in this walk")
    shown = len(win.pages_shown)
    filled = W.filled_answer(win._answer_box)
    assert filled is not None and filled.isDefault(), page
    want = filled.text()
    pressed = []
    for b in win._buttons:
        b.clicked.connect(lambda _c=False, t=b.text(): pressed.append(t))
    QTest.keyClick(win.popup(), key)
    p.idle()
    assert pressed == [want], (page, pressed)
    assert len(win.pages_shown) > shown or finished or saved


@pytest.fixture
def the_apps_dialog_filter():
    """main() installs DialogFocusFilter on the application (every dialog: no button starts
    with the focus); the suite's QApplication does not, so this test does, as the app does."""
    from ui.widgets import DialogFocusFilter
    app = QApplication.instance()
    f = DialogFocusFilter(app)
    app.installEventFilter(f)
    yield
    app.removeEventFilter(f)


def test_space_presses_nothing_until_the_person_moves_the_focus_to_a_button(
        qtbot, monkeypatch, tmp_path, settings, the_apps_dialog_filter):
    """As in the other dialogs: no button keeps the focus Qt gives one as a dialog appears, so
    Space alone presses nothing on any page; Space on a button the person moved the focus to
    presses that button."""
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings)
    p.script.update({"end_of_session": "Save and stop"})
    for _ in range(40):
        page = p.page()
        if page == "go":
            break
        qtbot.wait(400)                   # the application's focus passes have run
        fw = win.popup().focusWidget()
        assert not isinstance(fw, QPushButton), (page, fw.text())
        p.answer_page(page)
    qtbot.wait(400)
    n, shown = _moves(sim), len(win.pages_shown)
    pressed = []
    for b in win._buttons:
        b.clicked.connect(lambda _c=False, t=b.text(): pressed.append(t))
    pop = win.popup()
    fw = pop.focusWidget()
    assert not isinstance(fw, QPushButton), fw.text()
    QTest.keyClick(pop.focusWidget() or pop, Qt.Key.Key_Space)   # where the key goes
    qtbot.wait(100)
    assert pressed == [] and _moves(sim) == n and len(win.pages_shown) == shown
    other = [b for b in win._buttons if not b.isDefault()][0]
    want = other.text()
    other.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(other, Qt.Key.Key_Space)
    p.idle()
    assert pressed == [want]


def test_return_presses_nothing_while_the_filled_answer_waits_or_is_missing(
        qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings)
    p.press("Start")
    assert p.page() == "ready_to_open"
    shown = len(win.pages_shown)
    start = [b for b in win._buttons if b.text() == "Start"][0]
    # the ticks not given: no filled answer, no default, Return presses nothing
    assert not start.isEnabled() and _defaults(win) == []
    QTest.keyClick(win.popup(), Qt.Key.Key_Return)
    p.idle()
    assert len(win.pages_shown) == shown and p.page() == "ready_to_open"
    for cb in win._tick_widgets:
        cb.setChecked(True)
    assert _defaults(win) == [start]
    # the hands-off answer while it waits to be ready (HANDS_OFF_READY_MS): the default, not
    # pressed by Return
    start.setEnabled(False)
    QTest.keyClick(win.popup(), Qt.Key.Key_Return)
    p.idle()
    assert p.page() == "ready_to_open"
    start.setEnabled(True)
    QTest.keyClick(win.popup(), Qt.Key.Key_Return)
    p.idle()
    assert p.page() != "ready_to_open"


def test_the_hands_off_answer_is_the_default_while_it_waits(qtbot, monkeypatch, tmp_path,
                                                            settings):
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings)
    p.drive_until("go")
    # the page as it is shown when the hands-off wait is on (the walks set it to 0): the same
    # two calls in the same order as _show
    monkeypatch.setattr(W, "HANDS_OFF_READY_MS", 400)
    win._hold_hands_off_answers(win._buttons)
    win._present_popup("go", win._title.text())
    go = W.filled_answer(win._answer_box)
    assert go is not None and go.isDefault() and not go.isEnabled()
    n, shown = _moves(sim), len(win.pages_shown)
    QTest.keyClick(win.popup(), Qt.Key.Key_Return)
    qtbot.wait(50)
    assert _moves(sim) == n and len(win.pages_shown) == shown
    qtbot.waitUntil(go.isEnabled, timeout=3000)
    assert go.isDefault() and W.filled_answer(win._answer_box) is go
    QTest.keyClick(win.popup(), Qt.Key.Key_Return)
    p.idle()
    assert len(win.pages_shown) > shown


def test_esc_on_a_pop_up_withdraws_and_moves_nothing(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings)
    p.drive_until("go")
    n = _moves(sim)
    win.popup().reject()                                  # what Esc calls
    p.idle()
    assert _moves(sim) == n and p.page() in ("home_offered", "home_at_end", "done", "end_of_session")
    if p.page() == "end_of_session":
        win.popup().reject()                              # Esc on the ending: a withdrawal
        p.idle()
        assert p.page() == "ending_closed" and _moves(sim) == n


def test_the_close_box_of_a_pop_up_is_its_esc(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings)
    p.drive_until("go")
    n = _moves(sim)
    win.popup().close()
    p.idle()
    assert _moves(sim) == n and p.page() in ("home_offered", "home_at_end", "done", "end_of_session")
    assert win.popup().isVisible()                        # the next question, never nothing


def test_the_place_the_person_moved_the_pop_up_to_is_remembered(qtbot, monkeypatch, tmp_path,
                                                               settings):
    settings.set(W.POPUP_POS_KEY, "")
    try:
        win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings)
        p.drive_until("go")
        pop = win.popup()
        at = QPoint(pop.pos().x() + 37, pop.pos().y() + 23)
        pop.move(at)
        p.answer_page("go")                                # the pop-up closes for the step
        p.page()
        assert settings.get(W.POPUP_POS_KEY) == f"{at.x()},{at.y()}"
        assert win.popup().pos() == at                    # the next one opens there
    finally:
        settings.set(W.POPUP_POS_KEY, "")


# ---- condition 2 and 3: open only for an answer; nothing moves while it is open -----------------

@pytest.mark.parametrize("case", ["cold", "failed_row", "strip", "two_rows_report"])
def test_nothing_moves_while_a_pop_up_is_open(qtbot, monkeypatch, tmp_path, settings, case):
    kw = {}
    script = {}
    if case == "cold":
        kw["sim"] = WindowSim(cold=True)
    elif case == "failed_row":
        kw["sim"] = WindowSim(faults={"read": {2: "dies"}})
        kw["sheet"] = small_sheet([4, 4, 4])
        script = {"row_failed": "Read it again"}
    elif case == "strip":
        kw["args"] = ["-v", "-c", "1", "-S", "chart"]
    elif case == "two_rows_report":
        kw["asking"] = True
        kw["presentation"] = W.PRESENTATION_POPUPS
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings, **kw)
    p.script.update(script)
    p.script.update({"end_of_session": "Save and stop", "stopped_by_you": "Next step",
                     "stored_white_refused": "Go on"})
    p.page()
    watch = _MoveWatch(win, sim)
    busy_with_popup = []
    real_idle = p.idle

    def idle():
        if win._busy and win.popup_open():
            busy_with_popup.append(win.pages_shown[-1])
        real_idle()
    p.idle = idle
    p.drive_until("done")
    assert watch.n > 0, "nothing moved at all"
    assert watch.bad == [], watch.bad
    assert busy_with_popup == []


def _hold_the_job_call(monkeypatch, win):
    """The window's job call for the next answer waits in the worker until the returned event
    is set. 4.3.64 gate (2026-11-25): without it the report raced the job thread. Reported
    within ~5 ms of the window going busy, the stop was taken before the GO answer reached the
    job (stopped_before_the_next_move, the case below); reported later, as on a loaded machine,
    the job had already answered GO, read the arm and asked its first-visit question (this
    file keeps every first visit), and Cancel then showed that question: the companion test
    after this one. Each ordering is now driven on purpose, never by the scheduler."""
    import threading
    gate = threading.Event()
    real = win.job.answer

    def held(*a, **k):
        gate.wait(10)
        return real(*a, **k)
    monkeypatch.setattr(win.job, "answer", held)
    return gate


def test_report_a_problem_while_a_row_runs_waits_until_the_table_has_stopped(
        qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings,
                                               sheet=small_sheet([6, 6]))
    p.drive_until("rows")
    watch = _MoveWatch(win, sim)
    sim.transport.delay_s = 0.02
    gate = _hold_the_job_call(monkeypatch, win)
    [b for b in win._buttons if b.text() == "Go"][0].click()
    qtbot.waitUntil(lambda: win._busy, timeout=5000)
    win._on_problem()                                     # the tab's Report a problem
    gate.set()                                            # the job call goes on only now
    assert not win.popup_open() and win.pages_shown[-1] != "problem"
    qtbot.waitUntil(lambda: not win._busy, timeout=30000)
    sim.transport.delay_s = 0.0
    assert win.pages_shown[-1] == "problem" and win.popup_open()
    assert watch.bad == []
    n = _moves(sim)
    p.press("Cancel")
    # the stop that made room for the window was not the person's: the next move asks GO
    assert p.page() in ("go", "stopped_by_you", "report_after_step") and _moves(sim) == n


def test_a_problem_reported_once_the_job_waits_at_its_question_shows_that_question_again(
        qtbot, monkeypatch, tmp_path, settings):
    """The other ordering (the 4.3.64 gate's): the job had answered GO, read the arm and asked
    its first-visit question before the report reached it. The problem window still opens only
    when the job call has returned, Cancel brings back the question that waits, and nothing has
    moved; answering it does not move either, because the stop the report asked for is honoured
    before the move."""
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings,
                                               sheet=small_sheet([6, 6]))
    p.drive_until("rows")
    watch = _MoveWatch(win, sim)
    sim.transport.delay_s = 0.02
    job = win.job
    asked = []
    real = job.answer

    def answered_then_wait(*a, **k):
        res = real(*a, **k)                   # GO, the arm read, the first-visit question
        asked.append(res)
        return res
    monkeypatch.setattr(job, "answer", answered_then_wait)
    import time
    n = _moves(sim)
    [b for b in win._buttons if b.text() == "Go"][0].click()
    assert win._busy
    # no event loop here: the job's result is queued for the window, not yet delivered
    t0 = time.monotonic()
    while not asked and time.monotonic() - t0 < 10:
        time.sleep(0.005)
    assert asked and asked[0].kind == "needs_confirmation" and asked[0].confirm == "first_visit", asked
    win._on_problem()
    assert win._busy and not win.popup_open() and win.pages_shown[-1] != "problem"
    qtbot.waitUntil(lambda: not win._busy, timeout=30000)
    sim.transport.delay_s = 0.0
    assert win.pages_shown[-1] == "problem" and win.popup_open()
    p.press("Cancel")
    assert p.page() == "first_visit" and _moves(sim) == n
    p.press("Make this move, my hands are away")
    assert _moves(sim) == n and watch.bad == []
    assert p.page() in ("go", "stopped_by_you", "report_after_step")


# ---- condition 3: a way to the ending from inside every pop-up of an open table ------------------

@pytest.mark.parametrize("page", ["go", "sheet_laid", "aimed", "first_visit",
                                  "row_failed", "stopped_by_you", "next_page"])
def test_every_pop_up_of_an_open_table_leads_to_the_ending(qtbot, monkeypatch, tmp_path,
                                                          settings, page):
    from tests.i1io_table.test_final_m1_hands_off_after_every_question import _two_pages
    kw = {}
    if page == "row_failed":
        kw = {"sim": WindowSim(faults={"read": {2: "dies"}}), "sheet": small_sheet([4, 4])}
    if page == "next_page":
        kw = {"sheet": _two_pages()}
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings, **kw)
    if page == "stopped_by_you":
        p.drive_until("rows")
        win._on_stop()
    try:
        p.drive_until(page)
    except AssertionError:
        pytest.skip(f"{page} is not asked in this walk")
    pop = win.popup()
    ways = [b for b in pop.findChildren(QPushButton) if b.isVisible() and b.isEnabled()
            and b.text() in (W.tr("End measurement"),)]
    assert ways, (page, [b.text() for b in pop.findChildren(QPushButton) if b.isVisible()])
    n = _moves(sim)
    ways[0].click()
    p.idle()
    assert p.page() in ("end_of_session", "home_offered", "home_at_end", "done"), p.page()
    assert _moves(sim) == n


# ---- the instrument's button closes only its own aiming pop-up ----------------------------------

def test_the_button_closes_only_the_aiming_pop_up_it_belongs_to(qtbot, monkeypatch, tmp_path,
                                                               settings):
    sim = WindowSim(press=True)
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings, sim=sim)
    p.drive_until("aimed")
    qtbot.waitUntil(lambda: "is ready" in win._status.text(), timeout=5000)
    for mark in (1, 2, 3):
        assert p.page() == "aimed" and win.popup_open()
        sim.aim(mark)
        sim.sim.clock += 2.0
        assert sim.helper.press()["event"] == "press"
        qtbot.waitUntil(lambda m=mark: win._busy or win._last.detail.get("mark") != m
                        or p.page() != "aimed", timeout=5000)
        p.idle()
    assert p.page() == "go" and win.popup_open()
    n = _moves(sim)
    # a press now: no aiming question; the GO pop-up stays and nothing moves
    assert sim.helper.press() is None
    qtbot.wait(300)
    assert p.page() == "go" and win.popup_open() and _moves(sim) == n


# ---- quitting ---------------------------------------------------------------------------------

def test_quit_with_a_pop_up_open_asks_the_ending_there(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings)
    p.drive_until("go")
    n = _moves(sim)
    assert win.request_quit() is False
    p.idle()
    assert p.page() in ("end_of_session", "home_offered", "home_at_end", "done") and _moves(sim) == n
    assert win.popup_open()


def test_quit_while_a_row_runs_and_no_pop_up_is_open(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings,
                                               sheet=small_sheet([6, 6]))
    p.drive_until("rows")
    sim.transport.delay_s = 0.02
    [b for b in win._buttons if b.text() == "Go"][0].click()
    qtbot.waitUntil(lambda: win._busy, timeout=5000)
    assert not win.popup_open()
    assert win.request_quit() is False
    qtbot.waitUntil(lambda: not win._busy, timeout=30000)
    sim.transport.delay_s = 0.0
    # the ending when something was read, else straight to the homing offer
    assert p.page() in ("end_of_session", "home_offered", "home_at_end") and win.popup_open()
    if p.page() == "end_of_session":
        p.press("Save and stop")
    assert p.page() == "home_at_end"
    p.leave_it_there()
    p.idle()
    if not finished:
        # the arm was left out: the last page says how it gets home, and Close quits
        assert p.page() == "done" and win.popup_open()
        p.press("Close")
    assert finished == ["quit"] and not win.popup_open()


# ---- the shared helpers and the hand path's model ----------------------------------------------

def test_the_pop_ups_are_built_through_the_apps_shared_dialog_helpers(qtbot, monkeypatch,
                                                                     tmp_path, settings):
    import ui.widgets as UW
    import ui.default_button as DB
    tinted, destroyed = [], []
    real_tint, real_mark = UW.tint_dialog_primary, DB.mark_destructive
    monkeypatch.setattr(UW, "tint_dialog_primary",
                        lambda dlg, c: (tinted.append(c), real_tint(dlg, c)))
    monkeypatch.setattr(DB, "mark_destructive", lambda b: (destroyed.append(b.text()),
                                                          real_mark(b)))
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings)
    p.drive_until("end_of_session")
    from ui.tabs.tab_measure import _TAB_COLOR
    assert tinted and set(tinted) == {_TAB_COLOR}          # the Measure tab's accent
    box = win._answer_box
    assert isinstance(box, QDialogButtonBox)
    R = QDialogButtonBox.ButtonRole
    roles = {b.text(): box.buttonRole(b) for b in box.buttons()}
    # the roles M-END gives its buttons on the hand path (_confirm_end_of_session)
    assert roles == {"Save and stop": R.AcceptRole, "Discard and stop": R.DestructiveRole,
                     "Keep measuring": R.RejectRole}
    assert "Discard and stop" in destroyed
    save = [b for b in box.buttons() if b.text() == "Save and stop"][0]
    # item 80 (Basti, 27 Nov 2026): the filled answer is the default, as on the hand path
    assert save.objectName() == "primary" and save.isDefault()
    # the order is the style's (main.py: WinButtonLayoutStyle), never hard-coded here
    import inspect
    src = inspect.getsource(W.TableMeasureWindow._flow_popup_choices)
    assert "addButton(" in src and "insertWidget" not in src


def test_a_disabled_confirming_answer_is_not_filled(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings)
    assert p.page() == "prepare"
    p.press("Start")
    assert p.page() == "ready_to_open"
    start = [b for b in win._buttons if b.text() == "Start"][0]
    assert not start.isEnabled() and start.objectName() != "primary"
    for cb in win._tick_widgets:
        cb.setChecked(True)
    assert start.isEnabled() and start.objectName() == "primary"


def test_every_question_of_the_panel_is_a_pop_up_with_the_same_words(qtbot, monkeypatch,
                                                                    tmp_path, settings):
    """One definition: the same walk in both presentations shows the same pages with the same
    titles, texts and answers."""
    walks = {}
    for pres in (W.PRESENTATION_PANEL, W.PRESENTATION_POPUPS):
        win, sim, run, p, saved, finished = open_window(
            qtbot, monkeypatch, tmp_path / pres, settings, asking=False, presentation=pres)
        p.script.update({"end_of_session": "Save and stop"})
        seen = []
        for _ in range(200):
            page = p.page()
            seen.append((page, win._title.text(), win._text.text(),
                         tuple(b.text() for b in win._buttons)))
            if page == "done":
                break
            p.answer_page(page)
        walks[pres] = seen
    a, b = walks[W.PRESENTATION_PANEL], walks[W.PRESENTATION_POPUPS]
    assert [x[0] for x in a] == [x[0] for x in b]
    for x, y in zip(a, b):
        assert x[0] == y[0] and x[1] == y[1] and x[2] == y[2], x[0]
        assert sorted(x[3]) == sorted(y[3]), x[0]


def test_the_log_says_what_the_table_does_and_each_question_and_answer(qtbot, monkeypatch,
                                                                      tmp_path, settings):
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings)
    lines = []
    win.log_line.connect(lines.append)
    p.script.update({"end_of_session": "Save and stop"})
    p.drive_until("done")
    text = "\n".join(lines)
    assert "In the table's window: The arm is about to move" in text
    assert "Your answer: Go" in text
    assert "Now: reading row 1 of page 1, patch" in text
    assert "Arm: at its resting place." in text
    assert "Readings taken in this measurement:" in text
    assert "White reference:" in text


# ---- the Measure tab ---------------------------------------------------------------------------

def _tab_quiet(tab, tmp_path, monkeypatch, size=None, sim=None):
    """The tab with the pre-4.3.52 quiet mode (every question in a pop-up, no report): the
    guidance stays on, the presentation is the pop-ups (see WindowSim.report_switch)."""
    from tests.i1io_table.test_window_in_the_measure_tab import start, table_run
    from tests.i1io_table.window_sim import WindowSim
    import ui.i1io_table_window as WW
    tab._settings.set(WW.ASK_KEY, True)
    monkeypatch.setattr(WW, "presentation_for", lambda _s: WW.PRESENTATION_POPUPS)
    sim = sim or WindowSim()
    sim.report_switch = False
    tab._settings.set(WW.POPUP_POS_KEY, "")
    if size is not None:
        tab.resize(*size)
    tab.show()
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch, sim=sim)
    return run, sim


from tests.i1io_table.test_window_in_the_measure_tab import beta, tab  # noqa: E402,F401


def test_quiet_mode_keeps_the_tabs_own_layout(tab, beta, tmp_path, monkeypatch, qtbot):
    from tests.i1io_table.window_person import WindowPerson
    before_stack = tab._stack.currentWidget()
    run, sim = _tab_quiet(tab, tmp_path, monkeypatch, size=(1440, 900))
    win = tab._table_window
    assert win.presentation == W.PRESENTATION_POPUPS
    assert tab._stack.currentWidget() is before_stack and not win.isVisible()
    assert tab._left_buttons.isVisible() and tab._stop_btn.isVisible()
    assert not tab._start_btn.isEnabled()
    assert tab._table_switch_off_line.isVisible() and tab._table_problem_btn.isVisible()
    assert "switch the table off at its power switch" in tab._table_switch_off_text.text()
    # Report a problem stands in that line, at its right end, directly above Stop
    assert tab._table_problem_btn.parentWidget() is tab._table_switch_off_line
    # options greyed as for a hand read; the live-preview group stays usable
    assert not tab._m_options.isEnabled()
    p = WindowPerson(win, sim, lambda c: qtbot.waitUntil(c, timeout=15000))
    p.script.update({"end_of_session": "Save and stop"})
    p.drive_until("go")
    p.answer_page("go")
    # the table is open: the tab's Stop is live, and Report a problem beside it
    assert tab._stop_btn.isEnabled() and tab._table_problem_btn.isEnabled()
    log = tab._log.toPlainText()
    assert "In the table's window:" in log and "Your answer: Go" in log
    monkeypatch.setattr(tab, "_show_all_stripes_done", lambda table=False: None)
    p.drive_until("done")
    p.press("Close")
    assert tab._table_window is None
    assert not tab._table_switch_off_line.isVisible() and not tab._table_problem_btn.isVisible()
    assert tab._start_btn.isEnabled() and not tab._stop_btn.isEnabled()


def test_the_tabs_stop_is_the_tables_stop(tab, beta, tmp_path, monkeypatch, qtbot):
    from tests.i1io_table.window_person import WindowPerson
    run, sim = _tab_quiet(tab, tmp_path, monkeypatch, size=(1440, 900))
    win = tab._table_window
    p = WindowPerson(win, sim, lambda c: qtbot.waitUntil(c, timeout=15000))
    p.drive_until("rows")
    sim.transport.delay_s = 0.02
    [b for b in win._buttons if b.text() == "Go"][0].click()
    qtbot.waitUntil(lambda: win._busy, timeout=5000)
    assert tab._stop_btn.isEnabled() and not win.popup_open()
    tab._stop_btn.click()
    qtbot.waitUntil(lambda: not win._busy, timeout=30000)
    sim.transport.delay_s = 0.0
    assert p.page() == "stopped_by_you" and win.popup_open()
    labels = [b.text() for b in win.popup().findChildren(QPushButton) if b.isVisible()]
    assert "Next step" in labels and "End measurement" in labels
    assert "Stop pressed: ChromIQ stops before the next move." in tab._log.toPlainText()


@pytest.mark.parametrize("size", [(1440, 900), (900, 540)])
def test_the_pop_up_never_opens_over_the_chart_preview(tab, beta, tmp_path, monkeypatch, qtbot,
                                                       size):
    """(1440, 900): the Measure tab at the main window's default size (1440 x 1025 less the
    masthead and the tab bar); (900, 540): at the smallest main window (900 x 650)."""
    from tests.i1io_table.window_person import WindowPerson
    run, sim = _tab_quiet(tab, tmp_path, monkeypatch, size=size)
    win = tab._table_window
    p = WindowPerson(win, sim, lambda c: qtbot.waitUntil(c, timeout=15000))
    prev = QRect(tab._preview.mapToGlobal(QPoint(0, 0)), tab._preview.size())
    for target in ("prepare", "sheet_laid", "aimed", "go", "end_of_session"):
        p.drive_until(target)
        fg = win.popup().frameGeometry()
        assert not fg.intersects(prev), (size, target, fg, prev)


@pytest.mark.parametrize("page", ["prepare", "sheet_laid", "go", "end_of_session",
                                  "home_at_end"])
def test_no_button_of_a_pop_up_is_cut(qtbot, monkeypatch, tmp_path, settings, page):
    """Found on screen: the last answer and the footer were cut at the pop-up's lower edge
    (the polished buttons are taller than a hint taken before the pop-up was shown)."""
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings)
    # the app's button style makes buttons taller than a fixed 32 px (as on screen); styled
    # on the pop-up itself, never on the application (CLAUDE.md)
    win.popup().setStyleSheet("QPushButton { min-height: 40px; padding: 4px 14px; }")
    p.script.update({"end_of_session": "Save and stop"})
    p.drive_until(page)
    qtbot.wait(300)
    pop = win.popup()
    inside = QRect(0, 0, pop.width(), pop.height())
    for b in pop.findChildren(QPushButton):
        if not b.isVisible():
            continue
        r = QRect(b.mapTo(pop, QPoint(0, 0)), b.size())
        assert inside.contains(r), (page, b.text(), r, inside)
        box = b.parentWidget()
        assert QRect(0, 0, box.width(), box.height()).contains(b.geometry()), (page, b.text())
        assert b.height() >= b.minimumSizeHint().height(), (page, b.text())
    # and no empty band under the text: the scroll area is at most a line taller than its page
    ls = win._text.fontMetrics().lineSpacing()
    if win._answers.parent() is pop:
        assert win._scroll.viewport().height() <= win._scroll.widget().sizeHint().height() + ls * 2


def test_at_most_one_answer_is_filled_in_the_accent(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings)
    p.script.update({"end_of_session": "Save and stop", "stopped_by_you": "Next step"})
    p.script.update({"refused": "Next step"})
    seen, stopped = 0, False
    for _ in range(120):
        page = p.page()
        if p.at_the_rows(page) and not stopped:
            stopped = True
            win._on_stop()                       # the Stopped page: two confirming answers
            p.press("Go")                        # honoured at the answer: nothing moves
            page = p.page()
            assert page == "stopped_by_you"
        filled = [b.text() for b in win._answer_box.buttons() if b.objectName() == "primary"]
        assert len(filled) <= 1, (page, filled)
        seen += 1
        if page == "done":
            break
        p.answer_page(page)
    assert seen > 10


@pytest.mark.parametrize("presentation", ["panel", "popups"])
def test_the_problem_window_has_the_note_field(qtbot, monkeypatch, tmp_path, settings,
                                               presentation):
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings,
                                               presentation=presentation)
    p.drive_until("go")
    win._on_problem()
    p.idle()
    assert p.page() == "problem"
    host = win.popup() if presentation == "popups" else win
    assert win._note_box.isVisibleTo(host) and win._note_edit.isVisibleTo(host)


def test_the_countdown_has_no_default_return_presses_nothing(qtbot, monkeypatch, tmp_path,
                                                             settings):
    """Item 80: the countdown (guidance off) has only Stop, never filled: Return there presses
    nothing, and the arm moves only when the countdown ends."""
    seen = []
    real = W.TableMeasureWindow._present_popup

    def present(self, page_id, title):
        real(self, page_id, title)
        if page_id == "countdown" and self.popup() is not None and self.popup().isVisible():
            pop = self.popup()
            seen.append([b.text() for b in pop.findChildren(QPushButton) if b.isDefault()])
            stops = []
            self._popup.stop_btn.clicked.connect(lambda *_a: stops.append(1))
            QTest.keyClick(pop, Qt.Key.Key_Return)
            QTest.keyClick(pop, Qt.Key.Key_Enter)
            seen.append(stops)
    monkeypatch.setattr(W.TableMeasureWindow, "_present_popup", present)
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings,
                                               guided=False)
    p.script.update({"end_of_session": "Save and stop"})
    for _ in range(60):
        page = p.page()
        if seen or page == "done":
            break
        p.answer_page(page)
    assert seen and seen[0] == [] and seen[1] == [], seen


def _key(widget, kind, key, repeat=False):
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QKeyEvent
    ev = QKeyEvent(QEvent.Type.KeyPress if kind == "press" else QEvent.Type.KeyRelease, key,
                   Qt.KeyboardModifier.NoModifier, "\r", repeat)
    QApplication.sendEvent(widget, ev)


@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Enter])
def test_a_held_return_counts_once(qtbot, monkeypatch, tmp_path, settings, key,
                                   _no_modal_may_hang_the_suite):
    """Safety review of item 80, S1: held from "Go" for 6 s (a press, then the key's auto-repeat
    every 33 ms) it answered Go, Save and stop and the homing: 9 movement lines from one key.
    As in an ordinary dialog one press closes, a held key counts once: Go only."""
    monkeypatch.setattr(W, "HANDS_OFF_READY_MS", 600)
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings)
    p.script.update({"end_of_session": "Save and stop"})
    monkeypatch.setattr(W, "HANDS_OFF_READY_MS", 0)
    p.drive_until("go")
    monkeypatch.setattr(W, "HANDS_OFF_READY_MS", 600)
    # a page waits 6 s here for an answer that never comes (the suite closes one after 4 s)
    _no_modal_may_hang_the_suite.grace_ms = 30000
    go = W.filled_answer(win._answer_box)
    qtbot.waitUntil(go.isEnabled, timeout=3000)
    pressed = []

    class _Rec:
        def __init__(self, label):
            self.label = label

        def hit(self, *_a):
            pressed.append(self.label)
    recs = []

    def watch():
        for b in win._buttons:
            r = _Rec(b.text())
            recs.append(r)
            b.clicked.connect(r.hit)
    real = win._present_popup

    def present(page_id, title):
        real(page_id, title)
        watch()
    monkeypatch.setattr(win, "_present_popup", present)
    watch()
    n0 = _moves(sim)
    _key(win.popup(), "press", key)                      # the press: Go
    t0 = __import__("time").monotonic()
    while __import__("time").monotonic() - t0 < 6.0:     # held: the auto-repeat, every 33 ms
        pop = win.popup()
        target = pop if pop.isVisible() else (QApplication.focusWidget() or win)
        _key(target, "press", key, repeat=True)
        qtbot.wait(33)
    p.idle()
    assert pressed == [W.tr("Go")], pressed
    # Go asks the move to new ground next: nothing moved, nothing saved
    assert p.page() == "first_visit" and _moves(sim) == n0 and not saved
    # the key still held when the next page appears (no release seen): a non-repeat press there
    # (a key event a window may synthesise) answers nothing either
    page, shown = p.page(), len(win.pages_shown)
    assert win.popup().isVisible() and W.filled_answer(win._answer_box) is not None
    if True:
        qtbot.waitUntil(lambda: W.filled_answer(win._answer_box).isEnabled(), timeout=3000)
        _key(win.popup(), "press", key)
        p.idle()
        assert len(win.pages_shown) == shown and p.page() == page and pressed == [W.tr("Go")]
        # released: the next press answers
        _key(win.popup(), "release", key)
        _key(win.popup(), "press", key)
        _key(win.popup(), "release", key)
        p.idle()
        assert pressed == [W.tr("Go"), W.tr("Make this move, my hands are away")]


def test_a_repeating_key_whose_press_went_elsewhere_answers_nothing(qtbot, monkeypatch, tmp_path,
                                                                    settings):
    """The press of a held key landed in another window (the main window, before the pop-up
    appeared); its auto-repeat then reaches the pop-up: it answers nothing."""
    win, sim, run, p, saved, finished = _quiet(qtbot, monkeypatch, tmp_path, settings)
    p.drive_until("go")
    shown, n = len(win.pages_shown), _moves(sim)
    for _ in range(10):
        _key(win.popup(), "press", Qt.Key.Key_Return, repeat=True)
        qtbot.wait(20)
    p.idle()
    assert len(win.pages_shown) == shown and p.page() == "go" and _moves(sim) == n

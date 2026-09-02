"""Three endings that destroyed or stranded a measurement (beta 7, F6/F7/F8).

All three were found by driving the real app, and **all three would have passed
a source-reading test**: the names were right and the behaviour was wrong. So
nothing here reads `inspect.getsource`. Every test drives the shipping object
and looks at what actually goes out to the reader.

* **F6** — closing the window mid-measurement went straight to
  `ArgyllRunner.cleanup()`, which kills the reader. Stock chartread writes its
  `.ti3` only on a clean exit (§0), so an ordinary Cmd-Q four strips in
  destroyed all four with no question asked. Measured on the real binary: one
  strip read, ended with 'd' then 'y' the file holds 16 readings; killed there
  is no file at all.

* **F7** — from the reader's own "Are you sure [y/n]", "Save and stop" sent 'd'
  (stock) or `{"cmd":"quit"}` (engine). Neither is 'y', so the reader dropped
  back into its loop having saved nothing, and no second prompt was ever
  printed for the chain to wait for. Measured on the real chartread: at that
  prompt 'd' does not even end the process; 'y' exits 0 and writes the file.

* **F8** — "Keep measuring" on that same window returned "n" from a **slot**,
  whose return value Qt discards, and never re-installed the application event
  filter. The prompt stayed unanswered and the keyboard stayed disconnected.

`docs/design/measurement_exit_strategy.md`: *"Every way out of a session goes
through `_confirm_end_of_session` … A window that ends a session any other way
is a second exit, and that is the thing this document exists to catch."*
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt                       # noqa: E402
from PyQt6.QtGui import QKeyEvent                         # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget         # noqa: E402

from workflow.measure_manager import MeasureManager       # noqa: E402

#: What stock chartread prints when the user presses 'd' with a patch unread.
UNREAD_LINE = "\nDone ? - At least one unread patch (1, A1), Are you sure [n]: "
#: …and what the ChromIQ helper reports for the same thing.
UNREAD_EVENT = json.dumps({"event": "unread_confirm", "id": "1", "loc": "A1"})
#: chartread.c:1652 — the misread prompt the reader blocks on.
RETRY_LINE = "Strip read failed due to misread (Bad read)"
#: "Ready to read strip pass B" — the strip menu.
MENU_LINE = "Ready to read strip pass B"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class Radio:
    """The process, and only the process. Records what ChromIQ sends it."""

    def __init__(self):
        self.sent: list[str] = []
        self.is_running = True

    def write_stdin(self, data):
        self.sent.append(data if isinstance(data, str) else data.decode())

    def abort(self):
        self.sent.append("<KILL>")
        self.is_running = False

    def cleanup(self):
        self.abort()


def a_manager(engine: bool):
    r = Radio()
    m = MeasureManager(r)
    m._engine_active = engine
    m._external_values = False
    return m, r


def at_the_unread_prompt(engine: bool):
    """A manager whose reader is blocked on its own "Are you sure [y/n]"."""
    m, r = a_manager(engine)
    raised: list[str] = []
    m.unread_confirm.connect(raised.append)
    if engine:
        m._handle_engine_line(UNREAD_EVENT, lambda _l: None)
    else:
        m._handle_line(UNREAD_LINE, lambda _l: None)
    assert raised, "the window that offers Save and stop was never raised"
    assert r.sent == [], "nothing should have been sent yet"
    return m, r


# ---------------------------------------------------------------- F7 -----
@pytest.mark.parametrize("engine,expected", [
    (False, ["y"]),
    (True, ['{"cmd": "yes"}\n']),
])
def test_save_and_stop_at_the_unread_prompt_sends_the_key_that_writes(
        qapp, engine, expected):
    """'y' is the only key that saves from there, on either reader.

    Everything else falls back into the read loop — measured on the real
    chartread, 'd' and 'n' both leave it running with no `.ti3` at all, and 'y'
    exits 0 with the readings in the file.
    """
    m, r = at_the_unread_prompt(engine)
    m.send_save_partial_and_quit()
    assert r.sent == expected, (
        "Save and stop sent a key the reader rejects, so nothing is written")
    assert m._save_partial_state is None, (
        "the chain is waiting for a prompt that will never be printed again")


@pytest.mark.parametrize("engine,expected", [
    (False, ["n"]),
    (True, ['{"cmd": "next_unread"}\n']),
])
def test_keep_measuring_answers_the_prompt(qapp, engine, expected):
    """The manager must be able to say "no" there; on the engine that means the
    key has to be in KEY_TO_COMMAND, or it is dropped in silence."""
    m, r = at_the_unread_prompt(engine)
    m.send_key("n")
    assert r.sent == expected


def test_the_prompt_flag_is_spent_by_whatever_is_sent_first(qapp):
    """The reader consumes exactly one character there, so the flag must not
    outlive it — otherwise a later Stop would send 'y' into a strip menu."""
    m, r = at_the_unread_prompt(False)
    assert m._at_unread_prompt is True
    m.send_key("f")                        # the user navigates instead
    assert m._at_unread_prompt is False
    r.sent.clear()
    m.send_save_partial_and_quit()
    assert r.sent == ["d"], "the menu route was not restored"


# ---- the controls: the routes that already worked must not move ---------
def test_control_the_menu_route_still_sends_d_then_y(qapp):
    """`send_save_partial_and_quit` from the strip menu: 'd' raises the saving
    question and 'y' answers it. This is the chain F7's fix must not disturb —
    and a probe that cannot show it still works proves nothing about the one
    above."""
    m, r = a_manager(engine=False)
    m.send_save_partial_and_quit()
    assert r.sent == ["d"]
    assert m._save_partial_state == "wait_are_you_sure"
    m._handle_line(UNREAD_LINE, lambda _l: None)
    assert r.sent == ["d", "y"]
    assert m._save_partial_state is None


def test_control_the_retry_route_still_spends_a_key_first(qapp):
    """From a failure prompt the retry key has to be spent before 'd' can reach
    the menu (§1b). Unchanged."""
    m, r = a_manager(engine=False)
    m._handle_line(RETRY_LINE, lambda _l: None)
    assert m._at_retry_prompt is True
    m.send_save_partial_and_quit()
    assert r.sent == ["r"]
    m._handle_line(MENU_LINE, lambda _l: None)
    m._handle_line(UNREAD_LINE, lambda _l: None)
    assert r.sent == ["r", "d", "y"]
    assert m._save_partial_state is None


def test_control_the_engine_two_quit_chain_is_untouched(qapp):
    """Away from that prompt the engine still sends two quits (§1b), which is
    what makes its helper write the file."""
    m, r = a_manager(engine=True)
    m.send_save_partial_and_quit()
    assert r.sent == ['{"cmd": "quit"}\n']
    assert m._save_partial_state == "wait_give_up_prompt"


# ------------------------------------------------------- the Measure tab --
class StubRunner:
    """Enough ArgyllRunner for the tab: something is running, and it can stop."""

    def __init__(self):
        self.is_running = True
        self.cleaned = False

    def cleanup(self):
        self.cleaned = True
        self.is_running = False


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    t = TabMeasure(ArgyllRunner(s), s)
    t._manager, t._radio = a_manager(engine=False)
    t._runner = StubRunner()
    t._arm_key_watchdog = lambda: None
    t._cue_window = lambda *_a, **_k: None
    t._session_live = True
    yield t
    # Never leave an application-wide filter behind for the next test.
    t._session_live = False
    QApplication.instance().removeEventFilter(t)


def keyboard_reaches_the_reader(tab) -> bool:
    """Does a keypress anywhere in the app still reach the reader?

    The filter is installed on the QApplication, so an event sent to any widget
    passes through it. Used both as the measurement and as its own control.
    """
    tab._radio.sent.clear()
    probe = QWidget()
    QApplication.sendEvent(probe, QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_F,
        Qt.KeyboardModifier.NoModifier, "f"))
    return tab._radio.sent == ["f"]


# ---------------------------------------------------------------- F8 -----
def test_keep_measuring_sends_the_answer_and_gives_the_keyboard_back(tab):
    """The window's own promise: *"closes this window and carries on where you
    were."*

    Both halves are asserted, because either one alone leaves the session dead:
    without the 'n' the reader stays blocked on its y/n for ever, and without
    the filter the user's keys never reach it again.
    """
    QApplication.instance().installEventFilter(tab)
    assert keyboard_reaches_the_reader(tab), (
        "CONTROL: the probe cannot see a filter that IS installed, so a "
        "negative result below would mean nothing")

    tab._manager, tab._radio = at_the_unread_prompt(engine=False)
    tab._confirm_end_of_session = lambda *_a, **_k: None      # Keep measuring
    tab._on_unread_confirm("1, A1")

    assert tab._radio.sent == ["n"], (
        "the reader is still blocked on its own y/n; a slot's return value is "
        "discarded by Qt")
    assert keyboard_reaches_the_reader(tab), (
        "the application event filter was removed and never put back")


@pytest.mark.parametrize("choice", ["save", "discard"])
def test_an_ending_from_that_window_does_not_reconnect_the_keyboard(tab, choice):
    """The session is over, so the app-wide filter must not survive it —
    otherwise an arrow key anywhere in ChromIQ is swallowed afterwards."""
    QApplication.instance().installEventFilter(tab)
    tab._manager, tab._radio = at_the_unread_prompt(engine=False)
    tab._confirm_end_of_session = lambda *_a, **_k: choice
    tab._on_unread_confirm("1, A1")
    tab._session_live = False
    assert not keyboard_reaches_the_reader(tab)


def test_save_from_that_window_runs_the_save_chain(tab):
    tab._manager, tab._radio = at_the_unread_prompt(engine=False)
    tab._confirm_end_of_session = lambda *_a, **_k: "save"
    tab._on_unread_confirm("1, A1")
    assert tab._radio.sent == ["y"], "Save and stop did not save"


# ---------------------------------------------------------------- F6 -----
def test_quitting_asks_the_one_ending_question(tab):
    asked: list[str] = []

    def ask(how="stop"):
        asked.append(how)
        return None

    tab._confirm_end_of_session = ask
    assert tab.confirm_quit_during_measurement() is False, (
        "Keep measuring must cancel the quit, not close the app anyway")
    assert asked == [tab.END_QUIT], (
        "quitting is a second exit again; it must go through the one window")


def test_keep_measuring_leaves_the_session_alone(tab):
    tab._confirm_end_of_session = lambda *_a, **_k: None
    ended: list = []
    tab._end_session = lambda c: ended.append(c)
    assert tab.confirm_quit_during_measurement() is False
    assert ended == [], "the session was ended even though the user said no"
    assert tab._radio.sent == []


@pytest.mark.parametrize("choice", ["save", "discard"])
def test_the_chosen_ending_is_carried_out_before_the_app_closes(tab, choice):
    order: list[str] = []
    tab._confirm_end_of_session = lambda *_a, **_k: choice
    real_end = tab._end_session
    tab._end_session = lambda c: (order.append("end:" + str(c)), real_end(c))
    tab.wait_for_the_reader_to_finish = lambda *a, **k: order.append("wait")

    assert tab.confirm_quit_during_measurement() is True
    assert order == ["end:" + choice, "wait"], (
        "the app must not tear the process down before the ending has run")


def test_a_quit_with_nothing_running_asks_nothing(tab):
    tab._session_live = False
    tab._confirm_end_of_session = lambda *_a, **_k: pytest.fail(
        "a quit with no measurement must not raise a window")
    assert tab.confirm_quit_during_measurement() is True


def test_the_wait_returns_only_when_the_reader_has_gone(tab):
    """It is what lets the save chain finish. Measured on the real stock
    chartread: without it only 'd' goes out and there is no `.ti3`; with it
    'd' then 'y' go out, the reader exits 0 and the readings are on disk."""
    ticks = {"n": 0}

    class Slow:
        cleaned = False

        @property
        def is_running(self):
            ticks["n"] += 1
            return ticks["n"] < 5

    tab._runner = Slow()
    assert tab.wait_for_the_reader_to_finish(timeout_s=5.0) is True
    assert ticks["n"] >= 5, "the wait returned while the reader was still up"


def test_the_wait_gives_up_rather_than_hanging_the_quit(tab):
    class Stuck:
        is_running = True

    tab._runner = Stuck()
    assert tab.wait_for_the_reader_to_finish(timeout_s=0.2) is False


# ------------------------------------------------- the window itself -----
@pytest.fixture
def window(tmp_path, monkeypatch):
    """A real MainWindow, in a sandbox — no user settings, no user presets."""
    from PyQt6.QtCore import QSettings
    import core.settings as cs

    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    ini = str(tmp_path / "settings.ini")
    monkeypatch.setattr(
        cs, "QSettings",
        lambda *a, **k: QSettings(ini, QSettings.Format.IniFormat))
    QApplication.instance() or QApplication([])
    from ui.main_window import MainWindow
    win = MainWindow(cs.AppSettings())
    yield win
    win.close()


def test_the_window_can_actually_REACH_the_quit_door(window):
    """⚠ THE LESSON FROM `_mark_quit_on_the_measurement`.

    Its first version looked for `self.tab_measure` and `self._measure_manager`
    — MainWindow has neither — so the guard was dead code for weeks while a
    source-reading test stayed green. This one follows the real lookup.
    """
    assert callable(getattr(window._tab_measure,
                            "confirm_quit_during_measurement", None))
    assert window._ask_before_quitting_on_a_measurement() is True, (
        "with no measurement running the quit must not be held up")


def test_closing_is_refused_while_a_measurement_says_no(window):
    """The whole point: close() must come back False and nothing may be killed.

    Driven through the real `closeEvent`, because the fault was that the ask
    did not exist there at all.
    """
    killed: list[str] = []
    window._runner.cleanup = lambda: killed.append("cleanup")
    window._tab_measure.confirm_quit_during_measurement = lambda: False

    assert window.close() is False, "the quit was not cancelled"
    assert killed == [], (
        "the reader was killed anyway, which is the data loss this removes")
    assert window._closing is False, (
        "a refused close must not leave the window unable to close later")


def test_closing_proceeds_when_the_measurement_is_done_with(window):
    window._tab_measure.confirm_quit_during_measurement = lambda: True
    assert window.close() is True


def test_a_broken_guard_never_traps_the_user(window):
    def boom():
        raise RuntimeError("no")

    window._tab_measure.confirm_quit_during_measurement = boom
    assert window._ask_before_quitting_on_a_measurement() is True

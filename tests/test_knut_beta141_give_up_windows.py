"""#130 beta.141 — Give Up closes its window before asking, and ends once.

Knut found three faces of the same fault, in strip mode on the ChromIQ engine:

* *"clicking 'Give Up' called both 'Instrument Error' and 'Strip Read
  Interrupted' windows simultaneously. The 'Strip Read Interrupted' window
  should not come at all."*
* Wrong Strip Read → Give Up → *"window 'Keep what you have measured so far?'
  appears (good), but it appears on top of the previous window … (the window
  was not closed, or it came more than once)"*
* Unexpected Color Response → Give Up → the same.

Two causes. The ending question was opened from inside the button handler,
*before* ``dlg.accept()``, so it stacked on the window it belonged to. And
nothing told the reader that the ending had already been answered, so its own
report of the interruption raised a second window about it.
"""
from __future__ import annotations

import inspect
import re

import pytest

from ui.tabs.tab_measure import TabMeasure
from workflow.measure_manager import MeasureManager


class _Runner:
    def __init__(self):
        self.sent = []

    def write_stdin(self, text):
        self.sent.append(text)


def _feed(manager, line: str) -> None:
    manager._handle_engine_line(line, lambda _t: None)


@pytest.fixture
def manager(qapp):
    m = MeasureManager.__new__(MeasureManager)
    MeasureManager.__init__(m, _Runner())
    m._engine_active = True
    return m


# ---- the window must close before the next one opens --------------------
def test_no_failure_window_asks_while_it_is_still_open():
    """The ending question must never be raised from inside a button handler:
    dlg.accept() runs afterwards, so the question lands on top."""
    src = inspect.getsource(TabMeasure)
    bad = re.findall(r"def _give_up\(\):\s*\n\s*chosen\[0\] = self\._give_up_or_save\(\)",
                     src)
    assert not bad, (
        f"{len(bad)} Give Up handler(s) still ask while their window is open")


def test_every_give_up_defers_the_question():
    src = inspect.getsource(TabMeasure)
    assert src.count("chosen[0] = self.GIVE_UP_PENDING") == 5, (
        "not every failure window defers its Give Up")
    # …and every one of them resolves it after the window has closed.
    assert src.count("self._resolve_give_up(chosen[0])") >= 5


def test_the_pending_marker_is_never_sent_to_the_instrument():
    """If a path forgot to resolve it, the sentinel would go out as keystrokes."""
    assert TabMeasure.GIVE_UP_PENDING.startswith("__")
    src = inspect.getsource(TabMeasure._resolve_give_up)
    assert "self._give_up_or_save()" in src


# ---- and the ending is answered only once -------------------------------
def test_giving_up_silences_the_readers_own_report(manager):
    """Knut's first case: after Give Up, the reader says it was interrupted —
    which is the ending the user just chose, not news."""
    seen = []
    manager.strip_interrupted.connect(lambda: seen.append(1))

    manager.mark_ending_answered()
    _feed(manager, '{"event":"strip_interrupted"}')
    assert seen == [], "a second window opened about an ending already answered"


def test_an_interruption_the_user_did_not_choose_still_asks(manager):
    """The window still exists for what it was written for: the reader stopping
    on its own, with no ending answered."""
    seen = []
    manager.strip_interrupted.connect(lambda: seen.append(1))
    _feed(manager, '{"event":"strip_interrupted"}')
    assert seen == [1]


def test_a_new_session_forgets_the_previous_ending(manager):
    """Otherwise the first interruption of the next measurement is swallowed."""
    seen = []
    manager.strip_interrupted.connect(lambda: seen.append(1))
    manager.mark_ending_answered()
    _feed(manager, '{"event":"session_start","strips":[]}')
    _feed(manager, '{"event":"strip_interrupted"}')
    assert seen == [1], "the flag leaked into the next session"


def test_the_resolver_marks_the_ending_for_both_endings():
    """Save and discard both stop the session, so both must silence the report;
    "keep measuring" must NOT, because the session continues."""
    src = inspect.getsource(TabMeasure._resolve_give_up)
    assert 'answer in ("\\x1b", self.END_SAVE)' in src
    assert "mark_ending_answered" in src


# ---- the instrument that never came up ----------------------------------
def test_a_startup_failure_reaches_the_user_on_either_reader(manager):
    """Knut, beta.141: *"Initialising instrument failed with message
    'Communications failure' … this message did not pop up with a window
    message, only in log window."*

    The window has existed since #130; its trigger lived only in the stock
    parser, so in engine mode the failure reached the log and nothing else.
    """
    seen = []
    manager.inst_init_failed.connect(seen.append)
    _feed(manager, "Initialising instrument failed with message "
                   "'Communications failure' (Communications failure)")
    assert seen == ["Communications failure"], (
        "the engine reader still swallows a startup failure")


def test_a_comms_failure_reaches_the_user_too(manager):
    seen = []
    manager.coms_init_failed.connect(seen.append)
    _feed(manager, "Установка... ")          # noise first, to prove it filters
    src = inspect.getsource(MeasureManager._check_startup_failures)
    assert "coms_init_failed" in src and "inst_init_failed" in src


def test_both_parsers_use_the_same_checker():
    """So which reader is running can never decide whether the user is told."""
    src = inspect.getsource(MeasureManager)
    assert src.count("self._check_startup_failures(line)") == 2

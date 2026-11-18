"""Final fix round, M-1: every table test is also a walk through its questions. The job's motion
guard refuses a movement line while a hands-off confirmation is owed after an answered question
(``job.HANDS_OFF_BREACHES``); a test in which that ever happened fails here, whatever it asserted
itself. A test that plants the breach on purpose clears the list itself.

The job module is never imported here (some tests check what is imported): only looked up."""
from __future__ import annotations

import sys

import pytest

_JOB = "workflow.i1io.table.job"
_WIN = "ui.i1io_table_window"


@pytest.fixture(autouse=True)
def _no_move_without_the_hands_off_confirmation():
    mod = sys.modules.get(_JOB)
    if mod is not None:
        mod.HANDS_OFF_BREACHES.clear()
    yield
    mod = sys.modules.get(_JOB)
    if mod is None:
        return
    breaches = list(mod.HANDS_OFF_BREACHES)
    mod.HANDS_OFF_BREACHES.clear()
    assert not breaches, ("a movement was refused because it followed an answered question "
                          f"without the hands-off confirmation: {breaches}")


@pytest.fixture(autouse=True)
def _hands_off_answers_pressable_at_once(request):
    """Review 14, S-1: the window holds an answer that IS the hands-off confirmation for
    ``HANDS_OFF_READY_MS`` (0.6 s) after its page is shown. The scripted person of these walks
    presses the moment a page is there, which stands for a person who waited: the walks check
    WHICH answers lead to a move, not how fast a person clicks. A test about the hold itself
    asks for ``hands_off_hold`` and gets the shipped 0.6 s. (Looked up, never imported here.)"""
    mod = sys.modules.get(_WIN)
    if mod is None or "hands_off_hold" in request.fixturenames \
            or not hasattr(mod, "HANDS_OFF_READY_MS"):
        yield
        return
    old = mod.HANDS_OFF_READY_MS
    mod.HANDS_OFF_READY_MS = 0
    try:
        yield
    finally:
        mod.HANDS_OFF_READY_MS = old


@pytest.fixture
def hands_off_hold():
    """The shipped hold of the hands-off answers (review 14, S-1)."""
    import importlib
    mod = importlib.import_module(_WIN)
    assert mod.HANDS_OFF_READY_MS == 600
    return mod.HANDS_OFF_READY_MS

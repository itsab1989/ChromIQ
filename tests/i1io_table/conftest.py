"""Final fix round, M-1: every table test is also a walk through its questions. The job's motion
guard refuses a movement line while a hands-off confirmation is owed after an answered question
(``job.HANDS_OFF_BREACHES``); a test in which that ever happened fails here, whatever it asserted
itself. A test that plants the breach on purpose clears the list itself.

The job module is never imported here (some tests check what is imported): only looked up."""
from __future__ import annotations

import sys

import pytest

_JOB = "workflow.i1io.table.job"


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

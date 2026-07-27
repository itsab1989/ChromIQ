"""#130 (Knut, 2026-07-27): a failed strip must raise exactly one window.

The engine prints ArgyllCMS's own "Strip read failed …" line *and* reports the
failure as a JSON event. Both were parsed, so the failure was raised twice: the
user answered the first window, and the second one — which nobody saw answered —
carried its own default and replaced that answer. Knut pressed
"Save Partial & Quit" and the measurement simply carried on retrying, which is
exactly what his log shows.
"""
from __future__ import annotations

import json

import pytest

from workflow.measure_manager import MeasureManager


class _Runner:
    """The little of ArgyllRunner a manager needs to be constructed."""
    def __init__(self):
        self.sent = []

    def write_stdin(self, data):
        self.sent.append(data)

    def __getattr__(self, _name):          # any other call is a no-op signal
        return lambda *a, **k: None


@pytest.fixture
def manager(qapp=None):
    return MeasureManager(_Runner())


CONSOLE = "Strip read failed due to misread (Swipe didn't start and end on the media)"
EVENT = json.dumps({"event": "error", "kind": "misread",
                    "detail": "Swipe didn't start and end on the media"})


def _seen(manager):
    got = []
    manager.strip_error.connect(got.append)
    return got


def test_the_printed_line_is_ignored_while_the_engine_runs(manager):
    """The engine reports the failure as a JSON event; the line it also prints
    must not raise it a second time. Two windows meant the second one's default
    answer replaced whatever the user had chosen in the first."""
    manager._engine_active = True
    got = _seen(manager)

    manager._handle_line(CONSOLE, lambda _s: None)

    assert got == [], got


def test_stock_chartread_still_raises_it_from_the_printed_line(manager):
    """It is the only source there, so it must keep working."""
    manager._engine_active = False
    got = _seen(manager)

    manager._handle_line(CONSOLE, lambda _s: None)

    assert got == ["Swipe didn't start and end on the media"], got


def test_a_communication_failure_still_reaches_the_user_on_stock(manager):
    manager._engine_active = False
    got = _seen(manager)

    manager._handle_line("Strip read failed due to communication problem",
                         lambda _s: None)

    assert got == ["communication problem"], got


def test_the_printed_wording_still_classifies_correctly_on_stock(manager):
    """On stock chartread the printed line is the only source, and its wording
    is what decides slow-down versus strip-failed."""
    manager._engine_active = False
    got = _seen(manager)

    manager._handle_line(
        "Strip read failed due to misread "
        "(Not enough samples per patch - Slow Down!)", lambda _s: None)

    from core.measure_pace import failure_kind
    assert got and failure_kind(got[0]) == "too_fast", got

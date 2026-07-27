"""#131 (Knut, 2026-07-27): Skip Strip must advance, and Retry must not be timed.

Both come from his log of the same session.

**Skip Strip.** After a failed strip the engine sits at its retry prompt, not at
a console strip menu. Skip was implemented as "acknowledge, then send 'n' when
the menu appears" — so the acknowledgement put the engine back on the *same*
strip and the queued key waited for a prompt that never arrives in that form.
His log shows it exactly: `send_key CR` at 21:21:19, nothing moving, and the run
killed at 21:23:12 because there was no way forward.

**Retry timing.** The swipe clock was only cleared when the pace hint was
enabled. With the hint off it survived the failure, so the NEXT strip was timed
from the failed swipe — and the figure shown included however long he sat in the
failure window before pressing Retry.
"""
from __future__ import annotations

import json

import pytest

from workflow.measure_manager import MeasureManager


class _Runner:
    def __init__(self):
        self.stdin = []

    def write_stdin(self, data):
        self.stdin.append(data)

    def __getattr__(self, _name):
        return lambda *a, **k: None


@pytest.fixture
def manager():
    return MeasureManager(_Runner())


# ---- Skip Strip -----------------------------------------------------------
# Proved against the real helper in tests/test_skip_strip_replay.py: a
# navigation command sent at the retry prompt is spent as "any other key" —
# which means RETRY — so the acknowledgement has to go first. These are the
# unit-level guards on that sequence.
def test_the_acknowledgement_goes_first(manager):
    manager._engine_active = True

    manager.send_post_retry_key("f")

    assert manager._runner.stdin == ['{"cmd": "ok"}\n']
    assert manager._pending_post_retry_key == "f", \
        "the navigation key waits for the strip menu"


def test_skip_asks_for_the_next_strip_not_the_next_unread_one(manager):
    """A strip that has just FAILED is itself still unread, so "next unread"
    lands back on the strip you are trying to leave."""
    manager._engine_active = True

    manager.skip_current_strip()

    assert manager._pending_post_retry_key == "f"


def test_stock_chartread_keeps_the_two_step(manager):
    manager._engine_active = False

    manager.send_post_retry_key("n")

    assert manager._runner.stdin == ["\r"]
    assert manager._pending_post_retry_key == "n"


def test_the_queued_key_is_sent_when_the_menu_appears(manager):
    """The second half of the two-step, on the engine path."""
    manager._engine_active = True
    manager.send_post_retry_key("f")
    manager._runner.stdin.clear()

    manager._handle_engine_line(
        json.dumps({"event": "strip_ready", "strip": "A"}), lambda _s: None)

    assert manager._runner.stdin == ['{"cmd": "forward"}\n']
    assert manager._pending_post_retry_key is None


# ---- the swipe clock -------------------------------------------------------
class _Tab:
    """Just enough of the tab for the clock rule."""
    from ui.tabs.tab_measure import TabMeasure
    _report_failed_strip_pace = TabMeasure._report_failed_strip_pace

    def __init__(self, hint_enabled):
        self._scan_started_at = 1234.5
        self._settings = {"pace_hint_enabled": hint_enabled}
        self._last_strip_patches = 15

    class _S(dict):
        def get(self, k, d=None):
            return dict.get(self, k, d)


@pytest.mark.parametrize("hint_enabled", [True, False])
def test_a_failed_strip_always_consumes_the_clock(hint_enabled):
    """With the hint off it used to survive, and the next strip inherited it —
    which is why a Retry showed a reading time that grew with the wait."""
    tab = _Tab(hint_enabled)
    tab._settings = _Tab._S({"pace_hint_enabled": hint_enabled})
    try:
        tab._report_failed_strip_pace("misread")
    except Exception:      # noqa: BLE001 — the rest of the slot needs a real tab
        pass
    assert tab._scan_started_at is None, \
        "the failed swipe's start time must not be left for the next strip"


def test_the_clock_is_cleared_before_the_preference_is_read():
    """Source-level, because that ordering IS the fix."""
    import inspect

    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._report_failed_strip_pace)
    clear_at = src.index("self._scan_started_at = None")
    pref_at = src.index('pace_hint_enabled')
    assert clear_at < pref_at, \
        "the clock must be consumed whatever the preference says"

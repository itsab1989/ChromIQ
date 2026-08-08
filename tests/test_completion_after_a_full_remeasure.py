"""Re-measuring a whole chart is a completion, even if it was complete before.

Basti, 2026-08-08: he read printer-test end to end — every strip A–F, from zero,
no `-r` — and got no window offering Build Profile. His log shows the engine did
its part:

    {"event":"strip_ready","strip":"F","read":true,"all_done":true}
    Ready to read strip pass F (!! ALL ROWS READ !!)

`_all_done_is_news` suppressed it because `_chart_was_complete` was true: the
chart already had a finished `.ti3` from an earlier session, and the flag is
judged once, at the start. So a chart that has ever been measured completely was
silenced for ever after, however much of it you read.

The suppression itself is Knut's (#131) and is right for what it was written
for — its own words are *"re-reading ONE strip does not complete anything"*.
This narrows it to that: a full re-read announces, a touch-up stays quiet. It
must not weaken his beta.150 fix either, where the chart's completeness has to
come from the `.ti3` because the strip flags are per strip while the gap can be
per patch.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measure_manager import MeasureManager           # noqa: E402


class _M:
    """Only the state the two predicates read."""
    _all_done_is_news = MeasureManager._all_done_is_news
    _read_the_whole_chart_this_session = \
        MeasureManager._read_the_whole_chart_this_session

    def __init__(self, chart_complete, strips, read_now, resume=False):
        self._chart_was_complete = chart_complete
        self._session_strips = [{"strip": s} for s in strips]
        self._strips_read_this_session = set(read_now)
        self._read_something = bool(read_now)
        self._is_resume = resume


ALL = ["A", "B", "C", "D", "E", "F"]


def test_a_full_re_read_of_a_finished_chart_announces():
    """Basti's case: every strip read again, chart was already complete."""
    m = _M(chart_complete=True, strips=ALL, read_now=ALL)
    assert m._all_done_is_news() is True, (
        "a complete re-measurement of the chart was not announced, so nothing "
        "offered to take the user on to Build Profile"
    )


def test_re_reading_one_strip_of_a_finished_chart_stays_quiet():
    """Knut's case (#131) must not regress — this is why the rule exists."""
    m = _M(chart_complete=True, strips=ALL, read_now=["C"])
    assert m._all_done_is_news() is False


def test_a_partial_re_read_stays_quiet():
    """Most of the chart is still not all of it."""
    m = _M(chart_complete=True, strips=ALL, read_now=ALL[:-1])
    assert m._all_done_is_news() is False


def test_finishing_an_unfinished_chart_still_announces():
    """The ordinary path is untouched: the chart was not complete beforehand."""
    m = _M(chart_complete=False, strips=ALL, read_now=["F"])
    assert m._all_done_is_news() is True


def test_no_session_map_does_not_invent_a_completion():
    """With no strip list there is nothing to compare against — stay quiet."""
    m = _M(chart_complete=True, strips=[], read_now=["A"])
    assert m._all_done_is_news() is False


def test_blank_strip_names_are_ignored():
    """A malformed session map must not make `wanted` trivially satisfied."""
    m = _M(chart_complete=True, strips=["A", "", "  "], read_now=["A"])
    assert m._all_done_is_news() is True     # only "A" is a real strip, and it was read


def test_completeness_still_comes_from_the_ti3():
    """Knut's beta.150 fix stays: the flags are per strip, the gap per patch."""
    import inspect

    src = inspect.getsource(MeasureManager._measurement_was_complete)
    assert "classify(" in src and "Ti3State.COMPLETE" in src, (
        "the chart's completeness is no longer judged from its .ti3"
    )

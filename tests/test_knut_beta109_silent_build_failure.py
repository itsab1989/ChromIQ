"""#130 (Knut, 2026-07-30): a failed chart build must not be silent.

*"All the messages given only comes in the log window, not as popups for the
user, which should be done for all actions performed in the user interface."* —
after Restore Used Chart his preview went empty and the only trace was two lines
in the log:

    printtarg: Error - Input file doesn't contain two or three tables
    [ERROR] Chart generation failed.

ChromIQ does have a window for a failed build, but it only appears for errors a
pattern recognises. His message was not one of them, so `primary_failure()`
returned None and nothing was shown. An unrecognised error is still an error, and
the user is still owed the tool's own words.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.chart_creator import ChartCreator          # noqa: E402


def _creator():
    c = ChartCreator.__new__(ChartCreator)
    c._matched_errors = []
    c._matched_warnings = []
    c._raw_errors = []
    return c


def test_his_printtarg_message_is_remembered(qapp=None):
    """The exact line from his log."""
    c = _creator()
    c._scan_line("printtarg",
                 "printtarg: Error - Input file doesn't contain two or three tables")
    assert c.primary_failure() is None, "no friendly pattern knows this one"
    tool, said = c.unmatched_failure()
    assert tool == "printtarg"
    assert "two or three tables" in said


def test_a_recognised_error_still_wins():
    """The fallback must not displace the friendly message when there is one."""
    c = _creator()
    c._matched_errors.append(("targen", "some_key", "A friendly explanation."))
    c._raw_errors.append(("targen", "targen: Error - raw"))
    assert c.unmatched_failure() is None
    assert c.primary_failure()[2] == "A friendly explanation."


def test_ordinary_output_is_not_treated_as_a_failure():
    c = _creator()
    for line in ("printtarg: laying out patches", "Wrote 4 pages", ""):
        c._scan_line("printtarg", line)
    assert c.unmatched_failure() is None


def test_the_first_error_is_the_one_reported():
    """Later noise must not replace the message that explains the failure."""
    c = _creator()
    c._scan_line("printtarg", "printtarg: Error - Input file doesn't contain two or three tables")
    c._scan_line("printtarg", "printtarg: Error - giving up")
    assert "two or three tables" in c.unmatched_failure()[1]


def test_the_window_appears_when_nothing_was_recognised():
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._on_generate_finished)
    assert "unmatched_failure()" in src
    assert "The chart could not be built" in src
    # …and it says the user's files are safe, which is the first thing they ask
    assert "untouched" in src
    assert "Restore Used Chart" in src, \
        "it must connect the failure to the restore he had just done"


def test_the_failure_window_is_not_shown_twice():
    """A recognised failure already has its own window; only one may appear."""
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._on_generate_finished)
    assert "if failure is not None:" in src
    assert src.index("if failure is not None:") < src.index("unmatched_failure()")
    # An elif, not an else: a build that reported nothing at all (a cancel, or a
    # caller driving this handler directly) has nothing to show, and a modal
    # there once kept the whole test suite waiting on a window nobody could
    # dismiss.
    assert "elif self._creator.unmatched_failure() is not None:" in src

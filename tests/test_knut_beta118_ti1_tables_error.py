"""#130 (Knut, 2026-08-01): printtarg refused a chart with

    *"printtarg error: input file doesn't contain two or three tables"*

and all ChromIQ could do was repeat it. The sentence is accurate and useless:
"a .ti1 with the wrong number of tables" is not something most people have a
mental model of, and nothing in it says what to do next.

What it actually means: the ``.ti1`` holds only the list of colours, without the
two further sections printtarg reads to group patches into strips — which is
what a ``.ti1`` exported by another program usually looks like. The ChromIQ
layout engine does not need them, so turning it on is a one-click way past it.

Also covered here: the sidecar drift that made the rebuild guard cry wolf while
this was being reproduced.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.chart_creator import (ChartCreator,               # noqa: E402
                                    _PRINTTARG_ERROR_PATTERNS)


def _match(line: str):
    for pattern, key, fmt in _PRINTTARG_ERROR_PATTERNS:
        m = pattern.search(line)
        if m:
            return key, fmt.format(*m.groups())
    return None, None


def test_the_error_is_recognised():
    """Unrecognised, it fell through to the window that just quotes the tool."""
    key, _ = _match("printtarg: Error - Input file doesn't contain two or "
                    "three tables")
    assert key == "ti1_wrong_tables"


def test_it_is_recognised_however_the_tool_capitalises_it():
    for line in ("Input file doesn't contain two or three tables",
                 "input file doesn't contain two or three tables",
                 "Error - Input file doesn't contain two or three tables"):
        assert _match(line)[0] == "ti1_wrong_tables", line


def test_the_message_says_what_to_do():
    _, msg = _match("Input file doesn't contain two or three tables")
    assert "ChromIQ layout engine" in msg, \
        "the one-click way past this must be named"
    assert "Generate Chart" in msg


def test_the_message_reassures_about_the_measurement():
    """This appears most often right after Restore Used Chart, where the first
    fear is that the run's readings have been damaged."""
    _, msg = _match("Input file doesn't contain two or three tables")
    assert "measurement" in msg.lower()
    assert "as they were" in msg.lower() or "untouched" in msg.lower()


def test_the_message_avoids_the_unexplained_jargon():
    """"two or three tables" is the phrasing that told Knut nothing; if it is
    repeated it must be explained, not quoted."""
    _, msg = _match("Input file doesn't contain two or three tables")
    assert "two or three tables" not in msg
    assert "only the list of colours" in msg


def test_a_recognised_error_beats_the_raw_fallback():
    """primary_failure() is checked first, so recognising the line is what
    replaces the tool's own words with the explanation."""
    c = ChartCreator.__new__(ChartCreator)
    c._matched_errors = []
    c._matched_warnings = []
    c._raw_errors = []
    ChartCreator._scan_line(
        c, "printtarg", "Error - Input file doesn't contain two or three tables")
    assert c.primary_failure() is not None
    assert c.primary_failure()[1] == "ti1_wrong_tables"
    assert c.unmatched_failure() is None, \
        "a recognised error must not also surface as an unrecognised one"


def test_other_printtarg_errors_still_match_their_own_patterns():
    """The new pattern is inserted into a shared list — a greedy regex here
    would silently capture messages that have their own explanations."""
    assert _match("Not enough width for even one row")[0] == "paper_too_narrow"
    assert _match("Unsupported instrument type")[0] == "unsupported_instrument"
    assert _match("Paper size not long enough for a single patch per row")[0] \
        == "paper_too_short_row"


def test_an_unrelated_line_matches_nothing():
    assert _match("printtarg: writing page 1 of 3")[0] is None

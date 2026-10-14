"""4.3.5 beta 5, Knut #182 6168612728 (R3): a patch the neighbour check had
made red, read again and no longer suspected, turns GREEN.

His B14, run 5's verification, resumed: from the file it stood out from its
four most similar patches by ΔE*ab 5.04 at a neighbour limit of 5.00 (red).
He read strip B again; it stood out by 4.78, the red outline went, and no
green came. The two readings were ΔE 0.3 apart, and the code asked for "a
clearly different colour" (more than the Same-reading tolerance) before it
called the re-read a correction. That condition was a build note of 10.10
nobody confirmed. The CONFIRMED rule (Knut 5984277558) is: red by the limit or
by the neighbour check, whose re-read is no longer flagged by either, is
outlined green; and Knut's (d) (6045500910) already makes a re-read under the
limit green whatever its colour. The neighbour check now follows the same (d).

Knut's own numbers: tests below use his two readings of B14 (his 07 log,
13:59:52 and 14:22:33), converted to Lab D50 the way the Measure tab does.
"""
from __future__ import annotations

from workflow import patch_flags as pf
from workflow.icc_info import xyz_to_lab

EXP = (40.2, 40.4, 10.7)          # B14's expected colour on his card
FIRST = tuple(xyz_to_lab((27.9845, 19.1384, 7.167)))     # 13:59:52, red
AGAIN = tuple(xyz_to_lab((27.6788, 18.906, 7.0855)))     # 14:22:33, re-read
MISREAD = (20.0, 60.0, -40.0)


def _j(judge, meas, flagged, *, live=True, suspect=False):
    return judge.judge("B14", EXP, meas, pf._norm(pf._sub(meas, EXP)),
                       flagged, live=live, strip="B", reread_only=suspect,
                       limit=7.0)


def test_his_two_readings_are_the_same_colour():
    assert pf._norm(pf._sub(FIRST, AGAIN)) < pf.SAME_READING_DE


def test_b14_from_the_file_then_read_again_live_is_green():
    """Exactly his session: the red reading comes from the file (resumed)."""
    judge = pf.FlagJudge()
    assert _j(judge, FIRST, True, live=False, suspect=True).flag is pf.FLAG_RED
    v = _j(judge, AGAIN, False)
    assert v.flag == pf.FLAG_CORRECTED
    assert v.corrected_by == "neighbour"
    assert judge.export()["B14"]["kind"] == "corrected"


def test_the_same_within_one_session_is_green_too():
    judge = pf.FlagJudge()
    _j(judge, FIRST, True, suspect=True)
    assert _j(judge, AGAIN, False).flag == pf.FLAG_CORRECTED


def test_a_repaint_alone_still_never_makes_green():
    """No re-read, only later strips moving the neighbour check: no green
    (10.10, "nothing was read again")."""
    judge = pf.FlagJudge()
    _j(judge, FIRST, True, live=False, suspect=True)
    assert _j(judge, FIRST, False, live=False).flag is pf.FLAG_NONE
    judge = pf.FlagJudge()
    _j(judge, FIRST, True, suspect=True)
    assert _j(judge, FIRST, False, live=False).flag is pf.FLAG_NONE


def test_the_limit_rule_is_unchanged_a_raised_limit_is_not_a_correction():
    """Red by the LIMIT, read again with the same colour after the limit was
    raised: the reading was right, so it is not green (10.10, unchanged)."""
    judge = pf.FlagJudge()
    judge.judge("X1", EXP, MISREAD, 9.0, True, strip="X", limit=8.0)
    v = judge.judge("X1", EXP, MISREAD, 9.0, False, strip="X", limit=10.0)
    assert v.flag is not pf.FLAG_CORRECTED


def test_a_reread_still_suspected_is_not_green_yet():
    judge = pf.FlagJudge()
    _j(judge, FIRST, True, live=False, suspect=True)
    assert _j(judge, AGAIN, True, suspect=True).flag != pf.FLAG_CORRECTED

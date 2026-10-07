"""Beta-12 review: an unsettled patch (Knut, #182 6045500910, (a)/(c)) is
judged again against the limit as it is NOW when it is painted from the file.

Found in review: a measurement left with J28 unsettled at limit 95 (120, then
150) and opened again after the limit was raised to 130 showed the card "both
are past your limit 130.0" although the first reading (120) is not past it.
Under the rules at 130 the first reading was never red, so the patch is plain
red, not "the readings do not agree".
"""
from __future__ import annotations

from workflow import patch_flags as pf

EXP = (50.0, 0.0, 0.0)


def _j(judge, de, *, limit=95.0, live=True):
    meas = (50.0, float(de), 0.0)
    d = pf._norm(pf._sub(meas, EXP))
    return judge.judge("J28", EXP, meas, d, d >= limit, live=live,
                       strip="J", limit=limit)


def _unsettled_memory():
    judge = pf.FlagJudge()
    _j(judge, 120)
    assert _j(judge, 150).unsettled == (120.0,)
    return judge.export()


def test_opened_under_the_same_limit_it_is_still_unsettled():
    judge = pf.FlagJudge()
    judge.load(_unsettled_memory())
    v = _j(judge, 150, live=False)
    assert v.flag is pf.FLAG_RED and v.unsettled == (120.0,)


def test_opened_under_a_raised_limit_it_is_plain_red():
    judge = pf.FlagJudge()
    judge.load(_unsettled_memory())
    v = _j(judge, 150, limit=130.0, live=False)
    assert v.flag is pf.FLAG_RED
    assert v.unsettled == ()


def test_a_repaint_after_the_limit_was_raised_is_plain_red():
    judge = pf.FlagJudge()
    _j(judge, 120)
    _j(judge, 150)
    v = _j(judge, 150, limit=130.0, live=False)
    assert v.flag is pf.FLAG_RED and v.unsettled == ()


def test_only_the_readings_still_past_the_limit_are_listed():
    judge = pf.FlagJudge()
    _j(judge, 120)
    _j(judge, 150)
    assert _j(judge, 200).unsettled == (120.0, 150.0)
    v = _j(judge, 200, limit=130.0, live=False)
    assert v.flag is pf.FLAG_RED and v.unsettled == (150.0,)

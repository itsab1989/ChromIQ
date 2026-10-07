"""Beta 12: Knut's re-read rules for a patch red by the limit (#182
6045500910, answer 2).

    1st reading past the limit: red.
    (a) 2nd higher, not the same: red.
    (b) 2nd the "same" (within ΔE 3, SAME_READING_DE): yellow.
    (c) 2nd lower, still past the limit, not the same: red.
    (d) any re-read under the limit after one or more readings past it: green.
    In (a)/(c) the card says the readings were not similar and both past the
    limit, and that another reading is needed. A 3rd reading the same as ANY
    earlier reading is yellow with the normal confirmation (Basti's J28: it
    matched the first reading, not the misread in between).

Also how the rules sit with the earlier ones: the neighbour check (only a
re-read clears it, 5984174575), the pending green of beta 12's B1, similar
patches and a learned colour range (an unsettled patch is neither vouched for
nor a voucher), and a repaint (never a reading).
"""
from __future__ import annotations

from workflow import measurement_messages as M
from workflow import patch_flags as pf

LIMIT = 95.0
EXP = (50.0, 0.0, 0.0)


def _lab(de, b=0.0):
    """A measured colour ΔE*ab *de* from EXP (along a*), *b* sideways."""
    return (50.0, float(de), float(b))


def _j(judge, de, *, b=0.0, live=True, suspect=False, flagged=None,
       loc="J28", strip="J", limit=LIMIT):
    meas = _lab(de, b)
    d = pf._norm(pf._sub(meas, EXP))
    if flagged is None:
        flagged = d >= LIMIT or suspect
    return judge.judge(loc, EXP, meas, d, flagged, live=live, strip=strip,
                       reread_only=suspect and flagged, limit=limit)


def test_first_reading_past_the_limit_is_red():
    v = _j(pf.FlagJudge(), 120)
    assert v.flag is pf.FLAG_RED and v.unsettled == ()


def test_a_second_higher_and_not_the_same_stays_red_unsettled():
    judge = pf.FlagJudge()
    _j(judge, 120)
    v = _j(judge, 150)                                    # (a)
    assert v.flag is pf.FLAG_RED
    assert v.unsettled == (120.0,)


def test_b_second_the_same_is_yellow():
    judge = pf.FlagJudge()
    _j(judge, 120)
    v = _j(judge, 122)                                    # (b): within ΔE 3
    assert v.flag == pf.FLAG_CONFIRMED and v.prev_de == 120.0
    assert v.unsettled == ()


def test_c_second_lower_still_past_the_limit_stays_red_unsettled():
    judge = pf.FlagJudge()
    _j(judge, 150)
    v = _j(judge, 110)                                    # (c)
    assert v.flag is pf.FLAG_RED and v.unsettled == (150.0,)


def test_d_a_reread_under_the_limit_is_green():
    judge = pf.FlagJudge()
    _j(judge, 150)
    v = _j(judge, 40)                                     # (d)
    assert v.flag == pf.FLAG_CORRECTED
    assert v.prev_de == 150.0 and v.corrected_by == "limit"


def test_d_also_after_two_readings_past_the_limit():
    judge = pf.FlagJudge()
    _j(judge, 120)
    _j(judge, 150)
    v = _j(judge, 40)
    assert v.flag == pf.FLAG_CORRECTED and v.prev_de == 150.0


def test_d_holds_even_when_the_reread_lands_close_to_the_red_reading():
    """96 then 94 at limit 95: under the limit after a reading past it is
    green (6045500910 (d)), even though the two colours are within ΔE 3.
    Before beta 12 the same colour "corrected nothing"."""
    judge = pf.FlagJudge()
    _j(judge, 96)
    v = _j(judge, 94)
    assert v.flag == pf.FLAG_CORRECTED and v.prev_de == 96.0


def test_a_raised_limit_and_the_same_colour_is_still_not_green():
    """Kept from beta 11: the limit moved, nothing was corrected. The earlier
    reading is not past the CURRENT limit, so (d) does not apply."""
    judge = pf.FlagJudge()
    _j(judge, 96)
    _j(judge, 96, live=False, flagged=False, limit=100.0)  # repaint at 100
    v = _j(judge, 96.5, flagged=False, limit=100.0)
    assert v.flag is pf.FLAG_NONE


def test_then_a_third_the_same_as_the_first_is_yellow():
    """Knut: "If first measurement error, then (a), then third measurement
    same as first measurement=yellow."""
    judge = pf.FlagJudge()
    _j(judge, 120)
    _j(judge, 150)                                        # (a) red
    v = _j(judge, 121)
    assert v.flag == pf.FLAG_CONFIRMED and v.prev_de == 120.0
    assert v.unsettled == ()


def test_a_third_the_same_as_the_second_is_yellow():
    judge = pf.FlagJudge()
    _j(judge, 120)
    _j(judge, 150)
    v = _j(judge, 151)
    assert v.flag == pf.FLAG_CONFIRMED and v.prev_de == 150.0


def test_a_third_like_neither_stays_red_and_lists_both():
    judge = pf.FlagJudge()
    _j(judge, 120)
    _j(judge, 150)
    v = _j(judge, 200)
    assert v.flag is pf.FLAG_RED and v.unsettled == (120.0, 150.0)


def test_without_the_limit_the_older_rules_hold():
    """A caller that does not give the limit gets beta 11's behaviour, but a
    match with any earlier reading still confirms."""
    judge = pf.FlagJudge()
    _j(judge, 120, limit=None)
    v = _j(judge, 150, limit=None)
    assert v.flag is pf.FLAG_RED and v.unsettled == ()
    assert _j(judge, 121, limit=None).flag == pf.FLAG_CONFIRMED


def test_a_repaint_is_not_a_reading():
    judge = pf.FlagJudge()
    _j(judge, 120)
    _j(judge, 150)
    v = _j(judge, 150, live=False)
    assert v.flag is pf.FLAG_RED and v.unsettled == (120.0,)
    # The repaint did not count as a reading that matches the second.
    judge = pf.FlagJudge()
    _j(judge, 120, live=False)
    assert _j(judge, 120, live=False).flag is pf.FLAG_RED


def test_a_file_reading_is_the_earlier_reading_of_a_resumed_session():
    judge = pf.FlagJudge()
    _j(judge, 120, live=False)                 # painted from the file
    assert _j(judge, 121).flag == pf.FLAG_CONFIRMED


# ---- with the neighbour check (Knut 5984174575: only a re-read clears it) ----

def test_bastis_j28_the_misread_in_between():
    """J28 (2026-10-05): a neighbour suspect at ΔE 69.5, misread at 150.4,
    read again at 69.7 and still suspected. Yellow, confirmed by its own
    re-read with the same value as the first. When the neighbour check later
    stops suspecting it, the misread past the limit was corrected: green."""
    judge = pf.FlagJudge()
    assert _j(judge, 69.5, suspect=True).flag is pf.FLAG_RED
    v = _j(judge, 150.4, suspect=True)
    # The first reading was under the limit: not "both past the limit".
    assert v.flag is pf.FLAG_RED and v.unsettled == ()
    v = _j(judge, 69.7, suspect=True)
    assert v.flag == pf.FLAG_CONFIRMED and v.prev_de == 69.5
    v = _j(judge, 69.7, live=False, flagged=False)
    assert v.flag == pf.FLAG_CORRECTED
    assert v.prev_de == 150.4 and v.corrected_by == "limit"


def test_unsettled_and_suspected_needs_its_own_reread_too():
    judge = pf.FlagJudge()
    _j(judge, 120, suspect=True)
    v = _j(judge, 150, suspect=True)
    assert v.flag is pf.FLAG_RED and v.reread_only and v.unsettled == (120.0,)


def test_under_the_limit_but_suspected_turns_green_when_cleared():
    judge = pf.FlagJudge()
    _j(judge, 150)
    assert _j(judge, 40, suspect=True).flag is pf.FLAG_RED
    v = _j(judge, 40, live=False, flagged=False)
    assert v.flag == pf.FLAG_CORRECTED and v.prev_de == 150.0


# ---- similar patches and a learned range ----------------------------------

def test_an_unsettled_patch_is_not_vouched_for_by_similar_patches():
    """Two flagged patches of different strips, alike, confirm each other
    (5979886227). An unsettled patch does not: one of its readings is a
    misread, so its last one proves nothing, either way."""
    judge = pf.FlagJudge()
    _j(judge, 120, loc="A1", strip="A")
    _j(judge, 150, loc="A1", strip="A")                   # unsettled
    v = _j(judge, 150, loc="B1", strip="B")               # alike, other strip
    assert v.flag is pf.FLAG_RED
    assert judge.rejudge().get("A1") is None              # still unsettled red
    assert judge._verdicts["A1"].unsettled == (120.0,)
    # Once A1 settles (read the same as one of its readings) they are peers.
    _j(judge, 151, loc="A1", strip="A")
    assert judge._verdicts["A1"].flag == pf.FLAG_CONFIRMED
    judge.rejudge()
    assert judge._verdicts["B1"].flag == pf.FLAG_CONFIRMED


def test_an_unsettled_patch_is_not_yellow_by_a_learned_range():
    judge = pf.FlagJudge()
    # Three confirmed patches of one range, all off the same way.
    for loc, strip in (("C1", "C"), ("D1", "D"), ("E1", "E")):
        _j(judge, 120, loc=loc, strip=strip)
        _j(judge, 120, loc=loc, strip=strip)
    rng = judge.range_of("F1", EXP)
    assert judge.range_learned(rng)
    _j(judge, 300, loc="F1", strip="F")
    v = _j(judge, 130, loc="F1", strip="F")
    # Its last reading IS like the confirmed patches (the range would vouch
    # for it), but its two readings disagree: red until one is matched.
    assert judge._match(rng, EXP, pf._sub(_lab(130), EXP), None)[0] is not None
    assert v.flag is pf.FLAG_RED and v.unsettled == (300.0,)


# ---- the card ----------------------------------------------------------------

def test_the_words_wait_in_m_proposed():
    m = M.CATALOGUE["M-PATCH-UNSETTLED"]
    assert not m.approved
    for line in (M._CARD_UNSETTLED_HEAD, M._CARD_UNSETTLED_TWO_1,
                 M._CARD_UNSETTLED_3, M._CARD_UNSETTLED_4):
        assert "—" not in line


def _card_lines(qapp, info):
    from PyQt6.QtWidgets import QWidget
    from ui.tiff_preview import _PatchInfoTile
    host = QWidget()
    tile = _PatchInfoTile(host)
    tile.set_content(info, "both")
    return [t for _sw, t in tile._rows]


def _info(**kw):
    base = {"loc": "J28", "exp_rgb": (128, 128, 128),
            "meas_rgb": (120, 120, 120), "exp_lab": (50.0, 0.0, 0.0),
            "meas_lab": (50.0, 150.0, 0.0), "de": 150.4, "warn": True,
            "warn_de": 95.0, "fenced": False, "flag": "", "accurate": False}
    base.update(kw)
    return base


def test_the_card_of_a_and_c_says_the_readings_disagree(qapp):
    lines = _card_lines(qapp, _info(unsettled=[120.3]))
    assert M._CARD_UNSETTLED_HEAD in lines
    assert M._CARD_UNSETTLED_DE.format(de="150.4", prevs="120.3") in lines
    assert M._CARD_UNSETTLED_TWO_1 in lines
    assert M._CARD_UNSETTLED_TWO_2.format(limit="95.0") in lines
    assert M._CARD_UNSETTLED_3 in lines and M._CARD_UNSETTLED_4 in lines
    # Not the plain red card's "a large difference".
    assert "Red outline: a large difference" not in lines


def test_the_card_after_three_disagreeing_readings(qapp):
    lines = _card_lines(qapp, _info(unsettled=[120.3, 200.0]))
    assert M._CARD_UNSETTLED_MANY_1.format(n=3) in lines
    assert M._CARD_UNSETTLED_MANY_2.format(limit="95.0") in lines
    assert M._CARD_UNSETTLED_DE.format(de="150.4",
                                       prevs="120.3, 200.0") in lines


def test_a_plain_red_card_is_unchanged(qapp):
    lines = _card_lines(qapp, _info(unsettled=[]))
    assert "Red outline: a large difference" in lines
    assert M._CARD_UNSETTLED_HEAD not in lines


# ---- kept with the measurement (10.7) ----------------------------------------

def test_unsettled_is_kept_with_the_measurement_and_red_when_opened():
    """Drawn again from the file (a new judge, the stored memory, a repaint),
    an unsettled patch stays red, and a re-read in a resumed session that
    matches its FIRST reading is yellow."""
    from workflow import confirmed_patches as cp
    judge = pf.FlagJudge()
    _j(judge, 120)
    _j(judge, 150)
    stored = judge.export()
    assert stored["J28"]["kind"] == "unsettled"
    clean = cp._clean_entry(stored["J28"])
    assert clean["prevs"] == [120.0] and len(clean["readings"]) == 1
    # Opened later: a fresh judge, the memory, then the file's reading.
    opened = pf.FlagJudge()
    opened.load({"J28": clean})
    v = _j(opened, 150, live=False)
    assert v.flag is pf.FLAG_RED and v.unsettled == (120.0,)
    assert opened._last["J28"].unsettled          # never a similar patch
    # Resumed, read once more, the same as the first reading: yellow.
    v = _j(opened, 121)
    assert v.flag == pf.FLAG_CONFIRMED and v.prev_de == 120.0
    assert opened.export()["J28"]["kind"] == "confirmed"


def test_a_broken_unsettled_entry_is_dropped():
    from workflow import confirmed_patches as cp
    assert cp._clean_entry({"kind": "unsettled", "prevs": [],
                            "readings": []}) is None
    assert cp._clean_entry({"kind": "unsettled", "prevs": [1.0],
                            "readings": [{"de": "x"}]}) is None

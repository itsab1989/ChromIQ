"""4.3.40: the ruler check and a TURNED SHEET (pharmacist, 2026-11-15).

The direction question compares (the ruler's sign x the reader's "reversed")
with the majority of earlier strips. The swipe direction cancels out of that
product, so what it really sees is how the SHEET (or the ruler) lay under the
instrument: a tester turned his sheet and was asked about a strip saved
correctly, and in 4.3.39 one turn meant every later strip was asked.

* A: asked only when the strip's own colours cannot vouch for the saved order
  (`slipped_strip.own_row_direction`); when they do, one calm log line, the
  diagnostics file records it, and the strip votes;
* the majority is taken over the recent votes, so it follows the new way round;
* F3: a strip that got any question never votes; a re-read replaces its vote;
* F4: the log's direction line and ``direction_agrees`` use the reference the
  question uses, decided once the saving is known;
* the replay matrix of the tester's 702-patch chart: the question counts
  before (4.3.39, from the report) and after.
"""
from __future__ import annotations

import json
import math
import os
import random
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_ruler_session import _cut, _rec, _session        # noqa: E402
from workflow import slipped_strip as ss                          # noqa: E402
from workflow.ruler_session import RulerSession                   # noqa: E402

DATA = Path(__file__).parent / "data" / "ruler_turned_sheet"
D50 = (96.42, 100.0, 82.49)


# ---------------------------------------------------------------- colour
def _lab_to_xyz(lab):
    L, a, b = lab
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200

    def inv(t):
        return t ** 3 if t ** 3 > 0.008856 else (t - 16 / 116) / 7.787
    return [w * inv(t) for w, t in zip(D50, (fx, fy, fz))]


def _row(seed, n=16):
    """A row of clearly different colours (a randomised chart's strip)."""
    rng = random.Random(seed)
    return [(rng.uniform(25, 90), rng.uniform(-60, 60), rng.uniform(-60, 60))
            for _ in range(n)]


def _patches(strip, expected, measured=None, noise=1.5, seed=0):
    """A strip_read event's patches, as FILED: *measured* (Lab, default the
    expected colours plus a little noise) against *expected*."""
    rng = random.Random(seed)
    measured = measured if measured is not None else [
        (L + rng.gauss(0, noise), a + rng.gauss(0, noise),
         b + rng.gauss(0, noise)) for L, a, b in expected]
    return [{"loc": f"{strip}{i + 1}", "xyz": _lab_to_xyz(m),
             "exyz": _lab_to_xyz(e)} for i, (m, e) in enumerate(zip(measured,
                                                                     expected))]


def _read(rs, strip, sign, reversed_, *, expected=None, measured=None,
          other_question=False, gen="i1pro3"):
    """One accepted strip: the ruler saw *sign*, the reader saved it
    *reversed_*, with patches whose colours fit as saved (default)."""
    expected = expected if expected is not None else _row(sum(map(ord, strip)))
    rs.on_strip(_rec(strip, 300, gen=gen, sign=sign))
    ev = {"event": "strip_read", "strip": strip, "reversed": reversed_,
          "patches": _patches(strip, expected, measured)}
    return rs.on_strip_read(ev, other_question=other_question)


def _session3(tmp_path):
    return _session(tmp_path, gen="i1pro3")[0]


def _names(n, start=0):
    return [chr(ord("A") + start + i) for i in range(n)]


def _turned_note(summ):
    return any("the other way round compared with the strips before it" in ln
               for ln in summ["log_lines"])


# ---------------------------------------------------------------- the score
def test_the_colours_vouch_for_a_strip_saved_in_order():
    e = _row(1)
    d = ss.own_row_direction(_patches("A", e))
    assert d.verdict == "saved" and d.saved_de < 0.5 * d.turned_de


def test_the_colours_point_the_other_way_for_a_strip_saved_back_to_front():
    e = _row(2)
    d = ss.own_row_direction(_patches("A", e, measured=list(reversed(e))))
    assert d.verdict == "other"


def test_a_ramp_cannot_vouch():
    """A row that reads (almost) the same both ways: a grey ramp folded on
    itself, as on a chart in plain order."""
    half = [(30 + 5 * i, 0.0, 0.0) for i in range(8)]
    e = half + list(reversed(half))
    assert ss.own_row_direction(_patches("A", e)).verdict == "unsure"


def test_no_colours_no_vouch():
    assert ss.own_row_direction([{"loc": "A1"}] * 16) is None


# ---------------------------------------------------------------- A
def test_turned_once_mid_chart(tmp_path):
    """Eight strips one way, then the sheet turned (same swipe, so saved
    back to front by the reader, correctly): no window at all."""
    rs = _session3(tmp_path)
    for s in _names(8):
        assert not _read(rs, s, -1, False)["ask_direction"]
    after = [_read(rs, s, -1, True) for s in _names(8, 8)]
    assert not any(x["ask_direction"] for x in after)
    notes = [x for x in after if _turned_note(x)]
    assert 1 <= len(notes) <= 2 and _turned_note(after[0])
    # the majority has followed: the last strips are plain "against" lines
    assert any("moved against the reading direction" in ln
               for ln in after[-1]["log_lines"])


def test_turned_and_turned_back(tmp_path):
    rs = _session3(tmp_path)
    out = [_read(rs, s, -1, False) for s in _names(8)]
    out += [_read(rs, s, -1, True) for s in _names(4, 8)]
    out += [_read(rs, s, -1, False) for s in _names(6, 12)]
    assert not any(x["ask_direction"] for x in out)
    assert _turned_note(out[8]) and _turned_note(out[12])


def test_the_first_three_strips_turned(tmp_path):
    """The majority was learned the other way round (H2 of the report): in
    4.3.39 every later strip was asked."""
    rs = _session3(tmp_path)
    out = [_read(rs, s, -1, True) for s in _names(3)]
    out += [_read(rs, s, -1, False) for s in _names(13, 3)]
    assert not any(x["ask_direction"] for x in out)
    assert sum(_turned_note(x) for x in out) == 2


def test_one_strip_turned(tmp_path):
    rs = _session3(tmp_path)
    out = [_read(rs, s, -1, s == "F") for s in _names(10)]
    assert not any(x["ask_direction"] for x in out)
    assert [x["strip"] for x in out if _turned_note(x)] == ["F"]
    assert not out[6]["log_lines"] or not _turned_note(out[6])


def test_alternating_swipes_are_no_turn(tmp_path):
    """Read from either end, sheet as it was: the ruler's sign and the
    saving both flip, the product does not."""
    rs = _session3(tmp_path)
    out = [_read(rs, s, -1 if i % 2 == 0 else +1, i % 2 == 1)
           for i, s in enumerate(_names(12))]
    assert not any(x["ask_direction"] or _turned_note(x) for x in out)


def test_the_whole_sheet_turned_from_the_start(tmp_path):
    rs = _session3(tmp_path)
    out = [_read(rs, s, -1, True) for s in _names(12)]
    assert not any(x["ask_direction"] or _turned_note(x) for x in out)


def test_a_true_back_to_front_strip_on_a_fixed_order_chart_is_still_asked(tmp_path):
    """4.3.38's strip 9 in miniature: swiped like the others, saved back to
    front by the recognition, its colours fitting the reversed row better
    (but not by the back-to-front check's margin, so no other question)."""
    rs = _session3(tmp_path)
    for s in _names(8):
        _read(rs, s, -1, False)
    e = _row(99)
    # as saved, the readings are the true colours turned round, plus a
    # print far off its design
    meas = [(L + 4, a * 0.8, b * 0.8) for L, a, b in reversed(e)]
    summ = _read(rs, "I", -1, True, expected=e, measured=meas)
    assert summ["ask_direction"] and not _turned_note(summ)
    rs.flush()
    doc = json.loads(rs.diagnostics_path().read_text(encoding="utf-8"))
    entry = doc["strips"][-1]
    assert entry["direction_question"] is True
    assert entry["direction_colours"]["verdict"] == "other"
    assert entry["direction_confirmed_by_colours"] is False
    assert entry["voted"] is False


def test_jctays_strip_9_figures_are_asked_about():
    """The real case the question exists for, by its scores (as saved 109.9,
    turned round 53.7, mirror 113.9, 2 of 12 patches better as saved): the
    colours do not vouch."""
    assert not (109.9 <= ss.VOUCH_RATIO * 53.7)


def test_a_colour_ambiguous_turned_strip_is_still_asked(tmp_path):
    rs = _session3(tmp_path)
    for s in _names(8):
        _read(rs, s, -1, False)
    half = [(30 + 5 * i, 2.0, -2.0) for i in range(8)]
    ramp = half + list(reversed(half))
    summ = _read(rs, "I", -1, True, expected=ramp)
    assert summ["ask_direction"]
    rs.flush()
    doc = json.loads(rs.diagnostics_path().read_text(encoding="utf-8"))
    assert doc["strips"][-1]["direction_colours"]["verdict"] == "unsure"


def test_the_file_records_the_note(tmp_path):
    rs = _session3(tmp_path)
    for s in _names(6):
        _read(rs, s, -1, False)
    _read(rs, "G", -1, True)
    rs.flush()
    doc = json.loads(rs.diagnostics_path().read_text(encoding="utf-8"))
    assert doc["revision"] == 3 and doc["version"] == 1
    e = doc["strips"][-1]
    assert e["verdict"] == "accepted" and e["direction_question"] is False
    assert e["direction_confirmed_by_colours"] is True
    assert e["direction_colours"]["verdict"] == "saved"
    assert e["voted"] is True and e["direction_reference"] == -1
    assert e["direction_votes_before"] == [-1] * 5
    assert "ruler_direction" not in e["questions_asked"]


# ---------------------------------------------------------------- C (F3)
def test_a_strip_with_another_question_does_not_vote(tmp_path):
    rs = _session3(tmp_path)
    for s in _names(4):
        _read(rs, s, -1, False)
    _read(rs, "E", -1, False, other_question=True)
    assert rs.direction_votes == [-1] * 4


def test_a_re_read_replaces_the_vote(tmp_path):
    rs = _session3(tmp_path)
    for s in _names(4):
        _read(rs, s, -1, False)
    _read(rs, "E", -1, False, other_question=True)    # a slip, say
    _read(rs, "E", -1, False)                         # read again: fine
    assert rs.direction_votes == [-1] * 5
    _read(rs, "B", -1, False)                         # read again, no doubt
    assert len(rs.direction_votes) == 5
    assert list(rs._votes)[-1] == "B"


def test_a_re_read_after_a_wrong_vote_leaves_nothing_behind(tmp_path):
    """4.3.39: a strip asked something else still voted, and a re-read added
    a second vote beside the wrong one."""
    rs = _session3(tmp_path)
    for s in _names(4):
        _read(rs, s, -1, False)
    e = _row(5)
    _read(rs, "E", -1, True, expected=e, measured=list(reversed(e)),
          other_question=True)                        # back to front, asked
    _read(rs, "E", -1, False, expected=e)             # re-read, saved right
    assert rs.direction_votes == [-1] * 5


def _ramp(k=0):
    half = [(30 + 5 * i, (k % 5) - 2.0, 0.0) for i in range(8)]
    return half + list(reversed(half))


def test_re_read_on_the_direction_question_casts_no_vote(tmp_path):
    rs = _session3(tmp_path)
    for s in _names(6):
        _read(rs, s, -1, False)
    summ = _read(rs, "G", -1, True, expected=_ramp())
    assert summ["ask_direction"]
    rs.note_answer("G", "reread")
    assert rs.direction_votes == [-1] * 6


def test_continue_anyway_on_the_direction_question_is_a_vote(tmp_path):
    """Review MINOR-3: the person has said what happened."""
    rs = _session3(tmp_path)
    for s in _names(6):
        _read(rs, s, -1, False)
    assert _read(rs, "G", -1, True, expected=_ramp())["ask_direction"]
    assert rs.direction_votes == [-1] * 6           # not before the answer
    rs.note_answer("G", "continue")
    assert rs.direction_votes == [-1] * 6 + [+1]


def test_a_turned_ramp_chart_follows_after_continue_anyway(tmp_path):
    """No strip of a ramp chart can vouch: 4.3.39 (and ed864ff0a) asked every
    strip after a turn (10 of 10). With Continue Anyway as a vote: two."""
    rs = _session3(tmp_path)
    for k, s in enumerate(_names(6)):
        _read(rs, s, -1, False, expected=_ramp(k))
    asked = []
    for k, s in enumerate(_names(10, 6)):
        summ = _read(rs, s, -1, True, expected=_ramp(k))
        if summ["ask_direction"]:
            asked.append(s)
            rs.note_answer(s, "continue")
    assert asked == ["G", "H"]


def test_a_wrong_continue_anyway_is_outvoted(tmp_path):
    """Review MINOR-3, the wrong answer: Continue Anyway on a strip that
    really was saved back to front. One such vote cannot move the reference
    (4 of 5 still agree): the next back-to-front strip is asked again. Two in
    a row leave no majority (3 of 5) for the next strips, which are then not
    asked and get no direction line, until the window holds 4 of 5 again:
    after four good strips the reference is back and asks again."""
    rs = _session3(tmp_path)
    for s in _names(8):
        _read(rs, s, -1, False)
    assert _read(rs, "I", -1, True, expected=_ramp(1))["ask_direction"]
    rs.note_answer("I", "continue")                    # wrong
    assert rs._majority_direction() == -1
    assert _read(rs, "J", -1, True, expected=_ramp(2))["ask_direction"]
    rs.note_answer("J", "continue")                    # wrong again
    assert rs._majority_direction() == 0
    blind = []
    for s in _names(5, 10):
        if not rs._majority_direction():
            blind.append(s)
        assert not _read(rs, s, -1, False)["ask_direction"]
    assert blind == ["K", "L", "M", "N"]               # 4 strips, then back
    assert rs._majority_direction() == -1
    assert _read(rs, "P", -1, True, expected=_ramp(3))["ask_direction"]


def test_reviewers_case_another_question_early_then_back_to_front(tmp_path):
    """Review MINOR-1: no turn, strip 2 gets a slip question (not about its
    order), strip 4 is really saved back to front with colours that cannot
    tell. 4.3.39 asked strip 4; ed864ff0a did not (strip 2 did not vote, so
    no majority yet)."""
    rs = _session3(tmp_path)
    _read(rs, "A", -1, False)
    rs.on_strip(_rec("B", 300, gen="i1pro3", sign=-1))
    rs.on_strip_read({"event": "strip_read", "strip": "B", "reversed": False,
                      "patches": _patches("B", _row(66))},
                     other_question=True, other_questions=["slip"])
    _read(rs, "C", -1, False)
    assert _read(rs, "D", -1, True, expected=_ramp(4))["ask_direction"]


@pytest.mark.parametrize("question,votes", [
    ("slip", True), ("engine_slip", True), ("back_to_front", False)])
def test_which_other_questions_vote(tmp_path, question, votes):
    rs = _session3(tmp_path)
    rs.on_strip(_rec("A", 300, gen="i1pro3", sign=-1))
    rs.on_strip_read({"event": "strip_read", "strip": "A", "reversed": False,
                      "patches": _patches("A", _row(3))},
                     other_question=True, other_questions=[question])
    assert rs.direction_votes == ([-1] if votes else [])


@pytest.mark.parametrize("answer,votes", [
    ("keep", True), ("closed", True), ("reread", False), ("was_like", False)])
def test_read_twice_votes_once_kept(tmp_path, answer, votes):
    rs = _session3(tmp_path)
    rs.on_strip(_rec("A", 300, gen="i1pro3", sign=-1))
    rs.on_strip_read({"event": "strip_read", "strip": "A", "reversed": False,
                      "patches": _patches("A", _row(3))},
                     other_question=True, other_questions=["read_twice"])
    assert rs.direction_votes == []
    rs.note_question_answer("A", "read_twice", answer)
    assert rs.direction_votes == ([-1] if votes else [])


def test_re_read_on_the_ruler_window_takes_the_vote_back(tmp_path):
    """Re-read on the ruler's window (coverage, which votes at once, as
    MINOR-1 asks) discards that reading's vote."""
    rs = _session3(tmp_path)
    rs.on_strip(_rec("A", 300, gen="i1pro3", sign=-1))
    rs.on_strip_read({"event": "strip_read", "strip": "A", "reversed": False,
                      "patches": _patches("A", _row(3))},
                     other_question=False)
    assert rs.direction_votes == [-1]
    rs.note_answer("A", "reread")
    assert rs.direction_votes == []


def test_forget_drops_a_vote(tmp_path):
    rs = _session3(tmp_path)
    for s in _names(4):
        _read(rs, s, -1, False)
    rs.forget("B")
    assert list(rs._votes) == ["A", "C", "D"]


# ---------------------------------------------------------------- C (F4)
def test_after_a_turn_a_strip_saved_first_to_last_is_never_against(tmp_path):
    """The report's F4: sheet turned, the strip swiped from the other end
    and saved first to last. 4.3.39 said "moved against the reading
    direction"."""
    rs = _session3(tmp_path)
    for s in _names(8):
        _read(rs, s, -1, False)
    lines = []
    for s in _names(6, 8):           # sheet turned, swiped the other way
        lines += _read(rs, s, +1, False)["log_lines"]
    assert not any("against the reading direction" in ln for ln in lines)
    assert any("in the reading direction, from the first patch" in ln
               for ln in lines)


def test_the_direction_is_its_own_line_after_the_saving(tmp_path):
    rs = _session3(tmp_path)
    motion = rs.on_strip(_rec("A", 300, gen="i1pro3", sign=-1))
    assert not any("reading direction" in ln for ln in motion)
    first = rs.on_strip_read({"event": "strip_read", "strip": "A",
                              "reversed": False,
                              "patches": _patches("A", _row(1))},
                             other_question=False)
    assert first["log_lines"] == []           # nothing to compare with yet
    second = _read(rs, "B", -1, False)
    assert second["log_lines"] == [
        "Ruler (beta), strip B: the instrument moved in the reading "
        "direction, from the first patch towards the last."]


def test_direction_agrees_uses_the_majority(tmp_path):
    """First three strips turned: 4.3.39 measured against the first strip
    not saved reversed (strip D), so A-C read as disagreeing for ever."""
    rs = _session3(tmp_path)
    for s in _names(3):
        _read(rs, s, -1, True)
    for s in _names(9, 3):
        _read(rs, s, -1, False)
    rs.flush()
    doc = json.loads(rs.diagnostics_path().read_text(encoding="utf-8"))
    agrees = {e["strip"]: e["direction_agrees"] for e in doc["strips"]}
    assert agrees["B"] is True and agrees["C"] is True
    assert agrees["D"] is False                  # the turn, as it happened
    assert all(agrees[s] is True for s in "HIJKL")


# ---------------------------------------------------------------- D
def test_a_session_read_one_way_round_is_as_before(tmp_path):
    """Nothing turned: same questions as 4.3.39 (none), the reference never
    moves, and a real back-to-front strip is asked exactly as before."""
    rs = _session3(tmp_path)
    for i, s in enumerate(_names(10)):
        assert not _read(rs, s, -1 if i % 3 else +1, i % 3 == 0)["ask_direction"]
    assert set(rs.direction_votes) == {-1}


# ---------------------------------------------------------------- matrix
def _chart702():
    fields, rows, fmt, data = [], {}, False, False
    for ln in (DATA / "chart702.ti2").read_text(encoding="latin-1").splitlines():
        s = ln.strip()
        if s == "BEGIN_DATA_FORMAT":
            fmt = True
        elif s == "END_DATA_FORMAT":
            fmt = False
        elif fmt:
            fields += s.split()
        elif s == "BEGIN_DATA":
            data = True
        elif s == "END_DATA":
            data = False
        elif data and s:
            rec = dict(zip(fields, s.split()))
            loc = rec["SAMPLE_LOC"].strip('"')
            letter = "".join(c for c in loc if c.isalpha())
            num = int("".join(c for c in loc if c.isdigit()))
            rows.setdefault(letter, []).append(
                (num, loc, tuple(float(rec[k]) for k in ("XYZ_X", "XYZ_Y", "XYZ_Z"))))
    order = sorted(rows, key=lambda L: (len(L), L))
    return order, {k: [(loc, x) for _, loc, x in sorted(v)] for k, v in rows.items()}


def _distort(xyz, level, rng):
    """The replay study's print models: 0 exact, 2 "like his report"."""
    if level == 0:
        return xyz
    pull, gain, sd = {2: (0.30, 0.85, 1.0)}[level]
    g = (xyz[0] / 0.9642 + xyz[1] + xyz[2] / 0.8249) / 3.0
    return tuple(max(0.05, gain * ((1 - pull) * v + pull * g * w) + rng.gauss(0, sd))
                 for v, w in zip(xyz, (0.9642, 1.0, 0.8249)))


def _plans(order):
    n, ae, p3 = len(order), order.index("AE"), order.index("AA")
    base = [dict(dir="down", sheet="normal", rot=False) for _ in range(n)]

    def mod(f):
        out = [dict(d) for d in base]
        for i, d in enumerate(out):
            f(i, d)
        return out
    rnd = random.Random(11)
    return {
        "all_down": mod(lambda i, d: None),
        "all_up": mod(lambda i, d: d.update(dir="up")),
        "alternating": mod(lambda i, d: d.update(dir="up" if i % 2 else "down")),
        "random_dirs": mod(lambda i, d: d.update(dir=rnd.choice(["up", "down"]))),
        "AE_read_up": mod(lambda i, d: d.update(dir="up") if i == ae else None),
        "whole_sheet_turned": mod(lambda i, d: d.update(sheet="turned")),
        "AE_sheet_turned": mod(lambda i, d: d.update(sheet="turned") if i == ae else None),
        "page3_sheet_turned": mod(lambda i, d: d.update(sheet="turned") if i >= p3 else None),
        "page3_turned_alternating": mod(lambda i, d: d.update(
            sheet="turned" if i >= p3 else "normal", dir="up" if i % 2 else "down")),
        "AE_instrument_rotated": mod(lambda i, d: d.update(rot=True) if i == ae else None),
        "first3_turned_then_normal": mod(lambda i, d: d.update(sheet="turned") if i < 3 else None),
        "pages1_2_turned_page3_normal": mod(lambda i, d: d.update(sheet="turned") if i < p3 else None),
    }


#: (4.3.39 windows from the report's replay on the real helper, 4.3.40
#: windows, 4.3.40 log notes) for levels 0 and 2.
EXPECTED = {
    "all_down": (0, 0, 0), "all_up": (0, 0, 0), "alternating": (0, 0, 0),
    "random_dirs": (0, 0, 0), "AE_read_up": (0, 0, 0),
    "whole_sheet_turned": (0, 0, 0), "AE_sheet_turned": (1, 0, 1),
    "page3_sheet_turned": (13, 0, 2), "page3_turned_alternating": (13, 0, 2),
    "AE_instrument_rotated": (1, 0, 1), "first3_turned_then_normal": (36, 0, 2),
    "pages1_2_turned_page3_normal": (13, 0, 2),
}


def _legacy_windows(filed_signs):
    """4.3.39's rule, for the 'before' column: every vote of the session,
    a strip asked about does not vote."""
    votes, asked = [], 0
    for fs in filed_signs:
        maj = 0
        if len(votes) >= 3:
            plus = sum(1 for v in votes if v > 0)
            maj = 1 if plus >= 0.75 * len(votes) else (
                -1 if len(votes) - plus >= 0.75 * len(votes) else 0)
        if maj and fs != maj:
            asked += 1
        else:
            votes.append(fs)
    return asked


@pytest.mark.parametrize("level", [0, 2])
def test_the_replay_matrix_question_counts(tmp_path, level):
    """The tester's 702-patch chart (39 strips of 18), the physical model of
    the replay study (K = -1: the ruler's sign for a strip read from the top
    with the instrument held as usual), every strip saved correctly, as the
    real helper did in all 144 runs of the study."""
    order, rows = _chart702()
    rng = random.Random(7)
    meas = {L: [_distort(x, level, rng) for _, x in rows[L]] for L in order}
    got = {}
    for name, plan in _plans(order).items():
        rs = RulerSession(ti1_path=None)
        rs.on_session({"event": "ruler", "active": True,
                       "instrument": "i1pro2", "firmware": 634})
        windows = notes = 0
        filed = []
        for i, L in enumerate(order):
            d = plan[i]
            seen_rev = (d["dir"] == "up") != (d["sheet"] == "turned")
            sign = -1 * (1 if d["dir"] == "down" else -1) * (-1 if d["rot"] else 1)
            filed.append(-sign if seen_rev else sign)
            # saved correctly (the reader turned a reversed one round), so
            # the patches as filed are the strip's own in chart order
            patches = [{"loc": loc, "xyz": list(mx), "exyz": list(ex)}
                       for (loc, ex), mx in zip(rows[L], meas[L])]
            rs.on_strip(_cut(_rec(L, 300, gen="i1pro2", sign=sign), n=18))
            summ = rs.on_strip_read({"event": "strip_read", "strip": L,
                                     "reversed": seen_rev, "patches": patches},
                                    other_question=False)
            assert not summ["ask"], (name, L)
            windows += bool(summ["ask_direction"])
            notes += bool(summ["direction_confirmed_by_colours"])
            if summ["ask_direction"]:
                rs.note_answer(L, "continue")
        got[name] = (_legacy_windows(filed), windows, notes)
    assert got == EXPECTED


# ---------------------------------------------------------------- texts
def test_the_colours_variant_does_not_call_it_harmless():
    from workflow import measurement_messages as M
    m = M.CATALOGUE["M-STRIP-RULER-DIRECTION-COLOURS"]
    assert m.id in M.PROPOSED
    title, body = m.render(strip="9")
    assert "back to front" in title
    assert "harmless" not in body and "likeliest" not in body
    assert "Reading the strip again cannot make anything worse" in body
    assert "safe" not in body
    assert "—" not in title + body


@pytest.mark.parametrize("verdict,mid", [
    ("other", "M-STRIP-RULER-DIRECTION-COLOURS"),
    ("unsure", "M-STRIP-RULER-DIRECTION"), (None, "M-STRIP-RULER-DIRECTION")])
def test_the_window_picks_its_text_by_the_colours(verdict, mid):
    from ui.tabs.tab_measure import TabMeasure
    from workflow import measurement_messages as M
    assert TabMeasure._ruler_direction_texts(None, "9", verdict) == \
        M.CATALOGUE[mid].render(strip="9")


def test_the_summary_carries_the_colours_verdict(tmp_path):
    rs = _session3(tmp_path)
    for s in _names(8):
        _read(rs, s, -1, False)
    e = _row(99)
    meas = [(L + 4, a * 0.8, b * 0.8) for L, a, b in reversed(e)]
    summ = _read(rs, "I", -1, True, expected=e, measured=meas)
    assert summ["ask_direction"] and summ["direction_colours_verdict"] == "other"


# ---------------------------------------------------------------- off
def test_option_off_runs_none_of_this_at_the_measure_level(qapp, tmp_path,
                                                           monkeypatch):
    """With the ruler check off the manager has no RulerSession, none of the
    new code runs, and a strip's log is the plain "Strip read OK" line."""
    from tests.test_i1pro2_lights_beta_option import _Runner
    from workflow import chartread_engine
    from workflow import ruler_session as rsm
    from workflow.measure_manager import MeasureManager, MeasureParams

    def boom(*a, **k):
        raise AssertionError("ruler code ran with the option off")
    monkeypatch.setattr(ss, "own_row_direction", boom)
    for name in ("on_strip_read", "forget", "note_answer",
                 "note_question_answer", "on_strip"):
        monkeypatch.setattr(rsm.RulerSession, name, boom)
    monkeypatch.setattr(chartread_engine, "helper_caps",
                        lambda helper=None: frozenset({"ruler_check"}))
    monkeypatch.setattr(MeasureManager, "_refuse_system_port",
                        lambda self, *a, **k: False)
    runner = _Runner()
    m = MeasureManager(runner)
    m.start(MeasureParams(ti1_path=tmp_path / "chart.ti1",
                          engine_helper=tmp_path / "chromiq-chartread",
                          engine_ruler_check=False),
            lambda _l: None, lambda _c: None)
    assert getattr(m, "_ruler", None) is None
    lines = []
    ev = {"event": "strip_read", "strip": "A", "reversed": True,
          "worst_de": 1.25, "patches": _patches("A", _row(1))}
    m._handle_engine_line(json.dumps(ev), lines.append)
    m._handle_engine_line(json.dumps({"event": "strip_turned", "strip": "A",
                                      "patches": ev["patches"]}), lines.append)
    m.note_question_answer("A", "read_twice", "keep")
    assert not any("Ruler" in ln for ln in lines), lines
    assert any(ln.strip() == "Strip read OK — A (worst patch ΔE 1.2)"
               for ln in lines), lines


# ---------------------------------------------------------------- resume
def test_a_continued_measurement_starts_with_no_votes(tmp_path):
    """Tester, 2026-11-15 (4.3.39, a continued measurement): nothing from an
    earlier sitting seeds the reference. The manager builds a new
    RulerSession at every start (measure_manager.py, `self._ruler =
    RulerSession(...)`), which reads neither the .ti3 nor an earlier
    diagnostics file, and a vote needs a ruler record from this sitting. So
    the sheet the other way up than in the first sitting asks nothing on
    the first strips, whatever their colours."""
    rs = _session3(tmp_path)
    assert rs.direction_votes == []
    out = [_read(rs, s, -1, True, expected=_ramp(i))
           for i, s in enumerate(["AE", "AF", "AG"])]
    assert not any(x["ask_direction"] for x in out)


def test_readings_of_one_strip_are_one_vote(tmp_path):
    """4.3.39 counted every READING: one strip read three times (re-reads
    without a question) made a majority, and the next strip, read the other
    way up, was asked as the second strip of the sitting. Now one strip is
    one vote."""
    rs = _session3(tmp_path)
    for k in range(3):
        _read(rs, "AD", -1, False)
    assert rs.direction_votes == [-1]
    assert not _read(rs, "AE", -1, True, expected=_ramp(1))["ask_direction"]


def test_after_a_resume_the_first_vouched_strips_follow_the_new_way_up(tmp_path):
    """Resume with the sheet the other way up, after three strips of this
    sitting were read the first way up: the strip whose colours vouch gets
    a log line, not a window."""
    rs = _session3(tmp_path)
    for s in ("AA", "AB", "AC"):
        _read(rs, s, -1, False)
    summ = _read(rs, "AD", -1, True)
    assert not summ["ask_direction"] and _turned_note(summ)


# ---------------------------------------------------------------- the windows
class _Mgr:
    engine_active = True

    def __init__(self, rs):
        self.rs, self.answers, self.gotos = rs, [], []

    def ruler_answer(self, strip, answer):
        self.answers.append(answer)
        self.rs.note_answer(strip, answer)

    def goto_strip(self, strip):
        self.gotos.append(strip)


def _window_leaving(qapp, rs, strip, ruler, how):
    """TabMeasure._prompt_ruler_not_covered, the real function, on a stand-in
    widget; the window is left by *how*: "reread", "continue" or "escape"."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QPlainTextEdit, QPushButton, QWidget
    from ui.tabs.tab_measure import TabMeasure

    class Stand(QWidget):
        pass
    st = Stand()
    st._manager = _Mgr(rs)
    st._log = QPlainTextEdit()
    st._cue_window = lambda *_: None
    st._pace_prompt_open = False
    st._ruler_direction_texts = lambda s, v=None: \
        TabMeasure._ruler_direction_texts(st, s, v)
    seen = {}

    def exec_(dlg):
        seen["name"] = dlg.objectName()
        seen["title"] = dlg.windowTitle()
        if how == "escape":
            QTimer.singleShot(0, dlg.reject)
        else:
            want = {"reread": "Re-read Strip", "continue": "Continue Anyway"}[how]
            b = [x for x in dlg.findChildren(QPushButton) if x.text() == want][0]
            QTimer.singleShot(0, b.click)
        return dlg.exec()
    st._exec_measurement_window = exec_
    TabMeasure._prompt_ruler_not_covered(st, strip, ruler)
    return st._manager, seen


def _asked_strip(tmp_path, kind):
    """A session of 6 strips, then strip G asked: "unsure" (a ramp read the
    other way up), "other" (colours point to back to front), or "cover"."""
    rs = _session3(tmp_path)
    for s in _names(6):
        _read(rs, s, -1, False)
    if kind == "unsure":
        summ = _read(rs, "G", -1, True, expected=_ramp(2))
    elif kind == "other":
        e = _row(99)
        summ = _read(rs, "G", -1, True, expected=e,
                     measured=[(L + 4, a * 0.8, b * 0.8) for L, a, b in reversed(e)])
    else:
        summ = {"ask": True, "ask_direction": False, "travel_steps": 100,
                "coverage_steps": 90, "span_steps": 300, "mm_per_step": None}
    return rs, summ


@pytest.mark.parametrize("kind,how,answer,votes", [
    ("unsure", "continue", "continue", [-1] * 6 + [+1]),
    ("unsure", "escape", "closed", [-1] * 6),
    ("unsure", "reread", "reread", [-1] * 6),
    ("other", "continue", "continue", [-1] * 6),
    ("other", "escape", "closed", [-1] * 6),
    ("other", "reread", "reread", [-1] * 6),
    ("cover", "continue", "continue", [-1] * 6),
    ("cover", "escape", "closed", [-1] * 6),
    ("cover", "reread", "reread", [-1] * 6),
])
def test_each_window_and_each_way_of_leaving_it(qapp, tmp_path, kind, how,
                                                answer, votes):
    """Second look, MINOR-B: only Continue Anyway on the "cannot tell"
    window votes. Escape / the title-bar X keeps the reading as the exit spec
    says (nothing sent, no re-read) but is recorded as "closed" and casts no
    vote; on the window whose colours point to back to front no answer
    votes; Re-read sends the reader back and casts none."""
    rs, summ = _asked_strip(tmp_path, kind)
    m, seen = _window_leaving(qapp, rs, "G", summ, how)
    assert m.answers == [answer]
    assert m.gotos == (["G"] if how == "reread" else [])
    assert rs.direction_votes == votes
    if kind != "cover":
        assert seen["name"] == "ruler_direction_window"
        assert ("back to front" in seen["title"]) == (kind == "other")


# ---------------------------------------------------------------- MINOR-A
def _lost(summ):
    return [ln for ln in summ["log_lines"]
            if "do not agree about which way round the sheet lies" in ln]


def test_two_wrong_answers_in_a_row_say_the_reference_is_lost(tmp_path):
    """The reviewer's sequence: Continue Anyway twice on strips really saved
    back to front. The gap that follows is said once, in the log, on the
    first strip that cannot be compared; not again for the next ones."""
    rs = _session3(tmp_path)
    for s in _names(8):
        _read(rs, s, -1, False)
    for s, k in (("I", 1), ("J", 2)):
        assert _read(rs, s, -1, True, expected=_ramp(k))["ask_direction"]
        rs.note_answer(s, "continue")
    out = [_read(rs, s, -1, False) for s in _names(5, 10)]
    assert [len(_lost(x)) for x in out] == [1, 0, 0, 0, 0]


def test_a_ramp_chart_turned_says_the_reference_is_lost_once(tmp_path):
    rs = _session3(tmp_path)
    for k, s in enumerate(_names(6)):
        _read(rs, s, -1, False, expected=_ramp(k))
    lost = []
    for k, s in enumerate(_names(10, 6)):
        summ = _read(rs, s, -1, True, expected=_ramp(k))
        lost += [s] * len(_lost(summ))
        if summ["ask_direction"]:
            rs.note_answer(s, "continue")
    assert lost == ["I"]


def test_no_lost_line_before_there_was_a_reference_or_without_a_turn(tmp_path):
    rs = _session3(tmp_path)
    out = [_read(rs, s, -1 if i % 2 else +1, i % 2 == 0)
           for i, s in enumerate(_names(12))]
    assert not any(_lost(x) for x in out)


def test_continue_anyway_says_it_steers_the_next_strips():
    from workflow import measurement_messages as M
    _t, body = M.CATALOGUE["M-STRIP-RULER-DIRECTION"].render(strip="9")
    assert ("ChromIQ then takes this as the way the sheet lies for the next "
            "strips.") in body

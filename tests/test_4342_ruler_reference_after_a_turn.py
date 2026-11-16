"""The ruler check's direction reference after a CONFIRMED turn (4.3.42).

A tester's real 4.3.40 session (pharmacist, 2026-11-15, i1Pro 2): twice the
sheet was turned for two strips and turned straight back, and after each
quick turn back FOUR strips had no direction reference at all (the recent
five votes split 3:2 / 2:3), so nothing was compared. Since 4.3.42 a strip
whose ruler disagrees with the reference while its own colours vouch for the
order it was saved in (a confirmed turn) restarts the reference from that
strip's way round; while the restarted reference is young (its own votes hold no majority yet) it is held
together with the old one, so a strip either of them would ask about is
still asked about.

Replayed here from his REAL ruler records (tests/data/ruler_turned_sheet/
pharmacist_43{39,40}_ruler.json, the records without the brightness trace);
the patch colours are assumed, because the file holds none: "vouch" (every
strip's own row fits as saved, as his did where it was looked at), "unsure"
(a ramp, which can never vouch) and "mixed" (every second strip a ramp).
The numbers of the sequence models are in the work notes of 2026-11-16
(b1/eval3.txt): no session without a turn changes when every answer is
right; with turns, fewer real back-to-front strips go unasked than before.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests import test_4340_ruler_turned_sheet as T
from tests.test_ruler_session import _rec
from workflow.ruler_session import RulerSession

DATA = Path(__file__).parent / "data" / "ruler_turned_sheet"


def _ramp(k):
    half = [(30 + 6 * i, (k % 5) - 2.0, 0.0) for i in range(9)]
    return half + list(reversed(half))


def _colours(mode, k, name):
    if mode == "vouch" or (mode == "mixed" and k % 2 == 0):
        return T._row(sum(map(ord, name)) + k, n=18)
    return _ramp(k)


def _replay(fixture, mode):
    """-> (windows, notes, unreferenced, entries) over his records: windows
    and notes as strip names; unreferenced = accepted strips with no
    reference before them, from the fourth on."""
    doc = json.loads((DATA / fixture).read_text(encoding="utf-8"))
    entries = doc["strips"]
    reads = [i for i, e in enumerate(entries)
             if e.get("verdict") in ("accepted", "asked")]
    rs = RulerSession(ti1_path=None)
    rs.on_session({"event": "ruler", "active": True, "instrument": "i1pro2",
                   "firmware": 634})
    windows, notes, noref, n = [], [], [], 0
    for i, e in enumerate(entries):
        rec = dict(e["record"])
        rec["strip"] = e["strip"]
        rs.on_strip(rec)
        if e.get("verdict") not in ("accepted", "asked"):
            continue
        ref = rs._majority_direction() or rs._old_majority()
        ev = {"event": "strip_read", "strip": e["strip"],
              "reversed": bool(e.get("reversed")),
              "patches": T._patches(e["strip"], _colours(mode, i, e["strip"]),
                                    seed=i)}
        s = rs.on_strip_read(ev, other_question=False) or {}
        n += 1
        if not ref and n > 3 and s.get("usable"):
            noref.append(e["strip"])
        if s.get("ask_direction") or s.get("ask"):
            if s.get("ask_direction"):
                windows.append(e["strip"])
            nxt = [j for j in reads if j > i]
            a = e.get("answer") or ("reread" if nxt and entries[nxt[0]]["strip"]
                                    == e["strip"] else "continue")
            rs.note_answer(e["strip"], a)
        if s.get("direction_confirmed_by_colours"):
            notes.append(e["strip"])
    return windows, notes, noref, entries


def test_his_4340_session_had_four_unreferenced_strips_after_each_turn():
    """What his file itself says (the 4.3.40 code wrote it)."""
    entries = json.loads((DATA / "pharmacist_4340_ruler.json").read_text(
        encoding="utf-8"))["strips"]
    acc = [e for e in entries if e.get("verdict") in ("accepted", "asked")]
    assert [e["strip"] for e in acc[3:] if e.get("direction_reference") is None] \
        == ["N", "O", "P", "Q", "AA", "AB", "AC", "AD"]
    assert [e["strip"] for e in acc if e.get("direction_confirmed_by_colours")] \
        == ["L", "M", "Y", "Z", "AL", "AM"]


def test_his_4340_session_now_compares_every_strip():
    windows, notes, noref, _ = _replay("pharmacist_4340_ruler.json", "vouch")
    assert noref == []                  # was 8: four after each quick turn back
    assert windows == []                # still no window
    # his six notes, and one more for each turn back (N, AA): the strip that
    # showed the sheet was the right way round again
    assert notes == ["L", "M", "N", "Y", "Z", "AA", "AL", "AM"]


def test_his_4340_session_on_colours_that_cannot_vouch_is_as_before():
    """No vouch, no restart: exactly the 4.3.41 result."""
    windows, notes, noref, _ = _replay("pharmacist_4340_ruler.json", "unsure")
    assert windows == ["L", "M", "Y", "Z", "AL", "AM"] and notes == []
    assert noref == ["N", "O", "P", "Q", "AA", "AB", "AC", "AD"]


def test_his_4340_session_on_mixed_colours_leaves_at_most_two():
    windows, notes, noref, _ = _replay("pharmacist_4340_ruler.json", "mixed")
    assert windows == ["L", "N", "Y", "AL", "AM"]
    assert notes == ["M", "Z", "AA"]
    assert noref == ["O", "P"]          # was 8


@pytest.mark.parametrize("mode,noref", [("vouch", []),
                                        ("unsure", ["N", "O", "Y", "Z"]),
                                        ("mixed", ["Y", "Z"])])
def test_his_4339_session(mode, noref):
    windows, notes, got, _ = _replay("pharmacist_4339_ruler.json", mode)
    assert got == noref                 # 4.3.41: 4 in every mode
    expected = {"vouch": ([], ["L", "L", "M", "W", "X", "AL", "AM"]),
                "unsure": (["L", "L", "M", "W", "X", "AL", "AM"], []),
                "mixed": (["L", "W", "X", "AM"], ["L", "M", "AL"])}[mode]
    assert (windows, notes) == expected


def test_his_fixtures_hold_no_trace_and_no_serial():
    for name in ("pharmacist_4339_ruler.json", "pharmacist_4340_ruler.json"):
        text = (DATA / name).read_text(encoding="utf-8")
        doc = json.loads(text)
        assert "serial" not in json.dumps(doc["strips"]).lower()
        assert all("trace" not in e["record"] for e in doc["strips"])


# ------------------------------------------------------------ the rule
def _ramp16(k):
    """A 16-patch row that reads the same both ways (cannot vouch)."""
    half = [(30 + 6 * i, (k % 5) - 2.0, 0.0) for i in range(8)]
    return half + list(reversed(half))


def _read(rs, strip, sign, reversed_, measured=None, expected=None):
    expected = expected if expected is not None else T._row(sum(map(ord, strip)))
    rs.on_strip(_rec(strip, 300, gen="i1pro3", sign=sign))
    return rs.on_strip_read({"event": "strip_read", "strip": strip,
                             "reversed": reversed_,
                             "patches": T._patches(strip, expected, measured)},
                            other_question=False)


def _session():
    rs = RulerSession(ti1_path=None)
    rs.on_session({"event": "ruler", "active": True, "instrument": "i1pro3",
                   "firmware": 634})
    return rs


def test_a_confirmed_turn_restarts_the_reference_at_once(tmp_path):
    rs = T._session3(tmp_path)
    for s in "ABCDEFGH":
        _read(rs, s, -1, False)
    x = _read(rs, "I", -1, True)        # turned: the colours vouch
    assert x["direction_confirmed_by_colours"]
    assert rs._majority_direction() == -rs._old_majority() != 0
    flags = [e.get("direction_restarted") for e in rs.diag.doc["strips"]]
    assert flags == [False] * 8 + [True]


def test_a_ramp_strip_back_to_front_right_after_a_turn_back_is_asked():
    """The pharmacist's pattern, then a strip whose colours cannot vouch,
    saved back to front: 4.3.41 had no reference there and said nothing."""
    rs = _session()
    for s in "ABCDEFGH":
        _read(rs, s, -1, False)
    _read(rs, "I", -1, True)
    _read(rs, "J", -1, True)
    _read(rs, "K", -1, False)           # turned back: vouched
    r = _ramp16(3)
    x = _read(rs, "L", -1, True, measured=r, expected=list(reversed(r)))
    assert x["ask_direction"]


def test_while_the_restart_is_young_the_old_reference_still_asks():
    """One strip turned (vouched), then a ramp strip that the old reference
    sees as back to front: asked, as in 4.3.41."""
    rs = _session()
    for s in "ABCDEFGH":
        _read(rs, s, -1, False)
    _read(rs, "I", -1, True)
    r = _ramp16(1)
    x = _read(rs, "J", -1, True, measured=list(reversed(r)), expected=r)
    assert x["ask_direction"]


def test_without_a_turn_nothing_restarts():
    rs = _session()
    for i, s in enumerate("ABCDEFGHIJKL"):
        _read(rs, s, -1 if i % 2 else 1, bool(i % 2))
    assert rs._turn_sign == 0 and rs._old_majority() == 0


def test_the_ruler_help_says_what_happens_after_a_turn():
    from ui.dialogs.settings_dialog import ruler_check_help
    h = " ".join(ruler_check_help().split())
    assert "Turning the sheet or the ruler round is fine" in h
    assert "compares the strips after it with the new way round straight away" in h
    assert "Continue Anyway" in h and "for a few strips" in h


# ------------------------------------------- review finding B1 (fix A)
def _ramp_read(rs, strip, k, reversed_):
    r = _ramp16(k)
    return _read(rs, strip, -1, reversed_, measured=r,
                 expected=list(reversed(r)))


def test_a_ramp_strip_back_to_front_after_a_one_strip_turn_and_back_is_asked():
    """Review B1, shape H1: one strip turned (vouched: restart), the turn
    back on a ramp strip (asked, Continue: it votes), one more ramp strip,
    then a ramp strip saved back to front. The three votes since the turn
    (+, -, -) hold no majority of their own, while the session's last five
    do; 4.3.41 asked about W, and so must 4.3.42."""
    rs = _session()
    for s in "ABCDEF":
        _read(rs, s, -1, False)
    assert _read(rs, "T", -1, True)["direction_confirmed_by_colours"]
    u = _ramp_read(rs, "U", 1, False)
    assert u["ask_direction"]
    rs.note_answer("U", "continue")
    assert not _ramp_read(rs, "V", 2, False)["ask_direction"]
    w = _ramp_read(rs, "W", 3, True)
    assert w["ask_direction"]


def test_a_chance_vouched_misfile_does_not_hide_a_later_one():
    """Review B1, shape H2: a misfiled strip whose colours vouch by chance
    restarts the reference the wrong way; the next ramp misfile is still
    asked about, as in 4.3.41."""
    rs = _session()
    for s in "ABCDEFGH":
        _read(rs, s, -1, False)
    assert _read(rs, "M", -1, True)["direction_confirmed_by_colours"]
    n = _ramp_read(rs, "N", 1, False)
    if n["ask_direction"]:
        rs.note_answer("N", "continue")
    assert not _ramp_read(rs, "O", 2, False)["ask_direction"]
    assert _ramp_read(rs, "P", 3, True)["ask_direction"]


def test_the_old_reference_steps_aside_once_the_new_one_has_a_majority():
    """The other side of fix A: once the votes since the turn hold a
    majority of their own, the old reference is no longer consulted, so a
    real turn is followed as before."""
    rs = _session()
    for s in "ABCDEFGH":
        _read(rs, s, -1, False)
    _read(rs, "I", -1, True)            # turned, vouched
    for s in "JKL":
        _read(rs, s, -1, True)          # still turned: votes agree
    assert rs._majority_direction() == 1
    assert rs._old_majority() == 0

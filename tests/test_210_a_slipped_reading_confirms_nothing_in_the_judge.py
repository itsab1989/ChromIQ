"""#210: a reading from a strip the misalignment safety net flagged confirms
nothing, and nothing confirms it (Basti, 2026-10-15).

The net says the strip was read a patch or two out, so every reading in it
belongs to another patch. ``FlagJudge.judge(slipped=True)`` keeps that on the
reading (``_Reading.slipped``), and every path that can make a patch yellow
leaves it out:

* the earlier readings a re-read is compared with (a later reading the net
  did NOT flag never confirms against a slipped one: the gap the first #210
  change left in ``workflow/patch_flags.py``);
* the re-read itself (a slipped reading that repeats an earlier one is not a
  confirmation, and a slip that repeats a slip is not one either);
* similar patches, for both tests (``_pair_ok``, the rule of dd76f0b25,
  Knut #182 6196599132): a slipped reading is nobody's similar patch and
  has none;
* the colour range: it is never learned and teaches nothing.

Ordinary identical re-reads still confirm (the controls).
"""
from __future__ import annotations

from workflow import patch_flags as pf

BLUE = (33.0, 21.0, -61.0)
SHIFT = (5.0, -20.0, 25.0)              # ΔE*ab 32.4, past the limit
LIMIT = 20.0
LOCS = [f"{c}{n}" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for n in range(1, 31)]


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _judge():
    return pf.FlagJudge(device_ranges={loc: "blue" for loc in LOCS})


def _read(j, loc, exp=BLUE, shift=SHIFT, *, pe=True, nb=False, live=True,
          slipped=False):
    meas = _add(exp, shift)
    return j.judge(loc, exp, meas, pf._norm(shift), pe or nb,
                   strip=loc.rstrip("0123456789"), live=live,
                   reread_only=nb, warn=pe, limit=LIMIT, slipped=slipped)


def _settle(j):
    j.rejudge()
    return j._verdicts


# ---- the controls -----------------------------------------------------------
def test_control_an_identical_re_read_confirms():
    j = _judge()
    _read(j, "A1")
    v = _read(j, "A1")
    assert v.flag == pf.FLAG_CONFIRMED and v.pe_state == pf.STATE_REREAD


def test_control_similar_patches_confirm():
    j = _judge()
    _read(j, "A1")
    assert _read(j, "B1").flag == pf.FLAG_CONFIRMED


# ---- re-reads -----------------------------------------------------------------
def test_a_later_unflagged_reading_never_confirms_against_the_slip():
    """THE GAP: slipped first, then an ordinary reading of the same colour."""
    j = _judge()
    _read(j, "A1", slipped=True)
    v = _read(j, "A1")
    assert v.flag is pf.FLAG_RED and v.pe_state == pf.STATE_RED
    assert "A1" not in j.confirmed
    # the next ordinary reading of that colour confirms the ordinary one
    assert _read(j, "A1").flag == pf.FLAG_CONFIRMED


def test_a_slip_repeating_an_earlier_reading_is_not_a_confirmation():
    j = _judge()
    _read(j, "A1")
    v = _read(j, "A1", slipped=True)
    assert v.flag is pf.FLAG_RED and "A1" not in j.confirmed


def test_a_slip_repeating_a_slip_is_not_a_confirmation():
    j = _judge()
    _read(j, "A1", slipped=True)
    assert _read(j, "A1", slipped=True).flag is pf.FLAG_RED
    assert "A1" not in j.confirmed


def test_a_neighbour_suspect_is_never_confirmed_by_a_slip():
    j = _judge()
    _read(j, "A1", pe=False, nb=True, slipped=True)
    v = _read(j, "A1", pe=False, nb=True)
    assert v.flag is pf.FLAG_RED and v.nb_state == pf.STATE_RED


def test_a_slipped_reading_of_a_confirmed_patch_is_red_and_forgets_nothing():
    """The confirmation stays on record (it was two good readings), but it
    does not vouch for the slipped reading, nor teach while it is the last."""
    j = _judge()
    _read(j, "A1")
    _read(j, "A1")
    assert "A1" in j.confirmed
    v = _read(j, "A1", slipped=True)
    assert v.flag is pf.FLAG_RED
    assert j.range_status("blue") == (0, ())
    assert _read(j, "A1").flag == pf.FLAG_CONFIRMED


def test_a_repaint_of_a_slipped_reading_stays_red():
    j = _judge()
    _read(j, "A1", slipped=True)
    assert _read(j, "A1", live=False, slipped=True).flag is pf.FLAG_RED
    assert _settle(j)["A1"].flag is pf.FLAG_RED


def test_a_clean_slipped_reading_corrects_nothing():
    """Under the limit, but a reading of another patch: not green."""
    j = _judge()
    _read(j, "A1")
    v = _read(j, "A1", BLUE, (0.5, 0.5, 0.5), pe=False, slipped=True)
    assert v.flag is pf.FLAG_NONE
    assert "A1" not in j.corrected


# ---- similar patches (both tests) ---------------------------------------------
def test_a_slipped_reading_is_nobodys_similar_patch_for_the_patch_error():
    j = _judge()
    _read(j, "A1", slipped=True)
    v = _read(j, "B1")
    assert v.flag is pf.FLAG_RED and v.peer_locs == ()


def test_a_slipped_reading_has_no_similar_patches_for_the_patch_error():
    j = _judge()
    _read(j, "A1")
    v = _read(j, "B1", slipped=True)
    assert v.flag is pf.FLAG_RED and v.peer_locs == ()
    assert _settle(j)["A1"].flag is pf.FLAG_RED


def test_a_slipped_reading_is_nobodys_similar_patch_for_the_neighbour_check():
    j = _judge()
    _read(j, "A1", pe=False, nb=True, slipped=True)
    v = _read(j, "B1", pe=False, nb=True)
    assert v.flag is pf.FLAG_RED and v.nb_peer_locs == ()
    w = _settle(j)["A1"]
    assert w.flag is pf.FLAG_RED and w.nb_peer_locs == ()


def test_a_good_re_read_of_the_slipped_strip_makes_it_a_similar_patch_again():
    j = _judge()
    _read(j, "A1", slipped=True)
    _read(j, "B1")
    _read(j, "A1")                                   # read again, not slipped
    assert _settle(j)["B1"].flag == pf.FLAG_CONFIRMED


# ---- the colour range ---------------------------------------------------------
REFS = {"R1": (70.0, 21.0, -61.0), "S1": (33.0, 60.0, -61.0),
        "T1": (33.0, 21.0, -20.0)}


def test_a_slipped_reading_is_never_learned():
    j = _judge()
    for loc, exp in REFS.items():
        _read(j, loc, exp)
        _read(j, loc, exp)
    assert j.range_learned("blue")
    v = _read(j, "L1", _add(BLUE, (0.0, 0.0, 20.0)), SHIFT, slipped=True)
    assert v.flag is pf.FLAG_RED and v.like_loc == ""


def test_a_slipped_reading_teaches_nothing():
    j = _judge()
    _read(j, "A1", slipped=True)
    _read(j, "B1", _add(BLUE, (2.0, 0.0, 0.0)), slipped=True)
    _read(j, "C1", _add(BLUE, (4.0, 0.0, 0.0)), slipped=True)
    _settle(j)
    assert j.range_status("blue") == (0, ())

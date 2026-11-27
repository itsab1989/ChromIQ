"""4.3.69: THE TWO PASSES' TIMING IS JUDGED WITHOUT THE PLACE ALONG THE ROW THEY SHARE, MIRRORED.

The lamp pass runs forward, the UV pass back. A row that lies further along the table than the aims
say is met later by the lamp pass and earlier by the UV pass: the two best starts move apart,
mirrored, and both timing checks read that place as timing (the owner's 26 Nov rows 19 and 20:
lamp +2.0 / +1.75 readings, UV -1.25 / -2.25; the UV's R squared gain 0.0002 under its gate). The
mirrored part (the smaller of the two, the lamp's sign) is taken out of both; each pass is then
judged by its own limits, as before. The place is the row placement check's.

NO FAULT THE EARLIER CHECKS REFUSED IS ACCEPTED NOW, unless both passes are off in opposite
directions (a place, not a time): the planted faults of test_dual_uv_timing.py and
test_dual_lamp_timing.py, every one, and a grid of both passes off together."""
from __future__ import annotations

import random

import pytest

from tests.i1io_table.test_dual_uv_timing import _plan, _sheet, _stream
from workflow.i1io.table import dual_rows as dl
from workflow.i1io.table import scan as sc


def _passes(k_lamp=0.0, k_uv=0.0, seed=3):
    """Both passes' streams, each with its motion start k readings late (negative: early)."""
    lamp, uv = _plan()
    rng = random.Random(seed)
    levels = [0.08 + 0.8 * rng.random() for _ in range(25)]
    at = _sheet(lamp, levels)
    lr = _stream(lamp, sc.FIRST_READING_AFTER_LAMP_S,
                 sc.DUAL_LAMP_MOTION_START_S + k_lamp * sc.READING_S, lamp.N, at, False, rng)
    ur = _stream(uv, sc.UV_FIRST_READING_AFTER_TRIGGER_S,
                 sc.UV_MOTION_START_AFTER_TRIGGER_S + k_uv * sc.READING_S, uv.N, at, True, rng)
    return lamp, uv, lr, ur


def _verdicts(k_lamp, k_uv, monkeypatch=None, old=False):
    lamp, uv, lr, ur = _passes(k_lamp, k_uv)
    if old:
        monkeypatch.setattr(dl, "place_part", lambda a, b: 0.0)
    f = dl.uv_timing_fit(lamp, uv, lr, ur)
    if old:
        monkeypatch.undo()
    return f["lamp_refuse"], f["refuse"], f


def test_the_place_part_is_the_mirrored_smaller_one():
    assert dl.place_part(2.0, -1.25) == 1.25
    assert dl.place_part(1.75, -2.25) == 1.75
    assert dl.place_part(-1.5, 0.75) == -0.75
    assert dl.place_part(2.0, 0.0) == 0.0 and dl.place_part(2.0, 1.0) == 0.0
    assert dl.place_part(None, -1.0) == 0.0 and dl.place_part(1.0, None) == 0.0


def test_the_owners_far_rows_are_far_from_a_refusal_now():
    """The decision on the 26 Nov rows 19 and 20 as recorded (their best starts and gains)."""
    for lb, ub, ugain in ((2.0, -1.25, 0.00367), (1.75, -2.25, 0.00479)):
        place = dl.place_part(lb, ub)
        assert abs(lb - place) < 1.0 < dl.LAMP_FIT_REFUSE_LATE
        assert abs(ub + place) <= 0.5 < dl.UV_FIT_REFUSE_READINGS
        # before: the UV pass 2.25 readings off, refused at a gain of 0.005, it had 0.00479
        assert abs(ub) >= dl.UV_FIT_REFUSE_READINGS and ugain < dl.UV_FIT_MIN_GAIN


@pytest.mark.parametrize("k", [-6, -4, -3, -2, 2, 3, 4, 6])
def test_every_uv_fault_of_the_earlier_tests_is_still_refused(k):
    lamp_refuse, uv_refuse, f = _verdicts(0.0, float(k))
    assert uv_refuse is True, f


@pytest.mark.parametrize("k", [2.0, 3.0, 4.0, 6.0, -3.0, -4.0, -6.0])
def test_every_lamp_fault_of_the_earlier_tests_is_still_refused(k):
    lamp_refuse, uv_refuse, f = _verdicts(k, 0.0)
    assert lamp_refuse is True, f


@pytest.mark.parametrize("k", [1.0, 1.5, 2.0, 2.5])
def test_a_row_that_lies_further_along_is_judged_on_time_and_recorded(k):
    """The sheet's place: the lamp pass k readings late, the UV pass k early."""
    lamp_refuse, uv_refuse, f = _verdicts(k, -k)
    assert (lamp_refuse, uv_refuse) == (False, False), f
    assert abs(f["place_readings"] - k) <= 0.5, f
    assert abs(f["place_mm"] - f["place_readings"] * sc.READING_S * sc.DUAL_SPEED) < 1e-3


def test_no_fault_the_old_checks_refused_slips_through_but_a_mirrored_place(monkeypatch):
    """The table: both passes off together, every combination of -4 .. +4 readings. A row the
    old checks refused and the new ones accept has its two passes off in OPPOSITE directions."""
    ks = [-4.0, -2.0, -1.0, 0.0, 1.0, 2.0, 4.0]
    newly_accepted, newly_refused = [], []
    for kl in ks:
        for ku in ks:
            old = _verdicts(kl, ku, monkeypatch, old=True)
            new = _verdicts(kl, ku)
            old_r, new_r = old[0] or old[1], new[0] or new[1]
            if old_r and not new_r:
                newly_accepted.append((kl, ku))
            if new_r and not old_r:
                newly_refused.append((kl, ku))
    assert newly_refused == []
    assert newly_accepted and all(kl * ku < 0 for kl, ku in newly_accepted), newly_accepted

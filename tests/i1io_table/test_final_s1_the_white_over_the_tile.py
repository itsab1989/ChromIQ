"""Final fix round, S-1 (review 13): the white calibration is made only with the arm in the
recorded resting box over the tile (the recorded homing at rest first if it is not, after the
hands-off GO as before any move), and its LEVEL is checked on a reading of the table's tile:
a white made partly off its tile is refused in plain words, nothing is read with it, and the
calibration can be made again.

Review 13's probe P4 (a calibration 8 mm out from rest, at Y 79, accepted) fails here now."""
from __future__ import annotations

import pytest

from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_reading import job_for, ready_to_read
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl

MOVES = ("m0", "m1", "m2", "i1", "i0")


def _moves(sim, since=0):
    return [ln for ln in sim.received[since:] if ln[1:3] in MOVES]


def test_the_rule_is_the_recorded_resting_box():
    assert tbl.REST_RECORDED.ymax == 48 and tbl.REST_GUARD.ymax == 80
    assert J.WHITE_TILE_Y == (82.0, 97.0)
    assert J.WHITE_TILE_Y[0] < 89.78 < J.WHITE_TILE_Y[1]      # the volunteer's table, 17 Nov


def test_a_calibration_from_8_mm_out_homes_first_after_go_and_is_made_over_the_tile(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    assert p.drive(job.open()).ok
    sim.pos = [1102.0, 79.0]                    # review 13's P4: inside the guard, off the box
    n = len(sim.received)
    seen = []
    p.on_ask = lambda person, res: seen.append((res.confirm, len(_moves(sim, n)),
                                                helper.calibrations)) or None
    r = p.drive(job.calibrate())
    assert r.ok, (r.reason, r.detail)
    go = [s for s in seen if s[0] == J.Confirm.GO]
    assert go and go[0][1] == 0 and go[0][2] == 0     # asked before anything moved or read
    homing = _moves(sim, n)
    assert homing and all(ln[1:3] == "i1" for ln in homing)
    assert tbl.REST_RECORDED.contains(tuple(int(v) for v in sim.pos))
    assert helper.calibrations == 1


def test_go_back_before_that_homing_moves_nothing_and_makes_no_white(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, script={J.Confirm.GO: "back"})
    assert p.drive(job.open()).ok
    sim.pos = [1102.0, 60.0]
    n = len(sim.received)
    r = p.drive(job.calibrate())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "person_chose_back")
    assert _moves(sim, n) == [] and job.calibration is None and helper.calibrations == 0


def test_in_the_recorded_box_nothing_moves_for_the_white(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    assert p.drive(job.open()).ok
    sim.pos = [1102.0, 35.0]
    n = len(sim.received)
    assert p.drive(job.calibrate()).ok
    assert _moves(sim, n) == [] and job.calibration is not None


@pytest.mark.parametrize("level,ok", [(0.88, True), (0.83, True), (0.99, False), (0.70, False)])
def test_the_own_tile_white_is_checked_on_the_tables_tile(tmp_path, monkeypatch, level, ok):
    """The own tile: after the instrument is seated again, the table's tile is read once with
    the new white (nothing moves); a level a white tile never has refuses the white."""
    monkeypatch.setattr(RS, "REST_TILE", level)
    job, sim, helper, run, p = job_for(tmp_path, script={J.Confirm.CAL_PLACE: "own tile"})
    assert p.drive(job.open()).ok
    n = len(_moves(sim))
    r = p.drive(job.calibrate())
    assert len(_moves(sim)) == n
    if ok:
        assert r.ok and abs(r.detail["white_level_y"] - level * 100) < 0.5
        assert job.calibration is not None
        return
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "white_level_implausible")
    assert job.calibration is None and job.strip_calibration is None
    # nothing is read with it: a row is refused for the missing white
    assert job.read_row().reason in ("needs_calibration", "needs_alignment")
    # and the calibration can be made again (the instrument's own tile once more)
    monkeypatch.setattr(RS, "REST_TILE", 0.88)
    assert p.drive(job.calibrate()).ok and job.calibration is not None


def test_a_refused_white_is_said_in_plain_words():
    from ui import i1io_table_window as W
    text = W.reason_text("white_level_implausible", {"tile_y": 103.2, "lowest": 82.0,
                                                     "highest": 97.0})
    assert "103.2" in text and "82" in text and "97" in text and "calibrate again" in text
    assert "nothing has been read with it" in text
    for rid in ("arm_not_over_the_tile", "white_level_not_checked"):
        assert "diagnostics file" not in W.reason_text(rid)        # its own sentence


def test_the_table_tile_with_the_stored_white_option_is_level_checked_too(tmp_path,
                                                                          monkeypatch):
    monkeypatch.setattr(RS, "REST_TILE", 0.60)
    job, sim, helper, run, p = job_for(tmp_path)
    job.stored_tile_white = True
    sim.stored_tile = tuple([0.88] * 36)
    assert p.drive(job.open()).ok
    r = p.drive(job.calibrate())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "white_level_implausible")
    assert job.calibration is None


def test_a_whole_page_still_reads_with_the_own_tile(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, script={J.Confirm.CAL_PLACE: "own tile"})
    ready_to_read(job, p)
    while job.rows_left():
        assert p.drive(job.read_row()).ok

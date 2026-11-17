"""What the volunteer's table answered on 17 Nov 2026, as test data (owner-results fix round).

Only wire lines and numbers, nothing private (no serial, no memory block, no tile values): the
"test data" list of the analysis of that night, items 2 to 6 (item 1, m1, is in
test_ownerfix_m1_lands_where_the_real_table_put_it.py).
"""
from __future__ import annotations

import pytest

from tests.i1io_table.test_job_reading import read_page, small_sheet
from tests.i1io_table.test_roundB_strip import _job, _ready
from workflow.i1io.table import job as J
from workflow.i1io.table import lines as cl
from workflow.i1io.table import scan as sc
from workflow.i1io.table import session_table as tbl


# ---- (2) c4 answered BC and BA; BC passes, BD stops --------------------------------------------

@pytest.mark.parametrize("line,byte", [(":$c40BC56", 0xBC), (":$c40BA58", 0xBA)])
def test_the_recorded_c4_answers_decode_and_are_inside_the_range(line, byte):
    rep = tbl.parse_done_c(line, "c4", cl.C_DATA_LEN["scan_c4"])
    assert int(rep.data, 16) == byte
    assert sc.C4_RANGE[0] <= byte <= sc.C4_RANGE[1]


def test_the_c4_range_is_the_recorded_one():
    assert sc.C4_RANGE == (0xB7, 0xBC)
    assert "BC" in cl.C_RECORDED_AT["scan_c4"] and "17 Nov 2026" in cl.C_RECORDED_AT["scan_c4"]


def test_a_strip_row_whose_c4_answers_bc_is_read(tmp_path):
    """Failed before this round: BC was 'never seen' and every such row failed."""
    job, sim, helper, run, p = _job(tmp_path, sheet=small_sheet())
    sim.c_faults["c4_byte"] = 0xBC
    _ready(job, p)
    rows = read_page(job, p)
    assert rows and all(r.ok and r.detail["row_kind"] == "strip" for r in rows)


def test_a_strip_row_whose_c4_answers_bd_stops_cleanly(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, sheet=small_sheet(),
                                    script={J.Confirm.ROW_FAILED_STRIP: "stop"})
    sim.c_faults["c4_byte"] = 0xBD
    _ready(job, p)
    n_m2 = sum(1 for ln in sim.received if ln.startswith(";m2"))
    r = p.drive(job.read_row())
    assert r.kind == J.Kind.REFUSED and r.reason == "stopped_after_a_failed_row"
    asked = [a for a in p.asked if a[1] == J.Confirm.ROW_FAILED_STRIP]
    assert len(asked) == 1 and asked[0][2]["why"].startswith("strip_")
    # no scan move after the unknown answer, nothing pending
    assert sum(1 for ln in sim.received if ln.startswith(";m2")) == n_m2
    assert not r.state.strip_move_may_be_pending


# ---- (6) the calibration: a long wait at a question, and S-1 ------------------------------------

from tests.i1io_table.test_job_reading import job_for  # noqa: E402
from workflow.i1io.table import reader as rd  # noqa: E402


def test_a_200_s_wait_at_the_question_before_a_calibration_still_calibrates(tmp_path,
                                                                             monkeypatch):
    """The tester counted the person's answering time into the reader's budget (201 s on the
    real table, the calibration "took too long"). The app's reader starts its own wait only
    when it is opened, after the answers: 200 s at the place question change nothing."""
    clock = [1000.0]
    monkeypatch.setattr(rd.time, "monotonic", lambda: clock[0])

    def on_ask(person, res):
        if res.confirm in (J.Confirm.CAL_PLACE, J.Confirm.CAL_OWN_TILE):
            clock[0] += 200.0
        return None
    for place in ("table tile", "own tile"):
        job, sim, helper, run, p = job_for(tmp_path / place.replace(" ", "_"),
                                           {J.Confirm.CAL_PLACE: place})
        p.drive(job.open())
        p.on_ask = on_ask
        r = p.drive(job.calibrate())
        assert r.ok and r.detail["place"] == place, (r.reason, r.detail)
        assert helper.calibrations == 1 and not job.instrument_out


def test_s1_a_failed_own_tile_calibration_then_table_tile_never_calibrates_outside_the_arm(
        tmp_path):
    """The sequence of the real table (17 Nov 2026): own tile chosen, the calibration fails,
    the next answer. Before this round the job asked the place again; "table tile" then
    calibrated on whatever the instrument lay on and left it "out of the arm" for good, so
    every step but a calibration was refused for the rest of the session."""
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.CAL_PLACE: "own tile"},
                                       faults={"open": "cal_fails", "open_at": 1})
    p.drive(job.open())
    r = p.drive(job.calibrate())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "calibration_failed")
    assert job.instrument_out and job.align().reason == "instrument_not_in_the_arm"
    # the person would now answer "table tile"
    p.script[J.Confirm.CAL_PLACE] = "table tile"
    p.asked.clear()
    r = p.drive(job.calibrate())
    assert r.ok and r.detail["place"] == "own tile", (r.reason, r.detail)
    kinds = [a[1] for a in p.asked]
    assert J.Confirm.CAL_PLACE not in kinds
    assert kinds == [J.Confirm.CAL_OWN_TILE, J.Confirm.CAL_RESEAT]
    assert not job.instrument_out and job.calibration["place"] == "own tile"
    assert p.drive(job.align()).ok


def test_s1_a_stop_at_ready_after_the_failure_keeps_the_instrument_out(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.CAL_PLACE: "own tile"},
                                       faults={"open": "cal_fails", "open_at": 1})
    p.drive(job.open())
    p.drive(job.calibrate())
    p.script[J.Confirm.CAL_OWN_TILE] = "stop"
    n = len(sim.received)
    r = p.drive(job.calibrate())
    assert not r.ok and job.instrument_out and job.calibration is None
    assert job.align().reason == "instrument_not_in_the_arm"
    assert [ln for ln in sim.received[n:] if ln[1:3] in ("m0", "m1", "m2", "i1", "i0")] == []

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


# ---- (3) i1Profiler's two rows at speed 168 --------------------------------------------------

from workflow.i1io.table import geometry as geo  # noqa: E402
from workflow.i1io.table import spot as sp  # noqa: E402

#: (row start, row end, the m0 to the start, the m2) as i1Profiler sent them, serpentine
ROWS_168 = (((-1331, 1572), (1146, 1564), ";m0facd0624012cd8", ";m2047a061c00a837"),
            ((1124, 1639), (-1353, 1647), ";m004640667012c91", ";m2fab7066f00a8cb"))


@pytest.mark.parametrize("start,end,m0,m2", ROWS_168)
def test_the_two_rows_at_168_are_rebuilt_byte_for_byte_and_pass_the_allow_list(start, end, m0,
                                                                               m2):
    plan = sc.plan_row("rec", start, end, 168)
    assert (plan.A, plan.T, plan.N) == (840, 1474, 470)
    assert geo.m0_line(*start) == (m0 + "\r").encode()
    assert geo.m2_line(end[0], end[1], 168) == (m2 + "\r").encode()
    assert cl.classify((m2 + "\r").encode()) == ("m2", True, "scan move")
    sc.check_plan(plan)


def test_the_recorded_answers_of_those_rows_decode():
    d1 = tbl.parse_done_c(":$d10016D02", "d1", cl.C_DATA_LEN["scan_d1"])
    assert d1.data == "016D" and cl.C_FIXED["scan_d1"] == b";d1016d35\r"
    a3 = tbl.parse_done_c(":$a3000000348000005C200A8DC", "a3", cl.C_DATA_LEN["scan_a3"])
    A, T, V = int(a3.data[4:8], 16), int(a3.data[12:16], 16), int(a3.data[16:20], 16)
    assert (A, T, V) == (840, 1474, 168)
    assert cl.C_FIXED["scan_a3"] == b";a331\r"


def test_the_recorded_timings_of_those_rows_fit_the_apps_constants():
    # the lit data end: lamp + 2.722 / 2.721 s = 0.370 + N x 5.004 ms
    assert sc.FIRST_READING_AFTER_LAMP_S + 470 * sc.READING_S == pytest.approx(2.722, abs=0.002)
    # done after lamp + T + A: +0.456 / +0.448 s, inside what the app accepts
    for extra in (0.456, 0.448):
        assert sc.DONE_EXTRA_ACCEPT_S[0] <= extra <= sc.DONE_EXTRA_ACCEPT_S[1]
    # the m2 -> dark +0.053, lamp +0.098 / +0.101: the speed is now one of the recorded ones
    assert 168 in geo.RECORDED_M2_SPEEDS and 168 in sp.STRIP_SPEEDS
    assert sp.STRIP_SPEEDS == tuple(sorted(sp.STRIP_SPEEDS))      # slowest first, 168 last


def test_a_strip_row_may_be_read_at_168_when_no_slower_speed_fits(tmp_path, monkeypatch):
    """Slowest first: 168 is used only where every slower recorded speed breaks the readings
    rule. With the readings limit lowered for the test, only 168 keeps the row inside."""
    from tests.i1io_table.test_job_safety import shaped_sheet
    sheet = shaped_sheet([20, 20], along=12.0, w=210.0, h=297.0)    # long rows, 12 mm patches
    job0, _s, _h, _r, p0 = _job(tmp_path / "probe", sheet=sheet)
    _ready(job0, p0)
    plan = sp.plan_strip_row(job0.sheet, job0.page, 0, job0.alignment, job0._table.front_y)
    n168 = sc.plan_row("x", plan.scan.start, plan.scan.end, 168).N
    assert n168 < sc.plan_row("x", plan.scan.start, plan.scan.end, 138).N
    monkeypatch.setattr(sp, "STRIP_N_MAX", n168)
    job, sim, helper, run, p = _job(tmp_path / "run", sheet=sheet)
    _ready(job, p)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["row_kind"] == "strip", (r.reason, r.detail)
    m2 = [ln for ln in sim.received if ln.startswith(";m2")]
    assert m2 and geo.decode_xyv((m2[-1] + "\r").encode())[3] == 168


# ---- (5) the three button presses and their p1 answers ----------------------------------------

@pytest.mark.parametrize("answer,xy", [(":$p100476061D25", (1142, 1565)),
                                       (":$p100460066833", (1120, 1640)),
                                       (":$p10FABB066FE4", (-1349, 1647))])
def test_the_recorded_p1_answers_after_the_button_decode(answer, xy):
    assert cl.C_FIXED["aim"] == b";p124\r"
    assert tbl.parse_done_c(answer, "p1", cl.C_DATA_LEN["aim"]).xy() == xy
    assert "33 in all" in cl.C_RECORDED_AT["aim"]


def test_i1profilers_scans_run_through_the_recorded_aims_with_no_offset():
    """i1Profiler's aims of that night: mark 2 = row 1 col 0, mark 3 = row 1 col 23. Its row-1
    scan then started and ended 0.4 mm beyond those two points on the line through them: the
    p1 reading is the opening's target, no offset (as geometry.fit_model assumes)."""
    m2, m3 = (1120, 1640), (-1349, 1647)
    start, end = (1124, 1639), (-1353, 1647)          # i1Profiler's m0 / m2 of row 1
    L = ((m3[0] - m2[0]) ** 2 + (m3[1] - m2[1]) ** 2) ** 0.5
    u = ((m3[0] - m2[0]) / L, (m3[1] - m2[1]) / L)
    for p, q, sign in ((start, m2, -1), (end, m3, 1)):
        along = (p[0] - q[0]) * u[0] + (p[1] - q[1]) * u[1]
        across = abs((p[0] - q[0]) * u[1] - (p[1] - q[1]) * u[0])
        assert sign * along == pytest.approx(4, abs=1.5) and across <= 1.5   # 0.4 mm beyond


# ---- (4) the start-up of a just-switched-on table, as ChromIQ sent it (S1 of 17 Nov 2026) ------

from tests.i1io_table import job_harness as H  # noqa: E402
from tests.i1io_table import part_c_sim as csim  # noqa: E402

#: what the tester (ChromIQ's own code) sent after a0 answered 111800, in order
START_UP_SENT = [";i02c", ";s022", ";f42b", ";f42b", ";f42b", ";f42b", ";s022", ";p025", ";i12b",
                 ";s022"]


def test_the_recorded_start_up_answers_decode():
    tbl.parse_ack(":!i00C", "i0")
    assert tbl.parse_done(":$i00D9", "start_up").data == ""
    assert tbl.parse_done(":$p00044E001D20", "position").xy() == (1102, 29)
    lo, hi = tbl.TIME_WINDOW["start_up"]
    assert lo <= 3.088 <= hi and lo <= 3.167 <= hi
    assert tbl.START_GUARD.contains((1102, 29))


def test_the_job_sends_the_start_up_exactly_as_it_ran_on_the_real_table():
    """The table as it answered that night: i0 done after 3.088 s, the arm at (1102, 29), the
    homing 0.288 s; the job sends the same ten lines in the same order and goes on warm."""
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims(), cold=True, i0_s=3.088,
                         i0_after=(1102.0, 29.0), jitter=False)
    res, job, sim, _p = H.run_steps(["open", "start_up"], sim=sim)
    assert res[1].ok, (res[1].reason, res[1].detail)
    i = sim.received.index(";i02c")
    assert sim.received[i:i + len(START_UP_SENT)] == START_UP_SENT
    log = job.diag.lines
    assert any("i0 took 3.088 s" in ln for ln in log), [ln for ln in log if "i0" in ln]
    assert any(":$p00044E001D20" in ln for ln in log)
    assert job._table.state != "cold"

"""What the volunteer's table answered on 17 Nov 2026, as test data (owner-results fix round).

Only wire lines and numbers, nothing private (no serial, no memory block, no tile values): the
"test data" list of the analysis of that night, items 2 to 6 (item 1, m1, is in
test_ownerfix_m1_lands_where_the_real_table_put_it.py).
"""
from __future__ import annotations

import pytest

from tests.i1io_table import tester_d2 as D2
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
    """168 is used where the row's own clean border allows it. With the readings limit lowered
    for the test, only 168 keeps the row inside. 4.3.53 fix round 2: at 168 mm/s the border is
    3.0 mm, so the patches must be long (16 mm here; 12 mm until then)."""
    from tests.i1io_table.test_job_safety import shaped_sheet
    sheet = shaped_sheet([14, 14], along=16.0, w=210.0, h=297.0)    # long rows, 16 mm patches
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
    assert "45 in all" in cl.C_RECORDED_AT["aim"]


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


# ---- S-7: one arrival outside the tolerance is read once more (analysis 2, REC3) ----------------

def _offset_arrivals(sim, offsets):
    """After the first computed patch move, the next p0 answers are off by these dy values."""
    orig = sim._c_execute
    state = {"armed": False, "left": list(offsets)}

    def ex(line, cid, a, fault):
        st, data, t = orig(line, cid, a, fault)
        if cid == "m0" and line.startswith(";m0") and line not in ss_lines():
            state["armed"] = True
        elif cid == "p0" and state["armed"] and state["left"]:
            dy = state["left"].pop(0)
            x, y = int(data[:4], 16), int(data[4:8], 16)
            y = (y - 0x10000 if y & 0x8000 else y) + dy
            data = f"{x:04X}{y & 0xFFFF:04X}"
        return st, data, t
    sim._c_execute = ex
    return state


def ss_lines():
    return {v.decode().rstrip("\r") for v in tbl.WIRE.values()}


@pytest.mark.parametrize("offsets,ok,reread,closed", [
    ([-5], True, False, False), ([-6, -4], True, True, False),
    # 4.3.47 fix2 (safety review, suspect 4): read twice beside the target by at most 1 mm, the
    # step ends CLEANLY (nothing more is sent in it; the person may try again); beyond 1 mm on
    # either reading it is a doubt, as before (nothing more is sent at all)
    ([-6, -6], False, True, False), ([-10, -10], False, True, False),
    ([-11, -11], False, True, True), ([-6, -11], False, True, True),
    ([-11, -6], False, True, True), ([-40, -40], False, True, True)])
def test_an_arrival_off_by_six_is_read_once_more_before_any_doubt(tmp_path, offsets, ok,
                                                                  reread, closed):
    job, sim, helper, run, p = job_for(tmp_path)
    sim.jitter = False
    for s in ("open", "calibrate", "align"):
        assert p.drive(getattr(job, s)()).ok
    _offset_arrivals(sim, offsets)
    n = len(sim.received)
    r = p.drive(D2.check_move(job))
    assert r.ok is ok, (r.kind, r.reason)
    log = "\n".join(job.diag.lines)
    assert ("read again once" in log) is reread
    after = sim.received[n:]
    moves_after = [ln for ln in after if ln[1:3] in ("m0", "m1", "m2", "i1", "i0")]
    assert len(moves_after) == 1                       # the check move only, nothing more
    if closed:
        assert job._table.closed_reason is not None and "twice" in log
    elif not ok:
        assert job._table.closed_reason is None
        assert r.kind == "refused" and r.reason == "arrived_beside_the_target", r
        assert "the step ends cleanly" in log


# ---- analysis 2 (REC2 single scan, REC3 the first SPOT recording), test data A4 1-6 -------------

def test_a2_1_a_spot_patch_as_i1profiler_moved_it():
    rep = tbl.parse_done(":$p0003BE082C0B", "position")
    assert rep.xy() == (958, 2092)
    line = geo.m0_line(849, 2092)
    assert line == b";m00351082c012c6c\r"
    tbl.parse_ack(":!m008", "m0")
    assert tbl.parse_done_c(":$m00D5", "m0", 0).data == ""
    lo, hi = geo.move_window((958, 2092), (849, 2092))
    assert lo <= 0.480 <= hi


def test_a2_2_the_row_change_and_the_first_move_from_the_free_arm():
    assert geo.m0_line(1170, 2176) == b";m004920880012c93\r"
    lo, hi = geo.move_window((-1302, 2095), (1170, 2176))
    assert lo <= 2.239 <= hi
    assert geo.m0_line(1173, 2091) == b";m00495082b012c64\r"
    lo, hi = geo.move_window((-1211, 1865), (1173, 2091))
    assert lo <= 2.207 <= hi


def test_a2_3_i1profilers_arrival_spread_fits_the_tolerance_or_is_read_again():
    from workflow.i1io.table.job import _near
    for dx in range(-2, 4):
        for dy in range(-5, 2):
            assert _near((dx, dy), (0, 0))
    assert not _near((0, -6), (0, 0))       # read once more (S-7), the tolerance not widened


@pytest.mark.parametrize("m0,m2,start,end", [
    (";m0fae10835012c05", ";m20493083000a892", (-1311, 2101), (1171, 2096)),
    (";m00493087f012c5d", ";m2fae1088400a8fc", (1171, 2175), (-1311, 2180))])
def test_a2_4_rec2s_rows_are_rebuilt_byte_for_byte(m0, m2, start, end):
    assert geo.m0_line(*start) == (m0 + "\r").encode()
    assert geo.m2_line(end[0], end[1], 168) == (m2 + "\r").encode()
    plan = sc.plan_row("rec2", start, end, 168)
    a3 = tbl.parse_done_c(":$a3000000348000005C500A8D9", "a3", cl.C_DATA_LEN["scan_a3"])
    A, T, V = int(a3.data[4:8], 16), int(a3.data[12:16], 16), int(a3.data[16:20], 16)
    assert (A, V) == (plan.A, 168) and T == 1477
    for line, byte in ((":$c40BB57", 0xBB), (":$c40B861", 0xB8)):
        got = int(tbl.parse_done_c(line, "c4", 2).data, 16)
        assert got == byte and sc.C4_RANGE[0] <= got <= sc.C4_RANGE[1]


def test_a2_5_m1_from_far_away_is_a_plain_move_to_the_alignment_start():
    assert tbl.WIRE["m1"] == b";m10b10055b012c42\r"
    assert tbl.parse_done(":$m10D4", "m1").data == ""
    # 3,717 units in 2.751 s: the m0 profile's prediction for a move to (2507, 1429)
    assert geo.predicted_move_time((-1210, 1870), (2507, 1429)) == pytest.approx(2.751, abs=0.05)
    # the app sends m1 only from the far side (2507, 1498), where 0.400 s is recorded twice
    lo, hi = tbl.TIME_WINDOW["m1"]
    assert lo <= 0.400 <= hi
    assert geo.predicted_move_time((2507, 1498), (2507, 1429)) <= hi
    b_align = next(s for s in tbl.B_STEPS if s.key == "b_align").ops
    moves = [op for op in b_align if op[0] == "move"]
    assert moves[-1] == ("move", "m1", "m1") and moves[-2] == ("move", "to_2507", "to_2507")
    i = b_align.index(("move", "m1", "m1"))
    assert b_align[i - 1] == ("p0", "AT_2507", "at the far side")


def test_a2_6_f3_answers_01_with_the_arm_already_free_and_the_app_never_sends_it_then():
    rep = tbl.parse_done_c(":$f300178", "f3", 2)
    assert rep.data == "01"
    with pytest.raises(tbl.ProtocolError):
        tbl.parse_done(":$f300178", "f3")          # the app accepts only the recorded 00
    # the alignment start is always reached through the homing first (C_HOME then C_ALIGN), so
    # f3 is never sent with the arm free
    import inspect
    from workflow.i1io.table import job as Jm
    src = inspect.getsource(Jm.TableJob._align)
    # (4.3.52: C_HOME runs inside _home_first_or_start_homing, the START rule's wrapper)
    assert src.index("self._home_first_or_start_homing()") < src.index("self._run_b(C_ALIGN)")
    assert "self._run_b(C_HOME)" in inspect.getsource(Jm.TableJob._home_first_or_start_homing)
    assert "if not (d.arm_free is True and d.mode_on):" in src


def test_spot_rows_start_at_column_0_on_every_row():
    """S-8: as i1Profiler's spot rows (REC3: both rows column 0 -> 23, the move back 2.239 s)."""
    from tests.i1io_table.job_harness import demo_sheet, demo_aims
    from tests.i1io_table.part_c_sim import CSimTable  # noqa: F401
    sheet = demo_sheet()
    aims_mm = [tuple(sc.sheet_table_mm(sheet, a["page_mm"])) for a in sc.aims_of(sheet, 0)]
    al = geo.fit_alignment(aims_mm, demo_aims(sheet))
    for k in range(min(3, sp.rows_on_page(sheet, 0))):
        plan = sp.plan_row(sheet, 0, k, al)
        xs = [p.target[0] for p in plan.patches]
        assert xs == sorted(xs, reverse=True), k          # from the marks' end (largest X)

"""Build step 6: EVERY reviewed safety setting of tester 0.6.0's part C, carried into the app's
table job, each with its own test (NEXT_STEPS.md section 4a), plus the job's states, against the
simulator only (no hardware).

| setting (tester 0.6.0)                          | here                                         |
|-------------------------------------------------|----------------------------------------------|
| session caps (now DERIVED from the chart)        | test_caps_*                                  |
| per-stage caps and runs                          | test_the_per_step_numbers_are_the_testers,   |
|                                                  | test_a_stage_runs_at_most_as_often_as_*      |
| SPOT_ROW_PATCHES_MAX (now: the row, max 33)      | test_a_row_beyond_the_layouts_longest_*      |
| PAGE_PATCHES_MAX / PAGE_ROWS_MAX (now derived)   | test_a_page_beyond_the_layouts_densest_*     |
| CREEP_STEPS_MAX, CREEP_PAUSE_S, CREEP_STEP       | test_the_creep_*                             |
| C_HOME needs                                     | test_the_homing_needs_*                      |
| stillness before moving a free arm               | test_a_free_arm_that_moves_*                 |
| lost link: nothing more sent, state recorded     | test_a_lost_link_at_every_line_*             |
| the pending marker, read at the next start       | test_the_pending_marker_*                    |
| typed yes gates -> needs_confirmation            | test_every_confirmation_*, test_go_back_*,   |
|                                                  | test_declining_a_first_visit_*, front tests  |
"""
from __future__ import annotations

import json
import math
import re

import pytest

from core.file_manager import Run
from tests.i1io_table import job_harness as H
from tests.i1io_table import part_c_sim as csim
from workflow.i1io.table import caps as cp
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl

A = geo.MEASURING_AREA
MOTION = ("m0", "m1", "m2", "i1", "i0")


def moves(lines):
    return [x for x in lines if x[1:3] in MOTION]


def computed(lines):
    wire = {v.decode().rstrip("\r") for v in tbl.WIRE.values()}
    return [x for x in lines if x.startswith(";m0") and x not in wire]


# ---- a synthetic chart of a given shape, laid inside the area (counts AND geometry) -----------

def shaped_sheet(rows: "list[int]", pages: int = 1, along=8.9, across=7.0, w=230.0, h=320.0):
    """A side-file-like sheet: *rows* strips of n patches each, on every page, three crosses."""
    pg = []
    for _p in range(pages):
        strips = []
        sid = 1
        for k, n in enumerate(rows):
            x = 15.0 + k * across
            ys = [16.0 + i * along for i in range(n)]
            strips.append({"x_mm": x, "run_mm": [ys[0] - along, ys[-1] + along],
                           "patches": [{"loc": f"{k}-{i}", "sample_id": sid + i,
                                        "centre_mm": [x, y]} for i, y in enumerate(ys)]})
            sid += n
        aims = [{"number": 1, "corner_on_table": "top-left", "target": "cross", "patch": None,
                 "page_mm": [8.0, h - 12.0]},
                {"number": 2, "corner_on_table": "bottom-left", "target": "cross",
                 "patch": None, "page_mm": [w - 8.0, h - 12.0]},
                {"number": 3, "corner_on_table": "bottom-right", "target": "cross",
                 "patch": None, "page_mm": [w - 8.0, 12.0]}]
        pg.append({"strips": strips, "aim_points": aims})
    return {"schema": 1, "table_model": "i1iO 2", "head_model": "i1Pro 2", "paper_mm": [w, h],
            "patch_mm": [across, along], "orientation": "test", "pages": pg}


# ---- caps, derived ---------------------------------------------------------------------------

def test_the_per_step_numbers_are_the_testers():
    """Every per-step number the derived caps are built from is the tester's own (part C 0.6.0:
    OPEN_KEYS 11; b_home / b_align from the recorded step lists; D1 8/0; DZ 2x10+8 / 11;
    D2 4/1; F 8/1; D3 2n+4 / n; E2's row 12/2 and its front ends 7/2)."""
    assert cp.OPEN == (11, 0)
    assert cp.PARK == (tbl.STEP_MAX_LINES["b_home"], tbl.STEP_MAX_MOTIONS["b_home"]) == (4, 1)
    assert cp.APPROACH == (4 + tbl.STEP_MAX_LINES["b_align"], 1 + 3)
    assert (cp.AIMS, cp.CREEP, cp.CHECK_MOVE, cp.HOME) == ((8, 0), (28, 11), (4, 1), (8, 1))
    assert cp.spot_row(33) == (70, 33) and cp.STRIP_ROW == (19, 4)
    assert J.D1_CAPS == cp.AIMS and J.DZ_CAPS == cp.CREEP and J.D2_CAPS == cp.CHECK_MOVE
    assert (cp.ALLOWANCE_FRACTION, cp.ALLOWANCE_ROWS, cp.ALLOWANCE_ALIGNMENTS) == (0.10, 2, 1)


def test_caps_formula_is_the_stated_one():
    shape = cp.ChartShape(((24,) * 22,))
    c = cp.caps_for(shape)
    need = [cp.ALIGN_CYCLE[i] + 22 * cp.row_cost(24)[i] for i in (0, 1)]
    allow = [cp.ALIGN_CYCLE[i] + 2 * cp.row_cost(24)[i] + math.ceil(0.1 * need[i])
             for i in (0, 1)]
    assert (c.lines, c.moves) == (11 + 4 + need[0] + allow[0], 1 + need[1] + allow[1])


EXTREMES = {
    "densest page (990 = 30 x 33)": cp.ChartShape(((33,) * 30,)),
    "longest row (33)": cp.ChartShape(((33,),)),
    "most rows (30)": cp.ChartShape(((1,) * 30,)),
    "most pages (667, 10,000 patches)": cp.ChartShape(tuple((15,) for _ in range(666))
                                                      + ((10,),)),
    "the largest chart (105 pages of 990)": cp.ChartShape(tuple((33,) * 30
                                                                for _ in range(105))),
}


def _need(shape: cp.ChartShape) -> "tuple[int, int]":
    """What a full measurement sends at most, counted the TESTER's way: the opening, then per
    page one alignment (the recorded way out, the aims, a creep, the check move), every row read
    patch by patch (D3/D4: a reading of where the arm is, a second if free, then m0 + p0 per
    patch) or as a strip (E2: 19 / 4), and the homing at its end."""
    lines, moves = cp.OPEN[0] + cp.PARK[0], cp.PARK[1]
    for rows in shape.pages:
        lines += cp.ALIGN_CYCLE[0]
        moves += cp.ALIGN_CYCLE[1]
        for n in rows:
            lines += max(2 + 2 * n, cp.STRIP_ROW[0])
            moves += max(n, cp.STRIP_ROW[1])
    return lines, moves


@pytest.mark.parametrize("name", list(EXTREMES))
def test_caps_the_layouts_extreme_charts_are_never_refused(name):
    shape = EXTREMES[name]
    c = cp.caps_for(shape)                 # no CapsRefused
    need = _need(shape)
    assert c.lines >= need[0] and c.moves >= need[1], (name, c, need)
    # and the allowance is an allowance, not a blank cheque: at most 3 times the need (a
    # one-row page carries a whole second alignment, about 2.5 times; a full page about 1.3)
    assert c.lines <= 3 * need[0] and c.moves <= 3 * need[1], (c, need)


@pytest.mark.parametrize("shape,what", [
    (cp.ChartShape(((34,),)), "per_row"),
    (cp.ChartShape(((1,) * 31,)), "rows"),
    (cp.ChartShape(((33,) * 30 + (1,),)), "rows"),
    (cp.ChartShape(tuple((1,) for _ in range(668))), "pages"),
])
def test_a_row_or_page_beyond_the_layouts_maxima_is_refused(shape, what):
    with pytest.raises(cp.CapsRefused) as e:
        cp.caps_for(shape)
    assert e.value.reason == "chart_beyond_layout_maxima" and e.value.detail["what"] == what


def test_a_row_beyond_the_layouts_longest_row_is_refused_by_the_job():
    job, sim, _t = H.make_job(sheet=shaped_sheet([34]))
    r = H.Person(job, sim).drive(job.open())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "chart_beyond_layout_maxima")
    assert r.detail["what"] == "per_row" and sim.received == []


def test_a_page_beyond_the_layouts_densest_page_is_refused_by_the_job():
    job, sim, _t = H.make_job(sheet=shaped_sheet([30] * 31))
    r = H.Person(job, sim).drive(job.open())
    assert r.reason == "chart_beyond_layout_maxima" and sim.received == []


def test_the_caps_are_on_the_table_before_the_first_line():
    job, sim, _t = H.make_job()
    assert H.Person(job, sim).drive(job.open()).ok
    c = cp.caps_for_sheet(H.demo_sheet())
    assert job._table.c_caps == (c.lines, c.moves) and job._table.part == "C"
    assert job._table.c_gate is not None


def test_a_session_that_exceeds_its_derived_cap_is_stopped(monkeypatch):
    """Runaway protection: a session that keeps aligning and homing past its chart's caps is
    stopped by the table module's own cap check, and nothing more is sent after it."""
    sheet = shaped_sheet([1])
    monkeypatch.setitem(J.MAX_RUNS, "d1", 99)
    monkeypatch.setitem(J.MAX_RUNS, "f", 99)
    job, sim, _t = H.make_job(sheet=sheet, aims=None)
    p = H.Person(job, sim)
    sim.aims = H.demo_aims()           # the sheet's marks are not checked here: refused aims
    assert p.drive(job.open()).ok
    cap = job._table.c_caps[0]
    res = None
    for _ in range(200):
        res = p.drive(job.align())
        if res.kind == J.Kind.STOPPED:
            break
        res = p.drive(job.home())
        if res.kind == J.Kind.STOPPED:
            break
    assert res.kind == J.Kind.STOPPED and res.reason in ("session_line_cap",
                                                         "session_movement_cap")
    n = len(sim.received)
    assert n <= cap
    assert p.drive(job.home()).kind == J.Kind.REFUSED and len(sim.received) == n


def test_a_densest_page_aligns_within_its_caps_on_the_simulator():
    """The 990-patch page (30 rows of 33) on the largest sheet: opened, aligned (the creep if
    the front zone is needed), checked and homed, well inside its derived caps."""
    sheet = shaped_sheet([33] * 30)
    from workflow.i1io.table import scan as sc
    origin = (1720, 500)
    aims = [(int(round(origin[0] - 10 * u[0])), int(round(origin[1] + 10 * u[1])))
            for u in (sc.sheet_table_mm(sheet, a["page_mm"]) for a in sc.aims_of(sheet, 0))]
    res, job, sim, _p = H.run_steps(["open", "align", "check_move", "home"],
                                    sheet=sheet, aims=aims)
    kinds = [(r.step, r.kind, r.reason) for r in res]
    assert all(k != J.Kind.STOPPED for _s, k, _r in kinds), kinds
    assert res[1].ok and sim.violations == []
    assert len(sim.received) < job._table.c_caps[0]


# ---- the creep ---------------------------------------------------------------------------

def test_the_creep_numbers_are_pinned():
    assert (cp.CREEP_STEPS_MAX, cp.CREEP_PAUSE_S, geo.CREEP_STEP) == (10, 0.5, 50)
    # enough for the whole front zone: it needs at most 8 steps
    assert (geo.FRONT_CAP_Y - A.ymax) / geo.CREEP_STEP < cp.CREEP_STEPS_MAX
    assert cp.CREEP == (2 * 10 + 8, 10 + 1)


def _front_run(**kw):
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    return H.run_steps(["open", "align", "creep", "check_move", "home"],
                       script={J.Confirm.FRONT_CHOICE: "go on"}, sheet=sheet, aims=pts,
                       **kw) + (pts,)


def test_the_creep_steps_at_most_5_mm_and_never_beyond_the_confirmed_y():
    res, job, sim, person, pts = _front_run()
    assert [r.kind for r in res[:-1]] == [J.Kind.OK] * 5, [(r.step, r.reason) for r in res]
    creep = [geo.decode_xyv(x.encode() + b"\r") for x in computed(sim.received)]
    front = [c for c in creep if c[2] > A.ymax]
    ys = [A.ymax] + [c[2] for c in front]
    assert all(0 < b - a <= geo.CREEP_STEP for a, b in zip(ys, ys[1:])
               if b > a), ys
    need = res[1].detail["front_need_y"]
    assert max(c[2] for c in creep) <= need <= geo.FRONT_CAP_Y
    assert res[2].state.front_y == need
    assert sim.violations == []


def test_the_check_move_needs_the_creep_first_in_the_front_zone():
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    job, sim, _t = H.make_job(sheet=sheet, aims=pts)
    p = H.Person(job, sim, {J.Confirm.FRONT_CHOICE: "go on"})
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    n = len(sim.received)
    r = job.check_move()
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "needs_creep_first") and len(sim.received) == n


def test_the_creep_stops_at_a_mechanical_front_end_and_only_the_homing_is_left():
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    sim = csim.CSimTable(part_c=True, aims=list(pts), jitter=False)
    real = sim._c_physics
    wall = 2760

    def physics(line, cid, args):
        real(line, cid, args)
    sim._c_physics = physics
    orig_exec = sim._c_execute

    def execute(line, cid, a, fault):
        out = orig_exec(line, cid, a, fault)
        if sim.pos[1] > wall:
            sim.pos[1] = float(wall)
        return out
    sim._c_execute = execute
    job, sim, _t = H.make_job(sim=sim, sheet=sheet, aims=pts)
    p = H.Person(job, sim, {J.Confirm.FRONT_CHOICE: "go on"})
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    r = p.drive(job.creep())
    assert r.kind == J.Kind.REFUSED and r.reason == "creep_step_did_not_arrive", r
    assert r.state.only_homing and r.state.front_y is None or r.state.front_y <= wall
    n = len(sim.received)
    assert job.check_move().reason == "only_the_homing_now" and len(sim.received) == n
    assert p.drive(job.home()).ok


def test_the_creep_stops_cleanly_at_a_pause_when_asked():
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    job, sim, _t = H.make_job(sheet=sheet, aims=pts)
    p = H.Person(job, sim, {J.Confirm.FRONT_CHOICE: "go on"})
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    job.stop_at_next_pause()
    r = p.drive(job.creep())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "stopped_at_a_creep_pause")
    assert r.detail["by_person"] and r.state.front_y is not None
    assert r.way_back == J.WayBack.HOME_OFFERED
    assert p.drive(job.home()).ok


# ---- the homing's needs, the park, the stillness check ---------------------------------------

def test_the_homing_needs_are_the_testers():
    assert J.C_HOME.needs == ("warm", "homed", "b_done")
    assert J.C_HOME.ops == tbl.HOME_FIRST


def test_the_homing_needs_the_arm_out_and_the_park_needs_it_at_rest():
    job, sim, _t = H.make_job()
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok
    assert job.home().reason == "arm_not_out_on_the_table" and len(sim.received) == 11
    assert p.drive(job.park()).ok
    assert p.drive(job.align()).ok
    n = len(sim.received)
    assert job.park().reason == "arm_not_at_rest" and len(sim.received) == n


def test_the_homing_is_never_sent_from_outside_the_area():
    """Part C's F: a free arm pushed outside the measuring area is not homed (nothing moves)."""
    job, sim, _t = H.make_job()
    p = H.Person(job, sim, {J.Confirm.AIMED: "stop"})
    assert p.drive(job.open()).ok
    r = p.drive(job.align())                       # stopped by the person at the first aim
    assert r.reason == "stopped_during_the_aims" and r.state.arm_free is True
    sim.hand_to(geo.AREA_RAW.xmin - 200, 2000)
    n = len(sim.received)
    r = p.drive(job.home())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "homing_only_from_inside_the_area")
    assert moves(sim.received[n:]) == []


def test_a_far_away_arm_is_not_homed_at_the_start():
    job, sim, _t = H.make_job(pos=[1102.0, 400.0])
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok
    r = p.drive(job.park())
    assert r.kind == J.Kind.STOPPED and r.reason == "arm_not_where_expected"
    # read out on the table, nothing moved: this job sends nothing more, i1Profiler once
    assert moves(sim.received) == [] and r.way_back == J.WayBack.OPEN_I1PROFILER_ONCE


def test_a_free_arm_that_moves_between_two_readings_is_not_moved():
    """The stillness check before a computed move from a free arm (D2 and DZ)."""
    job, sim, _t = H.make_job()
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    count = {"p0": 0}
    orig = sim._command

    def command(line):
        orig(line)
        if line == ";p025":
            count["p0"] += 1
            if count["p0"] == 1:
                sim.pos = [sim.pos[0] + 30, sim.pos[1]]   # a hand still on the arm
    sim._command = command
    n = len(sim.received)
    r = p.drive(job.check_move())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "free_arm_moved_between_two_readings")
    assert moves(sim.received[n:]) == []


def test_a_stage_runs_at_most_as_often_as_the_tester_allowed_per_page():
    assert J.MAX_RUNS == {"park": 8, "d1": 5, "dz": 3, "d2": 3, "f": 8}
    job, sim, _t = H.make_job()
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok
    for _ in range(8):
        assert p.drive(job.park()).ok
    assert job.park().reason == "ran_as_often_as_allowed"


# ---- the lost link, at every line -----------------------------------------------------------

def _base_lines():
    res, job, sim, _p = H.run_steps(["open", "align", "check_move", "home"])
    return sim.received


@pytest.mark.parametrize("i", range(54))
def test_a_lost_link_at_every_line_ends_truthfully(i):
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims())
    sim.inject_at(i, "unplug")
    res, job, sim, _p = H.run_steps(["open", "align", "check_move", "home"], sim=sim)
    stop = [r for r in res if r.kind == J.Kind.STOPPED]
    assert stop, [(r.step, r.kind, r.reason) for r in res]
    r = stop[0]
    assert r.reason == "link_lost" and r.state.link_lost and r.state.sending_closed
    # nothing more was sent after the line on which the link went
    assert len(sim.received) <= i + 1
    # the way back: switch off first when a movement may be waiting, else replug is allowed
    if r.state.movement_may_be_unfinished or r.state.strip_move_may_be_pending:
        assert r.way_back == J.WayBack.LINK_LOST_SWITCH_OFF_FIRST
    else:
        assert r.way_back == J.WayBack.LINK_LOST_REPLUG
    # the state is the last READ one
    assert r.state.last_read == job._table.last_read
    assert res[-1].step == "close" and res[-1].way_back == r.way_back


def test_a_lost_link_during_the_start_up_says_switch_off_first():
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims(), cold=True)
    sim.inject_at(6, "unplug")                    # the start-up line itself
    res, job, sim, _p = H.run_steps(["open", "start_up"], sim=sim)
    r = res[1]
    assert (r.kind, r.reason) == (J.Kind.STOPPED, "link_lost")
    assert job._table.cold_failure == "link"
    assert r.way_back in (J.WayBack.LINK_LOST_SWITCH_OFF_FIRST, J.WayBack.COLD_WAY_OUT)


# ---- the pending marker ----------------------------------------------------------------------

def test_the_pending_marker_is_written_and_read_at_the_next_start(tmp_path):
    run = Run.for_dir(tmp_path / "run1")
    job, sim, _t = H.make_job(run=run, stamp="20261117-100000")
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok
    # a strip move that may be pending (the scan path's own closing reason)
    job._table.close_for_sending("a scan move may be pending")
    c = job.close()
    assert c.state.strip_move_may_be_pending and c.way_back == J.WayBack.SWITCH_OFF_PENDING
    assert run.i1io_table_pending_markers() == [run.i1io_table_pending_marker("20261117-100000")]
    # the next START: the person is asked first; "stop" opens nothing
    job2, sim2, _t2 = H.make_job(run=run, stamp="20261117-100500")
    p2 = H.Person(job2, sim2, {J.Confirm.MARKER: "stop"})
    r = p2.drive(job2.open())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "pending_marker_not_cleared")
    assert sim2.received == [] and job2._table is None
    # confirmed: acknowledged beside the marker (the marker is kept), then the opening
    job3, sim3, _t3 = H.make_job(run=run, stamp="20261117-101000")
    r = H.Person(job3, sim3).drive(job3.open())
    assert r.ok
    marker = run.i1io_table_pending_marker("20261117-100000")
    assert marker.is_file() and marker.with_suffix(".acknowledged.json").is_file()
    # a later start is not asked again
    job4, sim4, _t4 = H.make_job(run=run, stamp="20261117-101500")
    p4 = H.Person(job4, sim4)
    assert p4.drive(job4.open()).ok
    assert not any(k == J.Confirm.MARKER for _s, k, *_ in p4.asked)


def test_the_marker_name_is_the_scan_modules_and_the_runs():
    from core import file_manager as fm
    from workflow.i1io.table import scan as sc
    assert fm.I1IO_TABLE_PENDING_MARKER == sc.PENDING_MARKER


# ---- confirmations: explicit, never given by the job -----------------------------------------

def test_every_confirmation_is_asked_and_none_has_a_default():
    res, job, sim, person, _pts = _front_run()
    kinds = {k for _s, k, _d, _n, _m in person.asked}
    assert {J.Confirm.GO, J.Confirm.SHEET_LAID, J.Confirm.ARM_FELT, J.Confirm.AIMED,
            J.Confirm.FRONT_CHOICE, J.Confirm.FRONT_YES} <= kinds
    assert all(len(J.CHOICES[k]) >= 2 for k in J.CHOICES)
    src = open(J.__file__, encoding="utf-8").read()
    # the job never answers itself: only answer() continues a step, from the caller
    assert len(re.findall(r"self\._drive\(", src)) == 2      # _begin(None) and answer(value)


def test_no_question_is_asked_while_the_arm_moves():
    res, job, sim, person, _pts = _front_run()
    assert all(not moving for *_x, moving in person.asked)


def test_a_wrong_answer_is_refused_and_continues_nothing():
    job, sim, _t = H.make_job()
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok
    r = job.align()
    assert r.confirm == J.Confirm.GO
    n = len(sim.received)
    assert job.answer(J.Confirm.SHEET_LAID, "yes").reason == "not_the_confirmation_asked_for"
    assert job.answer(J.Confirm.GO, "sure").reason == "not_one_of_the_choices"
    assert job.answer(J.Confirm.GO, "").reason == "not_one_of_the_choices"
    assert len(sim.received) == n
    assert job.home().reason == "another_step_waits_for_a_confirmation"


def test_go_back_sends_nothing():
    job, sim, _t = H.make_job()
    p = H.Person(job, sim, {J.Confirm.GO: "back"})
    assert p.drive(job.open()).ok
    n = len(sim.received)
    for s in ("park", "align"):
        r = p.drive(getattr(job, s)())
        assert (r.kind, r.reason) == (J.Kind.REFUSED, "person_chose_back")
    assert len(sim.received) == n


def test_the_sheet_not_laid_sends_nothing():
    job, sim, _t = H.make_job()
    p = H.Person(job, sim, {J.Confirm.SHEET_LAID: "stop"})
    assert p.drive(job.open()).ok
    n = len(sim.received)
    assert p.drive(job.align()).reason == "sheet_not_laid" and len(sim.received) == n


@pytest.mark.parametrize("felt", ["holds", "not sure", "skip"])
def test_an_arm_not_felt_free_is_never_aimed_with(felt):
    job, sim, _t = H.make_job()
    p = H.Person(job, sim, {J.Confirm.ARM_FELT: felt})
    assert p.drive(job.open()).ok
    r = p.drive(job.align())
    assert r.reason == "arm_did_not_give_way_at_the_alignment_start"
    assert ";p124" not in sim.received
    assert not any(k == J.Confirm.AIMED for _s, k, *_ in p.asked)


def test_declining_a_first_visit_move_moves_nothing():
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    job, sim, _t = H.make_job(sheet=sheet, aims=pts)
    p = H.Person(job, sim, {J.Confirm.FRONT_CHOICE: "go on", J.Confirm.FIRST_VISIT: "no"})
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    n = len(sim.received)
    r = p.drive(job.creep())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "first_visit_declined")
    assert moves(sim.received[n:]) == []
    assert any(k == J.Confirm.FIRST_VISIT for _s, k, *_ in p.asked)


def test_the_front_choice_back_is_a_clean_stop_and_go_on_needs_its_own_yes():
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    for script, reason in (({}, "sheet_to_be_laid_further_back"),
                           ({J.Confirm.FRONT_CHOICE: "go on", J.Confirm.FRONT_YES: "no"},
                            "sheet_to_be_laid_further_back")):
        job, sim, _t = H.make_job(sheet=sheet, aims=pts)
        p = H.Person(job, sim, script)
        assert p.drive(job.open()).ok
        r = p.drive(job.align())
        assert (r.kind, r.reason) == (J.Kind.REFUSED, reason) and job.front_need is None
        assert job.creep().reason in ("needs_alignment",)


def test_the_cold_table_start_up_needs_its_yes_and_runs_once():
    res, job, sim, p = H.run_steps(["open", "start_up", "start_up"], simkw=None) if False \
        else (None, None, None, None)
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims(), cold=True)
    job, sim, _t = H.make_job(sim=sim)
    p = H.Person(job, sim)
    r = p.drive(job.open())
    assert r.ok and r.detail["table"] == "cold" and r.way_back == J.WayBack.COLD_NOT_STARTED
    assert job.align().reason == "table_not_started" and job.park().reason == \
        "table_not_started"
    r = job.start_up()
    assert r.confirm == J.Confirm.START_UP and ";i02c" not in sim.received
    r = p.drive(r)
    assert r.ok and sim.received.count(";i02c") == 1
    assert job.start_up().reason == "table_not_just_switched_on"
    assert sim.violations == []


def test_the_start_up_left_to_i1profiler_sends_nothing_more():
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims(), cold=True)
    job, sim, _t = H.make_job(sim=sim)
    p = H.Person(job, sim, {J.Confirm.START_UP: "i1profiler"})
    assert p.drive(job.open()).ok
    n = len(sim.received)
    r = p.drive(job.start_up())
    assert (r.kind, r.reason) == (J.Kind.STOPPED, "start_up_left_to_i1profiler")
    assert r.way_back == J.WayBack.COLD_NOT_STARTED and len(sim.received) == n == 6


def test_a_wrong_start_up_report_sends_nothing_more():
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims(), cold=True)
    job, sim, _t = H.make_job(sim=sim)
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok and p.drive(job.start_up()).ok
    job.report_start_up_wrong()
    n = len(sim.received)
    assert job.park().reason == "sending_closed" and len(sim.received) == n


@pytest.mark.parametrize("kind", ["late", "no_answer", "status"])
def test_a_start_up_that_does_not_end_as_recorded_stops(kind):
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims(), cold=True)
    sim.inject_at(6, kind, 30.0 if kind == "late" else 1.0)
    job, sim, _t = H.make_job(sim=sim)
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok
    r = p.drive(job.start_up())
    assert r.kind == J.Kind.STOPPED
    assert r.way_back in (J.WayBack.COLD_WAY_OUT, J.WayBack.SWITCH_OFF_UNFINISHED)
    assert job._table.cold_failure in ("outside", "no_answer", "bad_answer")
    assert len(sim.received) == 7


def test_a_wrong_report_restricts_the_sitting_to_the_homing():
    job, sim, _t = H.make_job()
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    job.restrict_to_homing("the person saw the arm do something wrong")
    n = len(sim.received)
    assert job.check_move().reason == "only_the_homing_now" and len(sim.received) == n
    assert p.drive(job.home()).ok


def test_i1profiler_started_during_the_session_stops_it():
    started = {"now": False}
    job, sim, _t = H.make_job(other_program=lambda: started["now"])
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok
    started["now"] = True
    n = len(sim.received)
    r = p.drive(job.park())
    assert (r.kind, r.reason) == (J.Kind.STOPPED, "cancelled_by_person") or \
        r.reason == "other_program_started" or r.kind == J.Kind.STOPPED
    assert len(sim.received) == n and r.state.sending_closed


# ---- cancel (the Ctrl-C equivalent) at every confirmation ---------------------------------

def test_cancel_at_every_confirmation_sends_nothing_more():
    res, job, sim, person, _pts = _front_run()
    total = len(person.asked)
    for k in range(total):
        hit = {"n": 0}

        def on_ask(pers, r, k=k, hit=hit):
            if hit["n"] == k:
                return pers.job.cancel()
            hit["n"] += 1
            return None
        sheet, pts = H.recorded_sheet("S2 684.0", 18)
        out, job2, sim2, _p = H.run_steps(["open", "align", "creep", "check_move", "home"],
                                          script={J.Confirm.FRONT_CHOICE: "go on"},
                                          on_ask=on_ask, sheet=sheet, aims=pts)
        stopped = [r for r in out if r.kind == J.Kind.STOPPED]
        assert stopped and stopped[0].reason == "cancelled_by_person", k
        # at once, not only at the close (before the opening there is nothing to close)
        assert stopped[0].state.sending_closed or job2._table is None, k
        n = len(sim2.received)
        assert job2.home().kind == J.Kind.REFUSED and len(sim2.received) == n


# ---- the simulated tables named in the brief -----------------------------------------------

def test_a_late_movement_that_still_arrives_is_a_clean_failure():
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims())
    job, sim, _t = H.make_job(sim=sim)
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    sim.inject("late", "m0", 6.0)
    r = p.drive(job.check_move())
    assert r.kind in (J.Kind.REFUSED, J.Kind.STOPPED)
    if r.kind == J.Kind.REFUSED:
        assert r.reason == "movement_late_but_arrived" and r.way_back == J.WayBack.HOME_OFFERED


@pytest.mark.parametrize("kind", ["refuse", "status"])
def test_a_refusing_table_stops_and_nothing_more_is_sent(kind):
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims())
    sim.inject(kind, "i1")
    res, job, sim, _p = H.run_steps(["open", "park", "align"], sim=sim)
    r = res[1]
    assert r.kind == J.Kind.STOPPED and r.state.sending_closed
    assert len([x for x in sim.received if x == ";i12b"]) == 1


@pytest.mark.parametrize("name", ["turned 180", "turned 90", "turned 5 degrees", "mirrored",
                                  "swapped corners"])
def test_a_turned_or_wrong_sheet_is_refused_before_any_move(name):
    from tests.i1io_table import job_wire_cases as W
    aims = W._wrong()[name]
    res, job, sim, _p = H.run_steps(["open", "align"], aims=aims)
    r = res[1]
    assert r.kind == J.Kind.REFUSED and r.reason.startswith(("aims_", "sheet_")), r.reason
    last_p1 = max(i for i, x in enumerate(sim.received) if x == ";p124")
    assert moves(sim.received[last_p1:]) == []


def test_a_sheet_that_does_not_fit_names_its_rows_and_its_marks():
    """A mark outside the area: refused with the reason, nothing moves after the aims."""
    aims = [(x, y + 600) for x, y in H.demo_aims()]
    res, job, sim, _p = H.run_steps(["open", "align"], aims=aims)
    r = res[1]
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "aims_outside_area")
    # rows of a page that fit only partly are named after a good fit
    res, job, sim, _p = H.run_steps(["open", "align"], aims=[(x - 400, y) for x, y in
                                                            H.demo_aims()])
    r = res[1]
    if r.ok:
        fit = r.detail["fit"]
        assert set(fit) >= {"spot_outside_rows", "rows_outside_list", "front_need"}


def test_states_are_the_tables_answers_only():
    res, job, sim, _p = H.run_steps(["open", "align", "check_move", "home"])
    st = res[3].state
    assert st.at_rest and st.last_read == tuple(int(v) for v in sim.pos)
    assert not st.movement_may_be_unfinished and not st.strip_move_may_be_pending
    assert res[1].state.arm_free is True and res[1].way_back == J.WayBack.HOME_OFFERED


def test_the_job_produces_no_text_for_a_person():
    """Ids only: no sentence leaves the job in a result (the later window words them)."""
    res, job, sim, person, _pts = _front_run()
    for r in res:
        for v in (r.reason, r.way_back, r.confirm or ""):
            assert " " not in v
        blob = json.dumps(r.detail, default=str)
        assert "Please" not in blob and "you " not in blob.lower()


def test_the_job_is_reached_by_nothing_in_the_app():
    import subprocess
    import sys
    code = ("import sys, main; import ui.main_window; "
            "print(any(m.startswith('workflow.i1io.table') for m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         encoding="utf-8", timeout=120, cwd=str(H.HERE.parents[1]),
                         env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"})
    assert out.stdout.strip().endswith("False"), out.stderr[-2000:]


def test_the_creep_never_takes_more_steps_than_allowed(monkeypatch):
    monkeypatch.setattr(cp, "CREEP_STEPS_MAX", 2)
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    job, sim, _t = H.make_job(sheet=sheet, aims=pts)
    p = H.Person(job, sim, {J.Confirm.FRONT_CHOICE: "go on"})
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    r = p.drive(job.creep())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "more_creep_steps_than_allowed")
    front = [x for x in computed(sim.received)
             if geo.decode_xyv(x.encode() + b"\r")[2] > A.ymax]
    assert len(front) == 2


def test_a_free_arm_pushed_outside_the_area_is_not_moved():
    job, sim, _t = H.make_job()
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    sim.hand_to(geo.AREA_RAW.xmax + 100, 1500)
    n = len(sim.received)
    r = p.drive(job.check_move())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "free_arm_outside_area")
    assert moves(sim.received[n:]) == []


def test_a_move_that_arrives_elsewhere_stops_everything():
    job, sim, _t = H.make_job()
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    sim.c_faults["arrival_off"] = 30          # the computed move lands 3 mm off
    r = p.drive(job.check_move())
    assert (r.kind, r.reason) == (J.Kind.STOPPED, "arm_not_where_expected")
    n = len(sim.received)
    assert job.home().kind == J.Kind.REFUSED and len(sim.received) == n

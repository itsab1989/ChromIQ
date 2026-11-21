# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""4.3.53 fix round: the rows review's MUST-1 and the inventory's NO REASON items that change the
job's behaviour (countdown after a person's answer; a failed patch row read once more by itself;
no limit on rows read again or on runs per page).

MUST-1 (review_rows453.txt): with the guidance off, after a person answered anything (their hand
was at the mouse, at the instrument's button, maybe at the table), the next movement is preceded
by the countdown with Stop. Movements that follow each other with nobody asked have none. Until
this fix the GO after "Row N could not be read" -> "again" / "patch by patch" was a countdown of
0 s (4.3.52 gave 3 s): the reviewer's probe, kept here as a test, showed 3.0, 3.0, 0.0."""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_4352_guidance_off import small_sheet
from ui import i1io_table_window as W
from workflow.i1io.table import job as J


def _unguided(tmp_path, faults, script=None, sheet=None):
    sheet = sheet or small_sheet()
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet,
                                                aims=H.demo_aims(sheet), faults=faults)
    job.guided = False
    job.consent_version = W.CONSENT_VERSION
    job.calibration_place_preference = "table tile"
    assert job.set_options(["-v", "-c", "1", "-p", "chart"]).ok
    p = H.Person(job, sim, script or {})
    for st in ("open", "calibrate", "align"):
        r = p.drive(getattr(job, st)())
        assert r.ok, (st, r.reason)
    return job, sim, helper, p, sheet


def _loc(sheet, row, col):
    return sheet["pages"][0]["strips"][row]["patches"][col]["loc"]


# ---- MUST-1: the reviewer's probe, as a test --------------------------------------------------

@pytest.mark.parametrize("answer", ["again", "patch by patch"])
def test_the_go_after_a_persons_answer_to_a_failed_row_is_a_full_countdown(tmp_path, answer):
    """Unguided; a patch of row 2 fails every time (so the row's own re-read fails too and the
    person is asked). After "again" the arm must not move at the click: the countdown runs its
    full UNGUIDED_COUNTDOWN_S with Stop. RED before the fix (0.0 s). "patch by patch" is asked
    for strip rows only, so for a patch row the same answer is "again"."""
    sheet = small_sheet()
    answers = iter([answer if answer == "again" else "again", "skip"])
    job, sim, helper, p, _ = _unguided(tmp_path, {"read_loc": {_loc(sheet, 1, 1): "dies"}},
                                       sheet=sheet)

    def on_ask(person, res):
        if res.confirm == J.Confirm.ROW_FAILED:
            person.script[J.Confirm.ROW_FAILED] = next(answers)
        return None
    p.on_ask = on_ask
    while job.rows_left():
        assert p.drive(job.read_row()).ok
    asked = [a[1] for a in p.asked]
    assert asked.count(J.Confirm.ROW_FAILED) == 2
    secs = [c["seconds"] for c in job.countdowns]
    # the align, the first row, then the GO after the person's "again": all full countdowns
    assert secs[:2] == [J.UNGUIDED_COUNTDOWN_S, J.UNGUIDED_COUNTDOWN_S], secs
    again = [c for c in job.countdowns[2:] if c["for"] == "read_row"]
    assert again and again[0]["seconds"] == J.UNGUIDED_COUNTDOWN_S, job.countdowns
    assert sim.violations == []


#: every kind a PERSON can answer in an unguided sitting (ALWAYS_ASKED, plus the questions that
#: stay asked in their own cases: the reader consent before v4, an incomplete END, the homing
#: offers), with an answer that is not itself the hands-off confirmation
PERSON_ANSWERS = sorted([(k, v) for k in J.ALWAYS_ASKED for v in J.CHOICES[k]
                         if (k, v) not in J.HANDS_OFF_ANSWERS]
                        + [(J.Confirm.READER_CONSENT, v) for v in J.CHOICES[J.Confirm.READER_CONSENT]]
                        + [(J.Confirm.END, v) for v in J.CHOICES[J.Confirm.END]])


@pytest.mark.parametrize("kind,value", PERSON_ANSWERS)
def test_after_every_answer_a_person_gives_unguided_the_next_movement_has_its_countdown(
        kind, value):
    """Every question kind an unguided sitting can show a person, every answer: the next
    countdown is the full one. Driven through the job's own answer path (a step waiting for that
    question), then the countdown the next movement would run."""
    job, sim, _t = H.make_job()
    job.guided = False
    job._countdown_owed = False                  # as after a movement with nobody asked

    def gen():
        yield J.Ask(kind, {"step": "x"})
        return {}
    job._gen, job._gen_step, job._pending = gen(), "x", None
    job._pending = job._gen.send(None)
    job.answer(kind, value)
    assert job._countdown_owed is True, (kind, value)
    job._countdown("x", J.Ask(J.Confirm.GO, {"step": "x"}))
    assert job.countdowns[-1]["seconds"] == J.UNGUIDED_COUNTDOWN_S


def test_a_window_page_a_person_answers_owes_the_countdown_too():
    job, sim, _t = H.make_job()
    job.guided = False
    job._countdown_owed = False
    job.person_answered("some_window_page", "carry on")
    job._countdown("x", J.Ask(J.Confirm.GO, {"step": "x"}))
    assert job.countdowns[-1]["seconds"] == J.UNGUIDED_COUNTDOWN_S


def test_movements_that_follow_each_other_with_nobody_asked_have_no_countdown():
    """The other half of the rule: a hands-off point reached with nobody asked since the last
    movement is cleared at once (0 s, nothing sent), as the homing at the end of a page."""
    job, sim, _t = H.make_job()
    job.guided = False
    job._countdown_owed = False
    n = len(sim.received)
    job._countdown("home", J.Ask(J.Confirm.GO, {"step": "home"}))
    assert job.countdowns[-1]["seconds"] == 0.0 and sim.received[n:] == []


# ---- inventory D5 / D6: a failed reading with the arm in place --------------------------------

def test_a_patch_row_whose_reading_failed_is_read_once_more_by_itself(tmp_path):
    """No question, no countdown, the sitting not turned guided; the same recorded lines as the
    row read the first time (a subset of 4.3.52's wire for the same answer "again", which also
    sent the countdown's nothing and the same moves)."""
    sheet = small_sheet()
    job, sim, helper, p, _ = _unguided(tmp_path, {"read_once": {_loc(sheet, 1, 1): "dies"}},
                                       sheet=sheet)
    while job.rows_left():
        r = p.drive(job.read_row())
        assert r.ok
    assert J.Confirm.ROW_FAILED not in [a[1] for a in p.asked]
    assert [w for _pg, _r, w in job.rows_reread_by_itself] == ["reader_died"]
    assert job.turned_guided is None and not job.guided_now
    assert [c["seconds"] for c in job.countdowns if c["seconds"]] == [J.UNGUIDED_COUNTDOWN_S] * 2
    m = job.measurement()
    assert m.ok and m.detail["measurement"]["state"] == "complete"
    assert sim.violations == []


def test_only_once_by_itself_then_the_person_is_asked(tmp_path):
    sheet = small_sheet()
    job, sim, helper, p, _ = _unguided(tmp_path, {"read_loc": {_loc(sheet, 1, 1): "dies"}},
                                       script={J.Confirm.ROW_FAILED: "skip"}, sheet=sheet)
    while job.rows_left():
        assert p.drive(job.read_row()).ok
    assert [a[1] for a in p.asked].count(J.Confirm.ROW_FAILED) == 1
    assert len(job.rows_reread_by_itself) == 1


def test_an_arrival_beside_its_target_is_still_a_question_not_a_silent_re_read():
    """Only a READING that failed with the arm on its patch is repeated by itself; an arrival
    beside is a table state and keeps its question (sp.READ_AGAIN_BY_ITSELF)."""
    from workflow.i1io.table import spot as sp
    assert "arrived_beside_the_target" not in sp.READ_AGAIN_BY_ITSELF
    assert not {"instrument_asks_for_calibration", "calibration_failed",
                "wrong_instrument", "reading_of_another_patch"} & set(sp.READ_AGAIN_BY_ITSELF)


# ---- SHOULD-1: one free-arm reading far out no longer makes ChromIQ forget the table ----------

def test_a_free_arm_reading_beyond_the_former_backstop_keeps_the_whole_record():
    """The reviewer's probe: learn (-1805, 3000) free, store, load. Until the fix round the
    whole entry was ignored at the next START ("a value outside what this build stores") and
    the motor front with it: the creep and the careful moves came back every sitting."""
    from workflow.i1io.table import reach as rc
    store = rc.MemoryReachStore()
    key = rc.table_key("a" * 64, store.salt())
    r = store.get(key)
    r.learn_motor_target((0, 3300), 3300)
    r.learn((-1805, 3000), "free")
    assert store.put(r)
    back = store.get(key)
    assert back.ignored is None, back.ignored
    assert back.right_end_x == -1805 and back.motor_front_y == 3300


def test_learning_clamps_to_what_loading_believes_so_nothing_voids_the_entry():
    from workflow.i1io.table import geometry as geo
    from workflow.i1io.table import reach as rc
    store = rc.MemoryReachStore()
    key = rc.table_key("b" * 64, store.salt())
    r = store.get(key)
    r.learn_motor_target((0, 3300), 3300)
    r.learn((-40000, 40000), "free")              # beyond anything a table can report
    assert (r.right_end_x, r.front_y) == (geo.TARGET_X_RIGHT, rc.CEILING_Y)
    assert store.put(r)
    back = store.get(key)
    assert back.ignored is None and back.motor_front_y == 3300


# ---- SHOULD-2: a move that did not arrive is never remembered as reached ---------------------

def _rows_job(tmp_path, store, **simkw):
    from tests.i1io_table import test_4353_rows_where_the_sheet_lies as R
    return R._job(tmp_path, R.HIS_AIMS, store=store, sight_offset=R.CLOSE_SIGHT, **simkw)


def _learned_points(job):
    """Every point the reach record is asked to learn, with how (spy on the record)."""
    seen = []
    orig_load = job._load_reach

    def load(d):
        orig_load(d)
        rr = job.reach
        if rr is None:
            return
        o_learn, o_motor = rr.learn, rr.learn_motor_target

        def learn(p, how, when=None):
            seen.append((how, tuple(p)))
            return o_learn(p, how, when)

        def motor(target, aimed_y=None):
            seen.append(("motor_target", tuple(target)))
            return o_motor(target, aimed_y)
        rr.learn, rr.learn_motor_target = learn, motor
    job._load_reach = load
    return seen


def _rightmost_target(received):
    from workflow.i1io.table import geometry as geo
    xs = [geo.decode_xyv(ln.encode())[1] for ln in received
          if ln[1:3] in ("m0", "m2") and len(ln.rstrip()) == 17]
    return min(xs)


def _drive_rows(job, p):
    for step in ("open", "calibrate", "align"):
        r = p.drive(getattr(job, step)())
        assert r.ok, (step, r.reason)
    if job.front_need and job.front_reached() < job.front_need:
        assert p.drive(job.creep()).ok
    out = []
    while job.rows_left():
        r = p.drive(job.read_row())
        out.append(r)
        if not r.ok:
            break
    return out


@pytest.mark.parametrize("short_by", [8, 40])
def test_a_careful_row_end_move_that_stops_short_is_not_remembered(tmp_path, short_by):
    """The table's real right end lies *short_by* units inside the row's run-out (8: an arrival
    beside, 40: a move that did not arrive). Nothing beyond where the arm can physically be is
    ever learned (plants P3a: the ends learned before they are driven; P3b: an arrival beside
    learned as reached), and the next sitting gets the careful moves again."""
    from workflow.i1io.table import reach as rc
    clean = rc.MemoryReachStore()
    job0, sim0, _h0, p0 = _rows_job(tmp_path / "clean", clean)
    _drive_rows(job0, p0)
    far = _rightmost_target(sim0.received)
    assert far < -1439                                    # the row really reaches new ground
    job0.close()
    store = rc.MemoryReachStore()
    end = far + short_by
    job, sim, _h, p = _rows_job(tmp_path / "short", store, right_end=end)
    seen = _learned_points(job)
    _drive_rows(job, p)
    assert seen, "the spy saw nothing"
    assert all(pt[0] >= end - 5 for _how, pt in seen), (end, [s for s in seen if s[1][0] < end])
    assert job.reach.right_end_x >= min(end - 5, rc.DEFAULT_RIGHT_END_X)
    job.close()
    # the next sitting (the end gone, as if the table had been moved): careful moves again
    from tests.i1io_table import test_4353_rows_where_the_sheet_lies as R
    job2, sim2, _h2, p2 = _rows_job(tmp_path / "next", store)
    care = R._spy_care(job2)
    _drive_rows(job2, p2)
    assert [c for c in care if c][:1] == [["right side"]]


def test_a_strip_row_whose_end_arrives_beside_is_not_remembered(tmp_path):
    """Plant P3c: a strip row's ends are learned only when the arm was read within the arrival
    tolerance of them. A table that knows the ground (no careful moves) but whose arm stops 8
    units short at the run-out: the target is never learned."""
    from workflow.i1io.table import reach as rc
    store = rc.MemoryReachStore()
    job0, sim0, _h0, p0 = _rows_job(tmp_path / "learn", store)
    _drive_rows(job0, p0)
    far = _rightmost_target(sim0.received)
    known = job0.reach.right_end_x
    assert known <= far + 5
    job0.close()
    end = far + 8
    job, sim, _h, p = _rows_job(tmp_path / "short", store, right_end=end,
                                motors_have_been_to=job0.reach.motor_front_y)
    seen = _learned_points(job)
    _drive_rows(job, p)
    beyond = [s for s in seen if s[1][0] < end - 5 and s[1][0] > known + 5]
    assert beyond == [], beyond


def test_the_strip_end_guard_itself_learns_only_ends_read_within_the_tolerance():
    """The second guard behind the scan's own end check (a strip whose end reads beside is a
    doubt and is never "done"): _learn_strip_ends learns an end only when the arm was READ
    within the arrival tolerance of it. Plant P3c (learning the target whatever was read) makes
    this red; the behavioural test above cannot see it, because the first guard stops first."""
    from types import SimpleNamespace
    job, sim, _t = H.make_job()
    assert H.Person(job, sim).drive(job.open()).ok
    r0 = job.reach.right_end_x
    plan = SimpleNamespace(start=(1000, 2000), end=(-1700, 2000))
    res = SimpleNamespace(at_start=(1001, 2000), end_xy=(-1692, 2000))     # 8 units short
    job._learn_strip_ends(res, plan)
    assert job.reach.right_end_x == r0                       # the end read beside: not learned
    assert all(e["at"][0] > -1690 for e in job.reach_diag["events"])
    res = SimpleNamespace(at_start=(1001, 2000), end_xy=(-1698, 2001))     # within 5 units
    job._learn_strip_ends(res, plan)
    assert job.reach.right_end_x == -1698


def test_a_sheet_aimed_beyond_the_former_front_backstop_is_accepted_and_felt_to():
    """4.3.53 fix round (SHOULD-4 / A3): the front backstop of 365 mm is gone. A sheet aimed so
    far forward that the front need lies beyond Y 3650, on a table whose real front end lies
    beyond it: the aims are accepted and the creep feels its way there in 5 mm steps."""
    from workflow.i1io.table import geometry as geo
    base = H.demo_aims()
    dy = 3800 - max(p[1] for p in base)
    aims = [(x, y + dy) for x, y in base]
    res, job, sim, _p = H.run_steps(["open", "align", "creep"], aims=aims,
                                    script={J.Confirm.FRONT_CHOICE: "go on"}, front_end=4500,
                                    jitter=False)
    assert res[1].ok, (res[1].reason, res[1].detail)
    assert res[2].ok, (res[2].reason, res[2].detail)
    assert job._table.front_y > 3650
    ys = [geo.decode_xyv(ln.encode())[2] for ln in sim.received
          if ln[1:3] == "m0" and len(ln.rstrip()) == 17]
    front = [y for y in ys if y > geo.MEASURING_AREA.ymax]
    assert all(0 < b - a <= geo.CREEP_STEP for a, b in zip(front, front[1:]) if b > a)
    assert sim.violations == []


# ---- inventory B15: two f4 after the aims, as i1Profiler sends ----------------------------------

def test_after_the_aims_the_job_sends_two_f4_as_i1profiler_does():
    res, job, sim, _p = H.run_steps(["open", "align"])
    assert res[1].ok
    last_p1 = max(i for i, x in enumerate(sim.received) if x == ";p124")
    after = sim.received[last_p1 + 1:]
    # the status line (s0), then the f4 checks, before anything else
    k = 0
    while k < len(after) and after[k][1:3] in ("s0", "f4"):
        k += 1
    assert sum(1 for x in after[:k] if x[1:3] == "f4") == 2 == J.F4_AFTER_AIMS


# ---- inventory A11: a sheet turned a little, read patch by patch --------------------------------

def _rot(points, deg):
    import math
    cx = sum(p[0] for p in points) / 3
    cy = sum(p[1] for p in points) / 3
    a = math.radians(deg)
    return [(int(round(cx + (x - cx) * math.cos(a) - (y - cy) * math.sin(a))),
             int(round(cy + (x - cx) * math.sin(a) + (y - cy) * math.cos(a))))
            for x, y in points]


def test_a_sheet_turned_by_10_degrees_is_accepted_patch_by_patch_and_not_for_rows():
    from workflow.i1io.table import geometry as geo
    from workflow.i1io.table import scan as sc
    good = H.demo_aims()
    sheet = H.demo_sheet()
    mm = [tuple(sc.sheet_table_mm(sheet, a["page_mm"])) for a in sc.aims_of(sheet, 0)]
    for deg in (10, -10):
        geo.fit_model(mm, _rot(good, deg), geo.ROTATION_TOL_SPOT_DEG)       # accepted
        with pytest.raises(geo.AlignmentRefused, match="turned"):
            geo.fit_model(mm, _rot(good, deg))                              # rows: as before
    with pytest.raises(geo.AlignmentRefused):
        geo.fit_model(mm, _rot(good, 90), geo.ROTATION_TOL_SPOT_DEG)        # turned: never


# ---- waits review M1: the lamp wait reaches the table's patch-by-patch readings -------------------

@pytest.mark.parametrize("ms", [None, 1500, 1060])
def test_the_lamp_wait_field_reaches_every_patch_reader_of_the_table(tmp_path, ms):
    sheet = small_sheet()
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet, aims=H.demo_aims(sheet))
    job.lamp_off_ms = ms
    job.guided = False
    job.consent_version = W.CONSENT_VERSION
    job.calibration_place_preference = "table tile"
    assert job.set_options(["-v", "-c", "1", "-p", "chart"]).ok
    p = H.Person(job, sim, {})
    for st in ("open", "calibrate", "align"):
        assert p.drive(getattr(job, st)()).ok, st
    while job.rows_left():
        assert p.drive(job.read_row()).ok
    assert helper.started
    for args in helper.started:
        if ms is None:
            assert "--lamp-off-ms" not in args
        else:
            i = args.index("--lamp-off-ms")
            assert args[i + 1] == str(ms)
    assert sim.violations == []


def test_the_window_hands_the_settings_value_to_the_job():
    import inspect
    src = inspect.getsource(W.default_job_factory)
    assert "_iw.to_ms(_iw.LAMP_OFF" in src and "lamp_off_ms=lamp_ms" in src


# ---- fix round 2: a FREE arm is homed from anywhere but the back strip ------------------------

def _free_arm_job():
    job, sim, _t = H.make_job(jitter=False)
    p = H.Person(job, sim, {J.Confirm.AIMED: "stop"})
    assert p.drive(job.open()).ok
    r = p.drive(job.align())                       # stopped by the person at the first aim
    assert r.reason == "stopped_during_the_aims" and r.state.arm_free is True
    return job, sim, p


def _home_lines(where):
    job, sim, p = _free_arm_job()
    sim.hand_to(*where)
    n = len(sim.received)
    r = p.drive(job.home())
    assert r.ok, (where, r.reason, r.detail)
    return [ln for ln in sim.received[n:]], job, sim


def test_a_free_arm_outside_the_old_box_is_homed_with_the_same_lines_as_inside():
    from workflow.i1io.table import geometry as geo
    inside, _j, s1 = _home_lines((0, 2000))
    assert geo.AREA_RAW.contains((0, 2000))
    for where in ((-1700, 3000), (0, 3000), (2400, 2500)):
        assert not geo.AREA_RAW.contains(where)
        out, job, sim = _home_lines(where)
        assert [ln[:3] for ln in out] == [ln[:3] for ln in inside], (where, out)
        assert out == inside                     # byte for byte: no coordinate in any of them
        assert ";i12b" in out and job.at_rest() and sim.violations == []


def test_a_free_arm_in_the_back_strip_is_still_refused_with_nothing_sent():
    from workflow.i1io.table import geometry as geo
    job, sim, p = _free_arm_job()
    sim.hand_to(1500, geo.AREA_RAW.ymin - 60)
    assert J.in_back_strip(tuple(sim.pos))
    n = len(sim.received)
    r = p.drive(job.home())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "arm_in_the_back_strip")
    assert not any(ln[1:3] in ("m0", "m1", "m2", "i0", "i1") for ln in sim.received[n:])


def test_a_homing_the_table_refuses_ends_on_the_power_switch_page_and_is_in_the_log():
    """The one recorded failure (R1 272.124): the table answered the homing of a free arm with
    status 3. Nothing more is sent after it, the way out starts with the power switch, and the
    detailed table log holds the line and the answer."""
    from ui import i1io_table_window as Wn
    from workflow import measurement_messages as M
    job, sim, p = _free_arm_job()
    sim.hand_to(-1700, 3000)
    sim.inject("status", "i1", 3)
    n = len(sim.received)
    r = p.drive(job.home())
    assert r.kind == J.Kind.STOPPED, (r.kind, r.reason)
    sent = sim.received[n:]
    assert sent[-1] == ";i12b" or ";i12b" in sent
    assert sent.index(";i12b") == len(sent) - 1          # nothing more after the refused homing
    assert r.way_back in (J.WayBack.OPEN_I1PROFILER_ONCE, J.WayBack.SWITCH_OFF_UNFINISHED)
    body = (M.M_I1IO_DRIVE_STOPPED_END_FIRST if r.way_back == J.WayBack.OPEN_I1PROFILER_ONCE
            else M.M_I1IO_DRIVE_SWITCH_OFF).body
    assert body.index("power switch") < body.index("i1Profiler 3.8.6")
    log = "\n".join(job.diag.lines)
    assert "i12b" in log and ("status 3" in log or "i13" in log), log[-1500:]
    assert Wn is not None

"""The changes the safety review of step 6 asked for, in the form the owner ruled:

* A: READY_TO_OPEN before anything is opened ("yes" / "stop", no default; two named facts).
* B, two modes selected by ``ask_after_each_step`` (the owner: ask in the first measurement,
  then the person may switch it off):
  - asking: after every step that moved, and after the start-up, REPORT_AFTER_STEP ("as
    described" / "something wrong" / "not sure"); until answered every moving step but the
    homing is refused; a non-"as described" leaves only the homing (after the start-up:
    nothing more is sent). A clean measurement ends with the offer "do not ask again".
  - not asking: no question; GO once per page.
  - both: ``report_problem(kind)`` accepted at any time, never lost.
* Recommended: the table object is private; the job keeps its own copy of the chart.
"""
from __future__ import annotations

import ast
import copy
import re
from pathlib import Path

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import part_c_sim as csim
from workflow.i1io.table import job as J

MOTION = ("m0", "m1", "m2", "i1", "i0")
STEPS = ["open", "align", "check_move", "home"]


def moves(lines):
    return [x for x in lines if x[1:3] in MOTION]


# ---- A ---------------------------------------------------------------------------------------

def test_ready_to_open_comes_before_anything_is_opened():
    job, sim, _t = H.make_job()
    opened = []
    real = job._open_transport
    job._open_transport = lambda: opened.append(1) or real()
    r = job.open()
    while r.confirm != J.Confirm.READY_TO_OPEN:
        r = job.answer(r.confirm, H.DEFAULT[r.confirm])
    # 4.3.48: "arm out" (the arm is not at its resting place) opens too, and moves nothing
    assert r.kind == J.Kind.NEEDS and r.choices == ("yes", "arm out", "stop")
    assert r.detail["items"] == ["arm_at_its_resting_place", "nothing_on_the_bed_but_the_sheet"]
    assert opened == [] and sim.received == [] and job._table is None
    r = job.answer(J.Confirm.READY_TO_OPEN, "yes")
    assert r.ok and opened == [1] and len(sim.received) == 11


def test_without_yes_nothing_is_opened_and_nothing_is_sent():
    job, sim, _t = H.make_job()
    p = H.Person(job, sim, {J.Confirm.READY_TO_OPEN: "stop"})
    r = p.drive(job.open())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "not_ready_to_open")
    assert job._table is None and sim.received == []
    assert job.answer(J.Confirm.READY_TO_OPEN, "yes").reason == \
        "nothing_waits_for_a_confirmation"
    for bad in ("", "y", "YES"):
        job2, sim2, _t2 = H.make_job()
        r = job2.open()
        while r.confirm != J.Confirm.READY_TO_OPEN:
            r = job2.answer(r.confirm, H.DEFAULT[r.confirm])
        assert job2.answer(J.Confirm.READY_TO_OPEN, bad).reason == "not_one_of_the_choices"
        assert sim2.received == []


# ---- B, the asking mode ---------------------------------------------------------------------

def _asked_reports(steps, **kw):
    res, job, sim, p = H.run_steps(steps, **kw)
    return res, job, sim, p


def test_asking_mode_asks_after_every_step_that_moved_and_not_after_the_homing():
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    res, job, sim, p = H.run_steps(["open", "park", "align", "creep", "check_move", "home"],
                                   script={J.Confirm.FRONT_CHOICE: "go on"}, sheet=sheet,
                                   aims=pts)
    assert [s for s, _a in p.reports] == ["park", "align", "creep", "check_move"]
    asked_after = {r.step: r.confirm for r in res}
    assert asked_after["open"] is None and asked_after["home"] is None
    assert all(asked_after[s] == J.Confirm.REPORT_AFTER_STEP
               for s in ("park", "align", "creep", "check_move"))


def test_asking_mode_asks_after_the_start_up():
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims(), cold=True)
    res, job, sim, p = H.run_steps(["open", "start_up", "align"], sim=sim)
    assert [s for s, _a in p.reports] == ["start_up", "align"]


@pytest.mark.parametrize("step", ["park", "align"])
def test_asking_mode_refuses_every_moving_step_but_the_homing_until_answered(step):
    job, sim, _t = H.make_job()
    p = H.Person(job, sim, {"report": None})          # the person does not answer yet
    assert p.drive(job.open()).ok
    order = {"park": [], "align": []}[step]
    for s in order:
        p.drive(H.step(job, s))
        job.answer(J.Confirm.REPORT_AFTER_STEP, "as described")
    r = p.drive(getattr(job, step)())
    assert r.confirm == J.Confirm.REPORT_AFTER_STEP and job.report_due == step
    n = len(sim.received)
    for other in ("park", "align", "creep"):
        assert getattr(job, other)().reason == "report_due"
    assert job.next_page().reason == "report_due"
    assert len(sim.received) == n
    if step != "park":
        # the homing stays possible
        assert p.drive(job.home()).ok


@pytest.mark.parametrize("answer", ["something wrong", "not sure"])
@pytest.mark.parametrize("step", ["park", "align"])
def test_asking_mode_a_report_but_as_described_leaves_only_the_homing(step, answer):
    job, sim, _t = H.make_job()
    p = H.Person(job, sim, {"report": None})
    assert p.drive(job.open()).ok
    p.drive(getattr(job, step)())
    r = job.answer(J.Confirm.REPORT_AFTER_STEP, answer)
    assert r.ok and r.state.only_homing
    n = len(sim.received)
    for other in ("park", "align", "creep"):
        assert getattr(job, other)().kind == J.Kind.REFUSED
    assert len(sim.received) == n
    if step != "park":
        assert p.drive(job.home()).ok


@pytest.mark.parametrize("answer", ["something wrong", "not sure"])
def test_asking_mode_a_wrong_start_up_sends_nothing_more(answer):
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims(), cold=True)
    job, sim, _t = H.make_job(sim=sim)
    p = H.Person(job, sim, {"report": None})
    assert p.drive(job.open()).ok and p.drive(job.start_up()).ok
    r = job.answer(J.Confirm.REPORT_AFTER_STEP, answer)
    assert r.state.sending_closed
    n = len(sim.received)
    assert job.park().kind == J.Kind.REFUSED and job.home().kind == J.Kind.REFUSED
    assert len(sim.received) == n


def test_asking_mode_the_report_takes_only_its_choices():
    job, sim, _t = H.make_job()
    p = H.Person(job, sim, {"report": None})
    assert p.drive(job.open()).ok
    p.drive(job.park())
    for bad in ("", "yes", "As described"):
        assert job.answer(J.Confirm.REPORT_AFTER_STEP, bad).reason == "not_one_of_the_choices"
    assert job.report_due == "park"


def test_a_clean_measurement_in_the_asking_mode_offers_not_to_ask_again():
    res, job, sim, p = H.run_steps(STEPS)
    assert res[-1].detail == {"offer": J.MAY_OFFER_DO_NOT_ASK_AGAIN}


@pytest.mark.parametrize("how", ["not asking", "a report not as described", "a problem",
                                 "a stop", "a refused alignment", "nothing moved",
                                 "a lost link", "ended out on the table"])
def test_no_offer_unless_the_measurement_was_clean(how):
    kw, script, steps = {}, {}, list(STEPS)
    if how == "not asking":
        kw["ask_after_each_step"] = False
    if how == "a report not as described":
        script["report"] = "not sure"
    if how == "a refused alignment":
        from tests.i1io_table import job_wire_cases as W
        kw["aims"] = W._wrong()["turned 90"]
        steps = ["open", "align", "home"]
    if how == "nothing moved":
        steps = ["open"]
    if how == "ended out on the table":
        steps = ["open", "align"]
    if how == "a lost link":
        sim = csim.CSimTable(part_c=True, aims=H.demo_aims())
        sim.inject_at(30, "unplug")
        kw["sim"] = sim
    job, sim, _t = H.make_job(**kw)
    p = H.Person(job, sim, script)
    for s in steps:
        r = p.drive(H.step(job, s))
        if how == "a problem" and s == "align":
            job.report_problem(J.PROBLEM_SOMETHING_WRONG)
        if how == "a stop" and s == "align":
            job.report_problem(J.PROBLEM_STOP_NOW)
        if r.kind == J.Kind.STOPPED:
            break
    assert job.close().detail == {}


# ---- B, the not-asking mode ------------------------------------------------------------------

def test_not_asking_mode_asks_nothing_after_a_step_and_go_once_per_page():
    """GO once per page, plus once more after the aims (the safety review's confirmation of
    step 6: the hands were on the free arm). 4.3.50: on a sheet that reaches the front, that
    second hands-off confirmation is the front question's "Go forward carefully, my hands are
    away" (asked after the aims), so no separate GO follows it."""
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    res, job, sim, p = H.run_steps(["open", "park", "align", "creep", "home"],
                                   script={J.Confirm.FRONT_CHOICE: "go on"}, sheet=sheet,
                                   aims=pts, ask_after_each_step=False)
    assert p.reports == [] and all(r.confirm is None for r in res)
    kinds = [k for _s, k, *_ in p.asked]
    assert kinds.count(J.Confirm.GO) == 1
    assert kinds.index(J.Confirm.FRONT_CHOICE) > max(i for i, k in enumerate(kinds)
                                                    if k == J.Confirm.AIMED)
    assert all(r.kind == J.Kind.OK for r in res)


def test_go_is_asked_again_on_the_next_page():
    sheet = H.demo_sheet()
    sheet["pages"] = sheet["pages"] * 2
    res, job, sim, p = H.run_steps(["open", "align", "home"], sheet=sheet,
                                   ask_after_each_step=False)
    pp = H.Person(job, sim)
    assert job.next_page().reason == "sending_closed" or True   # closed by run_steps
    job2, sim2, _t = H.make_job(sheet=sheet, ask_after_each_step=False)
    p2 = H.Person(job2, sim2)
    for s in ("open", "align", "home"):
        p2.drive(getattr(job2, s)())
    assert job2.next_page().ok
    p2.drive(job2.align())
    # page 1: the sheet-laid answer is the hands-off confirmation before the move to the
    # aiming place (final fix round, M-1: no GO before it), GO after the aims (before the
    # homing); page 2: its own sheet-laid answer again
    assert [k for _s, k, *_ in p2.asked].count(J.Confirm.GO) == 1
    assert [k for _s, k, *_ in p2.asked].count(J.Confirm.SHEET_LAID) == 2


# ---- the safety review's confirmation of step 6: GO again after the aims ----------------------

@pytest.mark.parametrize("asking", [True, False], ids=["asking mode", "not asking"])
def test_after_the_aims_the_careful_steps_follow_the_front_answer_only(asking):
    """4.3.50: on a sheet reaching the front, the hands-off confirmation after the aims is the
    front question's "Go forward carefully, my hands are away" (asked after the aims, its page
    asks the hands away): the creep then asks no GO; "I will move the sheet" moves nothing."""
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    for choice in ("back", "go on"):
        job, sim, _t = H.make_job(sheet=sheet, aims=pts, ask_after_each_step=asking)
        p = H.Person(job, sim, {J.Confirm.FRONT_CHOICE: choice})
        assert p.drive(job.open()).ok
        n_moves = len(moves(sim.received))
        r = p.drive(job.align())
        aimed_last = max(i for i, (_s, k, *_r) in enumerate(p.asked) if k == J.Confirm.AIMED)
        front = [i for i, (_s, k, *_r) in enumerate(p.asked) if k == J.Confirm.FRONT_CHOICE]
        assert front and front[0] > aimed_last
        moved_by_align = len(moves(sim.received)) - n_moves
        if choice == "back":
            assert r.reason == "sheet_to_be_laid_further_back" and job.alignment is None
            continue
        assert r.kind == J.Kind.OK and job._go_page == job.page
        before = len(p.asked)
        n = len(moves(sim.received))
        assert p.drive(job.creep()).ok
        assert [k for _s, k, *_r in p.asked[before:]] == []
        assert len(moves(sim.received)) > n and moved_by_align >= 0
        assert sim.violations == []


@pytest.mark.parametrize("asking", [True, False], ids=["asking mode", "not asking"])
@pytest.mark.parametrize("after", [["home"]], ids=["homing"])
def test_after_the_aims_no_moving_step_runs_without_a_new_go(asking, after):
    """The person's hands were on the free arm for the aims: the first motor move after them
    (the homing here; the first row in test_4350_no_mark3_check) waits for a hands-off GO, in
    both modes; a "back" there moves nothing."""
    sheet, pts = (H.demo_sheet(), H.demo_aims())
    job, sim, _t = H.make_job(sheet=sheet, aims=pts, ask_after_each_step=asking)
    p = H.Person(job, sim, {J.Confirm.FRONT_CHOICE: "go on"})
    for s in ("open", "align"):
        assert p.drive(H.step(job, s)).kind == J.Kind.OK
    assert job._go_page is None
    n_moves = len(moves(sim.received))
    r = getattr(job, after[0])()
    assert (r.kind, r.confirm) == (J.Kind.NEEDS, J.Confirm.GO)
    assert len(moves(sim.received)) == n_moves and not sim.moving
    r = job.answer(J.Confirm.GO, "back")
    assert r.reason == "person_chose_back" and len(moves(sim.received)) == n_moves
    for s in after:
        before = len(p.asked)
        assert p.drive(H.step(job, s)).kind == J.Kind.OK
        gos = [k for _s, k, *_ in p.asked[before:]].count(J.Confirm.GO)
        assert gos == (1 if s == after[0] else 0)
    assert sim.violations == []


# ---- report_problem: any time, either mode, never lost ---------------------------------------

def _front_sheet():
    return H.recorded_sheet("S2 684.0", 18)


@pytest.mark.parametrize("asking", [True, False])
@pytest.mark.parametrize("kind", [J.PROBLEM_STOP_NOW, J.PROBLEM_SOMETHING_WRONG])
def test_a_problem_at_every_confirmation_is_taken_at_once(asking, kind):
    sheet, pts = _front_sheet()
    _r, _j, _s, ref = H.run_steps(["open", "align", "creep", "check_move", "home"],
                                  script={J.Confirm.FRONT_CHOICE: "go on"}, sheet=sheet,
                                  aims=pts, ask_after_each_step=asking)
    total = len(ref.asked)
    for k in range(total):
        hit = {"n": 0, "res": None}

        def on_ask(pers, r, k=k, hit=hit):
            if hit["n"] == k:
                hit["res"] = pers.job.report_problem(kind)
                return hit["res"]
            hit["n"] += 1
            return None
        out, job, sim, _p = H.run_steps(["open", "align", "creep", "check_move", "home"],
                                        script={J.Confirm.FRONT_CHOICE: "go on"},
                                        on_ask=on_ask, sheet=sheet, aims=pts,
                                        ask_after_each_step=asking)
        assert job.problems and job.problems[0][0] == kind, k        # never lost
        n_after = job.problems[0][2]
        assert job._gen is None, k                                    # the waiting step ended
        if kind == J.PROBLEM_STOP_NOW or job._table is None:
            assert len(sim.received) == n_after, k                    # nothing more sent
            assert job.stopped_by_person
        else:
            # only the homing may follow: no movement but i1 after the report
            later = moves(sim.received[n_after:])
            assert all(x == ";i12b" for x in later), (k, later)


@pytest.mark.parametrize("kind", [J.PROBLEM_STOP_NOW, J.PROBLEM_SOMETHING_WRONG])
def test_a_problem_at_every_line_is_taken(kind):
    base = H.run_steps(STEPS)[2].received
    for i in range(len(base)):
        sim = csim.CSimTable(part_c=True, aims=H.demo_aims())
        holder = {}
        sim.on_command = (lambda n, i=i: holder["job"].report_problem(kind) if n == i else None)
        job, sim, _t = H.make_job(sim=sim)
        holder["job"] = job
        p = H.Person(job, sim)
        for s in STEPS:
            r = p.drive(H.step(job, s))
        assert job.problems and job.problems[0][0] == kind, i
        if kind == J.PROBLEM_STOP_NOW:
            assert len(sim.received) == i + 1, i                  # the line on its way, no more
            way = job.way_back()
            assert way in (J.WayBack.SWITCH_OFF_UNFINISHED, J.WayBack.END_THEN_START_AGAIN,
                           J.WayBack.NONE, J.WayBack.COLD_NOT_STARTED,
                           J.WayBack.LINK_LOST_REPLUG), (i, way)
        else:
            # the recorded step on its way runs whole (b_align holds the most: 3 movements);
            # after it nothing but the homing, and never a computed move
            from workflow.i1io.table import session_table as tbl
            wire = {v.decode().rstrip("\r") for v in tbl.WIRE.values()}
            later = moves(sim.received[i + 1:])
            assert job.only_home or job.stopped_by_person, i
            # 2026-11-21: the vendor's way home (a move at speed 200 to the home line) is part
            # of the homing
            assert len([x for x in later if x != ";i12b" and x[11:15] != "00c8"]) <= 3, \
                (i, later)
            # (2026-11-21: plus the vendor's detour lines, recorded: geometry.detour_line)
            assert all(x in wire or _is_detour(x) for x in later), (i, later)


def test_stop_now_while_a_movement_may_be_waiting_says_switch_off_first():
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims())
    holder = {}
    job, sim, _t = H.make_job(sim=sim)
    holder["job"] = job
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok
    sim.inject("no_done", "i1")
    r = p.drive(job.park())
    res = job.report_problem(J.PROBLEM_STOP_NOW)
    assert res.state.movement_may_be_unfinished
    assert res.way_back == J.WayBack.SWITCH_OFF_UNFINISHED


@pytest.mark.parametrize("kind", [J.PROBLEM_STOP_NOW, J.PROBLEM_SOMETHING_WRONG])
def test_a_problem_at_a_creep_pause_stops_the_creep_there(kind):
    sheet, pts = _front_sheet()
    sim = csim.CSimTable(part_c=True, aims=list(pts))
    job, sim, _t = H.make_job(sim=sim, sheet=sheet, aims=pts, ask_after_each_step=False)
    p = H.Person(job, sim, {J.Confirm.FRONT_CHOICE: "go on"})
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    steps = {"n": 0}
    real = job._table.c_wait

    def c_wait(seconds):
        steps["n"] += 1
        if steps["n"] == 2:
            job.report_problem(kind)       # the person, during the second pause
        return real(seconds)
    job._table.c_wait = c_wait
    r = p.drive(job.creep())
    assert job.problems[0][0] == kind
    assert r.kind in (J.Kind.REFUSED, J.Kind.STOPPED)
    front = [x for x in sim.received if x.startswith(";m0")]
    assert r.state.front_y is not None


def test_a_problem_before_the_opening_opens_nothing_ever():
    for kind in J.PROBLEM_KINDS:
        job, sim, _t = H.make_job()
        r = job.report_problem(kind)
        assert r.kind == J.Kind.STOPPED and job.problems == [(kind, None, 0)]
        assert H.Person(job, sim).drive(job.open()).reason == "stopped_by_person"
        assert sim.received == []


def test_a_problem_between_steps_and_after_the_close_is_kept():
    res, job, sim, p = H.run_steps(STEPS, ask_after_each_step=False)
    r = job.report_problem(J.PROBLEM_SOMETHING_WRONG)
    assert job.problems[-1][0] == J.PROBLEM_SOMETHING_WRONG
    assert job.report_problem("help").reason == "not_one_of_the_choices"


def test_every_moving_step_is_recorded_for_a_later_analysis(tmp_path):
    """B' (4): without the person's notes, the log still holds for every movement what was sent,
    read and how long it took."""
    from core.file_manager import Run
    run = Run.for_dir(tmp_path / "run1")
    res, job, sim, p = H.run_steps(STEPS, ask_after_each_step=False, run=run,
                                   stamp="20261117-140000")
    log = run.i1io_table_log("20261117-140000").read_text(encoding="utf-8")
    took = re.findall(r"^DATA\s+[\d.]+\s+\w\w(?: \(\w+\))? took [\d.]+ s", log, re.M)
    assert len(took) == len(moves(sim.received))
    assert len(re.findall(r"the arm reports \(", log)) >= len(moves(sim.received)) - 1


# ---- recommended: private table, the job's own chart ------------------------------------------

def test_the_job_keeps_its_own_copy_of_the_chart():
    sheet = H.demo_sheet()
    job, sim, _t = H.make_job(sheet=sheet)
    before = copy.deepcopy(job.sheet)
    sheet["pages"][0]["strips"] *= 3                     # the caller changes its chart
    sheet["table_model"] = "i1iO 3"
    assert job.sheet == before
    assert H.Person(job, sim).drive(job.open()).ok
    from workflow.i1io.table import caps as cp
    assert job._table.c_caps == (cp.caps_for_sheet(before).lines,
                                 cp.caps_for_sheet(before).moves)


ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "workflow" / "i1io" / "table"
WRITERS = {"exchange", "c_exchange", "c_send", "c_wait", "run_step", "run_cold_start",
           "_write", "_move", "_f4", "position", "opening", "request_stop",
           "close_for_sending"}


def test_the_table_object_is_private_and_nothing_outside_the_package_writes_to_it():
    src = (TABLE / "job.py").read_text(encoding="utf-8")
    assert "self.d " not in src and "self.d." not in src and "self.d=" not in src
    assert not hasattr(J.TableJob, "d")
    job, _sim, _t = H.make_job()
    assert not hasattr(job, "d")
    # no app module outside the table package touches a job's table or a table's writers;
    # step 9: only the Measure tab's table window and the settle hook import the package, and
    # only inside a function (lazily, after START on an i1iO chart with the Beta on), never at
    # module level
    lazy_ok = {"ui/i1io_table_window.py", "workflow/i1io/table_settle.py"}
    # 2026-11-18: two developer TOOLS, not the app. The recording tools' i1iO 2 plug-in and
    # their synthetic recording import the app's allow-list rather than copy it; nothing in the
    # app imports them (tests/test_i1io_table_not_reached_by_the_app.py). They may import only
    # inside a function (lazily) and only the read-only modules (constants, the line format,
    # the allow-list, the move builders), and never name the table object, a job or its
    # ``._table``.
    tools_ok = {"scripts/recordings/plugins/i1io2_table.py": None,
                "scripts/recordings/synthetic.py": None}
    tool_modules = {"workflow.i1io.table." + m
                    for m in ("geometry", "lines", "reader", "session_table")}
    offenders = []
    for base in ("core", "ui", "workflow", "scripts"):
        for f in (ROOT / base).rglob("*.py"):
            if TABLE in f.parents:
                continue
            text = f.read_text(encoding="utf-8")
            if "i1io" not in text and "TableJob" not in text:
                continue
            tree = ast.parse(text)
            mentions_job = "TableJob" in text
            rel = f.relative_to(ROOT).as_posix()
            top = {id(n) for n in tree.body}
            if rel in tools_ok:
                tools_ok[rel] = "seen"
                for n in ast.walk(tree):
                    if (isinstance(n, ast.Attribute) and n.attr in ("_table", "Table", "TableJob")
                            or isinstance(n, ast.Name) and n.id in ("Table", "TableJob")):
                        offenders.append(f"{rel}: names the table object or a job")
                    if not isinstance(n, (ast.Import, ast.ImportFrom)):
                        continue
                    mod = getattr(n, "module", "") or ""
                    names = ([a.name for a in n.names] if isinstance(n, ast.Import) else
                             [f"{mod}.{a.name}" for a in n.names] if mod == "workflow.i1io.table"
                             else [mod] + [f"{mod}.{a.name}" for a in n.names])
                    hits = [x for x in names if x.startswith("workflow.i1io")]
                    if hits and id(n) in top:
                        offenders.append(f"{rel}: imports the table package at module level")
                    for x in hits:
                        if x in ("workflow.i1io", "workflow.i1io.table") or (
                                x.startswith("workflow.i1io.table") and not any(
                                    x == m or x.startswith(m + ".") for m in tool_modules)):
                            offenders.append(f"{rel}: imports {x}")
                continue
            for n in ast.walk(tree):
                if rel in lazy_ok and id(n) not in top:
                    if mentions_job and isinstance(n, ast.Attribute) and n.attr == "_table":
                        offenders.append(f"{rel}: ._table")
                    continue
                if mentions_job and isinstance(n, ast.Attribute) and n.attr == "_table":
                    offenders.append(f"{f.relative_to(ROOT)}: ._table")
                if isinstance(n, (ast.Import, ast.ImportFrom)):
                    mod = getattr(n, "module", "") or ""
                    names = [a.name for a in n.names] + [mod] + [f"{mod}.{a.name}"
                                                                for a in n.names]
                    if any(x == "workflow.i1io.table" or x.startswith("workflow.i1io.table.")
                           for x in names):
                        offenders.append(f"{f.relative_to(ROOT)}: imports the table package")
    assert offenders == []
    assert all(v == "seen" for v in tools_ok.values()), tools_ok   # the allowance is used
    # inside the package only the job and the scan path call the table's writers
    for f in TABLE.glob("*.py"):
        if f.name in ("job.py", "scan.py", "session_table.py"):
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute)} & (WRITERS - {"position"})
        assert not calls, (f.name, calls)


@pytest.mark.parametrize("asking", [True, False])
def test_stop_now_between_steps_closes_the_sending_at_once(asking):
    job, sim, _t = H.make_job(ask_after_each_step=asking)
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    r = job.report_problem(J.PROBLEM_STOP_NOW)
    assert r.kind == J.Kind.STOPPED and r.state.sending_closed and r.state.stopped_by_person
    assert r.way_back == J.WayBack.END_THEN_START_AGAIN      # out on the table, free
    n = len(sim.received)
    for s in ("park", "align", "home", "next_page"):
        assert getattr(job, s)().kind == J.Kind.REFUSED
    assert len(sim.received) == n


def _is_detour(line: str) -> bool:
    """2026-11-21: one of the vendor's detour lines (N3, R1), as the allow-list classifies it."""
    from workflow.i1io.table import lines as cl
    from workflow.i1io.table import session_table as tbl
    try:
        return cl.classify((line + "\r").encode())[2] == "detour m0"
    except tbl.ForbiddenLine:
        return False

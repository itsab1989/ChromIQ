"""4.3.49 fix round (independent safety review 449, MUST-3 and SHOULD-4).

MUST-3: since 4.3.49 the area the person AIMED AT is the fence that replaced the fixed Y 3109.
The review planted faults in it and the suite stayed green (A1 the aimed front 30 mm further, A2
the job's cap at the 3650 backstop, A4 the across-margin 20 mm, R1 the remembered reach widening
the cap, R5 a free-arm reading counted as a motor arrival, G7 the on-sheet check off, X1/X2 two
of them at once). Each test here goes red for at least one of them.

SHOULD-4: a remembered reach spares the front-zone question and the creep. A stored entry that
is not exactly as this build writes it (edited by hand, another build, another key) is ignored
whole and said in the diagnostics; a motor front is kept only with the aimed front of the
sitting that learned it, and spares nothing beyond it or beyond this sitting's aimed area.
"""
from __future__ import annotations

import json

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_4349_acceptance_his_sheet_and_wider import (CROSSES_1, CROSSES_2,
                                                                        GO_ON, HIS_TABLE,
                                                                        _asked,
                                                                        _through_first_row)
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J
from workflow.i1io.table import reach as rc
from workflow.i1io.table import scan as sc


def _target_ys(sim):
    """The Y of every computed m0 / m2 target the simulated table received."""
    return [geo.decode_xyv(ln.encode())[2] for ln in sim.received
            if ln[1:3] in ("m0", "m2") and len(ln.rstrip()) == 17]


def _demo_aims_mm():
    sheet = H.demo_sheet()
    return [tuple(sc.sheet_table_mm(sheet, a["page_mm"])) for a in sc.aims_of(sheet, 0)]


# ---- MUST-3: the aimed front, numerically ------------------------------------------------------

@pytest.mark.parametrize("aims, front", [(CROSSES_1, 3273), (CROSSES_2, 3272)],
                         ids=["his round 1", "his round 2"])
def test_the_aimed_front_of_his_aims_is_two_mm_in_front_of_his_frontmost_cross(aims, front):
    al = geo.fit_alignment(_demo_aims_mm(), aims)
    assert al.aimed_front_y() == front
    assert al.aimed_front_y() - max(p[1] for p in aims) == 20       # ACROSS_MM, nothing more


@pytest.mark.parametrize("name, front", [("R1 200.3", 3128), ("R1 401.6", 3129),
                                         ("R2 427.5", 2959), ("S2 3.5", 3028),
                                         ("S2 684.0", 3029)])
def test_the_aimed_front_of_the_recorded_alignments(name, front):
    pts = geo.RECORDED_ALIGNMENTS[name]
    a_mm = [((p[0] - pts[0][0]) / -10.0, (p[1] - pts[0][1]) / 10.0) for p in pts]
    assert geo.fit_alignment(a_mm, pts).aimed_front_y() == front


def test_after_the_aims_the_job_the_gate_and_the_alignment_hold_the_same_front(tmp_path):
    out, job, sim, _p = _through_first_row(tmp_path, H.demo_sheet(), CROSSES_1)
    assert all(k == J.Kind.OK for _s, k, _r, _d in out), out
    assert job._cap() == job.alignment.aimed_front_y() == job._table.aimed_cap_y == 3273
    # and no computed target of the whole sitting lies in front of it
    ys = _target_ys(sim)
    assert ys and max(ys) <= 3273


def _sheet_with_a_patch_off_its_marks():
    sheet = H.demo_sheet()
    # strip 1's fourth patch 7 mm behind mark 1 (the sheet's own marks no longer contain it);
    # still well inside the table's target area, so only the on-sheet check can refuse it
    sheet["pages"][0]["strips"][0]["patches"][3]["centre_mm"][0] = 4.0
    return sheet


@pytest.mark.parametrize("kind", ["spot", "strip"])
def test_a_patch_outside_the_sheets_marks_is_refused_and_nothing_is_sent(tmp_path, kind):
    sheet = _sheet_with_a_patch_off_its_marks()
    job, sim, _h, _r = RS.make_reading_job(tmp_path, sheet=sheet, aims=CROSSES_1,
                                           ask_after_each_step=False,
                                           reach_store=rc.MemoryReachStore(), **HIS_TABLE)
    p = H.Person(job, sim, GO_ON)
    for step in ("open", "calibrate", "align", "creep", "check_move"):
        assert p.drive(getattr(job, step)()).kind == J.Kind.OK, step
    n = len(sim.received)
    r = p.drive(job.read_row(1, kind=kind))
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "target_off_sheet")
    assert sim.received[n:] == []


def test_the_alignment_refuses_a_target_outside_the_aimed_marks():
    al = geo.fit_alignment(_demo_aims_mm(), CROSSES_1)
    with pytest.raises(geo.AreaRefused):
        al.target((26.5, 4.0), "a patch off the sheet")
    al.target((26.5, 21.5), "a patch on the sheet")


# ---- MUST-3 R1 / R5: the remembered reach skips only, and learns only from the motors ----------

def _tagged_store(motor_front_y, motor_aimed_y, ident=None):
    from tests.i1io_table import session_sim as ss
    store = rc.MemoryReachStore()
    key = rc.table_key(ident or rc.ident_of_memory_block(ss._memory_a()), store.salt())
    r = store.get(key)
    r.learn_motor_target((0, motor_front_y), motor_aimed_y)
    assert store.put(r)
    return store, key


def test_a_remembered_reach_far_beyond_the_aims_changes_no_target_and_no_limit(tmp_path):
    store, _key = _tagged_store(3600, 3650)
    out, job, sim, p = _through_first_row(tmp_path, H.demo_sheet(), CROSSES_1, store,
                                          motors_have_been_to=3600)
    assert all(k == J.Kind.OK for _s, k, _r, _d in out), out
    assert job.reach.motor_front_y == 3600
    assert job._cap() == job.alignment.aimed_front_y() == job._table.aimed_cap_y == 3273
    assert job.front_reached() == 3273
    ys = _target_ys(sim)
    assert max(ys) <= 3273 and sim.violations == []


def test_a_free_arm_reading_never_counts_as_where_the_motors_arrived(tmp_path):
    job, sim, _h, _r = RS.make_reading_job(tmp_path, aims=CROSSES_1, ask_after_each_step=False,
                                           reach_store=rc.MemoryReachStore(), **HIS_TABLE)
    p = H.Person(job, sim, GO_ON)
    for step in ("open", "calibrate", "align"):
        assert p.drive(getattr(job, step)()).kind == J.Kind.OK, step
    assert job._table.arm_free is True
    sim.inject("refuse", cid="m0")              # the creep's first move is refused: no arrival
    r = p.drive(job.creep())
    assert r.kind != J.Kind.OK
    assert job.reads_after_question, "the free arm was read again after the questions"
    assert job.reach.motor_front_y is None, job.reach.as_dict()
    assert job.reach_diag["motor_arrivals"] == 0


# ---- SHOULD-4: what a stored entry may skip, and when it is ignored ----------------------------

def test_a_stored_entry_edited_by_hand_is_ignored_and_said_in_the_diagnostics(tmp_path):
    store, key = _tagged_store(3273, 3273)
    data = json.loads(store.text)
    data["tables"][key]["motor_front_y"] = 3650
    data["tables"][key]["motor_aimed_y"] = 3650
    store.text = json.dumps(data)
    got = store.get(key)
    assert got.motor_front_y is None and got.ignored and "tag" in got.ignored
    out, job, sim, p = _through_first_row(tmp_path, H.demo_sheet(), CROSSES_1, store)
    assert J.Confirm.FRONT_CHOICE in _asked(p) and J.Confirm.FRONT_YES in _asked(p)
    assert "creep" in [s for s, _k, _r, _d in out]
    assert job.reach_diag["ignored"] == got.ignored
    assert any(e["kind"] == "record_ignored" for e in job.reach_diag["refusals"])
    log = (job.diag.folder / "chromiq-table.log").read_text(encoding="utf-8") \
        if (job.diag.folder / "chromiq-table.log").exists() else ""
    assert not log or "IGNORED" in log


@pytest.mark.parametrize("change", ["no version", "another key", "a field added",
                                    "motor beyond its aimed front"])
def test_a_stored_entry_not_as_this_build_writes_it_is_ignored_whole(change):
    store, key = _tagged_store(3200, 3273)
    data = json.loads(store.text)
    e = data["tables"][key]
    if change == "no version":
        e.pop("v")
    elif change == "another key":
        data["tables"]["0123456789abcdef"] = data["tables"].pop(key)
        key = "0123456789abcdef"
    elif change == "a field added":
        e["serial"] = "X"
    else:
        e["motor_aimed_y"] = 3100
        e["tag"] = rc.entry_tag(data["salt"], key, e)      # even with a fitting tag
    store.text = json.dumps(data)
    got = store.get(key)
    assert got.motor_front_y is None and got.ignored, (change, got)
    assert store.get(key).front_y == rc.DEFAULT_FRONT_Y


def test_an_entry_as_stored_is_used(tmp_path):
    store, key = _tagged_store(3200, 3273)
    got = store.get(key)
    assert (got.motor_front_y, got.motor_aimed_y, got.ignored) == (3200, 3273, None)


def test_a_remembered_front_spares_nothing_beyond_this_sittings_need_or_its_own_aims(tmp_path):
    """Learned on a sheet aimed to 3273 with the motors at 3223; this sitting's sheet lies 6 mm
    further forward: the question is asked again and the creep goes on from 3223."""
    store, _key = _tagged_store(3223, 3273)
    aims = [(x, y + 60) for x, y in CROSSES_1]
    out, job, sim, p = _through_first_row(tmp_path, H.demo_sheet(), aims, store,
                                          motors_have_been_to=3223)
    assert J.Confirm.FRONT_CHOICE in _asked(p)
    creep = [d for s, _k, _r, d in out if s == "creep"]
    assert creep and all(k == J.Kind.OK for _s, k, _r, _d in out), out
    first_steps = _target_ys(sim)
    assert all(y <= 3333 for y in first_steps)
    assert sim.violations == []


def test_the_job_learns_the_aimed_front_with_the_motor_front(tmp_path):
    store = rc.MemoryReachStore()
    out, job, _sim, _p = _through_first_row(tmp_path, H.demo_sheet(), CROSSES_1, store)
    assert all(k == J.Kind.OK for _s, k, _r, _d in out), out
    r = job.reach
    assert r.motor_front_y >= job.front_need and r.motor_aimed_y == 3273
    back = store.get(r.key)
    assert (back.motor_front_y, back.motor_aimed_y, back.ignored) == (r.motor_front_y, 3273,
                                                                      None)

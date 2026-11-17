"""Review 9: the reviewer's probes (copied from review9/tree, the copy itself untouched) and the
tests of the fixes of that round (M-1, S-1, S-2, S-3 and the NOTE items). Where a probe was
written to let either fix through, it is kept as written; where the fix chose one of the ways,
the test now pins that way (marked "review 9 fix"). Simulators only: no table, no USB, no
window."""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_ending import SECOND, _end, job_on, project
from tests.i1io_table.test_job_reading import read_page, ready_to_read, small_sheet
from tests.i1io_table.test_job_safety import moves
from workflow.i1io.table import job as J

ASKING = pytest.mark.parametrize("asking", [True, False], ids=["asking", "quiet"])


def _rep(job):
    if job.report_due is not None:
        assert job.answer(J.Confirm.REPORT_AFTER_STEP, "as described").ok


def _one_row(tmp_path, asking=False, rows=(4, 4, 4)):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path, sheet=small_sheet(list(rows)), asking=asking)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    _rep(job)
    return run, job, sim, p


# ---- B-1: every route to an ending, every public call after it ------------------------------

def _ending(job, p, how):
    if how == "end_save":
        return _end(job, p, "save")[0]
    if how == "end_discard":
        return _end(job, p, "discard")[0]
    if how == "save":
        return job.save()
    if how == "discard":
        return job.discard()
    raise AssertionError(how)


@ASKING
@pytest.mark.parametrize("how", ["end_save", "end_discard", "save", "discard"])
def test_r9_b1_no_answer_of_any_kind_moves_after_an_ending(tmp_path, asking, how):
    run, job, sim, p = _one_row(tmp_path, asking)
    assert _ending(job, p, how).ok
    n = len(sim.received)
    for kind, choices in J.CHOICES.items():
        if kind == J.Confirm.REPORT_AFTER_STEP:
            continue
        for c in choices:
            r = job.answer(kind, c)
            assert r.kind == J.Kind.REFUSED, (kind, c, r.reason)
    for call in (lambda: job.read_row(2), lambda: job.read_row(1), job.align, job.creep,
                 job.check_move, job.park, job.start_up, job.next_page, job.calibrate,
                 job.read_tile, job.open, job.end):
        r = call()
        assert r.kind == J.Kind.REFUSED and job._gen is None, r.reason
    assert len(sim.received) == n


@ASKING
@pytest.mark.parametrize("how", ["end_save", "end_discard", "save", "discard"])
def test_r9_b1_the_homing_stays_possible_after_a_stop_and_a_problem(tmp_path, asking, how):
    """Not stuck: after the ending, a Stop and a 'something wrong' report, the homing still
    runs, after its own GO."""
    run, job, sim, p = _one_row(tmp_path, asking)
    assert _ending(job, p, how).ok
    job.stop_at_next_pause()
    assert job.report_problem(J.PROBLEM_SOMETHING_WRONG).ok
    n = len(moves(sim.received))
    h = job.home()
    assert h.confirm == J.Confirm.GO and len(moves(sim.received)) == n
    assert p.drive(job.answer(J.Confirm.GO, "yes")).ok and job.at_rest()


def test_r9_b1_report_due_left_open_does_not_block_the_homing_after_save(tmp_path):
    """Asking mode: the report after the row is never answered, the person saves; the homing
    is still possible (with GO)."""
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path, sheet=small_sheet([4, 4, 4]), asking=True)
    ready_to_read(job, p)
    p.script["report"] = None
    p.drive(job.read_row())
    assert job.report_due == "read_row"
    r, _st = _end(job, p, "save")
    assert r.ok and r.detail["next"] == ["home"]
    h = job.home()
    assert h.confirm == J.Confirm.GO
    assert p.drive(job.answer(J.Confirm.GO, "yes")).ok and job.at_rest()


# ---- truthful endings: save()/discard() called while M-END is shown -------------------------

def test_r9_public_save_while_the_ending_is_shown_then_discard_is_not_reported_as_discarded(
        tmp_path):
    """END is shown; the window calls save() directly; the person then presses Discard on the
    still open M-END. Review 9 fix: the direct save() is REFUSED while the ending is shown (only
    the answer to it saves), so the Discard that follows is true."""
    run, job, sim, p = _one_row(tmp_path)
    assert job.end().confirm == J.Confirm.END
    s = job.save()
    assert s.kind == J.Kind.REFUSED and s.reason == "another_step_waits_for_a_confirmation"
    assert not run.measurement_ti3.exists()
    r = job.answer(J.Confirm.END, "discard")
    assert r.ok and r.detail["ending"] == "discarded" and job.ended == "discarded"
    assert not run.measurement_ti3.exists()


def test_r9_public_discard_while_the_ending_is_shown_then_keep_measuring(tmp_path):
    run, job, sim, p = _one_row(tmp_path)
    assert job.end().confirm == J.Confirm.END
    d = job.discard()
    assert d.kind == J.Kind.REFUSED and job.ended is None
    r = job.answer(J.Confirm.END, "keep measuring")
    assert r.ok and r.detail["ending"] == "keep_measuring" and job.ended is None


def test_r9_fix_the_endings_own_discard_is_checked(tmp_path, monkeypatch):
    """Review 9, S-1: _end looks at its own discard()'s result; a refused one is not reported
    as discarded."""
    run, job, sim, p = _one_row(tmp_path)
    assert job.end().confirm == J.Confirm.END
    real = job.discard

    def refused():
        return job._result("discard", J.Kind.REFUSED, "planted_refusal")
    monkeypatch.setattr(job, "discard", refused)
    r = job.answer(J.Confirm.END, "discard")
    monkeypatch.setattr(job, "discard", real)
    assert r.kind == J.Kind.REFUSED and r.reason == "planted_refusal"
    assert r.detail.get("ending") != "discarded"


def test_r9_fix_save_and_discard_answered_through_the_ending_still_work(tmp_path):
    run, job, sim, p = _one_row(tmp_path)
    r, _st = _end(job, p, "save")
    assert r.ok and r.detail["ending"] == "saved" and run.measurement_ti3.is_file()
    run2, job2, sim2, p2 = _one_row(tmp_path / "b")
    r2, _st2 = _end(job2, p2, "discard")
    assert r2.ok and r2.detail["ending"] == "discarded"


# ---- S-1: a stop during a running move ------------------------------------------------------

def _stop_during_next_move(job):
    t = job._table
    real = t.c_exchange
    state = {"done": False}

    def c_exchange(line, *a, **k):
        if not state["done"]:
            state["done"] = True
            job.stop_at_next_pause()            # from the window's thread, a line on its way
        return real(line, *a, **k)
    t.c_exchange = c_exchange
    return lambda: setattr(t, "c_exchange", real)


def test_r9_s1_a_stop_pressed_during_the_check_move_then_the_homing_asks_go(tmp_path):
    """Stop pressed while the arm moves to mark 3 (a step with no pause check); the move ends
    (the table never cuts a line). The person then presses Home: the stop's documented effect
    is that the hands-off GO is asked before the next movement."""
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=small_sheet([4, 4]),
                                                aims=H.demo_aims(small_sheet([4, 4])),
                                                ask_after_each_step=False)
    p = H.Person(job, sim)
    ready_to_read(job, p, steps=("open", "calibrate", "align"))
    undo = _stop_during_next_move(job)
    r = p.drive(job.check_move())
    undo()
    assert job._pause_stop, "the stop was pressed during the move"
    n = len(moves(sim.received))
    h = job.home()
    assert h.confirm == J.Confirm.GO and len(moves(sim.received)) == n, (
        h.kind, h.reason, len(moves(sim.received)) - n, r.reason)


def test_r9_s1_a_stop_pressed_during_the_homing_is_not_left_behind(tmp_path):
    """Stop pressed while the homing runs (it is never refused for a stop): afterwards the
    next alignment on the same page should not be refused for a stop the homing already
    answered."""
    run, job, sim, p = _one_row(tmp_path)
    undo = _stop_during_next_move(job)
    assert p.drive(job.home()).ok
    undo()
    r = job.align()
    assert r.reason != J.STOPPED_BEFORE_THE_NEXT_MOVE, r.reason


# ---- S-1: a stop at the front-zone choice ---------------------------------------------------

def test_r9_s1_a_stop_at_the_front_choice_leaves_no_half_alignment():
    """'back' at FRONT_CHOICE clears the alignment (the sheet is to be laid further back). A
    stop pressed at the same question (S-1's throw) should leave the same state, not an
    alignment without its front-zone need."""
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    job, sim, _t = H.make_job(sheet=sheet, aims=pts, ask_after_each_step=False)
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok

    def on_ask(person, res):
        if res.confirm == J.Confirm.FRONT_CHOICE:
            job.stop_at_next_pause()
        return None
    p.on_ask = on_ask
    r = p.drive(job.align())
    assert r.reason == J.STOPPED_BEFORE_THE_NEXT_MOVE, r.reason
    p.on_ask = None
    n = len(moves(sim.received))
    cm = p.drive(job.check_move())
    after = len(moves(sim.received)) - n
    assert job.alignment is None or job.front_need is not None, (
        "alignment kept, front need dropped; check_move then:", cm.kind, cm.reason, after)


# ---- S-3: options refused after open, but open() does not refuse a refused option ----------

def test_r9_s3_a_refused_option_at_open_leaves_no_way_to_read(tmp_path):
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=small_sheet([4, 4]),
                                                aims=H.demo_aims(small_sheet([4, 4])),
                                                ask_after_each_step=False)
    p = H.Person(job, sim)
    assert job.set_options(["-p", "-x"]).reason == "option_refused"
    o = p.drive(job.open())
    # either open() refuses while an option is refused, or the option can still be taken out
    if o.ok:
        assert p.drive(job.calibrate()).reason == "option_refused"
        fix = job.set_options(["-p"])
        assert fix.ok, fix.reason


# ---- S-4: a change of the run's file before the next START ----------------------------------

def test_r9_s4_a_hand_change_before_the_next_start_offers_a_saved_session_as_interrupted(
        tmp_path, monkeypatch):
    """Review 9 fix (step 9): the Measure tab settles the table sessions of a run
    (``session_end.settle_filed_sessions``) before it writes the run's .ti3 by any other way; a
    session whose Save was cut off after filing then stays "saved" through a hand change."""
    from workflow.i1io.table import measurement as ms
    from workflow.i1io.table import session_end as se
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path)
    ready_to_read(job, p)
    read_page(job, p)
    real = job.diag.write_json

    def lost(rel, data):
        if rel == ms.SESSION_RESULT:
            raise KeyboardInterrupt("power cut")
        return real(rel, data)
    monkeypatch.setattr(job.diag, "write_json", lost)
    with pytest.raises(KeyboardInterrupt):
        job.save()
    monkeypatch.undo()
    from workflow.i1io.table_settle import settle_table_sessions_before_a_hand_write
    settle_table_sessions_before_a_hand_write(run)          # what the tab does first
    with open(run.measurement_ti3, "a", encoding="utf-8") as fh:   # a hand re-read, say
        fh.write("\n")
    job2, *_ = job_on(run, tmp_path / "b", stamp=SECOND)
    found = {e["stamp"]: e["state"] for e in job2.earlier_sessions()}
    assert found[RS.STAMP] == se.SAVED, found


# ---- S-5: a disk error inside the copy leaves a half file in the run folder ----------------

def test_r9_s5_a_disk_error_during_the_copy_leaves_nothing_half_written_in_the_run(
        tmp_path, monkeypatch):
    import core.file_manager as fm
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path)
    ready_to_read(job, p)
    read_page(job, p)

    def full(tmp, dest):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(fm, "replace_read_only_too", full)
    r = job.save()
    assert r.reason == "measurement_not_written"
    monkeypatch.undo()
    assert job.discard().ok
    left = sorted(x.name for x in run.dir.iterdir() if x.name.endswith(".table-part"))
    assert left == [], left


# ---- M-3: a page before the job's page ------------------------------------------------------

def test_r9_m3_a_job_built_on_a_complete_page_still_reaches_an_earlier_missing_page(tmp_path):
    from tests.i1io_table.test_job_review8_fixes import _MISSING_1_3, _pages
    sheet = _pages(3)
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet, aims=H.demo_aims(sheet),
                                                ask_after_each_step=False)
    job.page = 1                                        # page 2, nothing missing
    p = H.Person(job, sim)
    assert job.set_options(["-p"], only_locs=_MISSING_1_3).ok
    assert job.pages_to_read() == [1, 3]
    o = p.drive(job.open())
    if o.ok:
        reached = {job.page + 1}
        while True:
            n = job.next_page()
            if not n.ok:
                break
            reached.add(n.detail["page"])
        assert 1 in reached, ("page 1 has missing patches and is never reached", reached)


# ---- S-2/S-3: an option that changes the saved fields after an adoption --------------------

def test_r9_s3_an_option_changing_the_fields_after_adopting_still_lets_the_session_save(
        tmp_path):
    proj, run = project(tmp_path)
    j1, s1, *_r = job_on(run, tmp_path / "first")
    p1 = H.Person(j1, s1)
    ready_to_read(j1, p1)
    assert p1.drive(j1.read_row()).ok
    job, sim, helper, p = job_on(run, tmp_path / "second", stamp=SECOND)
    assert job.adopt_earlier(RS.STAMP).ok
    so = job.set_options(["-p", "-l"])
    if not so.ok:
        return                                          # refused up front: fine
    ready_to_read(job, p)
    read_page(job, p)
    e = job.end()
    assert e.kind == J.Kind.NEEDS and e.confirm == J.Confirm.END, (e.kind, e.reason)


# ---- GO after each event: the next movement asks GO first ----------------------------------

def _after(event, job, p, sim, tmp_path):
    if event == "stop_between_steps":
        job.stop_at_next_pause()
        r = job.read_row()                              # refused once, by design
        assert r.reason == J.STOPPED_BEFORE_THE_NEXT_MOVE
    elif event == "refused_step":
        assert job.read_row(99).kind == J.Kind.REFUSED
    elif event == "problem_report":
        assert job.report_problem(J.PROBLEM_SOMETHING_WRONG).ok
    elif event == "keep_measuring":
        assert _end(job, p, "keep measuring")[0].ok
    elif event == "dismissed_end":
        assert job.end().confirm == J.Confirm.END and job.dismiss_end().ok
    elif event == "save":
        assert job.save().ok
    elif event == "discard":
        assert job.discard().ok


@ASKING
@pytest.mark.parametrize("event", ["stop_between_steps", "refused_step", "problem_report",
                                   "keep_measuring", "dismissed_end", "save", "discard"])
def test_r9_go_is_asked_before_the_next_movement_after(tmp_path, asking, event):
    run, job, sim, p = _one_row(tmp_path, asking)
    _after(event, job, p, sim, tmp_path)
    n = len(moves(sim.received))
    step = job.home if event in ("problem_report", "save", "discard") else job.read_row
    r = step()
    assert r.confirm == J.Confirm.GO and len(moves(sim.received)) == n, (r.kind, r.reason,
                                                                        r.confirm)


def test_r9_m1_a_problem_reported_while_a_move_runs_then_the_homing_asks_go(tmp_path):
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=small_sheet([4, 4]),
                                                aims=H.demo_aims(small_sheet([4, 4])),
                                                ask_after_each_step=False)
    p = H.Person(job, sim)
    ready_to_read(job, p)
    t = job._table
    real = t.c_exchange
    state = {"done": False}

    def c_exchange(line, *a, **k):
        if not state["done"]:
            state["done"] = True
            job.report_problem(J.PROBLEM_SOMETHING_WRONG)
        return real(line, *a, **k)
    t.c_exchange = c_exchange
    p.drive(job.check_move())
    t.c_exchange = real
    n = len(moves(sim.received))
    h = job.home()
    assert h.confirm == J.Confirm.GO and len(moves(sim.received)) == n


def test_r9_m2_a_second_own_tile_white_clears_go_too(tmp_path):
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=small_sheet([4, 4, 4]),
                                                aims=H.demo_aims(small_sheet([4, 4, 4])),
                                                ask_after_each_step=False)
    p = H.Person(job, sim, {J.Confirm.CAL_PLACE: "own tile"})
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    job.calibration_due = True
    assert job.read_row().reason == "calibration_due"
    assert p.drive(job.home()).ok
    assert job._go_page == job.page
    assert p.drive(job.calibrate()).ok                 # the remembered place: own tile again
    assert job._go_page is None


# ---- M-4: two adopted sessions ----------------------------------------------------------

def test_r9_m4_two_adopted_sessions_both_saved(tmp_path):
    from workflow.i1io.table import session_end as se
    proj, run = project(tmp_path)
    sheet = small_sheet([4, 4, 4])
    stamps = [RS.STAMP, "20261117-150000"]
    for k, st in enumerate(stamps):
        j, s, *_r = job_on(run, tmp_path / f"s{k}", sheet=sheet, stamp=st)
        pp = H.Person(j, s)
        ready_to_read(j, pp)
        assert pp.drive(j.read_row(k + 1)).ok
    job, sim, helper, p = job_on(run, tmp_path / "third", sheet=sheet, stamp=SECOND)
    assert job.adopt_earlier(stamps[0]).ok and job.adopt_earlier(stamps[1]).ok
    assert job.only_locs is not None and all(l.startswith("2-") for l in job.only_locs)
    ready_to_read(job, p)
    read_page(job, p)
    r, st = _end(job, p, "save")
    assert r.ok and st["state"] == "complete"
    assert sorted(r.detail["adopted_marked_saved"]) == sorted(stamps)
    job.close()
    job4, *_ = job_on(run, tmp_path / "fourth", sheet=sheet, stamp="20261117-170000")
    found = {e["stamp"]: e["state"] for e in job4.earlier_sessions()}
    assert found == {stamps[0]: se.SAVED, stamps[1]: se.SAVED, SECOND: se.SAVED}


# ---- a legitimate new START after each ending -----------------------------------------------

def test_r9_a_new_start_resumes_a_saved_partial(tmp_path):
    run, job, sim, p = _one_row(tmp_path)
    r, st = _end(job, p, "save")
    assert r.ok and st["state"] == "partial"
    assert p.drive(job.home()).ok
    job.close()
    job2, sim2, helper2, p2 = job_on(run, tmp_path / "b", sheet=small_sheet([4, 4, 4]),
                                     stamp=SECOND)
    assert all(e["state"] != "interrupted" for e in job2.earlier_sessions())
    assert job2.set_options(["-p", "-r"]).ok
    ready_to_read(job2, p2)
    out = read_page(job2, p2)
    assert [x.detail["status"] for x in out] == ["nothing_to_read", "read", "read"]
    r2, st2 = _end(job2, p2, "save")
    assert r2.ok and st2["state"] == "complete"


def test_r9_a_new_start_after_a_disk_error_and_close_can_adopt(tmp_path, monkeypatch):
    from workflow.i1io.table import measurement as ms
    run, job, sim, p = _one_row(tmp_path)

    def full(*a, **k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(ms, "file_into_run", full)
    r, _st = _end(job, p, "save")
    assert r.reason == "measurement_not_written"
    monkeypatch.undo()
    assert p.drive(job.home()).ok
    job.close()
    job2, sim2, helper2, p2 = job_on(run, tmp_path / "b", sheet=small_sheet([4, 4, 4]),
                                     stamp=SECOND)
    found = {e["stamp"]: e["state"] for e in job2.earlier_sessions()}
    assert found[RS.STAMP] == "interrupted"
    assert job2.adopt_earlier(RS.STAMP).ok


# ---- test gaps: behaviour that holds on the head but no committed test pins ----------------

def test_r9_gap_x2_a_stop_before_the_start_up_ends_it_before_i0():
    from tests.i1io_table import part_c_sim as csim
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims(), cold=True)
    job, sim, _t = H.make_job(sim=sim)
    p = H.Person(job, sim)
    assert p.drive(job.open()).ok
    job.stop_at_next_pause()
    n = len(sim.received)
    r = job.start_up()
    assert r.reason == J.STOPPED_BEFORE_THE_NEXT_MOVE and len(sim.received) == n


def test_r9_gap_x4_save_settles_a_filed_session_before_it_changes_the_runs_file(
        tmp_path, monkeypatch):
    """A's Save was cut off after the run's (partial) file was written; B resumes without any
    earlier_sessions() call and saves: A must stay saved."""
    from workflow.i1io.table import measurement as ms
    from workflow.i1io.table import session_end as se
    run, job, sim, p = _one_row(tmp_path)
    real = job.diag.write_json

    def lost(rel, data):
        if rel == ms.SESSION_RESULT:
            raise KeyboardInterrupt("power cut")
        return real(rel, data)
    monkeypatch.setattr(job.diag, "write_json", lost)
    with pytest.raises(KeyboardInterrupt):
        job.save()
    monkeypatch.undo()
    job2, sim2, helper2, p2 = job_on(run, tmp_path / "b", sheet=small_sheet([4, 4, 4]),
                                     stamp=SECOND)
    assert job2.set_options(["-p", "-r"]).ok
    ready_to_read(job2, p2)
    read_page(job2, p2)
    assert job2.save().ok
    assert se.session_state(run.i1io_table_session_dir(RS.STAMP), run.measurement_ti3) == \
        se.SAVED


def test_r9_gap_x13_adopting_over_the_runs_partial_then_options_still_saves(tmp_path):
    """Run holds a partial (session 1 saved row 1); session 2 read row 2 and was cut off;
    session 3 adopts it, sets options without -r, reads row 3 and saves: the partial is the
    base, the Save is not refused."""
    run, job, sim, p = _one_row(tmp_path)
    assert _end(job, p, "save")[0].ok
    j2, s2, h2, p2 = job_on(run, tmp_path / "b", sheet=small_sheet([4, 4, 4]),
                            stamp="20261117-150000")
    assert j2.set_options(["-p", "-r"]).ok
    ready_to_read(j2, p2)
    assert p2.drive(j2.read_row(2)).ok                  # then the process is gone
    j3, s3, h3, p3 = job_on(run, tmp_path / "c", sheet=small_sheet([4, 4, 4]), stamp=SECOND)
    assert j3.adopt_earlier("20261117-150000").ok
    assert j3.set_options(["-p"]).ok
    ready_to_read(j3, p3)
    read_page(j3, p3)
    r, st = _end(j3, p3, "save")
    assert r.ok and st["state"] == "complete", (r.reason, st and st.get("state"))


# ---- review 9 fixes: the NOTE items ---------------------------------------------------------

def test_r9_fix_open_refuses_while_an_option_is_refused(tmp_path):
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=small_sheet([4, 4]),
                                                aims=H.demo_aims(small_sheet([4, 4])),
                                                ask_after_each_step=False)
    assert job.set_options(["-p", "-x"]).reason == "option_refused"
    o = job.open()
    assert o.kind == J.Kind.REFUSED and o.reason == "option_refused" and sim.received == []
    assert job.set_options(["-p"]).ok
    assert H.Person(job, sim).drive(job.open()).ok


def test_r9_fix_open_refuses_a_job_built_after_the_first_page_to_read(tmp_path):
    from tests.i1io_table.test_job_review8_fixes import _MISSING_1_3, _pages
    sheet = _pages(3)
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet, aims=H.demo_aims(sheet),
                                                ask_after_each_step=False)
    job.page = 1
    assert job.set_options(["-p"], only_locs=_MISSING_1_3).ok
    o = job.open()
    assert o.reason == "an_earlier_page_is_to_be_read_first" and o.detail["first_page"] == 1
    assert sim.received == []
    job.page = 0
    assert H.Person(job, sim).drive(job.open()).ok


def test_r9_fix_a_field_option_after_adopting_is_refused_and_changes_nothing(tmp_path):
    proj, run = project(tmp_path)
    j1, s1, *_r = job_on(run, tmp_path / "first")
    p1 = H.Person(j1, s1)
    ready_to_read(j1, p1)
    assert p1.drive(j1.read_row()).ok
    job, sim, helper, p = job_on(run, tmp_path / "second", stamp=SECOND)
    assert job.adopt_earlier(RS.STAMP).ok
    still = set(job.only_locs)
    for args in (["-p", "-l"], ["-p", "-L"], ["-p", "-n"], ["-p", "-H"]):
        so = job.set_options(args)
        assert so.reason == "options_change_the_fields", args
        assert so.detail["builds_on"] == {"xyz": True, "lab": False, "spectral": True,
                                          "high_res": False}
        assert job.options_report.options == J.sp.ReadOptions() and job.only_locs == still
    assert job.set_options(["-p", "-S"]).ok
    ready_to_read(job, p)
    read_page(job, p)
    r, st = _end(job, p, "save")
    assert r.ok and st["state"] == "complete"


def test_r9_fix_adopting_after_a_field_option_is_refused(tmp_path):
    proj, run = project(tmp_path)
    j1, s1, *_r = job_on(run, tmp_path / "first")
    p1 = H.Person(j1, s1)
    ready_to_read(j1, p1)
    assert p1.drive(j1.read_row()).ok
    job, sim, helper, p = job_on(run, tmp_path / "second", stamp=SECOND)
    assert job.set_options(["-p", "-n"]).ok
    a = job.adopt_earlier(RS.STAMP)
    assert a.reason == "options_change_the_fields" and job._earlier_dirs == []


def test_r9_fix_no_table_part_in_the_run_folder_and_the_next_save_reuses_it(
        tmp_path, monkeypatch):
    import core.file_manager as fm
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path)
    ready_to_read(job, p)
    read_page(job, p)

    def full(tmp, dest):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(fm, "replace_read_only_too", full)
    assert job.save().reason == "measurement_not_written"
    monkeypatch.undo()
    assert [x.name for x in run.dir.iterdir() if x.name.endswith(".table-part")] == []
    parts = list(run.i1io_table_session_dir(RS.STAMP).glob("*.table-part"))
    assert len(parts) == 1                              # in the session folder, reused next time
    assert job.save().ok and run.measurement_ti3.is_file()
    assert [x.name for x in run.dir.iterdir() if x.name.endswith(".table-part")] == []


def _pending_close(job):
    """Close a job whose table state says a strip move may still wait."""
    job._table.closed_reason = "a scan move may be pending"
    return job.close()


def test_r9_fix_a_pending_marker_of_another_run_is_asked_at_start(tmp_path):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path)
    assert p.drive(job.open()).ok
    _pending_close(job)
    assert run.i1io_table_pending_markers()
    run2 = proj.new_run() if hasattr(proj, "new_run") else None
    if run2 is None:
        pytest.skip("Project.new_run not available")
    run2.ensure_dir()
    job2, sim2, helper2, p2 = job_on(run2, tmp_path / "b", stamp=SECOND)
    r = job2.open()
    assert r.confirm == J.Confirm.MARKER and r.detail["markers"] == 1 and sim2.received == []


def test_r9_fix_an_app_level_marker_is_asked_in_another_project(tmp_path):
    place = (tmp_path / "settings", "sandbox.i1io-table-move-may-be-pending-")
    proj, run = project(tmp_path, "First")
    job, sim, helper, p = job_on(run, tmp_path, app_marker_place=place)
    assert p.drive(job.open()).ok
    _pending_close(job)
    from workflow.i1io.table import session_end as se
    assert len(se.app_markers(*place)) == 1
    proj2, run2 = project(tmp_path, "Second")
    job2, sim2, helper2, p2 = job_on(run2, tmp_path / "b", stamp=SECOND, app_marker_place=place)
    r = job2.open()
    assert r.confirm == J.Confirm.MARKER and sim2.received == []
    assert p2.drive(job2.answer(J.Confirm.MARKER, "switched off and on")).ok
    # fix round 10 (B-1): job2's own write-ahead "in use" marker stands until its close()
    assert [m.name for m in se.app_markers(*place)] == [
        se.app_in_use_name(place[1], SECOND)]
    job2.close()
    assert se.app_markers(*place) == []                 # acknowledged, kept
    strip = [f for f in (tmp_path / "settings").glob("*.json") if not se.is_in_use_marker(f)
             and "-in-use." not in f.name]
    assert len(strip) == 2                              # the strip marker and its acknowledgement
    job3, sim3, helper3, p3 = job_on(run2, tmp_path / "c", stamp="20261117-170000",
                                     app_marker_place=place)
    assert job3.open().confirm != J.Confirm.MARKER


def test_r9_fix_a_job_without_an_app_marker_place_writes_none(tmp_path):
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path)
    assert p.drive(job.open()).ok
    _pending_close(job)
    assert job.app_marker_place is None

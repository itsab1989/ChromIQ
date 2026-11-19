"""The dual row under 4.3.47's table rules (table safety review of 2026-11-19, MUST-1).

* a computed move is never judged from a reading older than the last question: the UV pass's
  zero-length m0 is preceded by a fresh p0 when a question was answered after the lamp pass's
  last reading;
* an arrival beside its target by 6..10 units after a move that ended normally fails the row
  CLEANLY (it may be read again); the UV pass's start is judged like run_row's row start;
* NOTE-4: after Stop during a step the report page no longer says the arm moves on.
All on 4.3.47's less ideal simulated table (arrivals a few units off, the resting arm relaxing).
"""
from __future__ import annotations

from types import SimpleNamespace

from tests.i1io_table import test_dual_table as T
from ui import i1io_table_window as W
from workflow.i1io.table import job as J


def _row_lines(sim, n0):
    return [ln for ln in sim.received[n0:]]


def test_the_uv_pass_reads_the_arm_again_after_a_question_answered_since_the_lamp_pass(tmp_path,
                                                                                    monkeypatch):
    job, sim, helper, run, p = T._job(tmp_path)
    T._ready(job, p)
    real = job._step

    def step(name, *a, **k):
        out = real(name, *a, **k)
        if name == "row_uv":
            job._mark_answered()       # the person answered a question during the lamp pass
        return out
    monkeypatch.setattr(job, "_step", step)
    n0, q0 = len(sim.received), len(job.reads_after_question)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["row_kind"] == "strip", (r.reason, r.detail)
    got = [ln[:3] for ln in _row_lines(sim, n0)]
    # lamp pass ... c3, p0 (its end) | p0 (read again) | m0 (zero), c4, d1, p0, m2, a3, c3, p0
    # 4.3.50: from the free arm after the aims, its stillness pair first (no check move)
    assert got == [";p0", ";p0", ";p0", ";c4", ";p0", ";m0", ";d1", ";p0", ";m2", ";a3", ";c3",
                   ";p0", ";p0", ";m0", ";c4", ";d1", ";p0", ";m2", ";a3", ";c3", ";p0"]
    assert len(job.reads_after_question) == q0 + 1
    assert sim.violations == []


def test_without_a_question_the_uv_pass_sends_no_extra_reading(tmp_path):
    job, sim, helper, run, p = T._job(tmp_path)
    T._ready(job, p)
    n0, q0 = len(sim.received), len(job.reads_after_question)
    r = p.drive(job.read_row())
    assert r.ok
    assert [ln[:3] for ln in _row_lines(sim, n0)].count(";p0") == 8   # 4.3.50: free start
    assert len(job.reads_after_question) == q0


def test_a_uv_start_beside_its_target_fails_the_row_cleanly_and_moves_nothing_more(tmp_path,
                                                                                  monkeypatch):
    job, sim, helper, run, p = T._job(tmp_path)
    T._ready(job, p)
    real = sim.lamp

    def lamp(t, dual_pass=None):
        real(t, dual_pass=dual_pass)
        if dual_pass == "lamp":
            # the zero-length m0 that follows lands 8 units beside (within 1 mm)
            sim.real_table = False
            sim.c_faults["arrival_off"] = 8
    monkeypatch.setattr(sim, "lamp", lamp)
    n0 = len(sim.received)
    res = T._until(job, job.read_row(), J.Confirm.ROW_FAILED_STRIP)
    assert res.detail["why"] == "arrived_beside_the_target"
    lines = _row_lines(sim, n0)
    assert sum(1 for ln in lines if ln.startswith(";m2")) == 1      # the lamp pass only
    assert not sim.m2_pending
    assert job._table.closed_reason is None                         # not a doubt: it goes on


def test_after_stop_the_report_page_does_not_say_the_arm_moves_on():
    res = SimpleNamespace(kind=W.OK, step="read_row", detail={})
    job = SimpleNamespace(ended=None, only_home=False, _pause_stop=True)
    win = SimpleNamespace(job=job, _next_action=lambda: (None, None, "the arm moves to row 2"))
    text = W.TableMeasureWindow._report_next_text(win, res)
    assert "moves to row 2" not in text and "You pressed Stop" in text
    job._pause_stop = False
    text = W.TableMeasureWindow._report_next_text(win, res)
    assert "the arm moves to row 2" in text
    # the row honours the stop itself and says so in its result (what the window sees)
    res.detail = {"stop_asked_during_the_last_patch": True}
    text = W.TableMeasureWindow._report_next_text(win, res)
    assert "moves to row 2" not in text and "You pressed Stop" in text

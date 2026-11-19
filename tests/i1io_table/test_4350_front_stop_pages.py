"""4.3.50 (independent safety review 449, SHOULD-2; the table re-review's S-4): the careful 5 mm
steps towards the front (the creep) are where the arm may meet the end of its travel. Three ends
of such a step close the sending (nothing more goes to the table): the table answers the step
with a non-zero STATUS, REFUSES the line, or does NOT ANSWER. Until 4.3.49 each got the general
stop page ("open i1Profiler once"), which says nothing about the front and sends the person to a
homing from a place no recording starts one.

Each now gets its own page (M-I1IO-DRIVE-FRONT-STOPPED): what happened (one sentence per case),
that nothing more is sent, where the arm was before the step and where it was sent, and the way
on. ChromIQ's own homing (with the way back) is NOT offered: the reviewed rules allow it only
after a stop at which the table answered every line as recorded. So: the power switch (at once
when the step was never reported finished), End measurement, ten seconds off, i1Profiler once.

Each case is driven against the simulated table: the fault is put into the second creep step.
"""
from __future__ import annotations

import types

import pytest

from core.i18n import tr
from tests.i1io_table import job_harness as H
from tests.i1io_table.test_4349_acceptance_his_sheet_and_wider import (CROSSES_1, HIS_TABLE,
                                                                        _through_first_row)
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.window_sim import WindowSim
from workflow import measurement_messages as M
from workflow.i1io.table import job as J
from workflow.i1io.table import reach as rc

#: the simulated table's fault kind -> the stop id the job gives it
CASES = {"status": "table_answered_a_status", "refuse": "table_refused_a_line",
         "no_answer": "table_did_not_answer"}


def _arm_fault_in_creep_step(sim, job_of, kind, nth=2):
    """Put *kind* into the *nth* creep step's m0 (a step is a creep step while the job holds
    ``_creep_step_now``, which it sets right before that m0)."""
    seen = {"n": 0, "at": None}

    def on_command(index):
        line = sim.received[index]
        job = job_of()
        if line[1:3] == "m0" and job is not None and job._creep_step_now is not None:
            seen["n"] += 1
            if seen["n"] == nth:
                sim.inject_at(index, kind)
                seen["at"] = index
    sim.on_command = on_command
    return seen


def _creep_with_fault(tmp_path, kind):
    holder = {}
    out, job, sim, p = None, None, None, None
    # the job is built inside _through_first_row; the hook finds it through the holder
    from tests.i1io_table import reader_sim as RS
    real = RS.make_reading_job

    def make(*a, **k):
        res = real(*a, **k)
        holder["job"] = res[0]
        holder["seen"] = _arm_fault_in_creep_step(res[1], lambda: holder.get("job"), kind)
        return res
    RS.make_reading_job = make
    try:
        out, job, sim, p = _through_first_row(tmp_path, H.demo_sheet(), CROSSES_1,
                                              front_end=3400)
    finally:
        RS.make_reading_job = real
    return out, job, sim, p, holder["seen"]


@pytest.mark.parametrize("kind", list(CASES))
def test_a_creep_step_answered_badly_stops_with_its_facts_and_sends_nothing_more(tmp_path,
                                                                                 kind):
    out, job, sim, p, seen = _creep_with_fault(tmp_path, kind)
    assert seen["at"] is not None, "the fault was never put into a creep step"
    step, k, reason, detail = out[-1]
    assert (step, k, reason) == ("creep", J.Kind.STOPPED, CASES[kind]), out[-1]
    # the facts of the step: where the arm was read before it, where it was sent (5 mm on)
    before, target = detail["creep_from"], detail["creep_to"]
    assert target[1] - before[1] <= 50 and target[1] > before[1]
    assert detail["front_y"] == job.front_reached() and detail["back_mm"] >= 1
    assert detail["creep_stop"] == CASES[kind] and job.creep_doubt["creep_stop"] == CASES[kind]
    # nothing more was sent after the step's own line, and nothing more can be
    assert len(sim.received) == seen["at"] + 1
    assert job.state().sending_closed
    n = len(sim.received)
    assert p.drive(job.home()).kind == J.Kind.REFUSED
    assert len(sim.received) == n
    # ChromIQ's own homing is not offered (the table's state is not known)
    want = (J.WayBack.SWITCH_OFF_UNFINISHED if kind == "no_answer"
            else J.WayBack.OPEN_I1PROFILER_ONCE)
    assert job.way_back() == want
    assert sim.violations == []


def _page(detail, reason, step="creep"):
    from ui.i1io_table_window import TableMeasureWindow as W
    fake = types.SimpleNamespace(_log_name="session.log")
    fake._front_stop_way = lambda rid, ending: W._front_stop_way(fake, rid, ending)
    res = types.SimpleNamespace(step=step, reason=reason, detail=detail)
    return W._front_stop_page(fake, res)


DETAIL = {"creep_from": [1402, 3170], "creep_to": [1402, 3220], "back_mm": 12}


@pytest.mark.parametrize("rid", list(CASES.values()))
def test_each_case_has_its_own_true_page(rid):
    title, body = _page(dict(DETAIL, creep_stop=rid), rid)
    assert title == "The table stopped during a small step towards the front"
    assert "ChromIQ sends nothing more to the table in this measurement." in body
    assert "X 1402, Y 3170" in body and "X 1402, Y 3220" in body
    assert "The table has not reported where the arm stands now." in body
    assert "about 12 mm further towards the back" in body and "session.log" in body
    # the way on: power switch, End measurement, ten seconds off, i1Profiler once
    for words in ("What to do now:", "power switch", "Press End measurement",
                  "ten seconds", "open i1Profiler 3.8.6 or older once",
                  "does not bring the arm home itself this time"):
        assert words in body, (rid, words)
    assert "Bring the arm home" not in body
    assert "—" not in title + body and "{" not in body
    if rid == "table_did_not_answer":
        assert body.index("Switch the table off now") < body.index("Press End measurement")
        assert "motor may still be trying" in body
    elif rid == "table_answered_a_status":
        assert "error code" in body and "end of its travel" in body
        assert "If you hear the motor keep running" in body
    else:
        assert "refused" in body and "cannot tell whether the arm moved" in body


def test_other_stops_keep_the_general_page():
    assert _page(dict(DETAIL, creep_stop="link_lost"), "link_lost") is None
    assert _page(dict(DETAIL, creep_stop="table_did_not_answer"), "table_did_not_answer",
                 step="read_row") is None
    assert _page({}, "table_did_not_answer") is None


def test_the_front_question_says_what_happens_on_an_error_answer():
    """Re-review S-4: "offers to bring it home" was true for two of four outcomes."""
    _t, body = M.M_I1IO_DRIVE_FRONT.render(back_mm=20)
    # 4.3.50: the page rewritten in plain words (a real user, issue 129); the case is still said
    assert ("If the table reports an error or does not answer, ChromIQ sends nothing more and "
            "tells you what to do.") in body


class _FaultyWindowSim(WindowSim):
    def __init__(self, kind, **kw):
        super().__init__(**kw)
        self.kind = kind
        self.seen = None

    def factory(self, *a, **k):
        job = super().factory(*a, **k)
        self.seen = _arm_fault_in_creep_step(self.sim, lambda: self.jobs[-1], self.kind)
        return job


@pytest.mark.parametrize("kind", list(CASES))
def test_in_the_window_the_page_and_its_way_home_after_the_ending(
        qtbot, monkeypatch, tmp_path, settings, kind):  # noqa: F811
    sim = _FaultyWindowSim(kind, aims=CROSSES_1, front_end=3400,
                           reach_store=rc.MemoryReachStore(), **HIS_TABLE)
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sheet=H.demo_sheet(), sim=sim)
    p.script["front_choice"] = "Go forward carefully, my hands are away"
    page = p.drive_until(("stopped", "refused", "end_of_session"))
    assert page == "stopped", (page, win._title.text(), win._text.text())
    assert win._title.text() == tr("The table stopped during a small step towards the front")
    text = win._text.text()
    assert tr("What to do now:") in text
    assert tr("Bring the arm home") not in p.labels()
    assert tr("End measurement") in p.labels()
    n = len(sim.sim.received)
    # End measurement: nothing was read, so the measurement ends; the done page keeps the way
    p.press("End measurement")
    page = p.drive_until(("done", "end_of_session"))
    if page == "end_of_session":
        p.press("Discard and stop")
        page = p.drive_until(("done",))
    text = win._text.text()
    assert "power switch" in text and "i1Profiler 3.8.6 or older once" in text
    assert tr("Press End measurement. Your readings so far are kept, and ChromIQ asks whether "
              "to save them.") not in text
    assert len(sim.sim.received) == n


def test_a_creep_step_outside_its_time_window_says_so_and_where_the_arm_is():
    """SHOULD-2's last part: the step was reported finished, outside a step's time. Its reason
    says that (not "did not arrive exactly"), where the arm reads, and the homing offered."""
    from ui.i1io_table_window import reason_text
    why = reason_text("creep_step_outside_time_window",
                      {"read": [1402, 3171], "target": [1402, 3220], "short_mm": 6})
    assert "took longer or shorter than such a step takes" in why
    assert "X 1402, Y 3171" in why and "about 6 mm further towards the back" in why
    assert "Bring the arm home" in why and "did not arrive exactly" not in why
    assert "—" not in why

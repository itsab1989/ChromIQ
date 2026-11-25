"""4.3.52 fix round: the independent safety review's MUSTs and SHOULDs
(~/Desktop/ChromIQ-work/2026-11-20_subopt452_review/review_subopt452.txt).

MUST-1: with "Guided, step by step measurement" off, after a Stop the arm drove out over the bed
again by itself ("Bring the arm home" gave a countdown in place of the hands-off question, and
after the homing the window went straight back to aiming: the sheet laid answered by the
setting, the arm driven out, 5 movements). THE RULE: once a sitting has had a Stop, a problem
report or a fault, the rest of that sitting is guided (TableJob.guided_now, TURNS_GUIDED).

The SHOULDs S-3 / S-4 (the exact lists, the three unguarded guards) are in
test_4352_fix_round_lists_and_guards.py."""
from __future__ import annotations

import logging

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import window_sim as WS
from tests.i1io_table.test_4349_acceptance_his_sheet_and_wider import CROSSES_1, HIS_TABLE
from tests.i1io_table.test_4352_guidance_off import (GUIDED_ANSWERS, UNGUIDED_ANSWERS,
                                                     _moves, _unguided_job)
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (the fixture)
from tests.i1io_table.window_sim import WindowSim
from workflow.i1io.table import job as J
from workflow.i1io.table import reach as rc

C = J.Confirm


@pytest.fixture(autouse=True)
def _no_breach():
    J.HANDS_OFF_BREACHES.clear()
    yield
    J.HANDS_OFF_BREACHES.clear()


# ---- MUST-1: after a Stop the rest of the sitting is guided -----------------------------------

def _stop_on_write(monkeypatch, holder, when):
    """Presses Stop (the job's stop_at_next_pause, as the window's Stop does) right after the
    first line *when* picks was written."""
    real = WS.SlowTransport.write
    state = {"done": False}

    def write(self, data, *a, **k):
        out = real(self, data, *a, **k)
        job = holder.jobs[-1] if holder.jobs else None
        if job is not None and not state["done"] and when(job, data):
            state["done"] = True
            job.stop_at_next_pause()
        return out
    monkeypatch.setattr(WS.SlowTransport, "write", write)
    return state


def _stop_in_countdown(monkeypatch, step="read_row"):
    """Presses Stop while the countdown before the first *step* runs (the countdown sees it at
    its next slice, as when the person presses Stop on the countdown page)."""
    real = J.TableJob._countdown
    state = {"done": False}

    def countdown(self, st, ask):
        if st == step and not state["done"]:
            state["done"] = True
            self.stop_at_next_pause()
        return real(self, st, ask)
    monkeypatch.setattr(J.TableJob, "_countdown", countdown)
    return state


def _row_move(job, data):
    return getattr(job, "_gen_step", None) == "read_row" and bytes(data)[1:3] in (b"m0", b"m2")


def _creep_move(job, data):
    return getattr(job, "_creep_step_now", None) is not None


STOP_PAGES = ("stopped_by_you", "stopped", "after_problem", "front_stopped", "front_end",
              "refused")


def _to_the_stop(p, state):
    pages = []
    for _ in range(80):
        pg = p.page()
        if state["done"] and pg in STOP_PAGES:
            return pages
        pages.append(pg)
        p.answer_page(pg)
    raise AssertionError(pages[-8:])


def _after_stop(win, sim, p):
    """Bring the arm home after the Stop: what is asked, and what moved before each answer."""
    job = sim.jobs[0]
    out = {"stop_page": p.page(), "labels": p.labels(),
           "countdowns_at_stop": len(job.countdowns), "lines_at_stop": len(sim.sim.received)}
    n = _moves(sim.sim.received)
    assert "Bring the arm home" in p.labels(), p.labels()
    p.press("Bring the arm home")
    out["page_after_button"] = p.page()
    out["moved_before_go"] = _moves(sim.sim.received) - n
    if p.page() == "go":
        p.press("Go")
        p.idle()
    out["page_after_homing"] = p.page()
    out["at_rest_after_homing"] = job.at_rest()
    m = _moves(sim.sim.received)
    p.idle()
    out["moved_after_homing"] = _moves(sim.sim.received) - m
    out["countdowns_after_stop"] = [c for c in job.countdowns[out["countdowns_at_stop"]:]]
    out["auto_after_stop"] = [a for a in job.auto_answers
                              if a["line"] >= out["lines_at_stop"]]
    out["lines"] = list(sim.sim.received)
    return out


def _run_stop_case(qtbot, monkeypatch, tmp_path, settings, case, guided):
    if case == "creep":
        sim = WindowSim(cold=False, aims=CROSSES_1, reach_store=rc.MemoryReachStore(),
                        **HIS_TABLE)
        sheet = H.demo_sheet()
    else:
        sim, sheet = WindowSim(), None
    if case == "countdown":
        if not guided:
            state = _stop_in_countdown(monkeypatch)
        else:
            # the guided twin: Stop at the same place, at the hands-off question before the
            # first row (nothing is on its way there in either mode)
            state = {"done": False}
    else:
        state = _stop_on_write(monkeypatch, sim, _creep_move if case == "creep" else _row_move)
    win, sim, run, p, *_ = open_window(qtbot, monkeypatch, tmp_path / f"{case}{guided}",
                                       settings, asking=guided,
                                       guided=None if guided else False, sim=sim, sheet=sheet)
    p.script.update(GUIDED_ANSWERS if guided else UNGUIDED_ANSWERS)
    if case == "countdown" and guided:
        for _ in range(60):
            pg = p.page()
            job = sim.jobs[0] if sim.jobs else None
            if pg == "go" and job is not None and job.alignment is not None:
                state["done"] = True
                win._on_stop()
                p.press("Go")
                break
            p.answer_page(pg)
    pages = _to_the_stop(p, state)
    out = _after_stop(win, sim, p)
    out["pages"] = pages
    out["job"] = sim.jobs[0]
    return out


@pytest.mark.parametrize("case", ["row", "countdown", "creep"])
def test_must1_after_a_stop_the_rest_of_the_sitting_is_guided(qtbot, monkeypatch, tmp_path,
                                                              settings, case, caplog):
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        u = _run_stop_case(qtbot, monkeypatch, tmp_path, settings, case, guided=False)
    job = u["job"]
    # the hands-off question is asked for the homing, nothing moved before the answer
    assert u["page_after_button"] == "go", u
    assert u["moved_before_go"] == 0, u
    # after the homing the sitting does not go on by itself: the sheet is asked about, the arm
    # stays at its resting place
    assert u["at_rest_after_homing"], u
    assert u["page_after_homing"] not in ("aimed", "working", "countdown"), u
    assert u["page_after_homing"] in ("sheet_laid", "report_after_step"), u
    assert u["moved_after_homing"] == 0, u
    # nothing after the Stop was answered by the setting and no countdown stood in for a question
    assert u["countdowns_after_stop"] == [], u["countdowns_after_stop"]
    assert u["auto_after_stop"] == [], u["auto_after_stop"]
    assert job.turned_guided and job.turned_guided.startswith("stop_pressed"), job.turned_guided
    assert job.guided is False and job.guided_now is True
    assert J.HANDS_OFF_BREACHES == []
    # the app log says the sitting turned guided, and why
    msgs = [r.getMessage() for r in caplog.records if r.name == "chromiq.events"]
    turned = [m for m in msgs if m.startswith("table guidance:")]
    assert turned and "now=guided" in turned[0] and "stop_pressed" in turned[0], turned
    # and the session log too
    log_text = job.diag.path.read_text(encoding="utf-8") if getattr(job.diag, "path", None) else ""
    if log_text:
        assert "the rest of this sitting is guided" in log_text


@pytest.mark.parametrize("case", ["row", "creep"])
def test_must1_the_wire_is_a_guided_runs_up_to_the_stop_and_after_it(qtbot, monkeypatch,
                                                                    tmp_path, settings, case):
    """The wire stays identical to a guided run answered yes: up to the Stop (as before), and
    now also after it (Bring the arm home, Go, the homing): the unguided sitting turned guided
    sends exactly what the guided one sends."""
    g = _run_stop_case(qtbot, monkeypatch, tmp_path / "g", settings, case, guided=True)
    u = _run_stop_case(qtbot, monkeypatch, tmp_path / "u", settings, case, guided=False)
    assert g["lines_at_stop"] == u["lines_at_stop"]
    assert [ln for ln in g["lines"]] == [ln for ln in u["lines"]]
    assert g["page_after_button"] == u["page_after_button"] == "go"


def test_must1_carry_on_after_a_stop_asks_the_hands_off_question(qtbot, monkeypatch, tmp_path,
                                                                 settings):
    sim = WindowSim()
    state = _stop_on_write(monkeypatch, sim, _row_move)
    win, sim, run, p, *_ = open_window(qtbot, monkeypatch, tmp_path, settings, guided=False,
                                       sim=sim)
    p.script.update(UNGUIDED_ANSWERS)
    _to_the_stop(p, state)
    job = sim.jobs[0]
    n, cds = _moves(sim.sim.received), len(job.countdowns)
    p.press("Next step")
    p.idle()
    assert p.page() == "go", p.page()
    assert _moves(sim.sim.received) == n and len(job.countdowns) == cds


@pytest.mark.parametrize("trouble", ["problem", "fault", "cancel"])
def test_must1_a_problem_or_a_fault_turns_the_rest_guided_too(tmp_path, trouble):
    job, sim, person = _unguided_job(tmp_path)
    assert job.guided_now is False
    if trouble == "problem":
        job._table = job._table or object.__new__(type("T", (), {}))
        job.problems.append(("wrong", None, 0))
    elif trouble == "fault":
        job._fault_seen = "read_row: table_answered_a_status"
    else:
        job.stopped_by_person = True
    seen = []
    job.on_progress = seen.append
    assert job.guided_now is True
    # review 2, S-4: reading the guidance records and emits nothing (the transition is made
    # where the job sets the flag; here the test set it by hand)
    assert seen == [] and job.turned_guided is None
    # every kind is asked now: nothing answered by the setting, no countdown
    for kind in list(J.BY_SETTING) + [C.GO]:
        assert job._without_the_person(J.Ask(kind, {"step": "read_row"})) is None, kind


def test_s4_every_place_that_sets_a_turns_guided_flag_turns_the_sitting_guided():
    """Review 2, S-4: guided_now has no side effect, so each place in the job that sets one of
    TURNS_GUIDED calls _turn_guided itself (within a few lines; a site inside a
    problem report is covered by the report's own call just above)."""
    import inspect
    import re
    lines = inspect.getsource(J).splitlines()
    pat = re.compile(r"self\.(stop_pressed|stopped_by_person|only_home|creep_stopped)\s*=\s*True"
                     r"|self\.problems\.append|self\._fault_seen\s*=")
    found = 0
    for i, line in enumerate(lines):
        if pat.search(line):
            found += 1
            near = "\n".join(lines[max(0, i - 8):i + 5])
            ok = "_turn_guided(" in near or "_from_exception" in near
            assert ok, f"line {i + 1}: {line.strip()} sets a flag without _turn_guided"
    assert found >= 8, found


def test_must1_turns_guided_names_every_flag_the_job_keeps():
    for flag in J.TURNS_GUIDED:
        if flag != "fault":
            assert hasattr(J.TableJob, flag) or flag in J.TableJob.__init__.__code__.co_names, \
                flag

"""Review 14, PART A.1: an independent random walker over the job's questions (not the builder's).

Invariant, defined here from the TEXTS (not from job.HANDS_OFF_ANSWERS): every movement line that
reaches the simulated table follows, as the LAST thing the person did, one of the answers whose
page says "take your hands away" and names the move. Every other answer, window answer or
problem report since the last such answer makes a movement a breach. The guard inside the table
module is NOT trusted: the wire itself is checked. Random answers, random next steps, random Stop
and problem reports, random window answers, both modes, spot and strip, faults."""
from __future__ import annotations

import random

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl

#: the answers whose page asks for the hands to be taken away (from the texts, review 14)
MY_HANDS_OFF = {("go", "yes"), ("sheet_laid", "yes"), ("first_visit", "yes"),
                ("start_up", "yes"), ("report_after_step", "as described"),
                # 4.3.50: "Go forward carefully, my hands are away" (M-I1IO-DRIVE-FRONT); the
                # mark-3 check and its "centred" are gone
                ("front_choice", "go on")}

MOTION = {ln.decode("ascii").rstrip("\r") for ln in tbl.MOTION_LINES}

WINDOW_PAGES = ["stopped_by_you", "refused", "stopped", "after_problem", "home_offered",
                "next_page", "problem", "stored_white_refused", "ending_closed"]

STEPS = ["open", "calibrate", "align", "creep", "read_row", "read_row",
         "read_row", "home", "park", "next_page", "end", "save", "read_tile", "start_up"]


def _is_move(ln: str) -> bool:
    s = ln.rstrip("\r")
    return s in MOTION or s[1:3] in ("m0", "m1", "m2", "i0", "i1")


class Walk:
    CANON = ["calibrate", "align", "read_row", "read_row", "read_row", "read_row",
             "read_row", "read_row", "end", "save", "home"]

    def __init__(self, job, sim, rnd, forward=0.85):
        self.job, self.sim, self.rnd, self.forward = job, sim, rnd, forward
        self.k = 0
        self.events: "list[tuple[int, tuple]]" = []
        for name in ("answer", "answer_by_button", "person_answered", "report_after_step",
                     "report_problem"):
            real = getattr(job, name)
            setattr(job, name, self._wrap(name, real))

    def _wrap(self, name, real):
        def call(*a, **k):
            if name == "answer":
                ev = (str(a[0]), str(a[1]))
            elif name == "answer_by_button":
                ev = ("aimed", "aimed")
            elif name == "person_answered":
                ev = (str(a[0]), str(a[1]) if len(a) > 1 else "")
            elif name == "report_after_step":
                ev = ("report_after_step", str(a[0]))
            else:
                ev = ("problem", str(a[0]))
            n = len(self.sim.received)
            res = real(*a, **k)
            # an answer the job refused (not the question asked) still counts: the person
            # answered something, so it never confirms anything
            self.events.append((n, ev))
            return res
        return call

    def breaches(self):
        out = []
        for i, ln in enumerate(self.sim.received):
            if not _is_move(ln):
                continue
            before = [ev for n, ev in self.events if n <= i]
            if not before:
                out.append((i, ln, "no answer at all"))
                continue
            last = before[-1]
            if last not in MY_HANDS_OFF:
                out.append((i, ln, last, before[-4:]))
        return out

    def answer_needs(self, res, limit=60):
        while res is not None and res.kind == J.Kind.NEEDS and limit > 0:
            limit -= 1
            kind = res.confirm
            choices = list(J.CHOICES[kind])
            # mostly the forward answer, sometimes any
            v = choices[0] if self.rnd.random() < self.forward else self.rnd.choice(choices)
            if kind == J.Confirm.AIMED and v == "aimed" and self.rnd.random() < 0.9:
                self.sim.aim(res.detail["mark"])
            if kind == J.Confirm.CAL_PLACE and self.rnd.random() < 0.7:
                v = "table tile"
            r = self.rnd.random()
            if r < 0.02:
                self.job.stop_at_next_pause()
            elif r < 0.03:
                return self.job.report_problem(self.rnd.choice(sorted(J.PROBLEM_KINDS)))
            elif r < 0.06:
                # a stale or doubled answer: the previous kind again, or a wrong kind
                self.job.answer(self.rnd.choice(list(J.CHOICES)), "yes")
            res = self.job.answer(kind, v)
        if res is not None and getattr(self.job, "report_due", None) is not None \
                and self.rnd.random() < 0.9:
            res = self.job.report_after_step(self.rnd.choice(
                ["as described", "as described", "something wrong", "not sure"]))
        return res

    def run(self, n_actions):
        job, rnd = self.job, self.rnd
        res = self.answer_needs(job.open())
        for _ in range(n_actions):
            if job.phase == "closed":
                break
            r = rnd.random()
            if r < 0.08:
                job.person_answered(rnd.choice(WINDOW_PAGES), rnd.choice(["carry on", "home",
                                                                        "go on", "cancel"]))
            elif r < 0.11:
                job.stop_at_next_pause()
                if rnd.random() < 0.5:
                    job.stop_honoured_between_steps()
            if rnd.random() < 0.75:
                step = self.CANON[self.k % len(self.CANON)]
            else:
                step = rnd.choice(STEPS)
            fn = getattr(job, step)
            try:
                res = self.answer_needs(fn())
            except TypeError:
                continue
            if step == self.CANON[self.k % len(self.CANON)] and res is not None and res.ok:
                self.k += 1


@pytest.mark.parametrize("seed", range(200))
def test_r14_no_move_without_hands_off_after_the_last_answer(tmp_path, seed):
    rnd = random.Random(seed)
    ask = bool(seed % 2)
    args = ["-v", "-c", "1", "chart"] if seed % 3 == 0 else ["-v", "-c", "1", "-p", "chart"]
    faults = None
    if seed % 5 == 4:
        faults = {"scan": {rnd.choice(["not_ready", "lights_err", "dark_fail"]): True},
                  "scan_at": 2}
    job, sim, helper, run = RS.make_reading_job(tmp_path, ask_after_each_step=ask, faults=faults,
                                                aims=None)
    job.set_options(args)
    w = Walk(job, sim, rnd)
    w.run(70)
    try:
        job.close()
    except Exception:      # noqa: BLE001
        pass
    # the guard firing would show here too (conftest); this checks the wire itself
    J.HANDS_OFF_BREACHES.clear()
    moves = sum(1 for ln in sim.received if _is_move(ln))
    assert not w.breaches(), (seed, w.breaches()[:3], moves)


def test_r14_the_walk_moves_at_all(tmp_path):
    """The walker is not vacuous: over the seeds it reaches reading rows."""
    total = 0
    for seed in range(8):
        rnd = random.Random(1000 + seed)
        job, sim, helper, run = RS.make_reading_job(tmp_path / str(seed), ask_after_each_step=False)
        job.set_options(["-v", "-c", "1", "-p", "chart"])
        w = Walk(job, sim, rnd)
        w.run(70)
        total += sum(1 for ln in sim.received if _is_move(ln))
        assert not w.breaches()
    assert total > 50

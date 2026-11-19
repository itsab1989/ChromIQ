"""TEST SUPPORT ONLY, never shipped: tester 0.6.0's stage D2 (the check move to mark 3) on a copy
of the app's job, so that the frozen tester captures keep pinning EVERY OTHER stage byte for byte.

4.3.50 removed the check move and its question from the app (the first complete page on a real
i1iO 2, 19 Nov 2026: nobody can see the opening under the instrument, i1Profiler has no such step;
tests/i1io_table/test_4350_no_mark3_check.py pins that the app's ``TableJob`` has none). Most of
tester 0.6.0's captured sittings contain D2 (``data/tester_060_*_wire.json``: the warm and cold
alignment, the creep, the faults and cancels at every line, the strip rows), and dropping them
would drop what they prove about the opening, the start-up, the alignment, the creep, the strip
row and the homing. ``TesterD2Job`` is the app's job plus exactly 4.3.49's D2 step, nothing else.
"""
from __future__ import annotations

from workflow.i1io.table import caps as cp
from workflow.i1io.table import job as J


class TesterD2Job(J.TableJob):
    STAGE_KEY = dict(J.STAGE_KEY, check_move="d2")
    MOVING_STEPS = J.MOVING_STEPS + ("check_move",)
    MAX_RUNS = dict(J.MAX_RUNS, d2=3)

    def check_move(self):
        return self._stage("check_move", self._check_move)

    def _ready(self, step: str):
        why = super()._ready(step)
        if why or step != "check_move":
            return why
        d = self._table
        if self.alignment is None:
            return "needs_alignment"
        if not self.out_known() and d.arm_free is not True:
            return "arm_not_out_on_the_sheet"
        if self.front_need is not None and self.front_reached() < self.front_need:
            return "needs_creep_first"
        return None

    def _check_move(self):
        """4.3.49's part C D2, line for line: the arm read (twice when free), one computed m0 to
        the third mark's p1 reading, its arrival read."""
        d = self._table
        al = self.alignment
        self._step("d2", *cp.CHECK_MOVE)
        target = al.readings[2]
        a = d.position()
        if d.arm_free:
            self._still(a)
        got = yield from self._move_to(target, "the move to mark 3")
        return {"target": target, "read": got}


def check_move(job):
    """4.3.49's check move on a job built as the app's (``job.check_move()`` until 4.3.50), for a
    test whose SUBJECT is something else that needs the arm held out over the sheet the way
    4.3.49 put it there (the homing from there, the GO after a question, a reading taken again
    before a move, a stop, the caps...). The job is turned into a ``TesterD2Job`` (the same object,
    the same state: the class only adds the step). Never used for what the app does after the
    aims: test_4350_no_mark3_check.py pins that."""
    if not isinstance(job, TesterD2Job):
        job.__class__ = TesterD2Job
    return job.check_move()

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""4.3.54, the review's M1 (and S2): the speed the table SAYS it ran is the speed the readings are
placed by. In every recorded row the a3 answer repeated the speed sent (raw S2: 23 rows, the
volunteer's 168 -> 168). A row whose a3 names another speed is not accepted: it fails cleanly
("strip_speed_not_as_sent", its readings unused), and when the person reads it again it is read
at ChromIQ's own speed for its patches (factor 1.00), never again at the factor's. At factor 1.00
the same check holds (a state check of the table), and nothing loops: each read again is the
person's answer. On the simulated table and the simulated helper (the owner's sheet)."""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from workflow.i1io.table import job as J
from workflow.i1io.table import reach as rc

AIMS = [(1403, 1488), (1409, 3368), (-1352, 3370)]
SIGHT = (-1546 + 1352, 3102 - 3370)


def _run(tmp_path, factor, a3_v=None, again=("again",) * 50, rows=2, inject_m2_refusal=False):
    job, sim, helper, r = RS.make_reading_job(tmp_path, sheet=H.demo_sheet(), aims=AIMS,
                                              ask_after_each_step=False,
                                              reach_store=rc.MemoryReachStore(),
                                              sight_offset=SIGHT, front_end=3700)
    job.guided = False
    job.row_speed_factor = factor
    if a3_v is not None:
        sim.c_faults["a3_v"] = a3_v
    if inject_m2_refusal:
        sim.inject("refuse", cid="m2")
    assert job.set_options(["-v", "-c", "1", "chart"]).ok
    answers = list(again)

    def on_ask(person, res):
        if res.confirm == J.Confirm.ROW_FAILED_STRIP:
            person.script[J.Confirm.ROW_FAILED_STRIP] = answers.pop(0)
        return None
    p = H.Person(job, sim, {J.Confirm.FRONT_CHOICE: "go on", J.Confirm.GO: "yes"},
                 on_ask=on_ask)
    for s in ("open", "calibrate", "align"):
        assert p.drive(getattr(job, s)()).ok, s
    if job.front_need and job.front_reached() < job.front_need:
        assert p.drive(job.creep()).ok
    results = []
    for _ in range(rows):
        if not job.rows_left():
            break
        results.append(p.drive(job.read_row()))
    m2 = [int(ln[11:15], 16) for ln in sim.received if ln[1:3] == "m2"]
    fails = [a for a in p.asked if a[1] == J.Confirm.ROW_FAILED_STRIP]
    log = job.diag.text() if hasattr(job.diag, "text") else ""
    job.close()
    return results, m2, fails, sim, log


def test_an_answer_equal_to_the_speed_sent_is_accepted(tmp_path):
    results, m2, fails, sim, _ = _run(tmp_path, 1.95)
    assert all(r.ok for r in results) and fails == []
    assert set(m2) == {168}
    assert sim.violations == []


def test_another_speed_answered_refuses_the_row_and_it_is_read_again_at_chromiqs_own(tmp_path):
    """The table answers 137 when 168 was sent (a table snapping a speed to one of its own): the
    row fails with the true reason; the person's read again runs at 88 mm/s (ChromIQ's own for
    these 10 mm patches) and is accepted. Each row: 168 once, then 88; no third move."""
    results, m2, fails, sim, _ = _run(tmp_path, 1.95, a3_v=lambda v: 137 if v == 168 else v)
    assert all(r.ok for r in results)
    assert [f[2]["why"] for f in fails] == ["strip_speed_not_as_sent"] * len(results)
    assert m2 == [168, 88] * len(results)
    assert sim.violations == []


def test_at_factor_one_the_same_check_holds_and_nothing_loops(tmp_path):
    """ChromIQ's own speed answered otherwise: refused; read again (the person's answer) at the
    same, its own, speed; refused again; the person ends it. Two moves, two questions: no loop."""
    results, m2, fails, sim, _ = _run(tmp_path, 1.0, a3_v=lambda v: v - 1,
                                      again=("again", "skip"), rows=1)
    assert [f[2]["why"] for f in fails] == ["strip_speed_not_as_sent"] * 2
    assert m2 == [88, 88]
    assert results and results[0].detail.get("status") == "skipped"


def test_a_refusal_at_the_factors_speed_is_read_again_at_chromiqs_own(tmp_path):
    """S2: the table refuses (:#) the scan move at the factor's speed (133 mm/s at 1.50, not a
    recorded value): the row fails cleanly and the read again runs at ChromIQ's own 88 mm/s."""
    results, m2, fails, sim, _ = _run(tmp_path, 1.5, rows=1, inject_m2_refusal=True)
    assert [f[2]["why"] for f in fails] == ["strip_move_refused_by_the_table"]
    assert m2 == [133, 88] and results[0].ok

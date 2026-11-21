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
from tests.i1io_table.test_window import settings  # noqa: F401 (fixture)
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


# ---- the review's M2: the saved measurement carries the mark ------------------------------------

@pytest.mark.parametrize("factor, marked", [(1.0, False), (1.95, True)])
def test_a_saved_table_measurement_carries_the_row_speed_mark(qtbot, monkeypatch, tmp_path,
                                                             settings, factor, marked):
    from tests.i1io_table.test_dual_table import long_sheet
    from tests.i1io_table.test_window import open_window
    from ui import i1io_table_window as W
    from workflow import ti3_provenance as tp
    settings.set(W.ROW_SPEED_KEY, factor)
    try:
        win, sim, run, p, saved, finished = open_window(
            qtbot, monkeypatch, tmp_path, settings, asking=False, sheet=long_sheet(),
            args=["-v", "-c", "1", "chart"])
        assert p.drive_until("end_of_session") == "end_of_session"
        p.press("Save and stop")
        assert saved
        mark = tp.read_row_speed(saved[0][0])
        if marked:
            assert mark and mark.startswith("factor 1.95: ") and "faster than the safe border" in mark
        else:
            assert mark is None
        assert sim.sim.violations == []
        win.close()
    finally:
        settings.set(W.ROW_SPEED_KEY, 1.0)


# ---- the review's S3: the frame only in a sitting whose factor is not 1.00 -----------------------

def test_the_gate_takes_unrecorded_speeds_only_when_the_factor_is_not_one():
    from types import SimpleNamespace
    from workflow.i1io.table import geometry as geo
    from workflow.i1io.table import lines as cl
    from workflow.i1io.table import session_table as tbl
    line = geo.m2_line(0, 2000, 133)
    for frame, ok in ((False, False), (True, True)):
        t = SimpleNamespace(dual_phase=None, position_now=(0, 2000), front_y=None, creep=False,
                            row_speed_frame=frame)
        gate = cl.make_gate(t)
        if ok:
            try:
                gate(line)
            except tbl.ForbiddenLine as exc:
                assert "recorded scan speed" not in str(exc), exc
        else:
            with pytest.raises(tbl.ForbiddenLine, match="ChromIQ's own speeds"):
                gate(line)
    # a recorded speed passes this check in both
    t = SimpleNamespace(dual_phase=None, position_now=(0, 2000), front_y=None, creep=False,
                        row_speed_frame=False)
    try:
        cl.make_gate(t)(geo.m2_line(0, 2000, 88))
    except tbl.ForbiddenLine as exc:
        assert "recorded scan speed" not in str(exc), exc


def test_the_job_opens_the_frame_only_for_a_factor_not_one():
    import inspect
    from workflow.i1io.table import job as J
    assert "d.row_speed_frame = abs(float(self.row_speed_factor) - 1.0) > 1e-9" in \
        inspect.getsource(J.TableJob)


# ---- the review's S6: two guards that a planted fault did not turn red --------------------------

def test_the_window_writes_the_table_row_speed_line_into_the_app_log(qapp, caplog):
    import logging
    from types import SimpleNamespace
    from ui import i1io_table_window as W
    fake = SimpleNamespace(_live=None)
    ev = {"event": "strip_move", "row": 3, "speed": 168, "factor": 1.95, "edge_mm": 1.07,
          "speed_line": "speed 168 mm/s (factor 1.95 on ChromIQ's own 88 mm/s; wanted 168), "
                        "border 1.07 mm; read faster than the safe border allows"}
    with caplog.at_level(logging.INFO):
        W.TableMeasureWindow._live_event(fake, ev)
    lines = [r.getMessage() for r in caplog.records if "table row speed" in r.getMessage()]
    assert len(lines) == 1 and "factor=1.95" in lines[0] and "edge_mm=1.07" in lines[0]
    assert "read faster than the safe border allows" in lines[0]


def test_the_table_start_takes_minus_f_out_when_the_rule_reads_a_single_scan():
    """Review S6: the predicate is tested in test_4354_dual_mode_on_the_table; this pins that the
    table's START uses it on the reader's arguments."""
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure)
    assert ("if table_dual is not None or self._table_row_is_choice_only():\n"
            "            # the dual scan records the filter row's choice") in src
    i = src.index("if table_dual is not None or self._table_row_is_choice_only():")
    assert "args = self._args_without_filter(args)" in src[i:i + 400]

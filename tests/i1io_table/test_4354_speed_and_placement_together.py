# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""4.3.54 release integration: the row speed factor (feat/4.3.54-dual-scan-mode) and the row
placement check (feat/4.3.54-row-placement-check) TOGETHER, behaviour neither branch tested.

* The order: the table's own speed answer is judged first (scan.run_row: a row the table ran at
  another speed fails before its readings are cut), the placement check second (strip.cut_row).
* A row read at a factor other than 1.00 that the placement check refuses is read again at
  ChromIQ's own speed (factor 1.00), as A does after a refused speed answer, so a fast setting
  cannot refuse the same row again and again at the same speed. A row read at 1.00 and refused
  keeps B's path unchanged (read again at the same speed).
* The CHROMIQ_ROW_SPEED mark counts the rows the measurement USES: a sitting whose fast rows were
  all refused and read again at 1.00 carries none; one with ANY accepted row read at another
  factor carries it.
* "Rest patch by patch" after the second refused row works at a factor above 1.00, and the
  measurement's mark and end line say only what the accepted strip rows were read at.
On the simulated table and the simulated helper; no hardware."""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_reading import ready_to_read, small_sheet
from tests.i1io_table.test_window import settings  # noqa: F401 (fixture)
from workflow.i1io.table import job as J
from workflow.i1io.table import strip as stp

STRIP = ["-v", "-c", "1", "chart"]
OFF = {"sheet_offset_mm": 2.5, "aperture_mm": 4.5}
CLEAN = {"aperture_mm": 4.5}


def _job(tmp_path, factor, rows=None):
    sheet = small_sheet(rows)
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet, aims=H.demo_aims(sheet),
                                                ask_after_each_step=False,
                                                faults={"scan": dict(CLEAN)})
    job.row_speed_factor = factor
    assert job.set_options(STRIP).ok
    p = H.Person(job, sim)
    return job, sim, helper, p


def _offset_on(helper, *attempts):
    """The sheet lies 2.5 mm off for the scan readers named (1 = the next one), clean otherwise."""
    n0 = len(helper.scans)
    helper.faults["scan"] = dict(OFF)
    helper.faults["scan_at"] = tuple(n0 + a for a in attempts)


def _answers(p, answers):
    seen = []

    def on_ask(person, res):
        if res.confirm == J.Confirm.ROW_FAILED_STRIP:
            seen.append(dict(res.detail))
            person.script[J.Confirm.ROW_FAILED_STRIP] = answers.pop(0)
        return None
    p.on_ask = on_ask
    return seen


def _m2(sim, since=0):
    return [int(ln[11:15], 16) for ln in sim.received[since:] if ln[1:3] == "m2"]


def _log(job):
    return "\n".join(x.read_text(encoding="utf-8", errors="replace")
                     for x in job.diag.folder.rglob("*.log"))


def _own_speed(tmp_path):
    """ChromIQ's own speed for the small sheet's first row (factor 1.00)."""
    job, sim, helper, p = _job(tmp_path / "own", 1.0)
    ready_to_read(job, p)
    n = len(sim.received)
    assert p.drive(job.read_row()).ok
    v = _m2(sim, n)
    job.close()
    assert len(v) == 1
    return v[0]


def test_the_speed_answer_is_judged_before_the_placement_check(tmp_path):
    """One fast row whose table answers another speed AND whose sheet lies 2.5 mm off: it is
    refused for the speed answer (its readings are never cut, so never judged for placement),
    read again at ChromIQ's own speed (clean, answered as sent) and accepted."""
    import json
    from workflow.i1io.table import measurement as ms
    own = _own_speed(tmp_path)
    job, sim, helper, p = _job(tmp_path / "both", 1.95)
    ready_to_read(job, p)
    sim.c_faults["a3_v"] = lambda v: v - 1 if v != own else v
    seen = _answers(p, ["again"])
    _offset_on(helper, 1)
    n = len(sim.received)
    r = p.drive(job.read_row())
    assert [s["why"] for s in seen] == ["strip_speed_not_as_sent"]
    v = _m2(sim, n)
    assert len(v) == 2 and v[0] > own and v[1] == own, (v, own)
    assert r.ok and r.detail["row_kind"] == "strip"
    recs = [json.loads(x.read_text(encoding="utf-8"))
            for x in sorted(job.diag.folder.rglob("*" + ms.ROW_RECORD_SUFFIX))]
    first, second = recs[:2]
    assert first["why"] == "strip_speed_not_as_sent" and "placement" not in first
    assert second["status"] == "read" and second["placement"]["confirmed"] is True
    job.close()


def test_a_fast_row_the_check_refuses_is_read_again_at_chromiqs_own_speed(tmp_path):
    own = _own_speed(tmp_path)
    job, sim, helper, p = _job(tmp_path / "fast", 1.95)
    ready_to_read(job, p)
    seen = _answers(p, ["again"])
    _offset_on(helper, 1)
    n = len(sim.received)
    r = p.drive(job.read_row())
    assert [s["why"] for s in seen] == [stp.PLACEMENT_REASON]
    v = _m2(sim, n)
    assert len(v) == 2 and v[0] > own and v[1] == own, (v, own)
    assert r.ok and r.detail["status"] == "read" and r.detail["row_kind"] == "strip"
    assert f"{stp.PLACEMENT_REASON}; it is read again at ChromIQ's own speed {own} mm/s " \
           "(factor 1.00)" in _log(job)
    # the accepted reading is the one at 1.00: it counts at 1.00, so no mark
    assert job.row_speed_marks[(0, 0)] == (1.0, False)
    assert job.row_speed_mark() is None
    assert sim.violations == []
    job.close()


def test_refused_again_at_one_it_stays_at_one_and_nothing_loops(tmp_path):
    """Refused at 1.95, read again at 1.00 and refused again: the third read is the person's
    answer again at 1.00 (not back at the factor's speed), and the person can skip."""
    own = _own_speed(tmp_path)
    job, sim, helper, p = _job(tmp_path / "fast", 1.95)
    ready_to_read(job, p)
    seen = _answers(p, ["again", "again", "skip"])
    _offset_on(helper, 1, 2, 3)
    n = len(sim.received)
    r = p.drive(job.read_row())
    assert [s["why"] for s in seen] == [stp.PLACEMENT_REASON] * 3
    v = _m2(sim, n)
    assert len(v) == 3 and v[0] > own and v[1:] == [own, own], (v, own)
    assert r.detail["status"] == "skipped"
    assert (0, 0) not in job.row_speed_marks and job.row_speed_mark() is None
    job.close()


def test_a_row_read_at_one_and_refused_keeps_the_checks_own_path(tmp_path):
    own = _own_speed(tmp_path)
    job, sim, helper, p = _job(tmp_path / "one", 1.0)
    ready_to_read(job, p)
    seen = _answers(p, ["again"])
    _offset_on(helper, 1)
    n = len(sim.received)
    r = p.drive(job.read_row())
    assert [s["why"] for s in seen] == [stp.PLACEMENT_REASON]
    assert _m2(sim, n) == [own, own]
    assert r.ok and r.detail["attempts"] == 2
    assert "it is read again at ChromIQ's own speed" not in _log(job)
    assert job.row_speed_mark() is None
    job.close()


def test_the_mark_is_there_when_any_accepted_row_was_read_at_another_factor(tmp_path):
    """Row 1 refused at 1.95 and read again at 1.00, row 2 accepted at 1.95: the mark names 1.95
    and counts both accepted strip rows."""
    job, sim, helper, p = _job(tmp_path, 1.95)
    ready_to_read(job, p)
    _answers(p, ["again"])
    _offset_on(helper, 1)
    r1 = p.drive(job.read_row())
    r2 = p.drive(job.read_row())
    assert r1.ok and r2.ok and r2.detail["attempts"] == 1
    assert job.row_speed_marks[(0, 0)] == (1.0, False)
    assert job.row_speed_marks[(0, 1)][0] == pytest.approx(1.95)
    mark = job.row_speed_mark()
    assert mark and mark.startswith("factor 1.95: ") and mark.endswith(
        " of 2 rows faster than the safe border"), mark
    job.close()


def test_no_mark_when_every_fast_row_was_refused_and_read_again_at_one(tmp_path):
    job, sim, helper, p = _job(tmp_path, 1.95)
    ready_to_read(job, p)
    _answers(p, ["again", "again"])
    _offset_on(helper, 1, 3)              # row 1's first read, row 2's first read
    out = [p.drive(job.read_row()), p.drive(job.read_row())]
    assert all(r.ok and r.detail["attempts"] == 2 for r in out)
    assert job.row_speed_marks == {(0, 0): (1.0, False), (0, 1): (1.0, False)}
    assert job.row_speed_mark() is None
    job.close()


def test_rest_patch_by_patch_at_a_fast_factor(tmp_path):
    """Factor 1.95, the sheet 2.5 mm off: row 1 refused at the fast speed, read again at 1.00 and
    accepted; row 2 refused at the fast speed (the page's second refused row): the rest of the
    page is offered patch by patch and chosen; rows 2 to 4 are read patch by patch. The mark:
    none, the only accepted strip row was read at 1.00. The rest is not read at any factor."""
    own = _own_speed(tmp_path)
    job, sim, helper, p = _job(tmp_path / "rest", 1.95, rows=[4, 4, 4, 4])
    ready_to_read(job, p)
    seen = _answers(p, ["again", "rest patch by patch"])
    _offset_on(helper, 1, 3)
    n = len(sim.received)
    res = []
    while job.rows_left():
        res.append(p.drive(job.read_row()))
    assert [(s["row"], s["why"], s["offer_rest"]) for s in seen] == [
        (1, stp.PLACEMENT_REASON, False), (2, stp.PLACEMENT_REASON, True)]
    assert [r.detail["row_kind"] for r in res] == ["strip", "spot", "spot", "spot"]
    assert all(r.ok and r.detail["status"] == "read" for r in res)
    v = _m2(sim, n)
    assert len(v) == 3 and v[0] > own and v[1] == own and v[2] > own, (v, own)
    assert job.row_speed_marks == {(0, 0): (1.0, False)}
    assert job.row_speed_mark() is None
    assert sim.violations == []
    job.close()


@pytest.mark.parametrize("refuse_from_row, marked", [(1, False), (2, True)])
def test_rest_patch_by_patch_and_the_end_line_in_the_window(qtbot, monkeypatch, tmp_path,
                                                            settings, refuse_from_row, marked):
    """The table's window at factor 1.95, the placement check refusing every row read faster
    than ChromIQ's own speed from row *refuse_from_row* on: the read again of a refused row runs
    at 1.00 and is accepted; the page's second refused row offers "Rest patch by patch", and the
    rest is read patch by patch. The saved measurement carries the mark only when an accepted
    strip row was read at 1.95 (row 1, when the refusals start at row 2), and the end line
    (M-I1IO-ROW-SPEED-END) is rendered from that mark."""
    from tests.i1io_table.test_window import open_window
    from ui import i1io_table_window as W
    from workflow import measurement_messages as M
    from workflow import ti3_provenance as tp
    real = stp.cut_row

    def cut_row(plan, outdir, fired, **kw):
        cut = real(plan, outdir, fired, **kw)
        note = getattr(plan, "speed_note", None) or {}
        fast = not note.get("refused") and abs(float(note.get("factor", 1.0)) - 1.0) > 1e-9
        row = int(plan.name.split("row")[-1].split("_")[0]) if "row" in plan.name else 0
        if fast and cut.ok and row >= refuse_from_row:
            return stp.Cut(False, stp.PLACEMENT_REASON, info=cut.info)
        return cut
    monkeypatch.setattr(stp, "cut_row", cut_row)
    settings.set(W.ROW_SPEED_KEY, 1.95)
    try:
        from tests.i1io_table.test_dual_table import shaped_sheet
        win, sim, run, person, saved, finished = open_window(
            qtbot, monkeypatch, tmp_path, settings, asking=False,
            sheet=shaped_sheet([6, 6, 6], along=10.6, across=10.0, w=210.0, h=297.0),
            args=STRIP)
        pressed = []
        for _ in range(12):
            page = person.drive_until(("row_failed_strip", "end_of_session"))
            if page == "end_of_session":
                break
            labels = person.labels()
            choice = ("Rest patch by patch" if "Rest patch by patch" in labels
                      else "Read it again as a strip")
            pressed.append(choice)
            person.press(choice)
        assert page == "end_of_session", pressed
        person.press("Save and stop")
        assert saved
        assert pressed == ["Read it again as a strip", "Rest patch by patch"], pressed
        mark = tp.read_row_speed(saved[0][0])
        if marked:
            assert mark and mark.startswith("factor 1.95: "), mark
            _title, body = M.M_I1IO_ROW_SPEED_END.render(mark=tp.row_speed_mark_text(mark))
            assert "1.95" in body or "1,95" in body
        else:
            assert mark is None
        assert sim.sim.violations == []
        win.close()
    finally:
        settings.set(W.ROW_SPEED_KEY, 1.0)

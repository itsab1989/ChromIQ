"""4.3.48 merge: the automatic second move (fix/4.3.48-table-home) meets the dual scan.

Decided at the merge (2026-11-19):

* A DUAL row read PATCH BY PATCH moves to each patch exactly as a single-scan patch row does
  (``_row_attempt`` -> ``_move_to(..., retry_beside=True)``), so an arrival read twice 0.6..1 mm
  beside a patch is moved to once more there too. The patch's two readings (lamp and UV, taken
  by the helper on the same spot, no table line) are taken only after the move returned, that
  is after an arrival within the tolerance: never at the place beside it.
* A DUAL ROW (lamp pass along the row, UV pass straight back) has its own arrival rule
  (scan.run_row, and the front-zone row ends through ``_move_to`` WITHOUT the retry): no second
  move there, as for a single-scan strip row.
* The caps add up: the step cap of a patch row is 4n+4+6 / n+2 with or without the dual scan
  (the dual spot reading sends no table line); the page cap is the need with the dual row plus
  (rows + 2) x 2 x (3, 1).
"""
from __future__ import annotations

import inspect
import json

from tests.i1io_table.test_4348_an_arrival_beside_is_moved_to_once_more import (
    _computed_m0, _land_beside)
from tests.i1io_table.test_dual_table import SPOT, _job, _ready, long_sheet
from workflow.i1io.table import caps as cp
from workflow.i1io.table import job as J
from workflow.i1io.table import lines as cl


def _row_record(job, name="p1_row1"):
    folder = next(iter(job.diag.folder.glob("row-*")))
    return json.loads((folder / f"{name}.row.json").read_text(encoding="utf-8"))


def test_a_dual_patch_row_moves_to_a_patch_once_more_and_reads_it_only_there(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, args=SPOT)
    sim.jitter = False
    _ready(job, p)
    # every patch reading: where the simulated arm stood, and the line count, at that moment
    at_read = []
    orig = job._read_patch

    def read(reader, patch, at=None):
        at_read.append((patch.loc, list(patch.target), [round(v) for v in sim.pos],
                        len(sim.received)))
        return orig(reader, patch, at)
    job._read_patch = read
    _land_beside(sim, (2,), 0, -7)
    n0 = len(sim.received)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["row_kind"] == "spot", (r.reason, r.detail)
    assert len(job.beside_retries) == 1 and job.beside_retries[0]["cured"] is True
    assert job._table.closed_reason is None and sim.violations == []
    sent = sim.received[n0:]
    moves = [k for k, ln in enumerate(sent) if _computed_m0(ln)]
    assert sent[moves[2]] == sent[moves[1]]                     # the same m0 line once more
    # every patch was read where it lies (within the arrival tolerance), and the second patch
    # only after the second move: never at the place 0.7 mm beside it
    assert len(at_read) == 6 and all(J._near(pos, tgt) for _loc, tgt, pos, _n in at_read), \
        at_read
    second_read_at = at_read[1][3] - n0
    assert second_read_at > moves[2] + 1, (second_read_at, moves)
    # both halves of every patch were taken (lamp and UV), and M1 / M2 were filed for the row
    rec = _row_record(job)
    assert rec["status"] == "read" and rec["conditions"]
    assert len(rec["dual_spot_results"]) == len(rec["accepted"]) == rec["patches"]
    assert all(d["ok"] for d in rec["dual_spot_results"])
    # the dual spot reading added no table line: every line is the released allow-list's
    for ln in sim.received:
        cl.classify((ln + "\r").encode())
    assert not any(ln.startswith((";m2", ";d1", ";c4")) for ln in sent)


def test_a_dual_patch_row_beside_twice_fails_cleanly_and_reads_nothing_there(tmp_path):
    from tests.i1io_table.test_4347_fix2_arrivals_and_aiming_again import _arrive_beside
    job, sim, helper, run, p = _job(tmp_path, args=SPOT)
    sim.jitter = False
    _ready(job, p)
    read_locs = []
    orig = job._read_patch

    def read(reader, patch, at=None):
        read_locs.append(patch.loc)
        return orig(reader, patch, at)
    job._read_patch = read
    _arrive_beside(sim, 2, 0, -8, reads=4)
    res = job.read_row()
    while res.kind == J.Kind.NEEDS and res.confirm != J.Confirm.ROW_FAILED:
        res = job.answer(res.confirm, "yes")
    assert res.confirm == J.Confirm.ROW_FAILED
    assert res.detail["why"] == "arrived_beside_the_target_again"
    assert len(read_locs) == 1                                  # patch 1 only; not the beside
    assert job._table.closed_reason is None and sim.violations == []


def test_a_dual_row_is_never_moved_to_a_second_time(tmp_path):
    """A dual ROW: the strip start arrival beside by 0.7 mm follows the row's own rule; no
    automatic second move, no repeated m0 target."""
    job, sim, helper, run, p = _job(tmp_path)
    sim.jitter = False
    _ready(job, p)
    _land_beside(sim, (1,), 0, -7)
    n0 = len(sim.received)
    res = job.read_row()
    while res.kind == J.Kind.NEEDS and res.confirm != J.Confirm.ROW_FAILED:
        res = job.answer(res.confirm, "yes")
    assert job.beside_retries == []
    sent = [ln for ln in sim.received[n0:] if _computed_m0(ln)]
    assert all(a != b for a, b in zip(sent, sent[1:])), sent
    assert sim.violations == []


def test_the_dual_row_code_never_asks_for_the_retry():
    src = inspect.getsource(J.TableJob._dual_strip_attempt)
    assert "_move_to(" in src and "retry_beside" not in src
    src = inspect.getsource(J.TableJob._row_attempt)
    assert "retry_beside=True" in src


def test_the_caps_add_both_sides_up():
    # the step cap of a patch row: 4n+4 + 2 x 3 lines, n + 2 x 1 movements (dual or not)
    assert cp.spot_row_step(33) == (4 * 33 + 4 + 6, 33 + 2)
    assert cp.DUAL_UV_PASS == (9, 2) and cp.DUAL_ROW == (cp.STRIP_ROW[0] + 9,
                                                         cp.STRIP_ROW[1] + 2) == (28, 6)
    for rows in [(33,) * 30, (24,) * 22, (33,), (6, 6)]:
        for dual in (False, True):
            need = [cp.ALIGN_CYCLE[i] + sum(cp.row_cost(n, dual)[i] for n in rows)
                    for i in (0, 1)]
            longest = max(cp.row_cost(n, dual) for n in rows)
            want = []
            for i in (0, 1):
                allow = (cp.ALLOWANCE_ALIGNMENTS * cp.ALIGN_CYCLE[i]
                         + cp.ALLOWANCE_ROWS * longest[i] + cp.CALIBRATION[i]
                         + cp.TILE_READING[i] + -(-cp.ALLOWANCE_FRACTION * need[i] // 1)
                         + (len(rows) + cp.ALLOWANCE_ROWS) * 2 * cp.BESIDE_RETRY[i])
                want.append(int(need[i] + allow))
            assert cp.page_caps(rows, dual) == tuple(want), (rows, dual)
    # the dual page needs more than the single-scan page only where a row is shorter than a
    # dual row; the second-move allowance is the same for both
    sheet = long_sheet()
    a, b = cp.caps_for_sheet(sheet), cp.caps_for_sheet(sheet, dual=True)
    assert b.lines > a.lines

"""Safety review 448, SHOULD-3: every automatic second move to a patch is written into the
session's diagnostics (the row's result block, ``data["second_moves"]``), not only into the log:
the target, the two readings before it, the reading(s) after it, and whether it cured the miss.
The real table's 0.6 to 1 mm arrivals are what the next tester round is to teach us."""
from __future__ import annotations

import json

import pytest

from tests.i1io_table.test_4347_fix2_arrivals_and_aiming_again import _arrive_beside
from tests.i1io_table.test_4348_an_arrival_beside_is_moved_to_once_more import (
    _land_beside, _ready)
from workflow.i1io.table import job as J


def _row_blocks(job):
    return [b for b in job.diag.blocks if (b.get("data") or {}).get("second_moves")]


@pytest.mark.parametrize("off", [(0, -6), (8, -8)])
def test_a_second_move_that_cured_the_miss_is_in_the_row_block(tmp_path, off):
    job, sim, p, seen = _ready(tmp_path)
    _land_beside(sim, (2,), *off)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "read"
    blocks = _row_blocks(job)
    assert len(blocks) == 1 and blocks[0] is job._last_block
    (e,) = blocks[0]["data"]["second_moves"]
    target = e["target"]
    beside = [target[0] + off[0], target[1] + off[1]]
    assert e["readings_before"] == [beside, beside]
    assert e["readings_after"] == [target]
    assert e["cured"] is True and e["result"] == "arrived"
    # and it is written down in the session's files and its log, not only kept in memory
    assert any(ln.startswith("RESULT") and "second_moves" in ln for ln in job.diag.lines)
    if job.diag.folder is not None:
        on_disk = json.loads((job.diag.folder / blocks[0]["folder"] / "result.json")
                             .read_text(encoding="utf-8"))
        assert on_disk["data"]["second_moves"][0]["cured"] is True


def test_a_second_move_that_stopped_beside_again_is_in_the_row_block(tmp_path):
    job, sim, p, seen = _ready(tmp_path, {J.Confirm.ROW_FAILED: "skip"})
    _arrive_beside(sim, 2, 0, 8, reads=4)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "skipped"
    (e,) = _row_blocks(job)[0]["data"]["second_moves"]
    target = e["target"]
    beside = [target[0], target[1] + 8]
    assert e["readings_before"] == [beside, beside]
    assert e["readings_after"] == [beside, beside]
    assert e["cured"] is False and e["result"] == "beside the target again"


def test_no_second_move_no_entry(tmp_path):
    job, sim, p, seen = _ready(tmp_path)
    assert p.drive(job.read_row()).ok
    assert _row_blocks(job) == []

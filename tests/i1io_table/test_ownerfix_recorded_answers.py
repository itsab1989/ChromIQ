"""What the volunteer's table answered on 17 Nov 2026, as test data (owner-results fix round).

Only wire lines and numbers, nothing private (no serial, no memory block, no tile values): the
"test data" list of the analysis of that night, items 2 to 6 (item 1, m1, is in
test_ownerfix_m1_lands_where_the_real_table_put_it.py).
"""
from __future__ import annotations

import pytest

from tests.i1io_table.test_job_reading import read_page, small_sheet
from tests.i1io_table.test_roundB_strip import _job, _ready
from workflow.i1io.table import job as J
from workflow.i1io.table import lines as cl
from workflow.i1io.table import scan as sc
from workflow.i1io.table import session_table as tbl


# ---- (2) c4 answered BC and BA; BC passes, BD stops --------------------------------------------

@pytest.mark.parametrize("line,byte", [(":$c40BC56", 0xBC), (":$c40BA58", 0xBA)])
def test_the_recorded_c4_answers_decode_and_are_inside_the_range(line, byte):
    rep = tbl.parse_done_c(line, "c4", cl.C_DATA_LEN["scan_c4"])
    assert int(rep.data, 16) == byte
    assert sc.C4_RANGE[0] <= byte <= sc.C4_RANGE[1]


def test_the_c4_range_is_the_recorded_one():
    assert sc.C4_RANGE == (0xB7, 0xBC)
    assert "BC" in cl.C_RECORDED_AT["scan_c4"] and "17 Nov 2026" in cl.C_RECORDED_AT["scan_c4"]


def test_a_strip_row_whose_c4_answers_bc_is_read(tmp_path):
    """Failed before this round: BC was 'never seen' and every such row failed."""
    job, sim, helper, run, p = _job(tmp_path, sheet=small_sheet())
    sim.c_faults["c4_byte"] = 0xBC
    _ready(job, p)
    rows = read_page(job, p)
    assert rows and all(r.ok and r.detail["row_kind"] == "strip" for r in rows)


def test_a_strip_row_whose_c4_answers_bd_stops_cleanly(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, sheet=small_sheet(),
                                    script={J.Confirm.ROW_FAILED_STRIP: "stop"})
    sim.c_faults["c4_byte"] = 0xBD
    _ready(job, p)
    n_m2 = sum(1 for ln in sim.received if ln.startswith(";m2"))
    r = p.drive(job.read_row())
    assert r.kind == J.Kind.REFUSED and r.reason == "stopped_after_a_failed_row"
    asked = [a for a in p.asked if a[1] == J.Confirm.ROW_FAILED_STRIP]
    assert len(asked) == 1 and asked[0][2]["why"].startswith("strip_")
    # no scan move after the unknown answer, nothing pending
    assert sum(1 for ln in sim.received if ln.startswith(";m2")) == n_m2
    assert not r.state.strip_move_may_be_pending

"""4.3.69, item 77: A DUAL ROW REFUSED BY THE PAIRING KEEPS NOTHING, ITS LAMP PASS INCLUDED.

The pairing check (the helper's ``cq_dual_pairing``, ``workflow.dual_scan.pairing``) refuses a row
whose two passes do not fit each other, and nothing tells which of the two is wrong. A lamp that
fades during its pass is refused there as often as a UV pass that fails, and until 4.3.68 the lamp
pass was then kept as M0 (on the owner's 52 recorded dual rows: a lamp at half its light from the
middle of the row, kept 50 times, up to 15.9 dE00; measured privately, numbers only). A UV pass
that fails before or while it runs (not the pairing) still leaves the lamp pass as M0."""
from __future__ import annotations

import json

import numpy as np
import pytest

from tests.i1io_table.test_dual_table import _job, _ready, _until
from workflow.dual_scan import pairing as pr
from workflow.dual_scan.model import WAVELENGTHS, DualCalibration
from workflow.dual_scan.reasons import DualScanRefused
from workflow.i1io.table import job as J


def _record(job):
    folder = job.diag.folder
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(folder.rglob("*.row.json"))]


def test_the_list_is_the_helpers_two_pairing_reasons():
    assert J.PAIRING_REASONS == ("uv_pass_wrong_strip", "uv_pass_no_uv_light")


@pytest.mark.parametrize("fault, why", [("uv_wrong_strip", "uv_pass_wrong_strip"),
                                        ("uv_no_light", "uv_pass_no_uv_light")])
def test_a_row_the_pairing_refused_keeps_no_m0(tmp_path, fault, why):
    job, sim, helper, run, p = _job(tmp_path, faults={"scan": {fault: True}})
    _ready(job, p)
    res = _until(job, job.read_row(), J.Confirm.ROW_FAILED_STRIP)
    assert res.detail["why"] == why
    rec = _record(job)[0]
    assert rec["accepted"] == [] and not rec.get("m0_only") and not rec.get("reader_ti3")
    assert not list(job.diag.folder.rglob("*.lamp_only_cut.json"))
    log = "\n".join(f.read_text(encoding="utf-8", errors="replace")
                    for f in job.diag.folder.rglob("*.log"))
    assert "nothing of the row is kept, its lamp pass included" in log
    # the row is offered again as after any failed row
    assert res.kind == J.Kind.NEEDS and res.confirm == J.Confirm.ROW_FAILED_STRIP


def test_a_uv_pass_that_would_not_start_still_keeps_the_lamp_pass(tmp_path):
    """Not the pairing: the UV pass never ran. The lamp pass is the row's own, kept as M0."""
    job, sim, helper, run, p = _job(tmp_path, faults={"scan": {"uv_not_ready": True}})
    _ready(job, p)
    res = _until(job, job.read_row(), J.Confirm.ROW_FAILED_STRIP)
    assert res.detail["why"] == "uv_pass_failed_clean"
    rec = _record(job)[0]
    assert rec["m0_only"] == "uv_pass_failed_clean" and rec["accepted"]


def _row(n=24, seed=4):
    """A row as tests/test_i1pro2_dual_scan_pairing_c.py builds one (the tile's light at the LED
    bands only)."""
    rng = np.random.default_rng(seed)
    nb = len(WAVELENGTHS)
    w = np.full(nb, 0.9)
    t = np.where(WAVELENGTHS <= 410, 0.2, 0.02)
    lamp = np.array([np.full(nb, v) for v in rng.uniform(0.1, 0.9, n)])
    uv = lamp * (t / w)[None, :]
    return lamp, uv, DualCalibration(w, t, np.full(nb, 1000.0))


@pytest.mark.parametrize("fade", [0.5, 0.02])
def test_the_pairing_refuses_a_lamp_that_fades_in_the_middle_of_the_row(fade):
    """What this rule protects: the pairing DOES refuse such a row, so keeping nothing of it is
    what keeps the dim half out of the measurement."""
    lamp, uv, cal = _row()
    assert pr.check_pairing(lamp, uv, cal).checked
    faded = lamp.copy()
    faded[len(faded) // 2:] *= fade
    with pytest.raises(DualScanRefused) as e:
        pr.check_pairing(faded, uv, cal)
    assert e.value.reason in J.PAIRING_REASONS

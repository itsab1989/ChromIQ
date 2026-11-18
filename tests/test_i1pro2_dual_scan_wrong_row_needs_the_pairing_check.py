"""The i1Pro 2 dual scan: a UV pass made over ANOTHER ROW must not give M1 / M2.

Independent safety review, 2026-11-18 (finding: MUST). On a printed chart the rows' patches sit
at the same positions along the strip, so a UV pass over the neighbouring row is cut into the
lamp pass's cells with full coverage and perfectly flat cells: the travel verdicts and the
alignment gate (0.01) all accept it. The only gate that tells the rows apart is the pairing check
(workflow/dual_scan/pairing.py, spec section 2a: "it belongs to the strip",
``uv_pass_wrong_strip``), and the instrument path built in step 2
(native/chartread_helper/chromiq_dualdev.c, ``cq_dd_strip``) does not run it: it goes from
``cq_dual_cut`` straight to ``cq_dd_compute``.

The first test proves, on the Python twin of the cut (held bit-equal to the C cut by
tests/test_i1pro2_dual_scan_engine.py), that the cut accepts such a pass and that the pairing
check refuses it, and how wrong M2 then is. The second is a strict xfail until the helper's strip
path applies the pairing check; it turns red (XPASS) when it does, so remove the mark then.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from workflow.dual_scan.cut import cut_uv_pass
from workflow.dual_scan.model import WAVELENGTHS, DualCalibration, UVTables, compute
from workflow.dual_scan.pairing import check_pairing
from workflow.dual_scan.reasons import DualScanRefused

ROOT = Path(__file__).resolve().parent.parent
NB = WAVELENGTHS.size


def _calibration() -> DualCalibration:
    w = np.full(NB, 0.9)
    t = np.where(WAVELENGTHS <= 410, 0.2, 0.02)          # the UV LED's tail on the tile
    e = np.full(NB, 1000.0)                                # Te 380-410 = 222 >= 100
    return DualCalibration(w, t, e)


def _tables() -> UVTables:
    ka = np.where((WAVELENGTHS >= 410) & (WAVELENGTHS <= 550), 1e-4, 0.0)
    return UVTables.from_values(ka, 1.6 * ka)


def _row(levels: "list[float]", glow: float) -> "tuple[np.ndarray, np.ndarray]":
    """Lamp and UV readings of one row: flat spectra at *levels*; the UV reading follows
    (T/W) x lamp, plus a glow in 420-500 nm."""
    cal = _calibration()
    L = np.array([np.full(NB, v) for v in levels])
    tw = cal.uv_tile / cal.white
    U = L * tw[None, :] + glow * ((WAVELENGTHS >= 420) & (WAVELENGTHS <= 500))[None, :] * L
    return L, U


def _pass(cells_uv: np.ndarray, per_cell: int = 6):
    """Lamp cells of 10 readings at positions 0..; a UV pass with *per_cell* readings over
    each cell's middle (backwards, as the recorded UV pass runs), each reading = its cell."""
    n = cells_uv.shape[0]
    cells = [(10 * k, 10) for k in range(n)]
    lamp_pos = np.arange(10 * n, dtype=float)
    up, ur = [], []
    for k in reversed(range(n)):
        for i in range(per_cell):
            up.append(10 * k + 3.0 + 3.0 * i / (per_cell - 1))
            ur.append(cells_uv[k])
    return cells, lamp_pos, np.array(up), np.array(ur)


ROW_A = [0.85, 0.20, 0.55, 0.10, 0.70, 0.35, 0.90, 0.15]      # the strip the lamp pass read
ROW_B = [0.30, 0.80, 0.12, 0.65, 0.25, 0.90, 0.40, 0.60]      # the next row on the sheet


def test_the_cut_accepts_a_uv_pass_over_another_row_and_only_the_pairing_check_refuses_it():
    LA, UA = _row(ROW_A, glow=0.08)
    _LB, UB = _row(ROW_B, glow=0.08)
    cut = cut_uv_pass(*_pass(UB))              # travel and alignment: all accepted
    assert cut.aligned_checked and cut.flatness <= 0.01
    assert min(cut.counts) >= 3
    with pytest.raises(DualScanRefused) as e:
        check_pairing(LA, cut.uv, _calibration())
    assert e.value.reason == "uv_pass_wrong_strip"
    # and the right pass is accepted by both
    right = cut_uv_pass(*_pass(UA))
    assert check_pairing(LA, right.uv, _calibration()).checked
    # what the missing check would let through: M2 of row A from row B's UV light
    good = compute(LA, right.uv, _calibration(), _tables(), 1.156)
    bad = compute(LA, cut.uv, _calibration(), _tables(), 1.156)
    assert np.abs(bad.m2 - good.m2).max() > 0.01     # visibly wrong, silently


def _code(path: Path) -> str:
    return re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8", errors="replace"), flags=re.S)


@pytest.mark.xfail(strict=True, reason="safety review 2026-11-18, MUST: the instrument path's hand "
                   "strip (cq_dd_strip) has no pairing check; remove this mark when it has")
def test_the_instrument_path_checks_that_the_uv_pass_belongs_to_the_strip():
    src = _code(ROOT / "native" / "chartread_helper" / "chromiq_dualdev.c")
    i = src.index("static void cq_dd_strip(")
    body = src[i:src.index("\n}\n", i)]
    assert "wrong_strip" in body or "pairing" in body

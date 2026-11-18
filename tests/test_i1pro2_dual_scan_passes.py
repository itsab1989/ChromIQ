"""The two passes of a hand i1Pro 2 dual scan are two units (the owner,
2026-11-18): each has its own verdict, a failed one is read again alone, a
UV pass is proved to belong to its strip's lamp pass, and M1 / M2 are offered
only when every strip has both. SYNTHETIC data (an invented instrument)."""
from __future__ import annotations

import numpy as np
import pytest

from workflow.dual_scan import cut, model, pairing, record
from workflow.dual_scan.reasons import REASONS, DualScanRefused

WL = model.WAVELENGTHS
BAND = (WL >= 410) & (WL <= 550)


def _inst():
    x = (WL - 410) / 140.0
    kA = np.where(BAND, 1.2e-4 * (1.0 + 0.8 * np.sin(np.pi * x)), 0.0)
    kD = np.where(BAND, kA * (1.6 + 0.9 * x), 0.0)
    cal = model.DualCalibration(0.9 + 0.02 * np.cos(WL / 50.0),
                                0.012 * np.exp(-(WL - 380) / 25.0) + 1e-4,
                                2.4e4 * (1.0 + 0.3 * (WL - 380) / 350.0), 139, 139)
    return model.UVTables.from_values(kA[:18], kD[:18]), cal


def _strip(seed, n=20, glow=900.0):
    rng = np.random.default_rng(seed)
    m2 = np.clip(rng.uniform(0.05, 0.9, (n, 1)) * (0.8 + 0.4 * rng.random((n, 36))), 0.02, 0.95)
    g = m2.mean(axis=1, keepdims=True) * glow * np.exp(-0.5 * ((WL - 440) / 25.0) ** 2)
    tab, cal = _inst()
    L, U, _ = model.forward(m2, g, cal, tab, 1.15)
    return L, U


# ----------------------------------------------------------------- pairing

def test_a_uv_pass_belongs_to_its_own_lamp_pass_and_not_to_another():
    _tab, cal = _inst()
    La, Ua = _strip(1)
    Lb, Ub = _strip(2)
    ev = pairing.check_pairing(La, Ua, cal)
    assert ev.correlation > 0.999 and ev.median_ratio_error < 1e-9
    for L, U in ((La, Ub), (Lb, Ua)):
        with pytest.raises(DualScanRefused) as e:
            pairing.check_pairing(L, U, cal)
        assert e.value.reason == "uv_pass_wrong_strip"


def test_the_pairing_check_needs_no_glow():
    _tab, cal = _inst()
    La, Ua = _strip(1, glow=0.0)
    Lb, _ = _strip(2, glow=0.0)
    pairing.check_pairing(La, Ua, cal)
    with pytest.raises(DualScanRefused):
        pairing.check_pairing(Lb, Ua, cal)


def test_a_strip_of_one_colour_is_judged_by_the_ratio_only():
    _tab, cal = _inst()
    L = np.full((10, 36), 0.5)
    tw = cal.uv_tile / cal.white
    U = L * tw
    ev = pairing.check_pairing(L, U, cal)
    assert ev.correlation != ev.correlation          # nan: not asked
    with pytest.raises(DualScanRefused):
        pairing.check_pairing(L, U * 1.3, cal)       # 30 % off


# ----------------------------------------------------------------- travel verdicts

@pytest.mark.parametrize("counts,want", [
    ([5, 5, 5, 5], None),
    ([0, 5, 5, 5], "uv_pass_short"),
    ([5, 5, 5, 0], "uv_pass_short"),
    ([5, 0, 5, 5], "uv_pass_stalled"),
    ([5, 2, 5, 5], "uv_pass_too_fast"),
    ([], "uv_pass_count"),
])
def test_each_travel_failure_has_its_own_reason(counts, want):
    assert cut.travel_verdict(counts) == want
    if want:
        assert REASONS[want]


def test_either_direction_is_a_good_pass_and_the_ruler_says_which():
    assert cut.pass_direction([0, 10, 20]) == 1
    assert cut.pass_direction([20, 10, 0]) == -1
    assert cut.pass_direction([5, 5]) == 0


def test_a_ruler_that_stood_still_is_a_stalled_pass():
    lp = np.arange(40) * 7.0
    up = np.r_[np.full(30, 100.0), np.arange(10.0)]
    with pytest.raises(DualScanRefused) as e:
        cut.cut_uv_pass([(k * 10, 10) for k in range(4)], lp, up, np.ones((40, 36)))
    assert e.value.reason == "uv_pass_stalled"


# ----------------------------------------------------------------- the record

def _record():
    _tab, cal = _inst()
    r = record.PassRecord(["A", "B", "C"])
    r.add_calibration("c1", cal)
    return r, {s: _strip(i + 1) for i, s in enumerate("ABC")}


def test_lamp_passes_alone_make_an_honest_m0_and_no_m1_m2():
    r, d = _record()
    for s in "ABC":
        assert r.lamp_read(s, d[s][0], "c1") == record.MISSING
    assert not r.complete()
    assert r.missing() == [("A", "uv"), ("B", "uv"), ("C", "uv")]
    assert r.strips_with_both() == []


def test_a_failed_uv_pass_is_read_again_alone_and_the_lamp_pass_is_kept():
    r, d = _record()
    r.lamp_read("A", d["A"][0], "c1")
    r.pass_failed("A", "uv", "uv_pass_too_fast")
    assert r.uv["A"].state == record.FAILED and r.uv["A"].reason == "uv_pass_too_fast"
    assert r.lamp["A"].state == record.OK
    assert ("A", "lamp") not in r.missing() and ("A", "uv") in r.missing()
    assert r.uv_read("A", d["A"][1], "c1") == record.OK
    assert ("A", "uv") not in r.missing()


def test_a_uv_pass_of_another_strip_is_refused_and_a_good_one_is_kept():
    r, d = _record()
    r.lamp_read("A", d["A"][0], "c1")
    assert r.uv_read("A", d["B"][1], "c1") == record.FAILED
    assert r.uv["A"].reason == "uv_pass_wrong_strip"
    assert r.uv_read("A", d["A"][1], "c1") == record.OK
    # a later wrong UV pass does not throw the good one away
    assert r.uv_read("A", d["C"][1], "c1") == record.FAILED
    assert r.uv["A"].state == record.OK


def test_a_uv_pass_before_its_lamp_pass_is_refused():
    r, d = _record()
    with pytest.raises(DualScanRefused) as e:
        r.uv_read("A", d["A"][1], "c1")
    assert e.value.reason == "uv_pass_missing"


def test_a_lamp_pass_read_again_keeps_its_uv_pass_only_when_it_still_belongs():
    r, d = _record()
    r.lamp_read("A", d["A"][0], "c1")
    r.uv_read("A", d["A"][1], "c1")
    # the same strip read again (a little noise): the UV pass still belongs
    again = d["A"][0] * (1 + 1e-3)
    assert r.lamp_read("A", again, "c1") == record.OK
    # another strip's readings filed as A: the UV pass no longer fits
    assert r.lamp_read("A", d["B"][0], "c1") == record.STALE
    assert r.uv["A"].reason == "lamp_pass_changed"
    assert ("A", "uv") in r.missing()


def test_a_failed_lamp_re_read_keeps_the_good_lamp_pass():
    r, d = _record()
    r.lamp_read("A", d["A"][0], "c1")
    r.pass_failed("A", "lamp", "misread")
    assert r.lamp["A"].state == record.OK


def test_m1_m2_only_when_every_strip_has_both_and_two_calibrations_are_recorded():
    r, d = _record()
    _tab, cal = _inst()
    for s in "AB":
        r.lamp_read(s, d[s][0], "c1")
        r.uv_read(s, d[s][1], "c1")
    r.lamp_read("C", d["C"][0], "c1")
    assert not r.complete() and r.strips_with_both() == ["A", "B"]
    # "Continue Measurement" later: a new dual calibration, only C's UV pass
    r.add_calibration("c2", cal)
    assert r.missing() == [("C", "uv")]
    r.uv_read("C", d["C"][1], "c2")
    assert r.complete()
    assert r.calibrations_used() == ["c1", "c2"] and r.more_than_one_calibration()


def test_the_record_survives_a_save_and_load(tmp_path):
    r, d = _record()
    r.lamp_read("A", d["A"][0], "c1")
    r.uv_read("A", d["A"][1], "c1")
    r.pass_failed("B", "lamp", "misread")
    p = tmp_path / "dual_scan" / "chart.passes.json"
    r.save(p)
    q = record.PassRecord.load(p)
    assert q.to_json() == r.to_json()
    assert "serial" not in p.read_text(encoding="utf-8").lower()


def test_no_glow_accepts_a_pairing_that_could_not_change_the_result():
    r, d = _record()
    r.lamp_read("A", d["A"][0], "c1")
    assert r.uv_read("A", d["B"][1], "c1", glowing=False) == record.OK


def test_the_record_lives_beside_the_conditions_folder(tmp_path):
    from core.file_manager import Run
    m = tmp_path / "proj" / "runs" / "run1" / "chart.ti3"
    assert Run.dual_pass_record(m) == m.parent / "dual_scan" / "chart.passes.json"

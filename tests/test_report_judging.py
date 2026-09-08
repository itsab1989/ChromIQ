"""#182: how a report is judged against a limit set.

The nearest-rank 95th percentile, the grey-ramp and tone-ramp blocks, the
per-row values, the verdict words on real (synthetic) measurements, the stamped
record and its old-form shim, the in-place rewrite and the mixed-set warning.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

import workflow.measurement_report as mr
from workflow.compliance_sets import (COND, FAIL, INFO, N_A, PASS, Limit,
                                      factory_limits)
from workflow.ti3_analysis import mark_verification_ti3


# ---- a synthetic measurement whose reference is the device RGB read as sRGB ----

def _xyz_d50(r, g, b):
    from workflow.i1profiler_import import _patch_xyz
    return mr._bradford_d65_to_d50(*_patch_xyz(float(r), float(g), float(b)))


def _write_ti3(path: Path, patches, *, verification=True, cast=None):
    """*patches*: (R, G, B) on 0..100. The measured XYZ equals the design XYZ,
    except the patches in *cast* ``{index: (da, db)}`` which are pushed off
    neutral by that Lab a*/b* amount."""
    lines = ["CTI3", "", 'DESCRIPTOR "synthetic"', "NUMBER_OF_FIELDS 7",
             "BEGIN_DATA_FORMAT", "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(patches)}", "BEGIN_DATA"]
    for i, (r, g, b) in enumerate(patches, start=1):
        x, y, z = _xyz_d50(r, g, b)
        if cast and (i - 1) in cast:
            from workflow.icc_info import xyz_to_lab
            L, a, bb = xyz_to_lab((x / 100, y / 100, z / 100))
            da, db = cast[i - 1]
            x, y, z = (v * 100 for v in _lab_to_xyz((L, a + da, bb + db)))
        lines.append(f"{i} {r:.2f} {g:.2f} {b:.2f} {x:.4f} {y:.4f} {z:.4f}")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    if verification:
        return mark_verification_ti3(path)      # renames to <stem>-verify.ti3
    return path


def _lab_to_xyz(lab):
    """D50 Lab → XYZ (0..1)."""
    L, a, b = lab
    fy = (L + 16) / 116
    fx = fy + a / 500
    fz = fy - b / 200
    def finv(t):
        return t ** 3 if t ** 3 > 0.008856 else (t - 16 / 116) / 7.787
    xn, yn, zn = 0.9642, 1.0, 0.8249
    return finv(fx) * xn, finv(fy) * yn, finv(fz) * zn


def _ramp(steps):
    return [(g, g, g) for g in np.linspace(0, 100, steps)]


def _colours(n=24):
    """Enough non-grey patches for a 95 % split."""
    out = []
    for i in range(n):
        out.append((100 - 4 * i, 30 + 2 * i, 60))
    return out


# ---- _stats ---------------------------------------------------------------------

def test_p95_is_nearest_rank_and_the_split_is_the_same_patch():
    a = np.arange(1, 1618, dtype=float)           # 1617 patches, values 1..1617
    s = mr._stats(list(a))
    assert s["p95"] == 1537.0                      # ceil(0.95 * 1617) = 1537
    assert s["max_low95"] == 1537.0
    assert s["avg_high5"] == pytest.approx(np.mean(a[1537:]))
    assert s["p95_rule"] == "nearest-rank" and s["small_sample"] is False
    s60 = mr._stats(list(np.arange(1, 61, dtype=float)))
    assert s60["p95"] == 57.0                      # unchanged where round == ceil


def test_below_twenty_patches_the_worst_five_percent_is_empty():
    s = mr._stats([1.0] * 18 + [5.0])
    assert s["small_sample"] is True
    assert s["avg_high5"] is None
    assert s["avg_low95"] == s["avg_all"] and s["p95"] == s["max_all"]


# ---- the grey ramp --------------------------------------------------------------

def test_a_sixteen_step_neutral_ramp_is_eligible_and_the_cast_is_found(tmp_path):
    patches = _ramp(16) + _colours()
    ti3 = _write_ti3(tmp_path / "v.ti3", patches, cast={8: (2.0, -1.5)})
    rep = mr.build_report(ti3)
    assert rep["reference_source"] == "device"
    gb = rep["grey_balance"]
    assert gb["eligible"] and gb["levels"] == 16 and gb["reason"] is None
    assert len(gb["per_level"]) == 15                # the paper patch is not in the statistics
    assert gb["max"] == pytest.approx(math.hypot(2.0, -1.5), abs=0.02)
    assert gb["avg"] == pytest.approx(gb["max"] / 15, abs=0.02)


def test_chromiqs_own_eight_step_ramp_passes_the_eligibility_rule(tmp_path):
    """CH-10: the paper patch counts as a level, so ChromIQ's 'Neutral grey
    ramp' generator with 8 steps (0, 14.3, …, 85.7, 100) is eligible."""
    ti3 = _write_ti3(tmp_path / "v.ti3", _ramp(8) + _colours())
    gb = mr.build_report(ti3)["grey_balance"]
    assert gb["eligible"] and gb["levels"] == 8


@pytest.mark.parametrize("patches, reason", [
    (_ramp(5) + _colours(), mr.REASON_TOO_FEW_STEPS),
    ([(g, g, g) for g in np.linspace(0, 80, 10)] + _colours(), mr.REASON_NO_WHITE),
    ([(g, g, g) for g in np.linspace(20, 100, 10)] + _colours(), mr.REASON_NO_BLACK),
    (_colours(), mr.REASON_NO_GREYS),
])
def test_an_ineligible_ramp_says_why(tmp_path, patches, reason):
    gb = mr.build_report(_write_ti3(tmp_path / "v.ti3", patches))["grey_balance"]
    assert not gb["eligible"] and gb["reason"] == reason and gb["avg"] is None


def test_near_greys_within_one_device_unit_count_and_beyond_do_not():
    rgb = np.array([[50, 50.9, 50], [50, 52, 50], [100, 100, 100], [0, 0, 0]], float)
    lab = [(50, 0, 0)] * 4
    ref = {"1": (50, 0, 0), "2": (50, 0, 0), "3": (100, 0, 0), "4": (0, 0, 0)}
    gb = mr.grey_balance_block(rgb, lab, ref, ["1", "2", "3", "4"])
    assert gb["n_greys"] == 3                         # the 52 is not a grey


# ---- the tone ramps -------------------------------------------------------------

def test_a_red_ramp_through_the_30_to_70_band_is_eligible(tmp_path):
    ramp = [(100 - tv, 100, 100) for tv in (0, 20, 30, 40, 50, 60, 70, 90)]
    ti3 = _write_ti3(tmp_path / "v.ti3", ramp + _colours())
    rp = mr.build_report(ti3)["ramps_30_70"]
    assert rp["eligible"] and rp["axes"]["R"]["eligible"]
    assert rp["axes"]["R"]["steps"] == 5 and rp["axes"]["R"]["span"] == 40.0
    assert rp["axes"]["G"]["eligible"] is False
    assert rp["max_dl"] == pytest.approx(0.0, abs=0.01)


def test_two_steps_are_not_a_ramp(tmp_path):
    ti3 = _write_ti3(tmp_path / "v.ti3", [(70, 100, 100), (30, 100, 100)] + _colours())
    rp = mr.build_report(ti3)["ramps_30_70"]
    assert not rp["eligible"] and rp["reason"] == mr.REASON_NO_RAMP


# ---- grading rules ---------------------------------------------------------------

def test_a_profiling_measurement_is_not_graded_a_verification_is(tmp_path):
    prof = mr.build_report(_write_ti3(tmp_path / "p.ti3", _colours(), verification=False))
    ver = mr.build_report(_write_ti3(tmp_path / "v.ti3", _colours()))
    assert not mr.is_graded_sheet(prof)
    assert mr.is_graded_sheet(ver)
    ver["printing"] = {"colour": "raw"}
    assert mr.is_drift_check(ver) and not mr.is_graded_sheet(ver)


def test_grey_rows_are_info_until_the_printing_method_is_recorded(tmp_path):
    ti3 = _write_ti3(tmp_path / "v.ti3", _ramp(16) + _colours(), cast={8: (5.0, 0.0)})
    rep = mr.build_report(ti3)
    rows = {r["row_id"]: r for r in mr.judge(rep, factory_limits("chromiq_default"))}
    assert rows["grey_balance_neutral_ramp_max"]["word"] == INFO          # CH-17
    assert rows["grey_balance_neutral_ramp_max"]["reason"] == mr.REASON_PRINTING_UNRECORDED
    assert rows["all_de00_avg"]["word"] == PASS
    rep["printing"] = {"colour": "through-profile", "intent": "relative", "route": "chromiq"}
    rows = {r["row_id"]: r for r in mr.judge(rep, factory_limits("chromiq_default"))}
    assert rows["grey_balance_neutral_ramp_max"]["word"] == COND         # 5.0 > (3.0), a should
    assert rows["grey_balance_neutral_ramp_avg"]["word"] == PASS


def test_rows_the_chart_cannot_supply_read_n_a_with_a_reason(tmp_path):
    rep = mr.build_report(_write_ti3(tmp_path / "v.ti3", _colours(12)))     # 12 patches
    rows = {r["row_id"]: r for r in mr.judge(rep, factory_limits("chromiq_default"))}
    assert rows["worst5_de00_avg"]["word"] == N_A
    assert rows["worst5_de00_avg"]["reason"] == mr.REASON_SMALL_SAMPLE
    assert rows["best95_de00_avg"]["word"] == PASS                         # over all patches
    assert rows["grey_balance_neutral_ramp_avg"]["word"] == N_A
    assert rows["grey_balance_neutral_ramp_avg"]["reason"] == mr.REASON_NO_GREYS
    # rows needing a reference file are not rows of a ChromIQ set (limit –, no value)
    assert "substrate_de00_max" not in rows


def test_fail_and_the_summary(tmp_path):
    rep = mr.build_report(_write_ti3(tmp_path / "v.ti3", _colours(),
                                     cast={i: (6.0, 6.0) for i in range(24)}))
    limits = factory_limits("chromiq_default")
    rows = mr.judge(rep, limits)
    words = {r["row_id"]: r["word"] for r in rows}
    assert words["all_de00_avg"] == FAIL and words["all_de00_max"] == FAIL
    s = mr.summarise(rep, limits, rows, "chromiq_default")
    assert s.word == FAIL and s.failed >= 2
    # the same numbers under a limit set that requires nothing readable → N-A
    empty = {rid: Limit.none() for rid in limits}
    assert mr.summarise(rep, empty, mr.judge(rep, empty), "chromiq_default").word == N_A


# ---- the stamped record ------------------------------------------------------------

def test_stamp_writes_the_old_pair_the_new_block_and_the_words(tmp_path):
    rep = mr.build_report(_write_ti3(tmp_path / "v.ti3", _ramp(16) + _colours()))
    rep["printing"] = {"colour": "through-profile", "intent": "relative", "route": "chromiq"}
    mr.stamp_verdict(rep, factory_limits("chromiq_tight"), set_id="chromiq_tight",
                     set_label="ChromIQ tight")
    assert rep["pass_thresholds"] == {"avg": 1.0, "max": 1.5}
    c = rep["compliance"]
    assert c["set_id"] == "chromiq_tight" and c["set_label"] == "ChromIQ tight"
    assert c["thresholds"]["all_de00_avg"] == 1.0 and c["edited"] is False
    assert c["thresholds"]["grey_balance_neutral_ramp_avg"] == [1.0, "should"]
    v = rep["verdict"]
    assert v["graded"] is True and v["all_pass"] is True and v["overall"] == PASS
    keys = {r["key"] for r in v["rows"]}
    assert {"avg_all", "avg_low95", "avg_high5", "max_all", "max_low95"} <= keys
    assert all(r["word"] in (PASS, FAIL, COND, INFO, N_A) for r in v["rows"])
    assert mr.recorded_compliance(rep) is c
    assert mr.recorded_thresholds(rep) == (1.0, 1.5)
    # and it survives JSON
    back = json.loads(json.dumps(rep))
    assert mr.recorded_compliance(back)["set_id"] == "chromiq_tight"


def test_the_old_two_number_form_still_works(tmp_path):
    rep = mr.build_report(_write_ti3(tmp_path / "v.ti3", _colours()))
    mr.stamp_verdict(rep, 2.5, 3.5)
    assert rep["pass_thresholds"] == {"avg": 2.5, "max": 3.5}
    assert rep["compliance"]["set_id"] == "pair"
    assert rep["compliance"]["thresholds"]["worst5_de00_avg"] == 2.5
    assert rep["compliance"]["thresholds"]["all_de00_p95"] == 3.5


def test_a_profiling_report_is_stamped_as_not_graded(tmp_path):
    rep = mr.build_report(_write_ti3(tmp_path / "p.ti3", _colours(), verification=False))
    mr.stamp_verdict(rep, factory_limits("chromiq_default"))
    assert rep["verdict"]["graded"] is False and rep["verdict"]["all_pass"] is None
    assert rep["verdict"]["overall"] == INFO
    # every computed row is INFO; a row the chart cannot supply stays N-A
    assert all(r["word"] == (INFO if r["value"] is not None else N_A)
               for r in rep["verdict"]["rows"])


def test_recorded_compliance_is_tolerant():
    assert mr.recorded_compliance({}) is None
    assert mr.recorded_compliance({"compliance": "junk"}) is None
    assert mr.recorded_compliance({"compliance": {"set_id": "x"}}) is None
    assert mr.recorded_compliance({"compliance": {"thresholds": {}}}) == {"thresholds": {}}


def test_rewrite_keeps_the_file_name_and_replaces_the_content(tmp_path):
    p = tmp_path / "report_2026-01-01_10-00-00.json"
    p.write_text("{}", encoding="utf-8")
    assert mr.rewrite_report(p, {"a": 1}) == p
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}
    assert list(tmp_path.iterdir()) == [p]


def test_report_scope_warns_when_two_limit_sets_meet():
    def run(label, created):
        return {"chart": "P", "created": created, "instrument": "i1",
                "compliance": {"set_id": label, "set_label": label,
                               "thresholds": {"all_de00_avg": 2.0}}}
    scope = mr.report_scope([run("ChromIQ default", "2026-01-01T10:00:00"),
                             run("ChromIQ tight", "2026-02-01T10:00:00")])
    kinds = [w["kind"] for w in scope["warnings"]]
    assert "compliance" in kinds
    assert mr.report_scope([run("ChromIQ default", "2026-01-01T10:00:00")] * 2)["warnings"] == []

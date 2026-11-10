"""Battery v3.1 (Agent 16b, 2026-10-05): the blind spots of battery v3.

Every metric added by protocol v3.1 is tested here, and each one is shown to
CATCH ITS ORIGINAL DEFECT on a saved defective profile (research-integration-2
builds from Agent 23's blind-spot hunt), against a profile without it.

* <= 4 inks: the defective profiles are committed, xz-compressed, in
  ``tests/data/v31_defects`` (X3 CMYK and X1 RGB, Maximum accuracy and
  colprof from the same .ti3, battery v3 targen 900, typical, seed 23).
* 5-7 inks (X5, X7, S5, FOGRA55: 5-7 MB each): the saved profiles live in the
  research folder (``Validation/v31-defect-profiles``, SHA256SUMS there);
  those tests skip when it is absent (CI), and say so.
"""
from __future__ import annotations

import json
import lzma
import os
from pathlib import Path

import numpy as np
import pytest

from benchmarks.research import metrics, oogq, stats3
from benchmarks.research.printers import build_printers

HERE = Path(__file__).resolve().parent
DEFECTS = HERE / "data" / "v31_defects"
WORKSPACE = Path(os.environ.get("CHROMIQ_V31_DEFECTS",
                                "/Users/Basti/develop/ProfileEngineResearch/Validation/"
                                "v31-defect-profiles"))
ARGYLL = Path("/Applications/Argyll/bin/icclu")
needs_ws = pytest.mark.skipif(not WORKSPACE.exists(),
                              reason="5-7 ink defect profiles are in the research folder only")


@pytest.fixture(scope="module")
def printers():
    return build_printers()


def _icc(name: str, tmp: Path) -> Path:
    out = tmp / f"{name}.icc"
    if not out.exists():
        out.write_bytes(lzma.decompress((DEFECTS / f"{name}.icc.xz").read_bytes()))
    return out


@pytest.fixture(scope="module")
def q(printers, tmp_path_factory):
    """oogq of the four committed profiles (computed once)."""
    tmp = tmp_path_factory.mktemp("v31")
    out = {}
    for name, pid in (("X3-accurate", "X3"), ("X3-colprof", "X3"),
                      ("X1-accurate", "X1"), ("X1-colprof", "X1")):
        r = oogq.evaluate(_icc(name, tmp), printers[pid])
        assert not r["errors"], r["errors"]
        out[name] = r["q"]
    return out


# ---------------------------------------------------------------------------
# the registry
# ---------------------------------------------------------------------------

def test_every_key_has_a_direction_a_floor_and_a_finding():
    for k, (sign, floor, safety, finding, what) in oogq.KEYS.items():
        assert sign in (1, -1) and floor > 0 and isinstance(safety, bool), k
        assert finding and what, k
    # the safety rows the brief asks for (D-17 2c)
    for k in ("oog_ramp_rev_r", "image_contours_r", "ramp_rev_p", "ramp_rev_s",
              "grey_swing_p", "grey_swing_s", "grey_swing_r", "below_black_swing_r",
              "black_gap_p", "black_C_p"):
        assert oogq.KEYS[k][2], k


def test_the_referee_imports_the_shared_hunt_code_and_no_engine_code():
    src = (HERE.parent / "benchmarks/research/oogq.py").read_text(encoding="utf-8")
    assert "from benchmarks.research.blindspots import hunt, xf" in src
    assert "workflow" not in src.split('"""', 2)[2]


@pytest.mark.skipif(not ARGYLL.exists(), reason="ArgyllCMS not installed")
def test_every_scored_key_is_produced(q):
    produced = set(q["X3-accurate"])
    missing = {k for k in oogq.KEYS if k not in produced}
    assert not missing, missing


# ---------------------------------------------------------------------------
# each metric catches its original defect (<= 4 inks, committed profiles)
# ---------------------------------------------------------------------------

def _catches(q, bad, good, key, factor=3.0, at_least=None):
    a, b = q[good][key], q[bad][key]
    floor = oogq.KEYS[key][1]
    assert b > a + 2 * floor, (key, a, b)
    assert b >= factor * max(a, floor), (key, a, b)
    if at_least is not None:
        assert b >= at_least, (key, b)


def test_f15_out_of_gamut_ramps_reverse_and_images_get_new_contours(q):
    _catches(q, "X3-accurate", "X3-colprof", "oog_ramp_rev_r", at_least=300)
    _catches(q, "X3-accurate", "X3-colprof", "image_contours_r", at_least=300)
    _catches(q, "X3-accurate", "X3-colprof", "oog_ramp_jump_r")
    _catches(q, "X1-accurate", "X1-colprof", "oog_ramp_rev_r", at_least=50)


def test_f15_pale_out_of_gamut_content_prints_dark(q):
    _catches(q, "X3-accurate", "X3-colprof", "pale_oog_dL_max_r", at_least=25)
    _catches(q, "X1-accurate", "X1-colprof", "pale_oog_dL_max_r", at_least=10)
    assert q["X3-accurate"]["pale_oog_share5_r"] > 0.05 > q["X3-colprof"]["pale_oog_share5_r"]


def test_f15_absolute_white_is_tinted(q):
    _catches(q, "X1-accurate", "X1-colprof", "abs_white_de", at_least=1.5)


def test_f17_blue_prints_purple_in_ipt(q):
    _catches(q, "X3-accurate", "X3-colprof", "blue_ipt_abs_r", at_least=12)
    _catches(q, "X1-accurate", "X1-colprof", "blue_ipt_abs_r", at_least=10)
    _catches(q, "X3-accurate", "X3-colprof", "oog_blue_ipt_abs_r", factor=3.0)


def test_f16_perceptual_and_saturation_colour_ramps_reverse(q):
    _catches(q, "X3-accurate", "X3-colprof", "ramp_rev_s", at_least=15)
    _catches(q, "X3-accurate", "X3-colprof", "dark_ramp_rev_ps", at_least=15)
    _catches(q, "X1-accurate", "X1-colprof", "red_ramp_rev_ps", at_least=10)
    # gmq M3 sees it too, now that it runs
    assert q["X3-accurate"]["gmq_p_M3_L_reversals"] > q["X3-colprof"]["gmq_p_M3_L_reversals"]


def test_f18_mid_grey_band_through_perceptual_and_saturation(q):
    _catches(q, "X3-accurate", "X3-colprof", "grey_swing_p", at_least=3.0)
    _catches(q, "X3-accurate", "X3-colprof", "grey_swing_s", at_least=3.0)
    _catches(q, "X3-accurate", "X3-colprof", "grey_chroma_max_p", factor=2.0)
    # the relative intent of the same profile is clean (the defect is p/s only)
    assert q["X3-accurate"]["grey_swing_r"] <= 0.1


def test_f13_rgb_reverses_below_the_device_black(q):
    _catches(q, "X1-accurate", "X1-colprof", "below_black_swing_r", at_least=1.0)
    _catches(q, "X1-accurate", "X1-colprof", "grey_swing_r", at_least=1.0)


# ---------------------------------------------------------------------------
# 5-7 inks (research-folder profiles)
# ---------------------------------------------------------------------------

@needs_ws
def test_f19_seven_ink_perceptual_shadows_reverse(printers):
    r = oogq.evaluate(WORKSPACE / "X7-accurate.icc", printers["X7"], with_gmq=False)
    assert r["q"]["grey_shadow_swing_p"] >= 3.0
    assert r["q"]["grey_shadow_swing_s"] >= 3.0
    # X5 (6 inks) is clean there: the row tells them apart
    r5 = oogq.evaluate(WORKSPACE / "X5-accurate.icc", printers["X5"], with_gmq=False)
    assert r5["q"]["grey_shadow_swing_p"] < 1.0


@needs_ws
def test_f20_fogra55_perceptual_black_prints_light_orange():
    from benchmarks.research import metrics as M
    tr = M.Truth(proxy_icc=WORKSPACE / "R-FOGRA55-ref.icc", proxy_reader="lcms")
    ad = oogq.TruthAdapter(tr, 7, False, 300.0, list("CMYKOGV"), "R-FOGRA55")
    r = oogq.evaluate(WORKSPACE / "R-FOGRA55-accurate.icc", ad, with_gmq=False)
    assert r["q"]["black_gap_p"] > 50 and r["q"]["black_C_p"] > 30
    assert r["q"]["black_gap_s"] > 50
    # the set's own commercial profile, read the same way, is clean
    ref = oogq.evaluate(WORKSPACE / "R-FOGRA55-ref.icc", ad, with_gmq=False)
    assert ref["q"]["black_gap_p"] < 3 and ref["q"]["black_C_p"] < 3


@needs_ws
def test_f05_multi_ink_perceptual_neutrals_carry_a_cast(printers):
    """S5 on the ECG chart (integration 2; Agent 21's A arm, byte-identical to
    the tag): the perceptual black sits 13 L* above the colorimetric one with
    C* 17; the targen-chart build of the same printer does not show it."""
    r = oogq.evaluate(WORKSPACE / "S5-ecg900-accurate.icc", printers["S5"])
    assert r["q"]["black_C_p"] > 10 and r["q"]["black_gap_p"] > 8
    assert r["q"]["gmq_p_M8_black_gap"] > 8 and r["q"]["gmq_p_M11_rt_median"] > 8
    ok = oogq.evaluate(WORKSPACE / "S5-accurate.icc", printers["S5"], with_gmq=False)
    assert ok["q"]["black_C_p"] < 2 and ok["q"]["black_gap_p"] < 3


@needs_ws
def test_f14_pale_in_gamut_colours_print_dark_and_the_fix_shows(printers):
    from types import SimpleNamespace
    p = printers["X5"]
    ds = SimpleNamespace(kind="synthetic", n_channels=p.n, color_rep="CMYKOG_XYZ",
                         ink_limit=p.tac, printer=p)
    tr = metrics.Truth(printer=p)
    bad, good = {}, {}
    metrics.score(WORKSPACE / "X5-accurate.icc", ds, "lcms", tr, n_eval=2000, light=True,
                  sink=bad)
    metrics.score(WORKSPACE / "X5-a21light.icc", ds, "lcms", tr, n_eval=2000, light=True,
                  sink=good)
    assert np.percentile(bad["pale_dl"], 95) > 2 * np.percentile(good["pale_dl"], 95)
    assert np.percentile(bad["pale_dl"], 95) > 5.0
    # and through perceptual (oogq pale row)
    rb = oogq.evaluate(WORKSPACE / "X5-accurate.icc", p, with_gmq=False)
    rg = oogq.evaluate(WORKSPACE / "X5-a21light.icc", p, with_gmq=False)
    assert rb["q"]["pale_oog_dL_max_p"] > 2 * rg["q"]["pale_oog_dL_max_p"]


@needs_ws
def test_ncq_runs_on_a_real_seven_ink_set_through_its_proxy():
    tr = metrics.Truth(proxy_icc=WORKSPACE / "R-FOGRA55-ref.icc", proxy_reader="lcms")
    ad = oogq.TruthAdapter(tr, 7, False, 300.0, list("CMYKOGV"), "R-FOGRA55")
    from benchmarks.research import ncpoints
    h = ncpoints.referee(WORKSPACE / "R-FOGRA55-accurate.icc", ad, "argyll")
    assert "NC5 visible jumps" in h and "NC3 grey extra ink max" in h


# ---------------------------------------------------------------------------
# statistics: property rows, seed SD, D-17 safety
# ---------------------------------------------------------------------------

def _results(qa: dict, qb: dict, variant="typical-targen900", name="X3"):
    def ds(q, eng):
        return {"name": name, "variant": variant, "role": "development", "kind": "synthetic",
                "n_channels": 4, "color_rep": "CMYK_XYZ", "info": {},
                "profiles": {eng: {"ok": True, "oogq": {"q": q}}}}
    return {"datasets": [ds(qa, "colprof")]}, {"datasets": [ds(qb, "accurate")]}


def test_property_rows_sign_and_minimum_effect():
    ra, rb = _results({"grey_swing_p": 0.0, "gmq_p_M7_core_p05": 0.70},
                      {"grey_swing_p": 3.9, "gmq_p_M7_core_p05": 0.60})
    rows = stats3.property_rows(ra, rb, "colprof", "accurate")
    table = {"colprof|typical|CMYK|q.grey_swing_p": 0.2, "accurate|typical|CMYK|q.grey_swing_p": 0.5}
    stats3.decide_properties(rows, "colprof", "accurate", table)
    by = {r["endpoint"]: r for r in rows}
    g = by["q.grey_swing_p"]
    assert g["min_effect"] == pytest.approx(1.0)          # 2 x the larger SD
    assert g["verdict"] == "WORSE*" and g["safety"]
    m7 = by["q.gmq_p_M7_core_p05"]                       # larger is better: a drop is a loss
    assert m7["diff"] == pytest.approx(0.10)
    assert m7["seed_sd_source"].startswith("unmeasured")


def test_a_property_loss_inside_the_seed_noise_is_a_tie():
    ra, rb = _results({"oog_ramp_rev_r": 14.0}, {"oog_ramp_rev_r": 18.0})
    rows = stats3.decide_properties(stats3.property_rows(ra, rb, "colprof", "accurate"),
                                    "colprof", "accurate",
                                    {"colprof|typical|CMYK|q.oog_ramp_rev_r": 3.0})
    assert rows[0]["verdict"] == "TIE"


def test_a_safety_property_loss_blocks_d17_and_strict_no_regression():
    ra, rb = _results({"grey_swing_p": 0.0, "oog_ramp_rev_r": 14.0},
                      {"grey_swing_p": 3.9, "oog_ramp_rev_r": 5.0})
    rows = stats3.decide_properties(stats3.property_rows(ra, rb, "colprof", "accurate"),
                                    "colprof", "accurate", None)
    w = stats3.weighed_adoption(rows, [], [])
    assert not w["pass"] and any(x["safety"] for x in w["all_losses"])
    nr = stats3.no_regression(rows, [])
    assert not nr["pass"]
    assert stats3.property_safety(rows)[0]["check"].startswith("q.grey_swing_p")


def test_a_single_build_property_win_does_not_count_until_seeds_confirm_it():
    ra, rb = _results({"oog_ramp_rev_r": 400.0}, {"oog_ramp_rev_r": 5.0})
    rows = stats3.decide_properties(stats3.property_rows(ra, rb, "colprof", "accurate"),
                                    "colprof", "accurate", None)
    assert rows[0]["verdict"] == "BETTER*"
    assert stats3.weighed_adoption(rows, [], [])["wins"] == 0


def test_property_seed_verdicts_confirm_over_ten_seeds():
    rows = []
    for k in range(10):
        ra, rb = _results({"grey_swing_p": 0.0}, {"grey_swing_p": 3.0 + 0.1 * k},
                          variant=f"seed{k}-typical-targen900")
        rows += stats3.property_rows(ra, rb, "colprof", "accurate")
    stats3.decide_properties(rows, "colprof", "accurate", None)
    sv = stats3.property_seed_verdicts(rows)
    assert len(sv) == 1 and sv[0]["seeds"] == 10 and sv[0]["verdict"] == "WORSE"


def test_seedspread_pools_the_property_rows():
    from benchmarks.research import seedspread3
    res = {"datasets": []}
    for k, v in enumerate((1.0, 2.0, 3.0)):
        res["datasets"].append({"name": "X3", "variant": f"seed{k}-typical-targen900",
                                "n_channels": 4, "color_rep": "CMYK_XYZ",
                                "profiles": {"accurate": {"oogq": {"q": {"grey_swing_p": v}}}}})
    table, _ = seedspread3.spread(res)
    assert table["accurate|typical|CMYK|q.grey_swing_p"] == pytest.approx(1.0)


def test_pale_lightness_is_an_endpoint_of_its_own():
    assert ("pale_dl", "mean") in stats3.ENDPOINTS and ("pale_dl", "p95") in stats3.ENDPOINTS


# ---------------------------------------------------------------------------
# datasets and the sealed slots
# ---------------------------------------------------------------------------

def test_fogra55_and_aptec_are_scored_and_join_the_final_multi_ink_run():
    from benchmarks.research import run
    assert not set(run.V3_REAL_SKIP) & {"R-FOGRA55", "R-APTEC7C"}
    assert set(run.V31_MULTI_REAL) == {"R-FOGRA55", "R-APTEC7C"}
    src = (HERE.parent / "benchmarks/research/run.py").read_text(encoding="utf-8")
    sealed_branch = src.split('elif suite == "sealed":', 1)[1].split("elif suite", 1)[0]
    assert "V31_MULTI_REAL" in sealed_branch and '"role": "development"' in sealed_branch


def test_the_referee_runs_on_a_sealed_slot_printer_through_the_generator_interface(tmp_path):
    """Public preview seed only (the same code path as the sealed draw): a Z
    printer object is all the referee needs; no sealed instance is read."""
    from benchmarks.research import gmq, run, sealed, zfamily as Z
    seed = b"public-preview-3"
    slot = next(s for s in sealed.SLOTS if s["device_rep"].startswith("CMYK") and
                len(s["device_rep"].split("_")[0]) == 4)
    p = Z.ZTruth(sealed.draw_slot(seed, slot))
    from types import SimpleNamespace
    ds = SimpleNamespace(kind="synthetic", printer=p)
    assert run.oogq_printer(ds, None) is p
    for attr in ("n", "is_additive", "tac", "letters", "lab_rel"):
        assert hasattr(p, attr), attr
    cloud = gmq.truth_cloud(p, n=3000)
    assert cloud.shape == (3000, 3)


def test_the_sealed_generator_files_are_untouched_by_v31():
    from benchmarks.research import sealed
    man = json.loads((HERE.parent / "benchmarks/research/data/sealed_manifest.json")
                     .read_text(encoding="utf-8"))
    now = sealed.generator_hashes()
    changed = {k for k in now if man["generator_sha256"].get(k) != now[k]}
    # documented: encoding= only (Integrator 4) and datasets.py's SWOP 2006
    # source entries (Agent 16, three minutes after sealing; no generation code)
    assert changed <= {"sealed.py", "charts.py", "datasets.py"}, changed
    for f in ("zfamily.py", "noise.py", "colour.py", "printers.py"):
        assert f not in changed

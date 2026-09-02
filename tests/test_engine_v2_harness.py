"""W0 harness tests (issue #123): synthetic battery, ICC reader, gates."""
import json
from pathlib import Path

import numpy as np
import pytest

from benchmarks.battery import evaluate_gates, score_profile
from benchmarks.iccread import IccProfile, _parse_mft2
from benchmarks.synthetic import (PRINTERS, SyntheticPrinter, eval_points,
                                  halton, make_chart, measure, write_ti3)
from workflow.profile_engine import icc_writer as icw
from workflow.profile_engine.builder import (BuildSettings,
                                             ENGINE_CANDIDATE_TOKENS,
                                             build_profile,
                                             candidates_from_env)
from workflow.profile_engine.metrics import delta_e_2000
from workflow.profile_engine.ti3_data import read_ti3


# ---------------------------------------------------------------------------
# Synthetic printers
# ---------------------------------------------------------------------------

def test_printer_characters():
    s1, s2, s3 = PRINTERS["S1"], PRINTERS["S2"], PRINTERS["S3"]
    for p in (s1, s2, s3):
        w = p.lab_relative_true(np.full((1, p.n_channels),
                                        1.0 if p.is_additive else 0.0))
        assert w[0, 0] == pytest.approx(100.0, abs=1e-6)   # media-relative
    blk2 = s2.lab_relative_true(np.zeros((1, 3)))[0, 0]
    assert 15.0 < blk2 < 22.0            # matte: compressed shadows
    k = np.zeros((1, 4)); k[0, 3] = 1.0
    # Halftone K-only solid on glossy sits near L* 20–25 (real inkjet
    # behaviour); the deep black comes from K+CMY under the TAC.
    assert s3.lab_relative_true(k)[0, 0] < 26.0

    # S6's violet solid must sit clearly OFF the 300° anchor hue.
    s6 = PRINTERS["S6"]
    v = np.zeros((1, 5)); v[0, 4] = 1.0
    lab = s6.lab_relative_true(v)[0]
    hue = np.degrees(np.arctan2(lab[2], lab[1])) % 360.0
    assert 10.0 < abs(hue - 300.0) < 60.0


def test_ground_truth_is_smooth_and_monotone():
    p = PRINTERS["S3"]
    ramp = np.zeros((21, 4)); ramp[:, 3] = np.linspace(0, 1, 21)
    l_star = p.lab_relative_true(ramp)[:, 0]
    assert (np.diff(l_star) < 0).all()   # more K = darker, strictly


def test_ti3_roundtrip_with_spectra(tmp_path):
    p = PRINTERS["S5"]
    chart = make_chart(p, 300)
    xyz, refl, _ = measure(p, chart)
    f = write_ti3(tmp_path / "s5.ti3", p, chart, xyz, refl)
    m = read_ti3(f)
    assert m.device_rep == "CMYKOG"
    assert np.abs(m.device - chart).max() < 1e-5
    assert m.spectral is not None and m.spectral.shape[1] == 36
    assert m.ink_limit == pytest.approx(320.0)
    assert m.extra_ink_hues()          # solids present in the chart


def test_noise_model_heteroscedastic_and_misreads():
    p = PRINTERS["S4"]
    chart = make_chart(p, 600)
    xyz, _, misread = measure(p, chart, seed=5)
    true = p.xyz_true(chart)
    err = np.abs(xyz - true).mean(1)
    dark = true[:, 1] < 5.0
    light = true[:, 1] > 60.0
    clean = np.ones(len(chart), bool); clean[misread] = True
    clean = ~np.isin(np.arange(len(chart)), misread)
    assert err[dark & clean].mean() > err[light & clean].mean()
    assert len(misread) > 0
    assert (misread >= 8).all()          # endpoint duplicates protected
    from workflow.profile_engine.ti3_data import xyz_to_lab
    de = delta_e_2000(xyz_to_lab(xyz[misread]), xyz_to_lab(true[misread]))
    assert de.min() > 2.0                # smudges are visibly wrong


def test_halton_deterministic_unit_cube():
    a = halton(500, 4, seed=1)
    b = halton(500, 4, seed=1)
    assert np.array_equal(a, b)
    assert a.min() >= 0.0 and a.max() < 1.0
    # low-discrepancy-ish: every axis covers its range densely
    for d in range(4):
        hist, _ = np.histogram(a[:, d], bins=10, range=(0, 1))
        assert hist.min() > 20


def test_eval_points_respect_tac():
    p = PRINTERS["S5"]
    pts = eval_points(p, 2000)
    assert pts.sum(1).max() <= p.tac / 100.0 + 1e-9


# ---------------------------------------------------------------------------
# mft2 reader
# ---------------------------------------------------------------------------

def test_mft2_parse_roundtrip():
    rng = np.random.default_rng(3)
    grid = 5
    clut = rng.uniform(0, 1, (grid ** 3, 4))
    in_t = np.tile(icw._identity_table(64), (3, 1))
    out_t = np.tile(icw._identity_table(128), (4, 1))
    blob = icw.make_mft2(3, 4, grid, (clut * 0xFFFF).round().astype(">u2"),
                         in_tables=in_t, out_tables=out_t)
    lut = _parse_mft2(blob)
    assert (lut.n_in, lut.n_out, lut.grid) == (3, 4, 5)
    # Node-exact: querying grid coordinates returns the CLUT rows.
    ax = np.linspace(0, 1, grid)
    q = np.stack(np.meshgrid(ax, ax, ax, indexing="ij"), -1).reshape(-1, 3)
    got = lut.apply(q)
    assert np.abs(got - clut).max() < 2e-4     # u16 quantisation


def test_icc_profile_reader_matches_model(tmp_path):
    p = PRINTERS["S1"]
    chart = make_chart(p, 400)
    xyz, refl, _ = measure(p, chart)
    ti3 = write_ti3(tmp_path / "c.ti3", p, chart, xyz, refl)
    icc = tmp_path / "c.icc"
    res = build_profile(ti3, icc, BuildSettings(quality="l",
                                                gammap_mode="accurate"))
    prof = IccProfile(icc)
    dev = halton(500, 3, seed=9)
    de = delta_e_2000(prof.a2b_lab(dev), res.model.predict(dev))
    assert float(np.median(de)) < 0.15         # table quantisation only
    # B2A direction runs and returns device values in range.
    d = prof.b2a_device(np.array([[50.0, 10.0, -20.0]]))
    assert d.shape == (1, 3) and (d >= 0).all() and (d <= 1).all()


# ---------------------------------------------------------------------------
# Candidate plumbing + outlier reporting
# ---------------------------------------------------------------------------

def test_candidates_from_env():
    assert candidates_from_env(None) == frozenset()
    assert candidates_from_env("") == frozenset()
    assert candidates_from_env("ucs") == {"ucs"}
    assert candidates_from_env("ucs, joint-sep") == {"ucs", "joint-sep"}
    assert candidates_from_env("bogus,ucs") == {"ucs"}
    assert candidates_from_env("bogus") == frozenset()
    assert candidates_from_env("ucs") <= ENGINE_CANDIDATE_TOKENS


def test_build_reports_outlier_rows(tmp_path):
    p = PRINTERS["S1"]
    chart = make_chart(p, 400)
    xyz = p.xyz_true(chart)
    xyz[150] = xyz[150] * 0.3 + 30.0           # one gross smudge
    ti3 = write_ti3(tmp_path / "o.ti3", p, chart, xyz)
    res = build_profile(ti3, tmp_path / "o.icc",
                        BuildSettings(quality="l", gammap_mode="accurate"))
    assert 150 in res.outlier_rows


def test_empty_candidates_default():
    assert BuildSettings().engine_candidates == frozenset()


# ---------------------------------------------------------------------------
# Promotion gates
# ---------------------------------------------------------------------------

def _fake(med_a2b, med_b2a, *, p95_scale=2.0, mx=3.0, ktv=0.1, f1=0.8,
          ff=0, secs=30.0):
    row = {
        "a2b": {"median": med_a2b, "p95": med_a2b * p95_scale,
                "p99": med_a2b * 3, "max": mx},
        "b2a": {"median": med_b2a, "p95": med_b2a * p95_scale,
                "p99": med_b2a * 3, "max": mx},
        "roundtrip": {"median": 0.1, "p95": 0.3, "p99": 0.5, "max": mx},
        "k_tv_excess": ktv, "k_tv": 1.0 + ktv, "k_max_step": 0.2,
        "build_seconds": secs,
        "outliers": {"flagged": [], "true": [], "precision": 1.0,
                     "recall": 1.0, "false_flags": ff, "f1": f1},
    }
    return row


def test_gates_promote_clear_win():
    base = {"printers": {"S3": _fake(0.40, 0.50), "S4": _fake(0.45, 0.55)}}
    cand = {"printers": {"S3": _fake(0.30, 0.40), "S4": _fake(0.35, 0.45)}}
    v = evaluate_gates(base, cand)
    assert v["promote"] and v["improvement"] > 0.15


def test_gates_block_class_regression():
    base = {"printers": {"S3": _fake(0.40, 0.50), "S4": _fake(0.45, 0.55)}}
    cand = {"printers": {"S3": _fake(0.20, 0.25),
                         "S4": _fake(0.50, 0.60)}}    # S4 regresses > 2%
    v = evaluate_gates(base, cand)
    assert not v["promote"]
    assert any("REGRESS S4" in d for d in v["detail"])


def test_gates_block_small_improvement():
    base = {"printers": {"S3": _fake(0.40, 0.50)}}
    cand = {"printers": {"S3": _fake(0.395, 0.495)}}   # ~1 %
    assert not evaluate_gates(base, cand)["promote"]


def test_gates_block_slow_build():
    base = {"printers": {"S3": _fake(0.40, 0.50, secs=30.0)}}
    cand = {"printers": {"S3": _fake(0.30, 0.38, secs=200.0)}}
    v = evaluate_gates(base, cand)
    assert not v["promote"]
    assert any("build time" in d for d in v["detail"])


def test_gates_serialisable(tmp_path):
    base = {"printers": {"S3": _fake(0.4, 0.5)}}
    f = tmp_path / "b.json"
    f.write_text(json.dumps(base), encoding="utf-8")
    assert json.loads(f.read_text(encoding="utf-8")) == base

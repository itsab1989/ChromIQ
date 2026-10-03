"""The research benchmark v2 (Agent 6, 2026-10-03): one regression test per
flaw that the adversarial review (agent 7) and the spectral agent (agent 4)
found in v1. Each test fails on the v1 code.

1. S4 was bit-identical to S3 (noise.measure ignored the printer's settings).
2. The CanonSG held-out set leaked 17 % through exact device duplicates.
3. The re-read noise was calibrated on one pair; no strip misreads.
4. The ColorSync column read every colour 0.5 low in a* and b*.
5. The i1Profiler data path pointed at a folder that no longer exists.
6. The spectra carried less noise than the XYZ (and no misreads).
7. The per-CMM kernel claims were not measured.
8. Development vs confirmatory sets were not separated.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from benchmarks.research import colour, noise
from benchmarks.research.printers import build_printers

ARGYLL = Path("/Applications/Argyll/bin/icclu")


@pytest.fixture(scope="module")
def printers():
    return build_printers()


@pytest.fixture(scope="module")
def s3_chart(printers):
    from benchmarks.research.datasets import make_chart
    return make_chart(printers["S3"], 900, 11)


# --- 1 ------------------------------------------------------------------------
def test_s4_is_measured_with_its_own_noise_scale_not_as_s3(printers, s3_chart):
    x0 = noise.measure(printers["S3"], s3_chart, level="none")[0]
    a, _, ma = noise.measure(printers["S3"], s3_chart, level="typical", seed=23)
    b, _, mb = noise.measure(printers["S4"], s3_chart, level="typical", seed=23)
    assert not np.array_equal(a, b)
    ok = np.ones(len(a), bool)
    ok[np.union1d(ma, mb)] = False
    ratio = (b - x0)[ok].std(0) / (a - x0)[ok].std(0)
    assert printers["S4"].noise_scale == 3.0
    np.testing.assert_allclose(ratio, 3.0, rtol=0.03)


def test_measure_honours_the_printers_misread_rate(printers, s3_chart):
    class Clean:
        noise_scale, misread_prob = 1.0, 0.0
        reflectance = staticmethod(printers["S3"].reflectance)

    class Bad(Clean):
        misread_prob = 0.05

    assert len(noise.measure(Clean(), s3_chart, level="typical")[2]) == 0
    n_bad = len(noise.measure(Bad(), s3_chart, level="typical")[2])
    assert 25 <= n_bad <= 70          # 5 % of 892 eligible rows = 45


# --- 3 ------------------------------------------------------------------------
def test_benchmarks_run_at_a_typical_and_a_pessimistic_level(printers, s3_chart):
    assert noise.BENCH_LEVELS == ("typical", "pessimistic")
    for pid in ("S3", "X3"):
        p = printers[pid]
        x0 = noise.measure(p, s3_chart, level="none")[0]
        meds = {}
        for lvl in noise.BENCH_LEVELS:
            x, _, mis = noise.measure(p, s3_chart, level=lvl, seed=23)
            ok = np.ones(len(x), bool)
            ok[mis] = False
            meds[lvl] = np.median(colour.de2000(colour.xyz_to_lab(x[ok]),
                                                colour.xyz_to_lab(x0[ok])))
        assert meds["pessimistic"] > 1.2 * meds["typical"], (pid, meds)


def test_the_pessimistic_level_has_whole_strip_misreads(printers, s3_chart):
    det: dict = {}
    x, _, mis = noise.measure(printers["X3"], s3_chart, level="pessimistic",
                              seed=23, detail=det)
    assert det["strips"], "no strip misread on a 900-patch chart at 2.8 %/strip"
    for rows in det["strips"]:
        assert len(rows) == noise.STRIP["len"] and min(rows) >= 8
        assert np.all(np.diff(rows) == 1)
        assert set(rows) <= set(mis.tolist())
    det2: dict = {}
    noise.measure(printers["X3"], s3_chart, level="typical", seed=23, detail=det2)
    assert det2["strips"] == []


def test_a_strip_misread_reports_the_neighbours_readings(printers, s3_chart):
    det: dict = {}
    clean = noise.measure(printers["X3"], s3_chart, level="none")[0]
    x, _, _ = noise.measure(printers["X3"], s3_chart, level="pessimistic",
                            seed=23, detail=det, misread_prob=0.0)
    rows = np.array(det["strips"][0])
    shifted = colour.de2000(colour.xyz_to_lab(x[rows]),
                            colour.xyz_to_lab(clean[np.roll(rows, -1)]))
    assert np.median(shifted) < 1.0


# --- 6 ------------------------------------------------------------------------
def _xyz_from_spec(spec):
    r1 = np.stack([np.interp(colour.LAM_1NM, noise.LAM_10, s) for s in spec])
    return colour.xyz_from_reflectance_1nm(r1, "D50")


@pytest.mark.parametrize("level", ["battery", "reread", "typical", "pessimistic"])
def test_spectra_and_xyz_carry_the_same_noise(printers, s3_chart, level):
    p = printers["X3"]
    x0, s0, _ = noise.measure(p, s3_chart, level="none")
    x, s, mis = noise.measure(p, s3_chart, level=level, seed=23)
    dx = x - x0
    ds = _xyz_from_spec(s) - _xyz_from_spec(s0)
    ok = np.ones(len(x), bool)
    ok[mis] = False
    np.testing.assert_allclose(ds[ok].std(0) / dx[ok].std(0), 1.0, atol=0.03)
    assert np.corrcoef(dx[ok, 1], ds[ok, 1])[0, 1] > 0.99
    if len(mis):                      # misreads show in the spectra too
        de_s = colour.de2000(colour.xyz_to_lab(_xyz_from_spec(s)[mis]),
                             colour.xyz_to_lab(_xyz_from_spec(s0)[mis]))
        assert np.median(de_s) > 4.0


def test_the_spectral_noise_basis_maps_onto_xyz_exactly():
    b = noise.xyz_dual_basis("D50")
    np.testing.assert_allclose(b @ colour.weights("D50").T, np.eye(3), atol=1e-9)


# --- 2 ------------------------------------------------------------------------
def _write_ti3(path, dev, xyz):
    lines = ["CTI3", 'COLOR_REP "iRGB_XYZ"', "NUMBER_OF_FIELDS 7",
             "BEGIN_DATA_FORMAT", "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(dev)}", "BEGIN_DATA"]
    for i, (d, x) in enumerate(zip(dev, xyz)):
        lines.append(" ".join([str(i + 1)] + [f"{v * 100:.4f}" for v in d]
                              + [f"{v:.4f}" for v in x]))
    lines.append("END_DATA")
    Path(path).write_text("\n".join(lines) + "\n")


def test_a_held_out_patch_never_has_a_duplicate_in_training(tmp_path, printers):
    from benchmarks.research import datasets as dsm
    rng = np.random.default_rng(2)
    dev = rng.uniform(0, 1, (300, 3)).round(3)
    dev[0] = 1.0                                 # paper white
    dev = np.vstack([dev, dev[1:121]])           # 120 exact duplicates (40 %)
    xyz = printers["X1"].xyz(dev)
    src = tmp_path / "dups.ti3"
    _write_ti3(src, dev, xyz)
    d = dsm.real_split("dups", src, tmp_path)
    assert d.info["holdout_leak"] == 0
    assert d.info["duplicate_groups"] == 120
    import re
    body = d.ti3.read_text().split("BEGIN_DATA\n")[1].split("\nEND_DATA")[0]
    train = np.array([[float(v) for v in ln.split()[1:4]] for ln in body.splitlines()]) / 100
    assert dsm.holdout_leak(train, d.holdout_device) == 0
    assert len(train) + d.info["held_out_rows"] == len(dev)
    n_sets = int(re.search(r"NUMBER_OF_SETS (\d+)", d.ti3.read_text()).group(1))
    assert n_sets == len(train)


def _available_real_sets():
    from benchmarks.research import datasets as dsm
    return [n for n in dsm.REAL_SOURCES if dsm.real_source(n)[0].exists()]


@pytest.mark.parametrize("name", _available_real_sets() or ["(none on this machine)"])
def test_every_real_held_out_set_is_leak_free(tmp_path, name):
    from benchmarks.research import datasets as dsm
    if name not in dsm.REAL_SOURCES:
        pytest.skip("no real data on this machine")
    d = dsm.real(name, tmp_path)
    assert d.info["holdout_leak"] == 0
    assert d.info["held_out"] >= 20


# --- 5 ------------------------------------------------------------------------
def test_the_i1profiler_data_root_is_configurable(monkeypatch, tmp_path):
    from benchmarks.research import datasets as dsm
    monkeypatch.delenv(dsm.XRITE_ENV, raising=False)
    assert dsm.xrite_root() == Path.home() / "develop" / "i1Profiler"
    monkeypatch.setenv(dsm.XRITE_ENV, str(tmp_path))
    assert dsm.xrite_root() == tmp_path
    assert dsm.real_source("R-FOGRA39L")[0].is_relative_to(tmp_path)
    with pytest.raises(FileNotFoundError, match=dsm.XRITE_ENV):
        dsm.real("R-FOGRA39L", tmp_path / "w")


# --- 4 ------------------------------------------------------------------------
SRGB = Path("/System/Library/ColorSync/Profiles/sRGB Profile.icc")


@pytest.mark.skipif(not SRGB.exists(), reason="macOS ColorSync only")
def test_the_colorsync_column_reads_white_as_neutral():
    pytest.importorskip("Quartz")
    from benchmarks.research import cmm
    assert cmm.QUARTZ_LAB_RANGE == [-127.5, 127.5, -127.5, 127.5]
    lab = cmm._colorsync(SRGB, np.array([[1.0, 1.0, 1.0], [0.5, 0.5, 0.5]]), True)
    np.testing.assert_allclose(lab[:, 1:], 0.0, atol=0.01)
    v1 = cmm._colorsync(SRGB, np.array([[1.0, 1.0, 1.0]]), True,
                        lab_range=cmm.QUARTZ_LAB_RANGE_V1)
    np.testing.assert_allclose(v1[0, 1:], -0.5, atol=0.01)    # the v1 artefact


# --- 7 ------------------------------------------------------------------------
def _random_profile(tmp_path, n, rep, sig=None):
    from workflow.profile_engine import icc_writer as icw
    rng = np.random.default_rng(n)
    grid = 5 if n <= 6 else 4
    lab = np.column_stack([rng.uniform(5, 95, grid ** n), rng.uniform(-50, 50, grid ** n),
                           rng.uniform(-50, 50, grid ** n)])
    a2b = icw.make_mft2(n, 3, grid, icw.lab_to_u16(lab))
    b2a = icw.make_mft2(3, n, 9, icw.device_to_u16(rng.uniform(0, 1, (9 ** 3, n))))
    spec = icw.ProfileSpec(n_channels=n, description="kernel probe", color_rep=rep)
    p = icw.write_profile(tmp_path / f"{rep}-{sig}.icc", spec,
                          {"A2B0": a2b, "A2B1": "A2B0", "A2B2": "A2B0",
                           "B2A0": b2a, "B2A1": "B2A0", "B2A2": "B2A0"})
    if sig:
        b = bytearray(Path(p).read_bytes())
        b[16:20] = sig
        Path(p).write_bytes(bytes(b))
    return p


@pytest.mark.skipif(not ARGYLL.exists(), reason="ArgyllCMS not installed")
@pytest.mark.parametrize("n, rep", [(3, "RGB"), (4, "CMYK"), (6, "CMYKOG"), (7, "CMYKRGB")])
@pytest.mark.parametrize("reader", ["argyll", "lcms"])
def test_each_cmm_column_reads_with_the_kernel_the_readme_states(tmp_path, n, rep, reader):
    from benchmarks.research import cmm, kernels
    p = _random_profile(tmp_path, n, rep)
    for direction in ("a2b", "b2a"):
        r = kernels.identify(p, reader, direction, n=150)
        assert r["best"] == cmm.kernel_of(reader, n, direction), r
        assert r["max_diff"][r["best"]] < 0.05, r


@pytest.mark.skipif(not ARGYLL.exists(), reason="ArgyllCMS not installed")
def test_argyll_reads_a_6_ink_table_by_its_signature(tmp_path):
    """Agent 7 T6: nCLR -> N-linear, MCH6 -> simplex (icc_xf.c:1373)."""
    from benchmarks.research import kernels
    assert kernels.identify(_random_profile(tmp_path, 6, "CMYKOG"), "argyll", n=100)["best"] \
        == "multilinear"
    assert kernels.identify(_random_profile(tmp_path, 6, "CMYKOG", b"MCH6"), "argyll",
                            n=100)["best"] == "simplex"


# --- 8 ------------------------------------------------------------------------
def test_the_s_family_is_development_and_the_x_family_confirmatory():
    from benchmarks.research import datasets as dsm
    for pid in ("S1", "S2", "S3", "S4", "S5", "S6", "S7"):
        assert dsm.role_of(pid) == "development"
    for pid in ("X1", "X3", "X3m", "X5", "X6", "X7", "X8", "R-FOGRA39L",
                "R-CMYK-default-i1Pro", "R-Knut-printer"):
        assert dsm.role_of(pid) == "confirmatory"
    for pid in ("R-Pro300-CanonSG", "R-Pro300-EpsonPremSG"):
        assert dsm.role_of(pid) == "development"

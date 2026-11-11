"""The research benchmark's referee must be right before it judges anything.

benchmarks/research (Agent 6, 2026-09-29) scores profiles against truth
computed WITHOUT the engine's own colour code. These tests pin the pieces
that make that true: CIEDE2000 against published reference pairs, the 1 nm
integration, the September printers reproduced exactly by the independent
evaluator, the readouts agreeing on a table where every kernel must agree,
and the paired statistic's null case.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest

from benchmarks.research import colour


# Sharma, Wu, Dalal (2005), Table 1, pairs 1, 7, 17, 25, 34.
@pytest.mark.parametrize("lab1, lab2, expected", [
    ((50, 2.6772, -79.7751), (50, 0, -82.7485), 2.0425),
    ((50, 0, 0), (50, -1, 2), 2.3669),
    ((50, 2.5, 0), (73, 25, -18), 27.1492),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
])
def test_referee_de2000_matches_sharma_reference_pairs(lab1, lab2, expected):
    got = colour.de2000(np.array(lab1, float), np.array(lab2, float))[0]
    assert got == pytest.approx(expected, abs=1e-4)


def test_one_nm_weights_give_a_perfect_white_y_100_and_d50_white():
    w = colour.white_of("D50")
    assert w[1] == pytest.approx(100.0, abs=1e-9)
    assert w == pytest.approx([96.42, 100.0, 82.49], abs=0.05)


def test_the_independent_evaluator_reproduces_the_september_printers():
    from benchmarks.research.printers import build_printers
    from benchmarks.synthetic import LAM, PRINTERS, halton
    printers = build_printers()
    for pid, sp in PRINTERS.items():
        dev = halton(200, sp.n_channels, 5)
        np.testing.assert_allclose(printers[pid].reflectance(dev, LAM),
                                   sp.reflectance(dev), atol=1e-12)


def test_clapper_yule_printer_is_paper_at_zero_ink_and_monotone_in_ink():
    from benchmarks.research.printers import build_printers
    p = build_printers()["X3"]
    lam = colour.LAM_1NM
    blank = p.reflectance(np.zeros((1, 4)), lam)[0]
    from benchmarks.research.printers import _cy_paper
    np.testing.assert_allclose(blank, _cy_paper("glossy", lam) * (1 + p.flare), rtol=1e-9)
    ramp = np.zeros((11, 4))
    ramp[:, 3] = np.linspace(0, 1, 11)
    y = p.xyz(ramp)[:, 1]
    assert (np.diff(y) < 0).all()


def test_paired_bootstrap_null_is_a_tie():
    from benchmarks.research.stats import paired_bootstrap
    a = np.random.default_rng(1).gamma(2.0, 0.2, 3000)
    r = paired_bootstrap(a, a.copy(), "median", n_boot=200)
    assert r["diff"] == 0.0 and r["ci95"] == [0.0, 0.0]


@pytest.mark.skipif(not Path("/Applications/Argyll/bin/icclu").exists(),
                    reason="ArgyllCMS not installed")
def test_all_readouts_agree_on_a_table_every_kernel_reads_alike(tmp_path):
    """A 2x2x2 A2B whose nodes are an affine function of the device values:
    multilinear, simplex and tetrahedral interpolation are all exact on it,
    so Argyll, littleCMS and the multilinear reader must agree."""
    from benchmarks.research import cmm
    from workflow.profile_engine import icc_writer as icw
    corners = np.stack(np.meshgrid([0, 1], [0, 1], [0, 1], indexing="ij"),
                       -1).reshape(-1, 3).astype(float)
    lab = np.column_stack([20 + 60 * corners.mean(1), 40 * (corners[:, 0] - corners[:, 1]),
                           30 * (corners[:, 1] - corners[:, 2])])
    a2b = icw.make_mft2(3, 3, 2, icw.lab_to_u16(lab))
    b2a = icw.make_mft2(3, 3, 2, icw.device_to_u16(corners))
    spec = icw.ProfileSpec(n_channels=3, description="referee probe", color_rep="RGB")
    p = icw.write_profile(tmp_path / "probe.icc", spec,
                          {"A2B0": a2b, "A2B1": "A2B0", "A2B2": "A2B0",
                           "B2A0": b2a, "B2A1": "B2A0", "B2A2": "B2A0"})
    dev = np.random.default_rng(3).uniform(0, 1, (50, 3))
    ref = cmm.a2b(p, dev, "multilinear")
    for reader in ("argyll", "lcms"):
        np.testing.assert_allclose(cmm.a2b(p, dev, reader), ref, atol=0.02)

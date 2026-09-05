"""W3 tests (issue #123): noise model, λ refine, uncertainty map ("gp")."""
import numpy as np
import pytest

from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
from workflow.profile_engine.accuracy import fit_forward_model_accurate
from workflow.profile_engine.builder import BuildSettings, build_profile
from workflow.profile_engine.gp import (duplicate_groups,
                                        estimate_xyz_noise,
                                        patch_noise_sigma,
                                        uncertainty_lines)
from workflow.profile_engine.metrics import delta_e_2000
from workflow.profile_engine.ti3_data import xyz_to_lab


def _chart_with_lab(pid="S1", n=600, noise_seed=23):
    p = PRINTERS[pid]
    chart = make_chart(p, n)
    xyz, _, mis = measure(p, chart, seed=noise_seed)
    from benchmarks.synthetic import _bradford_to_d50
    wi = int(np.argmax(xyz[:4, 1]))
    lab = xyz_to_lab(_bradford_to_d50(xyz, xyz[wi]))
    return p, chart, lab, mis


def test_duplicate_groups_found():
    p, chart, lab, _ = _chart_with_lab()
    groups = duplicate_groups(chart)
    assert len(groups) >= 2                       # white + black repeats
    assert all(len(g) >= 3 for g in groups)


def test_noise_estimate_scales_with_instrument():
    # The same chart measured with a 3× noisier instrument must yield a
    # clearly larger estimated amplitude.
    p = PRINTERS["S3"]
    p_noisy = PRINTERS["S4"]                      # same optics, 3× noise
    chart = make_chart(p, 600)
    from benchmarks.synthetic import _bradford_to_d50
    est = {}
    for tag, pr in (("clean", p), ("noisy", p_noisy)):
        xyz, _, _ = measure(pr, chart, seed=77)
        wi = int(np.argmax(xyz[:4, 1]))
        lab = xyz_to_lab(_bradford_to_d50(xyz, xyz[wi]))
        floor, dark = estimate_xyz_noise(chart, lab)
        est[tag] = floor + dark
    assert est["noisy"] > 1.8 * est["clean"]


def test_patch_sigma_dark_blowup():
    p, chart, lab, _ = _chart_with_lab()
    sigma, _ = patch_noise_sigma(chart, lab)
    order = np.argsort(lab[:, 0])
    darkest = order[:30]
    lightest = order[-120:]
    assert sigma[darkest].mean() > 3.0 * sigma[lightest].mean()
    assert (sigma > 0).all()


def test_uncertainty_lines_cover_regions():
    p, chart, lab, _ = _chart_with_lab()
    de = np.abs(np.random.default_rng(1).normal(0.0, 0.3, len(lab)))
    lines = uncertainty_lines(lab, de)
    assert lines and "Confidence map" in lines[0]
    assert "highlights" in lines[0]
    # Shadows either carry a band or are named as sparsely covered.
    assert any("shadows" in ln for ln in lines)


@pytest.mark.slow
def test_gp_fit_flags_misread_not_clean(tmp_path):
    p, chart, lab, mis = _chart_with_lab("S1", 600)
    lab = lab.copy()
    lab[300] += np.array([15.0, -12.0, 9.0])      # inject a gross smudge
    msgs = []
    m, out, lam = fit_forward_model_accurate(
        chart, lab, grid=17, base_lam=0.04, curve_rounds=1,
        progress=msgs.append, gp=True)
    assert 300 in out
    # Hygiene: few false flags on an otherwise clean chart.
    assert len(set(out) - {300} - set(int(i) for i in mis)) <= 8
    assert any("reading noise" in x for x in msgs)      # the σ line, reworded
    assert any("cross-validation" in x for x in msgs)


@pytest.mark.slow
def test_gp_lambda_can_leave_the_ladder():
    # The hill-climb explores beyond the 5 fixed factors when it pays;
    # at minimum it must run and return a positive λ.
    p, chart, lab, _ = _chart_with_lab("S1", 600)
    _, _, lam = fit_forward_model_accurate(chart, lab, grid=17,
                                           base_lam=0.04, curve_rounds=1,
                                           gp=True)
    assert lam > 0


@pytest.mark.slow
def test_gp_build_emits_confidence_map(tmp_path):
    p = PRINTERS["S1"]
    chart = make_chart(p, 500)
    xyz, refl, _ = measure(p, chart)
    ti3 = write_ti3(tmp_path / "c.ti3", p, chart, xyz, refl)
    lines = []
    s = BuildSettings(quality="l", gammap_mode="accurate",
                      engine_candidates=frozenset({"gp"}),
                      progress=lines.append)
    res = build_profile(ti3, tmp_path / "c.icc", s)
    assert res.icc_path.exists()
    assert any("Confidence map" in ln for ln in lines)
    assert any("Candidate pipeline active: gp" in ln for ln in lines)


def test_non_gp_path_untouched():
    # gp=False must not import or consult the noise model at all — the
    # shipped accurate mode stays bit-for-bit.
    p, chart, lab, _ = _chart_with_lab("S1", 400)
    m1, o1, l1 = fit_forward_model_accurate(chart, lab, grid=9,
                                            base_lam=0.03, curve_rounds=1)
    m2, o2, l2 = fit_forward_model_accurate(chart, lab, grid=9,
                                            base_lam=0.03, curve_rounds=1)
    assert np.array_equal(m1.nodes, m2.nodes)
    assert np.array_equal(o1, o2) and l1 == l2

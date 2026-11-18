"""The i1Pro 2 dual-scan calculation (workflow/dual_scan), on an INVENTED
instrument: made-up factory tables, tile and calibration, and a paper with
optical brightener forward-modelled through the formula's own physics. The
module must give back the paper's M1 and M2 exactly, refuse every input it
cannot use with a reason id, and its refinement must find the invented scale.
No real instrument's data is in this file."""
from __future__ import annotations

import numpy as np
import pytest

from workflow.dual_scan import cut, model, scale
from workflow.dual_scan.reasons import REASONS, DualScanRefused

WL = model.WAVELENGTHS
BAND = (WL >= 410) & (WL <= 550)


def invented_tables():
    x = (WL - 410) / 140.0
    kA = np.where(BAND, 1.2e-4 * (1.0 + 0.8 * np.sin(np.pi * x)), 0.0)
    kD = np.where(BAND, kA * (1.6 + 0.9 * x), 0.0)
    return model.UVTables.from_values(kA[:18], kD[:18])


def invented_calibration():
    white = 0.9 + 0.02 * np.cos(WL / 50.0)
    t = 0.012 * np.exp(-(WL - 380) / 25.0) + 1e-4
    emis = 2.4e4 * (1.0 + 0.3 * (WL - 380) / 350.0)
    return model.DualCalibration(white=white, uv_tile=t, emis=emis,
                                 lamp_clocks=517, uv_clocks=1443)


def invented_paper(n=30, seed=7):
    rng = np.random.default_rng(seed)
    base = rng.uniform(0.05, 0.9, size=(n, 1)) * (0.8 + 0.2 * rng.random((n, 36)))
    m2 = np.clip(base, 0.02, 0.95)
    # a brightener: emission peaking near 440 nm, more on lighter patches
    shape = np.exp(-0.5 * ((WL - 440) / 25.0) ** 2)
    g = (m2.mean(axis=1, keepdims=True)) * 900.0 * shape[None, :]
    return m2, g


S_TRUE = 1.137


def readings():
    tab, cal = invented_tables(), invented_calibration()
    m2, g = invented_paper()
    L, U, M1 = model.forward(m2, g, cal, tab, S_TRUE)
    return tab, cal, m2, L, U, M1


def test_the_formula_gives_back_the_invented_paper_exactly():
    tab, cal, m2, L, U, M1 = readings()
    c = model.compute(L, U, cal, tab, S_TRUE, lamp_clocks=517, uv_clocks=1443)
    np.testing.assert_allclose(c.m2, m2, atol=1e-12)
    np.testing.assert_allclose(c.m1, M1, atol=1e-12)
    np.testing.assert_array_equal(c.m0, L)
    # there really is glow to take off (the test would be empty otherwise)
    assert (L - m2)[:, BAND].max() > 0.05


def test_nothing_changes_outside_410_to_550_nm_and_nothing_is_clipped():
    tab, cal, m2, L, U, M1 = readings()
    c = model.compute(L, U, cal, tab, S_TRUE)
    np.testing.assert_array_equal(c.m1[:, ~BAND], L[:, ~BAND])
    np.testing.assert_array_equal(c.m2[:, ~BAND], L[:, ~BAND])
    # a value above 1 stays above 1 (no clipping)
    L2 = L.copy()
    L2[0, :] = 1.2
    c2 = model.compute(L2, U, cal, tab, S_TRUE)
    assert c2.m0[0].max() == pytest.approx(1.2) and c2.m1[0, ~BAND].max() == pytest.approx(1.2)


def test_m1_follows_the_factory_ratio():
    tab, cal, m2, L, U, M1 = readings()
    c = model.compute(L, U, cal, tab, S_TRUE)
    np.testing.assert_allclose(c.m1 - c.m0, tab.a * (c.m0 - c.m2), atol=1e-12)


def test_a_paper_without_brightener_is_not_affected_whatever_the_factor():
    tab, cal = invented_tables(), invented_calibration()
    m2, _g = invented_paper()
    L, U, _ = model.forward(m2, np.zeros_like(m2), cal, tab, S_TRUE)
    for s in (0.9, scale.STANDARD_SCALE, 1.4):
        c = model.compute(L, U, cal, tab, s)
        np.testing.assert_allclose(c.m2, m2, atol=1e-12)
        np.testing.assert_allclose(c.m1, m2, atol=1e-12)


def test_the_denominator_matters():
    """Without it (the older form) M2 is visibly off: the formula really
    takes the reflected LED light off with M2, not M0."""
    tab, cal, m2, L, U, M1 = readings()
    te = cal.checked(36).te()
    j_old = S_TRUE * tab.kA * (U * cal.emis - te * L)
    assert np.abs((L - j_old) - m2)[:, BAND].max() > 1e-4


def test_refusals_carry_reason_ids():
    tab, cal, m2, L, U, M1 = readings()
    no_uv = model.DualCalibration(cal.white, None, cal.emis)
    cases = [
        (lambda: model.compute(L, U, no_uv, tab, 1.1), "no_dual_calibration"),
        (lambda: model.compute(L, U, None, tab, 1.1), "no_dual_calibration"),
        (lambda: model.compute(L, U, cal, tab, 1.1, lamp_clocks=139), "calibration_mismatch"),
        (lambda: model.compute(L, U, cal, tab, 1.1, uv_clocks=139), "calibration_mismatch"),
        (lambda: model.compute(L, U, cal, None, 1.1), "no_uv_tables"),
        (lambda: model.compute(L, None, cal, tab, 1.1), "uv_pass_missing"),
        (lambda: model.compute(L, U[:-1], cal, tab, 1.1), "uv_pass_count"),
        (lambda: model.compute(L, U[:, :30], cal, tab, 1.1), "bad_values"),
        (lambda: model.compute(np.where(L > 0.5, np.nan, L), U, cal, tab, 1.1), "bad_values"),
        (lambda: model.compute(L, U, cal, tab, float("nan")), "bad_scale"),
        (lambda: model.compute(L, U, cal, tab, 5.0), "bad_scale"),
        (lambda: model.compute(L, U, cal, tab, "x"), "bad_scale"),
        (lambda: model.UVTables.from_values(None, tab.kD), "no_uv_tables"),
        (lambda: model.UVTables.from_values(np.zeros(18), np.zeros(18)), "no_uv_tables"),
        (lambda: model.UVTables.from_values(np.ones(18), np.ones(18)), "bad_uv_tables"),
        (lambda: model.UVTables.from_values(tab.kA[:18], tab.kD[:17]), "bad_uv_tables"),
        (lambda: model.UVTables.from_values(-tab.kA[:18], tab.kD[:18]), "bad_uv_tables"),
        (lambda: model.UVTables.from_values(tab.kA[:18], np.r_[tab.kD[:17], 0.0])
         if tab.kA[17] > 0 else (_ for _ in ()).throw(DualScanRefused("bad_uv_tables")), "bad_uv_tables"),
    ]
    for call, want in cases:
        with pytest.raises(DualScanRefused) as e:
            call()
        assert e.value.reason == want
        assert e.value.reason in REASONS and e.value.sentence


def test_every_reason_has_a_sentence_without_an_em_dash():
    for rid, text in REASONS.items():
        assert text and "—" not in text, rid
    with pytest.raises(KeyError):
        DualScanRefused("not_a_reason")


# ----------------------------------------------------------------- the cut

def _strip(n_patch=12, per_cell=10, uv_per_cell=6, seed=3):
    """A lamp pass forward and a UV pass back over the same strip; the
    UV value of patch k is k + 1 in every band (so a wrong cut shows)."""
    rng = np.random.default_rng(seed)
    pitch = 70.0
    lamp_pos = np.arange(n_patch * per_cell) * (pitch / per_cell)
    cells = [(k * per_cell, per_cell) for k in range(n_patch)]
    n_uv = n_patch * uv_per_cell
    uv_pos = (np.arange(n_uv)[::-1] + 0.5) * (pitch / uv_per_cell) + rng.normal(0, 0.3, n_uv)
    patch_of = np.clip((uv_pos // pitch).astype(int), 0, n_patch - 1)
    uvr = np.repeat((patch_of + 1.0)[:, None], 36, axis=1)
    return cells, lamp_pos, uv_pos, uvr


def test_the_uv_pass_is_cut_into_the_lamp_cells_by_the_ruler():
    cells, lp, up, ur = _strip()
    r = cut.cut_uv_pass(cells, lp, up, ur)
    np.testing.assert_allclose(r.uv[:, 0], np.arange(1, 13))
    assert min(r.counts) >= cut.MIN_UV_READINGS
    assert r.flatness < 1e-6


def test_a_uv_pass_that_misses_patches_is_refused():
    cells, lp, up, ur = _strip()
    keep = up > 300                      # the second pass stopped half way
    with pytest.raises(DualScanRefused) as e:
        cut.cut_uv_pass(cells, lp, up[keep], ur[keep])
    assert e.value.reason == "uv_pass_not_aligned"
    with pytest.raises(DualScanRefused) as e:
        cut.cut_uv_pass(cells, lp, np.zeros_like(up), ur)
    assert e.value.reason == "no_ruler"
    with pytest.raises(DualScanRefused) as e:
        cut.cut_uv_pass(cells, lp, up[:-1], ur)
    assert e.value.reason == "no_ruler"
    with pytest.raises(DualScanRefused) as e:
        cut.cut_uv_pass([(200, 10)], lp, up, ur)
    assert e.value.reason == "uv_pass_count"


def test_reading_positions_interpolate_the_ruler():
    p = cut.reading_positions([0, 10, 20], [0, 5, 10], 4, 5.0)
    np.testing.assert_allclose(p, [1.25, 3.75, 6.25, 8.75])
    with pytest.raises(DualScanRefused):
        cut.reading_positions([0], [0], 4, 5.0)


def test_spot_pairs_one_to_one():
    L, U = cut.pair_spot(np.ones((3, 36)), np.ones((3, 36)))
    assert L.shape == U.shape == (3, 36)
    with pytest.raises(DualScanRefused) as e:
        cut.pair_spot(np.ones((3, 36)), np.ones((2, 36)))
    assert e.value.reason == "uv_pass_count"


# ----------------------------------------------------------------- the scale

def test_the_standard_factor_is_built_in_and_sensible():
    s = scale.ScaleChoice.standard()
    assert s.source == "standard"
    assert model.SCALE_RANGE[0] < s.value < model.SCALE_RANGE[1]
    assert 1.08 <= s.value <= 1.22          # between the two instruments' values


def test_fit_scale_recovers_the_invented_scale():
    tab, cal, m2, L, U, M1 = readings()
    s, rms = scale.fit_scale(L, U, cal, tab, m2)
    assert s == pytest.approx(S_TRUE, abs=1e-6)
    assert rms < 1e-9


def _reference(L, M1, m2):
    return {"M0": L, "M1": M1, "M2": m2}


def test_refine_scale_learns_it_from_a_matching_file():
    tab, cal, m2, L, U, M1 = readings()
    choice, ev = scale.refine_scale(L, U, cal, tab, _reference(L, M1, m2))
    assert choice.source == "refined" and choice.value == pytest.approx(S_TRUE, abs=1e-4)
    assert ev["patches"] == len(L)


def test_refine_scale_refuses_what_does_not_belong_together():
    tab, cal, m2, L, U, M1 = readings()
    with pytest.raises(DualScanRefused) as e:
        scale.refine_scale(L, U, cal, tab, {"M0": L})
    assert e.value.reason == "refine_no_conditions"
    with pytest.raises(DualScanRefused) as e:
        scale.refine_scale(L, U, cal, tab, _reference(L[:-1], M1[:-1], m2[:-1]))
    assert e.value.reason == "refine_patches_differ"
    with pytest.raises(DualScanRefused) as e:        # another strip
        scale.refine_scale(L, U, cal, tab, _reference(L[::-1], M1[::-1], m2[::-1]))
    assert e.value.reason == "refine_m0_differs"
    # another instrument: its M1 follows another kD/kA
    other = M1 + 0.4 * (M1 - L)
    with pytest.raises(DualScanRefused) as e:
        scale.refine_scale(L, U, cal, tab, _reference(L, other, m2))
    assert e.value.reason == "refine_other_instrument"
    # a paper without brightener: nothing to learn from
    L0, U0, _ = model.forward(m2, np.zeros_like(m2), cal, tab, S_TRUE)
    with pytest.raises(DualScanRefused) as e:
        scale.refine_scale(L0, U0, cal, tab, _reference(L0, L0, L0))
    assert e.value.reason == "refine_no_glow"
    # values that no single factor explains
    rng = np.random.default_rng(1)
    noisy = m2 + np.where(BAND, rng.normal(0, 0.02, m2.shape), 0.0)
    M1n = L + tab.a * (L - noisy)
    with pytest.raises(DualScanRefused) as e:
        scale.refine_scale(L, U, cal, tab, _reference(L, M1n, noisy))
    assert e.value.reason == "refine_poor_fit"

"""Research C-S1 (Agent 24, tokens "a24-s1" / "a24-s1sprague"): F-series illuminants are
integrated at 1 nm in Maximum accuracy. The 5 nm CIE F tables put their mercury lines at 405,
435 and 545 nm, which a 10 nm band grid never samples (Findings/agent4-01 s2.3); smooth
illuminants and every other mode keep the band sum and their bytes (Findings/agent24-01 s2)."""
import inspect

import numpy as np
import pytest

from workflow.profile_engine import builder, spectral
from workflow.profile_engine.builder import BuildSettings, _spectral_method


@pytest.mark.parametrize("ill,fine", [("F5", True), ("F8", True), ("F10", True),
                                      ("F8M2", True), ("D50", False), ("D65", False),
                                      ("A", False), ("C", False), ("D50M2", False),
                                      ("", False)])
def test_only_line_illuminants_need_fine_integration(ill, fine):
    assert spectral.needs_fine_integration(ill) is fine


@pytest.mark.parametrize("mode", ["fast", "argyll"])
def test_other_modes_never_change(mode):
    s = BuildSettings(gammap_mode=mode, illuminant="F8")
    s.engine_candidates = frozenset({"a24-s1"})
    assert _spectral_method(s) == ""


def test_maximum_accuracy_needs_the_token_and_an_f_illuminant():
    # Research integration 3: "a24-s1" is a Maximum accuracy default, so an
    # F illuminant integrates by spline unless the token is switched off.
    s = BuildSettings(gammap_mode="accurate", illuminant="F8")
    assert _spectral_method(s) == "spline"
    s.engine_candidates = frozenset({"no-a24-s1"})
    assert _spectral_method(s) == ""
    s.engine_candidates = frozenset({"a24-s1"})
    assert _spectral_method(s) == "spline"
    s.engine_candidates = frozenset({"a24-s1sprague"})
    assert _spectral_method(s) == "sprague"
    for ill in ("D50", "D65", "A", ""):
        s = BuildSettings(gammap_mode="accurate", illuminant=ill)
        s.engine_candidates = frozenset({"a24-s1"})
        assert _spectral_method(s) == "", ill


def _truth_and_bands(seed=4):
    """Smooth print-like reflectances known at 1 nm, read as 10 nm point samples."""
    rng = np.random.default_rng(seed)
    lam1 = np.arange(360.0, 831.0)
    c = rng.uniform(420, 680, (60, 1))
    w = rng.uniform(30, 90, (60, 1))
    r1 = 0.05 + 0.85 / (1 + np.exp(-(lam1 - c) / (w / 4)))
    r1 = np.where(rng.uniform(size=(60, 1)) < 0.5, r1, 0.9 - r1)
    lam10 = np.arange(380.0, 731.0, 10.0)
    r10 = r1[:, (lam10 - 360).astype(int)]
    return lam1, r1, lam10, r10


@pytest.mark.parametrize("method", ["spline", "sprague"])
def test_fine_integration_lands_on_the_1nm_truth_under_f8(method):
    from benchmarks.research import colour
    lam1, r1, lam10, r10 = _truth_and_bands()
    truth = spectral.spectra_to_xyz(r1, lam1, illuminant="F8")
    band = spectral.spectra_to_xyz(r10, lam10, illuminant="F8")
    fine = spectral.spectra_to_xyz(r10, lam10, illuminant="F8", method=method)
    def lab(x, lam, m=""):   # media-relative to each method's own paper (ICC tables)
        w = spectral.spectra_to_xyz(np.full((1, len(lam)), 0.9), lam, illuminant="F8", method=m)[0]
        return colour.media_relative_lab(x, w)
    t = lab(truth, lam1)
    e_band = colour.de2000(lab(band, lam10), t)
    e_fine = colour.de2000(lab(fine, lam10, method), t)
    assert np.median(e_band) > 0.2            # the defect
    assert np.median(e_fine) < 0.1 * np.median(e_band)


def test_the_band_sum_is_the_default():
    lam1, r1, lam10, r10 = _truth_and_bands()
    a = spectral.spectra_to_xyz(r10, lam10, illuminant="F8")
    b = spectral.spectra_to_xyz(r10, lam10, illuminant="F8", method="")
    assert np.array_equal(a, b)


def test_the_builder_routes_both_integrations_through_the_gate():
    src = inspect.getsource(builder._build_profile_impl)
    assert "method=_spectral_method(settings)" in src
    assert "method=_spectral_method(settings)" in inspect.getsource(builder._v4_adaptation)

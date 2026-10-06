"""Integration 3 (Agent 10b, Findings/agent10-02 s3.3): the colprof-oracle
cache must key on every input of the oracle's command line. It used to leave
out settings.sat_gamut, so after one "-s" (perceptual only) build every later
"-S" build of the same measurement in the same app session reused the -s
result, and its saturation table became the perceptual one."""
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from workflow.profile_engine import gamut_map


def _settings(**kw):
    base = dict(quality="h", sat_gamut=True, perc_intent="", sat_intent="",
                src_viewing="", dst_viewing="", perc_src_colorimetric=False,
                sat_src_colorimetric=False, illuminant="", observer="",
                fwa=False, fwa_illum="", k_rule="", k_locus=False,
                k_curve_params=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _meas(tmp_path):
    p = tmp_path / "m.ti3"
    p.write_text("CTI3\n")
    return SimpleNamespace(path=p)


def test_s_and_S_get_different_cache_keys(tmp_path):
    meas = _meas(tmp_path)
    src = Path("/tmp/srgb.icc")
    k_S = gamut_map._oracle_cache_key(meas, src, _settings(sat_gamut=True), None)
    k_s = gamut_map._oracle_cache_key(meas, src, _settings(sat_gamut=False), None)
    assert k_S is not None and k_s is not None
    assert k_S != k_s
    a_S = gamut_map._oracle_args(Path("colprof"), _settings(sat_gamut=True), src)
    a_s = gamut_map._oracle_args(Path("colprof"), _settings(sat_gamut=False), src)
    assert "-S" in a_S and "-s" in a_s


def test_every_oracle_argument_is_in_the_key(tmp_path):
    meas = _meas(tmp_path)
    src = Path("/tmp/srgb.icc")
    base = gamut_map._oracle_cache_key(meas, src, _settings(), None)
    for change in (dict(quality="m"), dict(perc_intent="p"), dict(sat_intent="s"),
                   dict(src_viewing="mt"), dict(dst_viewing="pp"),
                   dict(perc_src_colorimetric=True), dict(sat_src_colorimetric=True),
                   dict(illuminant="D65"), dict(observer="1964_10"),
                   dict(fwa=True), dict(k_rule="x")):
        assert gamut_map._oracle_cache_key(meas, src, _settings(**change), None) != base, change
    # the same settings give the same key (the cache still hits)
    assert gamut_map._oracle_cache_key(meas, src, _settings(), None) == base
    # quality is keyed as the oracle clamps it: "u" runs colprof at -qh
    assert (gamut_map._oracle_cache_key(meas, src, _settings(quality="u"), None)
            == base)
    node = np.zeros((5, 3))
    assert gamut_map._oracle_cache_key(meas, src, _settings(), node) != base

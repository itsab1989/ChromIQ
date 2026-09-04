"""Two options the Build Profile tab could ask for and the engine got wrong.

Found by the engine-accuracy challenge, 2026-09-04:

* ``-L klimit`` is colprof's BLACK ink limit (0–100 %, usage text of
  colprof 3.5.0); the engine's extra-options parser folded it into the TOTAL
  ink limit, so a hand-typed ``-L 50`` on a CMYK build capped every ink at
  50 % — and no black limit existed at all, not even the chart's own
  ``BLACK_INK_LIMIT`` keyword (targen ``-L``) that colprof honours.
* The CIE Observer box has offered "2015 2°" and "2015 10°" since #121;
  ``engine_support`` said the engine could build them and the build then
  died with "Unknown observer '2015_2'". The CIE 170-2:2015 tables (CVRL
  database) are in :mod:`spectral_data` now; parity against
  ``colprof -o 2015_2`` on the real ColorMunki chart measured ΔE2000 median
  0.18 at the patches — the same level as the 1964_10 path that was already
  trusted.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from benchmarks.iccread import IccProfile
from tests.test_profile_engine import synth_xyz, write_synth_ti3
from workflow.engine_builder import _apply_extra_args
from workflow.profile_engine import BuildSettings, build_profile
from workflow.profile_engine.spectral import observer_cmf, spectra_to_xyz
from workflow.profile_engine.ti3_data import read_ti3

_TS = datetime(2026, 9, 5, tzinfo=timezone.utc)
_CMYK = [f"CMYK_{c}" for c in "CMYK"]


def test_extra_option_L_is_the_black_limit_and_l_the_total():
    s = BuildSettings()
    _apply_extra_args("-L 50", s)
    assert s.black_ink_limit == 50.0 and s.ink_limit is None
    s = BuildSettings()
    _apply_extra_args("-l 250 -L80", s)
    assert s.ink_limit == 250.0 and s.black_ink_limit == 80.0


def _k_max(icc_path, tag="B2A1") -> float:
    icc = IccProfile(icc_path)
    # A neutral ramp plus a dense grid of dark, saturated targets — where
    # the separation wants the most K.
    ramp = np.stack([np.linspace(2.0, 98.0, 49), np.zeros(49),
                     np.zeros(49)], 1)
    rng = np.random.default_rng(7)
    dark = rng.uniform([2, -40, -40], [40, 40, 40], (400, 3))
    dev = icc.b2a_device(np.vstack([ramp, dark]), tag)
    return float(dev[:, 3].max())


@pytest.mark.parametrize("mode", ["fast", "accurate"])
def test_black_ink_limit_caps_the_k_channel_only(tmp_path, mode):
    ti3 = write_synth_ti3(tmp_path / "c.ti3", "CMYK", _CMYK, False,
                          n_per_axis=6, ink_limit=300.0)
    plain = tmp_path / "plain.icc"
    build_profile(ti3, plain, BuildSettings(quality="l", gammap_mode=mode,
                                            timestamp=_TS))
    capped = tmp_path / "capped.icc"
    lines: list[str] = []
    build_profile(ti3, capped, BuildSettings(quality="l", gammap_mode=mode,
                                             timestamp=_TS,
                                             black_ink_limit=60.0,
                                             progress=lines.append))
    assert any("Black ink limited to 60%" in ln for ln in lines), lines
    # Without the limit the synthetic printer's black corner uses full K.
    assert _k_max(plain) > 0.95
    # With it, K never exceeds 60 % in the written table (u16 rounding)...
    assert _k_max(capped) <= 0.60 + 1e-3
    # ...and the OTHER inks are not capped: the total limit alone still
    # lets C reach its solid.
    icc = IccProfile(capped)
    dev = icc.b2a_device(np.array([[55.0, -35.0, -45.0]]), "B2A1")[0]
    assert dev[0] > 0.9, dev


def test_chart_black_ink_limit_keyword_is_honoured_like_colprof(tmp_path):
    ti3 = write_synth_ti3(tmp_path / "c.ti3", "CMYK", _CMYK, False,
                          n_per_axis=6, ink_limit=300.0)
    text = ti3.read_text(encoding="utf-8").replace(
        'TOTAL_INK_LIMIT "300"', 'TOTAL_INK_LIMIT "300"\nBLACK_INK_LIMIT "70"')
    ti3.write_text(text, encoding="utf-8")
    assert read_ti3(ti3).black_ink_limit == 70.0
    out = tmp_path / "k70.icc"
    build_profile(ti3, out, BuildSettings(quality="l", timestamp=_TS))
    assert _k_max(out) <= 0.70 + 1e-3


def test_2015_observers_exist_and_are_not_the_1931_tables():
    lam = np.arange(380.0, 731.0, 5.0)          # 555 nm must be on the grid
    c31 = observer_cmf("", lam)
    for name in ("2015_2", "2015_10"):
        c = observer_cmf(name, lam)
        assert c.shape == c31.shape
        # ȳ peaks at 555 nm in every CIE observer, with unit height.
        assert abs(c[1].max() - 1.0) < 2e-3
        assert lam[int(np.argmax(c[1]))] == 555.0
        # …but the curves are a different observer, not a copy.
        assert np.abs(c - c31).max() > 0.02
    # A flat reflector under D50 is the illuminant's own white, whichever
    # observer integrates it (k normalises Y to 100).
    refl = np.ones((1, len(lam)))
    for name in ("", "1964_10", "2015_2", "2015_10"):
        xyz = spectra_to_xyz(refl, lam, illuminant="D50", observer=name)[0]
        assert abs(xyz[1] - 100.0) < 1e-9
        assert 90.0 < xyz[0] < 100.0 and 75.0 < xyz[2] < 90.0, (name, xyz)


def test_build_with_a_2015_observer_uses_the_spectra(tmp_path):
    """The build that used to die with "Unknown observer" now completes,
    and the colorimetry actually moves (the observer did something)."""
    rng = np.random.default_rng(3)
    dev = rng.uniform(0.0, 1.0, (150, 3))
    dev[0] = 1.0
    lam = np.arange(380.0, 731.0, 10.0)
    # Smooth synthetic reflectances: a paper white and three ink absorbers.
    peaks = np.array([450.0, 540.0, 610.0])
    absorb = np.exp(-((lam[None, :] - peaks[:, None]) / 40.0) ** 2)
    refl = 0.9 * np.prod(1.0 - 0.85 * (1.0 - dev)[:, :, None] * absorb[None],
                         axis=1)
    lines = ["CTI3", "", 'COLOR_REP "RGB_XYZ"', 'DEVICE_CLASS "OUTPUT"',
             'SPECTRAL_BANDS "36"', 'SPECTRAL_START_NM "380.0"',
             'SPECTRAL_END_NM "730.0"',
             f"NUMBER_OF_FIELDS {7 + 36}", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z "
             + " ".join(f"SPEC_{int(w)}" for w in lam),
             "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(dev)}", "BEGIN_DATA"]
    xyz = spectra_to_xyz(refl, lam)
    for i, (d, x, r) in enumerate(zip(dev, xyz, refl)):
        lines.append(f"{i + 1} " + " ".join(f"{v * 100:.4f}" for v in d)
                     + " " + " ".join(f"{v:.4f}" for v in x)
                     + " " + " ".join(f"{v:.5f}" for v in r))
    lines.append("END_DATA")
    ti3 = tmp_path / "spec.ti3"
    ti3.write_text("\n".join(lines), encoding="utf-8")
    base = tmp_path / "base.icc"
    obs = tmp_path / "obs.icc"
    build_profile(ti3, base, BuildSettings(quality="l", timestamp=_TS))
    build_profile(ti3, obs, BuildSettings(quality="l", timestamp=_TS,
                                          observer="2015_10"))
    a = IccProfile(base).a2b_lab(dev[:40], "A2B1")
    b = IccProfile(obs).a2b_lab(dev[:40], "A2B1")
    diff = np.linalg.norm(a - b, axis=1)
    assert diff.max() > 0.5, diff.max()          # the observer changed colours
    assert np.abs(b[0]).sum() < 100.5           # white still (100, 0, 0)

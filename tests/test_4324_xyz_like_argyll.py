"""4.3.24: an i1Profiler import computes XYZ from its spectra the way
ArgyllCMS does (``workflow.argyll_colorimetry``), not by 10 nm sums.

jctay (printerknowledge, 2026-11-04): his own converter matched ArgyllCMS's
``spec2cie`` to about 0.001 dE76, ChromIQ's import was 0.05 mean, 0.10 max
away on the very same spectra. ``spec2cie`` integrates at 1 nm over 360 to
830 nm, interpolates a 10 nm spectrum with a 4-point Lagrange cubic and holds
its end values beyond the measured range (``xicc/xspect.c``,
``xsp2cie_sconvert``). Every spectrum here is invented.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.argyll_colorimetry import spectra_to_xyz_like_argyll  # noqa: E402
from workflow.profile_engine.ti3_data import xyz_to_lab              # noqa: E402
from workflow.reference_convert import (                             # noqa: E402
    XYZ_METHOD_KEYWORD, cxf_measurement_to_ti3)
from workflow.ti3_analysis import parse_ti3                          # noqa: E402

_LAM10 = np.arange(380, 731, 10.0)
_X = np.arange(36)
#: Five invented 380-730 nm spectra (percent): a perfect white, three smooth
#: colours, and a step like a brightened paper.
_GOLDEN_SPECTRA = np.array([
    np.full(36, 100.0),
    100 * (0.05 + 0.8 * np.exp(-((_X - 7) / 5.0) ** 2)),
    100 * (0.04 + 0.7 * np.exp(-((_X - 28) / 6.0) ** 2)),
    100 * (0.03 + 0.6 * np.exp(-((_X - 17) / 4.0) ** 2)),
    np.concatenate([np.full(8, 112.0), np.full(28, 88.0)]),
])
#: What ArgyllCMS 3.5.0 ``spec2cie`` (D50, 1931 2 degree) wrote for them,
#: 2026-11-04, as printed.
_GOLDEN_XYZ = np.array([
    [96.42425, 100.0, 82.51239],
    [14.67711, 11.36709, 58.96369],
    [26.61781, 16.25423, 3.326287],
    [21.66854, 36.60986, 4.410252],
    [86.75544, 88.1374, 82.21366],
])


def _de76(a, b) -> np.ndarray:
    return np.linalg.norm(xyz_to_lab(np.asarray(a)) - xyz_to_lab(np.asarray(b)),
                          axis=1)


# ---- pure Python ------------------------------------------------------------

def test_golden_values_from_spec2cie():
    got = spectra_to_xyz_like_argyll(_GOLDEN_SPECTRA, _LAM10, percent=True)
    assert np.allclose(got, _GOLDEN_XYZ, atol=1e-4), got
    assert _de76(got, _GOLDEN_XYZ).max() < 1e-4


def test_a_fraction_and_percent_give_the_same_xyz():
    a = spectra_to_xyz_like_argyll(_GOLDEN_SPECTRA, _LAM10, percent=True)
    b = spectra_to_xyz_like_argyll(_GOLDEN_SPECTRA / 100.0, _LAM10)
    assert np.allclose(a, b)


def test_the_old_10nm_sums_were_measurably_different():
    """Why this module exists: the 4.3.23 import's sums are ~0.05 dE76 away
    on the same spectra (0.10 max on jctay's)."""
    from workflow.profile_engine.spectral import spectra_to_xyz
    old = spectra_to_xyz(_GOLDEN_SPECTRA, _LAM10, illuminant="D50")
    d = _de76(old, _GOLDEN_XYZ)
    assert d.max() > 0.01


def test_negative_xyz_is_clamped_as_argyll_clamps_it():
    sp = np.full((1, 36), -1.0)
    assert np.all(spectra_to_xyz_like_argyll(sp, _LAM10, percent=True) == 0)


def test_uneven_wavelengths_are_refused():
    with pytest.raises(ValueError):
        spectra_to_xyz_like_argyll(np.ones((1, 3)), [380.0, 390.0, 410.0])


# ---- against ArgyllCMS itself ------------------------------------------------

def _spec2cie() -> "str | None":
    p = Path("/Applications/Argyll/bin/spec2cie")
    return str(p) if p.exists() else shutil.which("spec2cie")


def _read_xyz(path: Path) -> np.ndarray:
    return np.asarray(parse_ti3(path).xyz, dtype=float)


def _spectral_ti3(path: Path, lam, spectra) -> Path:
    lines = ["CTI3", "", 'DESCRIPTOR "invented"', 'ORIGINATOR "test"',
             'DEVICE_CLASS "OUTPUT"', 'COLOR_REP "RGB_XYZ"',
             f'SPECTRAL_BANDS "{len(lam)}"',
             f'SPECTRAL_START_NM "{lam[0]:f}"', f'SPECTRAL_END_NM "{lam[-1]:f}"',
             "", f"NUMBER_OF_FIELDS {7 + len(lam)}", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z "
             + " ".join(f"SPEC_{int(w)}" for w in lam),
             "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {len(spectra)}",
             "BEGIN_DATA"]
    for i, s in enumerate(spectra, 1):
        lines.append(f"{i} 0 0 0 0 0 0 " + " ".join(f"{v:.6f}" for v in s))
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _run_spec2cie(src: Path, dst: Path) -> None:
    r = subprocess.run([_spec2cie(), str(src), str(dst)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       timeout=120)
    assert r.returncode == 0, "spec2cie did not finish: " + r.stdout + r.stderr


@pytest.mark.skipif(not _spec2cie(), reason="ArgyllCMS not installed")
@pytest.mark.parametrize("lam", [
    np.arange(380, 731, 10.0), np.arange(400, 701, 10.0),
    np.arange(380, 781, 5.0), np.arange(400, 701, 20.0),
    np.arange(340, 831, 10.0)], ids=["380-730/10", "400-700/10", "380-780/5",
                                     "400-700/20", "340-830/10"])
def test_matches_spec2cie_on_invented_spectra(tmp_path, lam):
    rng = np.random.default_rng(int(lam[0] + len(lam)))
    spectra = []
    for _ in range(30):
        c, w, a = (rng.uniform(380, 720, 3), rng.uniform(15, 80, 3),
                   rng.uniform(0, 0.9, 3))
        spectra.append(100 * (0.02 + sum(
            a[k] * np.exp(-((lam - c[k]) / w[k]) ** 2) for k in range(3))))
    spectra = np.array(spectra)
    spectra[0] = 100.0
    spectra[1, :] = 88.0
    spectra[1, :6] = 130.0          # a brightened, fluorescent blue end
    src = _spectral_ti3(tmp_path / "in.ti3", lam, spectra)
    _run_spec2cie(src, tmp_path / "out.ti3")
    want = _read_xyz(tmp_path / "out.ti3")
    got = spectra_to_xyz_like_argyll(spectra, lam, percent=True)
    d = _de76(got, want)
    assert d.max() < 0.001, (d.mean(), d.max())


@pytest.mark.skipif(not _spec2cie(), reason="ArgyllCMS not installed")
def test_an_i1profiler_import_has_spec2cies_xyz(tmp_path):
    """The import itself: spec2cie recomputing the written .ti3 from its own
    SPEC_ columns changes nothing (0.001 dE76)."""
    from tests.test_4324_cxf_selected_condition import _native
    src = _native(tmp_path / "a.mxf", ("M0", "M1", "M2"), "1")
    out = cxf_measurement_to_ti3(src, tmp_path / "a.ti3")
    _run_spec2cie(out, tmp_path / "s.ti3")
    d = _de76(_read_xyz(out), _read_xyz(tmp_path / "s.ti3"))
    assert d.max() < 0.001, (d.mean(), d.max())


# ---- only new imports use it -------------------------------------------------

def test_a_new_import_says_how_its_xyz_was_computed(tmp_path):
    from tests.test_4324_cxf_selected_condition import _native
    out = cxf_measurement_to_ti3(_native(tmp_path / "a.mxf", ("M1",), "1"),
                                 tmp_path / "a.ti3")
    assert parse_ti3(out).keywords.get(XYZ_METHOD_KEYWORD, "").startswith(
        "ArgyllCMS")


def test_an_earlier_import_keeps_the_xyz_it_was_written_with(tmp_path):
    """Nothing recomputes an existing .ti3: an import made by 4.3.23 (no
    method keyword) reads back with exactly its own numbers."""
    src = _spectral_ti3(tmp_path / "old.ti3", _LAM10, _GOLDEN_SPECTRA)
    text = src.read_text(encoding="utf-8").replace(
        "1 0 0 0 0 0 0 ", "1 0 0 0 96.4000 99.9000 82.4000 ", 1)
    src.write_text(text, encoding="utf-8")
    before = src.read_bytes()
    d = parse_ti3(src)
    assert np.allclose(np.asarray(d.xyz)[0], [96.4, 99.9, 82.4])
    assert XYZ_METHOD_KEYWORD not in d.keywords
    assert src.read_bytes() == before

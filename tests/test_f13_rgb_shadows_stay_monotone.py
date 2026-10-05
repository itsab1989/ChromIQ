"""Research finding F-13 (Findings/agent20-01-f13.md): an RGB printer's
Maximum accuracy colorimetric table must not turn lighter in the deep shadows.

On the battery's RGB printer X1 (black L* 7.9) an sRGB grey ramp printed
relative colorimetric through lcms and ColorSync rose from L* 7.86 at code 0
to about 10-11 at codes 8-20 and fell back to 9 near code 24: the smoothing
refit (b2a.refine_b2a_clut) set the neutral-column nodes below the black from
their lighter, chromatic neighbours. colprof's column is flat at the black
until the ramp enters the gamut. The ramp here is printed on the battery's
synthetic truth, so a lighter step is a lighter print, not a model artefact.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from workflow.profile_engine import BuildSettings, build_profile

FIXTURE = Path(__file__).parent / "data" / "f13" / "X1-typical-s23-targen400.ti3"
SRGB = "/System/Library/ColorSync/Profiles/sRGB Profile.icc"
CODES = np.arange(0.0, 40.0001, 0.25)        # 16-bit steps near black
TOL = 0.02                                    # L*, a step darker than this is a reversal


def _lcms_ramp(src: str, prof: Path) -> np.ndarray:
    from benchmarks.research import cmm
    lib = cmm._lcms()
    hs = lib.cmsOpenProfileFromFile(src.encode(), b"r")
    hp = lib.cmsOpenProfileFromFile(str(prof).encode(), b"r")
    v = np.round(CODES / 255.0 * 65535.0)
    rgb = np.ascontiguousarray(np.repeat(v[:, None], 3, 1), dtype=np.uint16)
    fmt = (4 << 16) | (3 << 3) | 2                       # TYPE_RGB_16
    t = lib.cmsCreateTransform(hs, fmt, hp, fmt, 1, 0x0100)  # relative, NOOPTIMIZE
    assert t
    out = np.zeros((len(v), 3), np.uint16)
    lib.cmsDoTransform(t, rgb.ctypes.data, out.ctypes.data, len(v))
    lib.cmsDeleteTransform(t); lib.cmsCloseProfile(hp); lib.cmsCloseProfile(hs)
    return out / 65535.0


def _colorsync_ramp(src: str, prof: Path) -> np.ndarray:
    Q = pytest.importorskip("Quartz")

    def space(p):
        d = Path(p).read_bytes()
        return Q.CGColorSpaceCreateWithICCData(Q.CFDataCreate(None, d, len(d)))
    s, d = space(src), space(prof)
    res = []
    for c in CODES / 255.0:
        m = Q.CGColorCreateCopyByMatchingToColorSpace(
            d, Q.kCGRenderingIntentRelativeColorimetric,
            Q.CGColorCreate(s, [float(c)] * 3 + [1.0]), None)
        comp = Q.CGColorGetComponents(m)
        res.append([comp[i] for i in range(3)])
    return np.array(res)


def _largest_reversal(lstar: np.ndarray) -> float:
    return float((np.maximum.accumulate(lstar) - lstar).max())


@pytest.fixture(scope="module")
def x1_profile(tmp_path_factory):
    out = tmp_path_factory.mktemp("f13") / "X1-accurate.icc"
    st = BuildSettings(quality="m", gammap_mode="accurate", icc_version="2",
                       progress=lambda m: None)
    return build_profile(FIXTURE, out, st).icc_path


@pytest.fixture(scope="module")
def x1_truth():
    from benchmarks.research.printers import build_printers
    return build_printers()["X1"]


@pytest.mark.slow
@pytest.mark.skipif(sys.platform != "darwin" or not Path(SRGB).exists(),
                    reason="uses the system sRGB profile (and ColorSync)")
@pytest.mark.parametrize("cmm", ["lcms", "colorsync"])
def test_srgb_grey_ramp_never_prints_lighter_in_the_shadows(cmm, x1_profile, x1_truth):
    ramp = (_lcms_ramp if cmm == "lcms" else _colorsync_ramp)(SRGB, x1_profile)
    lstar = x1_truth.lab_rel(np.clip(ramp, 0.0, 1.0))[:, 0]
    black = x1_truth.lab_rel(np.zeros((1, 3)))[0, 0]
    # the black stays the deepest black (D-17 black depth row)
    assert lstar[0] == pytest.approx(black, abs=0.05)
    rev = _largest_reversal(lstar)
    worst = int(np.argmax(np.maximum.accumulate(lstar) - lstar))
    assert rev <= TOL, (
        f"{cmm}: sRGB code {CODES[worst]:.2f} prints L* {lstar[worst]:.2f}, "
        f"{rev:.2f} darker than an earlier, darker code (F-13)")


def test_below_black_column_selects_only_the_neutral_column_under_the_black():
    from workflow.profile_engine import b2a as b2a_mod
    nodes = np.array([[0.0, 0.0, 0.0], [3.125, 0.0, 0.0], [6.25, 0.4, -0.3],
                      [9.375, 0.0, 0.0], [3.125, 8.0, 0.0], [6.25, 0.0, -8.0]])
    assert b2a_mod.below_black_column(nodes, 7.9).tolist() == [0, 1, 2]
    pinned = b2a_mod.pin_nodes(np.ones((6, 3)), np.array([1, 2]), np.zeros(3))
    assert pinned[[1, 2]].max() == 0.0 and pinned[[0, 3, 4, 5]].min() == 1.0

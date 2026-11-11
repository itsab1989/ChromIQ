"""Maximum accuracy's black is at least as deep as Fast mode's (2026-09-05).

The independent challenger (C3) measured the mode's CMYK black 1.5 L*
LIGHTER than Fast's on the same synthetic chart, both exactly on the
total ink limit — contrary to the Preferences text "dark shadows keep
their depth when the total ink limit steps in".

Measured on the battery's CMYK printer (S3, 280 % limit, quality m):
the inversion's own objective at L*=0 has its optimum at (0.66, 0.59,
0.55, K 1.0), true L* 9.9 — and the solver delivered (0.75, 0.56, 0.75,
0.75), L* 14.8. The total ink limit was enforced by a projection AFTER
every Gauss–Newton step, which subtracts a common amount from every
channel: a dark target drives C, M, Y and K all onto the 1.0 face, the
projection hands back equal parts of each, and the K prior's pull is
undone each iteration. Neither the proportional scaling of the parity
path (L* 14.7 on the same model), ``black_l`` nor the locus were it. The
step is now solved ON the limit's face for the rows that would cross it
(``b2a._tac_face_step``): B2A1(0,0,0) prints L* 9.8, Fast 13.5, and the
neutral ramp below L* 20 is monotone (was 14.8 → 12.9 → 13.3 → 12.0 …).
Fast mode is untouched — the face step only runs with ``tac_projection``.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from benchmarks.iccread import IccProfile
from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
from workflow.profile_engine import BuildSettings, build_profile

_TS = datetime(2026, 9, 5, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def cmyk_blacks(tmp_path_factory):
    """B2A1 device value for L*=0 and the neutral ramp, both modes, on the
    battery's CMYK printer (exact physics as the referee)."""
    tmp = tmp_path_factory.mktemp("black")
    printer = PRINTERS["S3"]
    chart = make_chart(printer, 400)
    xyz, refl, _ = measure(printer, chart)
    ti3 = write_ti3(tmp / "S3.ti3", printer, chart, xyz, refl)
    ls = np.array([0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 15.0, 20.0])
    ramp = np.stack([ls, 0 * ls, 0 * ls], 1)
    out = {}
    for mode in ("fast", "accurate"):
        icc = tmp / f"{mode}.icc"
        build_profile(ti3, icc, BuildSettings(quality="l", gammap_mode=mode,
                                              ink_limit=printer.tac,
                                              timestamp=_TS))
        dev = IccProfile(icc).b2a_device(ramp, "B2A1")
        out[mode] = (dev, printer.lab_relative_true(dev))
    return printer, out


def test_accurate_black_is_at_least_as_deep_as_fast(cmyk_blacks):
    printer, out = cmyk_blacks
    dev_f, lab_f = out["fast"]
    dev_a, lab_a = out["accurate"]
    # Both blacks sit on the total ink limit — depth is not bought with ink.
    assert dev_f[0].sum() <= printer.tac / 100.0 + 1e-3
    assert dev_a[0].sum() <= printer.tac / 100.0 + 1e-3
    assert lab_a[0, 0] <= lab_f[0, 0] + 0.2, (lab_a[0], lab_f[0])


def test_accurate_black_uses_the_full_black_ink(cmyk_blacks):
    # The deepest colour under a total ink limit spends the limit on the
    # darkest ink first; the projection used to hand back ~0.75 of it.
    _printer, out = cmyk_blacks
    dev_a, _lab = out["accurate"]
    assert dev_a[0, 3] >= 0.97, dev_a[0]


def test_accurate_neutral_ramp_below_l20_never_gets_lighter_going_down(
        cmyk_blacks):
    _printer, out = cmyk_blacks
    _dev, lab_a = out["accurate"]
    l_printed = lab_a[:, 0]
    # Requested L* 0, 2, 4 … 20: what prints must not get LIGHTER as the
    # request gets darker (the old solver printed L*=0 lighter than L*=8).
    assert (np.diff(l_printed) >= -0.15).all(), l_printed

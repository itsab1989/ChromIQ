"""Maximum accuracy prints the neutral highlight and the black where they belong.

Research agent5-03 (2026-10-03), confirmed by agent 7 (T2c): the accurate B2A
sent the neutral L* 93.75 node far too dark (battery S5 printed L* 62-68, a
Clapper-Yule 6-ink printer 58.7, CMYK glossy 87.8). Two causes: the n > 3
refit drew its inverse samples from uniform device points that almost never
print light, and the A2B shaper curves started from the identity, so the first
10 % of ink (where dot gain moves the colour most) shared one grid cell with
paper. Plus the black: the L* = 0 corner could land on a chromatic vertex of
the ink-limit face. These tests build the battery's own printers and print the
B2A on their exact physics.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from benchmarks.iccread import IccProfile
from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
from workflow.profile_engine import BuildSettings, build_profile
from workflow.profile_engine.forward_model import ramp_positioning_curves

_TS = datetime(2026, 10, 3, tzinfo=timezone.utc)


def _build(tmp, pid, n_patches, quality):
    printer = PRINTERS[pid]
    chart = make_chart(printer, n_patches)
    xyz, refl, _ = measure(printer, chart)
    ti3 = write_ti3(tmp / f"{pid}.ti3", printer, chart, xyz, refl)
    icc = tmp / f"{pid}.icc"
    build_profile(ti3, icc, BuildSettings(quality=quality,
                                          gammap_mode="accurate",
                                          ink_limit=printer.tac,
                                          timestamp=_TS))
    return printer, IccProfile(icc)


@pytest.fixture(scope="module")
def s5(tmp_path_factory):
    return _build(tmp_path_factory.mktemp("s5"), "S5", 600, "l")


@pytest.mark.slow
def test_six_ink_neutral_highlight_prints_light(s5):
    printer, icc = s5
    ls = np.array([85.0, 90.0, 93.75, 96.0])
    dev = icc.b2a_device(np.stack([ls, 0 * ls, 0 * ls], 1), "B2A1")
    lab = printer.lab_relative_true(dev)
    # was L* 62-69 for the 93.75 node before the fix
    assert np.all(np.abs(lab[:, 0] - ls) < 3.0), lab
    assert np.all(np.hypot(lab[:, 1], lab[:, 2]) < 3.0), lab


@pytest.mark.slow
def test_six_ink_neutral_ramp_is_monotone_and_black_neutral(s5):
    printer, icc = s5
    ls = np.arange(0.0, 100.0 + 1e-9, 0.5)
    dev = icc.b2a_device(np.stack([ls, 0 * ls, 0 * ls], 1), "B2A1")
    lab = printer.lab_relative_true(dev)
    black = lab[0]
    reach = ls >= black[0] + 1.0
    assert (np.diff(lab[reach, 0]) > -0.1).all(), "L* reversal on the ramp"
    assert np.hypot(black[1], black[2]) < 2.0, black


def test_ramp_curves_stretch_the_first_per_cent_under_dot_gain():
    # One ink whose visual distance from paper grows like sqrt(ink): dot
    # gain. Ramp 0.1 .. 1.0 plus paper, as on the battery's charts.
    x = np.round(np.arange(0.0, 1.0001, 0.1), 3)
    lab = np.stack([100.0 - 60.0 * np.sqrt(x), 0 * x, 0 * x], 1)
    dev = x[:, None]
    cur = ramp_positioning_curves(dev, lab, knots=21)[0]
    # concave: the first 10 % of ink gets more than its share of the grid
    assert cur[2] > 0.1 + 0.05, cur[:4]
    assert cur[0] == 0.0 and abs(cur[-1] - 1.0) < 1e-9
    assert (np.diff(cur) > 0).all()


def test_ramp_curves_keep_the_identity_without_single_ink_patches():
    rng = np.random.default_rng(1)
    dev = rng.uniform(0.2, 1.0, (50, 4))       # no ramps, no paper
    lab = rng.uniform(20, 80, (50, 3))
    cur = ramp_positioning_curves(dev, lab, knots=21)
    assert np.allclose(cur, np.tile(np.linspace(0, 1, 21), (4, 1)))

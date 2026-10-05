"""Agent 18b: the N-ink chart battery's independent development printers
(challenge B2: X9 reused the X5/X6 ink spectra). X10-X12 use a second ink set,
matte paper, other gains and a kinked TVI; existing printers are unchanged."""
from __future__ import annotations

import numpy as np

from benchmarks.research import colour
from benchmarks.research.printers import ClapperYuleTruth, _kink, build_printers


def test_existing_printers_do_not_move():
    p = build_printers()
    dev = np.random.default_rng(1).uniform(0, 1, (50, 7))
    ref = ClapperYuleTruth("X9", "CMYKOGV", tac=320.0)
    assert np.allclose(p["X9"].lab_rel(dev), ref.lab_rel(dev))
    assert p["X9"].inkset == "a" and p["X9"].kink_amp == 0.0


def test_the_independent_printers_use_other_inks():
    p = build_printers()
    for a, b in (("X9", "X10"), ("X3", "X12")):
        n = p[a].n
        solids = np.eye(n)
        de = colour.de2000(p[a].lab_rel(solids), p[b].lab_rel(solids))
        chromatic = [i for i, l in enumerate(p[a].letters) if l != "K"]
        assert (de[chromatic] > 3.0).all(), (a, b, de)
    assert p["X11"].letters == ["C", "M", "Y"]


def test_the_kink_keeps_paper_and_solid_and_breaks_the_slope():
    a = np.linspace(0, 1, 2001)
    k = _kink(a, 0.42, 0.05)
    assert k[0] == 0.0 and abs(k[-1] - 1.0) < 1e-12
    assert np.all(np.diff(k) > 0)                          # still monotone
    d = np.diff(k) / np.diff(a)
    i = int(0.42 * 2000)
    assert d[i + 2] - d[i - 2] > 0.15                     # a real slope break

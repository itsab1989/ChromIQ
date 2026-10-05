"""Research agent17-01 item 1: the neutral black on a printer whose dark end
lightens.

Agent 13's XKB truth (X3 behind a 50 % linearisation kink, plus a reddish
bronzing sheen that switches on between 230 % and 250 % total ink): the
darkest neutral it prints under a 300 % limit is about L* 7.2-8. The neutral
walk from paper white follows the late-GCR branch, loads C, M and Y into the
bronzing zone and stopped far lighter (L* 12.1 on the exact-truth grid model
here; L* 21.6-21.9 in 5 of 6 real builds). The black is now also searched
without the ink policy, and the axis re-routed to it.
"""
from dataclasses import dataclass

import numpy as np
import pytest

from benchmarks.research.printers import TruthPrinter, build_printers
from workflow.profile_engine import b2a
from workflow.profile_engine.forward_model import ForwardModel


@dataclass(frozen=True)
class _KinkBronze(TruthPrinter):
    id: str = "XKB"
    device_rep: str = "CMYK"
    tac: float | None = 300.0
    family: str = "clapper-yule-kinked"

    def reflectance(self, device, lam):
        x3 = build_printers()["X3"]
        d = np.clip(np.atleast_2d(np.asarray(device, float)), 0, 1)
        lin = np.where(d < 0.5, 0.75 * d, 0.375 + 1.25 * (d - 0.5))
        r = x3.reflectance(lin, lam)
        s = np.clip((d.sum(1) - 2.3) / 0.2, 0.0, 1.0)
        s = s * s * (3 - 2 * s)
        sheen = 0.035 * (0.3 + 0.7 * d[:, 0]) * s
        spec = 1.0 / (1.0 + np.exp(-(np.asarray(lam) - 600.0) / 25.0))
        return r + sheen[:, None] * (0.3 + 0.7 * spec)[None, :]


_KW = dict(channel_letters=list("CMYK"), is_additive=False, ink_limit=300.0,
           accurate=True, extra_hues={}, black_l=None, k_gen=None, ucs=False,
           channel_max=None)


@pytest.fixture(scope="module")
def xkb():
    p = _KinkBronze()
    ax1 = np.linspace(0.0, 1.0, 9)
    dev = np.stack(np.meshgrid(*[ax1] * 4, indexing="ij"), -1).reshape(-1, 4)
    model = ForwardModel(grid=9, n_channels=4, nodes=p.lab_rel(dev),
                         curves=np.tile(np.linspace(0.0, 1.0, 21), (4, 1)))
    return p, model


@pytest.mark.slow
def test_the_black_is_the_darkest_neutral_not_the_end_of_the_walk(xkb):
    p, model = xkb
    walk = b2a.neutral_axis(model, deep_black=False, **_KW)
    axis = b2a.neutral_axis(model, **_KW)
    # the walk alone stops lighter (the defect)
    assert walk["l_black"] > 11.0
    # the fixed axis reaches the deep neutral, and the PRINTER agrees
    assert axis["l_black"] < 9.0
    printed = p.lab_rel(axis["black"][None, :])[0]
    assert printed[0] < 9.0
    assert np.hypot(printed[1], printed[2]) < 1.0
    assert axis["black"].sum() <= 3.0 + 1e-9
    # every accepted axis step prints neutral and the ramp never reverses
    ok = np.asarray(axis["ok"], bool)
    pr = p.lab_rel(np.asarray(axis["dev"])[ok])
    assert np.hypot(pr[:, 1], pr[:, 2]).max() < 1.5
    assert (np.diff(pr[:, 0]) < 0.05).all()       # light to dark


def test_a_walk_that_reaches_the_black_is_returned_unchanged():
    # A smooth CMYK model: the walk already ends at the deepest neutral,
    # so the axis (and with it every Maximum accuracy build on such a
    # printer) is exactly the walk's.
    x3 = build_printers()["X3"]
    ax1 = np.linspace(0.0, 1.0, 5)
    dev = np.stack(np.meshgrid(*[ax1] * 4, indexing="ij"), -1).reshape(-1, 4)
    model = ForwardModel(grid=5, n_channels=4, nodes=x3.lab_rel(dev),
                         curves=np.tile(np.linspace(0.0, 1.0, 21), (4, 1)))
    kw = dict(_KW, black_l=5.0)
    walk = b2a.neutral_axis(model, deep_black=False, **kw)
    axis = b2a.neutral_axis(model, **kw)
    assert "deep_black" not in axis
    assert axis["l_black"] == walk["l_black"]
    np.testing.assert_array_equal(axis["dev"], walk["dev"])

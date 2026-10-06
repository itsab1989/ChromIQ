"""Agent 29b (research token ``a29-oog-darkmono``): the a25-oog relative
colorimetric clip may not aim below the black the colorimetric table's
neutral column ends at, and in a band above that black it keeps lightness
before chroma (Findings agent29b-01, cluster 2 of agent27-01 s6.3).

Measured on the integrated engine (c2546c48, R-SWOP2006C3): the sRGB
magenta-to-black ramp printed L* 7.9 near its end (a tinted point darker
than the neutral black, L* 10.7) and then turned 3 L* lighter again into
the black. The synthetic printer below has the same shape: a deep blue that
is darker than its own device black.
"""
from __future__ import annotations

import threading

import numpy as np
import pytest

from tests.test_engine_oog_clip_a25 import _srgb_lab
from workflow.profile_engine import b2a, oog_clip
from workflow.profile_engine.builder import (ENGINE_CANDIDATE_TOKENS,
                                             candidates_from_env)
from workflow.profile_engine.forward_model import ForwardModel


def _tinted_black_printer(grid: int = 9) -> ForwardModel:
    """RGB printer (gamut inside sRGB, black at L* 13) whose deep blues are
    up to 2.4 L* darker than the device black, as a CMYK printer's
    blue-black is darker than its neutral black."""
    ax = np.linspace(0.0, 1.0, grid)
    dev = np.stack(np.meshgrid(ax, ax, ax, indexing="ij"), -1).reshape(-1, 3)
    ok = oog_clip.lab_to_oklab(_srgb_lab(dev))
    ok[:, 0] = 25.0 + ok[:, 0] * 0.75
    ok[:, 1:] *= 0.55 + 0.1 * (ok[:, :1] / 100.0)
    r, g, b = dev.T
    ok[:, 0] -= 100.0 * b * (1 - b) ** 2 * (1 - r) * (1 - g)
    lab = oog_clip.oklab_to_lab(ok)
    curves = np.tile(np.linspace(0.0, 1.0, 64), (3, 1))
    return ForwardModel(grid=grid, n_channels=3, nodes=lab, curves=curves)


@pytest.fixture(autouse=True)
def _tokens_off():
    yield
    b2a.set_research_tokens((), is_additive=None)


def _invert(model, lab, tokens, floor=None):
    b2a.set_research_tokens(tokens, is_additive=True)
    oog_clip.set_dark_floor(floor)
    d, r = b2a.invert_to_device(model, lab, channel_letters=["R", "G", "B"],
                                is_additive=True, accurate=True)
    b2a.set_research_tokens((), is_additive=True)
    return d, r


def _swing(lightness: np.ndarray) -> float:
    """Largest rise after the running minimum along a ramp into black (the
    battery's l_swing, hunt.ramp_props)."""
    return float((lightness - np.minimum.accumulate(lightness)).max())


def test_the_tokens_are_known_and_switch_on_and_off():
    assert {"a29-oog-darkmono", "a29-oog-darkmono-bpc"} <= ENGINE_CANDIDATE_TOKENS
    assert candidates_from_env("a29-oog-darkmono") == {"a29-oog-darkmono"}
    b2a.set_research_tokens(("a25-oog", "a29-oog-darkmono"), is_additive=False)
    assert oog_clip.PARAMS["dm_on"] and oog_clip.PARAMS["dm_band"] == 0.0
    oog_clip.set_dark_floor(10.0)
    assert oog_clip.dark_floor() == 10.0
    b2a.set_research_tokens(("a25-oog", "a29-oog-darkmono-bpc"), is_additive=False)
    assert oog_clip.PARAMS["dm_band"] == 15.0
    assert oog_clip.dark_floor() is None          # every build sets its own
    b2a.set_research_tokens((), is_additive=False)
    assert oog_clip.PARAMS == oog_clip.DEFAULTS
    oog_clip.set_dark_floor(10.0)
    assert oog_clip.dark_floor() is None          # token off: no floor


def test_the_target_map_is_monotone_and_never_below_the_black():
    lt = np.linspace(-1.0, 60.0, 611)
    for band in (0.0, 15.0):
        m = oog_clip.dark_target_l(lt, 10.0, band)
        assert (np.diff(m) >= -1e-12).all()
        assert m.min() >= 10.0 - 1e-12
        top = lt >= 10.0 + band
        assert np.array_equal(m[top], lt[top])


def test_the_floor_belongs_to_the_thread_that_builds_the_colorimetric_table():
    b2a.set_research_tokens(("a25-oog", "a29-oog-darkmono"), is_additive=True)
    oog_clip.set_dark_floor(12.0)
    seen = []
    t = threading.Thread(target=lambda: seen.append(oog_clip.dark_floor()))
    t.start()
    t.join()
    assert seen == [None] and oog_clip.dark_floor() == 12.0


def test_a_ramp_into_black_no_longer_turns_lighter():
    model = _tinted_black_printer()
    black = float(model.predict(np.zeros((1, 3)))[0, 0])
    t = np.linspace(0.0, 1.0, 64)[:, None]
    src = _srgb_lab(np.array([0.0, 0.0, 1.0]) * (1.0 - t))
    d0, _ = _invert(model, src, ("a25-oog",))
    d1, _ = _invert(model, src, ("a25-oog", "a29-oog-darkmono"), black)
    l0 = model.predict(d0)[:, 0]
    l1 = model.predict(d1)[:, 0]
    # measured: a25-oog alone 1.29 L* (darker than the black, then back up)
    assert _swing(l0) > 1.0 and l0.min() < black - 1.0
    assert _swing(l1) < 0.5
    assert l1.min() >= black - 0.05


def test_nodes_away_from_the_black_keep_their_values():
    model = _tinted_black_printer()
    black = float(model.predict(np.zeros((1, 3)))[0, 0])
    rng = np.random.default_rng(29)
    lab = np.column_stack([rng.uniform(0.0, 100.0, 600),
                           rng.uniform(-90.0, 90.0, 600),
                           rng.uniform(-90.0, 90.0, 600)])
    d0, r0 = _invert(model, lab, ("a25-oog",))
    d1, r1 = _invert(model, lab, ("a25-oog", "a29-oog-darkmono"), black)
    away = (lab[:, 0] >= black + oog_clip.DEFAULTS["dm_lband"]) | (r0 < 0.5)
    assert away.sum() > 400
    assert np.array_equal(d0[away], d1[away])
    assert np.array_equal(r0, r1)          # gamt keeps the nearest-clip distance


def test_without_a_floor_the_token_changes_nothing():
    model = _tinted_black_printer()
    t = np.linspace(0.0, 1.0, 32)[:, None]
    src = _srgb_lab(np.array([1.0, 0.0, 1.0]) * (1.0 - t))
    d0, _ = _invert(model, src, ("a25-oog",))
    d1, _ = _invert(model, src, ("a25-oog", "a29-oog-darkmono"), None)
    assert np.array_equal(d0, d1)

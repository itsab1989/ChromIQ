"""Agent 25 (research tokens ``a25-oog``): the colorimetric out-of-gamut clip
is one continuous weighted nearest clip (Findings agent25-01, F-15, F-17).

Every test runs the integration-2 clip (tokens off) and the candidate on the
same synthetic printer model and states what was measured on the old code:
the old clip FAILS the F-15 / F-17 checks, the candidate passes them, and
in-gamut nodes keep their bytes.
"""
from __future__ import annotations

import numpy as np
import pytest

from workflow.profile_engine import b2a, oog_clip
from workflow.profile_engine.forward_model import ForwardModel
from workflow.profile_engine.ti3_data import xyz_to_lab


def _srgb_lab(rgb: np.ndarray) -> np.ndarray:
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4360747, 0.3850649, 0.1430804],
                  [0.2225045, 0.7168786, 0.0606169],
                  [0.0139322, 0.0971045, 0.7141733]])     # D50-adapted sRGB
    return xyz_to_lab(lin @ m.T * 100.0)


def _rgb_printer(grid: int = 9) -> ForwardModel:
    """An RGB 'inkjet' with a gamut well inside sRGB: device white = paper,
    a black at Oklab L 0.25, colourfulness 55-65 % of sRGB's at the SAME
    PERCEIVED hue (scaled in Oklab), so sRGB primaries are far outside and
    holding CIELAB hue while clipping them moves the perceived hue."""
    ax = np.linspace(0.0, 1.0, grid)
    dev = np.stack(np.meshgrid(ax, ax, ax, indexing="ij"), -1).reshape(-1, 3)
    ok = oog_clip.lab_to_oklab(_srgb_lab(dev))
    ok[:, 0] = 25.0 + ok[:, 0] * 0.75
    ok[:, 1:] *= 0.55 + 0.1 * (ok[:, :1] / 100.0)
    lab = oog_clip.oklab_to_lab(ok)
    curves = np.tile(np.linspace(0.0, 1.0, 64), (3, 1))
    return ForwardModel(grid=grid, n_channels=3, nodes=lab, curves=curves)


@pytest.fixture(autouse=True)
def _tokens_off():
    yield
    b2a.set_research_tokens((), is_additive=None)


def _invert(model, lab, tokens):
    b2a.set_research_tokens(tokens, is_additive=True)
    d, r = b2a.invert_to_device(model, lab, channel_letters=["R", "G", "B"],
                                is_additive=True, accurate=True)
    b2a.set_research_tokens((), is_additive=True)
    return d, r


def test_tokens_off_leave_the_switches_off():
    b2a.set_research_tokens(("a25-oog",), is_additive=False)
    assert oog_clip.PARAMS["on"] and b2a.LIGHT_CLOUD["on"]
    b2a.set_research_tokens((), is_additive=False)
    assert not oog_clip.PARAMS["on"]
    assert not b2a.LIGHT_CLOUD["on"] and not b2a.CLIP_FIX["on"]
    assert oog_clip.PARAMS == oog_clip.DEFAULTS


def test_rgb_keeps_its_light_cloud_off_unless_asked():
    b2a.set_research_tokens(("a25-oog",), is_additive=True)
    assert not b2a.LIGHT_CLOUD["on"]


def test_in_gamut_nodes_keep_their_values():
    model = _rgb_printer()
    rng = np.random.default_rng(3)
    lab = model.predict(rng.uniform(0.05, 0.95, (300, 3)))
    d0, r0 = _invert(model, lab, ())
    d1, r1 = _invert(model, lab, ("a25-oog",))
    inside = r0 < 0.5
    assert inside.mean() > 0.9
    assert np.array_equal(d0[inside], d1[inside])
    assert np.array_equal(r0, r1)          # gamt keeps the nearest-clip distance


def _ramp(a, b, n=81):
    return np.asarray(a, float) + np.linspace(0.0, 1.0, n)[:, None] * (
        np.asarray(b, float) - np.asarray(a, float))


@pytest.mark.parametrize("start,end", [
    ((80.0, 8.0, 0.0), (99.5, 8.0, 0.0)),             # pale tint (the L* 100
                                                      # node is the white pin)
    ((88.0, -80.0, 80.0), (100.0, 0.0, 0.0)),         # sRGB-like green to white
    ((30.0, 68.0, -112.0), (0.0, 0.0, 0.0)),          # sRGB blue to black
    ((54.0, 80.0, 70.0), (0.0, 0.0, 0.0)),            # sRGB red to black
])
def test_out_of_gamut_ramps_print_without_lightness_reversals(start, end):
    """F-15: printed L* must follow the ramp's L* (no step against it larger
    than 1 L*; the integration-2 clip reverses 9.4 L* on the blue ramp and
    fails the red one) and no step may jump more than 8x the median step.
    Per node, before the B2A refit smooths the field."""
    model = _rgb_printer()
    lab = _ramp(start, end)
    d, _ = _invert(model, lab, ("a25-oog",))
    pr = model.predict(d)
    sgn = np.sign(lab[-1, 0] - lab[0, 0])
    back = -sgn * np.diff(pr[:, 0])
    assert back.max() <= 1.0, back.max()
    step = np.linalg.norm(np.diff(pr, axis=0), axis=1)
    assert step.max() <= 8.0 * max(np.median(step), 0.05), step.max()


def test_pale_out_of_gamut_colours_keep_their_lightness():
    """F-15: pale targets just outside the gamut (L* 90-100, a few units of
    chroma, every hue) print within 6 L* of their own lightness (the old
    clip wrote raw cloud seeds 25 L* darker)."""
    model = _rgb_printer()
    h = np.radians(np.arange(0, 360, 15))
    lab = np.array([[L, c * np.cos(t), c * np.sin(t)] for L in (90.0, 95.0, 100.0)
                    for c in (8.0, 16.0, 24.0) for t in h])
    d, r = _invert(model, lab, ("a25-oog",))
    pr = model.predict(d)
    oog = r > 0.5
    assert oog.sum() > 50
    assert (lab[oog, 0] - pr[oog, 0]).max() <= 6.0


def test_saturated_blue_keeps_its_perceived_hue():
    """F-17: an sRGB-blue-like target far outside the gamut is clipped
    along Oklab's constant-hue line, so its IPT hue moves less than 6 deg
    (holding CIELAB hue turns it purple: measured +10 to +38 deg on the
    battery printers with the integration-2 clip)."""
    model = _rgb_printer()
    tgt = _srgb_lab(np.array([[0.0, 0.0, 1.0], [0.15, 0.15, 1.0]]))
    d, _ = _invert(model, tgt, ("a25-oog",))
    pr = model.predict(d)
    ipt_t = oog_clip.lab_to_ipt(tgt)
    ipt_p = oog_clip.lab_to_ipt(pr)
    dh = np.degrees(np.arctan2(ipt_p[:, 2], ipt_p[:, 1])
                    - np.arctan2(ipt_t[:, 2], ipt_t[:, 1]))
    dh = (dh + 180.0) % 360.0 - 180.0
    assert np.abs(dh).max() < 6.0, dh


def test_lattice_neighbours_on_the_b2a_grid():
    from workflow.profile_engine.pcs import LabPcs
    nl = LabPcs.node_lab(5)
    nb = oog_clip._lattice_neighbours(nl)
    assert nb.shape == (125, 6)
    for i in (0, 31, 124):
        for j in nb[i][nb[i] >= 0]:
            assert np.count_nonzero(nl[i] != nl[j]) == 1
    assert oog_clip._lattice_neighbours(nl[::-1]) is None


def test_hue_line_angle_reduces_to_cielab_at_zero_chord():
    lab = np.array([[50.0, 30.0, -40.0], [70.0, -20.0, 50.0]])
    ang = oog_clip.hue_line_angle(lab, "oklab", 1e-9)
    own = np.arctan2(lab[:, 2], lab[:, 1])
    assert np.allclose(np.cos(ang - own), 1.0, atol=1e-3)

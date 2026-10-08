"""Agent 46 (2026-10-07): research token "a46-softcorner" (opt-in), D-29.

The relative colorimetric table stays exact in gamut except a narrow zone
just inside the gamut edge, where it eases off along the table's own clip
direction with a C1 knee (b2a.py, comment above A46_TOKEN;
ProfileEngineResearch Findings/agent46-01-softcorner.md).

No file IO here or in the token code.
"""
import inspect

import numpy as np

from workflow.profile_engine import b2a, builder
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates)

G = 17
_M = np.array([[0.3 * 70, 0.5 * 70, 0.2 * 70],
               [80.0, -80.0, 0.0],
               [0.0, 80.0, -80.0]])
_O = np.array([25.0, 0.0, 0.0])
_MI = np.linalg.inv(_M)


class _ToyRgb:
    """A linear RGB printer (identity shaper curves); its gamut is a
    parallelepiped whose faces are the planes R, G or B = 0 or 1."""

    n_channels = 3

    def __init__(self):
        self.curves = np.tile(np.linspace(0.0, 1.0, 21), (3, 1))

    def predict(self, d):
        return _O[None, :] + np.atleast_2d(np.asarray(d, float)) @ _M.T

    def shape_device(self, d):
        return np.asarray(d, float).copy()

    def unshape_device(self, d):
        return np.asarray(d, float).copy()


def _dev(lab):
    return (np.atleast_2d(lab) - _O[None, :]) @ _MI.T


def _true_depth(lab):
    """Euclidean distance to the nearest face plane (positive inside)."""
    d = _dev(lab)
    scale = np.linalg.norm(_MI, axis=1)[None, :]
    return (np.minimum(d, 1.0 - d) / scale).min(1)


def _inside(points, _idx):
    d = _dev(points)
    return np.all((d >= -1e-9) & (d <= 1 + 1e-9), axis=1)


def _table(model):
    node_lab = b2a.lab_grid(G)
    exact = _dev(node_lab)
    ing = np.all((exact >= 0) & (exact <= 1), axis=1)
    per = exact.copy()
    # the out-of-gamut nodes: the nearest point of the gamut (projected
    # gradient on the device cube; the linear model makes this exact enough)
    out = np.flatnonzero(~ing)
    x = np.clip(exact[out], 0, 1)
    h = np.linalg.inv(_M.T @ _M)
    for _ in range(400):
        r = model.predict(x) - node_lab[out]
        x = np.clip(x - 0.5 * (r @ _M) @ h.T * 0.2, 0, 1)
    per[out] = x
    return node_lab, per, ing


def test_the_token_is_known_and_not_a_default():
    assert b2a.A46_TOKEN == "a46-softcorner"
    assert b2a.A46_TOKEN in ENGINE_CANDIDATE_TOKENS
    assert b2a.A46_TOKEN not in ACCURATE_DEFAULT_TOKENS
    assert b2a.A46_TOKEN not in accurate_candidates(frozenset())
    assert 0.0 < b2a.A46_WIDTH < 1.0


def test_the_knee_is_identity_deep_inside_and_c1_at_the_zone_edge():
    w = 4.0
    s = np.linspace(-20, -w, 50)
    assert np.array_equal(b2a.soft_knee(s, w), s)
    h = 1e-6
    left = (b2a.soft_knee(-w, w) - b2a.soft_knee(-w - h, w)) / h
    right = (b2a.soft_knee(-w + h, w) - b2a.soft_knee(-w, w)) / h
    assert abs(float(left) - 1.0) < 1e-4 and abs(float(right) - 1.0) < 1e-4
    left = (b2a.soft_knee(w, w) - b2a.soft_knee(w - h, w)) / h
    assert abs(float(left)) < 1e-4              # C1 into the clip at +w
    x = np.linspace(-w, w, 2000)
    g = b2a.soft_knee(x, w)
    assert np.all(np.diff(g) > 0)               # monotone: no reversal
    assert np.all(g <= 0) and np.all(g <= x)    # never beyond the edge
    assert abs(float(b2a.soft_knee(0.0, w)) + w / 4) < 1e-12
    far = np.linspace(w, 60, 50)
    assert np.array_equal(b2a.soft_knee(far, w), 0 * far)   # the clip itself
    # zero width: the hard clip, unchanged
    assert np.array_equal(b2a.soft_knee(x, 0.0), x)


def test_deep_in_gamut_nodes_are_left_exactly_alone():
    model = _ToyRgb()
    node_lab, per, ing = _table(model)
    prn = model.predict(per)
    tgt, ch, info = b2a.soft_corner_targets(node_lab, prn, ing, G, width=0.2,
                                            inside=_inside)
    assert ch.any() and (ch & ing).any() and (ch & ~ing).any()
    assert np.array_equal(tgt[~ch], node_lab[~ch])
    depth = _true_depth(node_lab)
    w, n = info["w"], info["n"]
    # every in-gamut node it moved lies less than its zone width from the
    # edge, measured along its own clip direction ...
    moved_in = np.flatnonzero(ch & ing)
    assert not _inside(node_lab[moved_in] + w[moved_in, None] * n[moved_in],
                       None).any()
    # ... and its measured depth is that distance (bisection, w / 64)
    for i in moved_in[:40]:
        t_hit = np.linspace(0, w[i], 2001)
        ok = _inside(node_lab[i] + t_hit[:, None] * n[i], None)
        assert abs(t_hit[ok].max() + info["s"][i]) <= w[i] / 64 + 1e-6
    # in-gamut nodes deeper than the widest zone anywhere are never moved
    wmax = 0.2 * np.hypot(prn[:, 1], prn[:, 2]).max()
    assert not (ch & ing & (depth > wmax + 1.0)).any()


def test_new_targets_are_printable_and_eased_inward():
    model = _ToyRgb()
    node_lab, per, ing = _table(model)
    prn = model.predict(per)
    tgt, ch, info = b2a.soft_corner_targets(node_lab, prn, ing, G, width=0.2,
                                            inside=_inside)
    d = _dev(tgt[ch])
    # in (or, at a vertex of the toy gamut, within 0.03 of) the gamut
    assert np.all((d >= -0.03) & (d <= 1.03))
    # in gamut: moved inward along the edge normal by less than 0.37 w
    i = np.flatnonzero(ch & ing)
    assert np.all(-info["s"][i] < info["w"][i])
    shift = np.linalg.norm(tgt[i] - node_lab[i], axis=1)
    assert np.all(shift <= 0.25 * info["w"][i] + 1e-9)


def test_soft_corner_keeps_untouched_and_pinned_nodes_byte_identical():
    model = _ToyRgb()
    node_lab, per, ing = _table(model)
    shaped = model.shape_device(per)
    pins = np.flatnonzero(ing)[:50]

    def invert(t, seed):
        return np.clip(_dev(t), 0, 1)
    out, info = b2a.soft_corner(model, shaped, node_lab, ingamut=ing,
                                grid=G, invert=invert, width=0.2,
                                keep_out=pins)
    _tgt, ch, _ = b2a.soft_corner_targets(node_lab, model.predict(per), ing,
                                          G, width=0.2, keep_out=pins,
                                          inside=_inside)
    assert info["taken"] > 0
    assert np.array_equal(out[~ch], shaped[~ch])
    assert np.array_equal(out[pins], shaped[pins])
    assert not ch[pins].any()


def test_a_non_uniform_grid_or_zero_width_is_skipped():
    model = _ToyRgb()
    node_lab, per, ing = _table(model)
    prn = model.predict(per)
    bent = node_lab.copy()
    bent[:, 0] = bent[:, 0] ** 1.1
    _t, ch, info = b2a.soft_corner_targets(bent, prn, ing, G, width=0.2)
    assert info["skipped"] == "grid" and not ch.any()
    _t, ch, info = b2a.soft_corner_targets(node_lab, prn, ing, G, width=0.0)
    assert not ch.any()


def test_the_builder_wires_it_after_a44b_and_before_the_ceiling():
    src = inspect.getsource(builder._build_profile_impl)
    i_tok = src.index("b2a_mod.A46_TOKEN in candidates")
    assert src.index("b2a_mod.smooth_exact(") < i_tok
    assert i_tok < src.index("top = model.shape_device(channel_max[None, :])")
    assert i_tok < src.index("b2a_mod.pin_white_node(")
    # colorimetric table only: the mapped (perceptual / saturation) tables
    # are built elsewhere and never read dev_clut_shaped
    assert "soft_corner" not in inspect.getsource(
        __import__("workflow.profile_engine.gamut_map",
                   fromlist=["x"]))


def test_the_field_solve_moves_only_the_moved_nodes():
    model = _ToyRgb()
    node_lab, per, ing = _table(model)
    shaped = model.shape_device(per)
    rng = np.random.default_rng(1)
    free = np.zeros(len(shaped), bool)
    free[rng.choice(len(shaped), 300, replace=False)] = True
    want = model.predict(shaped) + 0.5 * free[:, None]
    out = b2a._smooth_moved(model, shaped, want, free, G)
    assert np.array_equal(out[~free], shaped[~free])
    assert np.abs(out[free] - shaped[free]).max() > 0


def test_local_moves_stay_on_their_branch_and_reach_close_targets():
    model = _ToyRgb()
    node_lab, per, ing = _table(model)
    i = np.flatnonzero(ing)[:200]
    s0 = model.shape_device(per[i])
    want = model.predict(s0) + np.array([0.0, -1.0, 0.5])
    s1 = b2a._move_prints(model, s0, want)
    err = np.linalg.norm(model.predict(s1) - want, axis=1)
    inside = np.all((_dev(want) >= 0) & (_dev(want) <= 1), axis=1)
    assert np.all(err[inside] < 1e-3)
    assert np.abs(s1 - s0).max() < 0.05


# --- a46b-cuspclip ---------------------------------------------------------

def test_the_cusp_token_is_known_and_not_a_default():
    assert b2a.A46B_TOKEN == "a46b-cuspclip"
    assert b2a.A46B_TOKEN in ENGINE_CANDIDATE_TOKENS
    assert b2a.A46B_TOKEN not in ACCURATE_DEFAULT_TOKENS
    assert b2a.A46B_WIDTH == 0.20


def test_cusp_lightness_finds_each_hues_most_colourful_l():
    h = np.radians(np.arange(0, 360, 1.0))
    lab = []
    for L, c in ((30.0, 20.0), (60.0, 50.0), (85.0, 10.0)):
        lab.append(np.stack([np.full_like(h, L), c * np.cos(h), c * np.sin(h)], 1))
    cl = b2a.cusp_lightness(np.vstack(lab))
    assert np.allclose(cl, 60.0)


def test_cusp_clip_keeps_hue_aims_at_the_cusp_and_leaves_in_gamut_alone():
    model = _ToyRgb()
    node_lab, per, ing = _table(model)
    prn = model.predict(per)
    cl = np.full(180, 55.0)
    tgt, ch = b2a.cusp_clip_targets(node_lab, prn, ing, cl, _inside)
    assert ch.any() and not (ch & ing).any()
    assert np.array_equal(tgt[~ch], prn[~ch])
    i = np.flatnonzero(ch & (np.hypot(node_lab[:, 1], node_lab[:, 2]) >= 15))
    t, p = node_lab[i], tgt[i]
    # on the line from T to (55, 0, 0): same hue, and printable (on the edge)
    ht = np.degrees(np.arctan2(t[:, 2], t[:, 1]))
    hp = np.degrees(np.arctan2(p[:, 2], p[:, 1]))
    assert np.abs((hp - ht + 180) % 360 - 180).max() < 1e-6
    e = np.stack([np.full(len(i), 55.0), 0 * i, 0 * i], 1)
    lam = np.linalg.norm(p - t, axis=1) / np.linalg.norm(e - t, axis=1)
    assert np.allclose(t + lam[:, None] * (e - t), p, atol=1e-6)
    d = _dev(p)
    assert np.all((d >= -0.01) & (d <= 1.01))


def test_the_builder_runs_the_cusp_clip_before_the_knee():
    src = inspect.getsource(builder._build_profile_impl)
    i_cc = src.index("b2a_mod.cusp_clip(")
    assert src.index("b2a_mod.smooth_exact(") < i_cc < src.index("b2a_mod.soft_corner(")


# --- a46c-cuspclip-ipt -----------------------------------------------------

def test_a46c_token_known_not_default_and_wired():
    assert b2a.A46C_TOKEN == "a46c-cuspclip-ipt"
    assert b2a.A46C_TOKEN in ENGINE_CANDIDATE_TOKENS
    assert b2a.A46C_TOKEN not in ACCURATE_DEFAULT_TOKENS
    src = inspect.getsource(builder._build_profile_impl)
    assert '"space": "ipt"' in src and "b2a_mod.A46C_BAND" in src


def test_a46c_keeps_ipt_hue_and_leaves_colours_above_the_cusp_alone():
    from workflow.profile_engine.oog_clip import ipt_to_lab, lab_to_ipt
    model = _ToyRgb()
    node_lab, per, ing = _table(model)
    prn = model.predict(per)
    cl = np.full(180, 45.0)                 # IPT I of every hue's cusp
    tgt, ch = b2a.cusp_clip_targets(node_lab, prn, ing, cl, _inside,
                                    to_s=lab_to_ipt, from_s=ipt_to_lab,
                                    below_band=5.0)
    assert ch.any() and not (ch & ing).any()
    ti = lab_to_ipt(node_lab)
    assert not (ch & (ti[:, 0] >= 45.0)).any()          # above the cusp: kept
    assert np.array_equal(tgt[~ch], prn[~ch])
    full = ch & (ti[:, 0] <= 40.0) & (np.hypot(node_lab[:, 1], node_lab[:, 2]) >= 15)
    i = np.flatnonzero(full)
    assert len(i)
    pi = lab_to_ipt(tgt[i])
    h1 = np.degrees(np.arctan2(ti[i, 2], ti[i, 1]))
    h2 = np.degrees(np.arctan2(pi[:, 2], pi[:, 1]))
    assert np.abs((h2 - h1 + 180) % 360 - 180).max() < 1e-6   # IPT hue kept

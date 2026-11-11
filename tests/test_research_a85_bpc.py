"""Research Agent 85: the BPC wedge metric (benchmarks/research/bpcq.py, Adobe / Little CMS master black point)
and the a85-bpcblack token (RGB rel. col. neutral column below the darkest printable neutral re-solved in
CIELAB, gated on a tinted device black)."""
import os

import numpy as np
import pytest

from benchmarks.research import bpcq
from workflow.profile_engine import builder, purecolprof as P
from workflow.profile_engine import icc_writer as icw


class Toy:
    """RGB printer, device 0..1 (1 = white): black L* 4 with a* 2.2, b* -3.4 fading out by L* 12."""
    n_channels = 3

    def predict(self, d):
        d = np.atleast_2d(np.asarray(d, float))
        m = d.mean(1)
        L = 4.0 + 96.0 * m ** 0.8
        f = np.clip(1.0 - (L - 4.0) / 8.0, 0.0, 1.0) * self.tint
        a = 2.2 * f + 30 * (d[:, 0] - d[:, 1])
        b = -3.4 * f + 30 * (d[:, 1] - d[:, 2])
        return np.stack([L, a, b], 1)

    def __init__(self, tint=1.0):
        self.tint = tint


def _toy_profile(path, model):
    g = 9
    ax = np.linspace(0, 1, g)
    dev = np.stack(np.meshgrid(ax, ax, ax, indexing="ij"), -1).reshape(-1, 3)
    a2b = icw.make_mft2(3, 3, g, icw.lab_to_u16(model.predict(dev)))
    gb = 17
    Lax, abax = icw.lab_grid_axes(gb)
    nl = np.stack(np.meshgrid(Lax, abax, abax, indexing="ij"), -1).reshape(-1, 3)
    cax = np.linspace(0, 1, 41)
    cloud = np.stack(np.meshgrid(cax, cax, cax, indexing="ij"), -1).reshape(-1, 3)
    cl = model.predict(cloud)
    idx = [int(np.argmin(((cl - t) ** 2).sum(1))) for t in nl]
    b2a = icw.make_mft2(3, 3, gb, icw.device_to_u16(cloud[idx]), in_tables=icw.lab_b2a_in_tables(256))
    spec = icw.ProfileSpec(n_channels=3, description="toy", color_rep="RGB")
    path.write_bytes(icw.assemble_profile(spec, {"A2B0": a2b, "A2B1": "A2B0", "A2B2": "A2B0", "B2A0": b2a,
                                                 "B2A1": "B2A0", "B2A2": "B2A0"}))
    return path


def test_quadratic_root_is_little_cms_s():
    x = np.linspace(5, 30, 40)
    y = 0.001 * (x - 3.0) * (x + 50.0)
    c, b, a = np.polynomial.polynomial.polyfit(x, y, 2)
    assert bpcq._quad_root(x, y) == pytest.approx((-b + np.sqrt(b * b - 4 * a * c)) / (2 * a), abs=1e-6)
    assert bpcq._quad_root(x[:3], y[:3]) == 0.0


def test_bpc_targets_map_black_to_the_black_point_and_keep_white():
    t = bpcq.bpc_targets(4.1, np.array([0.0, 1.0, 5.0, 100.0]))
    assert t[0, 0] == pytest.approx(4.1, abs=1e-9)
    assert t[-1, 0] == pytest.approx(100.0, abs=1e-6)
    assert np.all(np.diff(t[:, 0]) > 0) and np.abs(t[:, 1:]).max() < 1e-9


def test_black_point_and_wedge_on_a_toy_profile(tmp_path):
    icc = str(_toy_profile(tmp_path / "toy.icc", Toy()))
    bp, how = bpcq.destination_black_point(icc, "r")
    assert bp == pytest.approx(4.0, abs=0.05) and "darkest colorant" in how   # RGB 0, made neutral
    res = bpcq.evaluate(icc, {"truth": lambda d: Toy().predict(d)})
    for it in ("r", "p"):
        for ref in ("truth", "own"):
            r = res[it][ref]
            assert set(r) >= {"bp_L", "black_L", "lift", "sep_min", "sep_ratio", "wedge_de", "printed_L"}
            assert len(r["printed_L"]) == len(bpcq.WEDGE_L)
    q = bpcq.q_rows(res, "truth")
    assert set(q) == set(bpcq.KEYS)
    if os.environ.get("CHROMIQ_LCMS_MASTER"):
        c = res["cmm_check"]["r"]
        assert c["bp_L_diff"] < 1e-6 and c["device_max_diff"] < 1e-6


def test_a85_is_registered_and_off_by_default():
    assert P.A85_TOKEN in builder.ENGINE_CANDIDATE_TOKENS
    assert P.A85_TOKEN not in builder.ACCURATE_DEFAULT_TOKENS
    assert P.a85_params(builder.ACCURATE_DEFAULT_TOKENS) is None
    assert P.a85_params({P.A85_TOKEN})["gap"] == P.A85["gap"]


def _column_case(model):
    g = 33
    Lax, abax = icw.lab_grid_axes(g)
    nl = np.stack(np.meshgrid(Lax, abax, abax, indexing="ij"), -1).reshape(-1, 3)
    # a CAM-clip-like plateau: every dark node prints the toy's darkest neutral (device 0.06 grey)
    tab = np.full((len(nl), 3), 0.06)
    lit = nl[:, 0] > 12
    tab[lit] = np.clip(((nl[lit, 0] - 4) / 96) ** 1.25, 0, 1)[:, None]
    res = np.where(nl[:, 0] < 12, 3.0, 0.0)
    tables = np.tile(icw._identity_table(256), (3, 1))
    return nl, tab, res, tables


def test_a85_fires_on_a_tinted_black_and_moves_only_the_dark_clipped_column():
    m = Toy()
    nl, tab, res, tables = _column_case(m)
    p = P.a85_params({P.A85_TOKEN})
    out, info = P.a85_bpcblack(tab, nl, res, m, p, tables)
    assert info["fires"] and info["gap"] >= p["gap"] and info["nodes"] > 0
    col = np.hypot(nl[:, 1], nl[:, 2]) < 0.5
    moved = np.abs(out - tab).max(1) > 1e-9
    assert moved[col & (nl[:, 0] < info["neutral_l"])].all()
    assert not moved[~col].any() and not moved[res <= 0.5].any()
    # the node at the black point now prints darker than the plateau
    k = int(np.flatnonzero(col & (np.abs(nl[:, 0] - nl[col][1, 0]) < 1e-9))[0])
    assert m.predict(out[k])[0, 0] < m.predict(tab[k])[0, 0] - 0.5


def test_a85_does_not_fire_on_a_neutral_black():
    m = Toy(tint=0.0)
    nl, tab, res, tables = _column_case(m)
    out, info = P.a85_bpcblack(tab, nl, res, m, P.a85_params({P.A85_TOKEN}), tables)
    assert not info["fires"] and out is tab or np.array_equal(out, tab)

"""Agent 63 research token a63-palefine on a58 keep-grid33in: off by default, the pale keep counts down from the
printer's white, and it only ever moves a node toward the fine table."""
import numpy as np

from workflow.profile_engine import purecolprof as p


def _lab(g=33):
    from workflow.profile_engine.icc_writer import lab_grid_axes
    la, ab = lab_grid_axes(g)
    L, A, B = np.meshgrid(la, ab, ab, indexing="ij")
    return np.stack([L.ravel(), A.ravel(), B.ravel()], axis=1)


def _clear(monkeypatch):
    for e in ("CHROMIQ_A63_L", "CHROMIQ_A63_W", "CHROMIQ_A63_C"):
        monkeypatch.delenv(e, raising=False)


def test_token_off_is_none():
    assert p.a63_pale([], _lab()) is None
    assert p.a63_pale(["a60-darkacc"], _lab()) is None


def test_keep_counts_down_from_the_white(monkeypatch):
    _clear(monkeypatch)
    lab = _lab()
    keep, band = p.a63_pale(["a63-palefine"], lab, white_l=100.0)
    assert band == p.A63_C
    top = 100.0 - p.A63_L
    assert np.all(keep[lab[:, 0] >= top] == 1.0)
    assert np.all(keep[lab[:, 0] <= top - p.A63_W] == 0.0)
    assert np.all(np.diff(keep.reshape(33, 33, 33)[:, 5, 5]) >= 0)
    keep2, _ = p.a63_pale(["a63-palefine"], lab, white_l=95.0)
    assert np.all(keep2[lab[:, 0] >= 85.0] == 1.0) and np.all(keep2[lab[:, 0] <= 75.0] == 0.0)


def test_pale_nodes_keep_the_fine_table(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("CHROMIQ_A63_C", "none")
    g_f, g_c = 33, 17
    lab = _lab(g_f)
    fine = np.zeros((g_f ** 3, 3))
    coarse = np.ones((g_c ** 3, 3))
    res = np.full(g_f ** 3, 5.0)
    out = p.coarse_outside(fine, coarse, res, g_f, g_c, pale=p.a63_pale(["a63-palefine"], lab))
    assert np.all(out[lab[:, 0] >= 90] == 0.0)
    assert np.allclose(out[lab[:, 0] <= 80], 1.0)


def test_pale_band_widens_and_never_narrows(monkeypatch):
    _clear(monkeypatch)
    g_f, g_c = 33, 17
    lab = _lab(g_f)
    fine = np.zeros((g_f ** 3, 3))
    coarse = np.ones((g_c ** 3, 3))
    res = np.full(g_f ** 3, 8.0)
    pale = p.a63_pale(["a63-palefine"], lab)
    out = p.coarse_outside(fine, coarse, res, g_f, g_c, pale=pale)
    assert np.allclose(out[lab[:, 0] >= 90], 0.5)        # smoothstep(8 / 16)
    ref = p.coarse_outside(fine, coarse, res, g_f, g_c)
    assert np.all(out <= ref + 1e-12)
    # with the dark keep on too, the wider band of the two wins
    dark = p.a60_dark(["a60-darkacc"], lab, black_l=20.0)
    both = p.coarse_outside(fine, coarse, res, g_f, g_c, dark=dark, pale=pale)
    only_dark = p.coarse_outside(fine, coarse, res, g_f, g_c, dark=dark)
    assert np.all(both <= only_dark + 1e-12)
    assert np.allclose(both[lab[:, 0] <= 30], only_dark[lab[:, 0] <= 30])


def test_not_a_default():
    from workflow.profile_engine import builder
    assert "a63-palefine" in builder.ENGINE_CANDIDATE_TOKENS
    assert "a63-palefine" not in builder.ACCURATE_DEFAULT_TOKENS
    assert "a63-lowgrid" in builder.ENGINE_CANDIDATE_TOKENS


def test_lowgrid_off_keeps_colprofs_grid(monkeypatch):
    monkeypatch.delenv("CHROMIQ_A63_LOWGRID", raising=False)
    assert p.a63_coarse_grid([], 9, 33) == 9
    assert p.a63_coarse_grid(["a63-palefine"], 9, 33) == 9


def test_lowgrid_never_below_17_and_inert_at_17(monkeypatch):
    monkeypatch.delenv("CHROMIQ_A63_LOWGRID", raising=False)
    assert p.a63_coarse_grid(["a63-lowgrid"], 9, 33) == 17
    assert p.a63_coarse_grid(["a63-lowgrid"], 17, 33) == 17
    assert p.a63_coarse_grid(["a63-lowgrid"], 33, 33) == 33
    assert not p.a63_lowoff(["a63-lowgrid"], 9)


def test_lowgrid_sweeps(monkeypatch):
    monkeypatch.setenv("CHROMIQ_A63_LOWGRID", "fine")
    assert p.a63_coarse_grid(["a63-lowgrid"], 9, 33) == 33
    monkeypatch.setenv("CHROMIQ_A63_LOWGRID", "off")
    assert p.a63_coarse_grid(["a63-lowgrid"], 9, 33) == 9
    assert p.a63_lowoff(["a63-lowgrid"], 9) and not p.a63_lowoff(["a63-lowgrid"], 17)

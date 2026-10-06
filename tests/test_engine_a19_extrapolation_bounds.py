"""F-12 (research agent 19): device-cube corners the chart never sampled must
not be predicted darker than anything physical (L* 0 with a wrong hue in
every engine mode before), and the guard must leave what the data say alone.

Token ``a19-extrap`` (Maximum accuracy only, off by default)."""
import numpy as np
import pytest

from workflow.profile_engine import extrap
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             accurate_candidates)
from workflow.profile_engine.forward_model import ForwardModel


def _corners(n):
    return np.stack(np.meshgrid(*([[0, 1]] * n), indexing="ij"),
                    -1).reshape(-1, n).astype(float)


def _linear_lab(dev):
    """A Lab-linear 'fit': what the curvature penalty's null space gives
    beyond the data. Each ink takes 30 L*; two or more full inks go below
    L* 0 (the F-12 shape)."""
    lab = np.zeros((len(dev), 3))
    lab[:, 0] = 100.0 - 30.0 * dev.sum(1) - 25.0 * dev[:, 0] * dev[:, 1]
    lab[:, 1] = 20.0 * dev[:, 0] - 15.0 * dev[:, 2]
    lab[:, 2] = -10.0 * dev[:, 1] + 25.0 * dev[:, 3]
    return lab


def _model(n=5, grid=5):
    g = extrap.grid_coords(grid, n)
    curves = np.tile(np.linspace(0, 1, 21), (n, 1))
    return ForwardModel(grid=grid, n_channels=n, nodes=_linear_lab(g),
                        curves=curves)


def _chart(n=5):
    """Paper, single-ink ramps and a few dark mixtures: no two-ink solid."""
    rows = [np.zeros(n)]
    for i in range(n):
        for v in (0.25, 0.5, 0.75, 1.0):
            d = np.zeros(n)
            d[i] = v
            rows.append(d)
    rng = np.random.default_rng(3)
    for _ in range(40):
        d = rng.uniform(0.0, 0.45, n)
        rows.append(d)
    dev = np.array(rows)
    lab = _linear_lab(dev)
    # a printed black: the darkest real patches are about L* 8
    dark = np.full((3, n), 0.45)
    dark_lab = np.tile([[8.0, 0.5, -0.5]], (3, 1))
    return np.vstack([dev, dark]), np.vstack([lab, dark_lab])


def test_token_is_registered_and_off_by_default():
    assert "a19-extrap" in ENGINE_CANDIDATE_TOKENS
    assert "a19-extrap" not in ACCURATE_DEFAULT_TOKENS
    assert "a19-extrap" not in accurate_candidates(())


def test_unsampled_corners_are_not_predicted_below_the_measured_black():
    m = _model()
    dev, lab = _chart()
    before = m.predict(_corners(5))
    assert (before[:, 0] < 1.0).any()          # the F-12 shape is there
    nodes, moved = extrap.bound_by_data(m, dev, lab)
    after = ForwardModel(grid=m.grid, n_channels=5, nodes=nodes,
                         curves=m.curves)
    black = np.sort(lab[:, 0])[0]
    assert moved.any()
    # F-12's test: no node and no corner below the measured black - 3
    assert nodes[:, 0].min() >= black - 3.0 - 1e-6
    assert after.predict(_corners(5))[:, 0].min() >= black - 3.0 - 1e-6
    # and no saturated hue on a lifted near-black node
    lifted = nodes[moved]
    assert np.hypot(lifted[:, 1], lifted[:, 2]).max() < 25.0


def test_a_node_is_not_darker_than_a_patch_with_all_its_ink_and_more():
    """APTEC (agent 14): C+M+O+G+V at 500 % printed L* 18.9; a training
    patch with the same inks plus K read L* 18.8; the fit said L* 0."""
    n, grid = 5, 5
    m = _model(n, grid)
    g = extrap.grid_coords(grid, n)
    target = np.array([1.0, 1.0, 1.0, 0.0, 0.0])
    k = int(np.flatnonzero(np.all(np.isclose(g, target), axis=1))[0])
    m.nodes[k] = [0.0, 30.0, -20.0]
    dev, lab = _chart()
    heavier = np.array([[1.0, 1.0, 1.0, 1.0, 0.0]])
    dev = np.vstack([dev, heavier])
    lab = np.vstack([lab, [[18.8, 2.0, 1.0]]])
    # the fitted model at the heavier patch agrees with its reading
    m.nodes[int(np.flatnonzero(np.all(np.isclose(
        g, heavier[0]), axis=1))[0])] = [18.8, 2.0, 1.0]
    nodes, moved = extrap.bound_by_data(m, dev, lab)
    assert moved[k]
    assert nodes[k, 0] >= 18.8 - 3.0 - 1e-6


def test_nodes_that_obey_are_left_bit_for_bit():
    n, grid = 4, 5
    g = extrap.grid_coords(grid, n)
    lab = np.zeros((len(g), 3))
    lab[:, 0] = 100.0 - 20.0 * g.sum(1)        # never below L* 20
    m = ForwardModel(grid=grid, n_channels=n, nodes=lab.copy(),
                     curves=np.tile(np.linspace(0, 1, 21), (n, 1)))
    dev = np.vstack([g[::7], np.ones((1, n))])   # the chart has its black
    nodes, moved = extrap.bound_by_data(m, dev, m.predict(dev))
    assert not moved.any()
    assert np.array_equal(nodes, lab)


def test_a_measured_node_is_not_moved_even_if_its_neighbour_is_lighter():
    """Trapping makes a real overprint lighter in one channel than an ink
    alone (X5 truth: C+K has more Z than K). The bound must not overrule a
    node the chart measured."""
    n, grid = 4, 5
    g = extrap.grid_coords(grid, n)
    lab = np.zeros((len(g), 3))
    lab[:, 0] = 100.0 - 20.0 * g.sum(1)
    k_solid = np.array([0.0, 0.0, 0.0, 1.0])
    k = int(np.flatnonzero(np.all(np.isclose(g, k_solid), axis=1))[0])
    lab[k] = [10.0, 0.0, 0.0]
    m = ForwardModel(grid=grid, n_channels=n, nodes=lab.copy(),
                     curves=np.tile(np.linspace(0, 1, 21), (n, 1)))
    dev = np.vstack([np.zeros(n), k_solid, [1.0, 0.0, 0.0, 1.0]])
    lab_p = np.array([[100.0, 0, 0], [10.0, 0, 0], [16.0, -5.0, -8.0]])
    m.nodes[int(np.flatnonzero(np.all(np.isclose(
        g, dev[2]), axis=1))[0])] = lab_p[2]
    nodes, moved = extrap.bound_by_data(m, dev, lab_p)
    assert not moved[k]
    assert np.array_equal(nodes[k], lab[k])


def _s6_chart(tmp_path, n_patches=500):
    from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
    p = PRINTERS["S6"]                  # 5 inks (CMYKV), YNSN truth
    chart = make_chart(p, n_patches)
    xyz, refl, _ = measure(p, chart)
    return p, write_ti3(tmp_path / "s6.ti3", p, chart, xyz, refl)


def _build(ti3, out, tokens):
    from workflow.profile_engine.builder import BuildSettings, build_profile
    from datetime import datetime
    s = BuildSettings(quality="l", gammap_mode="accurate",
                      timestamp=datetime(2026, 1, 1))
    s.engine_candidates = frozenset(tokens)
    return build_profile(ti3, out, s)


@pytest.mark.slow
def test_max_accuracy_build_with_the_token_bounds_every_corner(tmp_path):
    """F-12 at builder level: a 5-ink chart with no two-ink solid; with the
    token no corner of the A2B model is darker than the chart's black - 3,
    and the extrapolated corners are closer to the truth on average."""
    p, ti3 = _s6_chart(tmp_path)
    off = _build(ti3, tmp_path / "off.icc", ())
    on = _build(ti3, tmp_path / "on.icc", ("a19-extrap",))
    c = _corners(5)
    black = float(np.sort(on.measurement.lab_relative[:, 0])[1])
    l_on = on.model.predict(c)[:, 0]
    assert l_on.min() >= black - 3.0
    from workflow.profile_engine.metrics import delta_e_2000
    truth = p.lab_relative_true(c)
    d_off = delta_e_2000(off.model.predict(c), truth)
    d_on = delta_e_2000(on.model.predict(c), truth)
    assert np.median(d_on) <= np.median(d_off) + 0.05


@pytest.mark.slow
def test_token_changes_no_byte_on_an_rgb_chart(tmp_path):
    """Additive devices are left alone: same bytes with and without."""
    from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
    pr = PRINTERS["S1"]                 # RGB
    chart = make_chart(pr, 300)
    xyz, refl, _ = measure(pr, chart)
    ti3 = write_ti3(tmp_path / "rgb.ti3", pr, chart, xyz, refl)
    _build(ti3, tmp_path / "off.icc", ())
    _build(ti3, tmp_path / "on.icc", ("a19-extrap",))
    assert (tmp_path / "off.icc").read_bytes() == (tmp_path / "on.icc").read_bytes()


def test_order_penalty_leaves_additive_and_pairwise_structure_free():
    """The interaction-order penalty (order 3) annihilates every function
    of the form a + sum b_i x_i + sum c_ij x_i x_j (the structure a chart
    measures), and penalises a three-ink product (what no chart pins)."""
    n, grid = 5, 4
    g = extrap.grid_coords(grid, n)
    rng = np.random.default_rng(1)
    f = (1.0 + g @ rng.normal(size=n)
         + sum(rng.normal() * g[:, i] * g[:, j]
               for i in range(n) for j in range(i + 1, n)))[:, None]
    assert np.abs(extrap.interaction(f, grid, n, 3)).max() < 1e-9
    h = (g[:, 0] * g[:, 1] * g[:, 2])[:, None]
    assert (h * extrap.interaction(h, grid, n, 3)).sum() > 1e-6


def test_order_correction_at_zero_weight_is_the_fit_bit_for_bit():
    m = _model()
    dev, lab = _chart()
    out = extrap.resolve_with_order_penalty(m, dev, lab, 0.03, 0.0,
                                            delta=True)
    assert np.array_equal(out, m.nodes)


def test_order_correction_moves_an_unsupported_corner_not_the_measured_ramps():
    """F-12 shape: a corner far from every patch moves; the nodes on the
    measured single-ink ramps (next to patches, light) barely move."""
    m = _model()
    m.nodes[-1] = [-30.0, 40.0, -40.0]        # a wild unsupported corner
    dev, lab = _chart()
    out = extrap.resolve_with_order_penalty(
        m, dev, lab, 0.03, 0.01, local=(0.5, 1.0), ink_gate=(0.5, 1.5),
        delta=True)
    g = extrap.grid_coords(m.grid, 5)
    ramp = (g > 0).sum(1) <= 1
    assert np.abs(out[ramp] - m.nodes[ramp]).max() < 0.05
    assert np.abs(out[-1] - m.nodes[-1]).max() > 1.0

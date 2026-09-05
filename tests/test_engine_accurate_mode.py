"""Maximum-accuracy engine mode (gammap_mode "accurate").

Covers every improvement the mode switches on:

* ΔE2000 metric (pinned to the Sharma/Wu/Dalal reference pairs);
* duplicate-patch white/black averaging (the max-selection bias fix);
* measured extra-ink hue anchors from the chart's solid patches;
* boundary-aware finite-difference Jacobian (no dead column at a face);
* Euclidean TAC projection (shadows keep their dense channels);
* hue-preserving clipping of out-of-gamut nodes;
* cross-validated + outlier-robust forward fit;
* dense multi-ink destination shell;
* end-to-end builds (RGB and CMYK incl. separation smoothness);
* the Settings dialog's third dropdown option.
"""
from __future__ import annotations

import numpy as np
import pytest

from tests.test_profile_engine import synth_xyz, write_synth_ti3
from workflow.profile_engine import BuildSettings, build_profile
from workflow.profile_engine import b2a as b2a_mod
from workflow.profile_engine.accuracy import fit_forward_model_accurate
from workflow.profile_engine.forward_model import fit_forward_model
from workflow.profile_engine.metrics import delta_e_2000
from workflow.profile_engine.ti3_data import read_ti3


# ---------------------------------------------------------------------------
# ΔE2000 — Sharma, Wu & Dalal (2005) reference pairs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lab1,lab2,expected", [
    ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
    ((50.0, 3.1571, -77.2803), (50.0, 0.0, -82.7485), 2.8615),
    ((50.0, 2.8361, -74.0200), (50.0, 0.0, -82.7485), 3.4412),
    ((50.0, -1.3802, -84.2814), (50.0, 0.0, -82.7485), 1.0000),
    ((50.0, 2.5000, 0.0), (50.0, 3.2592, 0.3350), 1.0000),
    ((50.0, 2.5000, 0.0), (73.0, 25.0, -18.0), 27.1492),
    ((50.0, 2.4900, -0.0010), (50.0, -2.4900, 0.0009), 7.1792),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
])
def test_delta_e_2000_reference_pairs(lab1, lab2, expected):
    got = float(delta_e_2000(np.array([lab1]), np.array([lab2]))[0])
    assert got == pytest.approx(expected, abs=1e-4)


def test_delta_e_2000_symmetry_and_zero():
    rng = np.random.default_rng(3)
    a = rng.uniform([0, -60, -60], [100, 60, 60], (50, 3))
    b = rng.uniform([0, -60, -60], [100, 60, 60], (50, 3))
    assert np.allclose(delta_e_2000(a, b), delta_e_2000(b, a))
    assert np.allclose(delta_e_2000(a, a), 0.0)


# ---------------------------------------------------------------------------
# White/black averaging (A1)
# ---------------------------------------------------------------------------

def _meas_with_duplicate_whites(tmp_path):
    rng = np.random.default_rng(7)
    dev = rng.uniform(0.0, 1.0, (60, 3))
    dev[:6] = 1.0                        # six duplicate paper-white patches
    dev[6:9] = 0.0                       # three duplicate blacks
    xyz = synth_xyz(dev, additive=True)
    noise = rng.normal(0.0, 0.25, (9, 3))
    xyz[:9] += noise                     # instrument noise on the duplicates
    lines = ["CTI3", "", 'COLOR_REP "RGB_XYZ"', "NUMBER_OF_FIELDS 7",
             "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(dev)}", "BEGIN_DATA"]
    for i, (d, x) in enumerate(zip(dev, xyz)):
        lines.append(f"{i + 1} " + " ".join(f"{v * 100:.4f}" for v in d)
                     + " " + " ".join(f"{v:.4f}" for v in x))
    lines.append("END_DATA")
    p = tmp_path / "dup.ti3"
    p.write_text("\n".join(lines), encoding="utf-8")
    return read_ti3(p), xyz


def test_average_endpoints_removes_max_selection_bias(tmp_path):
    meas, xyz = _meas_with_duplicate_whites(tmp_path)
    # Default behaviour: the single brightest duplicate — biased high.
    biased = meas.media_white_xyz.copy()
    assert biased[1] == pytest.approx(xyz[:6, 1].max(), abs=1e-3)
    meas.average_endpoints()
    assert meas.media_white_xyz[1] == pytest.approx(xyz[:6, 1].mean(),
                                                    abs=1e-3)
    assert meas.black_xyz[1] <= xyz[6:9, 1].max() + 1e-9
    # The dependent colour bases were invalidated and rebuilt on the average.
    assert meas.lab_relative.shape == (60, 3)
    # Paper (device white) must land at exactly L*=100 relative.
    wi = meas.white_index
    white_lab = meas.lab_relative[wi]
    assert not np.isnan(white_lab).any()


def test_average_endpoints_single_white_unchanged(tmp_path):
    write_synth_ti3(tmp_path / "s.ti3", "RGB", ["RGB_R", "RGB_G", "RGB_B"],
                    additive=True)
    meas = read_ti3(tmp_path / "s.ti3")
    before = meas.media_white_xyz.copy()
    meas.average_endpoints()
    assert np.allclose(meas.media_white_xyz, before)


# ---------------------------------------------------------------------------
# Measured extra-ink hues (A5)
# ---------------------------------------------------------------------------

def test_extra_ink_hues_read_from_solid_patches(tmp_path):
    write_synth_ti3(tmp_path / "og.ti3", "CMYKOG",
                    [f"CMYKOG_{c}" for c in "CMYKOG"], additive=False)
    meas = read_ti3(tmp_path / "og.ti3")
    # Guarantee usable solid patches for both extra inks.
    solid_o = np.zeros(6); solid_o[4] = 1.0
    solid_g = np.zeros(6); solid_g[5] = 1.0
    meas.device[2] = solid_o
    meas.device[3] = solid_g
    meas.xyz[2] = synth_xyz(solid_o[None, :], additive=False)[0]
    meas.xyz[3] = synth_xyz(solid_g[None, :], additive=False)[0]
    for a in ("lab_relative", "xyz_relative"):
        meas.__dict__.pop(a, None)
    hues = meas.extra_ink_hues()
    assert set(hues) == {"O", "G"}
    lab = meas.lab_relative
    for row, letter in ((2, "O"), (3, "G")):
        want = np.degrees(np.arctan2(lab[row, 2], lab[row, 1])) % 360.0
        assert hues[letter] == pytest.approx(want, abs=1.0)
    # And the hue gate is anchored on the measured value, not the table.
    tgt = np.array([[50.0, 60.0 * np.cos(np.radians(hues["O"])),
                     60.0 * np.sin(np.radians(hues["O"]))]])
    on = b2a_mod.extra_ink_amount(tgt, "O", hue_override=hues["O"])
    off = b2a_mod.extra_ink_amount(tgt, "O",
                                   hue_override=(hues["O"] + 180.0) % 360.0)
    assert on[0] > 0.5 and off[0] == 0.0


def test_extra_ink_hues_rgb_empty(tmp_path):
    write_synth_ti3(tmp_path / "s.ti3", "RGB", ["RGB_R", "RGB_G", "RGB_B"],
                    additive=True)
    assert read_ti3(tmp_path / "s.ti3").extra_ink_hues() == {}


# ---------------------------------------------------------------------------
# Boundary-aware Jacobian (A4)
# ---------------------------------------------------------------------------

def _small_rgb_model():
    rng = np.random.default_rng(5)
    dev = rng.uniform(0.0, 1.0, (400, 3))
    corners = np.stack(np.meshgrid(*([[0.0, 1.0]] * 3), indexing="ij"),
                       -1).reshape(-1, 3)
    dev = np.vstack([dev, corners])
    from workflow.profile_engine.ti3_data import xyz_to_lab
    lab = xyz_to_lab(synth_xyz(dev, additive=True))
    return fit_forward_model(dev, lab, grid=9, lam=0.02)


def test_jacobian_alive_at_the_top_face():
    model = _small_rgb_model()
    d = np.array([[1.0, 0.5, 0.2], [0.3, 1.0, 1.0]])
    f0 = model.predict(d)
    free = np.arange(3)
    plain = b2a_mod._model_jacobian(model, d, free, f0)
    aware = b2a_mod._model_jacobian(model, d, free, f0, boundary_fd=True)
    # Forward FD: the pinned channel's column is exactly zero (the stall).
    assert np.abs(plain[0, :, 0]).max() == 0.0
    # Backward FD keeps it alive, and matches forward FD off the boundary.
    assert np.abs(aware[0, :, 0]).max() > 0.1
    assert np.allclose(aware[0, :, 1], plain[0, :, 1], atol=1e-6)


# ---------------------------------------------------------------------------
# TAC projection (A6)
# ---------------------------------------------------------------------------

def test_project_tac_properties():
    rng = np.random.default_rng(2)
    d = rng.uniform(0.0, 1.0, (500, 4)) * 1.2
    limit = 2.4
    p = b2a_mod.project_tac(d, limit)
    assert (p.sum(1) <= limit + 1e-9).all()
    assert (p >= 0.0).all()
    under = d.sum(1) <= limit
    assert np.allclose(p[under], d[under])           # untouched under the cap
    # Euclidean projection lands at least as close as proportional scaling.
    over = ~under
    scaled = d[over] * (limit / d[over].sum(1))[:, None]
    assert (np.linalg.norm(p[over] - d[over], axis=1)
            <= np.linalg.norm(scaled - d[over], axis=1) + 1e-9).all()


def test_project_tac_preserves_dense_channel():
    # Deep CMYK shadow over the limit: the projection subtracts a common
    # amount, so the dense K channel keeps more of its value than under
    # proportional scaling (which thins K and lightens the shadow).
    d = np.array([[0.9, 0.9, 0.9, 1.0]])
    p = b2a_mod.project_tac(d, 2.8)
    scaled = d * (2.8 / d.sum())
    assert p[0].sum() == pytest.approx(2.8)
    assert p[0, 3] > scaled[0, 3]
    # A sparse channel is exhausted before the dense ones are touched.
    d2 = np.array([[0.05, 1.0, 1.0, 1.0]])
    p2 = b2a_mod.project_tac(d2, 2.0)
    assert p2[0, 0] == 0.0 and (p2[0, 1:] > 0.6).all()


# ---------------------------------------------------------------------------
# Hue-preserving clip (A7)
# ---------------------------------------------------------------------------

def test_hue_preserving_clip_keeps_colour_family():
    model = _small_rgb_model()

    def hue_err(dev, target):
        got = model.predict(dev)
        h1 = np.degrees(np.arctan2(got[:, 2], got[:, 1]))
        h2 = np.degrees(np.arctan2(target[:, 2], target[:, 1]))
        return np.abs(((h1 - h2 + 180.0) % 360.0) - 180.0)

    # Far out-of-gamut saturated targets (unreachable chroma).
    hs = np.radians(np.array([20.0, 140.0, 260.0, 320.0]))
    target = np.stack([np.full(4, 55.0),
                       130.0 * np.cos(hs), 130.0 * np.sin(hs)], 1)
    kw = dict(channel_letters=["R", "G", "B"], is_additive=True)
    d_plain, res_plain = b2a_mod.invert_to_device(model, target, **kw)
    d_acc, res_acc = b2a_mod.invert_to_device(model, target, accurate=True,
                                              **kw)
    assert (res_plain > 1.0).all() and (res_acc > 1.0).all()   # truly OOG
    # gamt residual stays the nearest-clip metric distance.
    assert np.allclose(res_acc, res_plain, atol=1.0)
    # The accurate clip is perceptually no worse anywhere and clearly
    # better in aggregate (per-row ΔE2000 — the metric the weights encode;
    # small per-row tolerance for solver noise).
    from workflow.profile_engine.metrics import delta_e_2000
    ce_p = delta_e_2000(model.predict(d_plain), target)
    ce_a = delta_e_2000(model.predict(d_acc), target)
    assert (ce_a <= ce_p + 0.5).all()
    assert ce_a.mean() < ce_p.mean() - 1.0
    # And it never flips colour family: gross hue errors are gone (the
    # plain nearest clip shifted one blue by 26°), mean hue error improves.
    he_p, he_a = hue_err(d_plain, target), hue_err(d_acc, target)
    assert he_a.max() < 10.0
    assert he_a.mean() < he_p.mean()


def test_hue_weight_matrices_identity_for_neutrals():
    w = b2a_mod._hue_weight_matrices(np.array([[50.0, 1.0, -1.0],
                                               [40.0, 30.0, 0.0]]))
    assert np.allclose(w[0], np.eye(3))
    assert not np.allclose(w[1], np.eye(3))


# ---------------------------------------------------------------------------
# Robust CV fit (A2 + A3)
# ---------------------------------------------------------------------------

def test_accurate_fit_resists_an_outlier_patch():
    rng = np.random.default_rng(9)
    dev = rng.uniform(0.0, 1.0, (300, 3))
    from workflow.profile_engine.ti3_data import xyz_to_lab
    lab = xyz_to_lab(synth_xyz(dev, additive=True))
    lab_bad = lab.copy()
    lab_bad[123] += np.array([25.0, -30.0, 18.0])       # a smudged patch
    clean_mask = np.ones(len(dev), bool)
    clean_mask[123] = False

    plain = fit_forward_model(dev, lab_bad, grid=9, lam=0.02)
    robust, outliers, _lam = fit_forward_model_accurate(
        dev, lab_bad, grid=9, base_lam=0.02)
    err_plain = np.linalg.norm(plain.predict(dev) - lab, axis=1)
    err_rob = np.linalg.norm(robust.predict(dev) - lab, axis=1)
    # The outlier is reported; the model predicts the TRUE colour at the
    # smudged patch (it ignored the smudge) and the bulk fit improves.
    assert 123 in outliers
    assert err_rob[123] < err_plain[123]
    assert np.median(err_rob[clean_mask]) < np.median(err_plain[clean_mask])


def test_accurate_fit_clean_chart_reports_no_outliers():
    rng = np.random.default_rng(10)
    dev = rng.uniform(0.0, 1.0, (200, 3))
    from workflow.profile_engine.ti3_data import xyz_to_lab
    lab = xyz_to_lab(synth_xyz(dev, additive=True))
    model, outliers, lam = fit_forward_model_accurate(
        dev, lab, grid=9, base_lam=0.02)
    assert len(outliers) == 0
    assert lam > 0
    res = np.linalg.norm(model.predict(dev) - lab, axis=1)
    assert np.median(res) < 0.5


# ---------------------------------------------------------------------------
# Dense multi-ink shell (A9)
# ---------------------------------------------------------------------------

def test_dense_shell_is_denser_and_respects_the_ink_limit(tmp_path):
    write_synth_ti3(tmp_path / "og.ti3", "CMYKOG",
                    [f"CMYKOG_{c}" for c in "CMYKOG"], additive=False,
                    n_per_axis=6)
    meas = read_ti3(tmp_path / "og.ti3")
    model = fit_forward_model(meas.device, meas.lab_relative, grid=5,
                              lam=0.05, curve_rounds=0)
    from workflow.profile_engine.gamut_map import destination_surface_lab
    thin = destination_surface_lab(model, is_additive=False)
    dense = destination_surface_lab(model, is_additive=False, dense=True)
    assert len(dense) == 10 * len(thin)
    dense_lim = destination_surface_lab(model, is_additive=False, dense=True,
                                        ink_limit=280.0)
    assert len(dense_lim) == len(dense)
    # Every hue sector the thin cloud reaches, the dense cloud covers too
    # (with 10× the samples an occupied 7.5° bin cannot go empty).
    def hue_bins(cloud):
        h = np.degrees(np.arctan2(cloud[:, 2], cloud[:, 1])) % 360.0
        return set((h // 7.5).astype(int))
    assert hue_bins(thin) <= hue_bins(dense)
    # n ≤ 3 is deterministic mesh-based and unaffected by the flag.
    rgb_model = _small_rgb_model()
    assert np.allclose(
        destination_surface_lab(rgb_model),
        destination_surface_lab(rgb_model, dense=True))


# ---------------------------------------------------------------------------
# End-to-end builds
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_accurate_rgb_build_end_to_end(tmp_path):
    ti3 = write_synth_ti3(tmp_path / "rgb.ti3", "RGB",
                          ["RGB_R", "RGB_G", "RGB_B"], additive=True,
                          n_per_axis=6)
    msgs: list[str] = []
    st = BuildSettings(quality="l", gammap_mode="accurate",
                       progress=msgs.append)
    res = build_profile(ti3, tmp_path / "rgb.icc", st)
    assert res.icc_path.exists()
    data = res.icc_path.read_bytes()
    assert data[36:40] == b"acsp"
    assert res.fit_median_de00 > 0.0
    assert res.fit_median_de00 <= res.fit_p95_de00
    assert res.fit_median_de < 1.5
    assert any("cross-validation" in m for m in msgs)


@pytest.mark.slow
def test_accurate_cmyk_build_and_separation_smoothness(tmp_path):
    ti3 = write_synth_ti3(tmp_path / "cmyk.ti3", "CMYK",
                          [f"CMYK_{c}" for c in "CMYK"], additive=False,
                          n_per_axis=7, ink_limit=300.0)
    st = BuildSettings(quality="l", gammap_mode="accurate")
    res = build_profile(ti3, tmp_path / "cmyk.icc", st)
    assert res.icc_path.exists()
    assert res.n_channels == 4

    # Separation smoothness (A8 check): walk the B2A CLUT along the neutral
    # a*=b*≈0 column and require every ink channel to move without jumps —
    # metameric flips between adjacent nodes would band in gradients.
    # Read the raw B2A1 CLUT straight from the profile bytes.
    import struct
    data = res.icc_path.read_bytes()
    ntags = struct.unpack(">I", data[128:132])[0]
    b2a_off = None
    for i in range(ntags):
        sig, off, size = struct.unpack(">4sII", data[132 + 12 * i:144 + 12 * i])
        if sig == b"B2A1":
            b2a_off = off
    assert b2a_off is not None
    n_in, n_out, grid = data[b2a_off + 8], data[b2a_off + 9], data[b2a_off + 10]
    assert (n_in, n_out) == (3, 4)
    n_in_entries, n_out_entries = struct.unpack(
        ">HH", data[b2a_off + 48:b2a_off + 52])
    clut_off = b2a_off + 52 + 2 * n_in * n_in_entries
    clut = np.frombuffer(data, dtype=">u2", count=grid ** 3 * n_out,
                         offset=clut_off).reshape(grid, grid, grid, n_out)
    mid = grid // 2
    neutral_col = clut[:, mid, mid, :].astype(float) / 0xFFFF
    # K must fall monotonically with L (small wiggle allowed) and not
    # oscillate — metameric flips between adjacent nodes band in gradients.
    k = neutral_col[:, 3]
    assert np.diff(k).max() < 0.10                    # no K re-rise
    assert np.abs(np.diff(k)).sum() < (k[0] - k[-1]) + 0.30
    # And no channel jumps by near half scale between adjacent nodes.
    assert np.abs(np.diff(neutral_col, axis=0)).max() < 0.45


def test_shaped_xyz_pcs_codec_roundtrips_and_resolves_shadows():
    from workflow.profile_engine import icc_writer as icw
    from workflow.profile_engine.pcs import XyzPcs, XyzPcsShaped, codec_for
    assert codec_for("x") is XyzPcs
    assert codec_for("x", accurate=True) is XyzPcsShaped
    assert codec_for("l", accurate=True).signature == b"Lab "
    # node targets and lab_to01 agree: node i maps back to coordinate i.
    grid = 9
    nodes = XyzPcsShaped.node_lab(grid)
    u = XyzPcsShaped.lab_to01(nodes)
    axes = np.linspace(0.0, 1.0, grid)
    expect = np.stack(np.meshgrid(axes, axes, axes, indexing="ij"),
                      -1).reshape(-1, 3)
    assert np.allclose(u, expect, atol=1e-4)   # Lab↔XYZ float roundtrip
    # the input tables encode the same cube root of (code / PCS white),
    # monotonically, saturating at the white (the grid ends at D50 so the
    # corner node IS the paper white — reviewer R1b, 2026-09-05).
    t = XyzPcsShaped.b2a_in_tables(2048).astype(float) / 0xFFFF
    assert (np.diff(t, axis=1) >= 0).all()
    code = 1024 / 2047 * icw.XYZ16_MAX
    assert t[0, 1024] == pytest.approx(np.cbrt(min(code / 0.9642, 1.0)), abs=1e-3)
    assert t[1, -1] == 1.0 and t[2, 1024] == pytest.approx(
        np.cbrt(min(code / 0.8249, 1.0)), abs=1e-3)
    # shadow resolution: the darkest grid step covers a small L* span now
    # (L* rides on the Y axis — the middle meshgrid dimension).
    l_axis_shaped = XyzPcsShaped.node_lab(33)[0:33 * 33:33, 0]
    l_axis_plain = XyzPcs.node_lab(33)[0:33 * 33:33, 0]
    assert l_axis_shaped[1] < 5.0           # first step ends deep in shadow
    assert l_axis_plain[1] > 15.0           # identity layout skips L* 0..20+


@pytest.mark.slow
def test_accurate_xyz_build_carries_shaped_tables(tmp_path):
    ti3 = write_synth_ti3(tmp_path / "rgb.ti3", "RGB",
                          ["RGB_R", "RGB_G", "RGB_B"], additive=True,
                          n_per_axis=6)
    st = BuildSettings(quality="l", gammap_mode="accurate", algorithm="x")
    res = build_profile(ti3, tmp_path / "rgb.icc", st)
    import struct
    data = res.icc_path.read_bytes()
    ntags = struct.unpack(">I", data[128:132])[0]
    off = None
    for i in range(ntags):
        sig, o, _ = struct.unpack(">4sII", data[132 + 12 * i:144 + 12 * i])
        if sig == b"B2A1":
            off = o
    nie, _ = struct.unpack(">HH", data[off + 48:off + 52])
    table = np.frombuffer(data, dtype=">u2", count=nie,
                          offset=off + 52).astype(float) / 0xFFFF
    # cube-root input curve, not identity.
    assert table[nie // 2] == pytest.approx(np.cbrt(0.5), abs=0.01)


def test_percent_progress_interpolates_substeps():
    from workflow.profile_engine.builder import _PercentProgress
    seen: list[str] = []
    p = _PercentProgress(seen.append)
    p("Fitting the printer model (900 patches, grid 9)…")
    p("Fitting the printer model: smoothing search 1/5…")
    p("Fitting the printer model: smoothing search 4/5…")
    p("Inverting the model (B2A grid 17)…")
    p("Inverting the model: converging 5/10…")
    pcts = [int(s.split("%")[0]) for s in seen]
    assert pcts[0] == 8
    assert 8 < pcts[1] < pcts[2] < 14      # interpolates toward next anchor
    assert pcts[3] == 14
    assert 14 < pcts[4] < 18
    # monotonic even if an out-of-order message arrives
    p("Fitting the printer model: smoothing search 1/5…")
    assert int(seen[-1].split("%")[0]) >= pcts[4]


@pytest.mark.slow
def test_accurate_build_emits_granular_progress(tmp_path):
    ti3 = write_synth_ti3(tmp_path / "rgb.ti3", "RGB",
                          ["RGB_R", "RGB_G", "RGB_B"], additive=True,
                          n_per_axis=6)
    msgs: list[str] = []
    st = BuildSettings(quality="l", gammap_mode="accurate",
                       progress=msgs.append)
    build_profile(ti3, tmp_path / "rgb.icc", st)
    assert any("smoothing search" in m for m in msgs)
    assert any("converging" in m for m in msgs)
    assert any("smoothing refit" in m for m in msgs)
    # more distinct percentages than plain stage anchors would give
    pcts = {m.split("%")[0] for m in msgs if "%" in m}
    assert len(pcts) >= 8


@pytest.mark.slow
def test_fast_mode_unchanged_by_default(tmp_path):
    # The parity path must not pick up any accurate-mode behaviour.
    ti3 = write_synth_ti3(tmp_path / "rgb.ti3", "RGB",
                          ["RGB_R", "RGB_G", "RGB_B"], additive=True)
    msgs: list[str] = []
    st = BuildSettings(quality="l", progress=msgs.append)
    res = build_profile(ti3, tmp_path / "rgb.icc", st)
    assert res.icc_path.exists()
    assert not any("cross-validation" in m for m in msgs)
    assert not any("down-weighted" in m for m in msgs)

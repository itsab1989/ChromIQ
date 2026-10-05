"""Research agent17-01 item 2 / Findings F-09: the v4 container's perceptual
and saturation tables are referred to the perceptual reference medium
(ICC.1:2022 6.3.4.3, Table 16), the v2 file keeps its bytes.

Before: the v4 twin carried the v2 tables byte for byte. A v4 CMM (lcms:
for a v4 profile in the perceptual and saturation intents the PCS black IS
the PRM black, L* 3.1373, and black point compensation is forced) then
handed the mapped B2A0 an L* 3.14 black where it expects L* 0, and sRGB
black printed 2.6-2.9 L* lighter through the twin than through the v2 file
(agent 13, V1)."""
import io

import numpy as np
import pytest

from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
from workflow.profile_engine import icc_writer as icw
from workflow.profile_engine import v4_prm
from workflow.profile_engine.builder import BuildSettings, build_profile


def test_the_spec_equation():
    # ICC.1:2022 6.3.4.3: Xp = Xt (1 - Xb/Xi) + Xb, per channel
    xt = np.array([[0.0, 0.0, 0.0], [0.2, 0.3, 0.1], [0.9642, 1.0, 0.8249]])
    got = v4_prm.scale_black(xt, np.zeros(3), v4_prm.PRM_BLACK)
    want = xt * (1 - v4_prm.PRM_BLACK / v4_prm.PCS_WHITE) + v4_prm.PRM_BLACK
    np.testing.assert_allclose(got, want, atol=1e-12)
    np.testing.assert_allclose(got[0], v4_prm.PRM_BLACK)
    np.testing.assert_allclose(got[2], v4_prm.PCS_WHITE)


def _toy_b2a(grid=17):
    """A Lab-PCS B2A whose one output is the legacy L* code of its input:
    output(L) = L, so the resampled table can be read off directly."""
    ls, ab = icw.lab_grid_axes(grid)
    mesh = np.stack(np.meshgrid(ls, ab, ab, indexing="ij"), -1).reshape(-1, 3)
    clut = np.clip(mesh[:, :1] / 100.0 * 0xFFFF, 0, 0xFFFF).round()
    return icw.make_mft2(3, 1, grid, clut.astype(">u2"),
                         in_tables=icw.lab_b2a_in_tables(1024))


def _eval_lab_b2a(blob, lab):
    """Evaluate a Lab-PCS lut16 the way a CMM does (input tables,
    trilinear CLUT, output tables)."""
    t = v4_prm.parse_mft2(blob)
    code = np.stack([lab[:, 0] / 100.0 * 0xFF00,
                     (lab[:, 1] + 128.0) * 256.0,
                     (lab[:, 2] + 128.0) * 256.0], 1)
    u = np.stack([v4_prm._table(t["in"][c], code[:, c]) for c in range(3)],
                 1) / 65535.0
    v = v4_prm._trilinear(t["clut"], t["grid"], u)
    return v4_prm._table(t["out"][0], v[:, 0]) / 0xFFFF * 100.0


def _l_from_y(y):
    return np.where(y > (6 / 29) ** 3, 116 * np.cbrt(y) - 16, y * 903.2963)


def test_resampled_b2a_takes_the_prm_black_where_it_took_zero():
    v2 = _toy_b2a()
    v4 = v4_prm.b2a_resampled(v2, b"Lab ", v4_prm.PRM_BLACK, np.zeros(3))
    l4 = np.array([0.0, 2.0, 3.1373, 5.0, 10.0, 25.0, 50.0, 90.0, 100.0])
    lab4 = np.stack([l4, np.zeros_like(l4), np.zeros_like(l4)], 1)
    got = _eval_lab_b2a(v4, lab4)
    # what the v2 table gives for the spec-inverted PCS value
    y4 = ((l4 + 16) / 116) ** 3
    y4 = np.where(l4 > 8, y4, l4 / 903.2963)
    yb = v4_prm.PRM_BLACK[1]
    want = _eval_lab_b2a(v2, np.stack([_l_from_y(np.clip((y4 - yb) / (1 - yb), 0, None)),
                                       np.zeros_like(l4), np.zeros_like(l4)], 1))
    np.testing.assert_allclose(got, want, atol=0.06)
    assert got[2] == pytest.approx(0.0, abs=0.06)       # PRM black -> v2 black
    assert got[-1] == pytest.approx(100.0, abs=0.01)    # white unchanged
    # and the old (unresampled) table read at the PRM black is NOT black
    assert _eval_lab_b2a(v2, lab4[2:3])[0] > 3.0


def _argyll() -> str:
    from tests.argyll_env import argyll_bin_dir
    d = argyll_bin_dir()
    if d is None:
        pytest.skip("ArgyllCMS not installed")
    return str(d)


@pytest.fixture(scope="module")
def _s3(tmp_path_factory):
    td = tmp_path_factory.mktemp("prm")
    p = PRINTERS["S3"]
    chart = make_chart(p, 500)
    xyz, refl, _ = measure(p, chart)
    return write_ti3(td / "c.ti3", p, chart, xyz, refl)


def _srgb_black_L(prof_path, lab_reader_path, intent):
    """sRGB black through ``prof_path`` (lcms, PIL), then the device value
    read back to Lab through the v2 file's colorimetric A2B1."""
    from PIL import Image, ImageCms
    srgb = ImageCms.createProfile("sRGB")
    prof = ImageCms.getOpenProfile(str(prof_path))
    t = ImageCms.buildTransform(srgb, prof, "RGB", "CMYK",
                                renderingIntent=intent)
    img = Image.new("RGB", (1, 1), (0, 0, 0))
    cmyk = ImageCms.applyTransform(img, t)
    back = ImageCms.buildTransform(ImageCms.getOpenProfile(str(lab_reader_path)),
                                   ImageCms.createProfile("LAB"), "CMYK", "LAB",
                                   renderingIntent=1)
    lab = ImageCms.applyTransform(cmyk, back).getpixel((0, 0))
    return lab[0] / 255.0 * 100.0


@pytest.mark.slow
def test_v4_twin_prints_srgb_black_like_the_v2_file(_s3, tmp_path):
    mode = "accurate"
    out = tmp_path / f"{mode}.icc"
    build_profile(_s3, out, BuildSettings(
        quality="l", gammap_mode=mode, icc_version="both",
        source_gamut="assets/profiles/ClayRGB1998.icm",
        argyll_bin=_argyll(),
        # Integration 2: F-09 is behind the research token "v4prm", OFF by
        # default (its ColorSync trade-off is decided separately).
        engine_candidates=("v4prm",)))
    twin = tmp_path / f"{mode}-v4.icc"
    from benchmarks.iccread import IccProfile
    p2, p4 = IccProfile(out), IccProfile(twin)
    for tag in ("A2B1", "B2A1", "gamt"):
        assert p2.tags[tag] == p4.tags[tag]
    for intent in (0, 2):
        l2 = _srgb_black_L(out, out, intent)
        l4 = _srgb_black_L(twin, out, intent)
        assert abs(l4 - l2) < 0.6, (intent, l2, l4)


@pytest.mark.slow
def test_without_the_token_the_v4_twin_keeps_the_v2_tables(_s3, tmp_path):
    """Integration 2: "v4prm" is OFF by default, so a default Maximum
    accuracy build writes the same intent 0/2 tables into both containers."""
    out = tmp_path / "accurate.icc"
    build_profile(_s3, out, BuildSettings(
        quality="l", gammap_mode="accurate", icc_version="both",
        source_gamut="assets/profiles/ClayRGB1998.icm",
        argyll_bin=_argyll()))
    from benchmarks.iccread import IccProfile
    p2 = IccProfile(out)
    p4 = IccProfile(tmp_path / "accurate-v4.icc")
    for tag in ("A2B0", "A2B1", "A2B2", "B2A0", "B2A1", "B2A2"):
        assert p2.tags[tag] == p4.tags[tag], tag

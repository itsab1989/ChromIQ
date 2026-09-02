"""Profile engine (#122): ICC writer primitives, .ti3 reader, build_profile.

Three layers:
* pure-python unit tests (always run) — encodings, tag assembly, reader;
* synthetic end-to-end builds for RGB / CMYK / CMYKOG (always run) — the
  builder must produce structurally complete profiles for every channel
  count without Argyll;
* Argyll acceptance matrix (skipped when the binaries are missing) — the
  issue-#122 evidence table re-run in CI: iccdump parses, xicclu agrees with
  the generating model at ≤4 channels, icclu handles the 6-channel profile,
  ColorSync accepts the file (macOS).
"""
from __future__ import annotations

import shutil
import struct
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from core.resource_path import argyll_binary
from tests.argyll_env import argyll_bin_dir, argyll_tool
from workflow.profile_engine import BuildSettings, build_profile
from workflow.profile_engine import icc_writer as icw
from workflow.profile_engine.ti3_data import (Ti3Error, read_ti3,
                                              split_rep_letters, xyz_to_lab)

ARGYLL = argyll_bin_dir()
needs_argyll = pytest.mark.skipif(argyll_tool("xicclu") is None,
                                  reason="ArgyllCMS binaries not installed")


# ---------------------------------------------------------------------------
# Synthetic printers (the spike's ink model, any channel count)
# ---------------------------------------------------------------------------

_ABS = np.array([
    (0.95, 0.30, 0.05), (0.10, 0.95, 0.30), (0.02, 0.06, 0.90),
    (0.90, 0.90, 0.90), (0.05, 0.55, 0.95), (0.85, 0.10, 0.75)])
_M_XYZ = np.array([(0.4360747, 0.3850649, 0.1430804),
                   (0.2225045, 0.7168786, 0.0606169),
                   (0.0139322, 0.0971045, 0.7141733)])


def synth_xyz(dev01: np.ndarray, additive: bool) -> np.ndarray:
    """Synthetic ink/light model → XYZ (Y=100 scale), well-behaved and smooth."""
    if additive:
        ink = 1.0 - dev01                      # RGB: 100% = white
    else:
        ink = dev01
    refl = np.ones((len(dev01), 3))
    for i in range(dev01.shape[1]):
        refl *= 1.0 - ink[:, i:i + 1] * _ABS[i][None, :]
    xyz = refl @ _M_XYZ.T * 100.0
    return 0.99 * xyz + 0.01 * np.array([96.42, 100.0, 82.49])[None, :]


def write_synth_ti3(path: Path, rep: str, fields: list[str],
                    additive: bool, n_per_axis: int = 5,
                    ink_limit: float | None = None) -> Path:
    n = len(fields)
    axes = [np.linspace(0.0, 1.0, n_per_axis)] * min(n, 3)
    if n <= 3:
        dev = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, n)
    else:
        rng = np.random.default_rng(42)
        dev = rng.uniform(0.0, 1.0, (n_per_axis ** 3, n))
        # Ensure exact white and black patches exist.
        dev[0] = 0.0
        dev[1] = 0.0
        dev[1, :4] = (0, 0, 0, 1)
    xyz = synth_xyz(dev, additive)
    lines = ["CTI3   ", "", 'DESCRIPTOR "synthetic"',
             f'COLOR_REP "{rep}_XYZ"']
    if ink_limit is not None:
        lines.append(f'TOTAL_INK_LIMIT "{ink_limit:.0f}"')
    lines += [f"NUMBER_OF_FIELDS {len(fields) + 4}", "BEGIN_DATA_FORMAT",
              "SAMPLE_ID " + " ".join(fields) + " XYZ_X XYZ_Y XYZ_Z",
              "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(dev)}", "BEGIN_DATA"]
    for i, (d, x) in enumerate(zip(dev, xyz)):
        lines.append(f"{i + 1} " + " ".join(f"{v * 100:.4f}" for v in d)
                     + " " + " ".join(f"{v:.4f}" for v in x))
    lines.append("END_DATA")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# icc_writer primitives
# ---------------------------------------------------------------------------

def test_lab16_roundtrip():
    lab = np.array([[0.0, 0.0, 0.0], [100.0, 0.0, 0.0],
                    [50.0, -60.5, 88.2], [3.2, 4.4, -120.0]])
    back = icw.u16_to_lab(icw.lab_to_u16(lab).astype(np.uint16))
    assert np.abs(back - lab).max() < 0.01


def test_lab_grid_axes_span_legacy_range():
    ls, ab = icw.lab_grid_axes(33)
    assert ls[0] == 0.0 and abs(ls[-1] - 100.390625) < 1e-9
    assert ab[0] == -128.0 and abs(ab[-1] - 127.99609375) < 1e-9


def test_device_space_sigs():
    assert icw.device_space_sig(3, "iRGB_XYZ") == b"RGB "
    assert icw.device_space_sig(3, "CMY_XYZ") == b"CMY "
    assert icw.device_space_sig(4, "CMYK_XYZ") == b"CMYK"
    assert icw.device_space_sig(6, "CMYKOG_XYZ") == b"6CLR"
    assert icw.device_space_sig(10, "CMYKORGBVW_XYZ") == b"ACLR"


def test_mft2_rejects_wrong_clut_shape():
    with pytest.raises(ValueError):
        icw.make_mft2(3, 3, 5, np.zeros((7, 3), dtype=">u2"))


def _tiny_profile_bytes(**spec_kw) -> bytes:
    grid = 3
    mesh = np.stack(np.meshgrid(*([np.linspace(0, 1, grid)] * 3),
                                indexing="ij"), -1).reshape(-1, 3)
    lab = np.stack([mesh[:, 0] * 100.0, mesh[:, 1] * 40 - 20,
                    mesh[:, 2] * 40 - 20], 1)
    a2b = icw.make_mft2(3, 3, grid, icw.lab_to_u16(lab))
    b2a = icw.make_mft2(3, 3, grid, icw.device_to_u16(mesh))
    gamt = icw.make_mft2(3, 1, grid,
                         np.zeros((grid ** 3, 1)).astype(">u2"))
    spec = icw.ProfileSpec(
        n_channels=3, description="tiny", color_rep="iRGB_XYZ",
        timestamp=datetime(2026, 7, 14, tzinfo=timezone.utc), **spec_kw)
    return icw.assemble_profile(spec, {
        "A2B0": a2b, "A2B1": "A2B0", "A2B2": "A2B0",
        "B2A0": b2a, "B2A1": "B2A0", "B2A2": "B2A0", "gamt": gamt})


def test_profile_bytes_golden_stability():
    b1 = _tiny_profile_bytes()
    b2 = _tiny_profile_bytes()
    assert b1 == b2                       # fixed timestamp → reproducible
    assert b1[36:40] == b"acsp"
    assert struct.unpack(">I", b1[:4])[0] == len(b1)
    assert b1[12:16] == b"prtr" and b1[16:20] == b"RGB " and b1[20:24] == b"Lab "


def test_alias_tags_share_offsets():
    blob = _tiny_profile_bytes()
    ntags = struct.unpack(">I", blob[128:132])[0]
    entries = {}
    for i in range(ntags):
        sig, off, size = struct.unpack_from(">4sII", blob, 132 + 12 * i)
        entries[sig] = (off, size)
    assert entries[b"A2B1"] == entries[b"A2B0"] == entries[b"A2B2"]
    assert entries[b"B2A2"] == entries[b"B2A0"]
    assert b"gamt" in entries and b"arts" in entries


def test_alias_to_missing_tag_raises():
    spec = icw.ProfileSpec(n_channels=3, description="x")
    with pytest.raises(ValueError):
        icw.assemble_profile(spec, {"A2B0": "B2A9"})


# ---------------------------------------------------------------------------
# ti3 reader
# ---------------------------------------------------------------------------

def test_split_rep_letters():
    assert split_rep_letters("RGB") == ["R", "G", "B"]
    assert split_rep_letters("CMYK") == ["C", "M", "Y", "K"]
    assert split_rep_letters("CMYKOG") == ["C", "M", "Y", "K", "O", "G"]
    assert split_rep_letters("CMYKcm") == ["C", "M", "Y", "K", "c", "m"]
    assert split_rep_letters("CMYK2c2m") == ["C", "M", "Y", "K", "2c", "2m"]


def test_read_ti3_rgb(tmp_path):
    p = write_synth_ti3(tmp_path / "t.ti3", "iRGB",
                        ["RGB_R", "RGB_G", "RGB_B"], additive=True)
    m = read_ti3(p)
    assert m.n_channels == 3 and m.is_additive
    assert m.device.min() >= 0.0 and m.device.max() <= 1.0
    # media white = the device-white patch with the highest Y
    assert np.allclose(m.device[m.white_index], 1.0)
    # relative basis puts media white at exactly L*=100
    assert abs(m.lab_relative[m.white_index, 0] - 100.0) < 1e-6
    assert np.abs(m.lab_relative[m.white_index, 1:]).max() < 1e-6


def test_read_ti3_cmykog_and_ink_limit(tmp_path):
    fields = [f"CMYKOG_{c}" for c in "CMYKOG"]
    p = write_synth_ti3(tmp_path / "t.ti3", "CMYKOG", fields,
                        additive=False, ink_limit=280)
    m = read_ti3(p)
    assert m.n_channels == 6 and not m.is_additive
    assert m.channel_letters == ["C", "M", "Y", "K", "O", "G"]
    assert m.ink_limit == 280.0
    assert np.allclose(m.device[m.white_index], 0.0)


def test_read_ti3_rejects_garbage(tmp_path):
    p = tmp_path / "x.ti3"
    p.write_text("not a cgats file", encoding="utf-8")
    with pytest.raises(Ti3Error):
        read_ti3(p)


# ---------------------------------------------------------------------------
# build_profile end-to-end (synthetic, no Argyll needed)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rep,fields,additive", [
    ("iRGB", ["RGB_R", "RGB_G", "RGB_B"], True),
    ("CMYK", [f"CMYK_{c}" for c in "CMYK"], False),
    ("CMYKOG", [f"CMYKOG_{c}" for c in "CMYKOG"], False),
])
def test_build_profile_synthetic(tmp_path, rep, fields, additive):
    ti3 = write_synth_ti3(tmp_path / "s.ti3", rep, fields, additive)
    out = tmp_path / "s.icc"
    res = build_profile(ti3, out, BuildSettings(
        quality="l", timestamp=datetime(2026, 7, 14, tzinfo=timezone.utc)))
    assert out.exists() and res.n_channels == len(fields)
    blob = out.read_bytes()
    assert struct.unpack(">I", blob[:4])[0] == len(blob)
    assert blob[16:20] == icw.device_space_sig(len(fields), rep)
    # the fit reproduces the synthetic model at the patches
    assert res.fit_median_de < 1.0
    # colorimetric-only build: B2A0/B2A2 alias B2A1
    ntags = struct.unpack(">I", blob[128:132])[0]
    entries = {}
    for i in range(ntags):
        sig, off, size = struct.unpack_from(">4sII", blob, 132 + 12 * i)
        entries[sig] = (off, size)
    assert entries[b"B2A0"] == entries[b"B2A1"] == entries[b"B2A2"]
    for sig in (b"desc", b"wtpt", b"bkpt", b"targ", b"gamt", b"arts"):
        assert sig in entries


def test_build_profile_quality_unknown(tmp_path):
    ti3 = write_synth_ti3(tmp_path / "s.ti3", "iRGB",
                          ["RGB_R", "RGB_G", "RGB_B"], additive=True)
    from workflow.profile_engine import EngineError
    with pytest.raises(EngineError):
        build_profile(ti3, tmp_path / "s.icc", BuildSettings(quality="x"))


# ---------------------------------------------------------------------------
# Argyll acceptance matrix (issue #122 evidence table)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def argyll_profiles(tmp_path_factory):
    """One RGB and one CMYKOG synthetic engine profile for the matrix."""
    tmp = tmp_path_factory.mktemp("engine_icc")
    out = {}
    for rep, fields, additive in (
            ("iRGB", ["RGB_R", "RGB_G", "RGB_B"], True),
            ("CMYKOG", [f"CMYKOG_{c}" for c in "CMYKOG"], False)):
        ti3 = write_synth_ti3(tmp / f"{rep}.ti3", rep, fields, additive,
                              n_per_axis=6)
        icc = tmp / f"{rep}.icc"
        build_profile(ti3, icc, BuildSettings(quality="l"))
        out[rep] = icc
    return out


@needs_argyll
def test_iccdump_parses_both(argyll_profiles):
    for icc in argyll_profiles.values():
        r = subprocess.run([str(ARGYLL / argyll_binary("iccdump")), str(icc)],
                           capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0
        assert "Lut16" in r.stdout


@needs_argyll
def test_xicclu_matches_model_rgb(argyll_profiles):
    """xicclu forward lookups agree with the generating synthetic model."""
    rng = np.random.default_rng(5)
    dev = rng.uniform(0, 1, (40, 3))
    inp = "\n".join(" ".join(f"{v:.6f}" for v in row) for row in dev)
    r = subprocess.run([str(ARGYLL / argyll_binary("xicclu")), "-ff", "-ir", "-pl",
                        str(argyll_profiles["iRGB"])],
                       input=inp, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0
    got = np.array([[float(v) for v in l.rsplit("->", 1)[1].split()[:3]]
                    for l in r.stdout.splitlines() if "->" in l])
    xyz = synth_xyz(dev, additive=True)
    white = synth_xyz(np.ones((1, 3)), additive=True)[0]
    # media-relative Lab, same Bradford basis the builder uses
    cone = icw.BRADFORD @ (xyz.T / 100)
    cw = icw.BRADFORD @ (white / 100)
    cd = icw.BRADFORD @ np.array([0.9642, 1.0, 0.8249])
    rel = (np.linalg.inv(icw.BRADFORD) @ (cone * (cd / cw)[:, None])).T * 100
    want = xyz_to_lab(rel)
    de = np.linalg.norm(got - want, axis=1)
    assert np.median(de) < 1.5 and de.max() < 6.0


@needs_argyll
def test_icclu_6clr_forward(argyll_profiles):
    """>4 channels: icclu (pure table walk) must accept the profile."""
    r = subprocess.run([str(ARGYLL / argyll_binary("icclu")), "-ff", "-ir",
                        str(argyll_profiles["CMYKOG"])],
                       input="0.2 0.1 0.4 0.0 0.3 0.0",
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "->" in r.stdout


@needs_argyll
def test_gamut_tag_lookup(argyll_profiles):
    """xicclu -fg works even on the 6CLR profile (gamt is 3-input)."""
    r = subprocess.run([str(ARGYLL / argyll_binary("xicclu")), "-fg", "-pl",
                        str(argyll_profiles["CMYKOG"])],
                       input="50 0 0", capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "->" in r.stdout


@pytest.mark.skipif(shutil.which("sips") is None, reason="macOS only")
def test_colorsync_accepts_profile(argyll_profiles):
    for icc in argyll_profiles.values():
        r = subprocess.run(["sips", "--verify", str(icc)],
                           capture_output=True, text=True, encoding="utf-8")
        out = r.stdout + r.stderr
        assert "Required tag is not present" not in out
        assert r.returncode == 0

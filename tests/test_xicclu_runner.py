"""workflow/xicclu_runner.py — the #72 perceptual bridge.

Unit tests drive the parser through an injectable fake runner (canned xicclu
output, no Argyll needed); the live tests shell the real xicclu against
Apple's Generic CMYK profile and are skipped when either is missing.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

import pytest

from core.resource_path import argyll_binary
from tests.argyll_env import argyll_bin_dir, argyll_tool
from workflow import xicclu_runner as X

# The runner resolves the platform binary name (xicclu.exe on Windows), so the
# stub file the unit tests plant must match — otherwise it's "not found" and the
# injected fake runner is never reached.
_XICCLU = argyll_binary("xicclu")

# The Argyll bin is located per-OS (was hardcoded to the macOS path, so the live
# tests skipped on Windows/Linux even with Argyll installed). The CMYK profile is
# deliberately Apple's *Generic CMYK*: the round-trip ΔE thresholds below are
# calibrated to it, so these are macOS-gated reference tests — a different CMYK
# profile has different fidelity and would make the assertions profile-dependent.
ARGYLL_BIN = argyll_bin_dir()
GENERIC_CMYK = Path("/System/Library/ColorSync/Profiles/Generic CMYK Profile.icc")
live = pytest.mark.skipif(
    argyll_tool("xicclu") is None or not GENERIC_CMYK.is_file(),
    reason="ArgyllCMS xicclu or the Generic CMYK reference profile not installed")


def _fake_runner(stdout: str, returncode: int = 0):
    """A runner returning canned xicclu output; records the call."""
    calls: list[dict] = []

    def run(cmd, **kw):
        calls.append({"cmd": cmd, **kw})
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")

    run.calls = calls
    return run


def test_backward_parses_device_and_scales(tmp_path):
    profile = tmp_path / "p.icc"
    profile.touch()
    fake = _fake_runner(
        "50.000000 40.000000 30.000000 [Lab] -> Lut -> "
        "0.126686 0.742860 0.733718 0.071004 [CMYK]\n")
    (tmp_path / _XICCLU).touch()
    out = X.backward_device([(50.0, 40.0, 30.0)], profile, tmp_path, runner=fake)
    assert out == [pytest.approx((12.6686, 74.2860, 73.3718, 7.1004), abs=1e-3)]
    # Flags: backward, relative intent, Lab in, default -kr; device 0..1 on stdin.
    cmd = fake.calls[0]["cmd"]
    assert {"-fb", "-ir", "-pl", "-kr"} <= set(cmd)
    # bytes on the wire, encoded as UTF-8 by `core.proc_text.run_text` —
    # named, rather than whatever the platform would have picked (#178).
    assert fake.calls[0]["input"].startswith(b"50.000000 40.000000 30.000000")


def test_backward_strips_tac_token_and_passes_limit(tmp_path):
    profile = tmp_path / "p.icc"
    profile.touch()
    (tmp_path / _XICCLU).touch()
    fake = _fake_runner(
        "50.0 -10.0 -20.0 [Lab] -> Lut -> "
        "0.882944 0.906397 0.170671 0.430979 TAC 2.390990 [CMYK]\n")
    out = X.backward_device([(50.0, -10.0, -20.0)], profile, tmp_path,
                            ink_limit=250.0, runner=fake)
    assert out == [pytest.approx((88.2944, 90.6397, 17.0671, 43.0979), abs=1e-3)]
    # Only -fif actually enforces -l (verified live) — -fb must not be used here.
    assert "-l250" in fake.calls[0]["cmd"] and "-fif" in fake.calls[0]["cmd"]
    assert "-fb" not in fake.calls[0]["cmd"]


def test_parser_tolerates_fif_clip_marker(tmp_path):
    profile = tmp_path / "p.icc"
    profile.touch()
    (tmp_path / _XICCLU).touch()
    fake = _fake_runner(
        "50.0 40.0 30.0 [Lab] -> Lut -> "
        "0.000000 0.708436 0.691810 0.183498 [CMYK] (clip)\n")
    out = X.backward_device([(50.0, 40.0, 30.0)], profile, tmp_path,
                            ink_limit=300.0, runner=fake)
    assert out == [pytest.approx((0.0, 70.8436, 69.1810, 18.3498), abs=1e-3)]


def test_forward_xyz_keeps_pX_scale_and_sends_unit_device(tmp_path):
    profile = tmp_path / "p.icc"
    profile.touch()
    (tmp_path / _XICCLU).touch()
    fake = _fake_runner(
        "0.500000 0.400000 0.300000 0.100000 [CMYK] -> Lut -> "
        "19.331530 20.214111 19.083632 [XYZ]\n")
    out = X.forward_xyz([(50.0, 40.0, 30.0, 10.0)], profile, tmp_path, runner=fake)
    assert out == [pytest.approx((19.3315, 20.2141, 19.0836), abs=1e-3)]
    # 0..100 input was scaled to 0..1 on the wire.
    assert fake.calls[0]["input"].startswith(b"0.500000 0.400000 0.300000 0.100000")
    assert {"-ff", "-ir", "-pX"} <= set(fake.calls[0]["cmd"])


def test_result_count_mismatch_raises(tmp_path):
    profile = tmp_path / "p.icc"
    profile.touch()
    (tmp_path / _XICCLU).touch()
    fake = _fake_runner("only a banner line, no arrow\n")
    with pytest.raises(X.XiccluError, match="0 results for 1"):
        X.forward_lab([(10.0, 10.0, 10.0, 0.0)], profile, tmp_path, runner=fake)


def test_nonzero_exit_raises_with_stderr(tmp_path):
    profile = tmp_path / "p.icc"
    profile.touch()
    (tmp_path / _XICCLU).touch()

    def run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

    with pytest.raises(X.XiccluError, match="boom"):
        X.forward_lab([(0.0, 0.0, 0.0, 0.0)], profile, tmp_path, runner=run)


def test_missing_binary_raises(tmp_path):
    with pytest.raises(X.XiccluError, match="not found"):
        X.forward_lab([(0.0, 0.0, 0.0, 0.0)], tmp_path / "p.icc", tmp_path / "nowhere")


# --- live (real xicclu + Generic CMYK) ---------------------------------------


@live
def test_live_roundtrip_mid_grey():
    # Lab → device → Lab must come back close for an in-gamut colour.
    lab = (50.0, 0.0, 0.0)
    dev = X.backward_device([lab], GENERIC_CMYK, ARGYLL_BIN)
    assert len(dev[0]) == 4 and all(0.0 <= v <= 100.0 for v in dev[0])
    back = X.forward_lab(dev, GENERIC_CMYK, ARGYLL_BIN)
    de = math.dist(lab, back[0])
    assert de < 3.0, f"in-gamut round-trip drifted ΔE {de:.2f}"


@live
def test_live_oog_is_clipped_but_parsed():
    # Far out-of-gamut Lab: no marker, plain clipped device values (#72).
    dev = X.backward_device([(50.0, -80.0, -50.0)], GENERIC_CMYK, ARGYLL_BIN)
    assert len(dev[0]) == 4
    back = X.forward_lab(dev, GENERIC_CMYK, ARGYLL_BIN)
    assert math.dist((50.0, -80.0, -50.0), back[0]) > 3.0   # visibly moved


@live
def test_live_batch_1000_one_process():
    labs = [(20.0 + (i % 60), (i % 21) - 10.0, (i % 31) - 15.0)
            for i in range(1000)]
    dev = X.backward_device(labs, GENERIC_CMYK, ARGYLL_BIN)
    assert len(dev) == 1000
    xyz = X.forward_xyz(dev, GENERIC_CMYK, ARGYLL_BIN)
    assert len(xyz) == 1000
    assert all(len(row) == 3 for row in xyz)


@live
def test_live_ink_limit_respected():
    dev = X.backward_device([(10.0, 0.0, 0.0)], GENERIC_CMYK, ARGYLL_BIN,
                            ink_limit=250.0)
    assert sum(dev[0]) <= 250.0 + 1e-6

"""Profile engine vs colprof — the P2 parity gate (issue #122).

Runs only where the real fixtures and Argyll binaries exist (Basti's machine
/ a CI runner with the fixture bundle): builds the engine profile from the
trusted ET-8550 measurement and holds it against the loss-free bands measured
on 2026-07-14:

* profcheck self-fit: engine within colprof's band (avg ≤ 0.30 CIEDE2000);
* B2A round-trip (device→Lab→device→Lab, 600 random colours): median ≤ 0.2,
  95% ≤ 1.5, max ≤ 4 (colprof -qh reference: 0.122 / 0.752 / 1.56);
* ColorSync accepts the file.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pytest

from tests.argyll_env import argyll_tool
from workflow.profile_engine import BuildSettings, build_profile

FIXTURE = Path(
    "/Users/Basti/Dropbox/Apps/Farbe/argyll-printer-profiler-v.1.3.8/"
    "Created_Profiles/ET8550_EpsPremSG_i1Studio_AdobeRGB_Mar26/"
    "ET8550_EpsPremSG_i1Studio_AdobeRGB_Mar26.ti3")

pytestmark = pytest.mark.skipif(
    argyll_tool("xicclu") is None or not FIXTURE.exists(),
    reason="parity fixture / Argyll not available")


def _xicclu(args: list[str], icc: Path, text: str) -> np.ndarray:
    r = subprocess.run([argyll_tool("xicclu"), *args, "-pl", str(icc)],
                       input=text, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr[:300]
    return np.array([[float(v) for v in ln.rsplit("->", 1)[1].split()[:3]]
                     for ln in r.stdout.splitlines() if "->" in ln])


@pytest.fixture(scope="module")
def engine_icc(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("parity") / "engine.icc"
    build_profile(FIXTURE, out, BuildSettings(quality="h"))
    return out


def test_profcheck_within_colprof_band(engine_icc):
    r = subprocess.run([argyll_tool("profcheck"), "-k", str(FIXTURE),
                        str(engine_icc)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0
    avg = float(r.stdout.split("avg. = ")[1].split(",")[0])
    assert avg <= 0.30, f"self-fit degraded: avg {avg}"


def test_b2a_round_trip_parity(engine_icc):
    rng = np.random.default_rng(3)
    dev = rng.uniform(0, 1, (600, 3))
    inp = "\n".join(" ".join(f"{v:.6f}" for v in row) for row in dev)
    labs = _xicclu(["-ff", "-ir"], engine_icc, inp)
    dev2 = _xicclu(["-fb", "-ir"], engine_icc,
                   "\n".join(" ".join(f"{v:.4f}" for v in r) for r in labs))
    labs2 = _xicclu(["-ff", "-ir"], engine_icc,
                    "\n".join(" ".join(f"{v:.6f}" for v in r) for r in dev2))
    d = np.linalg.norm(labs2 - labs, axis=1)
    assert np.median(d) <= 0.2, np.median(d)
    assert np.percentile(d, 95) <= 1.5, np.percentile(d, 95)
    assert d.max() <= 4.0, d.max()


def test_colorsync_verify(engine_icc):
    r = subprocess.run(["sips", "--verify", str(engine_icc)],
                       capture_output=True, text=True, encoding="utf-8")
    assert "Required tag is not present" not in (r.stdout + r.stderr)

"""D-06 end to end: a whole Maximum accuracy profile built with the engine's
thread pool is byte-identical to the same build on one thread (v2 file and
v4 twin), on THIS machine's numpy/BLAS. Run on every CI platform (D-07), it
proves the identity per platform; it says nothing about bytes ACROSS
platforms (D-07 point 4 has its own criterion).

Slow (two full builds with the colprof oracle each): --runslow only."""
from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from core.resource_path import argyll_binary


def _argyll_bin() -> str | None:
    """Argyll's bin dir the way the CI provides it on every OS: tests.argyll_env
    honours CHROMIQ_ARGYLL_BIN (the Windows job puts Argyll there, not on
    PATH, so the old shutil.which("colprof") lookup skipped this test on
    Windows; CI triage 37251847063, section 3)."""
    from tests.argyll_env import argyll_bin_dir
    d = argyll_bin_dir()
    if d is not None and (d / argyll_binary("colprof")).exists():
        return str(d)
    hit = shutil.which("colprof")
    return str(Path(hit).parent) if hit else None


def _build(ti3: Path, out: Path, threads: str, argyll: str,
           monkeypatch) -> tuple[bytes, bytes]:
    from workflow.profile_engine import builder as B
    monkeypatch.setenv("CHROMIQ_ENGINE_THREADS", threads)
    s = B.BuildSettings(
        quality="m", gammap_mode="accurate", icc_version="both",
        argyll_bin=argyll, source_gamut=str(
            Path(B.__file__).resolve().parents[2]
            / "assets/profiles/ClayRGB1998.icm"),
        timestamp=datetime(2026, 1, 1))
    B.build_profile(ti3, out, s)
    return out.read_bytes(), out.with_name(out.stem + "-v4.icc").read_bytes()


@pytest.mark.slow
@pytest.mark.skipif(_argyll_bin() is None, reason="ArgyllCMS not installed")
@pytest.mark.parametrize("pid", ["X3", "S1"])
def test_threaded_accurate_build_is_byte_identical(pid, tmp_path, monkeypatch):
    from benchmarks.research import datasets as dsm
    from workflow.profile_engine import gamut_map
    ds = dsm.synthetic(pid, tmp_path, 400)
    argyll = _argyll_bin()
    gamut_map._ORACLE_CACHE.clear()
    # Same file name in two folders: the description tag is the file stem.
    (tmp_path / "serial").mkdir()
    (tmp_path / "threaded").mkdir()
    serial = _build(ds.ti3, tmp_path / "serial" / "p.icc", "1", argyll,
                    monkeypatch)
    gamut_map._ORACLE_CACHE.clear()          # the threaded build runs colprof too
    threaded = _build(ds.ti3, tmp_path / "threaded" / "p.icc", "4", argyll,
                      monkeypatch)
    assert serial[0] == threaded[0]
    assert serial[1] == threaded[1]

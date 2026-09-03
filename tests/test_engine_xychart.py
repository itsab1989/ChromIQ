"""End-to-end tests for the engine's XY (SpectroScan) and chart (i1iSis/DTP70)
read modes and the opt-in gate (#126 follow-up).

The replay advertises XY or chart capability via CHROMIQ_REPLAY_MODE so the real
fork drops into rmode 2/3. Without --xychart the engine emits `mode_fallback`
(the app then re-runs stock chartread); with it, the engine reads the whole
chart / each sheet, publishing results and autosaving. Hardware-unverified —
these tests prove the protocol, not real SpectroScan/i1iSis behaviour.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, write_replay_script  # noqa: E402

ARGYLL = Path("/Applications/Argyll/bin")

pytestmark = pytest.mark.skipif(
    not HELPER.exists(), reason="chromiq-chartread helper not built")


def _make_chart(tmp: Path) -> Path:
    targen = shutil.which("targen") or str(ARGYLL / "targen")
    printtarg = shutil.which("printtarg") or str(ARGYLL / "printtarg")
    if not Path(targen).exists() or not Path(printtarg).exists():
        pytest.skip("Argyll targen/printtarg not available")
    tmp.mkdir(parents=True, exist_ok=True)
    base = tmp / "chart"
    subprocess.run([targen, "-v0", "-d2", "-G", "-e4", "-B4", "-f24",
                    str(base)], check=True, capture_output=True, cwd=tmp)
    subprocess.run([printtarg, "-v0", "-ii1", "-pA4", "-r", str(base)],
                   check=True, capture_output=True, cwd=tmp)
    return base


@pytest.fixture()
def chart(tmp_path: Path) -> tuple[Path, Path]:
    base = _make_chart(tmp_path)
    replay = tmp_path / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.0)
    return base, replay


# ---- default: XY/chart fall back to stock chartread -----------------------

def test_chart_mode_off_falls_back(chart, monkeypatch):
    base, replay = chart
    monkeypatch.setenv("CHROMIQ_REPLAY_MODE", "chart")
    s = ReplaySession(base, replay, extra_args=["-c", "1"])   # no --xychart
    try:
        ev = s.wait_event("mode_fallback", timeout=8)
        assert ev["mode"] == "chart"
    finally:
        s.proc.kill()


def test_xy_mode_off_falls_back(chart, monkeypatch):
    base, replay = chart
    monkeypatch.setenv("CHROMIQ_REPLAY_MODE", "xy")
    s = ReplaySession(base, replay, extra_args=["-c", "1"])
    try:
        ev = s.wait_event("mode_fallback", timeout=8)
        assert ev["mode"] == "xy"
    finally:
        s.proc.kill()


# ---- opt-in: the engine drives XY/chart -----------------------------------

def test_chart_mode_on_reads_and_saves(chart, monkeypatch):
    base, replay = chart
    monkeypatch.setenv("CHROMIQ_REPLAY_MODE", "chart")
    s = ReplaySession(base, replay, extra_args=["--xychart", "-c", "1"])
    try:
        s.wait_event("chart_reading", timeout=8)
        cr = s.wait_event("chart_read", timeout=5)
        assert len(cr["patches"]) > 0
        s.wait_event("saved", timeout=5)              # autosave
        code = s.finish(timeout=8)                    # autonomous → exits itself
        assert code == 0
        assert base.with_suffix(".ti3").is_file()
    finally:
        if s.proc.poll() is None:
            s.proc.kill()


def test_xy_mode_on_reads_sheets_and_saves(chart, monkeypatch):
    base, replay = chart
    monkeypatch.setenv("CHROMIQ_REPLAY_MODE", "xy")
    s = ReplaySession(base, replay, extra_args=["--xychart", "-c", "1"])
    try:
        # Each sheet asks to be placed; answer, then it reads + autosaves.
        for _ in range(6):
            if s.proc.poll() is not None:
                break
            try:
                s.wait_event("xy_place_sheet", timeout=4, after=s.event_index())
            except TimeoutError:
                break
            s.send(cmd="accept")
        # BUDGETED FOR A LOADED MACHINE, NOT AN IDLE ONE. These were 6 s and
        # 5 s. Measured idle, the whole test costs 4.04 s - most of it the
        # deliberate 4 s timeout that ends the loop above - so `xy_sheet_read`
        # arrives at once and 6 s looked like ample headroom. Inside a
        # `-n auto` gate it is not: the helper is a real subprocess competing
        # with twelve workers for twelve cores, and this failed at 6 s on a
        # gate run whose wall time was 291 s against the same suite's 185 s.
        # The same trap as `test_webengine_shutdown` in CLAUDE.md: 1.2 s idle,
        # 60 s budget, red anyway. A generous budget costs nothing when the
        # test passes, and `faulthandler_timeout` (300 s) still names a genuine
        # hang. The 4 s above stays short ON PURPOSE - it is how the loop ends.
        s.wait_event("xy_sheet_read", timeout=90)
        s.wait_event("saved", timeout=90)
        assert base.with_suffix(".ti3").is_file()
    finally:
        if s.proc.poll() is None:
            s.proc.kill()

"""End-to-end tests for the ChromIQ engine's patch-by-patch (spot) mode (#126).

Like test_chartread_engine.py, every test drives the REAL chromiq-chartread
binary through its replay instrument — the full patch-by-patch read loop runs,
only the USB edge is scripted. The spot loop now speaks the same JSON protocol
as the strip loop: `spot_ready` announces the current patch, `read` triggers a
measurement, `patch_read` carries the measured value, and `goto` jumps directly
to a patch by its location. Skipped when the helper isn't built or Argyll's
chart tools are missing.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import (  # noqa: E402
    HELPER, ReplaySession, parse_ti2_rows, write_replay_script)

ARGYLL = Path("/Applications/Argyll/bin")

pytestmark = pytest.mark.skipif(
    not HELPER.exists(), reason="chromiq-chartread helper not built")


def _make_chart(tmp: Path, *, patches: int = 30) -> Path:
    targen = shutil.which("targen") or str(ARGYLL / "targen")
    printtarg = shutil.which("printtarg") or str(ARGYLL / "printtarg")
    if not Path(targen).exists() or not Path(printtarg).exists():
        pytest.skip("Argyll targen/printtarg not available")
    tmp.mkdir(parents=True, exist_ok=True)
    base = tmp / "chart"
    subprocess.run([targen, "-v0", "-d2", "-G", "-e4", "-B4", f"-f{patches}",
                    str(base)], check=True, capture_output=True, cwd=tmp)
    # -r = fixed order so patch locations are deterministic (A1, A2, …).
    subprocess.run([printtarg, "-v0", "-ii1", "-pA4", "-r", str(base)],
                   check=True, capture_output=True, cwd=tmp)
    return base


@pytest.fixture()
def spot_chart(tmp_path: Path) -> tuple[Path, Path]:
    base = _make_chart(tmp_path)
    replay = tmp_path / "replay.txt"
    # Spot mode arms readings from the chart's own expected values, so the
    # script content is only needed to satisfy replay-load (>=1 strip).
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.0)
    return base, replay


def _spot_session(base: Path, replay: Path) -> ReplaySession:
    return ReplaySession(base, replay, extra_args=["-p"])


def test_spot_ready_announces_first_patch(spot_chart):
    base, replay = spot_chart
    s = _spot_session(base, replay)
    try:
        ev = s.wait_event("spot_ready", timeout=8)
        assert ev["loc"] == "A1"
        assert ev["read"] is False
        assert ev["all_done"] is False
        assert len(ev["exyz"]) == 3
    finally:
        s.proc.kill()


def test_read_emits_patch_read_and_advances(spot_chart):
    base, replay = spot_chart
    s = _spot_session(base, replay)
    try:
        first = s.wait_event("spot_ready", timeout=8)
        loc0 = first["loc"]
        idx = s.event_index()
        s.send(cmd="read")
        pr = s.wait_event("patch_read", after=idx, timeout=5)
        assert pr["loc"] == loc0
        # Replay echoes the expected value, so measured == expected, ΔE 0.
        assert pr["xyz"] == pr["exyz"]
        assert pr["de"] == 0.0
        # After a read the loop auto-advances to the next patch.
        nxt = s.wait_event("spot_ready", after=idx, timeout=5)
        assert nxt["loc"] != loc0
    finally:
        s.proc.kill()


def test_goto_jumps_to_patch_by_location(spot_chart):
    base, replay = spot_chart
    s = _spot_session(base, replay)
    try:
        s.wait_event("spot_ready", timeout=8)
        _, rows = parse_ti2_rows(base.with_suffix(".ti2"))
        first_row = sorted(rows)[0]
        target = f"{first_row}{len(rows[first_row])}"   # last patch of row A
        idx = s.event_index()
        s.send(cmd="goto", patch=target)
        ev = s.wait_event("spot_ready", after=idx, timeout=5)
        assert ev["loc"].lower() == target.lower()
    finally:
        s.proc.kill()


def test_goto_unknown_patch_reports_not_found(spot_chart):
    base, replay = spot_chart
    s = _spot_session(base, replay)
    try:
        s.wait_event("spot_ready", timeout=8)
        idx = s.event_index()
        s.send(cmd="goto", patch="ZZ999")
        ev = s.wait_event("error", after=idx, timeout=5)
        assert ev["kind"] == "patch_not_found"
    finally:
        s.proc.kill()


def test_navigation_forward_back(spot_chart):
    base, replay = spot_chart
    s = _spot_session(base, replay)
    try:
        s.wait_event("spot_ready", timeout=8)   # A1
        idx = s.event_index()
        s.send(cmd="forward")
        a2 = s.wait_event("spot_ready", after=idx, timeout=5)
        assert a2["loc"] == "A2"
        idx = s.event_index()
        s.send(cmd="back")
        a1 = s.wait_event("spot_ready", after=idx, timeout=5)
        assert a1["loc"] == "A1"
    finally:
        s.proc.kill()


def test_read_all_then_done_saves(spot_chart):
    base, replay = spot_chart
    s = _spot_session(base, replay)
    try:
        first = s.wait_event("spot_ready", timeout=8)
        npat, _ = parse_ti2_rows(base.with_suffix(".ti2"))
        _, rows = parse_ti2_rows(base.with_suffix(".ti2"))
        total = sum(len(v) for v in rows.values())
        # Read every patch by walking next_unread → read.
        seen = set()
        cur = first["loc"]
        for _ in range(total * 2):
            idx = s.event_index()
            s.send(cmd="read")
            pr = s.wait_event("patch_read", after=idx, timeout=5)
            seen.add(pr["loc"])
            if len(seen) >= total:
                break
            sr = s.wait_event("spot_ready", after=idx, timeout=5)
            if sr.get("all_done"):
                break
            cur = sr["loc"]
        s.send(cmd="done")
        code = s.finish(timeout=8)
        assert code == 0
        assert base.with_suffix(".ti3").is_file()
    finally:
        if s.proc.poll() is None:
            s.proc.kill()


def test_quit_aborts_without_saving(spot_chart):
    base, replay = spot_chart
    s = _spot_session(base, replay)
    try:
        s.wait_event("spot_ready", timeout=8)
        idx = s.event_index()
        s.send(cmd="quit")
        # Abort during the armed read surfaces as strip_interrupted; a second
        # quit answers the give-up prompt (same as the strip path's _quit).
        s.wait_event("strip_interrupted", after=idx, timeout=3)
        s.send(cmd="quit")
        s.finish(timeout=5)
        # Aborting skips save_ti3 — no measurement is written, and no `done`.
        assert not base.with_suffix(".ti3").is_file()
        assert not any(e.get("event") == "done" for e in s.events)
    finally:
        if s.proc.poll() is None:
            s.proc.kill()


def test_spot_calibration_handshake(spot_chart, monkeypatch):
    """The exact path that hung on a real ColorMunki: spot mode needs an initial
    calibration. It must arrive as a cal_required event answered by a command —
    never a console next_con_char (which fails on the JSON pipe)."""
    base, replay = spot_chart
    monkeypatch.setenv("CHROMIQ_REPLAY_NEEDCAL", "1")
    s = _spot_session(base, replay)
    try:
        ev = s.wait_event("cal_required", timeout=8)
        assert ev["cond"] == "man_ref_white"
        idx = s.event_index()
        s.send(cmd="accept")                 # user set the sensor, continue
        s.wait_event("cal_done", after=idx, timeout=5)
        # After calibration the read loop proceeds normally.
        s.wait_event("spot_ready", after=idx, timeout=5)
    finally:
        s.proc.kill()


def test_each_patch_read_autosaves(spot_chart):
    """Patch-by-patch autosaves after every patch (parity with strip mode) so a
    disconnect mid-session never loses the slow one-at-a-time readings: each
    read emits a `saved` event and the .ti3 exists on disk before finishing."""
    base, replay = spot_chart
    s = _spot_session(base, replay)
    try:
        s.wait_event("spot_ready", timeout=8)
        idx = s.event_index()
        s.send(cmd="read")
        s.wait_event("patch_read", after=idx, timeout=5)
        saved = s.wait_event("saved", after=idx, timeout=5)
        assert int(saved["read_patches"]) >= 1
        # Written mid-session, before any `done`.
        assert base.with_suffix(".ti3").is_file()
    finally:
        s.proc.kill()

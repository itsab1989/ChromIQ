"""Calibrating during a measurement, driven through the REAL helper.

Knut #182 5965478577 / 5965735823, Basti 5965500670: K (or the optional
Calibrate button) takes a new instrument calibration between strips or
patches, on ChromIQ's own engine, without ending the measurement.

Every test here runs the real ``chromiq-chartread`` binary through its replay
instrument, with ``CHROMIQ_REPLAY_CAL`` choosing how the calibration goes
(``setup_ok``, ``fail_once``, ``fail``, ``unavailable``). The cases are the
ones the challenge (2026-10-03, challenge.md section 7) asked for, and each
pins one of its findings:

* the request is a FLAG, not a key: a prompt that opens first (wrong strip)
  must not take it as "retry" and throw a good reading away (1a);
* one terminal ``cal_result`` for every outcome, "nothing to calibrate"
  included, so the GUI is never left waiting (1d);
* a failure LOCKS reading until a calibration succeeds (1c), and the save
  chain still ends the session with the .ti3 written;
* the external-values (-x, CR30) path ignores the request and does not crash
  (1f); the whole-sheet loop never sees it (1g).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, write_replay_script  # noqa: E402

ARGYLL = Path("/Applications/Argyll/bin")

pytestmark = pytest.mark.skipif(
    not HELPER.exists(), reason="chromiq-chartread helper not built")


def _make_chart(tmp: Path, *, patches: int = 42) -> Path:
    targen = shutil.which("targen") or str(ARGYLL / "targen")
    printtarg = shutil.which("printtarg") or str(ARGYLL / "printtarg")
    if not Path(targen).exists() or not Path(printtarg).exists():
        pytest.skip("Argyll targen/printtarg not available")
    tmp.mkdir(parents=True, exist_ok=True)
    base = tmp / "chart"
    subprocess.run([targen, "-v0", "-d2", "-G", "-e4", "-B4", f"-f{patches}",
                    str(base)], check=True, capture_output=True, cwd=tmp,
                   timeout=120)
    subprocess.run([printtarg, "-v0", "-ii1", "-pA4", "-r", str(base)],
                   check=True, capture_output=True, cwd=tmp, timeout=120)
    return base


@pytest.fixture()
def chart(tmp_path: Path) -> "tuple[Path, Path]":
    base = _make_chart(tmp_path)
    replay = tmp_path / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.3)
    return base, replay


def _results(s: ReplaySession) -> list:
    with s._lock:
        return [e for e in s.events if e.get("event") == "cal_result"]


def _quit_and_save(s: ReplaySession) -> int:
    """The engine's save chain: quit, the give-up prompt, quit."""
    idx = s.event_index()
    s.send(cmd="quit")
    s.wait_event("strip_interrupted", after=idx, timeout=8)
    s.send(cmd="quit")
    return s.finish(timeout=15)


# ---------------------------------------------------------------- strip mode

def test_calibrate_between_strips_then_the_same_strip_again(chart, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "setup_ok")
    base, replay = chart
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready", strip="A")
        s.send(cmd="swipe")
        s.wait_event("saved")
        b = s.wait_event("strip_ready", strip="B")
        assert b["read"] is False
        idx = s.event_index()
        s.send(cmd="calibrate")
        req = s.wait_event("cal_required", after=idx, timeout=8)
        assert req["requested"] is True
        assert req["cond"] == "man_ref_white"
        s.send(cmd="ok")                       # "Start Calibration"
        res = s.wait_event("cal_result", after=idx, timeout=8)
        assert res["result"] == "done" and res["prompted"] is True
        again = s.wait_event("strip_ready", after=idx, timeout=8)
        assert again["strip"] == "B", "the same strip is offered again"
        # No session-ending event of any kind.
        names = [e["event"] for e in s.events[idx:]]
        assert "aborted" not in names and "error" not in names
        assert "cal_done" not in names, "the old needs-cal event must not fire"
        # …and reading carries on normally.
        idx = s.event_index()
        s.send(cmd="swipe")
        assert s.wait_event("strip_read", after=idx)["strip"] == "B"
        s.send(cmd="done")
        s.wait_event("done", timeout=8)
        assert s.finish() == 0
    assert base.with_suffix(".ti3").is_file()


def test_the_printed_key_list_names_k(chart, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "setup_ok")
    base, replay = chart
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready")
        time.sleep(0.2)
        with s._lock:
            text = "\n".join(s.raw_lines)
        assert "'k' to calibrate" in text
        _quit_and_save(s)


def test_cancel_at_the_placement_prompt_keeps_measuring(chart, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "setup_ok")
    base, replay = chart
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready", strip="A")
        s.send(cmd="swipe")
        s.wait_event("saved")
        s.wait_event("strip_ready", strip="B")
        idx = s.event_index()
        s.send(cmd="calibrate")
        s.wait_event("cal_required", after=idx, timeout=8)
        s.send(cmd="cal_cancel")
        res = s.wait_event("cal_result", after=idx, timeout=8)
        assert res["result"] == "cancelled" and res["damaged"] is False
        s.wait_event("strip_ready", after=idx, strip="B", timeout=8)
        assert "aborted" not in [e["event"] for e in s.events[idx:]]
        assert s.proc.poll() is None, "a cancel never ends the session"
        idx = s.event_index()
        s.send(cmd="swipe")
        assert s.wait_event("strip_read", after=idx)["strip"] == "B"
        _quit_and_save(s)


def test_a_cal_cancel_outside_a_calibration_is_ignored(chart, monkeypatch):
    """A late cancel must never become a strip abort."""
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "setup_ok")
    base, replay = chart
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready", strip="A")
        idx = s.event_index()
        s.send(cmd="cal_cancel")
        time.sleep(0.5)
        names = [e["event"] for e in s.events[idx:]]
        assert "strip_interrupted" not in names and "aborted" not in names
        s.send(cmd="swipe")
        assert s.wait_event("strip_read", after=idx)["strip"] == "A"
        _quit_and_save(s)


def test_nothing_to_calibrate_answers_once(chart, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "unavailable")
    base, replay = chart
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready", strip="A")
        idx = s.event_index()
        s.send(cmd="calibrate")
        res = s.wait_event("cal_result", after=idx, timeout=8)
        assert res["result"] == "unavailable"
        s.wait_event("strip_ready", after=idx, strip="A", timeout=8)
        names = [e["event"] for e in s.events[idx:]]
        assert "cal_required" not in names
        assert names.count("cal_result") == 1
        _quit_and_save(s)


def test_a_failure_locks_reading_until_a_calibration_succeeds(chart, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "fail_once")
    base, replay = chart
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready", strip="A")
        s.send(cmd="swipe")
        s.wait_event("saved")
        s.wait_event("strip_ready", strip="B")
        idx = s.event_index()
        s.send(cmd="calibrate")
        s.wait_event("cal_required", after=idx, timeout=8)
        s.send(cmd="ok")
        res = s.wait_event("cal_result", after=idx, timeout=8)
        assert res["result"] == "failed" and res["damaged"] is True
        assert "White calibration failed" in res["detail"]
        # LOCKED: a swipe reads nothing, no strip is offered, and the old
        # needs-cal failure path (cal_failed -> engine fatal -> stock
        # fallback) is not taken.
        locked = s.event_index()
        s.send(cmd="swipe")
        s.send(cmd="forward")
        time.sleep(0.8)
        names = [e["event"] for e in s.events[locked:]]
        assert "strip_read" not in names and "strip_ready" not in names, names
        assert not [e for e in s.events[idx:]
                    if e.get("event") == "error"
                    and e.get("kind") == "cal_failed"]
        # Try again: the request is honoured in the lock, and succeeds.
        idx = s.event_index()
        s.send(cmd="calibrate")
        s.wait_event("cal_required", after=idx, timeout=8)
        s.send(cmd="ok")
        res = s.wait_event("cal_result", after=idx, timeout=8)
        assert res["result"] == "done"
        s.wait_event("strip_ready", after=idx, strip="B", timeout=8)
        idx = s.event_index()
        s.send(cmd="swipe")
        assert s.wait_event("strip_read", after=idx)["strip"] == "B"
        _quit_and_save(s)


def test_cancel_after_a_failure_stays_locked(chart, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "fail")
    base, replay = chart
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready", strip="A")
        idx = s.event_index()
        s.send(cmd="calibrate")
        s.wait_event("cal_required", after=idx, timeout=8)
        s.send(cmd="ok")
        s.wait_event("cal_result", after=idx, timeout=8, result="failed")
        idx = s.event_index()
        s.send(cmd="calibrate")
        s.wait_event("cal_required", after=idx, timeout=8)
        s.send(cmd="cal_cancel")
        res = s.wait_event("cal_result", after=idx, timeout=8)
        assert res["result"] == "cancelled" and res["damaged"] is True
        time.sleep(0.5)
        assert "strip_ready" not in [e["event"] for e in s.events[idx:]]
        _quit_and_save(s)


def test_save_and_stop_from_the_lock_writes_the_ti3(chart, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "fail")
    base, replay = chart
    ti3 = base.with_suffix(".ti3")
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready", strip="A")
        s.send(cmd="swipe")
        s.wait_event("saved")
        s.wait_event("strip_ready", strip="B")
        ti3.unlink()                          # prove the stop writes it again
        idx = s.event_index()
        s.send(cmd="calibrate")
        s.wait_event("cal_required", after=idx, timeout=8)
        s.send(cmd="ok")
        s.wait_event("cal_result", after=idx, timeout=8, result="failed")
        idx = s.event_index()
        s.send(cmd="quit")
        s.wait_event("strip_interrupted", after=idx, timeout=8)
        s.send(cmd="quit")
        s.wait_event("aborted", after=idx, timeout=8)
        s.finish(timeout=15)
    assert ti3.is_file(), "the readings were written before the session ended"
    assert "BEGIN_DATA" in ti3.read_text(encoding="utf-8", errors="replace")


def test_a_request_during_the_wrong_strip_prompt_does_not_discard_the_reading(
        chart, monkeypatch):
    """Challenge 1a: the old single key slot would have been read by this
    prompt as "any other key = retry", throwing the reading away."""
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "setup_ok")
    base, replay = chart
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready", strip="A")
        s.send(cmd="swipe", **{"as": "B"})
        w = s.wait_event("strip_warning")
        assert w["kind"] == "wrong_strip"
        idx = s.event_index()
        s.send(cmd="calibrate")
        time.sleep(0.6)
        names = [e["event"] for e in s.events[idx:]]
        assert "cal_required" not in names, "no calibration inside a prompt"
        assert "strip_ready" not in names, "the prompt did not take it as retry"
        # Use Anyway. B's values on A's line are also a large colour
        # mismatch, so chartread asks a second question; that one is answered
        # the same way, and neither took the waiting request.
        s.send(cmd="ok")
        s.wait_event("strip_warning", after=idx, kind="unexpected_response")
        s.send(cmd="ok")
        assert s.wait_event("strip_read", after=idx)["strip"] == "A"
        # …and the calibration runs at the next strip prompt.
        s.wait_event("cal_required", after=idx, timeout=8)
        s.send(cmd="ok")
        s.wait_event("cal_result", after=idx, timeout=8, result="done")
        _quit_and_save(s)


def test_a_request_at_the_unread_question_is_not_an_answer(chart, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "setup_ok")
    base, replay = chart
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready", strip="A")
        idx = s.event_index()
        s.send(cmd="done")
        s.wait_event("unread_confirm", after=idx)
        s.send(cmd="calibrate")
        time.sleep(0.5)
        assert "cal_required" not in [e["event"] for e in s.events[idx:]]
        assert s.proc.poll() is None
        s.send(cmd="no")                       # keep reading
        s.wait_event("cal_required", after=idx, timeout=8)
        s.send(cmd="ok")
        s.wait_event("cal_result", after=idx, timeout=8, result="done")
        _quit_and_save(s)


# ----------------------------------------------------------- patch by patch

def _spot(base, replay):
    return ReplaySession(base, replay, extra_args=["-p"])


def test_patch_by_patch_calibrate_then_the_same_patch(chart, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "setup_ok")
    base, replay = chart
    with _spot(base, replay) as s:
        s.wait_event("spot_ready", timeout=8)
        s.send(cmd="read")
        s.wait_event("patch_read")
        nxt = s.wait_event("spot_ready", loc="A2", timeout=8)
        assert nxt["loc"] == "A2"
        idx = s.event_index()
        s.send(cmd="calibrate")
        req = s.wait_event("cal_required", after=idx, timeout=8)
        assert req["requested"] is True
        s.send(cmd="ok")
        s.wait_event("cal_result", after=idx, timeout=8, result="done")
        again = s.wait_event("spot_ready", after=idx, timeout=8)
        assert again["loc"] == "A2"
        idx = s.event_index()
        s.send(cmd="read")
        assert s.wait_event("patch_read", after=idx)["loc"] == "A2"
        _quit_and_save(s)


def test_patch_by_patch_cancel_keeps_the_session(chart, monkeypatch):
    """Stock's patch-mode 'k' ends the program on ANY non-ok, a Cancel
    included; the engine's must not."""
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "setup_ok")
    base, replay = chart
    with _spot(base, replay) as s:
        s.wait_event("spot_ready", timeout=8)
        idx = s.event_index()
        s.send(cmd="calibrate")
        s.wait_event("cal_required", after=idx, timeout=8)
        s.send(cmd="cal_cancel")
        s.wait_event("cal_result", after=idx, timeout=8, result="cancelled")
        s.wait_event("spot_ready", after=idx, timeout=8)
        assert s.proc.poll() is None
        _quit_and_save(s)


def test_patch_by_patch_failure_locks_and_unavailable_answers(chart,
                                                             monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "fail")
    base, replay = chart
    with _spot(base, replay) as s:
        s.wait_event("spot_ready", timeout=8)
        idx = s.event_index()
        s.send(cmd="calibrate")
        s.wait_event("cal_required", after=idx, timeout=8)
        s.send(cmd="ok")
        s.wait_event("cal_result", after=idx, timeout=8, result="failed")
        locked = s.event_index()
        s.send(cmd="read")
        time.sleep(0.6)
        assert "patch_read" not in [e["event"] for e in s.events[locked:]]
        _quit_and_save(s)
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "unavailable")
    with _spot(base, replay) as s:
        s.wait_event("spot_ready", timeout=8)
        idx = s.event_index()
        s.send(cmd="calibrate")
        s.wait_event("cal_result", after=idx, timeout=8, result="unavailable")
        s.wait_event("spot_ready", after=idx, timeout=8)
        _quit_and_save(s)


# ------------------------------------------------- paths that must ignore it

def test_the_whole_sheet_loop_ignores_a_request(chart, monkeypatch):
    """Challenge 1g: i1iSis/XY must behave exactly as before."""
    monkeypatch.setenv("CHROMIQ_REPLAY_MODE", "chart")
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "setup_ok")
    base, replay = chart
    s = ReplaySession(base, replay, extra_args=["--xychart", "-c", "1"])
    try:
        s.send(cmd="calibrate")
        s.wait_event("chart_reading", timeout=8)
        s.wait_event("chart_read", timeout=15)
        code = s.finish(timeout=30)
        assert code == 0
        assert not _results(s)
        assert "cal_required" not in [e["event"] for e in s.events]
    finally:
        if s.proc.poll() is None:
            s.proc.kill()


def test_the_external_values_path_ignores_a_request(tmp_path):
    """Challenge 1f: under -x a 'k' reached the stock branch with no
    instrument open and dereferenced NULL. The request is never mirrored
    onto the line queue, so nothing reaches it."""
    from test_cr30_external_values import Reader
    r = Reader(tmp_path)
    try:
        deadline = time.time() + 8
        while not r.events("spot_ready") and time.time() < deadline:
            time.sleep(0.05)
        assert r.events("spot_ready")
        r.send({"cmd": "calibrate"})
        time.sleep(0.6)
        assert r.p.poll() is None, "the helper died on a calibrate under -x"
        assert not r.events("cal_result") and not r.events("cal_required")
        r.send({"cmd": "value", "xyz": "20 20 20"})
        deadline = time.time() + 8
        while not r.events("patch_read") and time.time() < deadline:
            time.sleep(0.05)
        assert r.events("patch_read"), "values still flow after the request"
    finally:
        r.kill()


def test_stock_mode_without_json_is_untouched():
    """The strip menu's printed lines are stock's when --json is absent: the
    engine-only 'k' line is printed in JSON mode only."""
    src = (Path(__file__).resolve().parents[1] / "native" / "chartread_helper"
           / "chromiq_chartread.c").read_text(encoding="utf-8")
    i = src.index("'k' to calibrate the instrument before the next strip")
    assert "if (cq_json)" in src[i - 200:i]
    j = src.index("inst_set_uih('K', 'K', DUIH_CMND);")
    assert "if (cq_json)" in src[j - 400:j]

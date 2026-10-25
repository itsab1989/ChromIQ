"""Button gestures in the engine (Basti, 2026-10-25; jctay, forum 149841).

A double or triple press of the instrument's button, timed and grouped by the
REAL chromiq-chartread through its replay instrument. ``{"cmd":"presses",
"at_ms":"0,300"}`` is a person pressing at those times: a press that triggers
a waiting strip is a quick tap whose scan ends "Reading is too short" 220 ms
later (Basti's ColorMunki ended them in 0.19-0.27 s), every other press is
reported by the fake driver's switch thread, as on a ColorMunki or i1Pro.

What has to hold, and is proved here:

* OFF (no ``--gestures``) is today, event for event and byte for byte
  (against a session recorded with the engine of 474c8995e);
* ON, one press still gives today's "Reading is too short" error, after the
  wait; 2 or 3 presses within the wait are a ``gesture`` and never a
  failure, never a reading, never a write;
* a real strip read (trigger, presses during it, a swipe) is never a gesture,
  nor is a failed scan that ran longer than CQ_GESTURE_MAX_SCAN_MS;
* patch by patch, a double press drops the reading its first press made;
* the holds group presses too; only the i1Pro line and the ColorMunki do it;
* ``--button-test`` reports every group and reads nothing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import (HELPER, ReplaySession, helper_env,  # noqa: E402
                          write_replay_script)

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "data" / "button_gestures_off_golden"

needs_helper = pytest.mark.skipif(not HELPER.exists(),
                                  reason="chromiq-chartread helper not built")

WAIT = 600          # the default wait, ms
ON = ["--gestures", f"{WAIT}:23"]


def _chart(tmp: Path):
    from test_chartread_engine import _make_chart
    base = _make_chart(tmp, randomised=False)
    replay = tmp / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.2)
    return base, replay


def _quit(s):
    from test_chartread_engine import _quit as quit_session
    quit_session(s)


def _events(s, after: int) -> list:
    with s._lock:
        return list(s.events[after:])


def _names(s, after: int) -> list:
    return [e.get("event") for e in _events(s, after)]


def _settle(s, after: int, seconds: float) -> list:
    time.sleep(seconds)
    return _names(s, after)


# ---------------------------------------------------------------------------
# OFF is today
# ---------------------------------------------------------------------------
def _scripted_session(s) -> None:
    """A session that touches every place gestures could change: a strip
    read, a misread answered with the button, a pause after a strip with a
    press in it, the end."""
    s.wait_event("strip_ready")
    i = s.event_index()
    s.send(cmd="swipe")
    s.wait_event("saved", after=i)
    s.wait_event("strip_ready", after=i)
    i = s.event_index()
    s.send(cmd="swipe", fault="misread", reason="Reading is too short")
    s.wait_event("error", after=i)
    i = s.event_index()
    s.send(cmd="switch")
    s.wait_event("switch", after=i)
    s.send(cmd="ok")
    ready = s.wait_event("strip_ready", after=i)
    s.send(cmd="hold_after", strip=ready["strip"])
    i = s.event_index()
    s.send(cmd="swipe")
    s.wait_event("held", after=i)
    i = s.event_index()
    s.send(cmd="switch")
    s.wait_event("switch", after=i, timeout=5)
    s.send(cmd="resume")
    s.wait_event("strip_ready", after=i)
    s.send(cmd="done")
    s.wait_event("done", timeout=8)
    s.finish()


def _normalised(s, base: Path) -> "tuple[list, str]":
    evs = []
    for e in s.events:
        if e.get("event") == "scan_ready":       # a timer thread's; order varies
            continue
        e = dict(e)
        e.pop("chart", None)                     # the temp path
        e.pop("path", None)                      # ...and the file's
        evs.append(e)
    ti3 = base.with_suffix(".ti3").read_text(encoding="latin-1")
    ti3 = "\n".join(ln for ln in ti3.splitlines()
                    if not ln.startswith("CREATED"))
    return evs, ti3


def _record_golden(tmp: Path) -> None:      # pragma: no cover - run by hand
    """How tests/data/button_gestures_off_golden was made: with the engine of
    474c8995e (the commit before gestures), CHROMIQ_CHARTREAD pointing at it."""
    base, replay = _chart(tmp)
    with ReplaySession(base, replay) as s:
        _scripted_session(s)
    evs, ti3 = _normalised(s, base)
    GOLDEN.mkdir(parents=True, exist_ok=True)
    (GOLDEN / "events.json").write_text(json.dumps(evs, indent=1) + "\n",
                                        encoding="utf-8")
    (GOLDEN / "chart.ti3").write_text(ti3 + "\n", encoding="latin-1")


@needs_helper
def test_off_is_today_event_for_event_and_byte_for_byte(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        _scripted_session(s)
    evs, ti3 = _normalised(s, base)
    want = json.loads((GOLDEN / "events.json").read_text(encoding="utf-8"))
    assert evs == want
    assert ti3 + "\n" == (GOLDEN / "chart.ti3").read_text(encoding="latin-1")
    assert not any(e.get("event") in ("gesture", "gestures") for e in s.events)


@needs_helper
def test_on_with_single_presses_writes_the_same_file(tmp_path):
    """Switched on, the same session (every press a single one) ends in the
    same .ti3 and the same events, plus the announcement."""
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay, extra_args=ON) as s:
        _scripted_session(s)
    evs, ti3 = _normalised(s, base)
    ann = [e for e in evs if e.get("event") == "gestures"]
    assert ann == [{"event": "gestures", "active": True, "unit": "strip",
                    "wait_ms": WAIT}]
    evs = [e for e in evs if e.get("event") != "gestures"]
    assert evs == json.loads((GOLDEN / "events.json").read_text(encoding="utf-8"))
    assert ti3 + "\n" == (GOLDEN / "chart.ti3").read_text(encoding="latin-1")


# ---------------------------------------------------------------------------
# ON, at a waiting strip
# ---------------------------------------------------------------------------
@needs_helper
def test_a_single_press_is_todays_error_after_the_wait(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay, extra_args=ON) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        t0 = time.monotonic()
        s.send(cmd="presses", at_ms="0")
        err = s.wait_event("error", after=i, timeout=5)
        # measured from the press itself, so a loaded machine can only make
        # it longer: today's error came 220 ms after the tap
        waited = time.monotonic() - t0
        assert err["kind"] == "misread"
        assert err["detail"] == "Reading is too short"
        assert err["button_retry"] is True
        # the wait runs from the last press (here the tap itself), so the
        # error comes a whole wait after it, not 220 ms after it as today
        assert waited >= WAIT / 1000 - 0.03, waited
        assert "gesture" not in _names(s, i)
        _quit(s)


@needs_helper
@pytest.mark.parametrize("at, n", [("0,300", 2), ("0,250,500", 3),
                                   ("0,550", 2), ("0,500,1000", 3)])
def test_two_or_three_presses_within_the_wait_are_a_gesture(tmp_path, at, n):
    base, replay = _chart(tmp_path)
    ti3 = base.with_suffix(".ti3")
    with ReplaySession(base, replay, extra_args=ON) as s:
        first = s.wait_event("strip_ready")
        before = ti3.read_bytes() if ti3.exists() else None
        i = s.event_index()
        s.send(cmd="presses", at_ms=at)
        g = s.wait_event("gesture", after=i, timeout=6)
        assert g["presses"] == n
        assert g["where"] == "strip" and g["strip"] == first["strip"]
        assert len(g["gaps_ms"]) == n - 1
        assert all(0 < x <= WAIT for x in g["gaps_ms"]), g
        names = _settle(s, i, 0.3)
        # never a failure, never a reading, never a write
        for bad in ("error", "strip_read", "saved", "strip_ready",
                    "strip_warning", "strip_misaligned"):
            assert bad not in names, (bad, names)
        assert (ti3.read_bytes() if ti3.exists() else None) == before
        # the engine waits for the GUI: back reads the previous strip
        i = s.event_index()
        s.send(cmd="resume")
        again = s.wait_event("strip_ready", after=i)
        assert again["strip"] == first["strip"] and again["read"] is False
        _quit(s)


@needs_helper
def test_the_moves_after_a_gesture(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay, extra_args=ON) as s:
        a = s.wait_event("strip_ready")
        assert a["strip"] == "A"
        i = s.event_index()
        s.send(cmd="presses", at_ms="0,300")
        s.wait_event("gesture", after=i, timeout=6)
        s.send(cmd="forward")
        assert s.wait_event("strip_ready", after=i)["strip"] == "B"
        i = s.event_index()
        s.send(cmd="presses", at_ms="0,300,600")
        s.wait_event("gesture", after=i, timeout=6)
        s.send(cmd="back")
        assert s.wait_event("strip_ready", after=i)["strip"] == "A"
        i = s.event_index()
        s.send(cmd="presses", at_ms="0,300")
        s.wait_event("gesture", after=i, timeout=6)
        s.send(cmd="goto", strip="B")
        assert s.wait_event("strip_ready", after=i)["strip"] == "B"
        i = s.event_index()
        s.send(cmd="presses", at_ms="0,300")
        s.wait_event("gesture", after=i, timeout=6)
        s.send(cmd="next_unread")
        s.wait_event("strip_ready", after=i)
        _quit(s)


@needs_helper
def test_presses_further_apart_than_the_wait_are_singles(tmp_path):
    """The first is a tap at the strip (today's error, after the wait), the
    second lands at the misread prompt and is its Retry, as today."""
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay, extra_args=ON) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="presses", at_ms=f"0,{220 + WAIT + 300}")
        s.wait_event("error", after=i, timeout=5)
        s.wait_event("switch", after=i, timeout=5)
        assert "gesture" not in _settle(s, i, 0.2)
        _quit(s)


@needs_helper
def test_a_count_with_no_action_is_a_single_press(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay, extra_args=["--gestures", f"{WAIT}:2"]) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="presses", at_ms="0,250,500")      # a triple, unassigned
        err = s.wait_event("error", after=i, timeout=5)
        assert err["kind"] == "misread"
        assert "gesture" not in _settle(s, i, 0.3)
        _quit(s)


@needs_helper
def test_at_the_misread_prompt_a_double_press_is_a_gesture(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay, extra_args=ON) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="swipe", fault="misread", reason="Too many patches")
        s.wait_event("error", after=i)
        i = s.event_index()
        s.send(cmd="presses", at_ms="0,300")
        g = s.wait_event("gesture", after=i, timeout=5)
        assert g["where"] == "prompt" and g["presses"] == 2
        assert "switch" not in _names(s, i)
        s.send(cmd="ok")
        s.wait_event("strip_ready", after=i)
        _quit(s)


# ---------------------------------------------------------------------------
# a real strip read is never a gesture
# ---------------------------------------------------------------------------
@needs_helper
def test_presses_during_a_real_scan_change_nothing(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay, extra_args=ON) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="trigger", ready_ms="50")
        s.wait_event("scan_started", after=i)
        s.send(cmd="switch")              # an accidental second press
        time.sleep(0.15)
        s.send(cmd="switch")              # and a third
        s.send(cmd="swipe")
        rd = s.wait_event("strip_read", after=i)
        assert rd["strip"] == "A"
        s.wait_event("saved", after=i)
        names = _settle(s, i, WAIT / 1000 + 0.3)
        assert "gesture" not in names and "error" not in names
        assert "switch" not in names
        _quit(s)


@needs_helper
def test_a_failed_scan_longer_than_the_limit_is_todays_error_at_once(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay, extra_args=ON) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="trigger", ready_ms="50")
        s.wait_event("scan_started", after=i)
        time.sleep(2.3)                   # a slide, past CQ_GESTURE_MAX_SCAN_MS
        s.send(cmd="switch")
        s.send(cmd="swipe", fault="misread", reason="Reading is inconsistent")
        t0 = time.monotonic()
        err = s.wait_event("error", after=i, timeout=5)
        assert time.monotonic() - t0 < 0.4, "a long scan was waited on"
        assert err["detail"] == "Reading is inconsistent"
        assert "gesture" not in _names(s, i)
        _quit(s)


# ---------------------------------------------------------------------------
# the holds
# ---------------------------------------------------------------------------
@needs_helper
def test_in_the_pause_presses_are_grouped_too(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay, extra_args=ON) as s:
        a = s.wait_event("strip_ready")
        s.send(cmd="hold_after", strip=a["strip"])
        i = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("held", after=i)
        i = s.event_index()
        s.send(cmd="presses", at_ms="0,300")
        g = s.wait_event("gesture", after=i, timeout=5)
        assert g["where"] == "held"
        # nothing moved and nothing was read: still held
        names = _settle(s, i, 0.3)
        assert "strip_ready" not in names and "scan_started" not in names
        i = s.event_index()
        s.send(cmd="presses", at_ms="0")
        s.wait_event("switch", after=i, timeout=5)
        s.send(cmd="resume")
        s.wait_event("strip_ready", after=i)
        _quit(s)


@needs_helper
def test_the_hold_while_a_finishing_window_is_open_groups_too(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay, extra_args=ON) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="hold")
        s.wait_event("held", after=i, here=True)
        i = s.event_index()
        s.send(cmd="presses", at_ms="0,300,600")
        g = s.wait_event("gesture", after=i, timeout=5)
        assert g["where"] == "held" and g["presses"] == 3
        assert "scan_started" not in _names(s, i)
        s.send(cmd="resume")
        s.wait_event("strip_ready", after=i)
        _quit(s)


@needs_helper
def test_no_press_is_reported_during_a_requested_calibration(tmp_path,
                                                             monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_CAL", "setup_ok")
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay, extra_args=ON) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="calibrate")
        s.wait_event("cal_required", after=i, timeout=8)
        j = s.event_index()
        s.send(cmd="presses", at_ms="0,300")
        names = _settle(s, j, WAIT / 1000 + 0.6)
        assert "gesture" not in names and "switch" not in names
        s.send(cmd="ok")
        s.wait_event("cal_result", after=j, timeout=8)
        _quit(s)


# ---------------------------------------------------------------------------
# which instruments
# ---------------------------------------------------------------------------
@needs_helper
@pytest.mark.parametrize("model, active", [("colormunki", True),
                                           ("dtp20", False)])
def test_only_instruments_that_report_presses(tmp_path, monkeypatch, model,
                                              active):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", model)
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay, extra_args=ON) as s:
        ann = s.wait_event("gestures")
        assert ann["active"] is active
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="presses", at_ms="0,300")
        if active:
            s.wait_event("gesture", after=i, timeout=5)
            s.send(cmd="resume")
        else:
            # today: the tap fails at once, and the window does not offer
            # the button (button_retry false); no group is ever made
            t0 = time.monotonic()
            err = s.wait_event("error", after=i, timeout=5)
            assert time.monotonic() - t0 < 0.45
            assert err["button_retry"] is False
            assert "gesture" not in _settle(s, i, 0.8)
        _quit(s)


# ---------------------------------------------------------------------------
# patch by patch
# ---------------------------------------------------------------------------
@needs_helper
def test_patch_by_patch_a_double_press_drops_its_reading(tmp_path):
    base, replay = _chart(tmp_path)
    ti3 = base.with_suffix(".ti3")
    with ReplaySession(base, replay, extra_args=ON + ["-p"]) as s:
        assert s.wait_event("gestures")["unit"] == "patch"
        first = s.wait_event("spot_ready")
        before = ti3.read_bytes() if ti3.exists() else None
        i = s.event_index()
        s.send(cmd="presses", at_ms="0,300")
        g = s.wait_event("gesture", after=i, timeout=5)
        assert g["where"] == "patch" and g["patch"] == first["loc"]
        names = _settle(s, i, 0.3)
        assert "patch_read" not in names and "saved" not in names
        assert (ti3.read_bytes() if ti3.exists() else None) == before
        s.send(cmd="resume")
        again = s.wait_event("spot_ready", after=i)
        assert again["loc"] == first["loc"] and not again.get("read")
        # a single press reads the patch, after the wait
        i = s.event_index()
        s.send(cmd="presses", at_ms="0")
        rd = s.wait_event("patch_read", after=i, timeout=5)
        assert rd["loc"] == first["loc"]
        nxt = s.wait_event("spot_ready", after=i)
        # back goes to the patch before, forward and next unread move on
        i = s.event_index()
        s.send(cmd="presses", at_ms="0,300,600")
        s.wait_event("gesture", after=i, timeout=5)
        s.send(cmd="back")
        assert s.wait_event("spot_ready", after=i)["loc"] == first["loc"]
        i = s.event_index()
        s.send(cmd="presses", at_ms="0,300")
        s.wait_event("gesture", after=i, timeout=5)
        s.send(cmd="forward")
        assert s.wait_event("spot_ready", after=i)["loc"] == nxt["loc"]
        i = s.event_index()
        s.send(cmd="presses", at_ms="0,300")
        s.wait_event("gesture", after=i, timeout=5)
        s.send(cmd="next_unread")
        nu = s.wait_event("spot_ready", after=i)
        assert nu["loc"] not in (first["loc"],)
        i = s.event_index()
        s.send(cmd="presses", at_ms="0,300")
        s.wait_event("gesture", after=i, timeout=5)
        s.send(cmd="goto", patch=first["loc"])
        assert s.wait_event("spot_ready", after=i)["loc"] == first["loc"]
        _quit(s)


# ---------------------------------------------------------------------------
# Preferences' "Try it"
# ---------------------------------------------------------------------------
def _button_test(tmp_path, env_extra=None):
    replay = tmp_path / "replay.txt"
    replay.write_text("PATCHES 1\nSTRIP A\n50 50 50\n", encoding="utf-8")
    env = helper_env()
    env.update(env_extra or {})
    return subprocess.Popen(
        [str(HELPER), "--json", "--replay", str(replay), "--button-test",
         "--gestures", f"{WAIT}:23"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", bufsize=1, env=env)


def _read_events_until(proc, name, timeout=8.0) -> list:
    import threading
    out: list = []
    done = threading.Event()

    def pump():
        for line in proc.stdout:
            if line.startswith("{"):
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
                if out[-1].get("event") == name:
                    done.set()
                    return
        done.set()
    t = threading.Thread(target=pump, daemon=True)
    t.start()
    done.wait(timeout)
    return out


@needs_helper
def test_try_it_reports_every_group_and_reads_nothing(tmp_path):
    proc = _button_test(tmp_path)
    try:
        evs = _read_events_until(proc, "instrument")
        inst = evs[-1]
        assert inst["event"] == "instrument" and inst["button"] is True
        assert inst["wait_ms"] == WAIT
        for at in ("0", "0,300", "0,250,500", "0,200,400,600"):
            proc.stdin.write(json.dumps({"cmd": "presses", "at_ms": at}) + "\n")
            proc.stdin.flush()
            got = _read_events_until(proc, "press_group")
            g = got[-1]
            assert g["event"] == "press_group"
            assert g["presses"] == len(at.split(",")), (at, g)
        proc.stdin.write('{"cmd":"quit"}\n')
        proc.stdin.flush()
        end = _read_events_until(proc, "button_test_end")
        assert end and end[-1]["event"] == "button_test_end"
        assert proc.wait(timeout=10) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)
        for p in (proc.stdin, proc.stdout):
            try:
                p.close()
            except Exception:  # noqa: BLE001
                pass
    assert not list(tmp_path.glob("*.ti3"))


@needs_helper
def test_try_it_ends_when_its_window_goes(tmp_path):
    """Closing stdin (the dialog's process ending) closes the instrument."""
    proc = _button_test(tmp_path)
    try:
        _read_events_until(proc, "instrument")
        proc.stdin.close()
        end = _read_events_until(proc, "button_test_end")
        assert end and end[-1]["event"] == "button_test_end"
        assert proc.wait(timeout=10) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)
        try:
            proc.stdout.close()
        except Exception:  # noqa: BLE001
            pass


@needs_helper
def test_try_it_says_when_the_instrument_has_no_button_events(tmp_path):
    proc = _button_test(tmp_path, {"CHROMIQ_REPLAY_INSTRUMENT": "dtp20"})
    try:
        evs = _read_events_until(proc, "instrument")
        assert evs[-1]["button"] is False
        proc.stdin.write('{"cmd":"quit"}\n')
        proc.stdin.flush()
        assert proc.wait(timeout=10) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)
        for p in (proc.stdin, proc.stdout):
            try:
                p.close()
            except Exception:  # noqa: BLE001
                pass


def test_caps_name_gestures():
    text = (ROOT / "native" / "chartread_helper" / "chromiq_chartread.c"
            ).read_text(encoding="utf-8")
    assert '\\"gestures\\",\\"button_test\\"' in text


# ---------------------------------------------------------------------------
# Basti's ColorMunki, 2026-10-25: two faults only the real instrument showed
# ---------------------------------------------------------------------------
@needs_helper
@pytest.mark.parametrize("port_args, port", [(["-c", "1"], 1), (["-c1"], 1),
                                             (["-c", "3"], 3), (["-c2"], 2)])
def test_try_it_takes_its_port_with_no_outfile(port_args, port):
    """The REAL argument parsing, with no replay: Argyll takes a flag's
    separate value only when a final argument is left for it, and Try it has
    none, so "-c 1" printed usage instead of opening the instrument. Nothing
    is opened here, not even the list of ports (parse-only)."""
    env = helper_env()
    env["CHROMIQ_BUTTON_TEST_PARSE_ONLY"] = "1"
    res = subprocess.run(
        [str(HELPER), "--json", "--button-test", "--gestures", f"{WAIT}:23",
         *port_args], capture_output=True, text=True, encoding="utf-8",
        stdin=subprocess.DEVNULL, env=env, timeout=30)
    assert "usage" not in res.stdout.lower(), res.stdout[:400]
    evs = [json.loads(ln) for ln in res.stdout.splitlines()
           if ln.startswith("{")]
    assert evs == [{"event": "button_test_args", "port": port,
                    "wait_ms": WAIT}], res.stdout[:400]


def test_the_app_passes_the_port_attached():
    src = (ROOT / "ui" / "button_shortcuts_section.py").read_text(
        encoding="utf-8")
    assert 'args += [f"-c{port}"]' in src


def _ends_within(proc, seconds):
    t0 = time.monotonic()
    try:
        rc = proc.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        return None, time.monotonic() - t0
    return rc, time.monotonic() - t0


@needs_helper
@pytest.mark.parametrize("stuck", ["", "close", "signal", "close,signal"])
@pytest.mark.parametrize("how", ["quit", "eof", "sigint", "sigterm"])
def test_try_it_always_lets_the_instrument_go(tmp_path, stuck, how):
    """An instrument-shaped hang (CHROMIQ_REPLAY_STUCK): closing it never
    returns, and/or Argyll's USB signal handler never returns. However Try it
    is ended, the process is gone within the grace (1.5 s) plus a margin for
    a loaded machine, and a process that has ended has let the USB device
    go. Before the fix the ColorMunki stayed held until SIGTERM."""
    import signal as _signal
    proc = _button_test(tmp_path, {"CHROMIQ_REPLAY_STUCK": stuck,
                                   "CHROMIQ_ENGINE_MUTE": "1"})
    try:
        _read_events_until(proc, "instrument")
        if how == "quit":
            proc.stdin.write('{"cmd":"quit"}\n')
            proc.stdin.flush()
        elif how == "eof":
            proc.stdin.close()
        else:
            proc.send_signal(_signal.SIGINT if how == "sigint"
                             else _signal.SIGTERM)
        rc, took = _ends_within(proc, 6)
        assert rc is not None, f"still running {took:.1f} s after {how}"
        assert took < 4.0, took
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        for p in (proc.stdin, proc.stdout):
            try:
                p.close()
            except Exception:  # noqa: BLE001
                pass


@needs_helper
@pytest.mark.parametrize("how", ["quit", "eof", "sigint"])
def test_a_measuring_session_always_lets_the_instrument_go(tmp_path,
                                                           monkeypatch, how):
    """The same, measuring: the hand test's strips run did not end either."""
    import signal as _signal
    monkeypatch.setenv("CHROMIQ_REPLAY_STUCK", "close,signal")
    monkeypatch.setenv("CHROMIQ_ENGINE_MUTE", "1")
    base, replay = _chart(tmp_path)
    s = ReplaySession(base, replay, extra_args=ON)
    try:
        s.wait_event("strip_ready")
        if how == "quit":
            i = s.event_index()
            s.send(cmd="quit")
            s.wait_event("strip_interrupted", after=i, timeout=5)
            s.send(cmd="quit")
        elif how == "eof":
            s.proc.stdin.close()
        else:
            s.proc.send_signal(_signal.SIGINT)
        rc, took = _ends_within(s.proc, 6)
        assert rc is not None, f"still running {took:.1f} s after {how}"
        assert took < 4.0, took
    finally:
        s.finish(timeout=5) if s.proc.poll() is None else s.finish()

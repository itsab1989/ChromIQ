"""#202 round 2 (Knut, 5943245399, Q3): "the timing should start at the beep,
as this is when measurement start happens".

After the instrument's button is pressed an i1Pro first warms its lamp: the
driver beeps 200 ms + 0.5 s later (i1pro_imp.c:3196-3203), and only then is it
sampling. ChromIQ used to time a strip from the press (`scan_started`), so every
strip carried ~0.7 s that was not swiping, and the per-patch figure was too
generous by that much.

The engine now registers an instrument event callback in JSON mode. On
`inst_event_scan_ready` it plays exactly the beep the driver plays without one,
`msec_beep(0, 1000, 200)` (Knut 5943350639: the beep stays Argyll's, at Argyll's
0.7 s), and emits `{"event":"scan_ready"}`. That callback runs on Argyll's
helper THREAD, so every JSON line is written whole under stdout's lock.

These tests drive the REAL chromiq-chartread through its replay instrument,
whose `{"cmd":"trigger"}` does what the i1Pro driver does on a press: reports
`inst_triggered`, then raises the ready moment through Argyll's own
`issue_scan_ready()` after 700 ms.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                    # noqa: E402
from PyQt6.QtWidgets import QApplication              # noqa: E402

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, write_replay_script  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "native" / "chartread_helper"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _chart(tmp: Path):
    """A small fixed-order i1Pro chart and a replay script for it (the same
    recipe as test_chartread_engine)."""
    from test_chartread_engine import _make_chart
    base = _make_chart(tmp, randomised=False)
    replay = tmp / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.2)
    return base, replay


def _quit(s):
    from test_chartread_engine import _quit as quit_session
    quit_session(s)


needs_helper = pytest.mark.skipif(not HELPER.exists(),
                                  reason="chromiq-chartread helper not built")


# ---------------------------------------------------------------------------
# 1. the engine
# ---------------------------------------------------------------------------
@needs_helper
def test_the_engine_reports_the_beep_after_the_lamp_has_warmed(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready")
        idx = s.event_index()
        s.send(cmd="trigger")
        s.wait_event("scan_started", after=idx)
        t_started = time.monotonic()
        s.wait_event("scan_ready", after=idx)
        gap = time.monotonic() - t_started
        # 700 ms in the driver; a loaded gate can only make it later.
        assert gap >= 0.6, f"scan_ready came {gap:.3f} s after the press"
        names = [e["event"] for e in s.events[idx:]]
        assert names.index("scan_started") < names.index("scan_ready")
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=idx)
        _quit(s)
    # The line itself: one clean JSON object on a line of its own.
    lines = [ln for ln in s.raw_lines if "scan_ready" in ln]
    assert lines == ['{"event":"scan_ready"}'], lines


@needs_helper
def test_every_line_stays_whole_while_the_helper_thread_writes(tmp_path):
    """The beep's line comes from Argyll's helper thread. Fired with no delay
    straight into the swipe, it races the main thread's strip_read, which is
    written in many pieces. Every line must still parse."""
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready")
        for _round in range(6):
            idx = s.event_index()
            s.send(cmd="trigger", ready_ms="0")
            s.send(cmd="swipe")
            s.wait_event("strip_read", after=idx)
            s.wait_event("saved", after=idx)
            s.send(cmd="goto", strip="A")
            s.wait_event("strip_ready", after=idx + 1, strip="A")
        _quit(s)
    broken = []
    for ln in s.raw_lines:
        if "{\"event\"" in ln and not ln.startswith("{"):
            broken.append(ln)                       # an event glued to prose
        elif ln.startswith("{"):
            try:
                json.loads(ln)
            except json.JSONDecodeError:
                broken.append(ln)
    assert not broken, broken[:3]
    assert sum(1 for e in s.events if e.get("event") == "scan_ready") >= 6


def _callback_body() -> str:
    text = (SRC / "chromiq_chartread.c").read_text(encoding="utf-8")
    m = re.search(r"void cq_event_callback\(void \*cntx, inst_event_type event\)"
                  r" \{(.*?)\n\}", text, re.S)
    assert m, "cq_event_callback has gone from chromiq_chartread.c"
    return m.group(1)


def test_the_beep_is_the_one_argyll_plays():
    """Registering a callback stops the driver beeping itself
    (i1pro_imp.c:3198-3203); without it the driver plays
    msec_beep(delay, 1000, 200). With the delay spent, that is exactly
    msec_beep(0, 1000, 200), called directly and not through normal_beep(),
    which chromiq_chartread.c redirects."""
    body = _callback_body()
    assert "msec_beep(0, 1000, 200);" in body
    assert "inst_event_scan_ready" in body
    # The beep first, then the line.
    assert body.index("msec_beep") < body.index("scan_ready\\\"}")
    driver = (ROOT / "native" / "instlib" / "i1pro_imp.c").read_text(
        encoding="utf-8", errors="replace")
    assert "msec_beep(delay, 1000, 200);" in driver


def test_only_json_mode_takes_the_ready_moment():
    """Console mode is stock chartread and keeps the driver's own beep."""
    text = (SRC / "chromiq_chartread.c").read_text(encoding="utf-8")
    assert re.search(r"if \(cq_json\)\s*\n\s*it->set_event_callback\(it, "
                     r"cq_event_callback", text), \
        "the event callback must be registered in JSON mode only"


def test_every_json_writer_holds_the_stdout_lock():
    """A multi-part event must be written under cq_out_lock, or the helper
    thread's line can land inside it."""
    text = (SRC / "chromiq_chartread.c").read_text(encoding="utf-8")
    for event in (r'"\n{\"event\":\"strip_read\",',
                  r'"\n{\"event\":\"session_start\",',
                  r'"\n{\"event\":\"%s\",\"patches\":['):
        i = text.index(event)
        before = text[max(0, i - 120):i]
        assert "cq_out_lock();" in before, f"{event} is written without the lock"
        after = text[i:]
        assert after.index("cq_out_unlock();") < after.index("\n}\n"), \
            f"{event}: the lock is not given back in the same function"
    js = (SRC / "chromiq_json.c").read_text(encoding="utf-8")
    raw = js[js.index("void cq_emit_raw("):js.index("void cq_emit_simple(")]
    assert raw.index("cq_out_lock();") < raw.index("vfprintf")
    assert raw.index("cq_out_unlock();") > raw.index("fflush(stdout);")


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS build only")
def test_the_committed_engine_runs_on_every_mac_the_app_does():
    """CI builds it universal2 for macOS 13.0 (build-release.yml); the
    committed copy that ChromIQ.spec bundles must match."""
    helper = ROOT / "native" / "chromiq-chartread"
    if not helper.is_file():
        pytest.skip("bundled helper not present")
    archs = subprocess.run(["lipo", "-archs", str(helper)], capture_output=True, encoding="utf-8",
                           text=True, timeout=60).stdout.split()
    assert set(archs) == {"arm64", "x86_64"}, archs
    load = subprocess.run(["otool", "-l", str(helper)], capture_output=True, encoding="utf-8",
                          text=True, timeout=60).stdout
    minos = re.findall(r"minos (\d+(?:\.\d+)*)", load)
    assert minos and all(m == "13.0" for m in minos), minos
    assert b"scan_ready" in helper.read_bytes()


# ---------------------------------------------------------------------------
# 2. the manager
# ---------------------------------------------------------------------------
def test_the_manager_turns_the_event_into_a_signal(qapp):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from workflow.measure_manager import MeasureManager
    m = MeasureManager(ArgyllRunner(AppSettings()))
    m._engine_active = True
    seen = []
    m.scan_ready.connect(lambda: seen.append("ready"))
    m.scan_started.connect(lambda: seen.append("started"))
    m._handle_engine_line('{"event":"scan_started"}', lambda _l: None)
    m._handle_engine_line('{"event":"scan_ready"}', lambda _l: None)
    assert seen == ["started", "ready"]


# ---------------------------------------------------------------------------
# 3. the tab
# ---------------------------------------------------------------------------
@pytest.fixture
def tab(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("pace_hint_enabled", True)
    # Knut's i1Pro 2 (#202): 200 readings a second, 24 per patch = 120 ms.
    s.set("pace_sample_hz_i1pro2", 200.0)
    s.set("pace_min_samples_i1pro2", 24)
    from ui.tabs.tab_measure import TabMeasure
    t = TabMeasure(ArgyllRunner(s), s)
    t._on_instrument_detected("X-Rite i1 Pro 2")
    return t


def _strip(n, name="A"):
    return {"strip": name, "patches": [{"id": f"{name}{i}"} for i in range(n)]}


def test_the_clock_starts_at_the_beep_not_the_press(tab, monkeypatch):
    """21 patches at 110 ms is a strip read too fast for an i1Pro 2 (120 ms).
    Timed from the press it took 0.7 s longer, 143 ms a patch, and passed."""
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    tab._on_scan_started()
    clock[0] += 0.7                       # the lamp warms up
    tab._manager.scan_ready.emit()        # through the real connection
    clock[0] += 21 * 0.110                # the swipe
    tab._report_strip_pace(_strip(21))
    assert tab._pace_times["A"][0] == pytest.approx(21 * 0.110)
    assert "Too fast" in tab._pace_panel._verdict, tab._pace_panel._verdict


def test_a_device_that_never_beeps_is_still_timed_from_the_press(tab, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    tab._on_scan_started()
    clock[0] += 3.0
    tab._report_strip_pace(_strip(21))
    assert tab._pace_times["A"][0] == pytest.approx(3.0)


def test_a_late_beep_never_starts_the_next_strips_clock(tab, monkeypatch):
    """A strip that fails at once can be reported before its beep arrives.
    That beep belongs to the strip that is over; it must not start a clock for
    a strip whose button has not been pressed."""
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    tab._on_scan_started()
    clock[0] += 0.3
    tab._report_failed_strip_pace("Strip read failed")
    clock[0] += 0.4
    tab._on_scan_ready()                  # the beep, late
    assert getattr(tab, "_scan_started_at", None) is None
    # The next strip: pressed 20 s later, beeps, and is read in 4 s.
    clock[0] += 20.0
    tab._on_scan_started()
    clock[0] += 0.7
    tab._on_scan_ready()
    clock[0] += 4.0
    tab._report_strip_pace(_strip(21, "B"))
    assert tab._pace_times["B"][0] == pytest.approx(4.0)


def test_a_beep_after_an_accepted_strip_is_ignored_too(tab, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    tab._on_scan_started()
    clock[0] += 3.0
    tab._report_strip_pace(_strip(21))
    tab._on_scan_ready()
    assert getattr(tab, "_scan_started_at", None) is None


def test_only_the_first_beep_of_a_press_moves_the_clock(tab, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    tab._on_scan_ready()                  # no press: nothing to time
    assert getattr(tab, "_scan_started_at", None) is None
    tab._on_scan_started()
    clock[0] += 0.7
    tab._on_scan_ready()
    clock[0] += 1.0
    tab._on_scan_ready()                  # a stray second one
    clock[0] += 2.0
    tab._report_strip_pace(_strip(21))
    assert tab._pace_times["A"][0] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# 1-3 together: the real engine's lines through the real manager into the tab
# ---------------------------------------------------------------------------
@needs_helper
def test_a_strip_measured_on_the_engine_leaves_out_the_lamp_time(tab, tmp_path):
    base, replay = _chart(tmp_path)
    mgr = tab._manager
    mgr._engine_active = True
    # Half a second for a whole strip is too fast on purpose, so the test does
    # not wait out a real swipe; the "Strip Read Quickly" window that opens
    # for it is not what is under test here.
    tab._suppress_fast_prompt = True
    handled = [0]
    seen_at: dict = {}

    def pump(s, until, timeout=10.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with s._lock:
                new = s.raw_lines[handled[0]:]
            for ln in new:
                handled[0] += 1
                # Noted BEFORE the line is handled: the tab reads the clock as
                # it handles the line.
                if ln.startswith("{"):
                    try:
                        seen_at.setdefault(json.loads(ln).get("event"),
                                           time.monotonic())
                    except json.JSONDecodeError:
                        pass
                mgr._handle_engine_line(ln, lambda _l: None)
            QApplication.processEvents()
            if until in seen_at:
                return
            time.sleep(0.005)
        raise TimeoutError(until)

    with ReplaySession(base, replay) as s:
        pump(s, "strip_ready")
        strip = s.wait_event("strip_ready")["strip"]
        s.send(cmd="trigger")
        pump(s, "scan_ready")
        time.sleep(0.5)                       # the swipe
        s.send(cmd="swipe")
        pump(s, "strip_read")
        _quit(s)
    elapsed = tab._pace_times[strip][0]
    from_press = seen_at["strip_read"] - seen_at["scan_started"]
    from_beep = seen_at["strip_read"] - seen_at["scan_ready"]
    assert elapsed == pytest.approx(from_beep, abs=0.05)
    assert from_press - elapsed >= 0.6, (
        f"the strip took {elapsed:.3f} s, {from_press:.3f} s from the press: "
        "the lamp's warm-up is still being counted")

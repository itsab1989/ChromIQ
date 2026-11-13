"""The i1Pro 2 lights (Preferences > Beta): the "lights may still be on" marker
and the window at Start (M-I1PRO2-LIGHTS-LEFT-ON), owner 2026-11-13.

A precaution nobody can try on hardware: a helper that crashed or was killed
while the white light was on cannot switch it off, and ArgyllCMS's notes say
a running light pattern can disturb the instrument's start-up. Proved here:

* with the option OFF no marker is ever written or read, and no window can
  appear;
* the marker lives beside the sandboxed settings (CHROMIQ_SETTINGS_FILE), or
  in ChromIQ's settings folder beside the presets, never in a project folder,
  and holds an instrument type and a time, nothing else;
* a marker of another instrument type, an unreadable one, or a chart for
  another instrument never shows the window;
* written when the helper reports the white light on, removed when it
  reports the lights off or exits normally, kept when it is killed, stuck or
  a light request failed;
* end to end with the real ArgyllRunner and MeasureManager and a stand-in
  helper that speaks the helper's JSON (the fake-USB driver build in
  test_i1pro2_lights_driver.py is a C test program, not a helper process):
  killed while lit, the next Start asks, Continue clears it, Cancel keeps it
  and starts nothing; a clean session, an answered Stop and an answered app
  quit leave no marker.
"""
from __future__ import annotations

import inspect
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
LIT = '{"event":"lights","active":true}'
OFF = '{"event":"lights","state":"off"}'


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """CHROMIQ_SETTINGS_FILE in tmp_path, so the marker lives there."""
    ini = tmp_path / "settings" / "driver.ini"
    ini.parent.mkdir()
    monkeypatch.setenv("CHROMIQ_SETTINGS_FILE", str(ini))
    from core import i1pro2_lights_marker as marker
    path = marker.marker_path()
    assert path == ini.parent / "driver.i1pro2-lights-on.json"
    return path


class _Settings(dict):
    def get(self, key, default=None):  # noqa: D401 - dict-like settings
        return super().get(key, default)


# ---------------------------------------------------------------------------
# Where it lives, what it holds
# ---------------------------------------------------------------------------
def test_it_follows_the_sandboxed_settings_file(sandbox):
    assert sandbox.name == "driver.i1pro2-lights-on.json"


def test_without_a_sandbox_it_lives_beside_the_presets(tmp_path, monkeypatch):
    monkeypatch.delenv("CHROMIQ_SETTINGS_FILE", raising=False)
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "prefs" / "presets"))
    from core import i1pro2_lights_marker as marker
    assert marker.marker_path() == tmp_path / "prefs" / "i1pro2-lights-on.json"


def test_never_in_a_project_folder(sandbox, monkeypatch, tmp_path):
    projects = tmp_path / "projects"
    monkeypatch.setenv("CHROMIQ_OUTPUT_ROOT", str(projects))
    from core import i1pro2_lights_marker as marker
    for path in (marker.marker_path(), sandbox):
        assert projects not in path.parents
    src = inspect.getsource(marker)
    for word in ("output_root", "custom_output_path", "Project", "run_dir"):
        assert word not in src.split('"""', 2)[2], word


def test_it_holds_an_instrument_type_and_a_time_and_nothing_else(sandbox):
    from core import i1pro2_lights_marker as marker
    marker.note_white_on(True)
    data = json.loads(sandbox.read_text(encoding="utf-8"))
    assert set(data) == {"instrument", "since"}
    assert data["instrument"] == "i1pro2"
    time.strptime(data["since"], "%Y-%m-%dT%H:%M:%S")
    assert not list(sandbox.parent.glob("*.tmp"))


# ---------------------------------------------------------------------------
# Option off: never written, never read
# ---------------------------------------------------------------------------
def test_option_off_writes_and_reads_nothing(sandbox, monkeypatch):
    from core import i1pro2_lights_marker as marker
    sandbox.write_text('{"instrument": "i1pro2", "since": "x"}',
                       encoding="utf-8")

    def _no(*_a, **_k):
        raise AssertionError("the marker was touched with the option off")
    monkeypatch.setattr(marker, "marker_path", _no)
    marker.note_white_on(False)
    marker.note_lights_off(False)
    assert marker.left_on(False, "i1") is False
    assert marker.option_on(_Settings()) is False
    assert marker.option_on(_Settings(i1pro2_lights_beta=False)) is False
    assert marker.option_on(None) is False


def test_option_off_a_session_writes_no_marker(sandbox, qapp, tmp_path,
                                               monkeypatch):
    m, _r, _lines = _started_manager(tmp_path, monkeypatch, lights=False)
    m._handle_engine_line(LIT, lambda _l: None)   # not sent without the flag
    m._lights_session_ended(-1)
    assert not sandbox.exists()


def test_option_off_the_start_shows_no_window(sandbox):
    sandbox.write_text('{"instrument": "i1pro2", "since": "x"}',
                       encoding="utf-8")
    tab = _StubTab(option=False, family="i1")
    assert _blocked(tab) is False
    assert tab.windows == [] and sandbox.exists()


# ---------------------------------------------------------------------------
# Only an i1Pro 2 marker, only for an i1Pro chart
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("content", [
    '{"instrument": "i1pro3", "since": "2026-11-13T10:00:00"}',
    '{"instrument": "colormunki"}',
    '{"since": "2026-11-13T10:00:00"}',
    '["i1pro2"]',
    'not json at all',
    '',
])
def test_a_marker_of_another_kind_never_shows_the_window(sandbox, content):
    from core import i1pro2_lights_marker as marker
    sandbox.write_text(content, encoding="utf-8")
    assert marker.left_on(True, "i1") is False
    tab = _StubTab(option=True, family="i1")
    assert _blocked(tab) is False and tab.windows == []


@pytest.mark.parametrize("family", ["CM", "CR30", "p3", "SS", "isis", None])
def test_it_never_stands_in_front_of_another_instrument(sandbox, family):
    from core import i1pro2_lights_marker as marker
    marker.note_white_on(True)
    tab = _StubTab(option=True, family=family)
    assert _blocked(tab) is False
    assert tab.windows == [] and sandbox.exists()   # kept for the i1Pro 2


# ---------------------------------------------------------------------------
# The manager: written on white, removed on a clean off, kept otherwise
# ---------------------------------------------------------------------------
class _Runner:
    def __init__(self):
        self.calls = []
        self.is_running = False
        self.courtesy = []
        self.last_exit_crashed = False

    def run(self, tool, args, cwd, on_line=None, on_finish=None, use_pty=False):
        self.calls.append((str(tool), list(args)))
        self.on_finish = on_finish

    def set_kill_courtesy(self, line):
        self.courtesy.append(line)

    def write_stdin(self, text):
        pass


def _started_manager(tmp_path, monkeypatch, *, lights):
    from workflow import chartread_engine
    from workflow.measure_manager import MeasureManager, MeasureParams
    monkeypatch.setattr(chartread_engine, "helper_caps",
                        lambda helper=None: frozenset({"i1pro2_lights"}))
    monkeypatch.setattr(MeasureManager, "_refuse_system_port",
                        lambda self, *a, **k: False)
    monkeypatch.setattr(MeasureManager, "_launch_stock",
                        lambda self, *a, **k: None)
    runner = _Runner()
    m = MeasureManager(runner)
    p = MeasureParams(ti1_path=tmp_path / "chart.ti1",
                      engine_helper=tmp_path / "chromiq-chartread",
                      engine_i1pro2_lights=lights)
    m.start(p, lambda _l: None, lambda _c: None)
    return m, runner, []


def test_white_on_writes_it_and_the_off_event_removes_it(sandbox, qapp,
                                                         tmp_path, monkeypatch):
    m, _r, lines = _started_manager(tmp_path, monkeypatch, lights=True)
    m._handle_engine_line(LIT, lines.append)
    assert sandbox.exists()
    m._handle_engine_line(OFF, lines.append)
    assert not sandbox.exists()


@pytest.mark.parametrize("code,crashed,failed,kept", [
    (0, False, False, False),     # the end of a chart: the close switched off
    (1, False, False, False),     # an ArgyllCMS error(): atexit switched off
    (9, True, False, True),       # killed, or crashed
    (4, False, False, True),      # the exit guard on a stuck close
    (137, False, False, True),    # a signal
    (0, False, True, True),       # a light request failed: may still be on
])
def test_how_the_helper_ended_decides(sandbox, qapp, tmp_path, monkeypatch,
                                      code, crashed, failed, kept):
    m, runner, lines = _started_manager(tmp_path, monkeypatch, lights=True)
    m._handle_engine_line(LIT, lines.append)
    if failed:
        m._handle_engine_line(
            '{"event":"lights","state":"failed","step":"off","err":512}',
            lines.append)
    runner.last_exit_crashed = crashed
    runner.on_finish(code)
    assert sandbox.exists() is kept


def test_a_session_that_never_lit_leaves_an_old_marker_alone(
        sandbox, qapp, tmp_path, monkeypatch):
    """Another instrument measured in between: its session neither writes
    nor clears; the i1Pro 2's marker waits for the i1Pro 2."""
    from core import i1pro2_lights_marker as marker
    marker.note_white_on(True)
    m, runner, lines = _started_manager(tmp_path, monkeypatch, lights=True)
    m._handle_engine_line(
        '{"event":"lights","active":false,"why":"instrument"}', lines.append)
    runner.on_finish(0)
    assert sandbox.exists()


# ---------------------------------------------------------------------------
# The Start guard and its window
# ---------------------------------------------------------------------------
class _Log:
    def __init__(self):
        self.text = []

    def appendPlainText(self, t):
        self.text.append(t)

    def ensureCursorVisible(self):
        pass


class _StubTab(SimpleNamespace):
    def __init__(self, *, option, family, answer=True):
        super().__init__(_settings=_Settings(i1pro2_lights_beta=option),
                         _log=_Log(), windows=[], answer=answer, family=family)

    def _chart_instrument_code(self):
        return self.family

    def _i1pro2_lights_left_on_window(self):
        self.windows.append("M-I1PRO2-LIGHTS-LEFT-ON")
        return self.answer

    def _start_button_name(self):
        return "Start Measurement"


def _blocked(tab) -> bool:
    from ui.tabs.tab_measure import TabMeasure
    return TabMeasure._blocked_by_i1pro2_lights_left_on(tab)


def test_continue_clears_it_and_the_start_goes_on(sandbox):
    from core import i1pro2_lights_marker as marker
    marker.note_white_on(True)
    tab = _StubTab(option=True, family="i1", answer=True)
    assert _blocked(tab) is False
    assert tab.windows == ["M-I1PRO2-LIGHTS-LEFT-ON"]
    assert not sandbox.exists()
    again = _StubTab(option=True, family="i1")
    assert _blocked(again) is False and again.windows == []   # once


def test_cancel_keeps_it_and_starts_nothing(sandbox):
    from core import i1pro2_lights_marker as marker
    marker.note_white_on(True)
    tab = _StubTab(option=True, family="i1", answer=False)
    assert _blocked(tab) is True
    assert sandbox.exists()
    assert len(tab._log.text) == 1
    assert "Measurement not started" in tab._log.text[0]
    assert "“Start Measurement”" in tab._log.text[0]
    assert "—" not in tab._log.text[0]


def test_the_guard_runs_before_anything_is_armed_archived_or_opened():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_start)
    at = src.index("self._blocked_by_i1pro2_lights_left_on()")
    for later in ("self._sound.arm(", "self._archive_measurement_before_replacing()",
                  "self._run_cr30_calibration()", "self._collect_params()"):
        assert at < src.index(later), later
    assert src.index("self._blocked_by_a_differing_condition()") < at


def _answer_box(monkeypatch, label):
    from PyQt6.QtWidgets import QMessageBox
    seen = {}

    def _exec(box):
        seen["title"] = box.windowTitle()
        seen["text"] = box.text()
        seen["body"] = box.informativeText()
        seen["buttons"] = [b.text() for b in box.buttons()]
        seen["default"] = box.defaultButton().text()
        seen["escape"] = box.escapeButton().text()
        next(b for b in box.buttons() if b.text() == label).click()
        return 0
    monkeypatch.setattr(QMessageBox, "exec", _exec)
    return seen


@pytest.mark.parametrize("label,expected", [("Continue", True), ("Cancel", False)])
def test_the_window_is_the_catalogues(qapp, monkeypatch, label, expected):
    from PyQt6.QtWidgets import QWidget
    from ui.tabs.tab_measure import TabMeasure
    from workflow import measurement_messages as M
    seen = _answer_box(monkeypatch, label)
    parent = QWidget()
    try:
        got = TabMeasure._i1pro2_lights_left_on_window(parent)
    finally:
        parent.deleteLater()
    title, body = M.M_I1PRO2_LIGHTS_LEFT_ON.render()
    assert got is expected
    # (QMessageBox keeps no window title on macOS; the headline is the text)
    assert seen["text"] == title
    assert seen["body"] == body
    assert sorted(seen["buttons"]) == ["Cancel", "Continue"]
    assert seen["default"] == "Continue" and seen["escape"] == "Cancel"


def test_the_window_plays_no_sound_and_the_text_is_proposed():
    from ui.tabs.tab_measure import TabMeasure
    from workflow import measurement_messages as M
    for meth in (TabMeasure._i1pro2_lights_left_on_window,
                 TabMeasure._blocked_by_i1pro2_lights_left_on):
        src = inspect.getsource(meth)
        assert "_cue_window" not in src and "play_window" not in src
    msg = M.M_I1PRO2_LIGHTS_LEFT_ON
    assert msg.approved is False and msg.id in M.PROPOSED
    for word in ("unplug", "wait a few seconds", "plug it in again",
                 "“Continue”", "“Cancel”", "ended unexpectedly"):
        assert word in msg.body, word
    assert "—" not in msg.title + msg.body


# ---------------------------------------------------------------------------
# End to end: the real runner and manager, a stand-in helper
# ---------------------------------------------------------------------------
STAND_IN = r'''#!{python}
import os, signal, sys, time
mode = {mode!r}
print('{{"event":"session_start"}}', flush=True)
print('{{"event":"lights","active":true}}', flush=True)
if mode == "clean":
    time.sleep(0.3)
    sys.exit(0)            # the close ran: del_i1proimp switched the lights off
for line in sys.stdin:
    if "lights_off_exit" in line and mode == "answers":
        print('{{"event":"lights","state":"off"}}', flush=True)
        os.kill(os.getpid(), signal.SIGKILL)   # ends itself as a kill would
time.sleep(60)
'''

posix_only = pytest.mark.skipif(sys.platform == "win32",
                                reason="the stand-in helper is a #! script")


@pytest.fixture
def live(qapp, tmp_path, monkeypatch, sandbox):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from workflow import chartread_engine
    from workflow.measure_manager import MeasureManager, MeasureParams
    monkeypatch.setattr(chartread_engine, "helper_caps",
                        lambda helper=None: frozenset({"i1pro2_lights"}))
    monkeypatch.setattr(MeasureManager, "_refuse_system_port",
                        lambda self, *a, **k: False)
    launched_stock = []
    monkeypatch.setattr(MeasureManager, "_launch_stock",
                        lambda self, *a, **k: launched_stock.append(a))
    runner = ArgyllRunner(AppSettings())
    finished = []

    def start(mode):
        script = tmp_path / f"stand-in-{mode}"
        script.write_text(STAND_IN.format(python=sys.executable, mode=mode),
                          encoding="utf-8")
        script.chmod(0o755)
        m = MeasureManager(runner)
        p = MeasureParams(ti1_path=tmp_path / "chart.ti1",
                          engine_helper=script, engine_i1pro2_lights=True)
        m.start(p, lambda _l: None, finished.append)
        assert runner._process.waitForStarted(5000)
        _spin_until(lambda: m.lights_active, 10)
        assert m.lights_active, "the stand-in's white light was not heard"
        return m

    yield SimpleNamespace(runner=runner, start=start, finished=finished,
                          marker=sandbox, stock=launched_stock)
    runner.cleanup()


def _spin_until(cond, seconds):
    from PyQt6.QtCore import QCoreApplication
    t0 = time.monotonic()
    while not cond() and time.monotonic() - t0 < seconds:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    return cond()


@posix_only
def test_killed_while_lit_then_the_next_start_asks_and_continue_clears(live):
    live.start("deaf")
    assert live.marker.exists()                       # written on white
    live.runner._process.kill()                       # the helper dies
    assert _spin_until(lambda: live.finished, 10)
    assert live.runner.last_exit_crashed is True
    assert live.marker.exists()                       # left: may still be lit
    tab = _StubTab(option=True, family="i1", answer=True)
    assert _blocked(tab) is False
    assert tab.windows == ["M-I1PRO2-LIGHTS-LEFT-ON"]
    assert not live.marker.exists()                   # Continue cleared it


@posix_only
def test_killed_while_lit_then_cancel_keeps_it(live):
    live.start("deaf")
    live.runner._process.kill()
    assert _spin_until(lambda: live.finished, 10)
    tab = _StubTab(option=True, family="i1", answer=False)
    assert _blocked(tab) is True and live.marker.exists()


@posix_only
def test_a_clean_session_leaves_no_marker(live):
    live.start("clean")
    assert _spin_until(lambda: live.finished, 10)
    assert live.finished == [0] and live.runner.last_exit_crashed is False
    assert not live.marker.exists()
    tab = _StubTab(option=True, family="i1")
    assert _blocked(tab) is False and tab.windows == []


@posix_only
def test_a_stop_the_helper_answers_leaves_no_marker(live):
    live.start("answers")
    assert live.marker.exists()
    live.runner.abort()                               # Discard and stop
    assert _spin_until(lambda: live.finished, 10)
    assert live.runner.last_exit_crashed is True      # it ended as a kill
    assert not live.marker.exists()                   # but said "off" first


@posix_only
def test_a_stop_the_helper_does_not_answer_keeps_it(live):
    live.start("deaf")
    live.runner.abort()                               # backstop kill in 1 s
    assert _spin_until(lambda: live.finished, 10)
    assert live.marker.exists()


@posix_only
def test_quitting_the_app_mid_measurement(live):
    live.start("answers")
    live.runner.cleanup()                             # MainWindow.closeEvent
    assert not live.marker.exists()


@posix_only
def test_quitting_the_app_with_a_helper_that_does_not_answer(live):
    live.start("deaf")
    live.runner.cleanup()
    assert live.marker.exists()

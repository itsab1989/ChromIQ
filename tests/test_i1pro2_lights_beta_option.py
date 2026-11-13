"""The i1Pro 2 indicator lights (Preferences > Beta, Basti 2026-11-13): the
option, the helper and the app around the driver patch.

The driver itself is proved in tests/test_i1pro2_lights_driver.py. Here:

* OFF (the default) is 4.3.32: the setting is off, the helper is started with
  exactly the command line it had, a stopped session is killed at once as
  before, and the helper's events for a whole scripted session are the golden
  ones recorded with the engine of 474c8995e (no "lights" event at all);
* ON, the helper is given --i1pro2-lights only when it says it knows it; for
  anything that is not an i1Pro 2 (here the replay instrument) it says so once
  and changes nothing else, event for event and byte for byte;
* while the lights are in use, ChromIQ ends a session it would kill by asking
  the helper to switch them off and end itself as a kill would, with the kill
  as a backstop bound to that one process;
* the Preferences row, its ⓘ and the window that asks before it goes on.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
needs_helper = pytest.mark.skipif(not HELPER.exists(),
                                  reason="chromiq-chartread helper not built")


# ---------------------------------------------------------------------------
# The setting and the command line
# ---------------------------------------------------------------------------
def test_the_setting_is_off_by_default():
    from core.settings import DEFAULTS
    assert DEFAULTS["i1pro2_lights_beta"] is False


class _Runner:
    def __init__(self):
        self.calls = []
        self.is_running = False
        self.courtesy = []

    def run(self, tool, args, cwd, on_line=None, on_finish=None, use_pty=False):
        self.calls.append((str(tool), list(args)))

    def set_kill_courtesy(self, line):
        self.courtesy.append(line)

    def write_stdin(self, text):
        pass


def _engine_args(qapp, tmp_path, monkeypatch, *, lights, caps):
    from workflow import chartread_engine
    from workflow.measure_manager import MeasureManager, MeasureParams
    monkeypatch.setattr(chartread_engine, "helper_caps",
                        lambda helper=None: frozenset(caps))
    monkeypatch.setattr(MeasureManager, "_refuse_system_port",
                        lambda self, *a, **k: False)
    runner = _Runner()
    m = MeasureManager(runner)
    p = MeasureParams(ti1_path=tmp_path / "chart.ti1",
                      engine_helper=tmp_path / "chromiq-chartread",
                      engine_i1pro2_lights=lights)
    m.start(p, lambda _l: None, lambda _c: None)
    assert runner.calls, "the engine was not started"
    return runner.calls[-1][1]


def test_off_starts_the_helper_with_exactly_todays_command_line(
        qapp, tmp_path, monkeypatch):
    off = _engine_args(qapp, tmp_path, monkeypatch, lights=False,
                       caps={"i1pro2_lights"})
    assert "--i1pro2-lights" not in off
    on = _engine_args(qapp, tmp_path, monkeypatch, lights=True,
                      caps={"i1pro2_lights"})
    assert [a for a in on if a != "--i1pro2-lights"] == off
    assert on.count("--i1pro2-lights") == 1


def test_a_helper_that_does_not_know_the_flag_is_not_given_it(
        qapp, tmp_path, monkeypatch):
    args = _engine_args(qapp, tmp_path, monkeypatch, lights=True,
                        caps={"gestures"})
    assert "--i1pro2-lights" not in args


def test_the_measure_tab_reads_the_setting_at_every_start():
    src = (ROOT / "ui" / "tabs" / "tab_measure.py").read_text(encoding="utf-8")
    assert ('p.engine_i1pro2_lights = bool(\n'
            '            self._settings.get("i1pro2_lights_beta", False))') in src


# ---------------------------------------------------------------------------
# The engine's "lights" events, as the manager reads them
# ---------------------------------------------------------------------------
def _manager_with_lines():
    from workflow.measure_manager import MeasureManager
    runner = _Runner()
    m = MeasureManager(runner)
    lines = []
    return m, runner, lines


@pytest.mark.parametrize("ev,courtesy,needle", [
    ({"event": "lights", "active": True}, ['{"cmd":"lights_off_exit"}\n'],
     "white while it waits for you"),
    ({"event": "lights", "active": False, "why": "instrument"}, [],
     "only on an i1Pro 2"),
    ({"event": "lights", "active": False, "why": "mode"}, [],
     "strips or single patches by hand"),
    ({"event": "lights", "active": False, "why": "lights"}, [],
     "could not use the lights"),
    ({"event": "lights", "state": "failed", "step": "off", "err": 512}, [None],
     "unplug the instrument"),
    ({"event": "lights", "state": "off"}, [None], None),
])
def test_the_lights_events(qapp, ev, courtesy, needle):
    m, runner, lines = _manager_with_lines()
    m._handle_engine_line(json.dumps(ev), lines.append)
    assert runner.courtesy == courtesy
    if needle is None:
        assert lines == []
    else:
        assert len(lines) == 1 and needle in lines[0]
        assert "—" not in lines[0]
    assert m.lights_active is bool(ev.get("active"))


def test_a_failed_first_white_is_said_once(qapp):
    m, runner, lines = _manager_with_lines()
    for ev in ({"event": "lights", "state": "failed", "step": "white", "err": 0},
               {"event": "lights", "active": False, "why": "lights"}):
        m._handle_engine_line(json.dumps(ev), lines.append)
    assert len(lines) == 1 and "did not accept" in lines[0]


# ---------------------------------------------------------------------------
# The runner: kill as before, unless the lights of THIS process are in use
# ---------------------------------------------------------------------------
@pytest.fixture
def runner(qapp):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    r = ArgyllRunner(AppSettings())
    yield r
    r.cleanup()


def _sleeper(runner, tmp_path, seconds=30):
    """A stand-in process that reads stdin and records what it was sent."""
    log = tmp_path / "got.txt"
    script = tmp_path / "sleeper.py"
    script.write_text(
        "import sys, time\n"
        f"out = open({str(log)!r}, 'w')\n"
        "for line in sys.stdin:\n"
        "    out.write(line); out.flush()\n"
        "    if 'lights_off_exit' in line:\n"
        "        time.sleep(0.2); sys.exit(0)\n"
        f"time.sleep({seconds})\n", encoding="utf-8")
    runner.run(sys.executable, [str(script)], tmp_path)
    assert runner._process.waitForStarted(5000)
    t0 = time.monotonic()
    while not log.exists() and time.monotonic() - t0 < 10:
        time.sleep(0.02)          # listening before anything is asked of it
    assert log.exists()
    return log


def _wait_gone(runner, ms):
    from PyQt6.QtCore import QProcess
    proc = runner._process
    t0 = time.monotonic()
    while proc.state() != QProcess.ProcessState.NotRunning and \
            time.monotonic() - t0 < ms / 1000:
        from PyQt6.QtCore import QCoreApplication
        QCoreApplication.processEvents()
        time.sleep(0.01)
    return proc.state() == QProcess.ProcessState.NotRunning, time.monotonic() - t0


def test_off_abort_kills_at_once_and_sends_nothing(runner, tmp_path):
    log = _sleeper(runner, tmp_path)
    runner.abort()
    gone, _t = _wait_gone(runner, 3000)
    assert gone
    assert log.read_text(encoding="utf-8") == ""


def test_on_abort_asks_first_then_the_process_ends(runner, tmp_path):
    log = _sleeper(runner, tmp_path)
    runner.set_kill_courtesy('{"cmd":"lights_off_exit"}\n')
    runner.abort()
    gone, took = _wait_gone(runner, 5000)
    assert gone
    assert log.read_text(encoding="utf-8") == '{"cmd":"lights_off_exit"}\n'
    assert runner._kill_courtesy is None


def test_on_abort_still_kills_a_helper_that_does_not_answer(runner, tmp_path):
    script = tmp_path / "deaf.py"
    script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    runner.run(sys.executable, [str(script)], tmp_path)
    assert runner._process.waitForStarted(5000)
    runner.set_kill_courtesy('{"cmd":"lights_off_exit"}\n')
    runner.abort()
    gone, took = _wait_gone(runner, 6000)
    assert gone and took < 5.0


def test_the_courtesy_never_reaches_a_later_run(runner, tmp_path):
    _sleeper(runner, tmp_path)
    runner.set_kill_courtesy('{"cmd":"lights_off_exit"}\n')
    first = runner._process
    first.kill()
    first.waitForFinished(3000)
    # the next run starts clean, so its abort is a plain kill again
    second = tmp_path / "second"
    second.mkdir()
    log2 = _sleeper(runner, second)
    assert runner._process is not first and runner._kill_courtesy is None
    runner.abort()
    gone, _t = _wait_gone(runner, 3000)
    assert gone and log2.read_text(encoding="utf-8") == ""


def test_quitting_the_app_asks_first_too(runner, tmp_path):
    log = _sleeper(runner, tmp_path)
    runner.set_kill_courtesy('{"cmd":"lights_off_exit"}\n')
    runner.cleanup()
    assert log.read_text(encoding="utf-8") == '{"cmd":"lights_off_exit"}\n'


# ---------------------------------------------------------------------------
# The real helper
# ---------------------------------------------------------------------------
@needs_helper
def test_caps_name_the_lights():
    r = subprocess.run([str(HELPER), "--caps"], capture_output=True, text=True,
                       encoding="utf-8", timeout=20)
    assert "i1pro2_lights" in json.loads(r.stdout.strip())["caps"]


def _gestures_module():
    import importlib
    return importlib.import_module("test_button_gestures_engine")


@needs_helper
def test_on_changes_nothing_but_one_event_for_another_instrument(tmp_path):
    """The replay instrument is an i1Pro (Rev A-D): the same scripted session
    as the gestures golden, with --i1pro2-lights, gives the golden events plus
    one {"event":"lights","active":false,"why":"instrument"}, and the same
    .ti3 byte for byte."""
    g = _gestures_module()
    base, replay = g._chart(tmp_path)
    with ReplaySession(base, replay, extra_args=["--i1pro2-lights"]) as s:
        g._scripted_session(s)
    evs, ti3 = g._normalised(s, base)
    lights = [e for e in evs if e.get("event") == "lights"]
    assert lights == [{"event": "lights", "active": False, "why": "instrument"}]
    want = json.loads((g.GOLDEN / "events.json").read_text(encoding="utf-8"))
    assert [e for e in evs if e.get("event") != "lights"] == want
    assert ti3 + "\n" == (g.GOLDEN / "chart.ti3").read_text(encoding="latin-1")


@needs_helper
def test_off_has_no_lights_event(tmp_path):
    g = _gestures_module()
    base, replay = g._chart(tmp_path)
    with ReplaySession(base, replay) as s:
        g._scripted_session(s)
    assert not any(e.get("event") == "lights" for e in s.events)


@needs_helper
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal check")
def test_lights_off_exit_ends_the_helper_as_a_kill_would(tmp_path):
    g = _gestures_module()
    base, replay = g._chart(tmp_path)
    s = ReplaySession(base, replay, extra_args=["--i1pro2-lights"])
    try:
        s.wait_event("strip_ready")
        before = base.with_suffix(".ti3").exists()
        i = s.event_index()
        s.send(cmd="lights_off_exit")
        rc = s.proc.wait(timeout=10)
        assert rc == -9                               # SIGKILL, like abort()
        time.sleep(0.2)
        assert s.events[i:] == []                     # nothing more was said
        assert base.with_suffix(".ti3").exists() == before
    finally:
        if s.proc.poll() is None:
            s.proc.kill()
        s.proc.wait(timeout=5)


# ---------------------------------------------------------------------------
# Preferences > Beta
# ---------------------------------------------------------------------------
@pytest.fixture
def dialog(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)
    dlg = SettingsDialog(s)
    yield dlg, s
    dlg.deleteLater()


def test_the_row_is_off_and_says_what_it_does(dialog):
    from ui.tooltip_button import TooltipButton
    dlg, _s = dialog
    box = dlg._i1pro2_lights_check
    assert box.isChecked() is False
    assert "i1Pro 2" in box.text() and "(beta)" in box.text()
    tips = [b for b in dlg.findChildren(TooltipButton)
            if b._title == "i1Pro 2 Lights (beta)"]
    assert len(tips) == 1
    body = tips[0]._body
    for needed in ("white while the instrument waits for you",
                   "off while it calibrates or measures",
                   "Only for the i1Pro 2", "i1Pro 3", "ColorMunki",
                   "chart-reading engine", "Read single patches",
                   "has not been tried on a real i1Pro 2",
                   "Nobody on the ChromIQ team owns one",
                   "ArgyllCMS's own program code", "one recording",
                   "only light commands that i1Profiler was seen sending",
                   "never writes anything into the instrument's memory",
                   "switch this off, unplug the instrument",
                   "Report a Bug", "GitHub",
                   "1.  Does the white light come on",
                   "2.  Does it go off",
                   "3.  Does the same chart",
                   "4.  Does the instrument start normally about ten times",
                   "exactly as before", "**Default:** off"):
        assert needed in body, needed
    assert "—" not in body and "—" not in box.text()


def _answer(monkeypatch, button):
    from PyQt6.QtWidgets import QMessageBox
    seen = {}

    def fake_exec(self):
        seen["text"] = self.text()
        seen["default"] = self.defaultButton()
        seen["buttons"] = [b.text() for b in self.buttons()]
        return button
    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    return seen


def test_switching_on_asks_and_cancel_keeps_it_off(dialog, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    dlg, s = dialog
    seen = _answer(monkeypatch, QMessageBox.StandardButton.Cancel)
    dlg._i1pro2_lights_check.click()
    assert dlg._i1pro2_lights_check.isChecked() is False
    assert "own risk" in seen["text"] and "not been tried" in seen["text"]
    assert "—" not in seen["text"]
    assert seen["default"] is not None and \
        seen["default"].text() == "Leave them off"
    dlg._save_and_close()
    assert s.get("i1pro2_lights_beta") is False


def test_switching_on_and_confirming_saves_it(dialog, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    dlg, s = dialog
    _answer(monkeypatch, QMessageBox.StandardButton.Ok)
    dlg._i1pro2_lights_check.click()
    assert dlg._i1pro2_lights_check.isChecked() is True
    dlg._save_and_close()
    assert s.get("i1pro2_lights_beta") is True
    # switching it off asks nothing
    called = _answer(monkeypatch, QMessageBox.StandardButton.Cancel)
    dlg._i1pro2_lights_check.click()
    assert dlg._i1pro2_lights_check.isChecked() is False and called == {}

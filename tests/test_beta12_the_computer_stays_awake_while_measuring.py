"""Beta 12, Basti #182 6015495063: the computer does not sleep (display and
system) while a measurement runs, and is allowed to again the moment it ends,
whatever ended it. ``core/keep_awake.py``; hooked in ``MeasureManager.start``.

Fakes only: the suite sets CHROMIQ_NO_KEEP_AWAKE, so no test holds the Mac
awake; the real assertion is proved on screen with ``pmset -g assertions``.
"""
from __future__ import annotations

import subprocess

import pytest

from core import keep_awake as KA


class FakeProc:
    def __init__(self, cmd, **_kw):
        self.cmd = cmd
        self.alive = True
        self.terminated = False

    def poll(self):
        return None if self.alive else 0

    def terminate(self):
        self.terminated = True
        self.alive = False

    def kill(self):
        self.alive = False

    def wait(self, timeout=None):
        return 0


class Popen:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, **kw):
        p = FakeProc(cmd, **kw)
        self.calls.append(p)
        return p


class Kernel32:
    def __init__(self):
        self.calls = []

    def SetThreadExecutionState(self, flags):  # noqa: N802 - the Win32 name
        self.calls.append(flags)
        return 0x80000000


def _ka(platform, **kw):
    kw.setdefault("environ", {})
    kw.setdefault("pid", 4242)
    return KA.KeepAwake(platform, **kw)


def test_macos_holds_caffeinate_on_the_apps_pid_and_releases_it():
    pop = Popen()
    ka = _ka("darwin", popen=pop, which=lambda n: f"/usr/bin/{n}")
    assert ka.hold() is True and ka.active
    assert pop.calls[0].cmd == ["/usr/bin/caffeinate", "-d", "-i", "-w", "4242"]
    assert ka.hold() is True and len(pop.calls) == 1        # idempotent
    ka.release()
    assert pop.calls[0].terminated and not ka.active
    ka.release()                                            # harmless


def test_windows_sets_and_clears_the_execution_state():
    k = Kernel32()
    ka = _ka("win32", kernel32=k)
    assert ka.hold() is True and ka.active
    assert k.calls == [KA.ES_CONTINUOUS | KA.ES_SYSTEM_REQUIRED
                       | KA.ES_DISPLAY_REQUIRED]
    ka.release()
    assert k.calls[-1] == KA.ES_CONTINUOUS and not ka.active


def test_linux_uses_systemd_inhibit_when_there_is_one():
    pop = Popen()
    ka = _ka("linux", popen=pop, which=lambda n: f"/usr/bin/{n}")
    assert ka.hold()
    cmd = pop.calls[0].cmd
    assert cmd[0] == "/usr/bin/systemd-inhibit" and "--what=idle:sleep" in cmd
    assert "--pid=4242" in cmd
    ka.release()
    assert not ka.active


def test_linux_without_systemd_inhibit_is_a_no_op():
    pop = Popen()
    ka = _ka("linux", popen=pop, which=lambda n: None)
    assert ka.hold() is False and pop.calls == [] and not ka.active
    ka.release()


def test_switched_off_by_the_environment():
    pop = Popen()
    ka = _ka("darwin", popen=pop, which=lambda n: n,
             environ={"CHROMIQ_NO_KEEP_AWAKE": "1"})
    assert ka.hold() is False and pop.calls == []


def test_a_failure_never_stops_a_measurement():
    def boom(*_a, **_k):
        raise OSError("no caffeinate")
    ka = _ka("darwin", popen=boom, which=lambda n: n)
    assert ka.hold() is False and not ka.active
    ka.release()


def test_the_suite_never_holds_the_real_mac_awake():
    import os
    assert os.environ.get("CHROMIQ_NO_KEEP_AWAKE") == "1"


# ---- the measurement session holds it and every ending releases it ----------

class Recorder:
    def __init__(self):
        self.events = []

    def hold(self):
        self.events.append("hold")
        return True

    def release(self):
        self.events.append("release")


def _wrap(fn):
    from workflow.measure_manager import _keeps_the_computer_awake
    return _keeps_the_computer_awake(fn)


def test_the_real_start_is_wrapped():
    from workflow.measure_manager import MeasureManager
    assert MeasureManager.start.__wrapped__.__name__ == "start"


@pytest.fixture
def manager(monkeypatch):
    from workflow import measure_manager as MM
    rec = Recorder()
    monkeypatch.setattr(KA, "keep_awake", rec)
    m = MM.MeasureManager.__new__(MM.MeasureManager)
    return m, rec


def test_a_session_holds_until_its_finish_whatever_the_code(manager, monkeypatch):
    m, rec = manager
    got = {}

    def fake_start(self, params, on_line, on_finish):
        got["finish"] = on_finish
    monkeypatch.setattr(type(m), "start", _wrap(fake_start))
    for code in (0, 1, -1):
        rec.events.clear()
        seen = []
        m.start(object(), lambda _l: None, seen.append)
        assert rec.events == ["hold"]
        got["finish"](code)
        assert seen == [code] and rec.events == ["hold", "release"]


def test_released_even_when_the_callers_finish_raises(manager, monkeypatch):
    m, rec = manager
    got = {}
    monkeypatch.setattr(type(m), "start", _wrap(
        lambda self, p, l, f: got.setdefault("finish", f)))

    def bad(_code):
        raise RuntimeError("tab code failed")
    m.start(object(), lambda _l: None, bad)
    with pytest.raises(RuntimeError):
        got["finish"](0)
    assert rec.events == ["hold", "release"]


def test_released_when_the_start_itself_fails(manager, monkeypatch):
    m, rec = manager

    def boom(self, *_a):
        raise ValueError("bad params")
    monkeypatch.setattr(type(m), "start", _wrap(boom))
    with pytest.raises(ValueError):
        m.start(object(), lambda _l: None, lambda _c: None)
    assert rec.events == ["hold", "release"]


def test_the_real_caffeinate_command_exists_on_macos():
    import shutil
    import sys
    if sys.platform != "darwin":
        pytest.skip("macOS only")
    assert shutil.which("caffeinate") or subprocess.os.path.exists(
        "/usr/bin/caffeinate")


def test_released_before_the_callers_finish_opens_its_windows(manager,
                                                              monkeypatch):
    """Beta-12 review: the Measure tab's finish opens end-of-measurement
    windows with exec() (no instrument, disconnected, the summary). The
    hold must already be gone while such a window waits for the user, or a
    failed read left overnight keeps the display and the Mac awake."""
    m, rec = manager
    got = {}
    monkeypatch.setattr(type(m), "start", _wrap(
        lambda self, p, l, f: got.setdefault("finish", f)))
    seen = []

    def finish(code):
        seen.append(list(rec.events))      # what was held while it ran
    m.start(object(), lambda _l: None, finish)
    got["finish"](1)
    assert seen == [["hold", "release"]]


def test_a_finish_that_starts_the_next_session_keeps_it_held(manager,
                                                             monkeypatch):
    m, rec = manager
    finishes = []
    monkeypatch.setattr(type(m), "start", _wrap(
        lambda self, p, l, f: finishes.append(f)))

    def finish(_code):
        if len(finishes) == 1:
            m.start(object(), lambda _l: None, lambda _c: None)
    m.start(object(), lambda _l: None, finish)
    finishes[0](0)
    assert rec.events == ["hold", "release", "hold"]

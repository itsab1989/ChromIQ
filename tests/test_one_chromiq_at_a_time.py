"""4.3.59: one ChromIQ at a time, per settings store (core/single_instance.py).

A tester's logs showed two ChromIQ windows open on the same project for 23 minutes (Windows,
where a second double-click starts a second process). A second start now asks the first to
come to the front and quits before it builds a window or opens the settings.

Pinned here, with the first instance in a REAL second process:
* a second claim on the same lock gets "already running" and sends the show request, and the
  first one receives it;
* a lock left by a ChromIQ that died does not block the next start;
* a first instance that holds the lock but cannot be reached gives UNREACHABLE (the one case
  with a message), and does so quickly;
* a sandboxed settings file (CHROMIQ_SETTINGS_FILE) has its own lock, so a driver never meets
  the user's own ChromIQ, either way round;
* main() claims before the settings and before any window, and names the window after it is
  built; the suite and the drivers never call main().
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

FIRST_SCRIPT = r'''
import os, sys, time
sys.path.insert(0, {root!r})
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtCore import QCoreApplication, QTimer
app = QCoreApplication(sys.argv)
from core import single_instance as si
mode = sys.argv[2]
lock = sys.argv[1]
if mode == "serve":
    outcome, guard = si.claim(si.Path(lock))
    print("OUTCOME", outcome, flush=True)
    seen = [0]
    def poll():
        if guard.requests != seen[0]:
            seen[0] = guard.requests
            print("REQUEST", guard.requests, "PENDING", guard.pending, flush=True)
    t = QTimer(); t.timeout.connect(poll); t.start(20)
    QTimer.singleShot(int(float(sys.argv[3]) * 1000), app.quit)
    print("READY", flush=True)
    app.exec()
    guard.release()
elif mode == "hold":          # the lock only, no server, then sleep: a hung first instance
    from PyQt6.QtCore import QLockFile
    lf = QLockFile(lock); lf.setStaleLockTime(0)
    print("LOCKED", lf.tryLock(0), flush=True)
    time.sleep(float(sys.argv[3]))
elif mode == "crash":         # take the lock and die without letting it go
    from PyQt6.QtCore import QLockFile
    lf = QLockFile(lock); lf.setStaleLockTime(0)
    print("LOCKED", lf.tryLock(0), flush=True)
    os._exit(0)
'''


def _start(tmp_path, lock: Path, mode: str, seconds: float = 20.0) -> subprocess.Popen:
    script = tmp_path / "first_instance.py"
    script.write_text(FIRST_SCRIPT.format(root=str(ROOT)), encoding="utf-8")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    return subprocess.Popen([sys.executable, str(script), str(lock), mode, str(seconds)],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                            encoding="utf-8", env=env, cwd=str(tmp_path))


def _read_until(proc: subprocess.Popen, word: str, timeout: float = 30.0) -> "list[str]":
    lines, end = [], time.monotonic() + timeout
    while time.monotonic() < end:
        ln = proc.stdout.readline()
        if not ln:
            break
        lines.append(ln.strip())
        if ln.startswith(word):
            return lines
    raise AssertionError(f"no {word!r} from the first instance: {lines}")


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=10)
    if proc.stdout is not None:
        proc.stdout.close()


def test_a_second_start_asks_the_first_to_come_to_the_front(qapp, tmp_path):
    from core import single_instance as si
    lock = tmp_path / "chromiq.lock"
    first = _start(tmp_path, lock, "serve")
    try:
        lines = _read_until(first, "READY")
        assert "OUTCOME first" in lines
        outcome, guard = si.claim(lock)
        assert outcome == si.SHOWN_OTHER and guard is None
        got = _read_until(first, "REQUEST")
        # no window named yet in that process: the request waits for it
        assert got[-1] == "REQUEST 1 PENDING True"
    finally:
        _stop(first)


def test_a_lock_left_by_a_chromiq_that_died_does_not_block(qapp, tmp_path):
    from core import single_instance as si
    lock = tmp_path / "chromiq.lock"
    dead = _start(tmp_path, lock, "crash")
    try:
        assert _read_until(dead, "LOCKED") == ["LOCKED True"]
        dead.wait(timeout=30)
    finally:
        _stop(dead)
    assert lock.exists(), "the dead process should have left its lock behind"
    outcome, guard = si.claim(lock)
    try:
        assert outcome == si.FIRST and guard is not None
    finally:
        guard.release()


def test_a_first_instance_that_cannot_be_reached_is_said_quickly(qapp, tmp_path):
    from core import single_instance as si
    lock = tmp_path / "chromiq.lock"
    holder = _start(tmp_path, lock, "hold", 30)
    try:
        assert _read_until(holder, "LOCKED") == ["LOCKED True"]
        t0 = time.monotonic()
        outcome, guard = si.claim(lock)
        took = time.monotonic() - t0
        assert outcome == si.UNREACHABLE and guard is None
        assert took < (si.CONNECT_MS + si.REPLY_MS) / 1000.0 + 2.0
    finally:
        _stop(holder)


def test_the_running_first_instance_answers_every_later_start(qapp, tmp_path):
    from core import single_instance as si
    lock = tmp_path / "chromiq.lock"
    first = _start(tmp_path, lock, "serve")
    try:
        _read_until(first, "READY")
        for n in (1, 2):
            assert si.claim(lock)[0] == si.SHOWN_OTHER
            assert _read_until(first, "REQUEST")[-1].startswith(f"REQUEST {n} ")
    finally:
        _stop(first)


def test_a_sandboxed_settings_file_has_its_own_lock(monkeypatch, tmp_path):
    from core import single_instance as si
    from core.settings import SETTINGS_FILE_ENV
    monkeypatch.setenv("CHROMIQ_LOG_DIR", str(tmp_path / "logs"))
    real = si.lock_path({})
    sandbox = tmp_path / "driver.ini"
    boxed = si.lock_path({SETTINGS_FILE_ENV: str(sandbox)})
    assert real == tmp_path / "logs" / "chromiq-instance.lock"
    assert boxed == tmp_path / "driver.ini.chromiq-instance.lock"
    # never QSettings' own lock of the .ini file: holding that hangs every settings write
    assert boxed != tmp_path / "driver.ini.lock"
    assert si.server_name(real) != si.server_name(boxed)
    # the same sandbox file twice is one store, so one lock
    assert si.lock_path({SETTINGS_FILE_ENV: str(sandbox)}) == boxed


def test_a_driver_on_a_sandbox_is_not_blocked_by_the_real_store(qapp, tmp_path, monkeypatch):
    """The user's own ChromIQ holds the real store's lock; a driver with a sandboxed file
    starts as a first instance, and the user's ChromIQ is not asked anything."""
    from core import single_instance as si
    from core.settings import SETTINGS_FILE_ENV
    monkeypatch.setenv("CHROMIQ_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.delenv(SETTINGS_FILE_ENV, raising=False)
    (tmp_path / "logs").mkdir()
    users = _start(tmp_path, si.lock_path(), "serve")
    try:
        _read_until(users, "READY")
        monkeypatch.setenv(SETTINGS_FILE_ENV, str(tmp_path / "driver.ini"))
        outcome, guard = si.claim()
        try:
            assert outcome == si.FIRST
        finally:
            guard.release()
        users.kill()
        rest = users.stdout.read()
        assert "REQUEST" not in rest
    finally:
        _stop(users)


def test_the_window_is_brought_up_un_minimised(qapp, tmp_path):
    from PyQt6.QtCore import QLockFile, Qt
    from PyQt6.QtWidgets import QWidget
    from core import single_instance as si
    win = QWidget()
    try:
        win.show()
        win.setWindowState(Qt.WindowState.WindowMinimized)
        g = si.Guard(QLockFile(str(tmp_path / "x.lock")), None, "x")
        g.pending = True
        g.set_window(win)           # a request that came before the window
        assert not (win.windowState() & Qt.WindowState.WindowMinimized)
        assert win.isVisible() and g.pending is False
    finally:
        win.close()
        win.deleteLater()


def test_main_claims_before_the_settings_and_any_window():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    body = src[src.index("def main() -> int:"):]
    claim = body.index("single_instance.claim()")
    assert body.index("pin_c_numeric_locale()") < claim      # a message box is safe then
    for later in ("AppSettings()", "make_splash(", "MainWindow(settings)"):
        assert claim < body.index(later), later
    assert body.index("MainWindow(settings)") < body.index("_instance_guard.set_window(win)")
    assert "single_instance.tell_already_running()" in body


def test_nothing_but_main_claims():
    """The suite and the on-screen drivers never take the lock."""
    for folder in ("core", "ui", "workflow", "scripts"):
        for f in (ROOT / folder).rglob("*.py"):
            if f.name == "single_instance.py":
                continue
            assert "single_instance" not in f.read_text(encoding="utf-8", errors="replace"), f
    assert "single_instance" not in (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")


def test_the_message_is_translated_everywhere():
    import json
    for f in sorted((ROOT / "data" / "i18n").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        assert d.get("ChromIQ is already running."), f.name
        assert "—" not in d["ChromIQ is already running."]


def test_the_guard_never_holds_the_settings_files_own_lock(qapp, tmp_path, monkeypatch):
    """QSettings locks an .ini file as "<file>.lock" while it writes it. The first build of
    this guard used that very name for a sandboxed store, and the app's first settings
    write then waited for ever (found on the on-screen run, 2026-11-23). With the guard
    held, another process still writes the same settings file at once."""
    from core import single_instance as si
    from core.settings import SETTINGS_FILE_ENV
    ini = tmp_path / "driver.ini"
    monkeypatch.setenv(SETTINGS_FILE_ENV, str(ini))
    outcome, guard = si.claim()
    try:
        assert outcome == si.FIRST
        code = ("import sys; from PyQt6.QtCore import QSettings; "
                "s = QSettings(sys.argv[1], QSettings.Format.IniFormat); "
                "s.setValue('k', 1); s.sync(); print('SYNCED', s.status().name)")
        try:
            r = subprocess.run([sys.executable, "-c", code, str(ini)], capture_output=True,
                               text=True, encoding="utf-8", timeout=60)
        except subprocess.TimeoutExpired:
            raise AssertionError("a settings write waited for the guard's lock") from None
        assert "SYNCED NoError" in r.stdout, r.stdout + r.stderr
    finally:
        guard.release()

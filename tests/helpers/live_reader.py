"""A REAL instrument at the far end of a REAL pty, for the windows that send keys.

B8-389. Three fixes in `ui/tabs/tab_measure.py` decide **which byte leaves
ChromIQ** when a measurement window is answered, and the path that carries that
byte is `MeasureManager.send_key` -> `ArgyllRunner.write_stdin` ->
``os.write(self._pty_master, ...)``. A guard that stops short of the pty is
guarding a method call, not a keystroke, so this puts the real thing underneath
the tab:

* a real ``os.openpty()`` pair, with the master wired into the real
  ``ArgyllRunner._pty_master`` -- so ``write_stdin`` takes its pty branch, the
  same branch a real chartread is driven through;
* a **real live child** holding the slave, because ``ArgyllRunner.is_running``
  asks ``self._pty_proc.poll() is None``. Without a live child it is False,
  ``TabMeasure._send_failure_choice`` early-returns with *"measurement already
  ended; not sending"*, and nothing is sent at all -- so the R23-F4 mutation
  could not land and a guard would pass over the fault it was written for;
* **raw mode on the slave**, which is the half round 23's own stand-in got
  wrong. Measured here both ways: with the default line discipline an Escape
  written to the master is still invisible at the far end 200 ms later (ICANON
  holds it until a newline completes the line), and in raw mode it arrives at
  once. That is enough to prove a fault -- a byte that arrives late still
  arrived -- and it is **not** enough to prove a fix, because a run in which
  nothing is seen might be a run in which a byte is merely sitting in a buffer.
  Real chartread reads one character at a time in raw mode (chartread.c:1611,
  :1654, :1857), so this does too.

The direction under test is ChromIQ -> instrument. Nothing here parses output,
so the runner's reader thread is deliberately not started: what a guard needs
from the manager's state (``_read_something``, ``_readings_count``) is set on
the real manager directly, as `tests/test_knut_beta118_stop_keeps_readings.py`
already does.
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import termios
import time
import tty

#: A child that is alive and does not read its stdin, so every byte ChromIQ
#: writes stays in the pty for this process to read. `is_running` only asks
#: whether it is alive.
_IDLE_CHILD = "import time; time.sleep(600)"


class LiveReader:
    """The far end of `ArgyllRunner`'s pty: a live process and a readable fd."""

    def __init__(self, runner) -> None:
        self._runner = runner
        self.master, self.slave = os.openpty()
        # RAW MODE. See this module's docstring -- without it a guard cannot
        # tell "nothing was sent" from "a byte is waiting for a newline".
        tty.setraw(self.slave, termios.TCSANOW)
        self.proc = subprocess.Popen(
            [sys.executable, "-c", _IDLE_CHILD],
            stdin=self.slave,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        os.set_blocking(self.slave, False)
        runner._pty_master = self.master
        runner._pty_proc = self.proc
        self._closed = False

    # -- what left ChromIQ -------------------------------------------------
    def read_all(self) -> bytes:
        """Every byte written to the pty since the last :meth:`forget`."""
        seen = b""
        while True:
            try:
                chunk = os.read(self.slave, 4096)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                break
            if not chunk:
                break
            seen += chunk
        return seen

    def forget(self) -> None:
        """Drop whatever is waiting, so the next read describes one gesture."""
        self.read_all()

    def wait_for_a_byte(self, timeout: float = 1.0) -> bytes:
        """Read until something arrives or *timeout* passes.

        A guard asserting that NOTHING arrived still has to wait: a write that
        has not happened yet and a write that never happens look identical at
        t=0. This one returns as soon as the first byte lands, so the fast case
        stays fast and the empty case pays the whole timeout once.
        """
        deadline = time.monotonic() + float(timeout)
        seen = b""
        while True:
            seen += self.read_all()
            if seen or time.monotonic() >= deadline:
                return seen
            time.sleep(0.01)

    # -- the reader's own state -------------------------------------------
    @property
    def alive(self) -> bool:
        return self.proc.poll() is None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._runner._pty_proc is self.proc:
            self._runner._pty_proc = None
        if self._runner._pty_master == self.master:
            self._runner._pty_master = None
        try:
            self.proc.kill()
            self.proc.wait(timeout=5)
        except OSError:
            pass
        for fd in (self.slave, self.master):
            try:
                os.close(fd)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# The tab, in the state `_on_start` leaves it in
# ---------------------------------------------------------------------------
#: The statements `TabMeasure._on_start` executes to make a session live.
#: `a_live_session` reproduces them rather than pressing Start, because Start
#: also needs a project, a laid-out chart and a real ArgyllCMS on disk --
#: `test_the_harness_starts_the_session_the_way_the_app_does` is what keeps the
#: pair honest, and fails if the app ever starts a session some other way.
THE_LINES_THAT_START_A_SESSION = (
    "self._stop_btn.setEnabled(True)",
    "self._session_live = True",
    "QApplication.instance().installEventFilter(self)",
)


def a_live_session(tmp_path, *, readings: int = 16):
    """A real `TabMeasure` with a real reader on the far end of a real pty.

    Returns ``(tab, reader)``; the caller must call :func:`end_the_session`.
    Use :func:`measuring` unless you need the pieces apart.

    STOCK chartread, deliberately: on the engine a key is translated into a
    JSON command (`MeasureManager.send_key` -> `command_for_key`), and the
    three fixes under guard are about the *byte* a window sends.
    """
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("chartread_engine", "argyll")
    runner = ArgyllRunner(s)
    tab = TabMeasure(runner, s)
    reader = LiveReader(runner)
    # The real manager's real state, as a session that has read a strip holds
    # it: `has_unsaved_readings` is what decides between M-END and M-END-EMPTY.
    tab._manager._read_something = True
    tab._manager._readings_count = int(readings)
    tab._stop_btn.setEnabled(True)
    tab._session_live = True
    QApplication.instance().installEventFilter(tab)
    return tab, reader


def end_the_session(tab, reader) -> None:
    """Put the application back as it was.

    The event filter is installed on the WHOLE APPLICATION, so a guard that
    leaves it behind eats arrow keys in every test that runs after it in the
    same worker -- which is the very fault
    `test_knut_beta119_shortcuts_are_not_instrument_keys.py` was written for.
    """
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None:
        app.removeEventFilter(tab)
    tab._session_live = False
    try:
        tab._key_watchdog.stop()
    except RuntimeError:
        pass
    reader.close()


@contextlib.contextmanager
def measuring(tmp_path, *, readings: int = 16):
    tab, reader = a_live_session(tmp_path, readings=readings)
    try:
        yield tab, reader
    finally:
        end_the_session(tab, reader)


def describe(w) -> str:
    """What to call the window on screen.

    **A QMessageBox has no window title on macOS.** `setWindowTitle` is a
    documented no-op there, so `windowTitle()` comes back empty for every one
    of ChromIQ's ending windows and a guard keyed on it would be asserting
    ``""`` against ``""`` on Linux and Windows too. The first line of the box's
    own text is what the user reads, and ChromIQ sets it to the same string.
    """
    title = w.windowTitle()
    if title:
        return title
    text = getattr(w, "text", None)
    if callable(text):
        return str(text() or "").split("\n", 1)[0].strip()
    return ""


class WindowDriver:
    """Do something to ChromIQ's window while it is up, and never hang.

    Every one of these windows blocks in its own ``exec()``, so the gesture has
    to come from a timer inside that event loop. The rescue matters as much as
    the gesture: when a key is EATEN rather than delivered -- which is exactly
    what the R23-F2 fault did -- the window stays up and ``exec()`` never
    returns, so without a rescue the mutation would hang the run instead of
    failing it. :attr:`stuck` records that it had to step in, and a guard that
    asserts on it reads the fault as a red test rather than a timeout.
    """

    def __init__(self, act, *, settle_ms: int = 1200, give_up_ms: int = 8000):
        self.act = act
        #: Title of the window the gesture was made at, or None if none came.
        self.acted_on: "str | None" = None
        #: True when the window was still up `settle_ms` after the gesture, so
        #: this driver had to close it. A window that answers its own key
        #: closes itself and never sets this.
        self.stuck = False
        self._settle = settle_ms / 1000.0
        self._give_up = give_up_ms / 1000.0
        #: The window itself, still readable after `exec()` has returned --
        #: which is how a guard asks WHICH BUTTON fired.
        self.window = None
        self._acted_at = 0.0
        self._timer = None
        self._started = 0.0

    def arm(self) -> "WindowDriver":
        from PyQt6.QtCore import QTimer

        self._started = time.monotonic()
        self._timer = QTimer()
        self._timer.setInterval(25)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        return self

    def disarm(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _tick(self) -> None:
        from PyQt6.QtWidgets import QApplication

        modal = QApplication.instance().activeModalWidget()
        if self.window is None:
            if modal is None:
                if time.monotonic() - self._started > self._give_up:
                    self.disarm()
                return
            self.window = modal
            self.acted_on = describe(modal)
            self._acted_at = time.monotonic()
            self.act(modal)
            return
        if modal is self.window and \
                time.monotonic() - self._acted_at > self._settle:
            self.stuck = True
            self.disarm()
            try:
                self.window.reject()
            except (AttributeError, RuntimeError):
                self.window.close()
            return
        if modal is not self.window:
            self.disarm()

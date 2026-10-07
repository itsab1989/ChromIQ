"""Keep the computer awake while a measurement runs (Basti, #182 6015495063).

*"Would it be possible to prevent the computer from going to sleep while a
measurement is running (display and full standby)?"* A measurement can take
an hour of strips with pauses between them; a display that goes dark or a Mac
that sleeps in a pause loses the instrument's connection and the user's place.

One process-wide :data:`keep_awake`, held by ``MeasureManager.start`` and
released by the same session's finish, whatever ended it (done, failed,
stopped, refused). It can never outlive the app:

* **macOS**: ``caffeinate -d -i -w <ChromIQ's pid>`` (display and idle system
  sleep). ``-w`` makes caffeinate end by itself when ChromIQ ends, crash
  included, so no assertion is ever left behind; ``pmset -g assertions``
  lists it while it is held.
* **Windows**: ``SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED |
  ES_DISPLAY_REQUIRED)``, and ``ES_CONTINUOUS`` alone to release. Windows
  drops the state with the thread that set it, so it cannot leak either.
* **Linux**, best effort: ``systemd-inhibit --what=idle:sleep`` around a
  ``tail --pid=<pid>`` that ends with ChromIQ. Without systemd-inhibit,
  nothing (and the log says so once).

Every call is idempotent: hold twice, release once, and it is released;
release with nothing held does nothing. A failure is logged and never stops a
measurement. ``CHROMIQ_NO_KEEP_AWAKE=1`` turns it off (the test suite sets it,
so a test run never holds Basti's Mac awake).
"""
from __future__ import annotations

import atexit
import logging
import os
import shutil
import subprocess
import sys

log = logging.getLogger(__name__)

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

REASON = "ChromIQ: a measurement is running"


class KeepAwake:
    """Holds the platform's keep-awake while a measurement runs."""

    def __init__(self, platform: "str | None" = None, *, popen=None,
                 which=None, kernel32=None, pid: "int | None" = None,
                 environ=None) -> None:
        self._platform = platform or sys.platform
        self._popen = popen or subprocess.Popen
        self._which = which or shutil.which
        self._kernel32 = kernel32
        self._pid = pid if pid is not None else os.getpid()
        self._environ = os.environ if environ is None else environ
        self._proc = None
        self._win_held = False
        self._warned = False

    @property
    def active(self) -> bool:
        if self._win_held:
            return True
        return self._proc is not None and self._proc.poll() is None

    def _disabled(self) -> bool:
        return str(self._environ.get("CHROMIQ_NO_KEEP_AWAKE", "")).strip() \
            not in ("", "0")

    def _command(self) -> "list[str] | None":
        pid = str(self._pid)
        if self._platform == "darwin":
            exe = self._which("caffeinate") or "/usr/bin/caffeinate"
            return [exe, "-d", "-i", "-w", pid]
        if self._platform.startswith("linux"):
            inhibit = self._which("systemd-inhibit")
            tail = self._which("tail")
            if not inhibit or not tail:
                return None
            return [inhibit, "--what=idle:sleep", "--who=ChromIQ",
                    f"--why={REASON}", "--mode=block",
                    tail, f"--pid={pid}", "-f", "/dev/null"]
        return None

    def _k32(self):
        if self._kernel32 is None:
            import ctypes
            self._kernel32 = ctypes.windll.kernel32   # type: ignore[attr-defined]
        return self._kernel32

    def hold(self) -> bool:
        """Keep the display and the system awake; True when it is held."""
        if self.active:
            return True
        if self._disabled():
            return False
        try:
            if self._platform == "win32":
                ok = self._k32().SetThreadExecutionState(
                    ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
                self._win_held = bool(ok)
                if self._win_held:
                    log.info("Keeping the computer awake while measuring "
                             "(SetThreadExecutionState).")
                return self._win_held
            cmd = self._command()
            if cmd is None:
                if not self._warned:
                    self._warned = True
                    log.info("Cannot keep the computer awake while measuring "
                             "on this system (no caffeinate/systemd-inhibit).")
                return False
            self._proc = self._popen(
                cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            log.info("Keeping the computer awake while measuring: %s",
                     " ".join(cmd))
            return True
        except Exception:      # noqa: BLE001 - never stops a measurement
            log.warning("Could not keep the computer awake", exc_info=True)
            self._proc = None
            self._win_held = False
            return False

    def release(self) -> None:
        """Let the computer sleep again. Safe to call at any time."""
        if self._win_held:
            self._win_held = False
            try:
                self._k32().SetThreadExecutionState(ES_CONTINUOUS)
                log.info("The computer may sleep again (measurement over).")
            except Exception:  # noqa: BLE001
                log.warning("Could not release the keep-awake", exc_info=True)
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
            log.info("The computer may sleep again (measurement over).")
        except Exception:      # noqa: BLE001
            log.warning("Could not release the keep-awake", exc_info=True)


#: The one the app uses.
keep_awake = KeepAwake()
atexit.register(keep_awake.release)

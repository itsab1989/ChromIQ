"""QProcess wrapper for ArgyllCMS tool execution."""
from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, pyqtSignal

from core.line_flood import RepeatGate
from core.logger import get_logger
from core.printtarg_env import is_printtarg, printtarg_env_additions
from core.proc_text import decode_output
from core.resource_path import argyll_binary

if sys.platform != "win32":
    import pty
    import select

if TYPE_CHECKING:
    from core.settings import AppSettings

log = get_logger(__name__)


# The serial-port exclusion (ARGYLL_EXCLUDE_SERIAL_SCAN) lives in
# core/argyll_env.py, so that every launch path shares it; these names are
# re-exported here for the callers and tests that have always imported them.
from core.argyll_env import (  # noqa: E402,F401
    _phantom_serial_ports, _read_serialcomm, _windows_bluetooth_com_ports,
    argyll_env, argyll_serial_exclusion_ports, merged_serial_exclusion,
    serial_exclusion_value)

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

if sys.platform == "win32":
    import ctypes as _ct
    import ctypes.wintypes as _wt

    _VK_MAP: dict[str, tuple[int, int]] = {
        '\r':   (0x0D, 0x1C),
        '\n':   (0x0D, 0x1C),
        '\x1b': (0x1B, 0x01),
        ' ':    (0x20, 0x39),
    }

    # Pointer-sized sentinel; HANDLE is c_void_p, so -1 → 0xFFFFFFFFFFFFFFFF on 64-bit.
    _INVALID_HANDLE_VALUE = _ct.c_void_p(-1).value

    # Bind argtypes/restype once so ctypes does not silently truncate handles
    # (HANDLE is pointer-sized; the default c_int return type loses the high
    # 32 bits on 64-bit Windows and the invalid-handle check then misfires).
    _k32 = _ct.windll.kernel32
    _k32.AttachConsole.argtypes       = [_wt.DWORD]
    _k32.AttachConsole.restype        = _wt.BOOL
    _k32.FreeConsole.argtypes         = []
    _k32.FreeConsole.restype          = _wt.BOOL
    _k32.GetLastError.argtypes        = []
    _k32.GetLastError.restype         = _wt.DWORD
    _k32.CreateFileW.argtypes         = [
        _wt.LPCWSTR, _wt.DWORD, _wt.DWORD,
        _ct.c_void_p, _wt.DWORD, _wt.DWORD, _wt.HANDLE,
    ]
    _k32.CreateFileW.restype          = _wt.HANDLE
    _k32.WriteConsoleInputW.argtypes  = [
        _wt.HANDLE, _ct.c_void_p, _wt.DWORD, _ct.POINTER(_wt.DWORD),
    ]
    _k32.WriteConsoleInputW.restype   = _wt.BOOL
    _k32.CloseHandle.argtypes         = [_wt.HANDLE]
    _k32.CloseHandle.restype          = _wt.BOOL
    _k32.SetStdHandle.argtypes        = [_wt.DWORD, _wt.HANDLE]
    _k32.SetStdHandle.restype         = _wt.BOOL

    # Cast negative STD_*_HANDLE constants to unsigned DWORD.
    _STD_INPUT_HANDLE  = _wt.DWORD(-10).value
    _STD_OUTPUT_HANDLE = _wt.DWORD(-11).value
    _STD_ERROR_HANDLE  = _wt.DWORD(-12).value

    def _win_reset_std_handles() -> None:
        # After FreeConsole, the parent's std handles point at a freed console
        # buffer. subprocess.run then fails with WinError 6 (invalid handle)
        # when it tries to inherit them. Clearing to NULL restores the same
        # state a no-console --windowed app starts with, which Python handles
        # gracefully.
        _k32.SetStdHandle(_STD_INPUT_HANDLE,  None)
        _k32.SetStdHandle(_STD_OUTPUT_HANDLE, None)
        _k32.SetStdHandle(_STD_ERROR_HANDLE,  None)

    def _win_inject_key(pid: int, text: str) -> bool:
        """Inject text[0] into the console of process `pid` via WriteConsoleInputW.

        Uses AttachConsole so we share the child's CONIN$ input buffer —
        the same buffer MSVCRT's _getch() reads from. Returns True on success,
        False if the keystroke could not be delivered (AttachConsole denied,
        CONIN$ open failed, or WriteConsoleInputW did not write both events).
        """
        if not text:
            return False
        ch = text[0]
        vk, scan = _VK_MAP.get(ch, (ord(ch.upper()) if ch.isalpha() else 0, 0))

        class _CharUnion(_ct.Union):
            _fields_ = [("UnicodeChar", _wt.WCHAR), ("AsciiChar", _ct.c_char)]

        class _KeyEvent(_ct.Structure):
            _fields_ = [
                ("bKeyDown",          _wt.BOOL),
                ("wRepeatCount",      _wt.WORD),
                ("wVirtualKeyCode",   _wt.WORD),
                ("wVirtualScanCode",  _wt.WORD),
                ("uChar",             _CharUnion),
                ("dwControlKeyState", _wt.DWORD),
            ]

        class _InputRecord(_ct.Structure):
            class _U(_ct.Union):
                _fields_ = [("KeyEvent", _KeyEvent)]
            _anonymous_ = ("_u",)
            _fields_ = [("EventType", _wt.WORD), ("_u", _U)]

        k32 = _k32
        k32.FreeConsole()
        _win_reset_std_handles()
        if not k32.AttachConsole(pid):
            err = k32.GetLastError()
            log.warning("_win_inject_key: AttachConsole(%d) failed (err %d)", pid, err)
            return False
        ok_full = False
        try:
            h = k32.CreateFileW(
                r"\\.\CONIN$",
                0xC0000000,   # GENERIC_READ | GENERIC_WRITE
                0x3,          # FILE_SHARE_READ | FILE_SHARE_WRITE
                None, 3, 0, None,
            )
            if not h or h == _INVALID_HANDLE_VALUE:
                err = k32.GetLastError()
                log.warning("_win_inject_key: CONIN$ open failed (err %d)", err)
                return False
            try:
                recs = (_InputRecord * 2)()
                for i, down in enumerate((True, False)):
                    recs[i].EventType                   = 1   # KEY_EVENT
                    recs[i].KeyEvent.bKeyDown            = _wt.BOOL(down)
                    recs[i].KeyEvent.wRepeatCount        = 1
                    recs[i].KeyEvent.wVirtualKeyCode     = vk
                    recs[i].KeyEvent.wVirtualScanCode    = scan
                    recs[i].KeyEvent.uChar.UnicodeChar   = ch
                    recs[i].KeyEvent.dwControlKeyState   = 0
                n_written = _wt.DWORD(0)
                ok = k32.WriteConsoleInputW(h, recs, 2, _ct.byref(n_written))
                ok_full = bool(ok) and n_written.value == 2
                if not ok_full:
                    err = k32.GetLastError()
                    log.warning(
                        "_win_inject_key: WriteConsoleInputW ok=%s written=%d err=%d",
                        bool(ok), n_written.value, err,
                    )
            finally:
                k32.CloseHandle(h)
        finally:
            k32.FreeConsole()
            _win_reset_std_handles()
        return ok_full
else:
    def _win_inject_key(pid: int, text: str) -> bool:  # pragma: no cover - non-Windows
        return False

_ANSI_RE = re.compile(r"\x1b(?:\[[0-9;]*[A-Za-z]|\][^\x07]*\x07|[()][AB012]|[=>])")


class ArgyllRunner(QObject):
    line_received   = pyqtSignal(str)
    started         = pyqtSignal()      # a tool actually began running
    finished        = pyqtSignal(int)   # exit code
    keypress_failed = pyqtSignal(str, str)  # (key_label, reason) — Windows injection failed
    _pty_done       = pyqtSignal(int, int)   # internal: PTY reader → main thread (exit code, run generation)
    #: A launch the last door refused because its instrument port is a system
    #: port that is never an instrument (the port's path). Emitted before the
    #: refused run's ``on_finish(1)``, the order the managers use.
    no_instrument   = pyqtSignal(str)

    # Map control bytes to human labels for logs and UI warnings.
    _KEY_LABELS = {
        "\r":     "CR",
        "\n":     "LF",
        "\x1b":   "ESC",
        " ":      "SPACE",
        "\x1b[D": "LEFT",
        "\x1b[C": "RIGHT",
    }

    @classmethod
    def _label_key(cls, text: str) -> str:
        if not text:
            return "<empty>"
        if text in cls._KEY_LABELS:
            return cls._KEY_LABELS[text]
        if len(text) == 1 and text.isprintable():
            return repr(text)
        return repr(text)

    def __init__(self, settings: "AppSettings", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._process: QProcess | None = None
        self._pending_stdin: bytes | None = None
        self._run_on_finish: Callable[[int], None] | None = None
        self._run_on_line:   Callable[[str], None] | None = None

        # PTY mode state
        self._pty_proc:   subprocess.Popen | None = None
        self._pty_master: int | None = None
        self._pty_thread: threading.Thread | None = None
        self._use_console_input: bool = False   # True = inject via WriteConsoleInputW
        # Incremented per PTY/pipe run. A finished reader reports its own
        # generation; a stale completion (next run already started in the
        # window between child exit and the queued _pty_done delivery) must
        # not tear down the new run's state or fire its callback.
        self._pty_gen: int = 0
        self._pty_done.connect(self._on_pty_finished)
        # ONE PERMANENT CONNECTION FOR THE PER-RUN `on_line` CALLBACK.
        #
        # It used to be `line_received.connect(on_line)` at the start of every
        # run and `disconnect(on_line)` at the end of it, with `on_line` a
        # closure the caller passed in. That is what killed the app in Read
        # Single Patches (his crash log, 2026-09-02 23:30): `line_received` is
        # emitted from the PTY READER THREAD, so PyQt delivers it through a
        # QUEUED call to a `PyQtSlotProxy`; a window opened from inside that
        # delivery runs a nested event loop, the same proxy is re-entered by the
        # lines that keep arriving, and PyQt guards re-entry with a BIT rather
        # than a counter (`PROXY_SLOT_INVOKED`, qpycore_pyqtslotproxy.cpp). The
        # inner call clears the bit; `disconnect()` then reaches
        # `PyQtSlotProxy::disable()`, which sees it clear and frees the proxy
        # while an outer `unislot()` frame is still live. The next queued call
        # lands on freed memory — `unislot -> deleteLater -> postEvent`, which
        # is his stack frame for frame.
        #
        # A permanent bound-method slot removes the whole class of fault:
        # nothing is ever disconnected, so `disable()` is never called, so the
        # bit can never be read at the wrong moment. Registering a run's
        # callback is now plain state, and dropping it is
        # `self._run_on_line = None`.
        self.line_received.connect(self._dispatch_run_line)

    def _dispatch_run_line(self, line: str) -> None:
        """Hand one output line to whatever callback the current run registered.

        Read through the attribute every time, so a run that has been forgotten
        (:meth:`forget_run_callbacks`) or has finished simply stops receiving —
        without a `disconnect()`, and without a slot proxy being torn down under
        a live invocation.
        """
        on_line = self._run_on_line
        if on_line is not None:
            on_line(line)

    #: What a refused launch says, in its log and to its own ``on_line``. It
    #: starts with stock Argyll's own "No instrument detected" so every parser
    #: that already recognises a reader finding no instrument (the spot-read
    #: manager's, for one) ends the session the way it ends that one.
    REFUSED_LAUNCH_LINE = ("No instrument detected: {tool} was not started, "
                           "because its instrument port is {port}, which is "
                           "never a measuring instrument.")

    def _refuse_launch(self, tool: str, args: "list[str]", port: str,
                       on_line: "Callable[[str], None] | None",
                       on_finish: "Callable[[int], None] | None") -> None:
        """End a launch the last door refused the way a reader that found no
        instrument ends: a log line, the line to the caller's own ``on_line``,
        :attr:`no_instrument`, then ``on_finish(1)``.

        All on the next turn of the event loop, never inside :meth:`run`: a
        caller (the Measure tab) clears its "no instrument" flag once its
        start has returned, and an emit inside the call was wiped (measured on
        screen for the managers' own refusal)."""
        name = Path(str(tool)).name
        line = self.REFUSED_LAUNCH_LINE.format(tool=name, port=port)
        log.warning("ArgyllRunner: refused %s %s: %s", name,
                    " ".join(map(str, args)), line)
        from PyQt6.QtCore import QTimer

        def _report() -> None:
            if on_line is not None:
                on_line(line)
            self.no_instrument.emit(str(port))
            if on_finish is not None:
                on_finish(1)
        QTimer.singleShot(0, _report)

    def _serial_exclusion_value(self, existing: "str | None") -> "str | None":
        """The ARGYLL_EXCLUDE_SERIAL_SCAN value to use for the next launch, or
        ``None`` to leave the environment untouched. The "Faster instrument
        connection" preference (default on) decides whether every phantom port
        is skipped; the ports whose open can hang for ever
        (``core/argyll_env.py``, the macOS Bluetooth incoming port) are
        skipped either way, and the user's own value is always kept."""
        phantoms = True
        try:
            phantoms = bool(self._settings.get("fast_instrument_connect", True))
        except Exception:  # noqa: BLE001 — a settings hiccup must not block a run
            pass
        return serial_exclusion_value(existing, phantoms=phantoms)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        tool: str,
        args: list[str],
        cwd: Path,
        on_line: Callable[[str], None] | None = None,
        on_finish: Callable[[int], None] | None = None,
        use_pty: bool = False,
    ) -> None:
        if self.is_running:
            # Not a failed START — a refused one. Leaving the flag set made the
            # Build Profile tab say "the program was not found, check
            # Preferences" for a run whose real cause was "something else is
            # running".
            self.last_failed_to_start = None
            log.warning("ArgyllRunner: already running, ignoring run(%s)", tool)
            # Never leave the caller waiting for a finish that can't come —
            # a silently dropped run() deadlocked the scanner tool's Check
            # alignment ("Checking the grid…" forever, Knut #108).
            if on_finish is not None:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: on_finish(-1))
            return

        # THE LAST DOOR: an instrument tool aimed at a port that is never an
        # instrument is not started (core/instrument_port.py). Its open can
        # block in the kernel for ever, and a process stuck there cannot be
        # killed. The measuring and spot-read managers refuse first and say
        # so; this catches any path that does not.
        from core import instrument_port
        refused = instrument_port.runner_refuses(self, tool, args)
        if refused is not None:
            self.last_failed_to_start = None
            self._refuse_launch(tool, args, refused, on_line, on_finish)
            return

        if use_pty:
            self._run_pty(tool, args, cwd, on_line, on_finish)
            return

        bin_path = self._resolve(tool)
        log.info("Run: %s %s  [cwd=%s]", bin_path, " ".join(args), cwd)

        self._process = QProcess(self)
        self._process.setWorkingDirectory(str(cwd))
        self._process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        # Skip Argyll's slow phantom-serial-port probe (macOS) so a USB
        # instrument connects fast. Only touch the environment when the option
        # is on AND we have something to exclude, so nothing else changes.
        _env = QProcessEnvironment.systemEnvironment()
        _extra = self.environment_additions(
            tool, _env.value("ARGYLL_EXCLUDE_SERIAL_SCAN", ""))
        if _extra:
            for _k, _v in _extra.items():
                _env.insert(_k, _v)
            self._process.setProcessEnvironment(_env)

        self._run_on_finish = on_finish
        self._run_on_line   = on_line
        self._run_tool      = tool      # for the failed-to-start message

        self._partial_json = b""
        self._stop_flood_quiet()
        self._line_gate = RepeatGate()
        self._process.readyReadStandardOutput.connect(self._on_ready_read)
        self._process.finished.connect(self._on_finished)
        # A PROCESS THAT NEVER STARTS MUST STILL REPORT BACK.
        # `finished` is emitted only by a process that actually ran. When the
        # binary is missing or not executable, QProcess emits `errorOccurred`
        # (FailedToStart) and NOTHING else — so every caller's `on_finish` was
        # simply never called. Driven with argyll_bin_path pointing at nothing
        # and an empty PATH: `on_finish called with: []`, `is_running: False`.
        # The Build Profile tab greys the tabs and (since #164) the masthead
        # before starting, and unlocks only from `on_finish` — so a mistyped
        # Argyll path locked the user out of their own Preferences, which is
        # the one place they could have fixed it, until they restarted.
        self._process.errorOccurred.connect(self._on_failed_to_start)


        # QProcess's OWN `started` — it fires only when the program really
        # began. Emitting ours straight after `start()` was a lie on the one
        # path that matters: `start()` returns immediately, and a missing
        # binary reports through `errorOccurred` afterwards, so `started` was
        # emitted for a tool that never ran.
        self._process.started.connect(self._on_process_started)
        self._process.start(str(bin_path), args)
        # THE MOMENT A TOOL IS ACTUALLY RUNNING. There was no such signal, so
        # anything wanting to react to "a tool started" had only
        # `target_started`, which the Create Chart tab emits BEFORE the process
        # exists — `is_running` is still False there. A masthead lock hung off
        # that combination never engaged: driven through a real targen build,
        # sampled every 80 ms, the buttons stayed live for the whole 3 s.


    def write_stdin(self, text: str) -> None:
        label = self._label_key(text)
        if self._pty_master is not None:
            try:
                os.write(self._pty_master, text.encode())
                log.info("send_key %s → pty OK", label)
            except OSError as e:
                log.warning("send_key %s → pty FAIL: %s", label, e)
                self.keypress_failed.emit(label, f"PTY write failed: {e}")
        elif self._use_console_input and self._pty_proc is not None:
            pid = self._pty_proc.pid
            ok  = _win_inject_key(pid, text)
            log.info("send_key %s pid=%d → inject %s", label, pid, "OK" if ok else "FAIL")
            if not ok:
                self.keypress_failed.emit(
                    label,
                    "Windows console injection failed (AttachConsole or "
                    "WriteConsoleInputW). Keypress did not reach chartread.",
                )
        elif self._pty_proc is not None and self._pty_proc.stdin:
            try:
                self._pty_proc.stdin.write(text.encode())
                self._pty_proc.stdin.flush()
                log.info("send_key %s → pipe OK", label)
            except OSError as e:
                log.warning("send_key %s → pipe FAIL: %s", label, e)
                self.keypress_failed.emit(label, f"pipe write failed: {e}")
        elif self._process and self._process.state() == QProcess.ProcessState.Running:
            self._process.write(text.encode())
            log.info("send_key %s → QProcess OK", label)
        else:
            log.warning("send_key %s: no active process", label)
            self.keypress_failed.emit(label, "no active process")

    def abort(self) -> None:
        if self._pty_proc is not None:
            self._pty_proc.kill()
            log.info("ArgyllRunner: PTY process killed")
        elif self._process:
            self._process.kill()
            log.info("ArgyllRunner: process killed")

    def forget_run_callbacks(self) -> None:
        """Drop the current run's ``on_line`` / ``on_finish`` callbacks.

        THE RUNNER OUTLIVES EVERY DIALOG (it is the app-wide singleton), and a
        run's callbacks are plain Python closures that capture the object that
        started it. When that object is a window being closed, the PTY reader
        thread can still deliver a queued completion afterwards — and calling
        the closure then emits a signal on an already-freed C++ object, which
        is a segfault rather than an exception.

        That is issue #145: Knut's ColorMunki kept dropping off a 2019 MacBook,
        spotread exited on its own each time, and after enough open-and-close
        rounds the app died in ``PyQtSlotProxy::unislot`` calling
        ``deleteLater()`` on a null object. :meth:`cleanup` already documented
        the same failure mode for app shutdown; this is the per-window half of
        it, so a dialog can leave the singleton clean without tearing down a
        runner other windows still use.

        It used to `disconnect()` the closure from `line_received` as well.
        That disconnect was itself a crash — see `__init__` — and it is no
        longer needed: `_dispatch_run_line` reads `_run_on_line` fresh on every
        line, so clearing the attribute stops the delivery just as completely
        and cannot free a slot proxy under a live invocation.
        """
        self._run_on_finish = None
        self._run_on_line = None

    def cleanup(self) -> None:
        """Kill any running process and join the PTY thread before app shutdown.

        Must be called from closeEvent before Qt starts destroying objects,
        otherwise the daemon PTY thread can emit signals into already-freed
        C++ objects and cause a segfault (macOS 'quit unexpectedly' dialog).
        """
        # ⚠ THE SESSION'S FINISH HANDLER STILL RUNS FROM HERE, ON PURPOSE.
        #
        # Killing the process makes `waitForFinished` deliver `finished` →
        # `_on_finished` → the per-run callback, synchronously, during
        # shutdown. Disconnecting `self.finished` does not prevent that:
        # `_on_finished` calls the per-run callback DIRECTLY, so a chained run
        # (targen→printtarg) can register its own. The public signal was never
        # the path that mattered.
        #
        # An earlier fix dropped the per-run callbacks here to stop a spurious
        # warning. **That was too blunt and is not what this does.** It also
        # silenced the §3b / M-TI3-EMPTY reconciliation, which legitimately
        # runs when a session ends — leaving an empty `.ti3` still claiming to
        # be a measurement and the one it replaced stranded in `old/`. Knut
        # specified that reconciliation. Silencing a false alarm must never
        # silence real work.
        #
        # The real fault was narrower: the session was not told WHY it was
        # ending. `MainWindow.closeEvent` now says so before calling this, via
        # `MeasureManager.note_app_quitting()`, because quitting IS a
        # deliberate ending. That silences the "unknown error" warning and
        # stops stock chartread being relaunched into a closing app, while the
        # finish handler still runs and still reconciles.

        # Disconnect all signals so no callbacks fire during teardown.
        for sig in (self.line_received, self.finished, self._pty_done):
            try:
                sig.disconnect()
            except (TypeError, RuntimeError):
                pass

        # Kill subprocess(es).
        if self._pty_proc is not None and self._pty_proc.poll() is None:
            self._pty_proc.kill()
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._process.waitForFinished(2000)

        # Close the PTY master fd so the reader thread unblocks immediately.
        if self._pty_master is not None:
            try:
                os.close(self._pty_master)
            except OSError:
                pass
            self._pty_master = None

        # Wait for the reader thread to exit so it cannot emit after we return.
        if self._pty_thread is not None and self._pty_thread.is_alive():
            self._pty_thread.join(timeout=2.0)
            self._pty_thread = None

        log.info("ArgyllRunner: cleanup complete")

    @property
    def is_running(self) -> bool:
        if self._pty_proc is not None and self._pty_proc.poll() is None:
            return True
        return (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        )

    # ------------------------------------------------------------------
    # PTY mode (macOS/Linux) / pipe mode (Windows)
    # ------------------------------------------------------------------

    def _the_tool_never_started(
        self,
        bin_path: "Path | str",
        on_finish: "Callable[[int], None] | None",
        exc: BaseException,
        on_line: "Callable[[str], None] | None" = None,
    ) -> None:
        """A launch that RAISED must report back, exactly as a failed QProcess does.

        THE APPLICATION ABORTED HERE. :meth:`run`'s QProcess path already says
        why this matters, in its own words: *"A PROCESS THAT NEVER STARTS MUST
        STILL REPORT BACK … When the binary is missing or not executable,
        QProcess emits `errorOccurred` (FailedToStart) and NOTHING else — so
        every caller's `on_finish` was simply never called."* It connects
        :meth:`_on_failed_to_start` for that.

        The three launchers below had no such handler at all. They call
        ``subprocess.Popen`` bare, so a missing binary raises
        ``FileNotFoundError`` **inside the Qt slot that pressed the button** —
        and PyQt6 answers an unhandled exception in a slot with ``qFatal()``.
        Not an error dialog, not a log line: the process aborts.

        Measured on screen, combined round 8, with ``argyll_bin_path`` pointing
        at a folder holding no ArgyllCMS and no ArgyllCMS on ``PATH`` — which is
        the ordinary shape of a user's machine, because ChromIQ's default is
        ``/Applications/Argyll/bin`` and nothing puts Argyll on ``PATH``:

        * press **Start Measurement**, answer *Measure anyway* to "This chart is
          fully measured" — **exit 134 (SIGABRT)**, no window, no log line, and
          the finished measurement already moved into ``runs/run1/old/<date>/``
          by the archive that question performs. The run holds no measurement.
        * press **Measure again to average** — **exit 134** again, from inside
          ``_start_averaging_read`` one line above the ``_session_live`` check
          that exists to put the reading back. The run holds no ``.ti3`` and the
          reading sits in ``reads/read1.ti3``, where nothing in ChromIQ looks.

        So the marker round 7 added is not wrong; it is never reached. Reporting
        the failure the way the QProcess path reports it gives every ending that
        already exists its turn: ``_on_measure_done`` runs, ``_session_live``
        goes back to False, the session guard judges the session, and the
        averaging restore puts the read back.

        Delivered through a zero-delay timer, like the refused-run branch of
        :meth:`run`, so the caller still standing in ``_on_start`` is never
        re-entered before it has finished starting.

        AND ONE LINE GOES INTO THE RUN'S OWN OUTPUT, because the ending the
        Measure tab then reaches says *"Measurement failed - see output above"*
        and there was nothing above: the reason was logged to the Python log,
        which no user reads. A message that points at something must point at
        something.
        """
        tool = Path(bin_path).name or str(bin_path)
        log.error("ArgyllRunner: %s could not be started at all (%s) — check "
                  "the ArgyllCMS path in Preferences", tool, exc)
        # The same field the QProcess path sets, so the tab that asked for the
        # run can TELL the user rather than printing a bare exit code.
        self.last_failed_to_start = tool
        self._pty_proc   = None
        self._pty_master = None
        self._run_on_finish = None
        self._run_on_line   = None

        def _report() -> None:
            if on_line is not None:
                # THE KEY THE BUILD PROFILE TAB'S OWN WINDOW ALREADY USES for
                # its title, so this adds NO new user-facing string and is
                # already translated into all twelve languages. The instruction
                # is on screen either way: the slab under the masthead on this
                # very tab reads "ArgyllCMS not found. Open Preferences to set
                # the path."
                from core.i18n import tr
                on_line("[ERROR] " + tr(
                    "ChromIQ could not start {tool}").format(tool=tool))
            self.finished.emit(-1)
            if on_finish is not None:
                on_finish(-1)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, _report)

    def _run_pty(
        self,
        tool: str,
        args: list[str],
        cwd: Path,
        on_line: Callable[[str], None] | None,
        on_finish: Callable[[int], None] | None,
    ) -> None:
        bin_path = self._resolve(tool)

        if sys.platform == "win32":
            # _run_winpty() uses CREATE_NEW_CONSOLE + WriteConsoleInputW — no pywinpty needed.
            self._run_winpty(bin_path, args, cwd, on_line, on_finish)
            return

        log.info("Run (PTY): %s %s  [cwd=%s]", bin_path, " ".join(args), cwd)
        # Skip Argyll's slow phantom-serial-port probe (macOS) — see run().
        _env = os.environ.copy()
        _env.update(self.environment_additions(
            tool, _env.get("ARGYLL_EXCLUDE_SERIAL_SCAN")))
        master_fd, slave_fd = pty.openpty()
        try:
            self._pty_proc = subprocess.Popen(
                [str(bin_path)] + args,
                stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                cwd=str(cwd),
                close_fds=True,
                start_new_session=True,
                env=_env,
            )
        except OSError as exc:
            # Both ends, or the pty leaks for the life of the process.
            os.close(master_fd)
            os.close(slave_fd)
            self._the_tool_never_started(bin_path, on_finish, exc, on_line)
            return
        os.close(slave_fd)
        self._pty_master = master_fd
        self._pty_gen += 1

        self._run_on_finish = on_finish
        self._run_on_line   = on_line

        self._pty_thread = threading.Thread(
            target=self._pty_reader,
            args=(master_fd, self._pty_proc, self._pty_gen),
            daemon=True,
        )
        self._pty_thread.start()

    def _run_winpty(
        self,
        bin_path: Path,
        args: list[str],
        cwd: Path,
        on_line: Callable[[str], None] | None,
        on_finish: Callable[[int], None] | None,
    ) -> None:
        """Windows interactive mode: hidden real console + WriteConsoleInputW for stdin.

        Pywinpty (ConPTY / WinPTY) proved unreliable in frozen PyInstaller apps
        across multiple beta releases.  Instead we give chartread its own real
        but invisible console (CREATE_NEW_CONSOLE + SW_HIDE) so _getch() works,
        pipe stdout for output reading, and inject keystrokes via AttachConsole +
        WriteConsoleInputW — the same path a physical keyboard uses.
        """
        cmd = [str(bin_path)] + args
        log.info("Run (new-console): %s  [cwd=%s]", " ".join(cmd), cwd)

        si = subprocess.STARTUPINFO()
        si.dwFlags   = subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0   # SW_HIDE

        CREATE_NEW_CONSOLE = 0x10
        _env = os.environ.copy()
        _env.update(self.environment_additions(
            str(bin_path), _env.get("ARGYLL_EXCLUDE_SERIAL_SCAN")))
        try:
            self._pty_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=CREATE_NEW_CONSOLE,
                startupinfo=si,
                cwd=str(cwd),
                env=_env,
            )
        except OSError as exc:
            self._the_tool_never_started(bin_path, on_finish, exc, on_line)
            return
        self._pty_master        = None
        self._use_console_input = True
        self._pty_gen += 1

        self._run_on_finish = on_finish
        self._run_on_line   = on_line

        self._pty_thread = threading.Thread(
            target=self._pipe_reader, args=(self._pty_gen,), daemon=True
        )
        self._pty_thread.start()

    def _run_pipe(
        self,
        bin_path: Path,
        args: list[str],
        cwd: Path,
        on_line: Callable[[str], None] | None,
        on_finish: Callable[[int], None] | None,
    ) -> None:
        log.info("Run (pipe): %s %s  [cwd=%s]", bin_path, " ".join(args), cwd)
        _env = os.environ.copy()
        _env.update(self.environment_additions(
            str(bin_path), _env.get("ARGYLL_EXCLUDE_SERIAL_SCAN")))
        try:
            self._pty_proc = subprocess.Popen(
                [str(bin_path)] + args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(cwd),
                creationflags=_CREATE_NO_WINDOW,
                env=_env,
            )
        except OSError as exc:
            self._the_tool_never_started(bin_path, on_finish, exc, on_line)
            return
        self._pty_master = None
        self._pty_gen += 1

        self._run_on_finish = on_finish
        self._run_on_line   = on_line

        self._pty_thread = threading.Thread(
            target=self._pipe_reader, args=(self._pty_gen,), daemon=True
        )
        self._pty_thread.start()

    def _pty_reader(self, master_fd: int, proc: subprocess.Popen, gen: int) -> None:
        buf = b""
        FLUSH_AFTER = 0.15   # emit partial prompt lines after this silence

        # Collapse a runaway stream of identical lines (a USB error loop) so
        # it cannot flood the Qt event queue or the log (core/line_flood.py).
        gate = RepeatGate()

        def _emit(line: str) -> None:
            for out in gate.feed(line):
                log.debug("[argyll-pty] %s", out)
                self.line_received.emit(out)

        while True:
            try:
                r, _, _ = select.select([master_fd], [], [], FLUSH_AFTER)
            except (OSError, ValueError):
                break

            if r:
                try:
                    data = os.read(master_fd, 4096)
                except OSError:
                    break
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    line = _ANSI_RE.sub("", decode_output(raw, what="argyll")).rstrip("\r")
                    if line:
                        _emit(line)
            else:
                # Silence window — flush any partial prompt
                if buf:
                    line = _ANSI_RE.sub("", decode_output(buf, what="argyll")).rstrip("\r")
                    buf = b""
                    if line:
                        _emit(line)
                # A flood that ended in silence is summed up now, not when
                # the next line arrives (core/line_flood.py, RepeatGate.idle).
                for out in gate.idle():
                    log.debug("[argyll-pty] %s", out)
                    self.line_received.emit(out)

            # Safety net for a hung fd (e.g. a grandchild keeping the slave
            # side open): only stop on child exit once nothing is readable,
            # otherwise a >4 KB final output burst would be truncated. The
            # normal exit path is EOF (`not data`) above.
            if not r and proc.poll() is not None:
                break

        # Flush remainder
        if buf:
            line = _ANSI_RE.sub("", decode_output(buf, what="argyll")).rstrip("\r")
            if line:
                _emit(line)
        for out in gate.flush():
            log.debug("[argyll-pty] %s", out)
            self.line_received.emit(out)

        try:
            code = proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            code = proc.wait()

        try:
            os.close(master_fd)
        except OSError:
            pass

        self._pty_done.emit(code, gen)

    def _pipe_reader(self, gen: int) -> None:
        """Read from subprocess stdout pipe (Windows fallback for PTY).

        A helper thread feeds bytes into a queue so the main loop can apply
        the same FLUSH_AFTER silence-window logic as the PTY reader, making
        interactive ArgyllCMS prompts (no trailing newline) visible promptly.
        """
        FLUSH_AFTER = 0.15

        proc = self._pty_proc
        if proc is None or proc.stdout is None:
            self._pty_done.emit(0, gen)
            return

        gate = RepeatGate()     # see the PTY reader and core/line_flood.py

        def _emit(line: str) -> None:
            for out in gate.feed(line):
                log.debug("[argyll-pipe] %s", out)
                self.line_received.emit(out)

        byte_q: queue.Queue[bytes | None] = queue.Queue()

        def _raw_reader() -> None:
            try:
                while True:
                    b = proc.stdout.read(1)
                    byte_q.put(b if b else None)
                    if not b:
                        break
            except OSError:
                byte_q.put(None)

        threading.Thread(target=_raw_reader, daemon=True).start()

        buf = b""
        while True:
            try:
                byte = byte_q.get(timeout=FLUSH_AFTER)
            except queue.Empty:
                if buf:
                    line = _ANSI_RE.sub(
                        "", decode_output(buf, what="argyll")
                    ).rstrip("\r")
                    buf = b""
                    if line:
                        _emit(line)
                for out in gate.idle():       # a flood that ended in silence
                    log.debug("[argyll-pipe] %s", out)
                    self.line_received.emit(out)
                continue

            if byte is None:
                break

            buf += byte
            if byte == b"\n":
                raw = buf.rstrip(b"\r\n")
                buf = b""
                line = _ANSI_RE.sub("", decode_output(raw, what="argyll"))
                if line:
                    _emit(line)

        if buf:
            line = _ANSI_RE.sub(
                "", decode_output(buf, what="argyll")
            ).rstrip("\r")
            if line:
                _emit(line)
        for out in gate.flush():
            log.debug("[argyll-pipe] %s", out)
            self.line_received.emit(out)

        try:
            code = proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            code = proc.wait()

        self._pty_done.emit(code, gen)

    def _on_pty_finished(self, code: int, gen: int) -> None:
        if gen != self._pty_gen:
            # A newer run already started; this completion belongs to the
            # previous process. Tearing down state here would orphan the new
            # run and fire its on_finish with the old exit code.
            log.warning(
                "ArgyllRunner (PTY): stale completion (gen %d, current %d, code %d) ignored",
                gen, self._pty_gen, code,
            )
            return
        self._pty_master        = None
        self._pty_proc          = None
        self._use_console_input = False
        on_finish = self._run_on_finish
        self._run_on_finish = None
        self._run_on_line   = None
        log.info("ArgyllRunner (PTY): finished with code %d", code)
        self.finished.emit(code)
        if on_finish:
            on_finish(code)

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    #: A held-back fragment longer than this is emitted anyway: a tool that
    #: prints an endless line must not make the log go silent.
    _PARTIAL_JSON_LIMIT = 1 << 20

    def _take_complete(self, raw: bytes) -> bytes:
        """*raw* plus any fragment held back from the previous read, minus a
        new trailing fragment that is the START OF AN ENGINE EVENT.

        One read ends wherever the pipe buffer did, so a long JSON event line
        from the chart-reading engine (a chart-mode ``chart_read``) arrived in
        two pieces, each emitted as a "line" and neither parsing: the event
        was lost (review P_review2_beta1, P-202-2). Only a fragment that
        begins like an event (``{``, after an optional BEL) waits for its
        newline. Anything else is emitted at once as before, because Argyll's
        own prompts ("hit any key to continue") end WITHOUT a newline and the
        user has to see them now."""
        buf = getattr(self, "_partial_json", b"") + raw
        self._partial_json = b""
        cut = max(buf.rfind(b"\n"), buf.rfind(b"\r")) + 1
        tail = buf[cut:]
        if (tail.lstrip(b"\x07 \t").startswith(b"{")
                and len(tail) < self._PARTIAL_JSON_LIMIT):
            self._partial_json = tail
            return buf[:cut]
        return buf

    def _gate(self) -> RepeatGate:
        """This run's repeat gate (made on first use for a runner built
        without `run`, as some tests do)."""
        gate = self.__dict__.get("_line_gate")
        if gate is None:
            gate = self._line_gate = RepeatGate()
        return gate

    def _gated_lines(self, text: str):
        """*text*'s lines through the repeat gate, in order.

        A read ends wherever the pipe buffer did, so a flood arrives cut into
        pieces, and every piece would pass the gate as a new line. A last piece
        (no newline after it) that is the start of the line being collapsed
        right now is held back for the next read, like a split engine event.
        It is decided only once this read's whole lines have been fed, so the
        gate knows about the flood by then."""
        gate = self._gate()
        lines = text.splitlines()
        partial = bool(lines) and not text.endswith(("\n", "\r"))
        for i, ln in enumerate(lines):
            if (partial and i == len(lines) - 1
                    and gate.is_flood_prefix(ln)):
                self._partial_json = ln.encode("utf-8")
                return
            yield from gate.feed(ln)

    def _on_ready_read(self) -> None:
        if not self._process:
            return
        raw = self._take_complete(self._process.readAllStandardOutput().data())
        text = decode_output(raw, what="argyll")
        # A runaway stream of identical lines (Knut, beta 8: an unplugged
        # instrument, ~255,000 log lines in a minute) is collapsed here, where
        # it enters ChromIQ, so the log, the panel and the parsers all see the
        # first lines and a count (core/line_flood.py).
        for line in self._gated_lines(text):
            log.debug("[argyll] %s", line)
            self.line_received.emit(line)
            # A SLOT MAY HAVE ENDED THE RUN. Some of these lines open a modal
            # window, which spins its own event loop — and the button in it can
            # stop the measurement, killing the process and dropping the object
            # this method is iterating output from. Carrying on then walks into
            # a deleted C++ object: Knut, beta.138, segfaulted here after
            # answering two windows in a row (crash log:
            # "argyll_runner.py, line 817 in _on_ready_read").
            if not self._process:
                return
        self._arm_flood_quiet()

    def _arm_flood_quiet(self) -> None:
        """While repeats are counted, wake once the tool has been quiet for
        longer than a burst gap, so a flood that ends in silence is summed up
        then (core/line_flood.py, RepeatGate.idle). A bound method on a timer
        the runner owns, never a lambda (CLAUDE.md)."""
        if not self._gate().pending():
            return
        from PyQt6.QtCore import QTimer
        from core.line_flood import BURST_GAP
        timer = self.__dict__.get("_flood_quiet_timer")
        if timer is None:
            # Held by the runner, not parented: a runner a test built with
            # __new__ has no QObject to parent it to.
            timer = self._flood_quiet_timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(self._on_flood_quiet)
        timer.start(int((BURST_GAP + 0.25) * 1000))

    def _stop_flood_quiet(self) -> None:
        timer = self.__dict__.get("_flood_quiet_timer")
        if timer is not None:
            timer.stop()

    def _on_flood_quiet(self) -> None:
        if not self._process:
            return                  # the run ended: _on_finished flushed it
        for line in self._gate().idle():
            log.debug("[argyll] %s", line)
            self.line_received.emit(line)
            if not self._process:
                return
        self._arm_flood_quiet()     # still counting a burst that goes on

    def _on_process_started(self) -> None:
        """The program really began — not merely that `start()` was called."""
        self.last_failed_to_start = None
        self.started.emit()

    def _on_failed_to_start(self, error: object) -> None:
        """QProcess could not launch the tool — report it as a failed run.

        Only FailedToStart is handled here: every other QProcess error still
        ends in `finished`, which already does the full teardown. Routing this
        through `_on_finished(-1, ...)` reuses that teardown verbatim, so the
        caller sees the same "it ended, badly" it sees for a non-zero exit.
        """
        from PyQt6.QtCore import QProcess

        if error != QProcess.ProcessError.FailedToStart:
            return                      # `finished` will follow for the rest
        tool = getattr(self, "_run_tool", None) or "the tool"
        log.error("ArgyllRunner: %s could not be started at all — check the "
                  "ArgyllCMS path in Preferences", tool)
        # Remembered so the tab that asked for the run can TELL the user, which
        # a bare exit code cannot: colprof exiting -1 with no output produced no
        # dialog at all, and the only trace was one line in the log.
        self.last_failed_to_start = tool
        self._on_finished(-1, None)

    def _on_finished(self, exit_code: int, _exit_status: object) -> None:
        log.info("ArgyllRunner: finished with code %d", exit_code)
        # Drain any output still buffered in QProcess before disconnecting.
        # Qt does not guarantee all readyReadStandardOutput events arrive before
        # finished(), so the last chunk of output (e.g. profcheck per-patch lines)
        # can be silently lost without this flush.
        self._stop_flood_quiet()
        if self._process:
            remaining = (getattr(self, "_partial_json", b"")
                         + self._process.readAllStandardOutput().data())
            self._partial_json = b""
            gate = self._gate()
            lines = []
            if remaining:
                text = decode_output(remaining, what="argyll")
                lines = [out for ln in text.splitlines()
                         for out in gate.feed(ln)]
            for line in lines + gate.flush():
                log.debug("[argyll] %s", line)
                self.line_received.emit(line)

        # Capture per-run callbacks before they can be overwritten by a chained run()
        on_finish = self._run_on_finish
        self._run_on_finish = None
        self._run_on_line   = None
        try:
            self._process.readyReadStandardOutput.disconnect(self._on_ready_read)
            self._process.finished.disconnect(self._on_finished)
        except RuntimeError:
            pass
        # Emit public signal for any external observers
        self.finished.emit(exit_code)
        # Call per-run callback directly so chained run() calls (targen→printtarg)
        # can register their own on_finish without it being disconnected here
        if on_finish:
            on_finish(exit_code)

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    def resolve_tool(self, tool: str) -> Path:
        """Where this runner would find *tool*, without running it.

        The public face of :meth:`_resolve`, for the one caller that has to
        drive an Argyll binary itself instead of through the QProcess queue:
        :mod:`workflow.scan_device_values`, whose values pass is a short
        synchronous read that must not take the singleton's ``is_running``
        guard from the build it is checking. Resolving through the same method
        keeps that call on the user's configured Argyll, not on whatever is
        first on ``PATH``.
        """
        return self._resolve(tool)

    def tool_is_installed(self, tool: str) -> bool:
        """Could this tool be launched right now, without launching it?

        For a caller that must not START anything before it has asked its
        questions: a build that cannot run must not archive the profile it was
        going to replace. :meth:`_resolve` answers with a bare NAME when the
        configured folder holds nothing, precisely so a ``PATH`` install still
        works, so a bare ``Path.is_file()`` on its answer would call a perfectly
        good ArgyllCMS missing. Both places are asked, in that order.
        """
        found = self._resolve(tool)
        if found.is_absolute():
            return found.is_file() and os.access(found, os.X_OK)
        import shutil
        return shutil.which(str(found)) is not None

    def environment_additions(self, tool: str,
                              current_exclusion: "str | None") -> "dict[str, str]":
        """What `run` adds to the tool's environment, and nothing else.

        The serial-probe exclusion (see `run`), and for printtarg the
        allocator setting that makes a seeded layout the same on every run
        (flk1, `core/printtarg_env.py`). Empty means the environment is
        left exactly as inherited."""
        extra: "dict[str, str]" = {}
        excl = self._serial_exclusion_value(current_exclusion)
        if excl:
            extra["ARGYLL_EXCLUDE_SERIAL_SCAN"] = excl
        if is_printtarg(tool):
            extra.update(printtarg_env_additions())
        return extra

    def _resolve(self, tool: str) -> Path:
        # Bundled helpers (chromiq-chartread) pass their absolute path —
        # they don't live in the Argyll bin dir.
        if Path(tool).is_absolute():
            return Path(tool)
        bin_dir = Path(self._settings.get("argyll_bin_path", "/Applications/Argyll/bin"))
        candidate = bin_dir / argyll_binary(tool)
        if not candidate.exists():
            log.warning(
                "%s not found in configured Argyll path %s — falling back to "
                "PATH lookup; a different Argyll version may be picked up",
                argyll_binary(tool), bin_dir,
            )
            return Path(argyll_binary(tool))
        return candidate

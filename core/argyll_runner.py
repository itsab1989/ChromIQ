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

from core.logger import get_logger
from core.resource_path import argyll_binary

if sys.platform != "win32":
    import pty
    import select

if TYPE_CHECKING:
    from core.settings import AppSettings

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Fast instrument connection: skip Argyll's slow serial-port probe (#macOS)
#
# Before opening a USB spectro, Argyll probes every serial port it can see at
# several baud rates (~2 s each). On macOS a phantom port like
# /dev/cu.Bluetooth-Incoming-Port is almost always present, adding ~10 s to
# every measurement start. Argyll's ARGYLL_EXCLUDE_SERIAL_SCAN env var takes a
# ';'-separated exact-match list of port paths to skip — we fill it with the
# phantom ports so a USB instrument is reached immediately, while KEEPING real
# USB-serial adapters (a serial SpectroScan, etc.) so nothing breaks.
# ---------------------------------------------------------------------------

#: Substrings of a macOS /dev/cu.* name that mark a REAL serial adapter — never
#: excluded, so serial instruments still work.
_REAL_SERIAL_HINTS = ("usbserial", "usbmodem")

#: Windows SERIALCOMM value-name prefixes that mark a Bluetooth serial port —
#: never a ChromIQ measurement instrument, so safe to skip (the direct analog of
#: excluding /dev/cu.Bluetooth-* on macOS). USB-serial adapters (VCP/USBSER, e.g.
#: a SpectroScan bridge) are deliberately NOT matched, so real serial instruments
#: still work. These are exactly the prefixes Argyll itself tags as ``btserial``
#: (see spectro/icoms_nt.c), so our exclusion can never disagree with its scan.
_WIN_BLUETOOTH_PREFIXES = ("BtPort", "BthModem")


def _phantom_serial_ports(candidates: list[str]) -> list[str]:
    """From /dev/cu.* candidates, the phantom ports that are never a measurement
    instrument (Bluetooth, debug consoles, paired devices) — everything that is
    NOT a real USB-serial adapter. Pure/side-effect-free for testing."""
    return sorted(
        p for p in candidates
        if not any(h in os.path.basename(p).lower() for h in _REAL_SERIAL_HINTS))


def _windows_bluetooth_com_ports(entries: "list[tuple[str, str]]") -> list[str]:
    """From ``(value_name, com_port)`` rows of HKLM\\...\\SERIALCOMM, the COM
    ports that are Bluetooth serial ports (never an instrument). Argyll keys a
    port's type off the leaf of its registry value name; we apply the identical
    rule (``BtPort*`` / ``BthModem*``), keeping every USB-serial adapter
    (``VCP*`` / ``USBSER*``) and native port. Pure/side-effect-free for
    testing."""
    ports: list[str] = []
    for name, com in entries:
        leaf = name.rsplit("\\", 1)[-1]
        if com and any(leaf.startswith(pfx) for pfx in _WIN_BLUETOOTH_PREFIXES):
            if com not in ports:
                ports.append(com)
    return sorted(ports)


def _read_serialcomm() -> "list[tuple[str, str]]":
    """Enumerate ``HKLM\\HARDWARE\\DEVICEMAP\\SERIALCOMM`` as ``(value_name,
    com_port)`` rows — the exact key Argyll reads. Empty when the key is absent
    (the common case: no serial ports) or unreadable. Windows-only; never
    raises."""
    try:
        import winreg
    except ImportError:  # pragma: no cover — non-Windows
        return []
    rows: list[tuple[str, str]] = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"HARDWARE\DEVICEMAP\SERIALCOMM") as key:
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                except OSError:  # ERROR_NO_MORE_ITEMS — end of the value list
                    break
                rows.append((name, str(value)))
                i += 1
    except OSError:  # key absent / unreadable — nothing to exclude
        return []
    return rows


def argyll_serial_exclusion_ports() -> list[str]:
    """The phantom serial ports to exclude from Argyll's scan on this machine.

    macOS: modern Macs have NO built-in serial port — every real serial
    instrument is on a USB-serial adapter (usbserial/usbmodem) — so excluding
    every OTHER /dev/cu.* (Bluetooth, debug consoles, paired devices) is both
    safe and complete.

    Linux: conservative. Only the Bluetooth ``/dev/rfcomm*`` ports are certainly
    not instruments. Native ``/dev/ttyS*`` ports (and USB adapters ttyUSB/ttyACM)
    are left completely untouched, so a real serial instrument can never be
    excluded.

    Windows: only Bluetooth COM ports. Argyll lists serial ports from
    ``HKLM\\HARDWARE\\DEVICEMAP\\SERIALCOMM`` and probes each fast/virtual one for
    ~2 s; a paired Bluetooth device (``BthModem*`` / ``BtPort*``) is never an
    instrument, so its COM port is skipped. USB-serial adapters (``VCP*`` /
    ``USBSER*``, e.g. a SpectroScan) and native ports are always kept. A machine
    with no serial ports (the common case) excludes nothing."""
    import glob
    try:
        if sys.platform == "darwin":
            return _phantom_serial_ports(glob.glob("/dev/cu.*"))
        if sys.platform.startswith("linux"):
            return sorted(glob.glob("/dev/rfcomm*"))
        if sys.platform == "win32":
            return _windows_bluetooth_com_ports(_read_serialcomm())
    except OSError:  # pragma: no cover — enumeration must never block a launch
        return []
    return []


def merged_serial_exclusion(existing: "str | None",
                            ports: "list[str] | None" = None) -> "str | None":
    """The value for ARGYLL_EXCLUDE_SERIAL_SCAN: our phantom ports merged with
    (and never dropping) anything the user already set. ``None`` when there is
    nothing to exclude. *ports* defaults to :func:`argyll_serial_exclusion_ports`
    (injectable for tests)."""
    if ports is None:
        ports = argyll_serial_exclusion_ports()
    items = [x for x in (existing or "").replace(",", ";").split(";") if x]
    for p in ports:
        if p not in items:
            items.append(p)
    return ";".join(items) if items else None

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

    def _serial_exclusion_value(self, existing: "str | None") -> "str | None":
        """The ARGYLL_EXCLUDE_SERIAL_SCAN value to use for the next launch, or
        ``None`` to leave the environment untouched. Honours the user's
        "Faster instrument connection" preference (default on); returns None the
        moment it's off, so the feature can be fully disabled."""
        try:
            if not self._settings.get("fast_instrument_connect", True):
                return None
        except Exception:  # noqa: BLE001 — a settings hiccup must not block a run
            pass
        return merged_serial_exclusion(existing)

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
        _excl = self._serial_exclusion_value(
            _env.value("ARGYLL_EXCLUDE_SERIAL_SCAN", ""))
        if _excl:
            _env.insert("ARGYLL_EXCLUDE_SERIAL_SCAN", _excl)
            self._process.setProcessEnvironment(_env)

        self._run_on_finish = on_finish
        self._run_on_line   = on_line
        self._run_tool      = tool      # for the failed-to-start message

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

        if on_line:
            self.line_received.connect(on_line)

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
        """
        on_line = self._run_on_line
        self._run_on_finish = None
        self._run_on_line = None
        if on_line is not None:
            try:
                self.line_received.disconnect(on_line)
            except (TypeError, RuntimeError):
                pass

    def cleanup(self) -> None:
        """Kill any running process and join the PTY thread before app shutdown.

        Must be called from closeEvent before Qt starts destroying objects,
        otherwise the daemon PTY thread can emit signals into already-freed
        C++ objects and cause a segfault (macOS 'quit unexpectedly' dialog).
        """
        # DROP THE PER-RUN CALLBACKS FIRST, AND THE QPROCESS SIGNALS WITH THEM.
        #
        # Disconnecting `self.finished` is not enough, and it looked like it
        # was. `_on_finished` calls `_run_on_finish` DIRECTLY — deliberately,
        # so a chained run (targen→printtarg) can register its own without it
        # being disconnected — so the public signal is not the path that
        # matters. Killing the process below makes `waitForFinished` deliver
        # `finished`, which runs the measurement session's finish handler in
        # the middle of application shutdown.
        #
        # Two things came of that. The owner saw
        # "the chart's instrument is one stock chartread cannot read (unknown
        # error) — not falling back" in his terminal on every quit: exit code 9
        # is SIGKILL, `_user_quit` is False because he never asked to stop, and
        # the #159 branch warns about a failure that did not happen. Worse and
        # latent: a non-CR30 engine session quit before its first event would
        # RELAUNCH stock chartread during shutdown, leaving an orphan process
        # behind the closing app.
        #
        # Nothing is lost by dropping them — CR30 readings are written to disk
        # after every patch, and this path exists only for quitting.
        self._run_on_finish = None
        self._run_on_line = None
        if self._process is not None:
            for _sig, _slot in ((self._process.finished, self._on_finished),
                                (self._process.readyReadStandardOutput,
                                 self._on_ready_read)):
                try:
                    _sig.disconnect(_slot)
                except (TypeError, RuntimeError):
                    pass

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
        _excl = self._serial_exclusion_value(
            _env.get("ARGYLL_EXCLUDE_SERIAL_SCAN"))
        if _excl:
            _env["ARGYLL_EXCLUDE_SERIAL_SCAN"] = _excl
        master_fd, slave_fd = pty.openpty()
        self._pty_proc = subprocess.Popen(
            [str(bin_path)] + args,
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            cwd=str(cwd),
            close_fds=True,
            start_new_session=True,
            env=_env,
        )
        os.close(slave_fd)
        self._pty_master = master_fd
        self._pty_gen += 1

        self._run_on_finish = on_finish
        self._run_on_line   = on_line
        if on_line:
            self.line_received.connect(on_line)

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
        self._pty_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=CREATE_NEW_CONSOLE,
            startupinfo=si,
            cwd=str(cwd),
        )
        self._pty_master        = None
        self._use_console_input = True
        self._pty_gen += 1

        self._run_on_finish = on_finish
        self._run_on_line   = on_line
        if on_line:
            self.line_received.connect(on_line)

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
        self._pty_proc = subprocess.Popen(
            [str(bin_path)] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(cwd),
            creationflags=_CREATE_NO_WINDOW,
        )
        self._pty_master = None
        self._pty_gen += 1

        self._run_on_finish = on_finish
        self._run_on_line   = on_line
        if on_line:
            self.line_received.connect(on_line)

        self._pty_thread = threading.Thread(
            target=self._pipe_reader, args=(self._pty_gen,), daemon=True
        )
        self._pty_thread.start()

    def _pty_reader(self, master_fd: int, proc: subprocess.Popen, gen: int) -> None:
        buf = b""
        FLUSH_AFTER = 0.15   # emit partial prompt lines after this silence

        # Throttle repeated identical lines so a runaway process (e.g. USB
        # error loop) cannot flood the Qt event queue and freeze the UI.
        _last_line  = ""
        _repeat_cnt = 0
        _MAX_REPEAT = 4  # show a line up to this many times, then suppress

        def _emit(line: str) -> None:
            nonlocal _last_line, _repeat_cnt
            if line == _last_line:
                _repeat_cnt += 1
                if _repeat_cnt == _MAX_REPEAT:
                    self.line_received.emit("[…repeated output suppressed]")
                if _repeat_cnt >= _MAX_REPEAT:
                    return
            else:
                _last_line  = line
                _repeat_cnt = 0
            log.debug("[argyll-pty] %s", line)
            self.line_received.emit(line)

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
                    line = _ANSI_RE.sub("", raw.decode("utf-8", errors="replace")).rstrip("\r")
                    if line:
                        _emit(line)
            else:
                # Silence window — flush any partial prompt
                if buf:
                    line = _ANSI_RE.sub("", buf.decode("utf-8", errors="replace")).rstrip("\r")
                    buf = b""
                    if line:
                        _emit(line)

            # Safety net for a hung fd (e.g. a grandchild keeping the slave
            # side open): only stop on child exit once nothing is readable,
            # otherwise a >4 KB final output burst would be truncated. The
            # normal exit path is EOF (`not data`) above.
            if not r and proc.poll() is not None:
                break

        # Flush remainder
        if buf:
            line = _ANSI_RE.sub("", buf.decode("utf-8", errors="replace")).rstrip("\r")
            if line:
                self.line_received.emit(line)

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

        _last_line  = ""
        _repeat_cnt = 0
        _MAX_REPEAT = 4

        def _emit(line: str) -> None:
            nonlocal _last_line, _repeat_cnt
            if line == _last_line:
                _repeat_cnt += 1
                if _repeat_cnt == _MAX_REPEAT:
                    self.line_received.emit("[…repeated output suppressed]")
                if _repeat_cnt >= _MAX_REPEAT:
                    return
            else:
                _last_line  = line
                _repeat_cnt = 0
            log.debug("[argyll-pipe] %s", line)
            self.line_received.emit(line)

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
                        "", buf.decode("utf-8", errors="replace")
                    ).rstrip("\r")
                    buf = b""
                    if line:
                        _emit(line)
                continue

            if byte is None:
                break

            buf += byte
            if byte == b"\n":
                raw = buf.rstrip(b"\r\n")
                buf = b""
                line = _ANSI_RE.sub("", raw.decode("utf-8", errors="replace"))
                if line:
                    _emit(line)

        if buf:
            line = _ANSI_RE.sub(
                "", buf.decode("utf-8", errors="replace")
            ).rstrip("\r")
            if line:
                self.line_received.emit(line)

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
        on_line   = self._run_on_line
        self._run_on_finish = None
        self._run_on_line   = None
        if on_line:
            try:
                self.line_received.disconnect(on_line)
            except (TypeError, RuntimeError):
                pass
        log.info("ArgyllRunner (PTY): finished with code %d", code)
        self.finished.emit(code)
        if on_finish:
            on_finish(code)

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_ready_read(self) -> None:
        if not self._process:
            return
        raw = self._process.readAllStandardOutput().data()
        text = raw.decode("utf-8", errors="replace")
        for line in text.splitlines():
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
        if self._process:
            remaining = self._process.readAllStandardOutput().data()
            if remaining:
                text = remaining.decode("utf-8", errors="replace")
                for line in text.splitlines():
                    log.debug("[argyll] %s", line)
                    self.line_received.emit(line)

        # Capture per-run callbacks before they can be overwritten by a chained run()
        on_finish = self._run_on_finish
        on_line   = self._run_on_line
        self._run_on_finish = None
        self._run_on_line   = None
        try:
            self._process.readyReadStandardOutput.disconnect(self._on_ready_read)
            self._process.finished.disconnect(self._on_finished)
        except RuntimeError:
            pass
        if on_line:
            try:
                self.line_received.disconnect(on_line)
            except (TypeError, RuntimeError):
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

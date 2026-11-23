# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""One ChromIQ at a time, per settings store (4.3.59).

A tester's logs showed two ChromIQ windows open on the same project for 23 minutes: on
Windows a second double-click starts a second process. Two instances can overwrite each
other's settings and write the same run.

:func:`claim` is called by ``main.main()`` right after the ``QApplication`` exists and before
any window is built or the settings are opened. The first ChromIQ holds a ``QLockFile`` and
listens on a ``QLocalServer``; a second one finds the lock held, asks the first over a
``QLocalSocket`` to bring its window to the front (un-minimised), and quits. Only when the
first one cannot be reached does the second say so, in one short message.

THE LOCK BELONGS TO THE SETTINGS STORE, not to the machine:

* the real store (no ``CHROMIQ_SETTINGS_FILE``): one lock in the user's own ChromIQ log folder
  (``core.platform_paths.log_dir``, per user on every platform);
* a sandboxed store (``CHROMIQ_SETTINGS_FILE`` set, as every driver does): a lock beside that
  file. A driver's run never meets the user's own running ChromIQ, either way round, and two
  starts on the same sandbox file are one instance, as two apps on one store must be.

Only ``main.main()`` calls this. The test suite and the on-screen drivers
(``scripts/capture_screens.build_app``) never call ``main()``, so nothing here touches them.

A lock left by a ChromIQ that crashed is not a blocker: ``QLockFile`` checks whether the
process that holds it is still alive and takes the lock over when it is not (stale time 0:
never by age, only by the holder's death). A first instance that does not answer cannot
hold up the second one for longer than :data:`CONNECT_MS` plus :data:`REPLY_MS`.
"""
from __future__ import annotations

import hashlib
import os
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QLockFile, QObject, Qt
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from core.logger import get_logger

log = get_logger("chromiq.single_instance")

#: how long the second ChromIQ waits to reach the first one's server (ms)
CONNECT_MS = 1500
#: how long it then waits for the answer (ms): the first one answers from its event loop,
#: which a window being built can hold for a few seconds; a hung one costs no more than this
REPLY_MS = 8000
#: what the second sends, and what the first answers
SHOW = b"show\n"
SHOWN = b"shown\n"
LOCK_NAME = "chromiq-instance.lock"
#: NOT "<settings file>.lock": that is the name QSettings itself locks an .ini file with while
#: it writes it, and holding it for the life of the app hung every settings write (measured
#: 2026-11-23 on a sandboxed run: the event loop stopped at the first sync).
SANDBOX_LOCK_SUFFIX = ".chromiq-instance.lock"


def lock_path(environ=None) -> Path:
    """The lock file of the settings store this process would use (*environ*: the
    environment to read, ``os.environ`` when None)."""
    environ = os.environ if environ is None else environ
    from core.settings import SETTINGS_FILE_ENV
    sandbox = str(environ.get(SETTINGS_FILE_ENV, "") or "").strip()
    if sandbox:
        p = Path(sandbox).expanduser().absolute()
        return p.with_name(p.name + SANDBOX_LOCK_SUFFIX)
    from core.platform_paths import log_dir
    return log_dir() / LOCK_NAME


def server_name(lock: Path) -> str:
    """The local server's name for *lock*: one per lock, so per user and per settings store
    (a Windows pipe name is machine-wide; the path holds the user's own folder). Short,
    because a Unix socket path has a length limit."""
    digest = hashlib.sha256(str(Path(lock).absolute()).encode("utf-8")).hexdigest()[:20]
    return f"chromiq-{digest}"


class Guard(QObject):
    """The first ChromIQ's hold on its settings store: the lock and the local server.

    Keep it for the life of the app (``main()`` does). :meth:`set_window` names the window a
    second start brings to the front; a request that arrives before then is carried out
    when the window is named."""

    def __init__(self, lock: QLockFile, server: "QLocalServer | None", name: str):
        super().__init__()
        self.lock = lock
        self.server = server
        self.name = name
        self.window = None
        self.pending = False
        self.requests = 0
        if server is not None:
            server.newConnection.connect(self._on_connection)

    # ---- the first instance's side --------------------------------------------------
    def set_window(self, win) -> None:
        self.window = win
        if self.pending:
            self.pending = False
            self.bring_to_front()

    def _on_connection(self) -> None:
        while self.server is not None and self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            if sock is None:
                break
            sock.setParent(self)
            sock.readyRead.connect(self._on_ready)
            sock.disconnected.connect(sock.deleteLater)
            if sock.bytesAvailable():
                self._answer(sock)

    def _on_ready(self) -> None:
        sock = self.sender()
        if isinstance(sock, QLocalSocket):
            self._answer(sock)

    def _answer(self, sock: QLocalSocket) -> None:
        try:
            data = bytes(sock.readAll())
            if SHOW.strip() not in data:
                return
            self.requests += 1
            log.info("single instance: another ChromIQ was started on this settings store; "
                     "bringing this window to the front instead")
            sock.write(SHOWN)
            sock.flush()
            if self.window is None:
                self.pending = True
            else:
                self.bring_to_front()
        except Exception:      # noqa: BLE001 - a request never breaks the running app
            log.debug("single instance: request not handled", exc_info=True)

    def bring_to_front(self) -> None:
        """Show the main window, un-minimised, raised and active. Never raises."""
        win = self.window
        if win is None:
            return
        try:
            state = win.windowState()
            if state & Qt.WindowState.WindowMinimized:
                win.setWindowState((state & ~Qt.WindowState.WindowMinimized)
                                   | Qt.WindowState.WindowActive)
            if not win.isVisible():
                win.show()
            win.raise_()
            win.activateWindow()
            if sys.platform == "darwin":
                _activate_this_app_macos()
        except Exception:      # noqa: BLE001
            log.debug("single instance: could not bring the window to the front",
                      exc_info=True)

    def release(self) -> None:
        try:
            if self.server is not None:
                self.server.close()
            self.lock.unlock()
        except Exception:      # noqa: BLE001
            pass


def _activate_this_app_macos() -> None:
    """macOS 14 and later activate an app only when the active one yields to it: the second
    ChromIQ yields (:func:`_yield_to`) before it asks, and this takes it up."""
    try:
        import AppKit
        app = AppKit.NSApplication.sharedApplication()
        if hasattr(app, "activate"):
            app.activate()
        else:      # pragma: no cover - macOS 13
            app.activateIgnoringOtherApps_(True)
    except Exception:      # noqa: BLE001 - no pyobjc: Qt's own raise is what there is
        pass


def _yield_to(pid: int) -> None:
    """Let the first ChromIQ (process *pid*) take the foreground. Windows lets only the
    foreground process hand it on (AllowSetForegroundWindow); macOS 14 and later ask the
    active app to yield. Never raises."""
    if pid <= 0:
        return
    try:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(int(pid))
        elif sys.platform == "darwin":
            import AppKit
            other = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(int(pid))
            me = AppKit.NSApplication.sharedApplication()
            if other is not None and hasattr(me, "yieldActivationToApplication_"):
                me.yieldActivationToApplication_(other)
    except Exception:      # noqa: BLE001
        pass


def ask_first_to_show(name: str, pid: int = 0, timeout_ms: int = CONNECT_MS,
                      reply_ms: int = REPLY_MS) -> bool:
    """The second instance's side: ask the first to show its window. True when it said so;
    *timeout_ms* bounds the connection and the write, *reply_ms* the answer."""
    _yield_to(pid)
    sock = QLocalSocket()
    try:
        sock.connectToServer(name)
        if not sock.waitForConnected(timeout_ms):
            return False
        sock.write(SHOW)
        if not sock.waitForBytesWritten(timeout_ms):
            return False
        got = b""
        end = time.monotonic() + reply_ms / 1000.0
        while SHOWN.strip() not in got:
            left = int((end - time.monotonic()) * 1000)
            if left <= 0 or not sock.waitForReadyRead(left):
                return False
            got += bytes(sock.readAll())
        return True
    except Exception:      # noqa: BLE001
        return False
    finally:
        try:
            sock.abort()
        except Exception:      # noqa: BLE001
            pass


#: what :func:`claim` found
FIRST = "first"                  # this process holds the store: go on
SHOWN_OTHER = "shown_other"      # another ChromIQ holds it and brought its window up: quit
UNREACHABLE = "unreachable"      # another ChromIQ holds it and did not answer: say so, quit
NO_GUARD = "no_guard"            # the lock could not be made at all: go on, as before 4.3.59


def claim(lock_file: "Path | None" = None) -> "tuple[str, Guard | None]":
    """Claim this process's settings store. Called by ``main.main()`` only, after the
    QApplication exists and before any window or the settings. Never raises.

    Returns (:data:`FIRST`, guard) for the first ChromIQ; (:data:`SHOWN_OTHER`, None) when
    another was running and has come to the front; (:data:`UNREACHABLE`, None) when another
    holds the lock and did not answer; (:data:`NO_GUARD`, None) when no lock could be made
    (a read-only folder, say): the app then starts as it always did."""
    try:
        path = Path(lock_file) if lock_file is not None else lock_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        name = server_name(path)
        lock = QLockFile(str(path))
        lock.setStaleLockTime(0)        # stale only when its process is gone
        if not lock.tryLock(0):
            err = lock.error()
            if err != QLockFile.LockError.LockFailedError:
                log.warning("single instance: no lock at %s (%s); starting without one",
                            path.name, err)
                return NO_GUARD, None
            ok, pid, _host, _app = lock.getLockInfo()
            log.info("single instance: another ChromIQ (process %s) holds this settings "
                     "store; asking it to come to the front", pid if ok else "?")
            if ask_first_to_show(name, int(pid) if ok else 0):
                return SHOWN_OTHER, None
            log.warning("single instance: the running ChromIQ did not answer")
            return UNREACHABLE, None
        server = QLocalServer()
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if not server.listen(name):
            # we hold the lock, so a server of this name is a crashed ChromIQ's leftover
            QLocalServer.removeServer(name)
            if not server.listen(name):
                log.warning("single instance: no local server (%s); a second start will "
                            "say that ChromIQ is already running", server.errorString())
                server = None
        return FIRST, Guard(lock, server, name)
    except Exception:      # noqa: BLE001 - never stand between the user and the app
        log.warning("single instance: guard not set up", exc_info=True)
        return NO_GUARD, None


def tell_already_running() -> None:
    """The one message a user can see from this: the running ChromIQ could not be reached.
    In the language of the settings store, read only. Never raises."""
    try:
        from core.i18n import set_language, tr
        try:
            from core.settings import AppSettings
            set_language(AppSettings().get("language", "en"))
        except Exception:      # noqa: BLE001
            pass
        from PyQt6.QtWidgets import QMessageBox
        from ui.widgets import keep_message_box_inside_the_work_area
        box = QMessageBox(QMessageBox.Icon.Information, "ChromIQ",
                          tr("ChromIQ is already running."))
        keep_message_box_inside_the_work_area(box)
        box.exec()
    except Exception:      # noqa: BLE001
        pass

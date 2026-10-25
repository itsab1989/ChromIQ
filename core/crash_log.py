"""The native crash log, ``chromiq-crash.log`` beside ``chromiq.log``.

`main.py` arms Python's ``faulthandler`` into this file at start-up, so a
fatal signal inside Qt or Chromium (which never reaches ``sys.excepthook``)
still leaves the Python stack of every thread where the user already looks.

Three things make the file readable on its own (Basti, 2026-10-23, from
jctay's Windows log, forum post 149800):

* **THE START-UP LINE NAMES THE BUILD.** It said only "faulthandler armed"
  and a date; 202 of them in one file, and nothing told which release wrote
  which. It now ends with ``ChromIQ <version>``.
* **A CLEAN SHUTDOWN SAYS SO.** `main._hard_exit` writes "closed normally".
  A start-up line with no "closed normally" after it, and no stack either,
  is a session that ended some other way (killed, a crash faulthandler could
  not catch); one with a stack is a crash.
* **THE WINDOWS PRINT DIALOG IS NOT A CRASH.** On Windows ``faulthandler``
  reports every exception with the error bit set, including the FIRST-CHANCE
  COM exceptions that the system print dialog raises and handles itself
  (``0x8001010e`` RPC_E_WRONG_THREAD, ``0x80040155`` REGDB_E_IIDNOTREG):
  jctay's file held 254 "Windows fatal exception" dumps from printing, every
  one harmless, each looking exactly like a crash. `quiet_for_native_dialog`
  pauses ``faulthandler`` for the length of such a dialog, and only there,
  and only on Windows, and puts back exactly what was armed, also when the
  dialog raises. Everything outside that one call keeps its crash coverage.
* **IT DOES NOT GROW FOR EVER.** The file was opened for appending and never
  trimmed, so every start of ChromIQ added to it for as long as ChromIQ was
  installed: jctay's held 3,700 lines going back to July (forum post 149834,
  2026-10-25), most of them start-up lines and the print-dialog dumps above.
  `arm` now starts a fresh file once the old one passes `MAX_BYTES`, and keeps
  the previous one beside it as ``chromiq-crash.log.1`` (one copy, replaced
  the next time), the way ``chromiq.log`` rotates. A crash is never lost to
  this: the file is only ever moved aside at start-up, before anything is
  written, and the copy it replaces is the one before that.
"""
from __future__ import annotations

import faulthandler
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import IO, Iterator

#: The file faulthandler writes to, once `arm` has opened it. Kept for the
#: whole process: faulthandler writes to the raw descriptor, so letting the
#: object be collected would close it under faulthandler.
_file: "IO[str] | None" = None
_all_threads = True
#: How many `quiet_for_native_dialog` blocks are open (they may nest).
_depth = 0
#: Did the outermost open block switch faulthandler off?
_paused = False

FILE_NAME = "chromiq-crash.log"
#: Past this size the file is moved aside to ``chromiq-crash.log.1`` at the
#: next start-up. A session without a crash adds two short lines (about 120
#: bytes), so this is a couple of thousand sessions; one crash dump of every
#: thread is a few kilobytes.
MAX_BYTES = 256 * 1024
#: The one older copy that is kept.
OLD_SUFFIX = ".1"


def rotate_if_large(path: Path, max_bytes: int = MAX_BYTES) -> bool:
    """Move *path* aside to ``<name>.1`` (replacing an older ``.1``) when it
    is larger than *max_bytes*. True when it was moved. Never raises: a log
    that cannot be rotated is simply appended to, as before."""
    try:
        if path.stat().st_size <= max_bytes:
            return False
        import os
        os.replace(path, path.with_name(path.name + OLD_SUFFIX))
        return True
    except OSError:
        return False


def armed_line(version: str, when: "datetime | None" = None) -> str:
    """The line written at start-up, before faulthandler is switched on."""
    when = when or datetime.now()
    return f"\n=== faulthandler armed {when:%Y-%m-%d %H:%M:%S} ChromIQ {version} ===\n"


def closed_line(code: int, when: "datetime | None" = None) -> str:
    """The line written when ChromIQ shuts down cleanly."""
    when = when or datetime.now()
    tail = "" if code == 0 else f" (exit code {code})"
    return f"=== ChromIQ closed normally {when:%Y-%m-%d %H:%M:%S}{tail} ===\n"


def arm(directory: Path, version: str) -> "IO[str]":
    """Open ``chromiq-crash.log`` in *directory* (append), write the start-up
    line and switch faulthandler on into it, for every thread. Returns the
    open file. Raises on any failure, so the caller can fall back to stderr."""
    global _file, _all_threads
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    rotate_if_large(directory / FILE_NAME)
    f = open(directory / FILE_NAME, "a", encoding="utf-8")
    f.write(armed_line(version))
    f.flush()
    faulthandler.enable(file=f, all_threads=True)
    _file, _all_threads = f, True
    return f


def closed_normally(code: int = 0) -> None:
    """Write the clean-shutdown line, if `arm` opened the file. Never raises:
    it runs on the way out, where nothing may stop the exit."""
    f = _file
    if f is None:
        return
    try:
        f.write(closed_line(code))
        f.flush()
    except Exception:      # noqa: BLE001 - never block the exit
        pass


@contextmanager
def quiet_for_native_dialog() -> Iterator[None]:
    """Pause faulthandler around a native Windows dialog that raises and
    handles COM exceptions of its own (the system print dialog).

    Only on Windows, only when faulthandler is on, and only when `arm` is what
    switched it on (so it can be put back exactly: the same file, every
    thread). Anywhere else, or when someone else armed faulthandler, this does
    nothing at all. Nested blocks are fine: the outermost one restores. The
    restore runs in ``finally``, so a dialog that raises does not leave
    ChromIQ without crash coverage."""
    global _depth, _paused
    outer = _depth == 0
    _depth += 1
    if outer:
        _paused = False
        try:
            if (sys.platform == "win32" and _file is not None
                    and faulthandler.is_enabled()):
                faulthandler.disable()
                _paused = True
        except Exception:      # noqa: BLE001 - a pause is a courtesy
            _paused = False
    try:
        yield
    finally:
        _depth -= 1
        if outer and _paused:
            _paused = False
            try:
                faulthandler.enable(file=_file, all_threads=_all_threads)
            except Exception:      # noqa: BLE001 - last resort: stderr
                faulthandler.enable()

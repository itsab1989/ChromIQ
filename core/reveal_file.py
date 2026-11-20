# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""Show a file in the system's file manager, selected (4.3.50, A9: Help > Show the log file).

macOS: ``open -R <file>`` (Finder, the file selected). Windows: ``explorer /select,<file>``.
Linux and others: the folder, through ``xdg-open`` (no common way to select a file). A
missing file falls back to its folder, made if needed. Started detached, never waited
for; never raises (a failure is logged and False returned)."""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def reveal_command(path: Path, platform: "str | None" = None) -> "list[str]":
    """The command that shows *path* (the file selected where the system can)."""
    plat = platform or sys.platform
    p = Path(path)
    if plat == "darwin":
        return ["open", "-R", str(p)] if p.is_file() else ["open", str(p.parent)]
    if plat == "win32":
        return (["explorer", f"/select,{p}"] if p.is_file()
                else ["explorer", str(p.parent)])
    return ["xdg-open", str(p.parent)]


def reveal_file(path, platform: "str | None" = None, runner=None) -> bool:
    """Show *path* in the file manager. Returns True when the command was started."""
    try:
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        cmd = reveal_command(p, platform)
        (runner or subprocess.Popen)(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     stdin=subprocess.DEVNULL)
        log.info("log file shown: %s", p)
        return True
    except Exception as exc:      # noqa: BLE001
        log.warning("could not show %s in the file manager: %s", path, exc)
        return False

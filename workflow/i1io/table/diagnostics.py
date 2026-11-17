# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The table job's session log and results (build step 6).

The same content the tester program's results zip gave the analysis script
(``analyse_session_050.py``): a log of ``KIND  text`` lines (INFO, SEND, RECV, DATA, STEP, STOP,
RESULT; the table's clock in front of every table line), one RESULT block per step as JSON in the
log AND as ``<stage>-<n>/result.json``, the alignment as ``d1-<n>/alignment.json``, and
``summary.json`` with every block. The stage keys are the tester's where the job's step is the
tester's stage (``d1`` the alignment, ``dz`` the creep, ``d2`` the check move, ``f`` the homing);
the park is ``park``.

PRIVACY: never a serial number (the table's memory answers are never written down: the table
module logs only their length), never a person's or a computer's name, never a folder path. Every
line passes :func:`scrub` before it is written: the home folder, the session folder and the
user's name, if they appear by any route, are replaced; a long run of hex digits (the shape of a
memory answer) is replaced by its length. Written through the run's own members
(``Run.i1io_table_log``, ``Run.i1io_table_session_dir``) by the job.
"""
from __future__ import annotations

import getpass
import json
import os
import re
from pathlib import Path

HEX_RUN = re.compile(r"[0-9A-Fa-f]{24,}")


def _private_words() -> "list[str]":
    out = []
    try:
        home = os.path.expanduser("~")
        if home and home != "~":
            out.append(home)
    except Exception:      # noqa: BLE001
        pass
    try:
        user = getpass.getuser()
        if user and len(user) >= 3:
            out.append(user)
    except Exception:      # noqa: BLE001
        pass
    return out


def scrub(text: str, extra: "tuple[str, ...]" = ()) -> str:
    text = HEX_RUN.sub(lambda m: f"<{len(m.group(0))} hex digits not written>", str(text))
    for word in sorted(set(list(extra) + _private_words()), key=len, reverse=True):
        if word:
            text = text.replace(word, "<private>")
    return text


class Diagnostics:
    """The session folder's log and results. *folder* None: kept in memory only (tests)."""

    def __init__(self, folder: "Path | None", log_path: "Path | None" = None):
        self.folder = Path(folder) if folder is not None else None
        self.log_path = Path(log_path) if log_path is not None else (
            self.folder / "session.log" if self.folder is not None else None)
        self.lines: "list[str]" = []
        self.blocks: "list[dict]" = []
        self._extra = tuple(str(p) for p in (self.folder,) if p is not None)
        self._fh = None
        if self.folder is not None:
            self.folder.mkdir(parents=True, exist_ok=True)
            self._fh = open(self.log_path, "a", encoding="utf-8")

    def log(self, kind: str, text: str) -> None:
        line = f"{kind:6} {scrub(text, self._extra)}"
        self.lines.append(line)
        if self._fh is not None:
            try:
                self._fh.write(line + "\n")
                self._fh.flush()
            except (OSError, ValueError):
                pass

    def stage_dir(self, key: str, n: int) -> "Path | None":
        if self.folder is None:
            return None
        p = self.folder / f"{key}-{n}"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def write_json(self, rel: str, data) -> None:
        if self.folder is None:
            return
        text = scrub(json.dumps(data, indent=1, default=str), self._extra)
        try:
            path = self.folder / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError:
            pass

    def block(self, block: dict) -> None:
        self.blocks.append(block)
        self.log("RESULT", json.dumps(block, default=str))
        self.write_json(f"{block['folder']}/result.json", block)

    def finish(self) -> None:
        self.write_json("summary.json", self.blocks)
        if self._fh is not None:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None

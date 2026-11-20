# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The table job's session log and results (build step 6).

The same content the tester program's results zip gave the analysis script
(``analyse_session_050.py``): a log of ``KIND  text`` lines (INFO, SEND, RECV, DATA, STEP, STOP,
RESULT; the table's clock in front of every table line), one RESULT block per step as JSON in the
log AND as ``<stage>-<n>/result.json``, the alignment as ``d1-<n>/alignment.json``, and
``summary.json`` with every block. The stage keys are the tester's where the job's step is the
tester's stage (``d1`` the alignment, ``dz`` the creep, ``d2`` the check move (until 4.3.49), ``f`` the homing);
the park is ``park``.

4.3.48 (safety review 448, SHOULD-3): a row's result block carries ``data["second_moves"]``, one
entry per automatic second move to a patch the arm had stopped beside (0.6 to 1 mm off, read
twice). Each entry: ``what`` (the move), ``target`` (table units, 0.1 mm), ``readings_before``
(the arrival reading and the one read again 0.3 s later), ``readings_after`` (the reading after
the second move, and the one read again if the first was off), ``cured`` (True: it arrived;
False: it did not; None: it was not sent, because a stop or a problem came first), ``result`` in
words, ``took_s`` when the move took longer than recorded, and ``line`` (the line number in this
sitting). The same is in the log as DATA lines.

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

#: 4.3.52, "Keep the table's detailed log" OFF (design3 F7): the lines left out of a CLEAN
#: sitting's log (every SEND and RECV line, and the per-move "<cid> took x s" DATA lines, which
#: the compact MOVE line replaces). They are kept in a ring of the last RING_LINES lines, written
#: under RING_HEADING at the first stop, doubt, status, refusal, timeout, lost link, problem
#: report or ending that is not a clean Save (:meth:`Diagnostics.trip`); from then on every line
#: is written until the session ends. Every other line (INFO, STEP, STOP, RESULT, ANSWER, NOTE,
#: MOVE, the other DATA lines) is always written.
OPTIONAL_KINDS = ("SEND", "RECV")
_TOOK = re.compile(r"^\s*[0-9.]+\s+\S\S( \([^)]*\))? took [0-9.]+ s$")
RING_LINES = 300
RING_HEADING = "the 300 lines before this stop, kept because something stopped"


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

    def __init__(self, folder: "Path | None", log_path: "Path | None" = None,
                 detail: bool = True):
        #: 4.3.52: "Keep the table's detailed log" (True: every line, as before)
        self.detail = bool(detail)
        #: the optional lines of a clean sitting so far (only with detail False)
        self.ring: "list[str]" = []
        #: why the whole log is written from now on (None: not yet)
        self.tripped: "str | None" = None
        #: how many optional lines were left out of the file
        self.left_out = 0
        self.folder = Path(folder) if folder is not None else None
        # the log's own name is the Run's (Run.i1io_table_log): without it, no log file
        self.log_path = Path(log_path) if log_path is not None else None
        self.lines: "list[str]" = []
        self.blocks: "list[dict]" = []
        self._extra = tuple(str(p) for p in (self.folder,) if p is not None)
        self._fh = None
        if self.folder is not None:
            self.folder.mkdir(parents=True, exist_ok=True)
        if self.log_path is not None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(self.log_path, "a", encoding="utf-8")

    def optional(self, kind: str, text: str) -> bool:
        """A line "Keep the table's detailed log" may leave out of a clean sitting."""
        if kind in OPTIONAL_KINDS:
            return True
        return kind == "DATA" and bool(_TOOK.match(str(text)))

    def log(self, kind: str, text: str) -> None:
        line = f"{kind:6} {scrub(text, self._extra)}"
        try:
            if not self.detail and self.tripped is None and self.optional(kind, text):
                self.ring.append(line)
                if len(self.ring) > RING_LINES:
                    del self.ring[:-RING_LINES]
                self.left_out += 1
                return
        except Exception:      # noqa: BLE001 - when in doubt, the line is written
            pass
        self._put(line)

    def trip(self, why: str) -> None:
        """Something stopped, or the ending is not a clean Save: the ring is written under its
        heading, and every line from now on (only with detail False; once). Never raises."""
        try:
            if self.detail or self.tripped is not None:
                return
            self.tripped = str(why or "a stop")
            self._put(f"{'INFO':6} {RING_HEADING} ({scrub(self.tripped, self._extra)}); "
                      f"{len(self.ring)} lines follow, {self.left_out} were left out before "
                      "them in all")
            for ln in list(self.ring):
                self._put(ln)
            self.ring.clear()
            self._put(f"{'INFO':6} the kept lines end here; from now on every line is written")
        except Exception:      # noqa: BLE001
            pass

    def _put(self, line: str) -> None:
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
        if not self.detail and self.tripped is None:
            self._put(f"{'INFO':6} the detailed table log is switched off: {self.left_out} "
                      "SEND, RECV and move-time lines of this clean sitting were not written "
                      "(each movement has its MOVE line)")
        self.write_json("summary.json", self.blocks)
        if self._fh is not None:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None

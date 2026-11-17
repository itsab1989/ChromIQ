# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The end of a table session and what the next START finds (build step 8, job side, no UI).

What a session leaves is told in the EXISTING terms of the binding specifications
(``measurement_exit_strategy.md``, ``unified_measurement_management.md``): a measurement that is
complete or partial (§3a, by location), or nothing read (§1 row 5, M-END-EMPTY); the endings are
M-END's three (Save and stop, Discard and stop, Keep measuring). Ids and numbers only.

Here: which patches are missing, by page and row; the earlier sessions of a run as the next
START finds them (saved, discarded, or INTERRUPTED: a crash, a logout, a power cut left readings
and no ending), with their pending-strip-move markers; and setting a discarded session's folder
aside (moved into ``old/``, never deleted).
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import measurement as ms

#: what a session's folder says about how it ended
SAVED, DISCARDED, INTERRUPTED, EMPTY = "saved", "discarded", "interrupted", "nothing_read"


def locs_by_row(sheet: dict) -> "dict[str, tuple[int, int]]":
    """{location: (page, row)}, both 0-based, from the side file."""
    out = {}
    for p, pg in enumerate(sheet.get("pages", [])):
        for r, st in enumerate(pg.get("strips", [])):
            for q in st.get("patches", []):
                out[q["loc"]] = (p, r)
    return out


def missing_by_page(sheet: dict, missing) -> "list[dict]":
    """The missing patches grouped: [{"page": 1-based, "rows": [{"row": 1-based, "patches":
    n, "locs": [...]}]}], pages and rows in order."""
    where = locs_by_row(sheet)
    pages: "dict[int, dict[int, list[str]]]" = {}
    for loc in missing:
        if loc not in where:
            continue
        p, r = where[loc]
        pages.setdefault(p, {}).setdefault(r, []).append(loc)
    return [{"page": p + 1, "rows": [{"row": r + 1, "patches": len(locs), "locs": sorted(locs)}
                                      for r, locs in sorted(rows.items())]}
            for p, rows in sorted(pages.items())]


def _accepted(sdir: Path) -> int:
    n = 0
    for f, rec in ms.row_records([sdir]):
        n += len(rec.get("accepted") or [])
    return n


def session_state(sdir: Path) -> str:
    sdir = Path(sdir)
    if (sdir / ms.DISCARDED).is_file():
        return DISCARDED
    if (sdir / ms.SESSION_RESULT).is_file():
        return SAVED
    return INTERRUPTED if _accepted(sdir) else EMPTY


@dataclass(frozen=True)
class EarlierSession:
    stamp: str
    state: str                       # saved / discarded / interrupted / nothing_read
    accepted: int                    # readings its rows accepted
    pending_marker: bool             # a strip move may still have waited for the lamp
    marker_acknowledged: bool
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"stamp": self.stamp, "state": self.state, "accepted": self.accepted,
                "pending_marker": self.pending_marker,
                "marker_acknowledged": self.marker_acknowledged, **self.detail}


def earlier_sessions(run, exclude: "str | None" = None, chart_ti2=None) -> "list[EarlierSession]":
    """Every table session of *run* but *exclude*, oldest first, with how it ended. An
    INTERRUPTED one also says what its readings would make (complete / partial, how many,
    assembled into a throw-away file in its own folder: ``measurement.ti3``, nothing in the
    run)."""
    out = []
    for sdir in run.i1io_table_sessions():
        if sdir.name == exclude:
            continue
        state = session_state(sdir)
        marker = run.i1io_table_pending_marker(sdir.name)
        detail = {}
        if state == INTERRUPTED and chart_ti2 is not None:
            a = ms.assemble([sdir], chart_ti2, run.i1io_table_measurement(sdir.name))
            detail = {"would_make": a.state, "read": a.read, "expected": a.expected}
        out.append(EarlierSession(sdir.name, state, _accepted(sdir), marker.is_file(),
                                  marker.with_suffix(".acknowledged.json").is_file(), detail))
    return out


def set_aside(run, stamp: str) -> "Path | None":
    """Move a DISCARDED session's folder to ``Run.i1io_table_session_archive_dir`` (never
    deleted; the owner may decide later what to do with old/). Returns the new place, or None
    when the folder is not a discarded session (an interrupted or saved one is never moved), or
    when it still holds a pending-strip-move marker the person has not acknowledged (review 8,
    B-2): ``Run.i1io_table_pending_markers`` looks only under ``i1io-table/``, so a marker moved
    into ``old/`` would no longer make the next START ask "switched off and on"."""
    src = run.i1io_table_session_dir(stamp)
    if not src.is_dir() or session_state(src) != DISCARDED:
        return None
    if marker_unacknowledged(run, stamp):
        return None
    dst = run.i1io_table_session_archive_dir(stamp)
    if dst.exists():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return dst


def marker_unacknowledged(run, stamp: str) -> bool:
    """The session's pending-strip-move marker is there and nobody said "switched off and on"
    since (the ``.acknowledged.json`` beside it, written by the job's open())."""
    marker = run.i1io_table_pending_marker(stamp)
    return marker.is_file() and not marker.with_suffix(".acknowledged.json").is_file()


def write_json_now(path: Path, data) -> None:
    """A small JSON record written whole or not at all (a ``.part`` file, then one replace).
    Raises OSError: the caller says what was not recorded."""
    import os
    path = Path(path)
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


def mark_saved_by(sdir: Path, stamp: str, result: dict) -> None:
    """Review 8, M-4: an ADOPTED earlier session whose readings went into the measurement that
    the session *stamp* saved: it ended there (``saved``), and is never offered as interrupted
    again. Raises OSError."""
    write_json_now(Path(sdir) / ms.SESSION_RESULT, {"saved_by": stamp, **result})


def mark_discarded(sdir: Path, why: str) -> None:
    Path(sdir).mkdir(parents=True, exist_ok=True)
    (Path(sdir) / ms.DISCARDED).write_text(json.dumps({"discarded_by_person": True,
                                                       "why": why}), encoding="utf-8")

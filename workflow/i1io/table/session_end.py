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


def sha256_of(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def filing_note(measurement: Path, stamp: str) -> dict:
    """Review 8, S-4: written into every session folder that goes into a Save, BEFORE the run's
    file changes: the checksum of the measurement about to become the run's ``.ti3``."""
    return {"filing_by": stamp, "sha256": sha256_of(measurement)}


def filed_into(sdir: Path, run_ti3: "Path | None") -> bool:
    """The session's filing note names exactly the bytes the run's ``.ti3`` holds now: the Save
    reached the run, whatever happened after it (a crash before session_result.json)."""
    note = Path(sdir) / ms.FILING
    if run_ti3 is None or not note.is_file() or not Path(run_ti3).is_file():
        return False
    try:
        want = json.loads(note.read_text(encoding="utf-8")).get("sha256")
        return bool(want) and sha256_of(Path(run_ti3)) == want
    except (OSError, ValueError, AttributeError):
        return False


# ---- review 12, M-2 / M-3: which chart (and which dated verification) a session was read from --
#: written into every session folder when the job is made, before anything is read: the
#: checksum of the chart (.ti2) the session reads against, and what else it belongs to (a
#: verification's date, ``I1ioTablePlace.i1io_table_session_key``). A session is completed only
#: into a measurement of the same chart for the same place; anything else is refused.
IDENTITY = "chart_identity.json"
#: the reasons a session is not offered for completion (each has a sentence in the window; not
#: "session_...", which the window's reason_text reads as the command cap)
ANOTHER_CHART = "earlier_readings_of_another_chart"
ANOTHER_VERIFICATION = "earlier_readings_of_another_verification"
CHART_NOT_RECORDED = "earlier_readings_chart_unknown"


def place_key(place) -> "str | None":
    return getattr(place, "i1io_table_session_key", None)


def write_identity(sdir: Path, chart_ti2, place) -> None:
    """Record the chart's checksum and the place's key in *sdir* (once: an existing record is
    never rewritten). Raises OSError; a chart that cannot be read is recorded as unknown, and
    such a session is then never completed into anything."""
    sdir = Path(sdir)
    if (sdir / IDENTITY).is_file():
        return
    try:
        sha = sha256_of(Path(chart_ti2)) if chart_ti2 is not None else None
    except OSError:
        sha = None
    # the checksum and the key only: never the chart's name (the diagnostics stay private)
    write_json_now(sdir / IDENTITY, {"chart_sha256": sha, "belongs_to": place_key(place)})


def read_identity(sdir: Path) -> "dict | None":
    try:
        rec = json.loads((Path(sdir) / IDENTITY).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


def belongs_elsewhere(place, sdir: Path, chart_ti2) -> "str | None":
    """None when the session in *sdir* was read from exactly this chart for this place; else
    why not: ANOTHER_CHART (the chart's bytes differ: it was replaced, rebuilt, imported or
    an older one restored), ANOTHER_VERIFICATION (another date of the same chart), or
    CHART_NOT_RECORDED (a session with no record, or a chart that could not be read then or
    now: it cannot be proved to be this chart, so it is never completed into it)."""
    rec = read_identity(sdir)
    if rec is None or not rec.get("chart_sha256") or chart_ti2 is None:
        return CHART_NOT_RECORDED
    try:
        now = sha256_of(Path(chart_ti2))
    except OSError:
        return CHART_NOT_RECORDED
    if now != rec.get("chart_sha256"):
        return ANOTHER_CHART
    if rec.get("belongs_to") != place_key(place):
        return ANOTHER_VERIFICATION
    return None


def session_state(sdir: Path, run_ti3: "Path | None" = None) -> str:
    """saved / discarded / interrupted / nothing_read. With *run_ti3* (the run's measurement),
    a session whose filing note matches it counts as saved (S-4: the crash came after the
    run's file was written and before the result was recorded)."""
    sdir = Path(sdir)
    if (sdir / ms.DISCARDED).is_file():
        return DISCARDED
    if (sdir / ms.SESSION_RESULT).is_file():
        return SAVED
    if filed_into(sdir, run_ti3):
        return SAVED
    return INTERRUPTED if _accepted(sdir) else EMPTY


def settle_filed_sessions(run, exclude: "str | None" = None) -> "list[str]":
    """Review 8, S-4: every session whose Save reached the run but whose result was never
    recorded (its filing note matches the run's ``.ti3`` now) gets that result written, so it
    stays saved after the run's file changes again. Returns the stamps settled; a folder that
    cannot be written stays as it is (it is still recognised while the file is unchanged)."""
    done = []
    run_ti3 = Path(run.measurement_ti3)
    for sdir in run.i1io_table_sessions():
        if sdir.name == exclude or (sdir / ms.SESSION_RESULT).is_file() \
                or (sdir / ms.DISCARDED).is_file() or not filed_into(sdir, run_ti3):
            continue
        try:
            write_json_now(sdir / ms.SESSION_RESULT, {"filed": True, "result_recorded_later":
                                                      True})
            done.append(sdir.name)
        except OSError:
            pass
    return done


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
    settle_filed_sessions(run, exclude=exclude)
    run_ti3 = Path(run.measurement_ti3)
    for sdir in run.i1io_table_sessions():
        if sdir.name == exclude:
            continue
        state = session_state(sdir, run_ti3)
        marker = run.i1io_table_pending_marker(sdir.name)
        detail = {}
        elsewhere = belongs_elsewhere(run, sdir, chart_ti2 if chart_ti2 is not None
                                      else getattr(run, "chart_ti2", None)) \
            if state == INTERRUPTED else None
        if elsewhere:
            # review 12, M-2 / M-3: kept where it is and never offered for completion here
            rec = read_identity(sdir) or {}
            detail = {"belongs_elsewhere": elsewhere, "belongs_to": rec.get("belongs_to")}
        elif state == INTERRUPTED and chart_ti2 is not None:
            a = ms.assemble([sdir], chart_ti2, run.i1io_table_measurement(sdir.name))
            detail = {"would_make": a.state, "read": a.read, "expected": a.expected}
        out.append(EarlierSession(sdir.name, state, _accepted(sdir), marker.is_file(),
                                  marker.with_suffix(".acknowledged.json").is_file(), detail))
    return out


def offered_for_completion(e) -> bool:
    """An earlier session (an `EarlierSession` or its ``as_dict()``) the next START may offer
    to complete: interrupted, and read from this very chart for this place (review 12)."""
    d = e.as_dict() if isinstance(e, EarlierSession) else dict(e)
    return d.get("state") == INTERRUPTED and not d.get("belongs_elsewhere")


def set_aside(run, stamp: str) -> "Path | None":
    """Move a DISCARDED session's folder to ``Run.i1io_table_session_archive_dir`` (never
    deleted; the owner may decide later what to do with old/). Returns the new place, or None
    when the folder is not a discarded session (an interrupted or saved one is never moved), or
    when it still holds a pending-strip-move marker the person has not acknowledged (review 8,
    B-2): ``Run.i1io_table_pending_markers`` looks only under ``i1io-table/``, so a marker moved
    into ``old/`` would no longer make the next START ask "switched off and on"."""
    src = run.i1io_table_session_dir(stamp)
    if not src.is_dir() or session_state(src, run.measurement_ti3) != DISCARDED:
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
    """The session's pending-strip-move marker (or, fix round 10, its "table in use" marker)
    is there and nobody said "switched off and on" since (the ``.acknowledged.json`` beside
    it, written by the job's open(), or for the in-use marker by the job's close())."""
    for marker in (run.i1io_table_pending_marker(stamp), in_use_marker(run, stamp)):
        if marker.is_file() and not marker.with_suffix(".acknowledged.json").is_file():
            return True
    return False


# ---- fix round 10, B-1: "the table is in use" (write-ahead) ----------------------------------
#: written into the session folder when the job opens the table's USB, BEFORE the first line;
#: the job's close() acknowledges it. A session the app never closed (a kill, a crash, a power
#: cut, a logout that did not wait) leaves it unacknowledged, and the next START asks
#: "switched off and on" before anything is sent, exactly as for a strip move that may wait.
IN_USE_MARKER = "TABLE_IN_USE.json"
IN_USE_WHAT = "the table was in use; ChromIQ ended without closing it"
_APP_IN_USE_SUFFIX = "-in-use.json"


def in_use_marker(run, stamp: str) -> Path:
    return run.i1io_table_session_dir(stamp) / IN_USE_MARKER


def app_in_use_name(prefix: str, stamp: str) -> str:
    """The app-level twin (beside the app-level strip markers, the stamp only)."""
    return f"{prefix}{stamp}{_APP_IN_USE_SUFFIX}"


def is_in_use_marker(path) -> bool:
    name = Path(path).name
    return name == IN_USE_MARKER or name.endswith(_APP_IN_USE_SUFFIX)


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


def mark_discarded(sdir: Path, why: str, by: "str | None" = None) -> None:
    """*by*: the stamp of the session whose Discard took this (adopted) one with it."""
    Path(sdir).mkdir(parents=True, exist_ok=True)
    rec = {"discarded_by_person": True, "why": why}
    if by is not None:
        rec["discarded_with"] = by
    (Path(sdir) / ms.DISCARDED).write_text(json.dumps(rec), encoding="utf-8")


# ---- review 9, NOTE: the waiting strip move is a state of the TABLE, not of one run --------------
#: the app-level markers end in this (one file per session stamp, so an acknowledgement never
#: answers a later marker); WHERE they live is the app's choice, passed to the job
#: (``workflow/i1io/table_settle.py::app_marker_place``: ChromIQ's own settings folder, as the
#: i1Pro 2 lights marker; never a project folder). A marker holds the session's stamp only.
APP_MARKER_ACK = ".acknowledged.json"


#: an acknowledged app-level marker is removed with its acknowledgement after this many days
#: (review 11, NOTE: two files per session, never removed, globbed at every START)
APP_MARKER_KEEP_DAYS = 30


def prune_acknowledged_app_markers(folder, prefix: str, now: "float | None" = None,
                                   keep_days: float = APP_MARKER_KEEP_DAYS) -> "list[Path]":
    """Remove app-level markers whose acknowledgement is older than *keep_days*, with the
    acknowledgement (they hold the stamp only and are ChromIQ's own, in its settings folder;
    an unacknowledged marker is never touched). Returns the markers removed; never raises."""
    import time as _time
    now = _time.time() if now is None else now
    gone = []
    try:
        found = sorted(p for p in Path(folder).glob(prefix + "*.json")
                       if not p.name.endswith(APP_MARKER_ACK))
    except OSError:
        return gone
    for m in found:
        ack = acknowledged_path(m)
        try:
            if not ack.is_file() or now - ack.stat().st_mtime < keep_days * 86400:
                continue
            m.unlink()
            ack.unlink()
            gone.append(m)
        except OSError:
            continue
    return gone


def app_markers(folder, prefix: str) -> "list[Path]":
    """Every app-level marker in *folder* that is not acknowledged yet, oldest first.
    Acknowledged ones older than a month are pruned first."""
    prune_acknowledged_app_markers(folder, prefix)
    try:
        found = sorted(p for p in Path(folder).glob(prefix + "*.json")
                       if not p.name.endswith(APP_MARKER_ACK))
    except OSError:
        return []
    return [p for p in found if not acknowledged_path(p).exists()]


def acknowledged_path(marker: Path) -> Path:
    return Path(marker).with_suffix(APP_MARKER_ACK)


def project_markers(run) -> "list[Path]":
    """Every pending marker of EVERY run of the run's project (a START on another run still
    asks "switched off and on"), not acknowledged yet."""
    from .scan import PENDING_MARKER          # == Run.I1IO_TABLE_PENDING_MARKER (pinned)
    dirs = getattr(run, "i1io_table_project_dirs", None)
    found = []
    if callable(dirs):
        # round A: every table folder of the project (each run, each run's
        # verifications, cal/), as the table now drives every run type
        for d in dirs():
            try:
                found += sorted(Path(d).glob(f"*/{PENDING_MARKER}"))
                found += sorted(Path(d).glob(f"*/{IN_USE_MARKER}"))
            except OSError:
                continue
    else:
        runs_dir = Path(run.dir).parent
        table_dir = Path(run.i1io_table_dir).name
        try:
            found = sorted(runs_dir.glob(f"*/{table_dir}/*/{PENDING_MARKER}"))
            # fix round 10, B-1: and every session the app never closed
            found += sorted(runs_dir.glob(f"*/{table_dir}/*/{IN_USE_MARKER}"))
        except OSError:
            found = []
    own = [m for m in run.i1io_table_pending_markers() if m not in found]
    return [m for m in found + own if not acknowledged_path(m).exists()]

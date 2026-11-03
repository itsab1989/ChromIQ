"""Where an FD-9 measurement keeps its session evidence, and how long.

Every Start on an FD-9 chart records what the instrument sent: the pre-scan
image, the wire transcripts, the raw and calibrated samples and the exported
measurement. That is what lets a Resume continue a measurement, and what lets
a fault be looked into. It is also a few megabytes each time, and before this
module nothing removed any of it (review M8).

**Where.** ``<folder of the chart>/fd9-sessions/<session id>/``, through
:attr:`core.file_manager.Run.fd9_sessions_dir` (all path construction goes
through Run). For a profiling chart that is the run folder; for a
verification chart the run's ``verifications/`` folder, beside the chart.
The layout preview the Measure tab draws goes to the run's ``cache/``.

**How long.** Kept: every session that FILED data (its measurement was saved
into the run, now or before: it is marked so, or a ``.ti3`` beside the chart
or in ``old/`` names it), and every session that can still be resumed (the
caller passes those). Deleted: a session that ended without filing anything
and cannot be resumed, EXCEPT the newest such one, which stays so the last
failure can still be looked into.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

#: The marker written into a session whose measurement was filed.
FILED_MARKER = "filed.json"

_SESSION_KEYS = ("FD9_SOURCE_SESSIONS", "CHROMIQ_FD9_SESSION")


def _run_for(folder: Path):
    from core.file_manager import Run
    return Run.for_dir(Path(folder))


def sessions_dir(chart) -> Path:
    """The ``fd9-sessions`` folder beside *chart*."""
    return _run_for(Path(chart).parent).fd9_sessions_dir


def preview_cache_dir(chart) -> Path:
    """Where the Measure tab's FD-9 layout preview goes: the RUN's cache/,
    also for a chart in ``verifications/`` (no stray cache/ there)."""
    from core.file_manager import VERIFICATIONS_DIRNAME
    folder = Path(chart).parent
    if folder.name == VERIFICATIONS_DIRNAME:
        folder = folder.parent
    return _run_for(folder).cache_dir


def new_session_dir(chart) -> Path:
    """A fresh, not yet existing session folder for *chart*."""
    from uuid import uuid4
    return sessions_dir(chart) / uuid4().hex[:12]


def mark_filed(session) -> None:
    """Record that *session*'s measurement was saved into the run."""
    if not session:
        return
    root = Path(session)
    if root.is_dir():
        (root / FILED_MARKER).write_text(json.dumps({"filed": True}) + "\n",
                                         encoding="utf-8")


def _named_sessions(ti3: Path) -> "set[str]":
    try:
        head = ti3.read_bytes()[:65536].decode("utf-8", "replace")
    except OSError:
        return set()
    head = head.split("BEGIN_DATA_FORMAT", 1)[0]
    out: "set[str]" = set()
    for key in _SESSION_KEYS:
        m = re.search(r'^' + key + r'\s+"([^"\n]*)"', head, re.M)
        if m:
            out.update(s for s in m.group(1).split(",") if s)
    return out


def filed_sessions(chart) -> "set[str]":
    """Names of the sessions a measurement of *chart* was filed from: the
    ``.ti3`` beside it and every ``.ti3`` in ``old/``."""
    chart = Path(chart)
    names: "set[str]" = set()
    candidates = [chart.with_suffix(".ti3")]
    old = chart.parent / "old"
    if old.is_dir():
        candidates += list(old.rglob("*.ti3"))
    for ti3 in candidates:
        if ti3.is_file():
            names |= _named_sessions(ti3)
    return names


def prune_sessions(chart, keep=()) -> "list[Path]":
    """Apply the retention rule to *chart*'s sessions. Returns what was
    removed. *keep* names sessions that can still be resumed or are running."""
    root = sessions_dir(chart)
    if not root.is_dir():
        return []
    keep = {str(k) for k in keep if k}
    filed = filed_sessions(chart)
    unfiled = []
    for session in root.iterdir():
        if not session.is_dir() or not re.fullmatch(r"[A-Za-z0-9_-]+", session.name):
            continue
        if session.name in keep or session.name in filed:
            continue
        if (session / FILED_MARKER).is_file():
            continue
        try:
            stamp = max([session.stat().st_mtime]
                        + [p.stat().st_mtime for p in session.iterdir()])
        except OSError:
            continue
        unfiled.append((stamp, session))
    unfiled.sort()
    removed = []
    for _stamp, session in unfiled[:-1]:      # the newest stays, for diagnosis
        shutil.rmtree(session, ignore_errors=True)
        if not session.exists():
            removed.append(session)
    return removed

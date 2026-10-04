"""Put a measurement's damaged copy of the printer calibration back (beta 7).

A chart made with a printer calibration (``-K`` applied or ``-I`` included)
carries the calibration as a ``CAL`` table in its ``.ti2``, and chartread copies
that table into the ``.ti3``. ChromIQ's measuring engine wrote the copy as
``nan`` before 4.3.3-beta.7 (one line in the vendored ``rspl1.c``; see
``native/instlib/PROVENANCE.md``). On another compiler the same fault can leave
numbers that are simply wrong. Every ArgyllCMS tool that loads such a ``.ti3``
(colprof, profcheck, average, colverify, a resumed chartread) either refuses
it ("Field 'CMYK_C' has unexpected type") or, past four inks, reads every
curve as zero.

The readings themselves are fine, and the chart still holds the table intact.
Basti ruled on 2026-10-03: repair the measurement IN PLACE, keep the original
in ``old/``, keep the yellow confirmed marks. So :func:`repair_embedded_cal`:

* acts only when the ``.ti3`` carries a calibration table that DIFFERS from the
  chart's AND is not a plausible calibration (not finite, outside 0..1,
  constant or non-monotonic in a channel; a plausible one that merely differs
  is logged and left alone), AND the ``.ti2`` is provably the chart that was
  measured: the same table shape and input column, the same device columns,
  and the same device values for every ``SAMPLE_ID`` the measurement holds;
* copies the original ``.ti3`` (and its ``.confirmed.json``) to the run's
  ``old/<date-time>/`` first (a verification's to its date's ``old/``, as the
  session guard does), and does nothing at all if that copy fails;
* replaces ONLY the first ``CAL`` table, byte for byte from the chart, and
  leaves every reading, keyword and the file's time stamp as they were;
* re-stamps ``<stem>.confirmed.json`` (``-verify.confirmed.json`` for a
  verification) for the repaired file, when it described the original;
* logs it, and tells whoever registered with :func:`set_notifier` (the main
  window shows M-CAL-TABLE-REPAIRED once).

It is called before every Argyll tool that loads a measurement ``.ti3``; the
hooks are listed in ``tests/test_cal_repair.py``. Nothing here imports Qt.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import weakref
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from core.logger import get_logger

log = get_logger(__name__)

#: Two calibration tables are the same when every value agrees to this. Both
#: are printed with six significant digits by Argyll's CGATS writer, so an
#: honest copy differs by rounding (< 1e-6); a damaged one by whole units or
#: by being ``nan``.
TABLE_TOLERANCE = 1e-5

#: How far a device value may sit from the chart's before the chart counts
#: as a different chart. Shared with the calibration-mode rules.
from workflow.printer_calibration import DEVICE_TOLERANCE  # noqa: E402

_HEADER_RE = re.compile(r"^(CTI1|CTI2|CTI3|CAL)[ \t]*\r?$", re.M)


@dataclass(frozen=True)
class CalRepair:
    """One measurement whose calibration table was put back."""

    ti3: Path
    chart: Path
    archive: Path            # the original, as it was, under old/<date-time>/
    confirmed_kept: bool     # a .confirmed.json was re-stamped for the new file


# ---------------------------------------------------------------------------
# Who hears about a repair (the UI registers; workflow code never shows text)
# ---------------------------------------------------------------------------

_notifier: "Callable[[], Callable[[CalRepair], None] | None] | None" = None


def set_notifier(fn: "Callable[[CalRepair], None] | None") -> None:
    """Register the one function told about every repair (or None to clear).

    A bound method is held weakly, so a closed main window is not kept alive
    by this module and is simply not told any more."""
    global _notifier
    if fn is None:
        _notifier = None
    elif hasattr(fn, "__self__") and hasattr(fn, "__func__"):
        _notifier = weakref.WeakMethod(fn)
    else:
        _notifier = lambda fn=fn: fn  # noqa: E731 — a plain function, held strongly


def _notify(rep: CalRepair) -> None:
    fn = _notifier() if _notifier is not None else None
    if fn is None:
        return
    try:
        fn(rep)
    except Exception:      # noqa: BLE001 — telling must never stop the tool
        log.warning("could not report the calibration-table repair",
                    exc_info=True)


# ---------------------------------------------------------------------------
# Reading tables
# ---------------------------------------------------------------------------

def _read_latin1(path: Path) -> str:
    """The file as text that writes back byte for byte (latin-1 round-trips
    every byte, and the tables themselves are ASCII)."""
    return Path(path).read_bytes().decode("latin-1")


def _first_cal_span(text: str) -> "tuple[int, int] | None":
    """(start, end) of the first ``CAL`` table: from its header line to the
    next table's header line, or to the end of the file."""
    heads = list(_HEADER_RE.finditer(text))
    for i, m in enumerate(heads):
        if m.group(1) == "CAL" and m.start() > 0:
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            return m.start(), end
    return None


@dataclass
class _Table:
    fields: "list[str]"
    rows: "list[list[str]]"


def _parse_table(block: str) -> "_Table | None":
    fm = re.search(r"BEGIN_DATA_FORMAT\s*\n(.*?)\n\s*END_DATA_FORMAT", block, re.S)
    dm = re.search(r"BEGIN_DATA\s*\n(.*?)\n\s*END_DATA\b", block, re.S)
    if not (fm and dm):
        return None
    fields = fm.group(1).split()
    rows = [ln.split() for ln in dm.group(1).splitlines() if ln.strip()]
    return _Table(fields, rows)


def _num(tok: str) -> "float | None":
    try:
        v = float(tok)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _numeric(t: _Table) -> bool:
    return bool(t.rows) and all(
        len(r) == len(t.fields) and all(_num(x) is not None for x in r)
        for r in t.rows)


def _same_shape(a: _Table, b: _Table) -> bool:
    return a.fields == b.fields and len(a.rows) == len(b.rows)


def _same_table(a: _Table, b: _Table) -> bool:
    if not (_same_shape(a, b) and _numeric(a) and _numeric(b)):
        return False
    for ra, rb in zip(a.rows, b.rows):
        for x, y in zip(ra, rb):
            if abs(_num(x) - _num(y)) > TABLE_TOLERANCE:
                return False
    return True


def _same_input_column(a: _Table, b: _Table) -> bool:
    """The ``*_I`` column (the curve's input grid) survives the engine fault
    as numbers, so it must agree exactly where the other columns cannot."""
    cols = [i for i, f in enumerate(a.fields) if f.endswith("_I")]
    if not cols:
        return False
    for ra, rb in zip(a.rows, b.rows):
        for i in cols:
            x, y = (_num(ra[i]) if i < len(ra) else None,
                    _num(rb[i]) if i < len(rb) else None)
            if x is None or y is None or abs(x - y) > TABLE_TOLERANCE:
                return False
    return True


#: A calibration curve maps 0..1 to 0..1; Argyll prints six digits, so a
#: value a hair outside still counts as inside.
RANGE_EPSILON = 1e-3
#: A curve may wobble by this much against its direction and still count as
#: monotonic (rounding of a flat stretch).
MONOTONIC_EPSILON = 1e-4


def _plausible(t: _Table) -> bool:
    """Whether a numeric table can be a real printer calibration: every
    channel finite, inside 0..1, not constant, and monotonic (either way).

    A table that passes is NEVER replaced, even when it differs from the
    chart's: a measurement printed with another calibration carries exactly
    that, and only an implausible table is the engine fault (Basti's ruling
    after the review of aad896d8: data safety first)."""
    if not _numeric(t):
        return False
    chans = [i for i, f in enumerate(t.fields) if not f.endswith("_I")]
    if not chans:
        return False
    for i in chans:
        col = [_num(r[i]) for r in t.rows]
        if any(v < -RANGE_EPSILON or v > 1.0 + RANGE_EPSILON for v in col):
            return False
        if max(col) - min(col) <= 1e-6:
            return False
        steps = [b - a for a, b in zip(col, col[1:])]
        if not (all(s >= -MONOTONIC_EPSILON for s in steps)
                or all(s <= MONOTONIC_EPSILON for s in steps)):
            return False
    return True


def cal_table_damaged(ti3: "Path | str") -> bool:
    """Whether *ti3* carries a calibration table that is not all numbers.

    The build-failed window asks this, so it blames the table ChromIQ wrote
    and not the person, only when the table is what colprof refused."""
    try:
        text = _read_latin1(Path(ti3))
    except OSError:
        return False
    span = _first_cal_span(text)
    if span is None:
        return False
    t = _parse_table(text[span[0]:span[1]])
    return t is not None and not _numeric(t)


# ---------------------------------------------------------------------------
# Is this .ti2 the chart that was measured?
# ---------------------------------------------------------------------------

def _is_the_measured_chart(ti3: Path, ti2: Path) -> bool:
    """Same device columns, and the same device values for every SAMPLE_ID
    the measurement holds (all of which the chart must have)."""
    from workflow.printer_calibration import device_fields_of, read_table
    try:
        f3, r3, _ = read_table(ti3)
        f2, r2, _ = read_table(ti2)
    except (OSError, ValueError):
        return False
    dev3, dev2 = device_fields_of(f3), device_fields_of(f2)
    if not dev3 or set(dev3) != set(dev2) or not r3:
        return False
    for sid, row3 in r3.items():
        row2 = r2.get(sid)
        if row2 is None:
            return False
        for f in dev3:
            a, b = _num(row3.get(f, "")), _num(row2.get(f, ""))
            if a is None or b is None or abs(a - b) > DEVICE_TOLERANCE:
                return False
    return True


def _chart_candidates(ti3: Path) -> "list[Path]":
    """Every chart this measurement may have been made from, nearest first.

    Beside it (a run's own chart, ``<stem>.ti2``), then each folder above it up
    to the project: its chart files, its per-date ``chart/`` snapshot, and the
    charts kept in its ``old/<date-time>/`` (newest first) when a stored chart
    was replaced. That covers a run's measurement, ``reads/readN.ti3``, a dated
    verification and a copy under ``old/`` that "Build anyway" builds from.
    """
    out: "list[Path]" = []
    seen: "set[Path]" = set()

    def add(p: Path) -> None:
        if p.is_file() and p not in seen:
            seen.add(p)
            out.append(p)

    add(ti3.with_suffix(".ti2"))
    d = ti3.parent
    for _ in range(6):
        for p in sorted(d.glob("*.ti2")):
            add(p)
        for p in sorted((d / "chart").glob("*.ti2")):
            add(p)
        old = d / "old"
        if old.is_dir():
            for stamp in sorted((x for x in old.iterdir() if x.is_dir()),
                                reverse=True):
                for p in sorted((stamp / "chart").glob("*.ti2")):
                    add(p)
                for p in sorted(stamp.glob("*.ti2")):
                    add(p)
        if (d / "project.json").is_file() or d.parent == d:
            break
        d = d.parent
    return out


# ---------------------------------------------------------------------------
# Where the original goes
# ---------------------------------------------------------------------------

def _home_of(ti3: Path) -> Path:
    """The folder whose ``old/`` keeps the original: the run (``runs/runN``)
    or the calibration folder (``cal``) the measurement belongs to, wherever
    under it the file sits; else the measurement's own folder.

    A verification's history stays inside ``verifications/``, as the session
    guard keeps it (§2a: ``runs/runN/verifications/<date>/old/``): a dated
    measurement's original goes to its date's ``old/``, a file in the
    ``verifications/`` root to ``verifications/old/``."""
    for d in ti3.parents:
        if d.name == "verifications" and d.parent.parent.name == "runs":
            rel = ti3.relative_to(d).parts
            return d / rel[0] if len(rel) > 1 else d
        if d.parent.name == "runs":
            return d
        if d.name == "cal" and (d.parent / "project.json").is_file():
            return d
        if (d / "project.json").is_file():
            break
    return ti3.parent


def _in_a_project(ti3: Path) -> bool:
    return any((d / "project.json").is_file() for d in ti3.parents)


def _just_archived(home: Path, ti3: Path) -> "Path | None":
    """The copy of exactly these bytes the session guard put in the newest
    ``old/<date-time>/`` (a resumed measurement is archived at Start, just
    before the reader asks for the repair), so the original is kept once."""
    old = home / "old"
    try:
        stamps = sorted((x for x in old.iterdir() if x.is_dir()), reverse=True)
    except OSError:
        return None
    if not stamps:
        return None
    try:
        data = ti3.read_bytes()
        me = ti3.resolve()
        for p in sorted(stamps[0].glob(ti3.stem + "*" + ti3.suffix)):
            # never the file itself: a copy under old/ being repaired
            # ("Build anyway") must still get an original of its own
            if p.resolve() == me:
                continue
            if p.is_file() and p.stat().st_size == len(data) \
                    and p.read_bytes() == data:
                return p
    except OSError:
        return None
    return None


def _archive(ti3: Path, when: datetime) -> "Path | None":
    from workflow.confirmed_patches import confirmed_path
    home = _home_of(ti3)
    if not _in_a_project(ti3) and not os.access(home, os.W_OK):
        log.warning("%s is outside any project and its folder cannot be "
                    "written, so no copy can be kept beside it; its "
                    "calibration table is left as it is", ti3.name)
        return None
    same = _just_archived(home, ti3)
    if same is not None:
        try:
            mem, kept = confirmed_path(ti3), confirmed_path(same)
            if mem.is_file() and not kept.is_file():
                shutil.copy2(mem, kept)
        except OSError:
            pass
        log.info("%s was archived just now as %s; that copy is the original",
                 ti3.name, same)
        return same
    dest = home / "old" / when.strftime("%Y-%m-%d_%H%M%S")
    try:
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / ti3.name
        n = 1
        while target.exists():
            target = dest / f"{ti3.stem}_{n}{ti3.suffix}"
            n += 1
        shutil.copy2(ti3, target)
        mem = confirmed_path(ti3)
        if mem.is_file():
            shutil.copy2(mem, confirmed_path(target))
    except OSError:
        log.warning("could not keep %s in old/ before repairing its "
                    "calibration table; it is left as it is", ti3.name,
                    exc_info=True)
        return None
    return target


# ---------------------------------------------------------------------------
# The repair
# ---------------------------------------------------------------------------

def repair_embedded_cal(ti3: "Path | str", ti2: "Path | str | None" = None,
                        *, when: "datetime | None" = None) -> "CalRepair | None":
    """Put the chart's calibration table back into *ti3* when its copy is
    damaged. Returns what was done, or None when nothing was (no table, the
    tables already agree, or no chart can be proved to be the one measured).

    *ti2* names the chart; when None, the chart is looked for beside and above
    the measurement (:func:`_chart_candidates`). Never raises.
    """
    try:
        return _repair(Path(ti3), None if ti2 is None else Path(ti2), when)
    except Exception:      # noqa: BLE001 — a repair must never stop the tool
        log.warning("calibration-table check of %s failed", ti3, exc_info=True)
        return None


def _repair(ti3: Path, ti2: "Path | None",
            when: "datetime | None") -> "CalRepair | None":
    if not ti3.is_file() or ti3.suffix.lower() != ".ti3":
        return None
    text = _read_latin1(ti3)
    span = _first_cal_span(text)
    if span is None:
        return None                      # no calibration: the usual case
    mine = _parse_table(text[span[0]:span[1]])
    if mine is None:
        return None

    cands = [ti2] if ti2 is not None else _chart_candidates(ti3)
    proved: "list[tuple[Path, str, _Table]]" = []
    for cand in cands:
        if cand is None or not cand.is_file():
            continue
        try:
            ctext = _read_latin1(cand)
        except OSError:
            continue
        cspan = _first_cal_span(ctext)
        if cspan is None:
            continue
        theirs = _parse_table(ctext[cspan[0]:cspan[1]])
        if theirs is None or not _numeric(theirs):
            continue
        if not (_same_shape(mine, theirs)
                and _same_input_column(mine, theirs)
                and _is_the_measured_chart(ti3, cand)):
            continue
        if _same_table(mine, theirs):
            return None                  # it already carries this chart's table
        proved.append((cand, ctext[cspan[0]:cspan[1]], theirs))

    if not proved:
        if not _numeric(mine):
            log.warning(
                "%s carries a damaged printer-calibration table, and no chart "
                "could be proved to be the one it measured (looked at: %s); "
                "it is left as it is", ti3.name,
                ", ".join(str(c) for c in cands if c is not None) or "none")
        return None

    if _plausible(mine):
        # It differs from the chart's, but it is a calibration a printer can
        # have: the measurement may well have been printed with it. Left as
        # it is; a person can decide.
        log.info(
            "%s carries a printer-calibration table that differs from the "
            "chart %s but is a plausible calibration (finite, 0..1, monotonic); "
            "it is left as it is", ti3.name, proved[0][0].name)
        return None
    chart, block, _theirs = proved[0]
    from workflow import confirmed_patches as cp
    before_sha = cp.ti3_sha256(ti3)
    st = ti3.stat()
    archive = _archive(ti3, when or datetime.now())
    if archive is None:
        return None

    new_text = text[:span[0]] + block + text[span[1]:]
    # A link is followed, not replaced by a file of its own; and the file
    # keeps its permissions (a read-only measurement stays read-only).
    dest = ti3.resolve() if ti3.is_symlink() else ti3
    tmp = dest.with_name(dest.name + ".cal-repair")
    try:
        tmp.write_bytes(new_text.encode("latin-1"))
        shutil.copymode(dest, tmp)
        os.replace(tmp, dest)
    except OSError:
        log.warning("could not write the repaired %s; the original is "
                    "unchanged and kept in %s", ti3.name, archive.parent,
                    exc_info=True)
        try:
            tmp.unlink()
        except OSError:
            pass
        return None
    try:
        # The readings did not change, so neither does the file's date: a
        # report or a list that orders by it must not see a new measurement.
        os.utime(dest, ns=(st.st_atime_ns, st.st_mtime_ns))
    except OSError:
        pass
    kept = cp.carry(ti3, before_sha, ti3) is not None
    rep = CalRepair(ti3=ti3, chart=chart, archive=archive, confirmed_kept=kept)
    log.info(
        "repaired the printer-calibration table of %s from the chart %s "
        "(the earlier engine wrote it damaged); readings unchanged; original "
        "kept as %s%s", ti3, chart.name, archive,
        "; confirmed patches re-stamped" if kept else "")
    _notify(rep)
    return rep


def repair_all(paths: "Iterable[Path | str | None]") -> "list[CalRepair]":
    """:func:`repair_embedded_cal` for each measurement, chart looked up."""
    out = []
    for p in paths:
        if p is None:
            continue
        rep = repair_embedded_cal(p)
        if rep is not None:
            out.append(rep)
    return out

"""Which verification files in a run belong to an earlier profile (#182).

Knut, #182 5964384250 Q1: a rebuild archives the profile only, and *"Only
after selecting run type = verification and this window pops up, 'Make a new
chart from current profile' shall also include 'and archive old verification
runs into old/ folder'"*. This module is the decision half of that window: it
answers, without a window and without touching the disk, which dated
measurements and whether the live chart were made with a profile the run no
longer has. ``ui/earlier_profile_offer.py`` asks the question.

**THE ANCHOR IS THE PROFILE'S OWN HEADER, NOT A FILE TIME.** ``P`` is the
creation time in the ICC header of ``Run.built_profile_icc()``. ArgyllCMS
writes it in UTC, so it is converted with the offset that was valid ON THAT
DATE (``astimezone()``), never today's: a summer build checked in winter would
otherwise be an hour off. File modification times are never used. They are
reset by a copy, a zip or a sync, and every value below is content that
travels with the project.

A dated folder counts only when it holds a measurement, and it is from an
earlier profile when ANY of these is earlier than ``P``:

* **its folder name** (``YYYY-MM-DD_HHMMSS``, local time): measured before the
  replacement, so its sheet was printed before it too;
* **its own chart snapshot's ``CREATED``** (``<date>/chart/<stem>-reference.ti3``):
  a FROM PROFILE GAMUT chart chosen by the earlier profile, measured after the
  build. This is how Knut's run2 ``2026-10-03_005807`` is caught;
* **its own print record's ``printed_at``**, beside the ``.ti3`` or in the
  date's ``chart/`` snapshot. NEVER the shared ``verifications/<stem>.print.json``:
  that describes the chart's LAST print, so a date measured after the build
  from a sheet printed elsewhere would be flagged for a print it never had.

The live chart is stale when it carries a colorimetric reference (it is a
FROM PROFILE GAMUT chart) whose ``CREATED`` is earlier than ``P``. An ordinary
chart is never stale: it is printed through whatever profile the run has now,
and Knut ruled it is kept and used as it is (5964384250 Q2).

Never raises: any failure means "nothing found", so the window stays quiet
rather than offering to move something on a guess.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class EarlierItems:
    """What a run holds from an earlier profile."""

    #: The current profile's header time, local and naive; None when the run
    #: has no readable profile (and then nothing else is filled).
    profile_when: "datetime | None" = None
    #: Dated folder ids measured with an earlier profile, oldest first.
    dates: "tuple[str, ...]" = ()
    #: The live verification chart is a FROM PROFILE GAMUT chart made from an
    #: earlier profile.
    chart_stale: bool = False
    #: That chart's CREATED, local and naive; None when not stale.
    chart_when: "datetime | None" = None
    #: ``verifications/reports`` documents none of whose dates stays at the top
    #: level once ``dates`` move.
    documents: "tuple[Path, ...]" = field(default_factory=tuple)

    @property
    def variant(self) -> str:
        """"A", "B", "C", or "" when there is nothing to ask about."""
        if self.dates and self.chart_stale:
            return "A"
        if self.dates:
            return "B"
        if self.chart_stale:
            return "C"
        return ""


def profile_created(icc_path: Path) -> "datetime | None":
    """The ICC header's creation time as local, naive time, or None."""
    try:
        from workflow.icc_info import read_icc
        raw = read_icc(icc_path).created
        if not raw:
            return None
        utc = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc)
        # THE OFFSET OF THAT DATE, not of today (summer time).
        return utc.astimezone().replace(tzinfo=None)
    except Exception:      # noqa: BLE001 — no profile date means no question
        return None


def folder_time(vid: str) -> "datetime | None":
    """``2026-10-03_005807[_n]`` as a local, naive time; None otherwise."""
    try:
        return datetime.strptime(vid[:17], "%Y-%m-%d_%H%M%S")
    except (TypeError, ValueError):
        return None


def reference_created(reference: Path) -> "datetime | None":
    """``CREATED`` of a colorimetric reference file, or None."""
    try:
        from core.cgats_date import parse_created_datetime
        from workflow.gamut_target import read_colorimetric_reference
        ref = read_colorimetric_reference(reference)
        if not ref:
            return None
        return parse_created_datetime(ref.get("created") or "")
    except Exception:      # noqa: BLE001
        return None


def _own_printed_at(v) -> "datetime | None":
    """``printed_at`` of the date's OWN print record (beside the ``.ti3`` or in
    its ``chart/`` snapshot), never the shared one beside the live chart."""
    stem = v.stem
    for cand in (v.dir / f"{stem}.print.json",
                 v.dir / "chart" / f"{stem}.print.json"):
        try:
            if not cand.is_file():
                continue
            data = json.loads(cand.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        raw = str(data.get("printed_at") or "").strip()
        if not raw:
            return None
        try:
            when = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if when.tzinfo is not None:
            when = when.astimezone().replace(tzinfo=None)
        return when
    return None


def _date_is_earlier(v, p: datetime) -> bool:
    when = folder_time(v.id)
    if when is not None and when < p:
        return True
    snap = v.dir / "chart" / f"{v.stem}-reference.ti3"
    if snap.is_file():
        created = reference_created(snap)
        if created is not None and created < p:
            return True
    printed = _own_printed_at(v)
    return printed is not None and printed < p


def _documents_leaving(run, moving: "set[str]") -> "tuple[Path, ...]":
    """The ``verifications/reports`` documents to move with *moving*: those
    covering at least one moving date and no date that stays at the top level
    of ``verifications/``. A date archived earlier is no longer at the top
    level, so it does not hold a document back."""
    from core.file_manager import REPORTS_DIRNAME
    from workflow import measurement_report as MR

    folder = run.verifications_dir / REPORTS_DIRNAME
    try:
        paths = sorted(folder.glob("report_*.json")) if folder.is_dir() else []
    except OSError:
        return ()
    staying = {MR.project_relative(v.dir) for v in run.verifications()
               if v.id not in moving}
    leaving = {MR.project_relative(run.verification(vid).dir)
               for vid in moving}
    out = []
    for path in paths:
        try:
            block = MR.recorded_document(MR.report_object(
                json.loads(path.read_text(encoding="utf-8"))))
        except Exception:      # noqa: BLE001 — unreadable: it stays
            continue
        if block is None:
            continue
        covers = {MR.project_relative(m.get("dir") or "")
                  for m in block.get("measurements") or [] if m.get("dir")}
        if covers & leaving and not covers & staying:
            out.append(path)
    return tuple(out)


def earlier_profile_items(run) -> EarlierItems:
    """What *run* holds from an earlier profile. Never raises."""
    try:
        p = profile_created(run.built_profile_icc())
        if p is None:
            return EarlierItems()
        dates = tuple(v.id for v in run.verifications()
                      if v.exists() and _date_is_earlier(v, p))
        chart_stale, chart_when = False, None
        try:
            ti2 = run.verify_chart_ti2
            if ti2.exists():
                from workflow.verification_print import (
                    colorimetric_reference_for)
                ref = colorimetric_reference_for(ti2)
                if ref.is_file():
                    created = reference_created(ref)
                    if created is not None and created < p:
                        chart_stale, chart_when = True, created
        except Exception:      # noqa: BLE001
            chart_stale, chart_when = False, None
        docs = _documents_leaving(run, set(dates)) if dates else ()
        return EarlierItems(p, dates, chart_stale, chart_when, docs)
    except Exception:      # noqa: BLE001 — a question never worth a crash
        log.warning("could not tell what belongs to an earlier profile",
                    exc_info=True)
        return EarlierItems()

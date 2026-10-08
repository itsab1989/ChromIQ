"""Read a print job's real ticket back from CUPS and say what it carries.

Until beta 14 the native macOS route "verified" colour management by reading back
the very dictionary it had just written, which could not fail and did not look at
the job (phase-1 investigation, 2026-10-08).  This module asks the printing system
instead: Get-Job-Attributes over IPP (pycups, the user's own job, no password),
and compares the colour-relevant keys with what ChromIQ asked for.

Pure Python apart from the optional ``cups`` module; every function degrades to
"could not read" where CUPS is absent (Windows) instead of raising.

The read-back never runs on the GUI thread (review 2026-10-08: up to ~1 s of
retries plus CUPS calls froze the window).  ``BackgroundReadBack`` runs it on a
daemon thread; the Print Chart tab polls it from a timer and gives up after
``READ_BACK_TIMEOUT_S``, saying the job could not be read back.
"""
from __future__ import annotations

import getpass
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from core.logger import get_logger
from workflow.ppd_color import (APPLICATION_COLOUR_MATCHING, PaperProfile,
                                paper_profile_for)

log = get_logger(__name__)

try:  # pragma: no cover - depends on the platform
    import cups as _cups
except Exception:  # noqa: BLE001
    _cups = None


@dataclass
class TicketReport:
    """What the job in CUPS carries, against what ChromIQ asked for."""

    queue: str
    job_id: int | None
    read: bool
    expected: dict[str, str]
    carried: dict[str, str] = field(default_factory=dict)
    mismatches: dict[str, tuple[str | None, str]] = field(default_factory=dict)
    paper_profile: PaperProfile | None = None
    #: native route: the description of the profile the chart was tagged with
    #: (for the log; the comparison is by bytes, ``tagged_icc``)
    tagged_with: str | None = None
    #: True when the tag is, byte for byte, the job's own paper profile (an
    #: identity match); False when it is not, or the chart went untagged
    tag_matches_job: bool | None = None
    #: Canon rule: "off" / "on" for the printer's own colour processing
    own_colour_processing: str | None = None

    @property
    def ok(self) -> bool:
        return self.read and not self.mismatches and self.tag_matches_job is not False

    def summary(self) -> str:
        """One log line, keys and values as CUPS holds them."""
        if not self.read:
            return f"job {self.job_id} on {self.queue}: ticket could not be read"
        keys = ", ".join(f"{k}={v}" for k, v in sorted(self.carried.items()))
        extra = ""
        if self.tagged_with is not None:
            extra = f"; chart tagged with {self.tagged_with!r} (matches job: {self.tag_matches_job})"
        bad = "" if not self.mismatches else f"; MISMATCH {self.mismatches}"
        return f"job {self.job_id} on {self.queue}: {keys}{extra}{bad}"


def _colour_keys(attrs: dict) -> dict[str, str]:
    out = {}
    for k, v in attrs.items():
        if (k in ("AP_ColorMatchingMode", "ColorSync") or k.startswith(("CNIJ", "EPIJ"))
                or "ColorMatching" in k or "Profile" in k):
            out[k] = str(v)
    return out


def find_job(queue: str, since: float, user: str | None = None) -> int | None:
    """The newest job on *queue* owned by *user* created at or after *since*."""
    if _cups is None:
        return None
    user = user or getpass.getuser()
    try:
        conn = _cups.Connection()
        jobs = conn.getJobs(which_jobs="all", my_jobs=True,
                            requested_attributes=["job-id", "job-printer-uri",
                                                  "time-at-creation",
                                                  "job-originating-user-name"])
    except Exception as exc:  # noqa: BLE001
        log.warning("print ticket: listing jobs failed: %s", exc)
        return None
    best = None
    for jid, a in jobs.items():
        if not str(a.get("job-printer-uri", "")).endswith("/" + queue):
            continue
        if a.get("job-originating-user-name") not in (None, user):
            continue
        if a.get("time-at-creation", 0) + 2 < since:
            continue
        best = jid if best is None else max(best, jid)
    return best


def read_ticket(job_id: int) -> dict | None:
    if _cups is None or job_id is None:
        return None
    try:
        return _cups.Connection().getJobAttributes(job_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("print ticket: reading job %s failed: %s", job_id, exc)
        return None


def check_job(queue: str, job_id: int | None, expected: dict[str, str],
              ppd_text: str | None = None, tagged_with: str | None = None,
              tagged_icc: bytes | None = None, retries: int = 5) -> TicketReport:
    """Read job *job_id* back and compare it with *expected*.  Blocking: call
    it through ``BackgroundReadBack``, never on the GUI thread.

    *ppd_text*, when given, lets the report name the paper profile the job selects
    (``ppd_color.paper_profile_for`` applied to the job's own options).
    *tagged_icc* is the ICC profile the native route tagged the chart with (b""
    when it went untagged, None when the route does not tag); it is compared BY
    BYTES with the job's paper-profile file (review 2026-10-08: the description
    was compared before, which two different profiles can share).
    *tagged_with* is that profile's description, for the log only.
    """
    attrs = None
    for _ in range(max(1, retries)):
        attrs = read_ticket(job_id) if job_id is not None else None
        if attrs:
            break
        time.sleep(0.2)
    rep = TicketReport(queue=queue, job_id=job_id, read=bool(attrs),
                       expected=dict(expected), tagged_with=tagged_with)
    if not attrs:
        return rep
    rep.carried = _colour_keys(attrs)
    for k, want in expected.items():
        raw = attrs.get(k)
        if not _same_value(raw, want):
            rep.mismatches[k] = (None if raw is None else str(raw), want)
    if ppd_text:
        opts = {k: str(v) for k, v in attrs.items() if isinstance(v, (str, int))}
        # the profile the JOB selects (its own option value), not the one its
        # medium's name maps to: a medium the rule does not know (or names
        # differently) must not turn into a false "not as sent" alarm
        pp = paper_profile_for(ppd_text, opts, honour_profile_option=True)
        if pp is not None:
            carried = opts.get(pp.option)
            if carried is None:
                # the job names no paper profile: the PPD default is what applies
                pp = paper_profile_for(ppd_text, {pp.rule.media_option: "__none__"})
            rep.paper_profile = pp
            if pp is not None and pp.rule.own_colour_off_needs_paper_profile:
                app = attrs.get("AP_ColorMatchingMode") == \
                    APPLICATION_COLOUR_MATCHING["AP_ColorMatchingMode"]
                named = carried is not None and carried != _default_of(ppd_text, pp)
                rep.own_colour_processing = "off" if (app and named) else "on"
            if tagged_icc is not None and pp is not None and pp.icc_path:
                try:
                    rep.tag_matches_job = bool(tagged_icc) and \
                        Path(pp.icc_path).read_bytes() == tagged_icc
                except OSError:
                    rep.tag_matches_job = None
    log.info("print ticket: %s", rep.summary())
    return rep


def _same_value(got, want: str) -> bool:
    """Is the job attribute *got* (as pycups returns it) the option value *want*
    ChromIQ sent?  cupsd stores an option value "true"/"false" as an IPP
    boolean, so pycups hands back True/False; compare those as words."""
    if got is None:
        return False
    if isinstance(got, bool):
        return want.strip().lower() == ("true" if got else "false")
    return str(got) == want


def _default_of(ppd_text: str, pp: PaperProfile) -> str | None:
    from workflow.ppd_color import _ppd_default
    return _ppd_default(ppd_text, pp.option)


#: How long the Print Chart tab waits for the read-back before it says the job
#: could not be read.  The read itself is five tries 0.2 s apart plus two IPP
#: requests; ten seconds leaves a loaded machine room and still answers soon.
READ_BACK_TIMEOUT_S = 10.0


class BackgroundReadBack:
    """Run one blocking read-back (*work*, returning a ``TicketReport``) on a
    daemon thread.  The GUI thread asks ``poll()``: "pending", "done" (the
    report is in ``report``) or "timeout" (the thread is abandoned; a daemon
    thread cannot keep the app from quitting).  Nothing here touches Qt."""

    def __init__(self, work: Callable[[], "TicketReport"],
                 timeout: float = READ_BACK_TIMEOUT_S) -> None:
        self.report: TicketReport | None = None
        self.error: BaseException | None = None
        self.thread_name: str | None = None
        self._done = threading.Event()
        self._deadline = time.monotonic() + timeout
        self._work = work
        self._thread = threading.Thread(target=self._run, name="print-read-back",
                                        daemon=True)
        self._thread.start()

    def _run(self) -> None:
        self.thread_name = threading.current_thread().name
        try:
            self.report = self._work()
        except BaseException as exc:  # noqa: BLE001 - reported, never raised here
            self.error = exc
            log.warning("print ticket: read-back failed: %s", exc)
        finally:
            self._done.set()

    def poll(self) -> str:
        if self._done.is_set():
            return "done"
        if time.monotonic() >= self._deadline:
            return "timeout"
        return "pending"

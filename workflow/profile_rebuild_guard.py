"""Whether rebuilding a profile would strand a run's verification measurements.

Specification §6 — ``docs/design/unified_measurement_management.md``. The
decision half only: it answers "should this warn, and with what numbers", so
every row of §6e is testable without a window.

**Why this warning exists.** A verification chart is printed *through* the
profile in its run, so a dated verification measurement records how *that
profile* behaved on that day. Replace the profile and the measurements do not
become wrong — Knut was right to correct that, and the report's metrics are
built to compare across charts and runs of the same printer — but they lose
their **origin**: nothing on disk then says which profile a given date was
measured against.

**What this deliberately does not do.** An earlier draft proposed recording a
build signature so an identical rebuild could stay silent. Knut dropped it
(#130, 2026-08-03): *"The main intention is to make user aware, then the user is
given authority to act responsibly on an informed basis."* Rebuilding with the
same settings is neither dangerous nor the likely case, and detecting it bought
precision nobody needed at the cost of a new file format. The escape is a
per-run, per-session "don't show this again" instead.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class RebuildWarning:
    """What §6e says about this build, and the numbers its message needs."""

    needed: bool
    dated: int = 0
    oldest: str = ""
    reason: str = ""
    #: Which of the four required files Duplicate is missing, if any. When this
    #: is non-empty the message must not offer Duplicate as a button — §4a's
    #: second half: recommending a greyed control is useless advice.
    duplicate_blocked_by: "list[str]" = field(default_factory=list)

    @property
    def can_duplicate(self) -> bool:
        return not self.duplicate_blocked_by


#: The files a run needs before it can be duplicated, and how to name them.
DUPLICATE_REQUIRES = (
    ("chart_ti1", "the patch list (.ti1)"),
    ("chart_ti2", "the laid-out chart (.ti2)"),
    ("chart_channels_json", "the chart's layout recipe (.channels.json)"),
)


def readable_date(vid: str) -> str:
    """A verification folder id as something to read in a sentence.

    The folders are named ``2026-03-14_100000`` so they sort; that trailing
    time is machinery, and "going back to 2026-03-14_100000" reads like a
    serial number. The date alone is unambiguous in every language, which a
    spelled-out month would not be. Anything unexpected is passed through
    unchanged rather than guessed at.
    """
    head = (vid or "").split("_", 1)[0]
    parts = head.split("-")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return head
    return vid


def _missing_for_duplicate(run) -> "list[str]":
    missing = []
    for attr, label in DUPLICATE_REQUIRES:
        try:
            if not getattr(run, attr).exists():
                missing.append(label)
        except Exception:      # noqa: BLE001 — a message, never a crash
            missing.append(label)
    try:
        if not run.chart_tiffs():
            missing.append("at least one printed page (.tif)")
    except Exception:      # noqa: BLE001
        pass
    return missing


def assess(run, *, silenced: bool = False) -> RebuildWarning:
    """Row of §6e for *run*.

    *run* may be ``None`` — Build Profile also works on a measurement loaded
    from anywhere, and that case has no run and no history, so it never warns.
    """
    if run is None:
        return RebuildWarning(False, reason="no run — a loaded file has no history")
    if silenced:
        return RebuildWarning(False, reason="silenced for this run this session")
    try:
        if not run.built_profile_icc().exists():
            return RebuildWarning(False, reason="no profile yet — first build")
        if not run.has_verify_chart():
            return RebuildWarning(False, reason="no verification chart")
        dated = [v for v in run.verifications() if v.exists()]
    except Exception:      # noqa: BLE001 — never block a build over this
        log.warning("could not assess the rebuild guard", exc_info=True)
        return RebuildWarning(False, reason="could not be assessed")

    if not dated:
        return RebuildWarning(
            False, reason="a verification chart with no measurements is just a chart")

    return RebuildWarning(
        True, dated=len(dated), oldest=readable_date(dated[0].id),
        reason="the run's verification measurements were made against this profile",
        duplicate_blocked_by=_missing_for_duplicate(run))

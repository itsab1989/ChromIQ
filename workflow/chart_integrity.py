"""What replacing a chart would cost the run it lives in.

Specification §4 and §4a — ``docs/design/unified_measurement_management.md``.
The decision half only: it answers *"is there something here to lose, and
what"*, so every row of §4 and §4a is testable without a window.

**The premise.** A `.ti3` describes one chart, and a profile describes one
`.ti3`. Change the chart and the set stops belonging together — the same
problem §5 has from the other end.

**Why the chart definition is imported rather than written again.**
``workflow/chart_slot.py`` is what Restore Used Chart compares and copies. A
second opinion here would mean a warning that talks about files a restore does
not touch, or silence about files it does.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from core.logger import get_logger
from workflow.chart_slot import has_layout_recipe, slot_for_run
from workflow.measurement_state import Ti3State, classify

log = get_logger(__name__)


class Blast(Enum):
    """How far replacing the chart reaches — §4's table, one row each."""

    #: Nothing on disk depends on the chart.
    NONE = "none"
    #: A measurement, and possibly a profile, would stop matching.
    RUN = "run"
    #: …and the run's dated verification measurements lose the profile they
    #: were made through. §4's W4 — "the widest blast radius of the three".
    RUN_AND_HISTORY = "run_and_history"
    #: Replacing the *verification* chart under dated verification
    #: measurements. §4's W5 — the same shape, one level down.
    VERIFY_HISTORY = "verify_history"


@dataclass(frozen=True)
class ChartCost:
    """What §4 says about replacing this chart, and the numbers its message
    needs. Everything is a count or a name; no sentence is built here."""

    blast: Blast = Blast.NONE
    #: Readings in the measurement that would stop matching, if there is one.
    readings: int = 0
    #: True when that measurement covers the whole chart (§5's COMPLETE).
    complete: bool = False
    #: A measurement file is present, whatever state it is in.
    has_measurement: bool = False
    #: A profile built from that measurement is present.
    has_profile: bool = False
    #: Dated verification measurements with readings in them.
    verifications: int = 0
    #: Page images that exist now.
    pages: int = 0
    #: False for §4a rows 3 and 5 — there is no `.channels.json`, so ChromIQ
    #: cannot redraw the pages and the printed sheets are the only copy.
    can_redraw_pages: bool = True
    #: Which of Duplicate's four requirements are absent, by name. Non-empty →
    #: the message must not recommend Duplicate (M-DUPLICATE-BLOCKED).
    duplicate_blocked_by: "list[str]" = field(default_factory=list)
    reason: str = ""

    @property
    def warn(self) -> bool:
        return self.blast is not Blast.NONE

    @property
    def can_duplicate(self) -> bool:
        return not self.duplicate_blocked_by

    @property
    def pages_are_the_only_copy(self) -> bool:
        """§4a row 5 — page images that cannot be redrawn from anything."""
        return self.pages > 0 and not self.can_redraw_pages


def _attr(run, name):
    """*run*.*name*, or None. ``getattr`` with a default only swallows
    AttributeError, and a Run backed by a vanished folder can raise OSError."""
    try:
        return getattr(run, name, None)
    except Exception:      # noqa: BLE001
        return None


def _exists(path) -> bool:
    try:
        return path.exists()
    except Exception:      # noqa: BLE001
        return False


def _profile_exists(run) -> bool:
    """The run's profile, however this object spells it.

    ``built_profile_icc()`` is the real name and prefers ``merged.icc``; the
    plain ``profile_icc`` is the fallback so a partial stand-in for a Run — or
    a future one — still gets an honest answer instead of a silent no.
    """
    for attr in ("built_profile_icc", "profile_icc"):
        try:
            value = getattr(run, attr)
            path = value() if callable(value) else value
            return path.exists()
        except Exception:      # noqa: BLE001
            continue
    return False


def _pages(files) -> int:
    return sum(1 for p in files if p.suffix.lower() in (".tif", ".tiff"))


def _missing_for_duplicate(run) -> "list[str]":
    """Duplicate's requirement, §4a row 6 — reused so a message never
    recommends a control the user would find greyed out."""
    from workflow.profile_rebuild_guard import DUPLICATE_REQUIRES

    missing = []
    for attr, label in DUPLICATE_REQUIRES:
        try:
            if not getattr(run, attr).exists():
                missing.append(label)
        except Exception:      # noqa: BLE001
            missing.append(label)
    try:
        if not run.chart_tiffs():
            missing.append("at least one printed page (.tif)")
    except Exception:      # noqa: BLE001
        pass
    return missing


def _dated_verifications(run) -> int:
    try:
        return sum(1 for v in run.verifications() if v.exists())
    except Exception:      # noqa: BLE001
        return 0


def assess_profiling_chart(run) -> ChartCost:
    """§4's table for replacing the **profiling** chart of *run*.

    *run* may be ``None`` — Generate Chart also works with no project open, and
    that case has nothing on disk to strand.
    """
    if run is None:
        return ChartCost(reason="no run — nothing on disk to lose")
    try:
        files = slot_for_run(run).live_files()
    except Exception:      # noqa: BLE001 — a warning, never a crash
        log.warning("could not read the chart of %s", run, exc_info=True)
        files = []

    # Each of the three is asked for on its own. A run whose measurement cannot
    # be read must still be warned about for the profile it holds, and the
    # other way round — one unreadable file is not a reason to fall silent
    # about everything else.
    ti3 = _attr(run, "measurement_ti3")
    has_measurement = bool(ti3 is not None and _exists(ti3))
    facts = None
    if has_measurement:
        try:
            facts = classify(ti3, _attr(run, "chart_ti2"))
        except Exception:      # noqa: BLE001
            log.warning("could not read the measurement of %s", run,
                        exc_info=True)
    has_profile = _profile_exists(run)

    readings = 0
    complete = False
    if facts is not None and facts.state in (Ti3State.PARTIAL,
                                             Ti3State.COMPLETE,
                                             Ti3State.MISMATCHED):
        readings = facts.held or 0
        complete = facts.state is Ti3State.COMPLETE

    verifications = _dated_verifications(run)
    if not has_measurement and not has_profile and verifications == 0:
        # §4 rows 1 and 2, and §4a rows 1, 2, 7 and 8: a chart with nothing
        # under it, a patch list, a stray image, nothing at all. Regenerating
        # costs a reprint, and the user is the one who asked for a new chart.
        return ChartCost(reason="nothing has been measured in this run")

    # Note that the test above asks whether the measurement FILE is there, not
    # whether it could be read. A file holding no usable readings is still
    # something this run holds and something the archive would move, and going
    # quiet about it is precisely Knut's #131 complaint. Its state only decides
    # whether the message can put a number on it.

    # Note what does NOT appear above: whether the run still holds a complete
    # chart. It was tempting to stay silent without a `.ti1` and `.ti2` — but
    # the loss this warning is about is the *measurement*, and a run can hold
    # one while its chart files are incomplete. Staying quiet there is exactly
    # Knut's #131 complaint, where a measurement was archived without a word.
    # Chart completeness only decides whether the pages can be drawn again.

    blast = Blast.RUN_AND_HISTORY if verifications else Blast.RUN
    return ChartCost(
        blast=blast,
        readings=readings, complete=complete, has_measurement=has_measurement,
        has_profile=has_profile,
        verifications=verifications,
        pages=_pages(files), can_redraw_pages=has_layout_recipe(files),
        duplicate_blocked_by=_missing_for_duplicate(run),
        reason="work in this run was made with the chart being replaced")


def assess_verification_chart(run) -> ChartCost:
    """§4's W5 — replacing the **verification** chart of *run*.

    One level down and a different loss: no measurement in the run stops
    matching, but the dated verification measurements lose the chart they were
    readings *of*.
    """
    if run is None:
        return ChartCost(reason="no run — nothing on disk to lose")
    try:
        if not run.has_verify_chart():
            return ChartCost(reason="no verification chart to replace")
        n = _dated_verifications(run)
    except Exception:      # noqa: BLE001
        log.warning("could not read the verification chart", exc_info=True)
        return ChartCost(reason="the verification chart could not be read")

    if not n:
        return ChartCost(
            reason="a verification chart with no measurements is just a chart")

    try:
        files = [p for p in run.verifications_dir.iterdir()
                 if p.is_file() and not p.name.startswith(".")]
    except Exception:      # noqa: BLE001
        files = []
    return ChartCost(
        blast=Blast.VERIFY_HISTORY,
        verifications=n,
        pages=_pages(files), can_redraw_pages=has_layout_recipe(files),
        duplicate_blocked_by=_missing_for_duplicate(run),
        reason="the run's verification measurements were made with this chart")

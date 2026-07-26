"""The shared "Profile run" + "Run type" selection for #130.

Create Chart, Print Chart and Measure all bind to ONE ``MeasurementTarget`` (the
app's single source of truth), so moving between the tabs is seamless and the
right chart is always the one shown / printed / measured. This module holds the
pure model + the resolution logic that maps a target to the concrete
``Run`` / ``Verification`` it reads or writes — no Qt, fully unit-testable.

Vocabulary mirrors the UI labels exactly (Knut): **"Profile run"** and
**"Run type"** (values ``"profiling"`` / ``"verification"``).
"""
from __future__ import annotations

from dataclasses import dataclass

from core.file_manager import Project, Run, Verification

RUN_TYPE_PROFILING = "profiling"
RUN_TYPE_VERIFICATION = "verification"

# verification_blocked_reason() codes:
BLOCK_NEW_RUN = "new_run"        # can't verify a run that doesn't exist yet
BLOCK_NO_PROFILE = "no_profile"  # the selected run has no built profile
BLOCK_NO_CHART = "no_chart"      # no verification chart defined for the run


@dataclass
class MeasurementTarget:
    """The active selection shared across the first three tabs.

    - ``run_type``        — ``"profiling"`` | ``"verification"``
    - ``profile_run``     — an existing run id to overwrite, or ``""`` = new run
    - ``verification_id`` — an existing dated verification id to overwrite, or
      ``""`` = a new verification (only meaningful for ``"verification"``)
    """

    run_type: str = RUN_TYPE_PROFILING
    profile_run: str = ""
    verification_id: str = ""

    def is_verification(self) -> bool:
        return self.run_type == RUN_TYPE_VERIFICATION

    def is_new_run(self) -> bool:
        return not self.profile_run

    def is_new_verification(self) -> bool:
        return self.is_verification() and not self.verification_id

    def status_label(self) -> str:
        """The short status-strip text, e.g. "run 1 · verification · new"."""
        run = self.profile_run or "new run"
        if not self.is_verification():
            return f"{run} · profiling"
        when = self.verification_id or "new"
        return f"{run} · verification · {when}"


# ---------------------------------------------------------------------------
# Resolution — target → concrete Run / Verification
# ---------------------------------------------------------------------------

def resolve_run(project: Project, target: MeasurementTarget,
                *, create: bool = False) -> Run:
    """The run the target points at. An existing ``profile_run`` wins; otherwise
    the project's current run, or a freshly created run when ``create`` and the
    target asks for a new run."""
    if target.profile_run and project.has_run(target.profile_run):
        return project.run(target.profile_run)
    if create and target.is_new_run():
        return project.new_run()
    return project.current_run()


def resolve_measurement(project: Project, target: MeasurementTarget,
                        *, create: bool = False) -> "Run | Verification":
    """Where a measurement is written — a ``Run`` (profiling) or a
    ``Verification`` (an existing dated id, or a new one). Both expose
    ``measurement_ti3``, ``reads_dir`` and ``reports_dir``. With ``create`` the
    target folders are materialised on disk."""
    run = resolve_run(project, target, create=create)
    if not target.is_verification():
        return run
    if target.verification_id:
        return run.verification(target.verification_id)
    verification = run.new_verification()
    if create:
        verification.ensure_dir()
    return verification


def verify_tool_dirs(project: "Project | None",
                     target: "MeasurementTarget | None" = None
                     ) -> "tuple[Path, Path]":
    """Browse-default folders for the Verify-a-Profile tool's two file pickers,
    as ``(profile_icc_dir, measurement_ti3_dir)`` (#130, Knut's cascade).

    - profile .icc: the target/current run's folder → the project root.
    - measurement .ti3: the selected dated verification → the run's
      ``verifications/`` (defaulting to its latest date) → the run folder →
      the project root.

    Both fall back to ``~/ChromIQ`` when no project is loaded, so the dialog
    always opens somewhere sensible."""
    from pathlib import Path
    home = Path.home() / "ChromIQ"
    if project is None:
        return home, home
    run = (resolve_run(project, target) if target is not None
           else project.current_run())
    profile_dir = run.dir if run.dir.exists() else project.root
    meas_dir = run.dir
    if run.verifications_dir.exists():
        meas_dir = run.verifications_dir
        if target is not None and target.verification_id:
            cand = run.verification(target.verification_id).dir
            if cand.exists():
                meas_dir = cand
        else:
            history = run.verifications()
            if history:
                meas_dir = history[-1].dir          # latest verification
    if not meas_dir.exists():
        meas_dir = project.root
    return profile_dir, meas_dir


def verification_blocked_reason(project: Project,
                                target: MeasurementTarget) -> "str | None":
    """Why a verification can't start for this target, or ``None`` (Hole 1).

    A verification grades a finished profile, so it needs an existing, profiled
    run — and, to measure, a verification chart. Returns a ``BLOCK_*`` code."""
    if not target.is_verification():
        return None
    if target.is_new_run():
        return BLOCK_NEW_RUN
    run = resolve_run(project, target)
    if not run.built_profile_icc().exists():
        return BLOCK_NO_PROFILE
    if not run.has_verify_chart():
        return BLOCK_NO_CHART
    return None


# ---------------------------------------------------------------------------
# Verification dates: one formatter, used by the bar and by every message
# ---------------------------------------------------------------------------
def pretty_verification_date(vid: str) -> str:
    """``"2026-07-15_103000"`` → ``"2026-07-15 10:30"``.

    Falls back to the folder name unchanged for anything that isn't a stamp, so
    a hand-named folder still reads sensibly.
    """
    try:
        date, time = vid.split("_", 1)
        return f"{date} {time[:2]}:{time[2:4]}"
    except Exception:      # noqa: BLE001
        return vid


def chart_overwrite_message(vid: str) -> str:
    """Shown when a measurement is about to be started on a verification date
    whose stored chart is **not** the chart currently loaded (#130, Knut
    2026-07-26).

    Every verification date keeps a copy of the chart it was measured with, and
    that copy is what *Restore Used Chart* puts back. Measuring a different
    chart into the same date replaces it, so the older result would end up
    described by a chart nobody kept. This says so plainly, and offers the way
    out that keeps both: measure into a new date instead.
    """
    from core.i18n import tr
    return tr(
        "The verification from {when} was measured with a different chart than "
        "the one loaded now.\n\n"
        "That date keeps its own copy of the chart it was measured with — the "
        "copy “Restore Used Chart” puts back. If you measure the chart you have "
        "loaded into this same date, that stored copy is replaced, and the "
        "result already sitting there would no longer describe a chart you "
        "still have.\n\n"
        "Measuring into a new verification date keeps both: the earlier check "
        "stays exactly as it is, with its own chart, and today's reading starts "
        "a fresh dated entry beside it."
    ).format(when=pretty_verification_date(vid))


# ---------------------------------------------------------------------------
# "New run" guards for Print / Measure (#130, Knut 2026-07-25)
# ---------------------------------------------------------------------------
def new_run_guard_message(action: str) -> str:
    """The message shown when Print or Measure is started while **Profile run**
    is set to *New run* (*action* = ``"print"`` or ``"measure"``).

    Neither tab can act on a run that does not exist yet: there is no chart to
    print or measure until one has been made. Rather than failing obscurely, the
    message says which selection to change, and — because the usual reason for
    landing here is wanting a brand-new run — spells out every way to create one
    (Knut's wording, #130).
    """
    from core.i18n import tr
    lead = (tr("You can only print an already created chart. Select an existing "
               "“Profile run” option to print the chart for that run.")
            if action == "print" else
            tr("You can only measure an already created chart. Select an "
               "existing “Profile run” option to measure the chart for that run."))
    return lead + "\n\n" + tr(
        "If you intended to create a new profile run, this is best done in the "
        "Create Chart tab by setting “Profile run” = “New run” and “Run type” = "
        "“Profiling”, then\n"
        "    • choosing your chart settings and pressing “Generate Chart”, or\n"
        "    • loading a chart preset, or\n"
        "    • loading a .ti1 file.\n\n"
        "You may also create a new profile run by loading a .ti2 file in the "
        "Print Chart or Measure tab while “Profile run” is set to “New run” and "
        "“Run type” is set to “Profiling”.")

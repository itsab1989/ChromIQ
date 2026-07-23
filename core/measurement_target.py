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

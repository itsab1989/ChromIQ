"""Tools ▸ Measurement report opens on the measurement THIS SELECTION has.

Found by the combined adversary round of 2026-09-15 (B8-209). The Tools menu is
a second door into the Measurement Report window, with its own seeding rule,
and no adversary round had walked it.

**A CALIBRATION IS A THIRD TARGET, AND THE RULE KNEW ONLY TWO.**
`tools_dialogs._report_seed` read "for a verification target the newest measured
date; otherwise the run's own measurement", and a calibration fell into
"otherwise": `resolve_run` hands back a RUN for a target that is not one. So
with Run type = Calibration the tool opened on the PROFILE run's measurement.

Driven on screen on `Demo-Switching`, with the calibration preference set
before the window was built so the bar genuinely reached a calibration run
(`~/Desktop/ChromIQ-beta18-proof/combined-round-3/O-result.json`,
`O1-tools-door-calibration.png`): the window described
`runs/run2/Demo-Switching.ti3`, **240 patches**, while
`cal/Demo-Switching-cal.ti3` — **64 patches** — sat unread beside it, and
*Generate report* would have filed the calibration's report into
`runs/run2/reports/`.

Same shape as `MainWindow._current_chart_ti2`'s "A CALIBRATION IS A THIRD
TARGET, AND THIS KNEW ONLY ONE", and as beta.165's: two run types assumed where
there are three.

`docs/design/tool_availability.md` §4 gives this tool ● in S5 with the note
*"Reports on a measurement this selection has"*. That table is a DRAFT awaiting
Knut's confirmation, so what is fixed is only the part that needs no ruling:
one selection's report must not be filed into another selection's folder.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from core.measurement_target import (RUN_TYPE_CALIBRATION,        # noqa: E402
                                     RUN_TYPE_PROFILING,
                                     RUN_TYPE_VERIFICATION)


class _Parent:
    """What `_report_seed` reads off the main window, and nothing else."""

    def __init__(self, ctl):
        self._target_ctl = ctl


def _project_with_everything(tmp_path):
    """A project holding a profiling measurement, a dated verification and a
    measured calibration, so every branch has something to find and picking the
    wrong one is visible."""
    from tests.test_import_measurement_module import _cgats, _env, _PATCHES
    s, fm, ctl = _env(tmp_path)
    # CALIBRATION IS A PREFERENCE AND ITS DEFAULT IS OFF, so a controller that
    # is not told answers "profiling" for a bar asked for a calibration and
    # every assertion below would be about the wrong run type. Round 2 of these
    # adversary rounds recorded three probes that made exactly that mistake.
    s.set("calibration_mode", True)
    ctl.set_calibration_allowed(True)
    proj = fm.project()
    run = proj.run("run1") if proj.has_run("run1") else proj.current_run()
    run.ensure_dir()
    run.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(
        _cgats("CTI3", _PATCHES[:6]), encoding="utf-8")
    cal = proj.calibration
    cal.ensure_dir()
    cal.ti3.write_text(_cgats("CTI3", _PATCHES[:4]), encoding="utf-8")
    ctl.set_profile_run(run.dir.name)
    return s, fm, ctl, proj, run, v, cal


def _seed(ctl, proj):
    from ui.dialogs.tools_dialogs import _report_seed
    return _report_seed(_Parent(ctl), proj)


# ---------------------------------------------------------------------------

def test_a_calibration_seeds_its_own_measurement(qapp, tmp_path):
    """THE FAULT: standing on Calibration, the tool opened on the profile run.

    MUTATION: remove the calibration branch from `_report_seed` and this goes
    red, naming the run's measurement.
    """
    _s, _fm, ctl, proj, run, _v, cal = _project_with_everything(tmp_path)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    assert ctl.target.is_calibration(), (
        "the control failed: the bar did not reach a calibration run, so this "
        "test is about a different run type")
    got = _seed(ctl, proj)
    assert got == cal.ti3, (
        "Tools ▸ Measurement report opened on %s; the calibration's own "
        "measurement is %s" % (got, cal.ti3))
    assert got != run.measurement_ti3


def test_a_calibration_with_nothing_measured_borrows_no_run(qapp, tmp_path):
    """None is the answer, not another selection's measurement. A report filed
    from here would go into that other selection's folder.

    MUTATION: make the calibration branch fall through when the file is
    missing and this goes red, naming the run's measurement.
    """
    _s, _fm, ctl, proj, run, _v, cal = _project_with_everything(tmp_path)
    cal.ti3.unlink()
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    assert ctl.target.is_calibration()
    assert _seed(ctl, proj) is None, (
        "a calibration with nothing measured was given %s" % _seed(ctl, proj))


def test_the_calibration_branch_is_not_swallowed_by_the_guard(qapp, tmp_path):
    """The seeding is wrapped in `except Exception`, so a branch that raises
    answers None and looks exactly like "nothing measured yet". The first cut
    of this fix asked the Calibration for `measurement_ti3` — a Run's spelling,
    which a Calibration does not have — and was inert for that reason. So the
    file it names is asserted to EXIST as well as to be returned.

    MUTATION: spell it `project.calibration.measurement_ti3` again and this
    goes red.
    """
    _s, _fm, ctl, proj, _run, _v, cal = _project_with_everything(tmp_path)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    got = _seed(ctl, proj)
    assert got is not None and got.exists() and got == cal.ti3


def test_a_profiling_run_still_seeds_its_own_measurement(qapp, tmp_path):
    """The behaviour this must not eat."""
    _s, _fm, ctl, proj, run, _v, _cal = _project_with_everything(tmp_path)
    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert _seed(ctl, proj) == run.measurement_ti3


def test_a_verification_still_seeds_its_newest_date(qapp, tmp_path):
    """…and the other one."""
    _s, _fm, ctl, proj, _run, v, _cal = _project_with_everything(tmp_path)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert _seed(ctl, proj) == v.measurement_ti3


# ---------------------------------------------------------------------------
# R24-F5 — "New run" is not a run, and the tool opened on somebody else's
# ---------------------------------------------------------------------------
def test_new_run_seeds_nothing_rather_than_the_manifests_current_run(qapp,
                                                                     tmp_path):
    """R24-F5. With the bar on "Profile run: New run", Tools ▸ Measurement
    report opened on `runs/run2`.

    `resolve_run(project, target)` with ``create=False`` falls through to
    `project.current_run()` for a target that has created nothing, so the
    window opened on the manifest's current run, labelled itself *"Judged
    against (run2):"* while the bar said *"New run"*, kept Generate live, and
    rewrote `runs/run2/meta.json` when the "Judged against" pulldown moved --
    re-binding the limit set of a run the user was not looking at.

    Whether the tool should refuse to OPEN in this state is
    `tool_availability.md` §4's ✕, and that document is a DRAFT awaiting
    Knut's confirmation, so it is not decided here. This is the half that
    needs no ruling and that `_report_seed`'s own docstring already states:
    one selection's report must not be filed into another selection's folder.

    MUTATION, proved to land: drop the `is_new_run()` branch from
    `_report_seed`.
    """
    _s, _fm, ctl, proj, run, _v, _cal = _project_with_everything(tmp_path)
    ctl.set_run_type(RUN_TYPE_PROFILING)
    ctl.set_profile_run("")                    # the bar reads "New run"
    assert ctl.target.is_new_run(), "the bar is not on “New run”"
    assert run.measurement_ti3.exists(), (
        "the current run has no measurement, so there is nothing for the tool "
        "to have borrowed and this would pass on the fault")

    assert _seed(ctl, proj) is None, (
        "the tool opened on a measurement belonging to another selection; "
        "its report, and its limit set, would be filed into that run")


def test_a_new_verification_seeds_nothing_either(qapp, tmp_path):
    """S4 has the same shape as S2: nothing has been created to report on."""
    _s, _fm, ctl, proj, _run, _v, _cal = _project_with_everything(tmp_path)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    ctl.set_profile_run("")
    assert _seed(ctl, proj) is None, (
        "a new verification borrowed another selection's measurement")


def test_a_calibration_is_not_caught_by_the_new_run_branch(qapp, tmp_path):
    """The control. A calibration's profile-run box means nothing -- there is
    one `cal/` per project -- so `is_new_run()` is True for it and the
    calibration must still find its own measurement.

    MUTATION: put the `is_new_run()` branch ABOVE the calibration branch and
    this goes red.
    """
    _s, _fm, ctl, proj, _run, _v, cal = _project_with_everything(tmp_path)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    ctl.set_profile_run("")
    assert ctl.target.is_new_run()
    assert _seed(ctl, proj) == cal.ti3, (
        "the calibration was caught by the New-run branch and lost its own "
        "measurement")

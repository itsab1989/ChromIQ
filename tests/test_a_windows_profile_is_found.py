"""A profile colprof wrote as ``.icm`` is the run's profile (forum report, #210).

ArgyllCMS appends its platform's ICC extension, and on Windows that is
``.icm``. `Run.profile_icc` asked for ``<stem>.icc`` only, so on Windows every
built profile was invisible to `built_profile_icc()` and its 23 callers. A
user on Windows 11 / ChromIQ 4.3.5 could not measure a verification at all:
Start Measurement answered "This run has no profile to verify yet" beside
``runs\\run8\\CP1500-576p-ChromIQ.icm``, and From Profile Gamut refused the run
the same way. Reproduced on screen with a real colprof on Windows before the
fix; copying the same file to ``.icc`` made the window go away.

The demo projects never showed it, because `make_demo_projects._build_icc`
renames ``.icm`` to ``.icc`` after colprof.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from core.file_manager import Project, Run, profile_file  # noqa: E402


def _touch(p: Path, mtime: float | None = None) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"icc")
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


def _run(tmp_path) -> Run:
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    return run


# ---- profile_file: the rule ------------------------------------------------
def test_neither_exists_gives_the_icc_name_so_writers_are_unchanged(tmp_path):
    icc, icm = tmp_path / "a.icc", tmp_path / "a.icm"
    assert profile_file(icc, icm) == icc


def test_only_the_icm_exists_gives_the_icm(tmp_path):
    icc, icm = tmp_path / "a.icc", _touch(tmp_path / "a.icm")
    assert profile_file(icc, icm) == icm


def test_only_the_icc_exists_gives_the_icc(tmp_path):
    icc, icm = _touch(tmp_path / "a.icc"), tmp_path / "a.icm"
    assert profile_file(icc, icm) == icc


def test_when_both_exist_the_newer_one_is_the_profile(tmp_path):
    """A profile renamed to .icc by hand, then rebuilt as .icm, must not keep
    answering for the run with the old one."""
    now = time.time()
    icc = _touch(tmp_path / "a.icc", now - 600)
    icm = _touch(tmp_path / "a.icm", now)
    assert profile_file(icc, icm) == icm
    os.utime(icc, (now + 600, now + 600))
    assert profile_file(icc, icm) == icc


def test_the_same_age_keeps_the_icc(tmp_path):
    now = time.time()
    icc = _touch(tmp_path / "a.icc", now)
    icm = _touch(tmp_path / "a.icm", now)
    assert profile_file(icc, icm) == icc


# ---- Run ---------------------------------------------------------------------
def test_a_run_built_on_windows_has_its_profile(tmp_path):
    run = _run(tmp_path)
    assert not run.built_profile_icc().exists()
    icm = _touch(run.dir / f"{run.stem}.icm")
    assert run.profile_icc == icm
    assert run.built_profile_icc() == icm
    assert run.built_profile_icc().exists()


def test_a_merged_profile_built_on_windows_is_the_deliverable(tmp_path):
    run = _run(tmp_path)
    _touch(run.dir / f"{run.stem}.icm")
    merged = _touch(run.dir / "merged.icm")
    assert run.merged_icc == merged
    assert run.built_profile_icc() == merged


def test_a_run_without_a_profile_still_names_the_icc(tmp_path):
    run = _run(tmp_path)
    assert run.profile_icc == run.dir / f"{run.stem}.icc"
    assert run.merged_icc == run.dir / "merged.icc"


def test_a_refinement_seeds_from_a_windows_profile(tmp_path):
    """`Project.new_run(preconditioning_from=...)` raised "has no profile.icc"
    for a parent whose profile is an .icm."""
    proj = Project.create(tmp_path / "P", "P")
    parent = proj.current_run()
    parent.ensure_dir()
    _touch(parent.dir / f"{parent.stem}.icm")
    parent.measurement_ti3.write_text("CTI3\n", encoding="utf-8")
    child = proj.new_run(preconditioning_from=parent)
    assert child.preconditioning_icc.is_file()


def test_a_merged_profile_follows_the_same_newer_wins_rule(tmp_path):
    run = _run(tmp_path)
    now = time.time()
    _touch(run.dir / "merged.icc", now - 600)
    merged = _touch(run.dir / "merged.icm", now)
    assert run.merged_icc == merged


def test_a_replace_archives_a_windows_profile_once(tmp_path):
    """`profile_icc` IS the `.icm` here, and `archive_run_for_replace` also
    lists `.icm` by name: the same file must be moved once, not twice."""
    from workflow.chart_import import archive_run_for_replace
    run = _run(tmp_path)
    run.chart_ti2.write_text("CTI2\n", encoding="utf-8")
    _touch(run.dir / f"{run.stem}.icm")
    archive = archive_run_for_replace(run, verification=False)
    assert archive is not None
    assert not (run.dir / f"{run.stem}.icm").exists()
    assert [p.name for p in archive.rglob("*.icm")] == [f"{run.stem}.icm"]


# ---- the profile a rebuild archives -----------------------------------------
class _StubRunner:
    is_running = False


def test_a_rebuild_finds_the_profile_the_run_shows(tmp_path):
    """`ProfileBuilder.expected_icc_path` names the profile a rebuild
    archives before colprof overwrites it. It preferred .icc while the run
    preferred the newer .icm, so a rebuild archived a stale .icc and let
    colprof overwrite the newer .icm without a copy."""
    from workflow.profile_builder import ProfileBuilder, ProfileParams
    run = _run(tmp_path)
    ti3 = run.dir / f"{run.stem}.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    now = time.time()
    _touch(run.dir / f"{run.stem}.icc", now - 600)
    newer = _touch(run.dir / f"{run.stem}.icm", now)
    got = ProfileBuilder(_StubRunner()).expected_icc_path(ProfileParams(ti3_path=ti3))
    assert got == newer == run.profile_icc


# ---- the window the forum user saw -------------------------------------------
@pytest.fixture(scope="module")
def _qapp():
    from PyQt6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


class _Settings:
    def __init__(self):
        self._d = {"appearance": "dark"}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


def test_verification_is_not_refused_for_an_icm_profile(tmp_path, _qapp):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_measure import TabMeasure
    from workflow import measurement_messages as M

    s = _Settings()
    tab = TabMeasure(ArgyllRunner(s), s)
    run = _run(tmp_path)
    run.chart_ti2.write_text("x", encoding="utf-8")
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text("vc", encoding="utf-8")
    tab._ti1_path = run.verify_chart_ti2
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1")
    tab.set_target_controller(ctl)
    ctl.set_run_type("verification")

    assert tab._verification_guard() is M.M_VERIFY_NO_PROFILE
    _touch(run.dir / f"{run.stem}.icm")
    assert tab._verification_guard() is None

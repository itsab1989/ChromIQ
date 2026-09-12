"""The Print Chart tab's "no profile in this run" notice, when the profile the
user is being told to build already exists in another run.

A user reported "Through the profile" greyed out and could not work out why.
ChromIQ keeps a verification inside the profiling run it judges, so the option
asks whether THIS run holds a profile, not whether the project does. Her project
did hold one, in a different run. The notice she was shown told her to set Run
type to Profiling, create, print and measure a chart and build a profile: an
instruction to redo, from the beginning, work she had already finished.

The notice now names the run that has one, and only when one does. The wording
for a project with no profile anywhere is unchanged, because that instruction is
correct there.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import RUN_TYPE_VERIFICATION  # noqa: E402
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import (                   # noqa: E402
    MeasurementTargetBar, MeasurementTargetController)
from ui.tabs import tab_print as TP                       # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _project(tmp_path, *, runs: int, profiles_in: tuple[str, ...],
             selected: str):
    """A verification-ready project of ``runs`` runs, with a built profile in
    each id named by ``profiles_in``, and the bar pointing at ``selected``."""
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    s.set("use_native_print_dialog", False)
    fm = FileManager(s)
    project = Project.create(tmp_path / "P", "P")
    project.current_run().ensure_dir()
    for _ in range(runs - 1):
        project.new_run()
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)

    for rid in profiles_in:
        project.run(rid).profile_icc.write_bytes(b"icc")

    run = project.run(selected)
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    ti2 = run.verify_chart_ti2
    ti2.write_text("CTI2\n", encoding="utf-8")
    page = run.verifications_dir / f"{run.verify_stem}_01.tif"
    page.write_bytes(b"II*\x00")

    ctl.set_profile_run(selected)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    return s, ctl, ti2, [page]


def _tab(s, ctl, ti2, pages):
    tab = TP.TabPrint(s)
    tab.set_target_controller(ctl)
    tab._current_ti2 = ti2
    tab.load_tiffs(list(pages))
    tab._update_colour_row_visible()
    return tab


def _notice(tmp_path, **kw):
    s, ctl, ti2, pages = _project(tmp_path, **kw)
    tab = _tab(s, ctl, ti2, pages)
    try:
        assert not tab._cm_through_rb.isEnabled(), (
            "the premise of every test here is that the option is greyed")
        return tab._cm_notice.text()
    finally:
        tab.deleteLater()


# --- the fault, and the two shapes of it -----------------------------------

def test_a_profile_in_another_run_is_named_rather_than_asked_for(tmp_path,
                                                                 qapp):
    text = _notice(tmp_path, runs=2, profiles_in=("run1",), selected="run2")
    assert MeasurementTargetBar._pretty_run("run1") in text
    # The instruction that was wrong for her: she is not sent back to build a
    # profile, she is sent to the dropdown.
    assert "Profile run" in text
    assert "Build Profile" not in text


def test_two_other_runs_with_profiles_are_both_named(tmp_path, qapp):
    text = _notice(tmp_path, runs=3, profiles_in=("run1", "run2"),
                   selected="run3")
    assert MeasurementTargetBar._pretty_run("run1") in text
    assert MeasurementTargetBar._pretty_run("run2") in text
    assert "Build Profile" not in text


def test_the_helper_leaves_out_the_run_it_was_asked_about(tmp_path, qapp):
    """`_profiles_in_other_runs` answers "OTHER runs", and is asked it by a
    caller that has just found the selected run has none.

    THIS IS ASSERTED ON THE HELPER, NOT THROUGH THE NOTICE, and deliberately.
    Through the notice the exclusion cannot fail: the branch that reaches it
    runs only when the selected run has no profile, so that run is absent from
    the list whether it is excluded or not. A test driven through the notice
    passes with the exclusion deleted, which is a test that guards nothing. The
    helper is documented as answering a narrower question than the notice needs,
    and this pins that question where it can actually be got wrong.
    """
    s, ctl, ti2, pages = _project(tmp_path, runs=2, profiles_in=("run1",
                                                                 "run2"),
                                  selected="run2")
    tab = _tab(s, ctl, ti2, pages)
    project = ctl.project_or_none()
    try:
        assert tab._profiles_in_other_runs(project.run("run1")) == ["run2"]
        assert tab._profiles_in_other_runs(project.run("run2")) == ["run1"]
    finally:
        tab.deleteLater()


def test_a_project_with_no_profile_anywhere_keeps_the_old_words(tmp_path,
                                                                qapp):
    text = _notice(tmp_path, runs=2, profiles_in=(), selected="run2")
    assert "Build Profile" in text, (
        "with nothing built anywhere, 'go and build one' is the right answer")
    assert MeasurementTargetBar._pretty_run("run1") not in text


# --- the singular / plural split, which is a rule, not a preference ---------

def test_neither_string_contains_a_bracketed_plural():
    for src in (TP._CM_NOTICE_PROFILE_IN_ONE_OTHER_RUN,
                TP._CM_NOTICE_PROFILE_IN_OTHER_RUNS):
        assert "(s)" not in src


def test_the_two_strings_are_separate_keys():
    assert (TP._CM_NOTICE_PROFILE_IN_ONE_OTHER_RUN
            != TP._CM_NOTICE_PROFILE_IN_OTHER_RUNS)


# --- the question must never raise ------------------------------------------

def test_no_controller_falls_back_to_the_old_notice(tmp_path, qapp):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    tab = TP.TabPrint(s)
    try:
        assert tab._profiles_in_other_runs(None) == []
        assert "Build Profile" in tab._no_profile_notice(None)
    finally:
        tab.deleteLater()


def test_a_project_that_raises_is_answered_with_none_known(tmp_path, qapp,
                                                           monkeypatch):
    s, ctl, ti2, pages = _project(tmp_path, runs=2, profiles_in=("run1",),
                                  selected="run2")
    tab = _tab(s, ctl, ti2, pages)
    try:
        monkeypatch.setattr(type(ctl), "project_or_none",
                            lambda self: (_ for _ in ()).throw(RuntimeError))
        assert tab._profiles_in_other_runs(None) == []
        assert "Build Profile" in tab._no_profile_notice(None)
    finally:
        tab.deleteLater()


# --- a run whose deliverable is merged.icc counts too ------------------------

def test_a_run_whose_profile_is_a_merge_counts(tmp_path, qapp):
    """`built_profile_icc` is merged.icc when a pre-conditioning merge produced
    one, and that run holds a profile the user can verify against."""
    s, ctl, ti2, pages = _project(tmp_path, runs=2, profiles_in=(),
                                  selected="run2")
    project = ctl.project_or_none()
    (project.run("run1").merged_icc).write_bytes(b"icc")
    tab = _tab(s, ctl, ti2, pages)
    try:
        assert tab._profiles_in_other_runs(project.run("run2")) == ["run1"]
    finally:
        tab.deleteLater()

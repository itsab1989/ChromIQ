"""A project that fails to load must not look like no project at all.

`MeasurementTargetController.project_or_none` swallows every exception, and it
is right to — the bar asks this on every refresh and must never take a tab down.
But swallowing it *silently* makes a broken project indistinguishable from an
unopened one: every control on the bar goes inert and "Restore Used Chart"
reports "open or create a printer profile project first". A malformed
`project.json` cost real debugging time for exactly that reason.
"""
import json

import pytest

from core.file_manager import FileManager
from core.settings import AppSettings
from ui.measurement_target_bar import MeasurementTargetController


@pytest.fixture
def broken_project(qapp, tmp_path):
    settings = AppSettings()
    settings.set("custom_output_path", str(tmp_path / "out"))
    fm = FileManager(settings)
    root = fm.root_dir()
    root.mkdir(parents=True, exist_ok=True)
    proj_dir = root / "Broken-Demo"
    proj_dir.mkdir(parents=True, exist_ok=True)
    # A manifest the loader will choke on: run entries as dicts, not ids.
    (proj_dir / "project.json").write_text(json.dumps({
        "schema_version": 2, "target_name": "Broken-Demo",
        "current_run": "run1", "runs": [{"id": "run1"}]}), encoding="utf-8")
    fm.set_target_name("Broken-Demo")
    return MeasurementTargetController(fm)


def test_it_still_returns_none_rather_than_raising(broken_project):
    """The swallow itself is correct and must stay."""
    assert broken_project.project_or_none() is None


def test_it_says_why_in_the_log(broken_project, caplog):
    import logging
    with caplog.at_level(logging.WARNING):
        assert broken_project.project_or_none() is None
    assert any("could not load the project" in r.message for r in caplog.records), (
        "the bar went inert without a word about why"
    )


def test_it_does_not_repeat_itself_on_every_refresh(broken_project, caplog):
    """This runs on every refresh; an unconditional line would drown the log."""
    import logging
    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            broken_project.project_or_none()
    said = [r for r in caplog.records if "could not load the project" in r.message]
    assert len(said) == 1, f"logged {len(said)} times for one broken project"


def test_a_healthy_project_says_nothing(qapp, caplog, tmp_path):
    import logging

    from core.file_manager import Project

    settings = AppSettings()
    settings.set("custom_output_path", str(tmp_path / "out"))
    fm = FileManager(settings)
    root = fm.root_dir()
    root.mkdir(parents=True, exist_ok=True)
    Project.create(root / "Good-Demo", "Good-Demo")
    fm.set_target_name("Good-Demo")
    ctl = MeasurementTargetController(fm)
    with caplog.at_level(logging.WARNING):
        assert ctl.project_or_none() is not None
    assert not [r for r in caplog.records if "could not load" in r.message]

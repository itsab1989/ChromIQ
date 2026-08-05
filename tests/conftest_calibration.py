"""Shared fixtures for the #137 calibration-run-type tests.

Every one of these builds a project in a TEMPORARY folder. That matters more
than it looks: FileManager resolves projects under ``custom_output_path`` or, if
that is unset, under the user's real ``~/ChromIQ`` — so a test that forgets it
writes into the user's own projects.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from core.settings import DEFAULTS


class CalSettings:
    """A settings double that keeps every project inside *tmp*."""

    def __init__(self, tmp: Path, **over):
        self.d = dict(DEFAULTS)
        self.d["custom_output_path"] = str(tmp)
        self.d.update(over)

    def get(self, key, default=None):
        return self.d.get(key, default)

    def set(self, key, value):
        self.d[key] = value


@pytest.fixture
def cal_home(tmp_path) -> Path:
    return tmp_path


@pytest.fixture
def cal_settings(cal_home):
    return CalSettings(cal_home, calibration_mode=True)


@pytest.fixture
def cal_project(cal_settings):
    """A file manager with one empty project, and its Project."""
    from core.file_manager import FileManager

    fm = FileManager(cal_settings)
    fm.set_target_name("Test-Printer")
    return fm, fm.project()

"""Beta 17, settings schema 29: the misread tests' old settings carried into
one value per chart type (#182, Knut 6082015002, 6084176226, 6085694445,
6070058549).

Rule of beta 16: each step runs only for settings stored before it, and a
value the user chose is kept where it corresponds; a stored default is only
an echo (Preferences ▸ OK writes every key).
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings   # noqa: E402

from core.settings import AppSettings, SETTINGS_SCHEMA   # noqa: E402
from workflow import misread_settings as MS   # noqa: E402


def _settings(tmp_path: Path, schema: int = 28, **stored) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s._qs.setValue("settings_schema", schema)
    for k, v in stored.items():
        s._qs.setValue(k, v)
    return s


def _all(s):
    return {
        "limit": [MS.patch_error_limit(s, k) for k in MS.KINDS],
        "strip": [MS.strip_test_on(s, k) for k in MS.KINDS],
        "nl": [MS.neighbour_limit(s, k) for k in MS.KINDS],
        "nr": [MS.neighbour_radius(s, k) for k in MS.KINDS],
        "srt": MS.same_reading_tolerance(s),
    }


DEFAULT = {"limit": [95, 20, 5, 95], "strip": [True, True, False, True],
           "nl": [10, 5, 3, 10], "nr": [15, 30, 30, 30], "srt": 3.0}


def test_the_schema_moved():
    assert SETTINGS_SCHEMA >= 29


def test_nothing_stored_gives_the_designed_table(tmp_path):
    s = _settings(tmp_path)
    s.migrate()
    assert _all(s) == DEFAULT


def test_stored_echoes_of_the_old_defaults_give_the_designed_table(tmp_path):
    """What Preferences ▸ OK wrote with nothing changed, in beta 16."""
    s = _settings(tmp_path, patch_read_warn_de_estimated=95.0,
                  patch_read_warn_de_accurate=20.0,
                  patch_read_warn_de_prediction=10.0,
                  patch_warn_outlier_fence="true",
                  patch_neighbour_buffer_de=10.0,
                  patch_neighbour_buffer_de_accurate=5.0,
                  patch_neighbour_check="true")
    s.migrate()
    assert _all(s) == DEFAULT
    for old in ("patch_warn_outlier_fence", "patch_neighbour_buffer_de",
                "patch_neighbour_buffer_de_accurate"):
        assert s._qs.value(old, None) is None, old


def test_a_users_own_values_are_kept_where_they_correspond(tmp_path):
    s = _settings(tmp_path, patch_read_warn_de_estimated=60.0,
                  patch_read_warn_de_accurate=25.0,
                  patch_read_warn_de_prediction=7.0,
                  patch_warn_outlier_fence="false",
                  patch_neighbour_buffer_de=14.0,
                  patch_neighbour_buffer_de_accurate=6.0)
    dropped = s.migrate()
    got = _all(s)
    # the limits: their own keys; calibration charts used the estimated one
    assert got["limit"] == [60, 25, 7, 60]
    # the strip test off stays off where it ruled; verification: its default
    assert got["strip"] == [False, False, False, False]
    # the "buffers" become the neighbour limits of the same chart types
    assert got["nl"] == [14, 6, 3, 10]
    assert got["nr"] == [15, 30, 30, 30] and got["srt"] == 3.0
    assert any("patch_neighbour_buffer_de" in d for d in dropped)


def test_a_value_already_in_a_new_key_is_never_overwritten(tmp_path):
    s = _settings(tmp_path, patch_neighbour_buffer_de=14.0,
                  patch_neighbour_limit_estimated=8.0,
                  patch_warn_outlier_fence="false",
                  patch_strip_test_accurate="true",
                  patch_read_warn_de_estimated=60.0,
                  patch_read_warn_de_calibration=90.0)
    s.migrate()
    got = _all(s)
    assert got["nl"][0] == 8.0
    assert got["strip"][:2] == [False, True]
    assert got["limit"][3] == 90.0


def test_it_runs_only_for_settings_older_than_it(tmp_path):
    """At schema 29 a stored 10 for verification charts is the user's."""
    s = _settings(tmp_path, schema=29, patch_read_warn_de_prediction=10.0,
                  patch_read_warn_de_estimated=60.0)
    s.migrate()
    assert MS.patch_error_limit(s, "verification") == 10.0
    assert MS.patch_error_limit(s, "calibration") == 95.0


def test_strings_from_an_ini_file_are_read(tmp_path):
    s = _settings(tmp_path, patch_neighbour_buffer_de="12,5",
                  patch_warn_outlier_fence="False")
    s.migrate()
    assert MS.neighbour_limit(s, "estimated") == 12.5
    assert MS.strip_test_on(s, "calibration") is False

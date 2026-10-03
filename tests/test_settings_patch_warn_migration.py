"""The patch-read limit's migrations.

schema 9 (#49): the old default 20 moved to 50; a stored echo of 20 is dropped.

schema 25 (#182, Sebastian 5956560815 approving proposal A, Knut 5956552085):
the single "patch_read_warn_de" became two limits, one for charts whose expected
colours are estimated (default 95) and one for charts made from a profile
(ACCURATE_EXPECTED_VALUES, default 30). A user who had moved the old limit away
from its default 50 keeps that number as the ESTIMATED-chart limit; otherwise
both new defaults apply. The old schema-8 rule that reset anything above 50 is
retired: with a default of 95 a raised value is a choice.
"""
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings   # noqa: E402
from core.settings import AppSettings, DEFAULTS, SETTINGS_SCHEMA   # noqa: E402


def _settings(tmp_path: Path, value, schema: int = 24) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s._qs.setValue("settings_schema", schema)
    if value is not None:
        s._qs.setValue("patch_read_warn_de", value)
    return s


def _limits(s: AppSettings) -> "tuple[float, float]":
    return (float(s.get("patch_read_warn_de_estimated")),
            float(s.get("patch_read_warn_de_accurate")))


def test_the_defaults_are_argyllcms_own_thresholds():
    assert DEFAULTS["patch_read_warn_de_estimated"] == 95.0     # WERR_TH
    assert DEFAULTS["patch_read_warn_de_accurate"] == 30.0      # ACC_WERR_TH
    assert "patch_read_warn_de" not in DEFAULTS
    assert SETTINGS_SCHEMA >= 25


def test_a_changed_old_limit_becomes_the_estimated_limit(tmp_path):
    s = _settings(tmp_path, 40.0)
    dropped = s.migrate()
    assert _limits(s) == (40.0, 30.0)
    assert s._qs.value("patch_read_warn_de", None) is None
    assert any("patch_read_warn_de" in d for d in dropped)


def test_a_raised_old_limit_is_kept_too(tmp_path):
    # Before schema 25 the floor migration would have thrown 70 away.
    s = _settings(tmp_path, 70.0)
    s.migrate()
    assert _limits(s) == (70.0, 30.0)


def test_the_old_default_gives_both_new_defaults(tmp_path):
    # Settings ▸ Save writes every key, so a stored 50 is simply the default.
    s = _settings(tmp_path, 50.0)
    s.migrate()
    assert _limits(s) == (95.0, 30.0)
    assert s._qs.value("patch_read_warn_de", None) is None
    assert s._qs.value("patch_read_warn_de_estimated", None) is None


def test_an_echo_of_the_older_default_20_gives_the_new_defaults(tmp_path):
    s = _settings(tmp_path, 20.0, schema=7)
    s.migrate()
    assert _limits(s) == (95.0, 30.0)


def test_a_lowered_value_from_an_old_schema_is_kept(tmp_path):
    s = _settings(tmp_path, 10.0, schema=7)
    s.migrate()
    assert _limits(s) == (10.0, 30.0)


def test_nothing_stored_gives_the_new_defaults(tmp_path):
    s = _settings(tmp_path, None)
    assert s.migrate() is not None
    assert _limits(s) == (95.0, 30.0)


def test_it_runs_once(tmp_path):
    s = _settings(tmp_path, 40.0)
    s.migrate()
    s._qs.setValue("patch_read_warn_de_estimated", 60.0)   # the user moves on
    s.migrate()
    assert _limits(s) == (60.0, 30.0)

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


def test_the_defaults():
    assert DEFAULTS["patch_read_warn_de_estimated"] == 95.0     # WERR_TH
    # Beta 11 (Knut #182 5983470377): 20, no longer ACC_WERR_TH's 30, and a
    # third limit for a verification judged against its profile.
    assert DEFAULTS["patch_read_warn_de_accurate"] == 20.0
    # Beta 17 (Knut 6070058549): the verification limit is 5, and calibration
    # charts have their own limit.
    assert DEFAULTS["patch_read_warn_de_prediction"] == 5.0
    assert DEFAULTS["patch_read_warn_de_calibration"] == 95.0
    assert "patch_read_warn_de" not in DEFAULTS
    assert SETTINGS_SCHEMA >= 29


def test_a_changed_old_limit_becomes_the_estimated_limit(tmp_path):
    s = _settings(tmp_path, 40.0)
    dropped = s.migrate()
    assert _limits(s) == (40.0, 20.0)
    assert s._qs.value("patch_read_warn_de", None) is None
    assert any("patch_read_warn_de" in d for d in dropped)


def test_a_raised_old_limit_is_kept_too(tmp_path):
    # Before schema 25 the floor migration would have thrown 70 away.
    s = _settings(tmp_path, 70.0)
    s.migrate()
    assert _limits(s) == (70.0, 20.0)


def test_the_old_default_gives_both_new_defaults(tmp_path):
    # Settings ▸ Save writes every key, so a stored 50 is simply the default.
    s = _settings(tmp_path, 50.0)
    s.migrate()
    assert _limits(s) == (95.0, 20.0)
    assert s._qs.value("patch_read_warn_de", None) is None
    assert s._qs.value("patch_read_warn_de_estimated", None) is None


def test_an_echo_of_the_older_default_20_gives_the_new_defaults(tmp_path):
    s = _settings(tmp_path, 20.0, schema=7)
    s.migrate()
    assert _limits(s) == (95.0, 20.0)


def test_a_lowered_value_from_an_old_schema_is_kept(tmp_path):
    s = _settings(tmp_path, 10.0, schema=7)
    s.migrate()
    assert _limits(s) == (10.0, 20.0)


def test_nothing_stored_gives_the_new_defaults(tmp_path):
    s = _settings(tmp_path, None)
    assert s.migrate() is not None
    assert _limits(s) == (95.0, 20.0)


def test_it_runs_once(tmp_path):
    s = _settings(tmp_path, 40.0)
    s.migrate()
    s._qs.setValue("patch_read_warn_de_estimated", 60.0)   # the user moves on
    s.migrate()
    assert _limits(s) == (60.0, 20.0)


# ---- schema 26 (beta 11, Knut #182 5983470377) ----------------------------
def _settings26(tmp_path: Path, **stored) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s26.ini"), QSettings.Format.IniFormat)
    s._qs.setValue("settings_schema", 25)
    for k, v in stored.items():
        s._qs.setValue(k, v)
    return s


def test_a_stored_echo_of_30_becomes_20(tmp_path):
    # Preferences ▸ Save writes every key: a stored 30 is the old default.
    s = _settings26(tmp_path, patch_read_warn_de_accurate=30.0)
    s.migrate()
    assert float(s.get("patch_read_warn_de_accurate")) == 20.0
    assert s._qs.value("patch_read_warn_de_accurate", None) is None


@pytest.mark.parametrize("own", [12.0, 25.0, 40.0])
def test_a_limit_the_user_chose_is_kept(tmp_path, own):
    s = _settings26(tmp_path, patch_read_warn_de_accurate=own)
    s.migrate()
    assert float(s.get("patch_read_warn_de_accurate")) == own


def test_the_verification_limit_is_new_and_takes_nobodys_old_value(tmp_path):
    s = _settings26(tmp_path, patch_read_warn_de_accurate=12.0,
                    patch_read_warn_de_estimated=60.0)
    s.migrate()
    assert float(s.get("patch_read_warn_de_prediction")) == 5.0   # beta 17
    assert s._qs.value("patch_read_warn_de_prediction", None) is None

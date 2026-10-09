"""Beta 15 follow-up: the neighbour check's buffer migration (schema 27).

k43 (Knut #182 6059912998, answer 6) split the one neighbour buffer in two:
"patch_neighbour_buffer_de" for charts with estimated colours (default 10) and
"patch_neighbour_buffer_de_accurate" for charts made with a pre-conditioning
profile (default 5). Until then the ONE buffer applied to both kinds of chart.

A user who had left it at 10 gets the designed pair 10/5. A user who had set
their own number keeps it for BOTH, so nobody's checking of pre-conditioning-
profile charts silently becomes stricter (found in the beta 15 review B: a
user who had raised it to 15 got 5).

Beta 17 (schema 29) carries the pair on into the Neighbour limit of the same
two chart types and removes the old keys, so the end of the chain is checked
in the new keys (``workflow/misread_settings.py``)."""
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings   # noqa: E402
from core.settings import AppSettings, DEFAULTS, SETTINGS_SCHEMA   # noqa: E402

KEY = "patch_neighbour_buffer_de"
ACC = "patch_neighbour_buffer_de_accurate"
NEW_KEY = "patch_neighbour_limit_estimated"
NEW_ACC = "patch_neighbour_limit_accurate"


def _settings(tmp_path: Path, value=None, accurate=None,
              schema: int = 26) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s._qs.setValue("settings_schema", schema)
    if value is not None:
        s._qs.setValue(KEY, value)
    if accurate is not None:
        s._qs.setValue(ACC, accurate)
    return s


def _pair(s: AppSettings) -> "tuple[float, float]":
    assert s._qs.value(KEY, None) is None and s._qs.value(ACC, None) is None
    return float(s.get(NEW_KEY)), float(s.get(NEW_ACC))


def test_the_designed_defaults():
    assert DEFAULTS[NEW_KEY] == 10.0 and DEFAULTS[NEW_ACC] == 5.0
    assert KEY not in DEFAULTS and ACC not in DEFAULTS
    assert SETTINGS_SCHEMA >= 29


def test_nothing_stored_gives_the_designed_pair(tmp_path):
    s = _settings(tmp_path)
    s.migrate()
    assert _pair(s) == (10.0, 5.0)


def test_a_stored_default_gives_the_designed_pair(tmp_path):
    # Save in Preferences writes every key, so a stored 10 is an echo.
    s = _settings(tmp_path, 10.0)
    s.migrate()
    assert _pair(s) == (10.0, 5.0)


@pytest.mark.parametrize("own", [15.0, 7.0, 3.5])
def test_a_changed_buffer_is_carried_to_both(tmp_path, own):
    s = _settings(tmp_path, own)
    dropped = s.migrate()
    assert _pair(s) == (own, own)
    assert any(KEY in d for d in dropped)


def test_a_value_already_in_the_new_key_is_never_overwritten(tmp_path):
    s = _settings(tmp_path, 15.0, accurate=6.0)
    s.migrate()
    assert _pair(s) == (15.0, 6.0)


def test_it_runs_once(tmp_path):
    # At schema 27 the user's later choice of the pair stands.
    s = _settings(tmp_path, 15.0, schema=27)
    s.migrate()
    assert _pair(s) == (15.0, 5.0)


def test_a_string_from_the_ini_is_read_as_a_number(tmp_path):
    s = _settings(tmp_path, "12")
    s.migrate()
    assert _pair(s) == (12.0, 12.0)

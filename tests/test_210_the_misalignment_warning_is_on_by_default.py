"""#210 (Basti, 4.3.5 beta 8): "Warn me if a strip looks misaligned" is ON by
default, and schema 30 moves users who carried the old OFF.

It is a Preferences setting, global by docs/design/per_target_settings.md §1.1
("Preferences → everything: your setup"), so no run, target or project stores
it and the migration is the only place an old value can live.

Why a stored OFF is dropped once: Preferences → OK writes every key, so OFF is
what anyone has who ever pressed OK, and until #210 the check could not fire
on a real print, so nobody had a reason to choose it off. From schema 30 on a
stored OFF is the user's choice and kept.
"""
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings   # noqa: E402
from core.settings import AppSettings, DEFAULTS, SETTINGS_SCHEMA   # noqa: E402


def _settings(tmp_path: Path, value, schema: int) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s._qs.setValue("settings_schema", schema)
    if value is not None:
        s._qs.setValue("misalign_safenet", value)
    return s


def test_the_default_is_on():
    assert DEFAULTS["misalign_safenet"] is True
    assert SETTINGS_SCHEMA >= 30


@pytest.mark.parametrize("old", [False, "false"])
def test_an_old_stored_off_becomes_on(tmp_path, old):
    s = _settings(tmp_path, old, 29)
    dropped = s.migrate()
    assert s.get("misalign_safenet") is True
    assert any("misalign_safenet" in d for d in dropped)


def test_an_old_stored_on_stays_on(tmp_path):
    s = _settings(tmp_path, True, 29)
    s.migrate()
    assert s.get("misalign_safenet") is True


def test_nothing_stored_is_on(tmp_path):
    s = _settings(tmp_path, None, 29)
    s.migrate()
    assert s.get("misalign_safenet") is True


def test_an_off_chosen_after_the_change_is_kept(tmp_path):
    s = _settings(tmp_path, False, 30)
    s.migrate()
    assert s.get("misalign_safenet") is False


def test_the_measure_tab_and_preferences_follow_the_default():
    """Both read sites take the default from DEFAULTS, not a literal False."""
    root = Path(__file__).resolve().parent.parent
    for rel in ("ui/tabs/tab_measure.py", "ui/dialogs/settings_dialog.py"):
        src = (root / rel).read_text(encoding="utf-8")
        assert 'get("misalign_safenet", False)' not in src, rel
        assert 'get("misalign_safenet")' in src, rel

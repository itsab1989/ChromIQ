"""A driver must not be able to damage the user's own preferences.

Scripts that drive ChromIQ on screen build a real `AppSettings`, which is the
real preferences store — so setting an output path, or merely resizing the
window, writes into the settings the person uses every day. It happened: one
run left `custom_output_path` pointing at a temp folder that was later swept,
and ChromIQ then looked for every project in a directory that did not exist and
found nothing. The symptom reached the owner as "the info line has stopped
appearing", which is nowhere near the cause.

Backing the file up first did not catch it. Three runs reported "no drift" by
comparing the file against a backup that already held the bad value.
"""
import os
import pathlib
import tempfile

import pytest

from core.settings import AppSettings, SETTINGS_FILE_ENV


@pytest.fixture()
def sandbox(monkeypatch):
    path = pathlib.Path(tempfile.mkdtemp()) / "sandbox.ini"
    monkeypatch.setenv(SETTINGS_FILE_ENV, str(path))
    return path


def _record_qsettings(monkeypatch):
    """Capture what `AppSettings` ASKS FOR.

    `tests/conftest.py` already replaces `core.settings.QSettings` so the suite
    never touches the real store, which means the resulting object's
    `fileName()` is the suite's sandbox whatever this code does — asserting on
    it would test conftest, not this feature. What matters is the arguments.
    """
    import core.settings as cs
    seen = []

    class _Fake:
        def __init__(self, *a, **k):
            seen.append(a)

        def value(self, *_a, **_k):
            return None

        def setValue(self, *_a, **_k):
            pass

        def sync(self):
            pass

        def fileName(self):
            return "fake"

    monkeypatch.setattr(cs, "QSettings", _Fake)
    return seen


def test_the_env_var_moves_the_whole_store(qapp, monkeypatch, sandbox):
    seen = _record_qsettings(monkeypatch)
    AppSettings()
    assert seen, "AppSettings built no settings store at all"
    assert seen[0][0] == str(sandbox), (
        f"the store was opened as {seen[0]!r}, not at the sandbox path — a "
        f"driver setting {SETTINGS_FILE_ENV} would still write to the user's "
        f"own preferences")


def test_without_the_env_var_the_real_store_is_used(qapp, monkeypatch):
    """Unset must change nothing: this may not alter the shipped app."""
    monkeypatch.delenv(SETTINGS_FILE_ENV, raising=False)
    seen = _record_qsettings(monkeypatch)
    AppSettings()
    assert seen[0] == ("ChromIQ", "ChromIQ"), (
        f"the real store is no longer the default: {seen[0]!r}")


def test_an_empty_env_var_is_not_a_sandbox(qapp, monkeypatch):
    """Unset and set-to-blank must mean the same thing, or a driver that
    exports it conditionally writes to the real store while believing it is
    sandboxed — which is exactly how this damage happened."""
    monkeypatch.setenv(SETTINGS_FILE_ENV, "   ")
    seen = _record_qsettings(monkeypatch)
    AppSettings()
    assert seen[0] == ("ChromIQ", "ChromIQ")

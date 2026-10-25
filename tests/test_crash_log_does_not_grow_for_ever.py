"""The crash log is moved aside once it is large, instead of growing for as
long as ChromIQ is installed (jctay, forum post 149834, 2026-10-25: 3,700
lines back to July, "Is there a way to clean up the log file?").
`core/crash_log.py` holds the reasons."""
from __future__ import annotations

from pathlib import Path

import pytest

from core import crash_log


class _FakeFH:
    def __init__(self):
        self.calls = []

    def enable(self, file=None, all_threads=True):
        self.calls.append(("enable", file, all_threads))

    def is_enabled(self):
        return True

    def disable(self):
        self.calls.append(("disable",))


@pytest.fixture
def armed(monkeypatch):
    monkeypatch.setattr(crash_log, "faulthandler", _FakeFH())
    monkeypatch.setattr(crash_log, "_file", None)
    opened = []
    yield opened
    f = crash_log._file
    if f is not None:
        f.close()


def test_a_small_file_is_appended_to_as_before(tmp_path, armed):
    log = tmp_path / crash_log.FILE_NAME
    log.write_text("=== an earlier session ===\n", encoding="utf-8")
    crash_log.arm(tmp_path, "9.9.9")
    crash_log._file.flush()
    text = log.read_text(encoding="utf-8")
    assert text.startswith("=== an earlier session ===")
    assert "ChromIQ 9.9.9" in text
    assert not (tmp_path / (crash_log.FILE_NAME + ".1")).exists()


def test_a_large_file_is_moved_aside_and_a_fresh_one_started(tmp_path, armed):
    log = tmp_path / crash_log.FILE_NAME
    big = "=== faulthandler armed 2026-07-06 12:23:37 ===\n" * (
        crash_log.MAX_BYTES // 40)
    log.write_text(big, encoding="utf-8")
    assert log.stat().st_size > crash_log.MAX_BYTES
    crash_log.arm(tmp_path, "9.9.9")
    crash_log._file.flush()
    old = tmp_path / (crash_log.FILE_NAME + ".1")
    assert old.read_text(encoding="utf-8") == big, "the old log was not kept"
    fresh = log.read_text(encoding="utf-8")
    assert "ChromIQ 9.9.9" in fresh
    assert len(fresh) < 200, "the new session did not start a fresh file"


def test_only_one_old_copy_is_kept(tmp_path):
    log = tmp_path / crash_log.FILE_NAME
    (tmp_path / (crash_log.FILE_NAME + ".1")).write_text("oldest\n", encoding="utf-8")
    log.write_text("x" * 50, encoding="utf-8")
    assert crash_log.rotate_if_large(log, max_bytes=10) is True
    assert (tmp_path / (crash_log.FILE_NAME + ".1")).read_text(
        encoding="utf-8") == "x" * 50
    assert not log.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        crash_log.FILE_NAME + ".1"]


def test_a_missing_or_unmovable_file_never_raises(tmp_path):
    assert crash_log.rotate_if_large(tmp_path / "nothing-here.log") is False

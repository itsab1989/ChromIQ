"""A read-only profile or measurement is still repaired on Windows.

`os.replace` over a file whose read-only attribute is set raises WinError 5 on
Windows, where macOS and Linux only ask for a writable folder. The first CI run
on Windows found the accent fix of a read-only profile and the calibration-table
repair of a read-only `.ti3` silently skipped there
(`test_icc_name_keeps_its_accents.py`, `test_cal_repair.py`).
`core.file_manager.replace_read_only_too` clears the attribute for the swap.
These tests play Windows' refusal on any host, so the gate on the Mac proves it.
"""
from __future__ import annotations

import os
import stat

import pytest

import core.file_manager as fm


def _windows_replace(real_replace):
    def _replace(src, dst):
        if os.path.exists(dst) and not os.stat(dst).st_mode & stat.S_IWUSR:
            raise PermissionError(13, "Access is denied", str(dst))
        return real_replace(src, dst)
    return _replace


@pytest.fixture
def as_windows(monkeypatch):
    monkeypatch.setattr(fm.os, "name", "nt")
    monkeypatch.setattr(fm.os, "replace", _windows_replace(os.replace))
    monkeypatch.setattr(fm.os, "access",
                        lambda p, m: bool(os.stat(p).st_mode & stat.S_IWUSR))


def test_a_read_only_target_is_replaced_and_stays_read_only(tmp_path, as_windows):
    dest, tmp = tmp_path / "p.icc", tmp_path / "p.icc.tmp"
    dest.write_bytes(b"OLD")
    tmp.write_bytes(b"NEW")
    os.chmod(dest, 0o444)
    os.chmod(tmp, 0o444)
    try:
        fm.replace_read_only_too(tmp, dest)
        assert dest.read_bytes() == b"NEW"
        assert not tmp.exists()
        assert stat.S_IMODE(dest.stat().st_mode) == 0o444
    finally:
        os.chmod(dest, 0o644)


def test_a_failed_swap_puts_the_read_only_bit_back(tmp_path, monkeypatch,
                                                    as_windows):
    dest, tmp = tmp_path / "p.icc", tmp_path / "p.icc.tmp"
    dest.write_bytes(b"OLD")
    tmp.write_bytes(b"NEW")
    os.chmod(dest, 0o444)

    def _boom(src, dst):
        raise OSError("disk gone")
    monkeypatch.setattr(fm.os, "replace", _boom)
    try:
        with pytest.raises(OSError):
            fm.replace_read_only_too(tmp, dest)
        assert dest.read_bytes() == b"OLD"
        assert stat.S_IMODE(dest.stat().st_mode) == 0o444
    finally:
        os.chmod(dest, 0o644)


def test_without_the_helper_windows_would_refuse(tmp_path, as_windows):
    """The simulation is faithful: a bare replace is refused, as on Windows."""
    dest, tmp = tmp_path / "p.icc", tmp_path / "p.icc.tmp"
    dest.write_bytes(b"OLD")
    tmp.write_bytes(b"NEW")
    os.chmod(dest, 0o444)
    try:
        with pytest.raises(PermissionError):
            fm.os.replace(tmp, dest)
    finally:
        os.chmod(dest, 0o644)

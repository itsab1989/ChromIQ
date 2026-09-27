"""Regression tests for core.platform_paths.

These pin the macOS and Windows return values to exactly what the
codebase produced before the refactor, so we can never silently
regress those platforms when adding Linux branches.

Linux is tested for the new XDG-respecting behavior.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest


@pytest.fixture
def fresh_module(monkeypatch):
    """Reload core.platform_paths under a patched sys.platform / env."""

    def _make(platform: str, env: dict | None = None):
        monkeypatch.setattr("sys.platform", platform)
        if env is not None:
            for k, v in env.items():
                if v is None:
                    monkeypatch.delenv(k, raising=False)
                else:
                    monkeypatch.setenv(k, v)
        import core.platform_paths as mod
        return importlib.reload(mod)

    return _make


# ---------------------------------------------------------------------------
# Platform predicates
# ---------------------------------------------------------------------------

def test_predicates_windows(fresh_module):
    pp = fresh_module("win32")
    assert pp.is_windows() and not pp.is_macos() and not pp.is_linux()


def test_predicates_macos(fresh_module):
    pp = fresh_module("darwin")
    assert pp.is_macos() and not pp.is_windows() and not pp.is_linux()


def test_predicates_linux(fresh_module):
    pp = fresh_module("linux")
    assert pp.is_linux() and not pp.is_windows() and not pp.is_macos()


# ---------------------------------------------------------------------------
# default_argyll_bin_dir
# ---------------------------------------------------------------------------

def test_default_argyll_dir_windows(fresh_module):
    pp = fresh_module("win32")
    assert pp.default_argyll_bin_dir() == r"C:\Program Files\ArgyllCMS\bin"


def test_default_argyll_dir_macos(fresh_module):
    pp = fresh_module("darwin")
    assert pp.default_argyll_bin_dir() == "/Applications/Argyll/bin"


def test_default_argyll_dir_linux(fresh_module):
    pp = fresh_module("linux")
    assert pp.default_argyll_bin_dir() == "/usr/bin"


# ---------------------------------------------------------------------------
# argyll_candidate_dirs
# ---------------------------------------------------------------------------

def test_argyll_candidates_macos_preserves_order(fresh_module):
    pp = fresh_module("darwin")
    dirs = pp.argyll_candidate_dirs()
    # The fixed-list ordering pre-refactor — must be preserved.
    fixed_tail = [
        Path("/Applications/Argyll/bin"),
        Path("/Applications/ArgyllCMS/bin"),
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
        Path("/opt/local/bin"),
        Path.home() / "ArgyllCMS/bin",
        Path.home() / "Applications/Argyll/bin",
        Path.home() / ".local/bin",
    ]
    assert dirs[-len(fixed_tail):] == fixed_tail


def test_argyll_candidates_windows(fresh_module):
    pp = fresh_module("win32")
    dirs = pp.argyll_candidate_dirs()
    assert Path(r"C:\Program Files\ArgyllCMS\bin") in dirs
    assert Path(r"C:\Program Files (x86)\ArgyllCMS\bin") in dirs


def test_argyll_candidates_linux(fresh_module):
    pp = fresh_module("linux")
    dirs = pp.argyll_candidate_dirs()
    assert Path("/usr/bin") in dirs
    assert Path("/usr/local/bin") in dirs
    # No /Applications scan on Linux.
    assert not any("/Applications" in str(d) for d in dirs)


# ---------------------------------------------------------------------------
# argyll_download_page
# ---------------------------------------------------------------------------

def test_download_page_windows(fresh_module):
    pp = fresh_module("win32")
    assert pp.argyll_download_page() == "https://www.argyllcms.com/downloadwin.html"


def test_download_page_macos(fresh_module):
    pp = fresh_module("darwin")
    assert pp.argyll_download_page() == "https://www.argyllcms.com/downloadmac.html"


def test_download_page_linux(fresh_module):
    pp = fresh_module("linux")
    assert pp.argyll_download_page() == "https://www.argyllcms.com/downloadlinux.html"


# ---------------------------------------------------------------------------
# log_dir
# ---------------------------------------------------------------------------
# Each unsets CHROMIQ_LOG_DIR, which the suite sets for itself (B8-1419), to
# pin what the app answers on a user's machine.

def test_log_dir_windows(fresh_module):
    pp = fresh_module("win32", {"LOCALAPPDATA": r"C:\Users\test\AppData\Local",
                                "CHROMIQ_LOG_DIR": None})
    assert pp.log_dir() == Path(r"C:\Users\test\AppData\Local") / "ChromIQ" / "Logs"


def test_log_dir_macos(fresh_module):
    pp = fresh_module("darwin", {"CHROMIQ_LOG_DIR": None})
    assert pp.log_dir() == Path.home() / "Library" / "Logs" / "ChromIQ"


def test_log_dir_linux_xdg(fresh_module):
    pp = fresh_module("linux", {"XDG_STATE_HOME": "/var/test-xdg/state",
                                "CHROMIQ_LOG_DIR": None})
    assert pp.log_dir() == Path("/var/test-xdg/state") / "ChromIQ" / "logs"


def test_log_dir_linux_fallback(fresh_module):
    pp = fresh_module("linux", {"XDG_STATE_HOME": None, "CHROMIQ_LOG_DIR": None})
    assert pp.log_dir() == Path.home() / ".local" / "state" / "ChromIQ" / "logs"


# ---------------------------------------------------------------------------
# icc_install_dir
# ---------------------------------------------------------------------------

def test_icc_install_windows(fresh_module):
    pp = fresh_module("win32", {"WINDIR": r"C:\Windows"})
    # On macOS test runners ``Path`` is PosixPath, so the join normalises
    # to forward slashes after the WINDIR prefix; compare to the same
    # expression rather than a hardcoded backslash literal.
    assert pp.icc_install_dir() == (
        Path(r"C:\Windows") / "System32" / "spool" / "drivers" / "color"
    )


def test_icc_install_macos(fresh_module):
    pp = fresh_module("darwin")
    assert pp.icc_install_dir() == Path.home() / "Library" / "ColorSync" / "Profiles"


def test_icc_install_linux_xdg(fresh_module):
    pp = fresh_module("linux", {"XDG_DATA_HOME": "/var/test-xdg/data"})
    assert pp.icc_install_dir() == Path("/var/test-xdg/data") / "color" / "icc"


def test_icc_install_linux_fallback(fresh_module):
    pp = fresh_module("linux", {"XDG_DATA_HOME": None})
    assert pp.icc_install_dir() == Path.home() / ".local" / "share" / "color" / "icc"


# ---------------------------------------------------------------------------
# icc_system_dirs
# ---------------------------------------------------------------------------

def test_icc_system_dirs_macos(fresh_module):
    pp = fresh_module("darwin")
    assert pp.icc_system_dirs() == [
        Path.home() / "Library" / "ColorSync" / "Profiles",
        Path("/Library/ColorSync/Profiles"),
        Path("/System/Library/ColorSync/Profiles"),
    ]


def test_icc_system_dirs_linux_includes_colord(fresh_module):
    pp = fresh_module("linux", {"XDG_DATA_HOME": None})
    dirs = pp.icc_system_dirs()
    assert Path("/var/lib/colord/icc") in dirs
    assert Path("/usr/share/color/icc") in dirs
    assert Path.home() / ".local" / "share" / "color" / "icc" in dirs


# ---------------------------------------------------------------------------
# native_print_supported
# ---------------------------------------------------------------------------

def test_native_print_only_on_macos(fresh_module):
    assert fresh_module("darwin").native_print_supported() is True
    assert fresh_module("win32").native_print_supported() is False
    assert fresh_module("linux").native_print_supported() is False

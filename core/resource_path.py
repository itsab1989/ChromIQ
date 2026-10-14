"""PyInstaller-compatible resource path resolver."""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent


def resource_path(relative: str) -> Path:
    """Return absolute path to a bundled resource.

    In a frozen PyInstaller bundle sys._MEIPASS points to the temp extraction
    directory.  During development the project root is used instead.
    """
    base = Path(getattr(sys, "_MEIPASS", _PROJECT_ROOT))
    return base / relative


def argyll_binary(name: str) -> str:
    """Return the platform-correct binary name (appends .exe on Windows)."""
    return name + ".exe" if sys.platform == "win32" else name


def argyll_tool_path(bin_dir: "str | Path", tool: str) -> Path:
    """The path of ArgyllCMS tool *tool* inside *bin_dir*, with the platform's
    executable suffix (``txt2ti3.exe`` on Windows).

    **EVERY PATH TO AN ARGYLL TOOL IS BUILT HERE.** ``bin_dir / "txt2ti3"``
    names a file that does not exist on Windows, so an ``.exists()`` check on
    it fails there and nowhere else: #209, the Measure tab's Import of an
    i1Profiler ``.txt`` said txt2ti3 could not be found while Tools >
    Convert i1Profiler, which goes through ``ArgyllRunner``, converted the
    same file. ``tests/test_209_argyll_tool_paths_carry_the_windows_suffix.py``
    fails on any code that joins a tool name onto a folder by hand."""
    return Path(bin_dir) / argyll_binary(tool)

"""ref/ resolution must follow Homebrew's per-binary symlinks (Knut).

/opt/homebrew/bin holds symlinks into the Cellar; ref/ is a sibling of the
Cellar bin, not of /opt/homebrew/bin.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from core.argyll_detect import resolve_ref_dir
from core.resource_path import argyll_binary

_TOOLS = ("targen", "printtarg", "chartread", "colprof")


def _make_cellar(tmp: Path) -> tuple[Path, Path, Path]:
    """Build a fake Homebrew layout: cellar bin with tools + ref/, and a
    brew 'bin' of symlinks pointing at them. Returns (brew_bin, cellar_bin, ref)."""
    cellar = tmp / "Cellar" / "argyll-cms" / "3.5.0"
    cellar_bin = cellar / "bin"
    cellar_bin.mkdir(parents=True)
    ref = cellar / "ref"
    ref.mkdir()
    (ref / "ClayRGB1998.icm").write_bytes(b"icc")
    for t in _TOOLS:
        (cellar_bin / argyll_binary(t)).write_text("#!/bin/sh\n", encoding="utf-8")
    brew_bin = tmp / "brew" / "bin"
    brew_bin.mkdir(parents=True)
    for t in _TOOLS:
        (brew_bin / argyll_binary(t)).symlink_to(cellar_bin / argyll_binary(t))
    return brew_bin, cellar_bin, ref


@pytest.mark.skipif(sys.platform == "win32", reason="symlink farm is a Homebrew/*nix layout")
def test_resolve_ref_via_symlinks(tmp_path):
    brew_bin, cellar_bin, ref = _make_cellar(tmp_path)
    # The brew bin has NO ref sibling, but resolving the symlinks finds it.
    assert not (brew_bin.parent / "ref").exists()
    assert resolve_ref_dir(brew_bin) == ref
    # Direct (real) bin also works.
    assert resolve_ref_dir(cellar_bin) == ref


def test_resolve_ref_direct_sibling(tmp_path):
    # A normal /Applications/Argyll install: ref beside bin.
    bind = tmp_path / "Argyll" / "bin"
    bind.mkdir(parents=True)
    ref = tmp_path / "Argyll" / "ref"
    ref.mkdir()
    for t in _TOOLS:
        (bind / argyll_binary(t)).write_text("x", encoding="utf-8")
    assert resolve_ref_dir(bind) == ref


def test_resolve_ref_none_when_absent(tmp_path):
    bind = tmp_path / "bin"
    bind.mkdir()
    assert resolve_ref_dir(bind) is None

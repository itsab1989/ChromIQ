"""The committed chart-reading helper carries no build machine's folder names.

4.3.59 review: i1pro3_imp.c's asserts print ``__FILE__``, the absolute source
path, so the helper committed to this (public) repository carried the
builder's home folder. ``native/chartread_helper/CMakeLists.txt`` now maps the
source root to "." with ``-ffile-prefix-map``; this keeps it that way, for the
binary as committed and for the build file that makes it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "native" / "chromiq-chartread"

#: a user's home folder on macOS, Linux and Windows, in any string of the binary
PRIVATE = (b"/Users/", b"/home/", b"C:\\Users\\", b"C:/Users/")


def test_the_committed_helper_holds_no_home_folder():
    if not HELPER.is_file():
        pytest.skip("no committed helper in this checkout")
    data = HELPER.read_bytes()
    found = {p.decode(): data.count(p) for p in PRIVATE if p in data}
    assert not found, f"the committed helper names a home folder: {found}"


def test_the_helper_still_names_its_source_file_relatively():
    """The map keeps the file name: an assert still says where it fired."""
    if not HELPER.is_file():
        pytest.skip("no committed helper in this checkout")
    assert b"native/instlib/i1pro3_imp.c" in HELPER.read_bytes()


def test_the_build_maps_the_source_root():
    cm = (ROOT / "native" / "chartread_helper" / "CMakeLists.txt").read_text(encoding="utf-8")
    assert re.search(r'add_compile_options\("-ffile-prefix-map=\$\{_cq_source_root\}=\."\)', cm)
    # set before any target, so every one of them gets it
    assert cm.index("add_compile_options(\"-ffile-prefix-map") < cm.index("add_library(instlib")

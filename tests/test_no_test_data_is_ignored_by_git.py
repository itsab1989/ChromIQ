"""A file the suite reads must be in the repository, not only on this Mac.

4.3.52 (review M1, 2026-11-20): the two sheet TIFFs that
tests/test_the_marker_finds_the_strips_of_an_imported_sheet.py opens sat in
tests/data/jctay_patch_length_sheets/ and were caught by `.gitignore`'s
``*.tif``. Every test was green here and 7 of them failed on any fresh
checkout (CI, the Windows VM, master after the merge). They are this
project's own generated sheets, posted on the forum (byte-identical to
ChromIQ-work 2026-11-19_jctay_reply/chart and 2026-11-20_jctay_sheet2/chart).

So: nothing under the suite's data folders may be ignored by git. A new data
file of a kind `.gitignore` catches fails here at once, on the machine that
has it, instead of on the next clean checkout.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA_DIRS = ("tests/data", "tests/fixtures", "tests/golden")


def _git(*args: str) -> "subprocess.CompletedProcess[str]":
    git = shutil.which("git")
    if git is None:
        pytest.skip("git not available")
    r = subprocess.run([git, "-C", str(ROOT), *args], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60)
    if r.returncode != 0 and "not a git repository" in r.stderr:
        pytest.skip("not a git checkout")
    return r


def test_no_file_under_the_test_data_folders_is_ignored():
    r = _git("ls-files", "--others", "--ignored", "--exclude-standard", "--", *DATA_DIRS)
    assert r.returncode == 0, r.stderr
    ignored = [ln for ln in r.stdout.splitlines()
               if ln and "__pycache__" not in ln and not ln.endswith(".pyc")]
    assert ignored == [], ("ignored by .gitignore, so missing on a fresh checkout: "
                           + ", ".join(ignored))


def test_the_imported_sheets_are_tracked():
    r = _git("ls-files", "--", "tests/data/jctay_patch_length_sheets")
    assert r.returncode == 0, r.stderr
    tracked = set(r.stdout.split())
    for name in ("PatchLengthTest_100x150.tif", "PatchLengthTest_100x150.ti2",
                 "PatchLengthTest2_100x150.tif", "PatchLengthTest2_100x150.ti2",
                 "strip_columns.json"):
        assert f"tests/data/jctay_patch_length_sheets/{name}" in tracked, name


def test_gitignore_keeps_the_exception():
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "!tests/data/**/*.tif" in gi and "!tests/data/**/*.tiff" in gi

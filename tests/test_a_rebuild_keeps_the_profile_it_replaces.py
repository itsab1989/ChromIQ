"""Pressing Build Profile twice must not destroy the profile you already had.

Adversary round 26, R26-F1, driven on screen: a run holding a finished
203,676-byte profile was asked to build again, and **a quarter of a second
later the file on disk was 0 bytes**. It stayed 0 bytes for every sample of
the next eight seconds, and quitting the app mid-build left it that way for
good. `Run.built_profile_icc().exists()` then answered True, Check & Refine
was enabled, and only `workflow.icc_info.read_icc` would say what the file
really was ("too small to be an ICC profile").

`colprof` is handed the run's basename and truncates `<stem>.icc` the moment
it opens it, so the protection cannot live in the builder's finish handler: it
has to happen BEFORE the process starts. That is what these guards pin, at the
door a person actually presses, with the builder replaced by a recorder that
answers one question - what was on disk at the instant the build was launched.

`_archive_superseded_profile` had done the right thing for a year, from ONE
branch: the "Build here anyway" answer to the §6 verification warning. For an
ordinary run `profile_rebuild_guard.assess` returns `needed=False` with the
reason "no verification chart", so the question is never asked and that branch
is never reached. A guard written against that method would have passed
throughout.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs.tab_profile import TabProfile  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _a_run_with_a_profile(tmp_path: Path, size: int = 203_676):
    """A real run folder on disk: a measurement, and a profile beside it."""
    run_dir = tmp_path / "Demo-Paper" / "runs" / "run1"
    run_dir.mkdir(parents=True)
    ti3 = run_dir / "Demo-Paper.ti3"
    ti3.write_text("CTI3\nNUMBER_OF_SETS 3\n", encoding="utf-8")
    icc = run_dir / "Demo-Paper.icc"
    icc.write_bytes(b"P" * size)
    return ti3, icc


def _tab_that_records_the_build(tmp_path, ti3):
    """The real tab, with the two doors that depend on this machine stubbed and
    the BUILDER replaced by a recorder.

    Only two things are faked, and neither is the subject: whether ArgyllCMS is
    installed here, and colprof itself. Everything between the button and the
    launch is the app's own.
    """
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    tab = TabProfile(ArgyllRunner(s), s)
    tab.set_ti3_path(ti3) if hasattr(tab, "set_ti3_path") else None
    tab._ti3_path = ti3
    tab._refuse_when_the_profiler_is_not_installed = lambda engine: False
    tab._resolve_engine = lambda params: "colprof"
    seen = {}

    def _record(params, on_line, on_finish):
        icc = params.ti3_path.with_suffix(".icc")
        seen["at_launch"] = icc.stat().st_size if icc.exists() else None
        seen["params"] = params
        # colprof truncates the file it is handed the moment it opens it.
        icc.write_bytes(b"")

    tab._builder.build = _record
    return tab, seen


def test_the_profile_is_archived_before_the_build_starts(qapp, tmp_path):
    ti3, icc = _a_run_with_a_profile(tmp_path)
    tab, seen = _tab_that_records_the_build(tmp_path, ti3)

    tab._on_build()

    assert "at_launch" in seen, "the build never started, so nothing was measured"
    assert seen["at_launch"] is None, (
        "the profile was still in the run folder when colprof was launched, so "
        "colprof truncated it: that is R26-F1")
    old = sorted((ti3.parent / "old").glob("*/Demo-Paper.icc"))
    assert len(old) == 1, f"the previous profile is not in old/: {old}"
    assert old[0].stat().st_size == 203_676, "it was archived, but not intact"


def test_a_run_with_no_profile_archives_nothing(qapp, tmp_path):
    """No empty dated folders for a first build: `old/` says something happened."""
    ti3, icc = _a_run_with_a_profile(tmp_path)
    icc.unlink()
    tab, seen = _tab_that_records_the_build(tmp_path, ti3)

    tab._on_build()

    assert "at_launch" in seen
    assert not (ti3.parent / "old").exists(), "a first build left an archive behind"


def test_a_zero_byte_profile_is_not_archived(qapp, tmp_path):
    """The wreckage of an earlier interrupted build is not worth keeping, and
    archiving it would bury the good copy under dated folders of nothing."""
    ti3, icc = _a_run_with_a_profile(tmp_path, size=0)
    tab, seen = _tab_that_records_the_build(tmp_path, ti3)

    tab._on_build()

    assert not (ti3.parent / "old").exists()

"""#137 Table C / D1 — a calibration is archived, never deleted.

This is the most valuable fix in the issue. Regenerating a calibration chart
called ``Calibration.reset()``, and that was ``shutil.rmtree(cal/)``: a whole
printed and measured sheet's worth of work, gone with no warning and no way
back — and with it printcal's Re-calibrate and Verify modes, which read the
previous ``.cal``.
"""
from __future__ import annotations

import inspect

import pytest

from core.file_manager import Calibration


@pytest.fixture
def cal(tmp_path):
    root = tmp_path / "Test-Printer"
    root.mkdir()
    c = Calibration(root)
    c.ensure_dir()
    for name in (f"{c.stem}.ti1", f"{c.stem}.ti2", f"{c.stem}.ti3",
                 f"{c.stem}.cal"):
        (c.dir / name).write_text(name)
    return c


def test_nothing_is_deleted(cal):
    before = {p.name: p.read_text() for p in cal.live_files()}
    cal.reset()
    archives = list(cal.old_dir.iterdir())
    assert len(archives) == 1
    kept = {p.name: p.read_text() for p in archives[0].iterdir() if p.is_file()}
    assert kept == before, "a calibration was lost"


def test_the_folder_is_cleared_for_the_new_chart(cal):
    cal.reset()
    assert cal.live_files() == []


def test_the_stored_chart_copy_travels_with_it(cal):
    """Restoring an archived calibration must give the chart it was measured
    with, not the chart that replaced it."""
    cal.snapshot_dir.mkdir()
    (cal.snapshot_dir / f"{cal.stem}.ti2").write_text("the measured chart")
    cal.reset()
    archive = next(iter(cal.old_dir.iterdir()))
    assert (archive / "chart" / f"{cal.stem}.ti2").read_text() == "the measured chart"


def test_archiving_an_empty_calibration_does_nothing(cal):
    cal.reset()
    n_before = len(list(cal.old_dir.iterdir()))
    cal.reset()
    assert len(list(cal.old_dir.iterdir())) == n_before, "an empty archive was made"


def test_an_archive_is_never_swept_into_the_next_one(cal):
    """Nesting old/ inside old/ turns "go back to it" into a dig."""
    cal.reset()
    (cal.dir / f"{cal.stem}.ti2").write_text("second chart")
    cal.reset()
    for archive in cal.old_dir.iterdir():
        assert not (archive / "old").exists()
    assert len(list(cal.old_dir.iterdir())) == 2


def test_the_chart_creator_no_longer_wipes_the_folder():
    """The call site is what mattered: reset() is archive-then-clear now, and
    nothing may reintroduce an rmtree of cal/."""
    import workflow.chart_creator as cc

    src = inspect.getsource(cc)
    assert "rmtree" not in src or "calibration" not in src.split("rmtree")[0][-200:]
    cal_src = inspect.getsource(Calibration.reset)
    assert "rmtree" not in cal_src
    assert "archive_to_old" in cal_src

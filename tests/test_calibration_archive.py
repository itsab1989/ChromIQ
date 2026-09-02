"""#137 Table C / D1 — a calibration's RESULTS are archived, never deleted.

This is the most valuable fix in the issue. Regenerating a calibration chart
called ``Calibration.reset()``, and that was ``shutil.rmtree(cal/)``: a whole
printed and measured sheet's worth of work, gone with no warning and no way
back — and with it printcal's Re-calibrate and Verify modes, which read the
previous ``.cal``.

**Knut narrowed what "archived" covers in beta.148**, and the rule is now the
one runs have always followed:

> *"Only measurement ti3 files shall be copied to cal/old/<date_time>/ folder,
> similar to how it is done for a run."*

So the measurement, the ``.cal`` and any profile built from them are archived —
they cannot be regenerated. What happens to the CHART depends on whether
anything was measured (the owner's ruling, 2026-09-02, option 3):

* nothing measured — the chart is an experiment. It is set aside for the length
  of the build and dropped when a replacement exists, exactly as
  :meth:`Run.reset_chart_artefacts` treats a run's chart, and no dated folder is
  made at all.
* measured — the chart travels into ``<archive>/chart/``, one level below the
  results, so the dated folder's own listing still holds only what cannot be
  regenerated. Sweeping it into the top level left a dated folder holding a bare
  ``.ti1``/``.ti2`` that reads like a kept calibration and is not one.
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
        (c.dir / name).write_text(name, encoding="utf-8")
    return c


def test_what_cannot_be_regenerated_is_archived(cal):
    cal.reset()
    archives = list(cal.old_dir.iterdir())
    assert len(archives) == 1
    kept = {p.name: p.read_text(encoding="utf-8") for p in archives[0].iterdir() if p.is_file()}
    assert kept == {f"{cal.stem}.ti3": f"{cal.stem}.ti3",
                    f"{cal.stem}.cal": f"{cal.stem}.cal"}, (
        "the measurement and the .cal are the calibration; both must survive"
    )


def test_the_chart_is_not_loose_in_the_dated_folder(cal):
    """Knut's beta.148 listing rule, and NOTHING MORE THAN THAT.

    THIS TEST USED TO BE CALLED `test_the_chart_is_replaced_rather_than_archived`
    AND ITS NAME WAS A LIE. Its assertion was scoped to the archive's top level;
    `fe92ed1f` moved the chart to `<archive>/chart/`, so it went on passing while
    the chart was kept in the dated folder — the exact thing its docstring said
    must not happen. Found by the adversarial round, 2026-09-02.

    What it can honestly guard is the listing clause: the dated folder's own
    contents are what cannot be regenerated. Whether keeping the chart one level
    down still answers K6's second clause ("The chart is replaced, as a run's
    is") is an open question for the owner, and a test must not pretend to have
    settled it. The unmeasured half of that question IS settled — see
    `test_an_unmeasured_chart_really_is_replaced_as_a_runs_is` below."""
    cal.reset()
    archive = next(iter(cal.old_dir.iterdir()))
    for name in (f"{cal.stem}.ti1", f"{cal.stem}.ti2"):
        assert not (archive / name).exists(), f"{name} should not be loose"
        assert not (cal.dir / name).exists(), f"{name} should be cleared"
    assert (archive / "chart" / f"{cal.stem}.ti2").is_file(), (
        "the chart is somewhere this test does not look — say where, or the "
        "assertions above guard nothing")


def test_an_unmeasured_chart_really_is_replaced_as_a_runs_is(tmp_path):
    """K6's second clause, made true for the case the owner ruled on
    (2026-09-02, option 3). A chart with nothing measured is set aside for the
    length of the build and dropped when it finishes — no dated folder at all,
    which is exactly what `Run.reset_chart_artefacts(stash=True)` does."""
    root = tmp_path / "Unmeasured"
    root.mkdir()
    c = Calibration(root)
    c.ensure_dir()
    for name in (f"{c.stem}.ti1", f"{c.stem}.ti2"):
        (c.dir / name).write_text(name, encoding="utf-8")

    got = c.reset(stash=True)
    assert got.archive is None and got.stash is not None
    c.settle_chart_stash(got.stash, built=True)

    assert not c.old_dir.exists(), "an experiment left a dated folder behind"
    assert c.live_files() == []


def test_the_folder_is_cleared_for_the_new_chart(cal):
    cal.reset()
    assert cal.live_files() == []


def test_a_rebuild_keeps_the_stored_chart_copy_where_it_is(cal):
    """``cal/chart/`` is what Restore Used Chart reads. A rebuild must not move
    it into an archive, or the button loses the chart it exists to put back."""
    cal.snapshot_dir.mkdir()
    (cal.snapshot_dir / f"{cal.stem}.ti2").write_text("the measured chart", encoding="utf-8")
    cal.reset()
    assert (cal.snapshot_dir / f"{cal.stem}.ti2").read_text(encoding="utf-8") == "the measured chart"


def test_archiving_everything_takes_the_stored_chart_copy_along(cal):
    """The whole-calibration archive is a different question from a rebuild:
    restoring one must give the chart it was measured with."""
    cal.snapshot_dir.mkdir()
    (cal.snapshot_dir / f"{cal.stem}.ti2").write_text("the measured chart", encoding="utf-8")
    archive = cal.archive_to_old()
    assert (archive / "chart" / f"{cal.stem}.ti2").read_text(encoding="utf-8") == "the measured chart"


def test_the_calibrations_own_words_survive_a_rebuild(cal):
    """``meta.json`` describes the calibration slot, not the chart."""
    meta = cal.load_meta()
    meta.description = "Canson Baryta, new ink set"
    meta.chart_notes = "printed 6 Aug"
    cal.save_meta(meta)
    cal.reset()
    assert cal.load_meta().description == "Canson Baryta, new ink set"
    assert cal.load_meta().chart_notes == "printed 6 Aug"


def test_archiving_an_empty_calibration_does_nothing(cal):
    cal.reset()
    n_before = len(list(cal.old_dir.iterdir()))
    cal.reset()
    assert len(list(cal.old_dir.iterdir())) == n_before, "an empty archive was made"


def test_an_archive_is_never_swept_into_the_next_one(cal):
    """Nesting old/ inside old/ turns "go back to it" into a dig."""
    cal.reset()
    (cal.dir / f"{cal.stem}.ti2").write_text("second chart", encoding="utf-8")
    (cal.dir / f"{cal.stem}.ti3").write_text("second measurement", encoding="utf-8")
    cal.reset()
    for archive in cal.old_dir.iterdir():
        assert not (archive / "old").exists()
    assert len(list(cal.old_dir.iterdir())) == 2


def test_the_chart_creator_no_longer_wipes_the_folder():
    """The call site is what mattered: reset() archives-then-clears, and
    nothing may reintroduce an rmtree of ``cal/`` itself."""
    import workflow.chart_creator as cc

    src = inspect.getsource(cc)
    assert "rmtree" not in src or "calibration" not in src.split("rmtree")[0][-200:]
    cal_src = inspect.getsource(Calibration.reset)
    assert "rmtree(self.dir" not in cal_src, "cal/ is being deleted wholesale"
    # `archive_to_old` moved one level down into `_archive_without_raising`,
    # which is the ONLY thing reset() may reach it through — a bare call would
    # put a PermissionError back into a Qt slot.
    assert "_archive_without_raising" in cal_src
    assert "archive_to_old" in inspect.getsource(
        Calibration._archive_without_raising)
    assert "archive_to_old" not in cal_src, (
        "reset() calls archive_to_old directly again, so a read-only cal/ "
        "raises out of the Qt slot that generates the chart")

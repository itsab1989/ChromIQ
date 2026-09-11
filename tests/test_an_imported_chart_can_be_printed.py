"""A chart imported without its pages must still be printable.

`import_external_chart` copies; it runs no layout tool. So a `.ti2` imported
with no page bitmaps beside it produced a run that could not be printed at all:
the Create Chart preview showed nothing and the Print tab listed no pages, with
nothing anywhere saying why. Found by the audit of every chart load and generate
path that Knut asked for (issue #182), driven on screen.

Knut chose between two readings of his own "loading a ti2 should generate"
(2026-09-11):

    *"A agree with implementing your point 1: 'Rebuild only the missing pages,
    from the recipe the file itself carries. That fixes the unprintable run and
    changes nothing else. A chart you have already printed still reprints
    exactly as it was.'"*

So the two halves of that sentence are the two halves of this file. The pages
are drawn from what the `.ti2` itself records, its own patch order, its
instrument and its paper; and a chart that already has pages is left alone.

He also ruled that this says nothing to the user: *"I don't think so. it is the
ti2 file that is imported, and any existing tif files may not show according to
the settings, margins and other features in the Create Chart tab in ChromIQ."*

These tests build a REAL chart with ArgyllCMS, because the thing being tested is
whether printtarg reproduces the imported chart's layout. A fake would be a
re-implementation of the code under test validating itself.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from workflow.chart_import import chart_page_tiffs, rebuild_missing_pages

_BIN = Path("/Applications/Argyll/bin")


@pytest.fixture(scope="module")
def a_real_chart(tmp_path_factory):
    """A 60-patch chart made by targen and printtarg: .ti1, .ti2 and one page."""
    if not (_BIN / "printtarg").exists():
        pytest.skip("no ArgyllCMS on this machine")
    d = tmp_path_factory.mktemp("chart")
    subprocess.run([str(_BIN / "targen"), "-d2", "-f60", "real"], cwd=d,
                   check=True, capture_output=True, timeout=120)
    subprocess.run([str(_BIN / "printtarg"), "-ii1", "-pA4", "-t300", "real"],
                   cwd=d, check=True, capture_output=True, timeout=120)
    assert (d / "real.ti2").is_file() and (d / "real.tif").is_file()
    return d


def _lone_ti2(src: Path, tmp_path: Path) -> Path:
    """The shape the audit found: the chart file, and nothing beside it."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    dst = tmp_path / "Imported.ti2"
    shutil.copy2(src / "real.ti2", dst)
    return dst


def test_a_chart_that_arrived_alone_gets_its_pages(a_real_chart, tmp_path):
    ti2 = _lone_ti2(a_real_chart, tmp_path)
    assert chart_page_tiffs(ti2) == [], "the fixture really is a chart with no pages"
    pages = rebuild_missing_pages(ti2, _BIN)
    assert pages, "the imported chart still cannot be printed"
    assert all(p.exists() and p.stat().st_size > 1000 for p in pages)
    assert chart_page_tiffs(ti2) == pages


def test_the_pages_are_the_chart_that_was_imported(a_real_chart, tmp_path):
    """THE ONLY THING THAT MATTERS ABOUT A REDRAWN SHEET. If printtarg puts the
    patches anywhere other than where the imported .ti2 says they are, the
    measurement taken from the sheet is read against the wrong colours."""
    from workflow.ti2_relayout import ChartSpec
    ti2 = _lone_ti2(a_real_chart, tmp_path)
    before = ChartSpec.from_ti2(ti2)
    rebuild_missing_pages(ti2, _BIN)
    after = ChartSpec.from_ti2(ti2)
    assert [(p.loc, p.dev) for p in after.patches] == \
           [(p.loc, p.dev) for p in before.patches]


def test_the_imported_chart_file_is_never_touched(a_real_chart, tmp_path):
    """printtarg writes a .ti2 of its own while drawing. It is discarded: the
    file that came in is what the measurement will be read against."""
    ti2 = _lone_ti2(a_real_chart, tmp_path)
    original = ti2.read_bytes()
    rebuild_missing_pages(ti2, _BIN)
    assert ti2.read_bytes() == original


def test_a_chart_that_already_has_pages_is_left_alone(a_real_chart, tmp_path):
    """The other half of Knut's sentence: a chart you have already printed
    still reprints exactly as it was."""
    ti2 = tmp_path / "Imported.ti2"
    shutil.copy2(a_real_chart / "real.ti2", ti2)
    page = tmp_path / "Imported.tif"
    shutil.copy2(a_real_chart / "real.tif", page)
    stamp = (page.stat().st_mtime_ns, page.stat().st_size)
    out = rebuild_missing_pages(ti2, _BIN)
    assert out == [page]
    assert (page.stat().st_mtime_ns, page.stat().st_size) == stamp, \
        "an existing page was redrawn"


def test_the_patch_set_is_written_when_the_import_brought_none(
        a_real_chart, tmp_path):
    """A run holding a chart and no patch set cannot be restored or re-laid-out
    later either."""
    ti2 = _lone_ti2(a_real_chart, tmp_path)
    assert not ti2.with_suffix(".ti1").exists()
    rebuild_missing_pages(ti2, _BIN)
    assert ti2.with_suffix(".ti1").is_file()


def test_a_patch_set_that_came_with_the_chart_is_not_overwritten(
        a_real_chart, tmp_path):
    ti2 = _lone_ti2(a_real_chart, tmp_path)
    ti1 = ti2.with_suffix(".ti1")
    shutil.copy2(a_real_chart / "real.ti1", ti1)
    original = ti1.read_bytes()
    rebuild_missing_pages(ti2, _BIN)
    assert ti1.read_bytes() == original


def test_a_file_that_is_not_a_chart_draws_nothing_and_does_not_raise(tmp_path):
    bad = tmp_path / "notachart.ti2"
    bad.write_text("this is not a chart\n", encoding="utf-8")
    assert rebuild_missing_pages(bad, _BIN) == []
    assert chart_page_tiffs(bad) == []


def test_a_missing_file_draws_nothing_and_does_not_raise(tmp_path):
    assert rebuild_missing_pages(tmp_path / "gone.ti2", _BIN) == []


# ---------------------------------------------------------------------------
# …and the import itself, not only the helper
# ---------------------------------------------------------------------------
def _project(tmp_path):
    from core.file_manager import Project
    work = tmp_path / "w"
    work.mkdir()
    return Project.create(work / "P", "P")


class _Target:
    """What the measurement bar hands the import: a run type and a run."""

    def __init__(self, verification=False, profile_run=""):
        self._v = verification
        self.profile_run = profile_run
        self.run_type = "verification" if verification else "profiling"

    def is_verification(self):
        return self._v


def test_the_import_draws_the_pages_when_it_is_given_the_binaries(
        a_real_chart, tmp_path, qapp):
    from workflow.chart_import import import_external_chart
    proj = _project(tmp_path)
    lone = _lone_ti2(a_real_chart, tmp_path / "src")
    out = import_external_chart(lone, None, [], proj, _Target(), bin_dir=_BIN)
    assert chart_page_tiffs(out), "the imported run still has no pages"


def test_and_copies_without_drawing_when_it_is_not(a_real_chart, tmp_path, qapp):
    """The default is unchanged behaviour, so a caller that has not been given
    the binaries cannot start running a layout tool by accident."""
    from workflow.chart_import import import_external_chart
    proj = _project(tmp_path)
    lone = _lone_ti2(a_real_chart, tmp_path / "src2")
    out = import_external_chart(lone, None, [], proj, _Target())
    assert chart_page_tiffs(out) == []


def test_a_verification_chart_gets_its_pages_too(a_real_chart, tmp_path, qapp):
    """The two run types file the chart in different folders, and the fix that
    reaches only one of them is the shape this project keeps finding."""
    from workflow.chart_import import import_external_chart
    proj = _project(tmp_path)
    lone = _lone_ti2(a_real_chart, tmp_path / "src3")
    out = import_external_chart(lone, None, [], proj,
                                _Target(verification=True), bin_dir=_BIN)
    assert "verifications" in str(out)
    assert chart_page_tiffs(out), "the verification chart cannot be printed"

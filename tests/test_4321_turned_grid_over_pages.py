"""4.3.21: a measurement of the turned i1Profiler chart that i1Profiler cut
over several pages is filed when every patch, counted on over the pages, is in
the turned chart's cell (forum report by jctay, 2026-11-02).

He measured his 600-patch chart once on i1Profiler's 12 x 50 grid on one page
(filed fine) and once after making i1Profiler's page shorter, which cut the
same grid into 5 pages of 10 rows. 4.3.19 and 4.3.20 refused the second with
a reason saying i1Profiler "numbered its rows page by page, starting again at
row 1 on each page"; his screenshots show i1Profiler asking for "row 11 on
page 2", "row 21 on page 3" and so on. In his two .mxf files every one of the
600 Locations, counted on over the pages (rows on earlier pages + row on this
page), is the same cell of the whole grid, with the same device values, and
the readings agree (mean 0.1, worst 0.83 in XYZ). So the paged file is the
same grid and is filed exactly like the one-page file.

What is still refused: other columns, any patch outside its cell (on any
page), and a paged file without Locations, since only the Locations show where
each patch was on the pages.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import exports_subdir                       # noqa: E402
from workflow import i1profiler_turned as T                        # noqa: E402
from workflow.i1profiler_export import i1p_location, i1p_page_rows  # noqa: E402
from workflow.measurement_import import complete_from_turned_order  # noqa: E402
from workflow.reference_convert import i1p_grid_of                 # noqa: E402

from tests.test_i1profiler_turned_export import _chart              # noqa: E402
from tests.test_i1profiler_turned_grid_check import _import, _mxf   # noqa: E402


def _data_rows(ti3: Path) -> list:
    lines = ti3.read_text(encoding="utf-8").splitlines()
    return lines[lines.index("BEGIN_DATA") + 1:lines.index("END_DATA")]


@pytest.fixture(scope="module")
def chart_600(tmp_path_factory):
    """600 patches: the order asks for 24 x 25 on one page, two sheets."""
    d = tmp_path_factory.mktemp("p600")
    ti2 = _chart(d / "p600", "P600", 600)
    assert not T.write_turned_export(ti2, exports_subdir(ti2.parent),
                                     "P600").skipped
    plan = T.plan_for(ti2)
    assert (plan.columns, plan.rows) == (24, 25)
    return ti2, T.TurnedFiles(exports_subdir(ti2.parent), "P600"), plan


def _filed(mxf: Path, ti2: Path) -> Path:
    ti3, v = _import(mxf, ti2)
    assert v.ok and v.turned_order, v.reason
    copy = mxf.with_name(mxf.stem + "-filed.ti3")
    shutil.copy2(ti3, copy)
    assert complete_from_turned_order(copy, ti2) == len(_data_rows(ti3))
    return copy


def test_five_pages_are_filed_exactly_like_one_page(chart_600, tmp_path):
    """jctay's case: the same columns, the rows cut evenly over 5 pages.
    The filed file is the one-page file row for row: SAMPLE_ID, SAMPLE_LOC,
    device values and readings. Only the grid keyword says what i1Profiler
    made."""
    ti2, files, plan = chart_600
    one = _filed(_mxf(files.txf("i1Pro 3"), tmp_path / "one.mxf",
                      columns=24), ti2)
    five_mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "five.mxf",
                    columns=24, pages=5)
    five = _filed(five_mxf, ti2)
    g = i1p_grid_of(five)
    assert (g.columns, g.rows, g.pages, g.located, g.misplaced) == (
        24, 5, 5, 600, 0)
    assert _data_rows(five) == _data_rows(one)
    assert 'columns=24 rows=5 pages=5' in five.read_text(encoding="utf-8")
    assert 'columns=24 rows=25 pages=1' in one.read_text(encoding="utf-8")


def test_the_page_relative_rows_are_what_the_file_holds(chart_600, tmp_path):
    """The Locations number the rows WITHIN each page (row 0 again on page
    2); counted on over the pages they are the order's cells. That is the
    reading the import relies on, so it is pinned here."""
    ti2, files, plan = chart_600
    per = i1p_page_rows(25, 5)
    assert per == [5, 5, 5, 5, 5]
    for j in range(600):
        page, row, col = i1p_location(j, 25, per)
        assert sum(per[:page - 1]) + row == j % plan.rows
        assert col == j // plan.rows


def test_an_uneven_split_is_filed_when_every_location_fits(tmp_path):
    """15 rows over 4 pages: i1Profiler's own split is 4 + 4 + 4 + 3 (larger
    first, as X-Rite's RGB_default-i1Pro.mxf has 23 + 23 + 22)."""
    ti2 = _chart(tmp_path / "p350", "P350", 350)
    T.write_turned_export(ti2, exports_subdir(ti2.parent), "P350")
    files = T.TurnedFiles(exports_subdir(ti2.parent), "P350")
    plan = T.plan_for(ti2)
    assert (plan.columns, plan.rows) == (24, 15)
    four = _filed(_mxf(files.txf("i1Pro 3"), tmp_path / "four.mxf",
                       columns=24, pages=4), ti2)
    assert i1p_grid_of(four).rows == 4
    one = _filed(_mxf(files.txf("i1Pro 3"), tmp_path / "one.mxf",
                      columns=24), ti2)
    assert _data_rows(four) == _data_rows(one)


@pytest.fixture()
def chart_360(tmp_path):
    ti2 = _chart(tmp_path / "p350", "P350", 350)
    T.write_turned_export(ti2, exports_subdir(ti2.parent), "P350")
    plan = T.plan_for(ti2)
    assert (plan.columns, plan.rows) == (24, 15)
    return ti2, T.TurnedFiles(exports_subdir(ti2.parent), "P350"), plan


@pytest.mark.parametrize("split", [[3, 4, 4, 4], [5, 5, 5], [4, 4, 4, 3],
                                   [6, 6, 3]])
def test_any_consistent_split_the_file_records_is_counted_on(chart_360,
                                                            tmp_path, split):
    """Review 4.3.21 r1: the rows on each page are read from the file's own
    Locations, not assumed. "Even, larger first" (4 + 4 + 4 + 3) and other
    splits (3 + 4 + 4 + 4) are filed alike when every Location, counted on
    over the pages, is the order's cell."""
    ti2, files, plan = chart_360
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "s.mxf", columns=24,
               pages=len(split), per_page=split)
    ti3, v = _import(mxf, ti2)
    g = i1p_grid_of(ti3)
    assert (g.pages, g.misplaced, g.located) == (len(split), 0, g.patches)
    assert v.ok and v.turned_order, v.reason


def test_a_page_filled_to_capacity_with_the_rest_last_is_filed(chart_600,
                                                               tmp_path):
    """The reviewer's case: 12 + 12 + 1 rows ("fill each page, the rest
    last"), which an "even" model (9 + 8 + 8) would have refused."""
    ti2, files, plan = chart_600
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "cap.mxf", columns=24,
               pages=3, per_page=[12, 12, 1])
    one = _filed(_mxf(files.txf("i1Pro 3"), tmp_path / "one.mxf",
                      columns=24), ti2)
    cap = _filed(mxf, ti2)
    g = i1p_grid_of(cap)
    assert (g.rows, g.pages, g.misplaced) == (12, 3, 0)
    assert _data_rows(cap) == _data_rows(one)


def _shift_page(mxf: Path, page: int, by: int) -> Path:
    """Every Location on *page* moves *by* rows down (a gap at its top)."""
    text = mxf.read_text(encoding="utf-8")
    pat = re.compile(r'(<cc:Tag Name="Page" Value="%d"/>'
                     r'<cc:Tag Name="Row" Value=")(\d+)(")' % page)
    text, n = pat.subn(lambda m: f"{m.group(1)}{int(m.group(2)) + by}"
                       f"{m.group(3)}", text)
    assert n
    mxf.write_text(text, encoding="utf-8")
    return mxf


def test_a_page_that_does_not_start_at_its_first_row_is_refused(chart_600,
                                                                tmp_path):
    """Page 2's rows start at row 1 instead of row 0: counted on over the
    pages, every patch from page 2 on sits one row off its cell, so the file
    is refused, with how many patches are outside their cell."""
    ti2, files, plan = chart_600
    mxf = _shift_page(_mxf(files.txf("i1Pro 3"), tmp_path / "gap.mxf",
                           columns=24, pages=5), 2, 1)
    ti3, v = _import(mxf, ti2)
    g = i1p_grid_of(ti3)
    assert g.misplaced > 0
    assert not v.ok and not v.turned_order
    assert (f"does not give {g.misplaced} of its {g.patches} patches the "
            "place") in v.reason
    before = ti3.read_bytes()
    assert complete_from_turned_order(ti3, ti2) == 0
    assert ti3.read_bytes() == before


def test_a_misplaced_cell_on_page_3_is_refused(chart_600, tmp_path):
    """Two entries on page 3 swap their Locations (rows 10 and 11 of the
    whole grid, column 0): the device values still agree, the grid is the
    same, and two patches are not in their cell."""
    ti2, files, plan = chart_600
    per = i1p_page_rows(25, 5)
    assert i1p_location(10, 25, per)[0] == 3
    assert i1p_location(11, 25, per)[0] == 3
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "swap.mxf", columns=24,
               pages=5, swap=(10, 11))
    ti3, v = _import(mxf, ti2)
    assert i1p_grid_of(ti3).misplaced == 2
    assert not v.ok and not v.turned_order
    r = v.reason
    assert ("i1Profiler kept the 24 columns that the how-to note for this "
            "chart names but cut the chart over 5 pages, with 5 rows on its "
            "first page") in r
    assert "does not give 2 of its 600 patches the place" in r
    assert "(columns: 24, rows: 25)" in r
    assert r.endswith("import that file")
    assert "—" not in r and "{" not in r
    copy = tmp_path / "copy.ti3"
    shutil.copy2(ti3, copy)
    before = copy.read_bytes()
    assert complete_from_turned_order(copy, ti2) == 0
    assert copy.read_bytes() == before


def test_other_columns_on_pages_are_refused(chart_600, tmp_path):
    ti2, files, plan = chart_600
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "wide.mxf", columns=23,
               pages=5, misread=(plan.rows, plan.columns))
    ti3, v = _import(mxf, ti2)
    assert i1p_grid_of(ti3).columns == 23
    assert not v.ok and not v.turned_order
    assert "laid that chart out on a different grid" in v.reason
    assert "columns: 23, pages: 5, rows on its first page:" in v.reason
    assert complete_from_turned_order(ti3, ti2) == 0


def test_pages_without_locations_are_refused(chart_600, tmp_path):
    """On one page the grid alone decides (as in 4.3.19); on several pages
    only the Locations say where each patch was, so without them nothing is
    filed."""
    ti2, files, plan = chart_600
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "bare.mxf", columns=24,
               pages=5, locations="none")
    ti3, v = _import(mxf, ti2)
    g = i1p_grid_of(ti3)
    assert (g.pages, g.located) == (5, 0)
    assert not v.ok and not v.turned_order
    # its own clause (review 4.3.21 r1), not "does not give 600 of its 600"
    assert ("the file records no place on those pages for any of its "
            "patches") in v.reason
    assert "does not give" not in v.reason
    assert v.reason.endswith("import that file")


def test_the_note_allows_pages_and_still_says_stop_for_other_columns(
        chart_600):
    ti2, files, plan = chart_600
    note = files.note.read_text(encoding="utf-8")
    assert "columns: 24, rows: 25, pages: 1" in note
    assert "If it shows anything else, stop" not in note
    assert "share the same rows out over several pages" in note
    assert "page 2 starts with row 11" in note
    assert ("If it shows another number of columns or another patch width, "
            "stop") in note


def test_the_measure_tab_files_a_paged_turned_mxf(qapp, tmp_path,
                                                  monkeypatch):
    """Through a real door: the Measure tab's IMPORT files the 5-page file
    into a new run, every reading on the patch the one-page file puts it."""
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.measurement_target import RUN_TYPE_PROFILING
    from core.settings import AppSettings
    from tests.test_i1profiler_turned_doors import (
        _answer, _project, _the_only_new_run, _well_filed)
    from tests.test_i1profiler_turned_import import _expected_xyz
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_measure import TabMeasure
    src = tmp_path / "src"
    src_ti2 = _chart(src, "Src", 600)
    T.write_turned_export(src_ti2, exports_subdir(src), "Src")
    files = T.TurnedFiles(exports_subdir(src), "Src")
    truth_dir = tmp_path / "truth"
    truth_dir.mkdir()
    truth = _expected_xyz(src_ti2, truth_dir)
    paged = _mxf(files.txf("i1Pro 3"), tmp_path / "paged.mxf", columns=24,
                 pages=5)
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    work = tmp_path / "work"
    work.mkdir()
    s.set("custom_output_path", str(work))
    proj, run = _project(work, "M", src_ti2, with_measurement=True)
    fm = FileManager(s)
    fm.set_target_name("M")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    tab = TabMeasure(ArgyllRunner(s), s)
    tab.set_target_controller(ctl)
    seen = _answer(monkeypatch, project="M")
    monkeypatch.setattr(tab, "_show_import_done_profiling", lambda *a: None)
    monkeypatch.setattr(tab, "_say_on_screen",
                        lambda t, b: seen["info"].append((t, b)))
    monkeypatch.setattr(tab, "_ask_how_printed", lambda *a: None)
    before = {p.name for p in proj.runs_root.iterdir() if p.is_dir()}
    tab._import_into_profiling_run(ctl, fm.project().run("run1"), paged)
    assert seen["refused"] == [], seen["refused"]
    new_dir = _the_only_new_run(proj.root, before)
    _well_filed(new_dir / "M.ti3", new_dir / "M.ti2", truth)


def test_the_note_of_a_chart_of_several_sheets_allows_pages(chart_600):
    """Step 6's sheets line agrees with step 5 (review 4.3.21 r1)."""
    ti2, files, plan = chart_600
    assert plan.sheets == 2
    note = files.note.read_text(encoding="utf-8")
    assert "This chart has 2 sheets." in note
    assert "or on several pages if it shares them out as step 5 describes" in note


def test_the_too_tall_refusal_no_longer_says_pages_cannot_match():
    import inspect
    src = re.sub(r'"\s*\n\s*"', "", inspect.getsource(T.plan_for))
    assert "no longer match the printed sheets" not in src
    # what is unchecked is a .txf asking for a taller page, not pages as
    # such (review 4.3.21 r2): jctay's paged case is checked
    assert ("How i1Profiler lays out a test-chart file that asks for a page "
            "taller than that has not been checked yet") in src
    assert "does not fit on one of its pages" not in src

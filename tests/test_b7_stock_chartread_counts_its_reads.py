"""Stock ArgyllCMS chartread's reads are counted, in patches (4.3.5 beta 7).

Found driving the real Measure tab through the engine's fallback: stock
chartread fed nothing into the patch count, so a fresh chart read whole ended
on "All strips are read, but 390 patches are not" instead of "All Strips
Read", the progress stayed at 0.0 %, and the ending window said "You have read
25 patches" for 25 strips. Stock chartread says only "Strip read OK" after the
menu that named the strip, and it always reads a strip whole (a strip read
again on a -r resume too), so the strip's locations in the .ti2 are what it
read.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest
from PyQt6.QtCore import QCoreApplication

from workflow.measure_manager import MeasureManager, MeasureParams


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QCoreApplication.instance() or QCoreApplication(sys.argv)


STRIPS = "ABC"
PER = 4


def _ti2(folder: Path) -> Path:
    rows = []
    n = 0
    for s in STRIPS:
        for p in range(1, PER + 1):
            n += 1
            rows.append(f'{n} "{s}{p}" 50.0 50.0 50.0 20.0 21.0 22.0')
    p = folder / "chart.ti2"
    p.write_text(
        'CTI2\n\nDESCRIPTOR "Argyll Calibration Target chart information 2"\n'
        'ORIGINATOR "test"\nCOLOR_REP "iRGB"\n'
        f'STEPS_IN_PASS "{PER}"\nPASSES_IN_STRIPS2 "{len(STRIPS)}"\n'
        'STRIP_INDEX_PATTERN "A-Z, A-Z"\n'
        'PATCH_INDEX_PATTERN "0-9,@-9,@-9;1-999"\n'
        'INDEX_ORDER "STRIP_THEN_PATCH"\n\n'
        'NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
        'SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n'
        f'END_DATA_FORMAT\n\nNUMBER_OF_SETS {n}\nBEGIN_DATA\n'
        + "\n".join(rows) + "\nEND_DATA\n", encoding="latin-1")
    return p


def _ti3(folder: Path, locs) -> Path:
    rows = [f'{i + 1} "{loc}" 50.0 50.0 50.0 20.0 21.0 22.0'
            for i, loc in enumerate(locs)]
    p = folder / "chart.ti3"
    p.write_text(
        'CTI3\n\nDESCRIPTOR "Argyll Calibration Target chart information 3"\n'
        'DEVICE_CLASS "OUTPUT"\nCOLOR_REP "RGB_XYZ"\n\n'
        'NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
        'SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n'
        f'END_DATA_FORMAT\n\nNUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n'
        + "\n".join(rows) + "\nEND_DATA\n", encoding="latin-1")
    return p


class _Runner:
    def __init__(self):
        self.runs = []

    def run(self, tool, args, cwd, on_line=None, on_finish=None, use_pty=False):
        self.runs.append(dict(tool=str(tool), args=list(args), on_line=on_line,
                              on_finish=on_finish))

    def write_stdin(self, text):
        pass

    def abort(self):
        pass


def _stock(tmp_path, *, resume=False, patch_by_patch=False):
    ti2 = _ti2(tmp_path)
    runner = _Runner()
    mgr = MeasureManager(runner)
    mgr._guided_state = "disabled"
    strips, patches = [], []
    mgr.stock_strip_read.connect(strips.append)
    mgr.stock_patch_read.connect(patches.append)
    mgr.start(MeasureParams(ti1_path=ti2.with_suffix(".ti1"), resume=resume,
                            patch_by_patch=patch_by_patch),
              lambda _l: None, lambda _c: None)
    assert runner.runs[-1]["tool"] == "chartread"
    feed = runner.runs[-1]["on_line"]
    return mgr, feed, strips, patches


def _menu(strip, done=False):
    return f"Ready to read strip pass {strip}" + (
        " (!! ALL ROWS READ !!)" if done else "")


def test_a_strip_read_counts_every_patch_of_that_strip(tmp_path):
    mgr, feed, strips, _ = _stock(tmp_path)
    feed(_menu("A"))
    feed(" Strip read OK")
    assert [s["strip"] for s in strips] == ["A"]
    assert [p["loc"] for p in strips[0]["patches"]] == ["A1", "A2", "A3", "A4"]
    assert mgr.readings_this_session == PER, "patches, not strips"


def test_the_wrong_strip_warning_does_not_move_the_strip(tmp_path):
    """chartread files a reading kept after "Seem to have read strip pass B
    rather than A" as A (chartread.c 1854-1875)."""
    mgr, feed, strips, _ = _stock(tmp_path)
    feed(_menu("A"))
    feed("(Warning) Seem to have read strip pass B rather than A!")
    feed(" Strip read OK")
    assert strips[0]["strip"] == "A"


def test_a_fresh_chart_read_whole_is_news_and_complete(tmp_path):
    mgr, feed, strips, _ = _stock(tmp_path)
    for s in STRIPS:
        feed(_menu(s))
        feed(" Strip read OK")
    seen = {p["loc"] for ev in strips for p in ev["patches"]}
    assert len(seen) == len(STRIPS) * PER
    assert mgr.patches_left_is_news()
    assert mgr.readings_this_session == len(STRIPS) * PER


def test_a_resume_whose_strips_all_counted_as_read_waits_for_the_whole_chart(
        tmp_path):
    """-r on a file missing single patches (B3): chartread counts every strip
    as read (its first patch is), so one strip read again is no news yet."""
    _ti3(tmp_path, [f"{s}{p}" for s in STRIPS for p in range(1, PER + 1)
                    if f"{s}{p}" != "B3"])
    mgr, feed, strips, _ = _stock(tmp_path, resume=True)
    feed(_menu("A"))
    feed(" Strip read OK")
    assert not mgr.patches_left_is_news()
    for s in "BC":
        feed(_menu(s))
        feed(" Strip read OK")
    assert mgr.patches_left_is_news()


def test_a_resume_with_a_strip_unread_is_news_when_it_is_read(tmp_path):
    _ti3(tmp_path, [f"{s}{p}" for s in "AB" for p in range(1, PER + 1)])
    mgr, feed, strips, _ = _stock(tmp_path, resume=True)
    assert mgr.patches_left_is_news()
    feed(_menu("C"))
    feed(" Strip read OK")
    assert [p["loc"] for p in strips[0]["patches"]] == ["C1", "C2", "C3", "C4"]


def test_patch_by_patch_counts_the_patch_it_named(tmp_path):
    mgr, feed, strips, patches = _stock(tmp_path, patch_by_patch=True)
    feed("Ready to read patch '6' at 'B2'")
    feed(" Patch read OK")
    assert patches == [{"loc": "B2"}] and not strips
    assert mgr.readings_this_session == 1


def test_the_measure_tab_counts_them_as_progress():
    from ui.tabs import tab_measure
    src = inspect.getsource(tab_measure)
    assert "stock_strip_read.connect(self._count_strip_progress)" in src
    assert "stock_patch_read.connect(self._count_patch_progress)" in src


def test_fill_up_squares_are_not_counted_as_patches_read(tmp_path):
    """printtarg's fill-up rows carry SAMPLE_ID 0; they are read with their
    strip but are no patch of the design, as the progress and "still have no
    reading" already treat them."""
    ti2 = _ti2(tmp_path)
    text = ti2.read_text(encoding="latin-1").replace(
        f"NUMBER_OF_SETS {len(STRIPS) * PER}",
        f"NUMBER_OF_SETS {len(STRIPS) * PER + 1}").replace(
        "\nEND_DATA\n", '\n0 "C5" 50.0 50.0 50.0 20.0 21.0 22.0\nEND_DATA\n')
    ti2.write_text(text, encoding="latin-1")
    runner = _Runner()
    mgr = MeasureManager(runner)
    mgr._guided_state = "disabled"
    mgr.start(MeasureParams(ti1_path=ti2.with_suffix(".ti1")),
              lambda _l: None, lambda _c: None)
    feed = runner.runs[-1]["on_line"]
    feed(_menu("C"))
    feed(" Strip read OK")
    assert mgr.readings_this_session == PER


_UNEXPECTED = ("There is at least one patch with an very unexpected response! "
               "(DeltaE 123.400000)")


def test_a_strip_kept_after_the_unexpected_response_question_counts(tmp_path):
    """chartread.c 1885-1900: Return at "very unexpected response" keeps the
    strip and breaks out WITHOUT printing " Strip read OK". Found driving the
    Measure tab on screen (review of beta 7): one strip kept that way left
    "16 patches still have no reading" on a chart read whole, and the ending
    window said 374 patches for 390."""
    mgr, feed, strips, _ = _stock(tmp_path)
    feed(_menu("A"))
    feed(_UNEXPECTED)
    feed("Hit Return to use it anyway, any other key to retry, Esc or  'q' to give up:")
    feed(_menu("B"))                     # kept: on to the next unread strip
    assert [s["strip"] for s in strips] == ["A"]
    assert mgr.readings_this_session == PER
    assert mgr.has_unsaved_readings


def test_a_retry_after_the_unexpected_response_question_counts_nothing(tmp_path):
    """Any other key retries: chartread prints the same menu again."""
    mgr, feed, strips, _ = _stock(tmp_path)
    feed(_menu("A"))
    feed(_UNEXPECTED)
    feed(_menu("A"))
    assert strips == [] and mgr.readings_this_session == 0
    feed(" Strip read OK")               # the retry is read normally
    feed(_menu("B"))
    assert [s["strip"] for s in strips] == ["A"]
    assert mgr.readings_this_session == PER


def test_the_last_strip_kept_after_the_question_completes_the_chart(tmp_path):
    """No unread strip left: chartread stays on it, now marked ALL ROWS READ,
    and the count is in before that line raises "all done"."""
    mgr, feed, strips, _ = _stock(tmp_path)
    for s in "AB":
        feed(_menu(s))
        feed(" Strip read OK")
    done = []
    mgr.all_stripes_done.connect(lambda: done.append(len(strips)))
    feed(_menu("C"))
    feed(_UNEXPECTED)
    feed(_menu("C", done=True))
    assert [s["strip"] for s in strips] == ["A", "B", "C"]
    assert done == [3], "counted before the completion is announced"

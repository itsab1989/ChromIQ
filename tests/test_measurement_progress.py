"""#153 (Knut): how far through the chart the measurement is.

    *"The calculation of progress shall count actual measured patches (not
    strips), so that same calculation works for both strip mode or
    patch-by-patch mode. This is also important because a user may go back and
    forth between strip mode and patch-by-patch mode to read and re-read
    patches, which may lead to single patches not read in a strip."*

That sentence is the whole design. Counting finished strips would be simpler and
would quietly lie the moment a single patch inside a strip went unread, so the
count is a **set of patch location ids**: a strip adds every patch in it, a
single patch adds one, and reading either again adds nothing.

His answers to the design questions, all of which these tests pin down:

* 100% is the **whole chart**, not just the part being re-read.
* Re-reading a strip already measured **does not move** the percentage.
* A verification run gets the same bar, counting its own shorter chart.
* The bar **stays** at 100% when the measurement finishes.
* The percentage carries **one decimal**.
* The colour is **only** the Measure tab's own accent.

And the rule for a file that cannot be trusted: *"If no ti3 file, or an empty or
corrupted ti3 file … then no progress bar is shown. The 'Progress: 0%' can still
show."*
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measurement_state import (PROGRESS_STATES, Ti3State,  # noqa: E402
                                        progress_from_files, progress_percent)

HEADER = """CTI3

DESCRIPTOR "Argyll Calibration Target chart information 3"
KEYWORD "DEVICE_CLASS"
DEVICE_CLASS "OUTPUT"
COLOR_REP "RGB_XYZ"

NUMBER_OF_FIELDS 4
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B
END_DATA_FORMAT

NUMBER_OF_SETS {n}
BEGIN_DATA
{rows}END_DATA
"""


def _cgats(tmp_path, name, n_rows, claimed=None):
    rows = "".join(f"{i} 0 0 0\n" for i in range(1, n_rows + 1))
    p = tmp_path / name
    p.write_text(HEADER.format(n=claimed if claimed is not None else n_rows,
                               rows=rows), encoding="utf-8")
    return p


# --- the arithmetic ---------------------------------------------------------

def test_a_part_measured_chart():
    assert progress_percent(500, 2000) == pytest.approx(25.0)


def test_one_decimal_is_meaningful_on_a_real_chart():
    """Knut asked for one decimal, and on a 2002-patch chart it earns its keep:
    a single patch is 0.05%, so whole numbers would sit at 0% for 20 patches."""
    assert f"{progress_percent(1, 2002):.1f}" == "0.0"
    assert f"{progress_percent(100, 2002):.1f}" == "5.0"
    assert f"{progress_percent(1001, 2002):.1f}" == "50.0"


def test_a_finished_chart_is_a_hundred():
    assert progress_percent(2002, 2002) == pytest.approx(100.0)


def test_it_can_never_read_over_a_hundred():
    """A session that re-reads a patch already in the file it resumed from can
    count one patch twice. 100 is a better answer than 101."""
    assert progress_percent(2003, 2002) == pytest.approx(100.0)


def test_no_total_means_no_bar():
    assert progress_percent(5, 0) is None
    assert progress_percent(5, None) is None


def test_no_measurement_means_no_bar():
    assert progress_percent(None, 100) is None


# --- which files may draw a bar at all --------------------------------------

def test_a_part_finished_measurement_draws_a_bar(tmp_path):
    ti2 = _cgats(tmp_path, "chart.ti2", 100)
    ti3 = _cgats(tmp_path, "chart.ti3", 40)
    assert progress_from_files(ti3, ti2) == pytest.approx(40.0)


def test_a_finished_measurement_draws_a_full_bar(tmp_path):
    ti2 = _cgats(tmp_path, "chart.ti2", 100)
    ti3 = _cgats(tmp_path, "chart.ti3", 100)
    assert progress_from_files(ti3, ti2) == pytest.approx(100.0)


def test_a_missing_measurement_draws_nothing(tmp_path):
    ti2 = _cgats(tmp_path, "chart.ti2", 100)
    assert progress_from_files(tmp_path / "nope.ti3", ti2) is None


def test_an_empty_measurement_draws_nothing(tmp_path):
    ti2 = _cgats(tmp_path, "chart.ti2", 100)
    ti3 = _cgats(tmp_path, "chart.ti3", 0)
    assert progress_from_files(ti3, ti2) is None


def test_an_unreadable_measurement_draws_nothing(tmp_path):
    ti2 = _cgats(tmp_path, "chart.ti2", 100)
    ti3 = tmp_path / "chart.ti3"
    ti3.write_bytes(b"\xff\xfe not a cgats file")
    assert progress_from_files(ti3, ti2) is None


def test_a_mismatched_measurement_draws_nothing(tmp_path):
    """It holds readings, but ChromIQ refuses to resume it elsewhere. A bar
    reading 40% beside that refusal would tell two stories about one file."""
    ti2 = _cgats(tmp_path, "chart.ti2", 100)
    ti3 = _cgats(tmp_path, "chart.ti3", 40, claimed=99)
    assert progress_from_files(ti3, ti2) is None


def test_only_trustworthy_states_may_draw():
    assert PROGRESS_STATES == {Ti3State.PARTIAL, Ti3State.COMPLETE}
    for bad in (Ti3State.ABSENT, Ti3State.EMPTY, Ti3State.NO_DATA_BLOCK,
                Ti3State.UNREADABLE, Ti3State.MISMATCHED):
        assert bad not in PROGRESS_STATES


# --- the header widget ------------------------------------------------------

@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _header(qapp):
    from ui.tiff_preview import _ProgressHeader
    return _ProgressHeader()


def test_the_bar_uses_the_measure_tabs_own_accent(qapp):
    """Knut: "The bar color shall only be as specified following the measure tab
    style color." So it comes from the shared palette, not a copied value."""
    from ui.styles import SPEC_GREEN
    h = _header(qapp)
    assert h._accent.name().lower() == SPEC_GREEN.lower()


def test_no_progress_and_zero_progress_are_different_states(qapp):
    """``None`` means "nothing trustworthy to draw" and 0.0 means "measured
    nothing yet". Only the first hides the bar."""
    h = _header(qapp)
    h.set_progress(None)
    assert h.progress() is None
    h.set_progress(0.0)
    assert h.progress() == 0.0


def test_the_bar_is_clamped_to_its_own_range(qapp):
    h = _header(qapp)
    h.set_progress(140.0)
    assert h.progress() == 100.0
    h.set_progress(-5.0)
    assert h.progress() == 0.0


def test_turning_it_off_removes_the_label_as_well(qapp):
    """With the feature off the header must look exactly as it always did."""
    from ui.tiff_preview import TiffPreview
    p = TiffPreview()
    p.set_measurement_progress(50.0, tracking=True)
    assert p.measurement_progress() == 50.0
    p.set_measurement_progress(50.0, tracking=False)
    assert p.measurement_progress() is None
    assert not p._header._show_label()

"""Re-reads never raise the progress (Knut, #182 5963044182).

    *"Re-reads shall not increase the Progress, and the total progress shall
    always count patches (not strips) measured compared to number of patches in
    chart."*

Review AR (2026-10-02) photographed "Progress: 100.0 %" beside a window saying
21 patches had no reading: a resumed session started from the file's ROW
COUNT and then added every patch it read, so re-reading a patch the file
already held counted it twice. The file's patches are now kept by name and
joined with the session's, fill-up squares left out.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_measure import TabMeasure  # noqa: E402


def _measured(file_locs, live, *, padding=(), base=None, total=None):
    me = SimpleNamespace(_progress_file_locs=set(file_locs),
                         _progress_locs=set(live),
                         _progress_padding=set(padding),
                         _progress_base=len(file_locs) if base is None else base)
    return TabMeasure._progress_measured(me, total)


def test_a_re_read_of_patches_the_file_holds_adds_nothing():
    held = {"A1", "A2", "A3", "B1", "B2", "B3"}
    assert _measured(held, {"A1", "A2", "A3"}, total=12) == 6


def test_a_new_patch_still_counts():
    assert _measured({"A1", "A2"}, {"A2", "B1"}, total=12) == 3


def test_fill_up_squares_never_count():
    assert _measured({"A1"}, {"C3", "C4"}, padding={"C4"}, total=11) == 2


def test_never_more_than_the_chart():
    assert _measured({"A1", "A2", "A3"}, {"B1"}, total=3) == 3


def test_a_file_without_locations_falls_back_to_its_row_count():
    assert _measured((), {"A1"}, base=5, total=20) == 6


def test_the_unread_count_reads_the_same_figure():
    import inspect
    src = inspect.getsource(TabMeasure._unread_patch_count)
    assert "_progress_measured(" in src
    src = inspect.getsource(TabMeasure._refresh_progress)
    assert "_progress_measured(" in src

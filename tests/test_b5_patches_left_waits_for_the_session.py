"""4.3.5 beta 5 regression review, fix 2: M-ALL-STRIPS-PATCHES-LEFT opened as
soon as one strip was read on a resume whose every strip already counted as
read, and its headline "Some patches are still unread" was one word from the
approved navigation question "Some patches are still not read" (identical in
French and Dutch).
"""
from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---- 2. M-ALL-STRIPS-PATCHES-LEFT: when, and under which headline --------
class _M:
    from workflow.measure_manager import MeasureManager as _MM
    patches_left_is_news = _MM.patches_left_is_news
    _read_the_whole_chart_this_session = _MM._read_the_whole_chart_this_session

    def __init__(self, all_read_at_start, read_now):
        self._strips_all_read_at_start = all_read_at_start
        self._session_strips = [{"strip": s} for s in "ABCD"]
        self._strips_read_this_session = set(read_now)


def test_not_news_after_one_strip_of_a_resume_whose_strips_were_all_read():
    assert _M(True, ["A"]).patches_left_is_news() is False
    assert _M(True, list("ABCD")).patches_left_is_news() is True


def test_still_news_when_the_last_unread_strip_is_read():
    assert _M(False, ["D"]).patches_left_is_news() is True


def test_the_start_records_whether_every_strip_was_read():
    from workflow.measure_manager import MeasureManager
    src = inspect.getsource(MeasureManager._handle_engine_line)
    assert "self._strips_all_read_at_start = bool(strips) and all(" in src


def test_the_tab_asks_before_it_opens_the_window():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_all_stripes_done)
    i = src.index("patches_left_is_news")
    assert i < src.index("self._patches_left_n = unread")
    assert i < src.index("self._all_done_shown = True")


def test_the_headline_is_not_the_navigation_questions_in_any_language():
    from workflow import measurement_messages as M
    ours = (M.M_ALL_STRIPS_PATCHES_LEFT.title, M.M_ALL_STRIPS_PATCHES_LEFT.title_one)
    theirs = {M.M_UNREAD_NEXT_OR_JUMP_STRIP.title,
              M.M_UNREAD_NEXT_OR_JUMP_STRIP.title_one,
              M.M_UNREAD_NEXT_OR_JUMP_PATCH.title,
              M.M_UNREAD_NEXT_OR_JUMP_PATCH.title_one}
    assert not set(ours) & theirs
    root = Path(__file__).resolve().parent.parent / "data" / "i18n"
    for f in sorted(root.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        mine = {d.get(k) for k in ours} - {None}
        other = {d.get(k) for k in theirs} - {None}
        assert len(mine) == 2 and not mine & other, f.name


def test_the_navigation_question_does_not_come_before_the_window():
    """On screen (left_new): reading the last unread strip raised "Some
    patches are still not read" and then this window, back to back. The
    manager hears the chart is closed only once this window is answered."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_all_stripes_done)
    unread = src[src.index("self._patches_left_n = unread") - 1600:
                 src.index("self._patches_left_n = unread")]
    assert "self._note_completion_to_manager()" not in unread.split(
        "self._all_done_shown = True")[-1]
    show = inspect.getsource(TabMeasure._show_patches_left)
    assert show.index("self._exec_measurement_window(box)") < \
        show.rindex("self._note_completion_to_manager()")

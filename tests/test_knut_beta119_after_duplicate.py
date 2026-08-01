"""#130 (Knut, testing beta.118, 2026-08-01): what happens straight after a
Duplicate.

Three things, all about the moment the copy becomes the run you are in.

1. The window that appeared was the one written for **a chart loaded from
   somewhere else**::

       "Nothing you built before is lost: any chart you'd generated earlier is
        still safe in its own project folder under ~/ChromIQ, and you can open
        it again any time from Print or Measure."

   *"Why mention safe in its own project folder, or that ti2 file can be opened
   again from Print or Measure?? First, Duplicate action was performed, so we
   are still inside the same open project."* Every reassurance in it answers a
   worry a duplicate does not raise.

2. Its last paragraph explained building a new chart from these settings, which
   *"sounds like creating a verification run chart, without mentioning that it
   is, and that run type must be set correctly to do so."*

3. *"the 'Run type' must start in 'Profiling', not in Verification."*
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.main_window import MainWindow                    # noqa: E402
from ui.tabs.tab_chart import TabChart                    # noqa: E402


def _src(fn):
    return inspect.getsource(fn)


# ---- the duplicate gets its own words ------------------------------------
def test_the_generic_loaded_chart_notice_is_suppressed():
    src = _src(MainWindow._on_run_duplicated)
    assert "_suppress_reflect_notice" in src
    assert "finally" in src, \
        "the flag must be cleared even if reflecting the chart raises"


def test_the_reflect_notice_honours_the_flag():
    src = _src(TabChart._maybe_warn_reflected_backfill)
    assert "_suppress_reflect_notice" in src


def test_the_duplicate_window_does_not_reassure_about_another_project():
    """The exact sentences he objected to must not be in the new window.

    The docstring quotes them (that is the record of why), so only the code
    below it is checked — otherwise this passes or fails on the comment.
    """
    src = _src(TabChart.announce_duplicated_run)
    body = src.split('"""', 2)[2]
    for phrase in ("safe in its own project folder", "~/ChromIQ",
                   "open it again any time from Print or Measure"):
        assert phrase not in body, f"still says: {phrase}"


def test_the_duplicate_window_names_the_two_runs():
    """"run 5 is a copy of run 3" is the one fact the window exists to give."""
    src = _src(TabChart.announce_duplicated_run)
    assert "{run}" in src and "{source}" in src
    assert "has not changed" in src, \
        "the source run being untouched is the whole promise of Duplicate"


def test_the_verification_route_is_named_properly():
    """His point 2: the paragraph described making a verification chart without
    saying so, or saying that Run type has to be set first."""
    src = _src(TabChart.announce_duplicated_run)
    assert "Run" in src and "Verification" in src
    assert "verification chart" in src
    assert src.index("Run") < src.index("then create the chart"), \
        "the Run type step has to come before the instruction to create it"


def test_the_window_can_be_turned_off():
    src = _src(TabChart.announce_duplicated_run)
    assert "duplicate_notice_hide" in src
    assert "Don't show this again" in src


# ---- run type ------------------------------------------------------------
def test_the_run_type_is_forced_to_profiling():
    """A duplicate is a profiling run. Reasserted AFTER the tabs have loaded,
    because showing the chart runs through paths that can put the bar back."""
    src = _src(MainWindow._on_run_duplicated)
    assert "set_run_type(RUN_TYPE_PROFILING)" in src
    assert (src.index("set_ti1_path") < src.index("set_run_type(RUN_TYPE_PROFILING)")), \
        "setting it before the tabs load leaves it to be overwritten"


def test_the_bar_is_refreshed_after_the_run_type_is_set():
    src = _src(MainWindow._on_run_duplicated)
    assert (src.index("set_run_type(RUN_TYPE_PROFILING)")
            < src.index("_target_bar.refresh()")), \
        "refreshing first would paint the old run type"


# ---- the help card row he looked in --------------------------------------
def test_the_main_actions_card_answers_duplicate_a_run():
    """Knut looked in "Overview of main actions" and found a row about charts
    only. That row is where anyone looks for "duplicate"."""
    from ui.main_actions import main_actions_html
    html = main_actions_html()
    assert "Duplicate a run" in html, \
        "the Duplicate row must mention runs, not only charts"
    assert "run bar" in html
    assert "untouched" in html

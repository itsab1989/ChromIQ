"""#156 (Knut): four faults found in one measurement session.

His closing remark is the reason several of these tests assert *behaviour*
rather than wiring:

    "You must ALWAYS make sure to retain already fixed problems and not
    introduce new bugs when changing code."

1. "Skip initial calibration" forgot itself after every measurement.
2. 'n' did not advance in patch-by-patch mode.
3. "All Strips Read" appeared at 97.1%, with three patches unread.
4. A refinement's overlay showed only that session's patches.

Bug 3 is the one his own new progress bar caught: 97.1% on screen contradicted
"All Strips Read" beside it.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_measure import TabMeasure                   # noqa: E402

C_SRC = Path(__file__).resolve().parent.parent / "native" / \
    "chartread_helper" / "chromiq_chartread.c"


# --- 1. the tick is remembered ---------------------------------------------

def test_manual_skip_calibration_is_remembered():
    src = inspect.getsource(TabMeasure._persist_skip_calibration)
    assert "manual2_chartread_nocal" in src


def test_guided_skip_calibration_is_never_remembered():
    """THE regression this fix must not cause.

    Guided builds the control and hides it outright. A remembered
    ``measure_no_cal`` once ran every guided measurement uncalibrated, with
    nothing on screen to say so and every patch rejected as inconsistent
    (beta.148). A control the user cannot see must never carry a stored value.
    """
    src = inspect.getsource(TabMeasure._persist_skip_calibration)
    assert "measure_no_cal" not in src, (
        "the hidden Guided box must not persist — this would rebuild the "
        "beta.148 uncalibrated-measurement bug")


def test_it_does_not_write_back_during_a_settings_load():
    """A load that triggered a save would store what it had just restored."""
    src = inspect.getsource(TabMeasure._persist_skip_calibration)
    assert "_loading_measure_settings" in src


# --- 2. 'n' moves ----------------------------------------------------------

def test_next_unread_starts_after_the_current_patch():
    """In patch-by-patch mode you always sit on a patch you have not read, so a
    scan starting on the current one matched where you already were."""
    src = C_SRC.read_text()
    block = src[src.index("} else if (incflag == 3)"):]
    block = block[:block.index("} else if (incflag == 4)")]
    assert "#156" in block, "the reason must stay with the code"
    body = block[block.index("*/"):]
    assert "pix++;" in body.split("for (;;)")[0], (
        "the search must advance past the current patch before looking")


def test_the_wrap_and_termination_survive():
    """It must still stop when the current patch is the only unread one left."""
    src = C_SRC.read_text()
    block = src[src.index("} else if (incflag == 3)"):]
    block = block[:block.index("} else if (incflag == 4)")]
    assert "if (pix == opix)" in block


# --- 3. all PATCHES, not all strips ----------------------------------------

def test_the_completion_window_is_gated_on_patches():
    src = inspect.getsource(TabMeasure._on_all_stripes_done)
    assert "_unread_patch_count" in src, (
        "'All Strips Read' must not appear while patches are unread — #156")


def test_an_unknown_total_never_claims_completion():
    """``None`` is not zero: if the chart's patch count cannot be read, no
    completion claim may be made from a guess."""
    src = inspect.getsource(TabMeasure._unread_patch_count)
    assert "return None" in src


def test_a_partly_read_chart_says_nothing_in_a_window():
    """The fix is to STOP showing the finished message, not to invent a
    replacement for it.

    Knut, #155: *"You are inventing new messages and new functions at your own
    initiative, which is NOT allowed for an app that is released for users."* A
    new window needs new wording, and measurement wording goes to §M-PROPOSED
    for approval before it reaches a tab. Until that text exists, the tab says
    its piece in the log.
    """
    src = inspect.getsource(TabMeasure._on_all_stripes_done)
    assert "_log.appendPlainText" in src
    assert not hasattr(TabMeasure, "_show_patches_still_unread"), (
        "an unapproved measurement window came back")


def test_the_unread_note_counts_in_words_not_brackets():
    src = inspect.getsource(TabMeasure._on_all_stripes_done)
    assert "(s)" not in src
    assert "1 patch still has" in src and "patches still have" in src


def test_patch_locations_are_tracked_even_with_the_bar_switched_off():
    """#153's switch turns off the percentage, not the record of which patches
    have a reading — #156's completion check depends on that record."""
    for name in ("_count_strip_progress", "_count_patch_progress"):
        src = inspect.getsource(getattr(TabMeasure, name))
        assert "_progress_enabled" not in src, name


# --- 4. the overlay shows everything measured ------------------------------

def test_a_refinement_seeds_the_overlay_from_the_existing_measurement():
    """Knut: "When starting a measurement ALL previously measured patches shall
    ALWAYS be shown, so that user knows where to measure if patches are
    missing." """
    src = inspect.getsource(TabMeasure._start_measurement) \
        if hasattr(TabMeasure, "_start_measurement") else ""
    if not src:
        import ui.tabs.tab_measure as tm
        src = inspect.getsource(tm)
    assert "_show_overlay_from_existing_ti3()" in src


def test_a_fresh_read_still_clears_the_overlay():
    """The opposite case must survive: a read that REPLACES the measurement
    should not leave the old one on screen describing a file on its way to
    old/."""
    import ui.tabs.tab_measure as tm
    src = inspect.getsource(tm)
    assert "if not self._read_builds_on_existing():" in src
    assert "self._clear_overlay()" in src


# --- the advice must be true at any scale ----------------------------------

def test_the_progress_preference_reaches_the_tab():
    """#153 follow-up, Knut: switching the bar off in Preferences left it on
    screen. Preferences pushes changes at the tabs, so a new option that is not
    pushed never arrives."""
    import inspect as _i
    from ui import main_window as mw
    assert "refresh_progress_setting" in _i.getsource(mw)
    assert hasattr(TabMeasure, "refresh_progress_setting")

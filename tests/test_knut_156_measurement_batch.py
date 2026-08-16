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

def test_start_measurement_writes_the_targets_settings():
    """THE FIX, and the actual cause of Knut's report (#156).

    `per_target_settings.md` §3 lists every moment a tab's settings are written,
    and **W8** is *"Start Measurement / Continue Measurement pressed → the
    Measure tab's settings"*. Every other event in that table was wired — W6
    (leaving a tab, changing target) through MainWindow, W1 (Generate Chart) on
    the Create Chart tab — and W8 was not. So the Measure tab was the one place
    where pressing the tab's own main button did not record what it was pressed
    with, and the next load put back the last value that had been stored.

    That is why the tick vanished: *"No matter if I start measurement in
    patch-by-patch or strip mode, when I stop the measurement, the checkmark is
    unticked. this also applies to other settings."* It was never one control —
    it was every control on the panel.
    """
    src = inspect.getsource(TabMeasure._on_start)
    assert "save_target_settings()" in src, (
        "Start Measurement does not write this target's settings (§3 W8)")


def test_it_is_written_before_the_reader_launches():
    """So what is stored is what the measurement actually ran with, not what the
    panel looked like after it finished."""
    src = inspect.getsource(TabMeasure._on_start)
    assert src.index("save_target_settings()") < src.index(
        "self._set_settings_enabled(False)")


def test_the_setting_is_not_kept_in_a_global_preference():
    """`per_target_settings.md` §0 names this shape as the fault itself: *"a
    global parameter … where several actors can change that parameter, but not
    know when or where."*

    A global write also leaks in the direction hardest to notice — it is what a
    target with nothing stored opens on, so ticking the box on one run would
    change what a brand-new run starts with.
    """
    src = inspect.getsource(TabMeasure._persist_skip_calibration)
    assert "manual2_chartread_nocal" not in src, (
        "back to a single value shared by every run and run type")


def test_guided_skip_calibration_is_never_remembered():
    """THE regression this fix must not cause.

    Guided builds the control and hides it outright. A remembered
    ``measure_no_cal`` once ran every guided measurement uncalibrated, with
    nothing on screen to say so and every patch rejected as inconsistent
    (beta.148). A control the user cannot see must never carry a stored value.
    """
    src = inspect.getsource(TabMeasure._collect_guided)
    assert "disable_initial_cal = False" in src, (
        "Guided must not send the hidden box's value — this would rebuild the "
        "beta.148 uncalibrated-measurement bug")


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

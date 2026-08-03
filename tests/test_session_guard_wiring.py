"""§T2.1, T2.3, T2.6 and T2.7 — the guard is actually wired in.

``docs/design/unified_measurement_management.md`` §2a and §S3. The policy is
tested as arithmetic in ``test_measurement_session.py``; this checks the Measure
tab really starts it before a read and judges it afterwards, because a perfect
guard that nothing calls protects nothing.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_measure import TabMeasure       # noqa: E402


def test_the_guard_starts_before_the_reader_does():
    """§2a: the copy has to be taken while the previous readings still exist.
    A resume overwrites the file it resumed from, so afterwards is too late."""
    src = inspect.getsource(TabMeasure._on_start)
    assert "_begin_session_guard" in src
    i = src.index("_begin_session_guard")
    # …and before the process is launched.
    for later in ("subprocess.run", "start_measurement", "_manager.measure"):
        if later in src:
            assert i < src.index(later), f"the guard must be set up before {later}"


def test_the_guard_is_judged_when_the_measurement_ends():
    whole = inspect.getsource(TabMeasure)
    assert "_finish_session_guard()" in whole


def test_the_verdict_is_reached_before_anything_reads_the_file():
    """A restore has to happen before the report or the resume checkbox looks
    at the measurement, or they describe the file that is about to be replaced."""
    src = inspect.getsource(TabMeasure._on_measure_done)
    i = src.index("_finish_session_guard()")
    for later in ("_finalize_verification", "_update_resume_availability"):
        if later in src:
            assert i < src.index(later), \
                f"{later} must not see the file before the verdict has acted"


def test_both_bad_outcomes_are_reported_on_screen():
    """Knut: *"The user should always be informed on-screen on events, or it
    will seem like hidden information."* A log line is hidden information."""
    src = inspect.getsource(TabMeasure._finish_session_guard)
    assert "M-TI3-EMPTY" in src and "M-TI3-SHRANK" in src
    assert src.count("_say_on_screen") >= 2


def test_a_good_session_says_how_many_were_added():
    src = inspect.getsource(TabMeasure._finish_session_guard)
    assert "out.added" in src
    assert "_flash_status" in src


def test_only_one_outcome_can_apply():
    """§S3: at most one window follows a measurement."""
    src = inspect.getsource(TabMeasure._finish_session_guard)
    assert src.count("elif ") >= 2 and "if out.message_id" in src


def test_the_guard_never_blocks_a_measurement():
    """A safety net that stops the work is worse than none."""
    src = inspect.getsource(TabMeasure._begin_session_guard)
    assert "except Exception" in src
    assert "log.warning" in src


def test_a_chart_outside_a_project_still_gets_a_guard():
    """Not every chart lives in a run; the archive then goes beside the file."""
    src = inspect.getsource(TabMeasure._begin_session_guard)
    assert 'ti3.parent / "old"' in src


def test_resume_is_read_from_whichever_mode_is_showing():
    """The verdict differs for a resume, so getting this wrong turns a normal
    replace into a false "readings went backwards" alarm."""
    src = inspect.getsource(TabMeasure._resume_is_active)
    assert "_resume_cb" in src and "_m_resume_cb" in src
    assert "isVisible()" in src, "a hidden box's state is not the user's choice"

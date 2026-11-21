"""After a stop that ends the sending, the page offers the way on (4.3.47).

The volunteer's 4.3.46 run of 18 Nov 2026 stopped at the aiming place with the arm free. The
Measure tab then showed "ChromIQ has stopped and let go of the table" with NO answer button,
said "you can still save them" with nothing read, and asked him to open i1Profiler while the
job still held the table's USB connection (it lets go only at the session's end). He wrote that
the software was stuck. Driven on screen with the old rule: pictures in the 4.3.47 report.

Here the simulated table's freed arm shifts by more than settling explains, so the same stop
happens under the 4.3.47 rule.
"""
from __future__ import annotations

import pytest

from core.i18n import tr
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.window_sim import WindowSim
from workflow import measurement_messages as M

PUSHED = (-60.0, 70.0)


def _stop_at_the_aiming_place(qtbot, monkeypatch, tmp_path, settings, asking):
    sim = WindowSim(release_settle=PUSHED)
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=asking, sim=sim)
    assert p.drive_until(("stopped", "aimed")) == "stopped"
    return win, sim, p, finished


@pytest.mark.parametrize("asking", [True, False])
def test_the_stopped_page_has_an_answer_and_says_end_first(qtbot, monkeypatch, tmp_path,
                                                           settings, asking):
    win, sim, p, _f = _stop_at_the_aiming_place(qtbot, monkeypatch, tmp_path, settings, asking)
    assert p.labels() == ["End measurement"]          # before 4.3.47: no button at all
    text = win._text.text()
    assert tr("ChromIQ has stopped") == win._title.text()
    assert "Press End measurement. Until you do, ChromIQ still holds the table's USB" in text
    # 4.3.53 fix round (SHOULD-3): the power switch and ChromIQ's own START first,
    # i1Profiler last (until then step 2 was "Then open i1Profiler")
    # 2026-11-21 (the owner: "driving the table should work without involving i1profiler"):
    # End measurement, then START (which brings the arm home), then the power switch; never
    # i1Profiler
    assert text.index("Press End measurement") < text.index("Press START MEASUREMENT") \
        < text.index("switch it off at its power switch")
    assert "i1Profiler" not in text
    assert "more than 5 mm" in text                    # the reason, in plain words
    assert M.M_I1IO_DRIVE_FREE_LEFT.render()[1] in text
    assert "Nothing was measured yet, so there is nothing to save." in text
    assert "you can still save them" not in text
    assert "let go of the table" not in text.split("\n")[0]
    assert "—" not in text


def test_the_page_button_ends_the_session_cleanly_and_the_last_page_says_the_free_arm(
        qtbot, monkeypatch, tmp_path, settings):
    win, sim, p, finished = _stop_at_the_aiming_place(qtbot, monkeypatch, tmp_path, settings,
                                                      True)
    sent = list(sim.sim.received)
    p.press("End measurement")
    assert p.page() == "done", p.win.pages_shown[-4:]
    assert sim.sim.received == sent                    # ending sends nothing to the table
    text = win._text.text()
    assert M.M_I1IO_DRIVE_FREE_LEFT.render()[1] in text
    assert "The arm stayed extended over the table" not in text
    assert p.labels() == ["Close"]
    assert win.job.state().arm_free is True


def test_a_held_arm_left_out_keeps_its_old_last_page_words():
    """The free-arm paragraph replaces the old sentence only when the arm is free (the held
    case is unchanged: no change of meaning beyond the free arm)."""
    import inspect
    import ui.i1io_table_window as W
    src = inspect.getsource(W.TableMeasureWindow._after_close)
    # 4.3.52 review 2, S-1: the held case now gives the power switch first
    assert "M_I1IO_DRIVE_ARM_WAY_OUT_ENDED" in src and "_arm_left_free()" in src


@pytest.mark.parametrize("asking", [True, False])
def test_the_free_arm_paragraph_comes_before_the_steps_and_both_say_should(
        qtbot, monkeypatch, tmp_path, settings, asking):
    """Safety review 4.3.47, SHOULD-1: no recording shows i1Profiler opening a table whose arm
    was left free out on the table, so step 2 says it SHOULD bring the arm home (as the free-arm
    paragraph does), and "leave the arm where it is" comes before the numbered steps."""
    win, sim, p, _f = _stop_at_the_aiming_place(qtbot, monkeypatch, tmp_path, settings, asking)
    text = win._text.text()
    free = M.M_I1IO_DRIVE_FREE_LEFT.render()[1]
    assert text.count(free) == 1
    assert text.index("The arm last reported") < text.index(free) < text.index("What to do now")
    assert text.index(free) < text.index("1. Press End measurement")
    assert "brings the arm home from where it is" in text
    assert "it brings the arm home" not in text
    assert text.index("Please send us the diagnostics file") < text.index(
        "Nothing was measured yet")


def test_without_a_free_arm_the_stopped_page_has_no_free_arm_paragraph():
    title, body = M.M_I1IO_DRIVE_STOPPED_END_FIRST.render(where="X 1, Y 2", log="x.zip",
                                                          free_arm="")
    assert "The arm is still free" not in body
    assert "reported X 1, Y 2.\n\nWhat to do now:" in body
    assert "brings the arm home from where it is" in body

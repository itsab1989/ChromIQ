"""4.3.48 in the Measure tab's table window: the arm home without i1Profiler, where allowed.

* The ready question has a third answer, "The arm is out" (only the bed ticked): ChromIQ connects,
  reads where the arm is, moves nothing, and says whether it can bring the arm home.
* After a stop at the homing's place check (the arm held out in the area), the stopped page offers
  "Bring the arm home" beside "End measurement"; it asks the hands-off GO, sends the usual homing
  and shows "The arm is at its resting place".
* Where no recorded homing starts, or after any other stop, the old advice stays (i1Profiler, the
  power switch) and no such button is shown.
"""
from __future__ import annotations

import pytest

from core.i18n import tr
from tests.i1io_table.test_window import ARGS, open_window, settings  # noqa: F401
from tests.i1io_table.window_sim import WindowSim

OUT_HELD = [0.0, 1600.0]
ALIGN_START = [2507.0, 1429.0]
HOMING = [";s022", ";p025", ";i12b", ";s022", ";f02f", ";f42b", ";f42b", ";p025"]


def _ready_page(qtbot, monkeypatch, tmp_path, settings, pos, asking=True, **simkw):
    sim = WindowSim(pos=list(pos), **simkw)
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sim=sim, asking=asking)
    assert p.drive_until("ready_to_open") == "ready_to_open"
    return win, sim, p


def _press_arm_out(win, p):
    t = win._tick_widgets
    t[1].setChecked(True)
    p.press("The arm is out")


def test_the_arm_out_answer_needs_the_bed_ticked_and_the_arm_not(qtbot, monkeypatch, tmp_path,
                                                                 settings):
    win, sim, p = _ready_page(qtbot, monkeypatch, tmp_path, settings, OUT_HELD)
    out = [b for b in win._buttons if b.text() == tr("The arm is out")][0]
    start = [b for b in win._buttons if b.text() == tr("Start")][0]
    t = win._tick_widgets
    assert not out.isEnabled() and not start.isEnabled()
    t[1].setChecked(True)
    assert out.isEnabled() and not start.isEnabled()
    t[0].setChecked(True)                       # "at its resting place" ticked: not "out"
    assert not out.isEnabled() and start.isEnabled()
    assert "The arm is out" in win._text.text()  # the paragraph that explains it
    assert sim.sim is None or sim.sim.received == []


@pytest.mark.parametrize("asking", [True, False])
def test_start_with_the_arm_out_brings_it_home_and_goes_on(qtbot, monkeypatch, tmp_path,
                                                          settings, asking):
    win, sim, p = _ready_page(qtbot, monkeypatch, tmp_path, settings, OUT_HELD, asking=asking)
    _press_arm_out(win, p)
    assert p.page() == "refused", win.pages_shown[-3:]
    text = win._text.text()
    assert tr("The arm is not at its resting place.") in text
    assert "ChromIQ can bring it home now" in text and "i1Profiler 3.8.6 or older" in text
    assert p.labels() == ["Bring the arm home"]          # no "Carry on" here
    assert sim.sim.received[11:] == [";p025"]            # read once, nothing moved
    p.press("Bring the arm home")
    assert p.page() == "go"
    n = len(sim.sim.received)
    p.press("Go")
    p.idle()
    assert sim.sim.received[n:n + 8] == HOMING
    # the measurement then goes on with the calibration, as at a usual start
    assert p.page() not in ("refused", "stopped"), win.pages_shown[-3:]
    assert sim.sim.violations == []


def test_start_with_the_arm_out_at_the_alignment_start_keeps_the_old_advice(
        qtbot, monkeypatch, tmp_path, settings):
    win, sim, p = _ready_page(qtbot, monkeypatch, tmp_path, settings, ALIGN_START)
    _press_arm_out(win, p)
    text = win._text.text()
    assert "ChromIQ cannot bring it home from there" in text
    assert "open i1Profiler 3.8.6 or older once" in text and "power switch" in text
    assert "Bring the arm home" not in p.labels()
    assert p.labels() == ["End measurement"]
    assert not [ln for ln in sim.sim.received if ln[1:3] in ("m0", "m1", "m2", "i1", "i0")]


def test_start_with_the_arm_out_on_a_cold_table_sends_no_start_up(qtbot, monkeypatch, tmp_path,
                                                                  settings):
    win, sim, p = _ready_page(qtbot, monkeypatch, tmp_path, settings, OUT_HELD, cold=True)
    _press_arm_out(win, p)
    assert p.page() == "refused"
    assert "never been recorded with the arm out over the table" in win._text.text()
    assert p.labels() == ["Close"]
    assert ";i02c" not in sim.sim.received


def _stopped_at_the_homing(qtbot, monkeypatch, tmp_path, settings, pos):
    sim = WindowSim(pos=list(pos))
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sim=sim, args=ARGS + ["-N"])
    assert p.drive_until(("stopped",)) == "stopped", win.pages_shown[-4:]
    return win, sim, p


def test_the_stopped_page_offers_the_homing_after_a_place_check(qtbot, monkeypatch, tmp_path,
                                                                settings):
    win, sim, p = _stopped_at_the_homing(qtbot, monkeypatch, tmp_path, settings, OUT_HELD)
    assert win._title.text() == tr("ChromIQ has stopped, and can bring the arm home")
    text = win._text.text()
    assert "press End measurement, then open i1Profiler 3.8.6 or older once" in text
    assert "power switch" in text and "—" not in text
    assert p.labels() == ["Bring the arm home", "End measurement"]
    p.press("Bring the arm home")
    assert p.page() == "go"
    n = len(sim.sim.received)
    p.press("Go")
    assert p.page() == "home_after_stop_done", win.pages_shown[-3:]
    assert sim.sim.received[n:] == HOMING
    assert win._title.text() == tr("The arm is at its resting place")
    assert p.labels() == ["End measurement"]
    p.press("End measurement")
    assert sim.sim.received[n:] == HOMING                 # nothing more was sent


def test_the_stopped_page_at_the_alignment_start_has_no_homing(qtbot, monkeypatch, tmp_path,
                                                               settings):
    win, sim, p = _stopped_at_the_homing(qtbot, monkeypatch, tmp_path, settings, ALIGN_START)
    assert "Bring the arm home" not in p.labels()
    text = win._text.text()
    assert "This stop is not one of those" in text
    assert "open i1Profiler 3.8.6 or older once" in text

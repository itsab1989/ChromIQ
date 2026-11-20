"""4.3.48 in the Measure tab's table window: the arm home without i1Profiler, where allowed.

* The ready question has a third answer, "The arm is out" (only the bed ticked): ChromIQ connects,
  reads where the arm is, moves nothing, and says whether it can bring the arm home.
* After a stop at the homing's place check (the arm held out in the area), the stopped page offers
  "Bring the arm home" beside "End measurement"; it asks the hands-off GO, sends the usual homing
  and shows "The arm is at its resting place".
* Where no recorded homing starts, or after any other stop, the old advice stays (i1Profiler, the
  power switch) and no such button is shown.

4.3.52 (the owner's ruling of 2026-11-20, test_4352_start_rule_by_state.py): at a START the arm is
brought home from wherever a held arm stands, after ONE short question (M-I1IO-DRIVE-HOME-AT-
START), with i1Profiler's start homing, and the measurement goes on; the one place nothing is
offered is the back strip beside the white tile's holder. A just-switched-on table gets its
start-up whatever the person answered about the arm.
"""
from __future__ import annotations

import pytest

from core.i18n import tr
from tests.i1io_table.test_window import ARGS, open_window, settings  # noqa: F401
from tests.i1io_table.window_sim import WindowSim

OUT_HELD = [0.0, 1600.0]
BACK_STRIP = [1058.0, 317.0]
#: the START rule's homing (i1Profiler's start homing + the reading at rest)
HOMING = [";s022", ";p025", ";i12b", ";s022", ";p025"]
MOVES = ("m0", "m1", "m2", "i1", "i0")


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
    assert p.page() == "home_at_start", win.pages_shown[-3:]
    text = win._text.text()
    assert tr("The arm is not at its resting place. ChromIQ brings it there now.") in text
    assert "i1Profiler" not in text and "record" not in text
    assert p.labels() == ["Not now", "Bring the arm home, my hands are away"]
    assert sim.sim.received[11:] == [";p025"]            # read once, nothing moved
    n = len(sim.sim.received)
    p.press("Bring the arm home, my hands are away")
    p.idle()
    assert sim.sim.received[n:n + 5] == HOMING
    assert p.page() not in ("refused", "stopped"), win.pages_shown[-3:]
    assert sim.sim.violations == []


def test_start_with_the_arm_out_in_the_back_strip_says_why(qtbot, monkeypatch, tmp_path,
                                                           settings):
    win, sim, p = _ready_page(qtbot, monkeypatch, tmp_path, settings, BACK_STRIP)
    _press_arm_out(win, p)
    text = win._text.text()
    assert "beside the holder of the white tile" in text
    assert "i1Profiler 3.8.6 or older" in text and "power switch" in text
    assert p.labels() == ["End measurement"]
    assert not [ln for ln in sim.sim.received if ln[1:3] in MOVES]


def test_start_with_the_arm_out_on_a_cold_table_starts_it(qtbot, monkeypatch, tmp_path,
                                                          settings):
    win, sim, p = _ready_page(qtbot, monkeypatch, tmp_path, settings, OUT_HELD, cold=True)
    _press_arm_out(win, p)
    assert p.page() == "start_up", win.pages_shown[-3:]
    assert ";i02c" not in sim.sim.received
    p.press(p.labels()[-1] if "Start the table, my hands are away" not in p.labels()
            else "Start the table, my hands are away")
    p.idle()
    assert ";i02c" in sim.sim.received


def _stopped_at_the_homing(qtbot, monkeypatch, tmp_path, settings, pos):
    sim = WindowSim(pos=list(pos))
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sim=sim, args=ARGS + ["-N"])
    page = p.drive_until(("stopped", "home_at_start"))
    if page == "home_at_start":
        p.press("Not now")                              # the person wants to wait
        p.idle()
    assert p.page() == "stopped", win.pages_shown[-4:]
    return win, sim, p


def test_the_stopped_page_offers_the_homing_after_a_place_check(qtbot, monkeypatch, tmp_path,
                                                                settings):
    win, sim, p = _stopped_at_the_homing(qtbot, monkeypatch, tmp_path, settings, OUT_HELD)
    assert win._title.text() == tr("The arm is not at its resting place")
    text = win._text.text()
    assert "ChromIQ can bring it home: press Bring the arm home." in text
    assert "power switch" in text and "—" not in text
    assert p.labels() == ["Bring the arm home", "End measurement"]
    p.press("Bring the arm home")
    assert p.page() == "go"
    n = len(sim.sim.received)
    p.press("Go")
    assert p.page() == "home_after_stop_done", win.pages_shown[-3:]
    assert sim.sim.received[n:] == HOMING
    assert win._title.text() == tr("The arm is at its resting place")
    # 4.3.52: the table is a started table at rest again: the measurement goes on
    assert p.labels() == ["Go on"]


def test_the_stopped_page_in_the_back_strip_has_no_homing(qtbot, monkeypatch, tmp_path,
                                                          settings):
    win, sim, p = _stopped_at_the_homing(qtbot, monkeypatch, tmp_path, settings, BACK_STRIP)
    assert "Bring the arm home" not in p.labels()
    text = win._text.text()
    assert "beside the holder of the white tile" in text
    assert "open i1Profiler once" in text

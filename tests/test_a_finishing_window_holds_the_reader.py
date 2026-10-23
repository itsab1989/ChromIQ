"""Behind "All Strips Read" the reader reads nothing (Basti's ColorMunki hand
test of the end-of-chart pause, 2026-10-23).

His chart had strips A-F, all read but E. He read E, the pause after the last
strip came, he pressed the instrument's button once, and "All Strips Read"
opened. The log showed three things, and the replay engine reproduces all of
them on 4.3.10 and on 4.3.9 (which has no pause at all):

* **the reader went on to strip F**, which was already read: the tab notes
  the completion window as shown from INSIDE the `all_stripes_done` emit, so
  the read that completed the chart was taken for a read after the window,
  and "the next strip after the one you completed" (Knut, #182 5956210745)
  was applied to it. The rule it was meant to leave alone says the reader
  stays put while the completion window is about to open;
* **the engine stayed armed there behind the window**: a press and a slide
  while "All Strips Read" was open read strip F again and replaced its
  reading in the .ti3 (replay, on screen: 4.3.9 and 4.3.10 both);
* **`scan_started` came with nothing scanned**: the i1Pro and ColorMunki
  drivers call `inst_triggered` after their wait loop however it ended, so
  the goto that moved the reader looked like the start of a swipe.

Now the read that completes the chart leaves the reader where it is, the
engine holds at that strip while a window that finishes the measurement is
open (`{"cmd":"hold"}`, a press only reported), the window's "Re-read" lets it
go (`resume`, the same strip offered again), its "Go to ... Tab" / Finish
sends `d` as before, and a wait left by a command reports no `scan_started`.

The engine tests drive the REAL chromiq-chartread through its replay
instrument, which now does what the real drivers do after an abort.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                   # noqa: E402
from PyQt6.QtWidgets import QApplication             # noqa: E402

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, write_replay_script  # noqa: E402

from core.argyll_runner import ArgyllRunner          # noqa: E402
from core.settings import AppSettings                # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "native" / "chartread_helper"

needs_helper = pytest.mark.skipif(not HELPER.exists(),
                                  reason="chromiq-chartread helper not built")


# ---------------------------------------------------------------------------
# the engine
# ---------------------------------------------------------------------------

def _chart(tmp: Path):
    from test_chartread_engine import _make_chart
    base = _make_chart(tmp, randomised=False,
                       targen_args=["-d2", "-G", "-e4", "-B4", "-f90"])
    replay = tmp / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.2)
    return base, replay


def _quit(s):
    from test_chartread_engine import _quit as quit_session
    quit_session(s)


def _events(s, after: int, name: str) -> list:
    with s._lock:
        return [e for e in s.events[after:] if e.get("event") == name]


@needs_helper
def test_the_session_says_the_engine_can_hold_at_a_menu(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        assert s.wait_event("session_start").get("hold_here") is True
        s.wait_event("strip_ready")
        _quit(s)


@needs_helper
def test_a_goto_at_an_armed_strip_is_not_the_start_of_a_scan(tmp_path):
    """The goto that moved Basti's reader to F came out as scan_started."""
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        labels = [x["strip"] for x in s.wait_event("session_start")["strips"]]
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="goto", strip=labels[2])
        s.wait_event("strip_ready", after=i, strip=labels[2])
        time.sleep(0.3)
        assert not _events(s, i, "scan_started"), \
            "a goto at an armed strip was reported as the start of a scan"
        # ...and a real press still is one
        j = s.event_index()
        s.send(cmd="switch")
        s.wait_event("scan_started", after=j)
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=j)
        _quit(s)


@needs_helper
def test_hold_here_reads_nothing_and_a_press_is_only_reported(tmp_path):
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        armed = s.wait_event("strip_ready")["strip"]
        i = s.event_index()
        s.send(cmd="hold")
        held = s.wait_event("held", after=i)
        assert held["strip"] == armed and held.get("here") is True
        assert held["button"] is True          # the replay is an i1Pro
        # the press behind the window: reported, and no scan starts (a slide
        # after it reads nothing on a real instrument; the replay's own
        # swipe command would be kept for the next armed strip, so it is
        # not sent here)
        s.send(cmd="switch")
        s.wait_event("switch", after=i)
        time.sleep(0.6)
        for name in ("scan_started", "strip_read", "strip_ready"):
            assert not _events(s, i, name), f"{name} while the reader holds"
        # Re-read Individual Strips: the same strip is offered again
        j = s.event_index()
        s.send(cmd="resume")
        assert s.wait_event("strip_ready", after=j)["strip"] == armed
        k = s.event_index()
        s.send(cmd="switch")
        s.wait_event("scan_started", after=k)
        s.send(cmd="swipe")
        assert s.wait_event("strip_read", after=k)["strip"] == armed
        _quit(s)


@needs_helper
def test_done_and_goto_from_the_hold_here(tmp_path):
    """The window's own commands end the hold: goto moves (no reading), and
    done is left for the strip menu, which asks about the unread patches."""
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        labels = [x["strip"] for x in s.wait_event("session_start")["strips"]]
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="hold")
        s.wait_event("held", after=i)
        j = s.event_index()
        s.send(cmd="goto", strip=labels[1])
        assert s.wait_event("strip_ready", after=j)["strip"] == labels[1]
        assert not _events(s, j, "scan_started")
        k = s.event_index()
        s.send(cmd="hold")
        s.wait_event("held", after=k)
        s.send(cmd="done")
        s.wait_event("unread_confirm", after=k)
        assert not _events(s, k, "strip_read")
        m = s.event_index()
        s.send(cmd="no")
        s.wait_event("strip_ready", after=m)
        _quit(s)


@needs_helper
def test_a_hold_anywhere_but_an_armed_strip_is_dropped(tmp_path):
    """At the misread prompt a stray hold is not "any other key" (retry)."""
    base, replay = _chart(tmp_path)
    with ReplaySession(base, replay) as s:
        s.wait_event("strip_ready")
        i = s.event_index()
        s.send(cmd="swipe", fault="misread", reason="Too many patches")
        s.wait_event("error", after=i, kind="misread")
        j = s.event_index()
        s.send(cmd="hold")
        time.sleep(0.6)
        assert not _events(s, j, "strip_ready"), "the hold was taken as retry"
        assert not _events(s, j, "held")
        s.send(cmd="retry")
        s.wait_event("strip_ready", after=j)
        _quit(s)


def test_the_hold_here_opens_the_switch_gate_around_its_one_wait():
    text = (SRC / "chromiq_chartread.c").read_text(encoding="utf-8")
    at = text.index("cq_json && ch == 'h'")
    seg = text[at:text.index("cq_json && (ch == 'k'", at)]
    assert '\\"here\\":true' in seg
    assert "cq_switch_gate_set(1);\n\t\t\t\t\t\t\t\thk = cq_hold_wait" in seg
    assert "cq_switch_gate_set(0);" in seg


# ---------------------------------------------------------------------------
# the manager and the Measure tab
# ---------------------------------------------------------------------------

STRIPS = [{"strip": s, "sheet": 1, "read": s != "E", "verifiable": True}
          for s in "ABCDEF"]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path, monkeypatch):
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    t = TabMeasure(ArgyllRunner(s), s)
    mgr = t._manager
    written = []
    monkeypatch.setattr(mgr._runner, "write_stdin",
                        lambda text: written.append(json.loads(text)))
    monkeypatch.setattr(type(mgr._runner), "is_running",
                        property(lambda self: True))
    mgr._engine_active = True
    mgr._engine_holds = True
    mgr._engine_holds_here = True
    mgr._spot_mode = False
    mgr._guided_state = "disabled"
    mgr._session_strips = [dict(x) for x in STRIPS]
    mgr._loc_strip = {f"{s}{i}": s for s in "ABCDEF" for i in (1, 2)}
    mgr._unread_locs = {"E1", "E2"}
    mgr._padding_locs = set()
    mgr._chart_was_complete = False
    mgr._is_resume = True
    mgr._read_something = True
    t._session_live = True
    t._written = written
    shown = []
    monkeypatch.setattr(t, "_show_all_stripes_done",
                        lambda: shown.append(list(written)))
    t._shown = shown
    yield t
    _settle(700)          # the window's timer fires here, on the stub
    t._session_live = False


def _feed(mgr, ev):
    mgr._handle_engine_line(json.dumps(ev), lambda _line: None)


def _settle(ms=600):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.005)


def _read_e_completing_the_chart(tab):
    mgr = tab._manager
    mgr._just_read_strip = "E"
    mgr._unread_locs = set()
    _feed(mgr, {"event": "strip_ready", "strip": "E", "read": True,
                "all_done": True})


def test_the_read_that_completes_the_chart_leaves_the_reader_where_it_is(tab):
    """Basti's log: "strip E read; moving the reader on to strip F"."""
    _read_e_completing_the_chart(tab)
    gotos = [w for w in tab._written if w.get("cmd") == "goto"]
    assert not gotos, f"the reader was moved to an already read strip: {gotos}"


def test_a_read_after_the_window_still_moves_on(tab):
    """Knut, #182 6154440320: after "All Strips Read" and Re-read, a read of
    strip C moves the reader on to D, as before."""
    mgr = tab._manager
    mgr._unread_locs = set()
    mgr.note_completion_shown()
    tab._all_done_shown = True
    mgr._just_read_strip = "C"
    _feed(mgr, {"event": "strip_ready", "strip": "C", "read": True,
                "all_done": True})
    assert {"cmd": "goto", "strip": "D"} in tab._written


def test_the_engine_holds_before_the_window_opens(tab):
    _read_e_completing_the_chart(tab)
    assert tab._written[-1] == {"cmd": "hold"}
    _feed(tab._manager, {"event": "held", "strip": "E", "button": True,
                         "here": True})
    _settle()
    assert tab._shown, "the completion window did not come"
    assert {"cmd": "hold"} in tab._shown[0], "the window opened unheld"


def test_a_press_behind_the_window_does_nothing(tab):
    mgr = tab._manager
    presses = []
    mgr.instrument_button.connect(lambda: presses.append(1))
    _read_e_completing_the_chart(tab)
    _feed(mgr, {"event": "held", "strip": "E", "button": True, "here": True})
    n = len(tab._written)
    _feed(mgr, {"event": "switch"})
    _settle(100)
    assert not presses and len(tab._written) == n
    assert not tab._page_pause_active()


def test_reread_lets_the_engine_go(tab):
    mgr = tab._manager
    _read_e_completing_the_chart(tab)
    _feed(mgr, {"event": "held", "strip": "E", "button": True, "here": True})
    # Re-read Individual Strips: nothing sent from the window
    tab._release_reader_after_window()
    assert tab._written[-1] == {"cmd": "resume"}
    assert mgr._window_hold is None
    # ...once: a second release writes nothing
    n = len(tab._written)
    tab._release_reader_after_window()
    assert len(tab._written) == n


def test_the_windows_own_done_is_never_followed_by_a_resume(tab):
    """The engine keeps ONE waiting command: a resume after "d" would
    replace it, and "Go to Build Profile Tab" would do nothing."""
    mgr = tab._manager
    _read_e_completing_the_chart(tab)
    _feed(mgr, {"event": "held", "strip": "E", "button": True, "here": True})
    mgr.send_key("d")
    tab._release_reader_after_window()
    assert tab._written[-1] == {"cmd": "done"}
    assert {"cmd": "resume"} not in tab._written


def test_the_hold_is_sent_after_whatever_the_menu_sends_first(tab):
    """A key held for this menu goes first; the hold then waits for the
    strip the key moves the reader to (one waiting command, not two)."""
    mgr = tab._manager
    mgr._pending_post_retry_key = "f"
    _read_e_completing_the_chart(tab)
    assert {"cmd": "hold"} not in tab._written
    assert mgr._window_hold == "wanted"
    _feed(mgr, {"event": "strip_ready", "strip": "F", "read": True,
                "all_done": True})
    assert tab._written[-1] == {"cmd": "hold"}


def test_no_hold_from_an_engine_that_cannot(tab):
    tab._manager._engine_holds_here = False
    _read_e_completing_the_chart(tab)
    assert {"cmd": "hold"} not in tab._written


def test_the_session_start_says_whether_the_engine_can_hold_here(tab):
    mgr = tab._manager
    _feed(mgr, {"event": "session_start", "chart": "", "strips": STRIPS,
                "hold_after": True, "hold_here": True})
    assert mgr._engine_holds_here is True
    _feed(mgr, {"event": "session_start", "chart": "", "strips": STRIPS,
                "hold_after": True})
    assert mgr._engine_holds_here is False


# ---------------------------------------------------------------------------
# patch by patch (agent 33, 2026-10-23)
#
# The same fault, one mode over. On a complete chart the spot loop stays
# armed at a patch (read_sample), and a ColorMunki's or i1Pro's button
# triggers a spot reading as it triggers a strip (munki_imp.c:2101-2133). On
# the replay engine of 4.3.9 and of 4.3.10 before this, a press behind "All
# Patches Read" read patch A1 again and the autosave wrote it at once. The
# replay now treats a press while a patch is armed as the trigger it is.
# ---------------------------------------------------------------------------

def _spot_chart(tmp: Path):
    from test_engine_spot import _make_chart
    base = _make_chart(tmp, patches=12)
    replay = tmp / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.0)
    return base, replay


def _quit_spot(s):
    # quit stops the spot read, and a second quit answers the give-up
    # prompt (test_engine_spot.test_quit_aborts_without_saving)
    s.send(cmd="quit")
    s.wait_event("strip_interrupted", timeout=5)
    s.send(cmd="quit")
    s.finish(10)


def _read_every_patch(s) -> dict:
    ev = s.wait_event("spot_ready", timeout=10)
    for _ in range(60):
        if ev.get("all_done") and ev.get("read"):
            return ev
        i = s.event_index()
        s.send(cmd="switch")                     # the instrument's button
        s.wait_event("patch_read", after=i, timeout=5)
        ev = s.wait_event("spot_ready", after=i, timeout=5)
    raise AssertionError("the chart was never complete")


@needs_helper
def test_the_session_says_the_engine_can_hold_at_the_patch_menu(tmp_path):
    base, replay = _spot_chart(tmp_path)
    with ReplaySession(base, replay, extra_args=["-p"]) as s:
        assert s.wait_event("session_start").get("hold_here_patch") is True
        s.wait_event("spot_ready")
        _quit_spot(s)


@needs_helper
def test_patch_by_patch_a_press_behind_the_window_reads_nothing(tmp_path):
    base, replay = _spot_chart(tmp_path)
    with ReplaySession(base, replay, extra_args=["-p"]) as s:
        armed = _read_every_patch(s)["loc"]
        # without the hold, a press reads the armed (already read) patch:
        # the fault this guards against
        i = s.event_index()
        s.send(cmd="switch")
        assert s.wait_event("patch_read", after=i)["loc"] == armed
        armed = s.wait_event("spot_ready", after=i)["loc"]
        # with it, the press is only reported
        j = s.event_index()
        s.send(cmd="hold")
        held = s.wait_event("held", after=j)
        assert held.get("here") is True and held["patch"] == armed
        s.send(cmd="switch")
        s.wait_event("switch", after=j)
        time.sleep(0.6)
        for name in ("scan_started", "patch_read", "saved", "spot_ready"):
            assert not _events(s, j, name), f"{name} while the reader holds"
        # Re-read Patches: the same patch is offered again and reads
        k = s.event_index()
        s.send(cmd="resume")
        assert s.wait_event("spot_ready", after=k)["loc"] == armed
        m = s.event_index()
        s.send(cmd="switch")
        assert s.wait_event("patch_read", after=m)["loc"] == armed
        # Finish from the hold: done is left for the patch menu and saves
        n = s.event_index()
        s.send(cmd="hold")
        s.wait_event("held", after=n)
        s.send(cmd="done")
        s.wait_event("done", after=n, timeout=10)
        assert not _events(s, n, "patch_read")
        assert s.finish(10) == 0


@needs_helper
def test_patch_by_patch_moves_from_the_hold(tmp_path):
    base, replay = _spot_chart(tmp_path)
    with ReplaySession(base, replay, extra_args=["-p"]) as s:
        s.wait_event("spot_ready")
        i = s.event_index()
        s.send(cmd="hold")
        s.wait_event("held", after=i)
        j = s.event_index()
        s.send(cmd="goto", patch="A3")
        assert s.wait_event("spot_ready", after=j)["loc"] == "A3"
        assert not _events(s, j, "patch_read")
        k = s.event_index()
        s.send(cmd="hold")
        s.wait_event("held", after=k)
        s.send(cmd="forward")
        assert s.wait_event("spot_ready", after=k)["loc"] == "A4"
        _quit_spot(s)


def test_the_patch_loop_registers_the_hold_only_for_the_engine():
    text = (SRC / "chromiq_chartread.c").read_text(encoding="utf-8")
    at = text.index("/* Setup the keyboard trigger to return our commands */")
    seg = text[at:text.index("/* Skip to next unread if first has been read */", at)]
    assert "if (cq_json)\n\t\t\t\tinst_set_uih('h', 'h', DUIH_CMND);" in seg
    at = text.index("cq_json && xtern == 0 && ch == 'h'")
    seg = text[at:text.index("} else if (ch == 'f') {", at)]
    assert "cq_switch_gate_set(1);\n\t\t\t\thk = cq_hold_wait" in seg
    assert "cq_switch_gate_set(0);" in seg


@pytest.fixture
def spot_tab(tab):
    mgr = tab._manager
    mgr._spot_mode = True
    mgr._engine_holds_here = True
    mgr._engine_holds_here_patch = True
    tab._spot_session = True
    return tab


def _read_the_last_patch(tab):
    mgr = tab._manager
    _feed(mgr, {"event": "patch_read", "loc": "E2", "xyz": [1, 1, 1],
                "exyz": [1, 1, 1], "de": 0.0})
    mgr._unread_locs = set()
    _feed(mgr, {"event": "spot_ready", "loc": "F1", "read": True,
                "all_done": True})


def test_patch_by_patch_the_engine_holds_before_the_window_opens(spot_tab):
    _read_the_last_patch(spot_tab)
    assert spot_tab._written[-1] == {"cmd": "hold"}
    assert not [w for w in spot_tab._written if w.get("cmd") == "goto"]
    _feed(spot_tab._manager, {"event": "held", "patch": "F1", "button": True,
                              "here": True})
    assert spot_tab._manager._engine_held == {"strip": "F1", "button": True,
                                               "window": True}
    _settle()
    assert spot_tab._shown and {"cmd": "hold"} in spot_tab._shown[0]


def test_patch_by_patch_a_press_behind_the_window_does_nothing(spot_tab):
    mgr = spot_tab._manager
    presses = []
    mgr.instrument_button.connect(lambda: presses.append(1))
    _read_the_last_patch(spot_tab)
    _feed(mgr, {"event": "held", "patch": "F1", "button": True, "here": True})
    n = len(spot_tab._written)
    _feed(mgr, {"event": "switch"})
    _settle(100)
    assert not presses and len(spot_tab._written) == n


def test_patch_by_patch_reread_lets_the_engine_go(spot_tab):
    mgr = spot_tab._manager
    _read_the_last_patch(spot_tab)
    _feed(mgr, {"event": "held", "patch": "F1", "button": True, "here": True})
    spot_tab._release_reader_after_window()
    assert spot_tab._written[-1] == {"cmd": "resume"}
    _feed(mgr, {"event": "spot_ready", "loc": "F1", "read": True,
                "all_done": True})
    assert mgr._engine_held is None and mgr._window_hold is None


def test_patch_by_patch_finish_is_never_followed_by_a_resume(spot_tab):
    mgr = spot_tab._manager
    _read_the_last_patch(spot_tab)
    _feed(mgr, {"event": "held", "patch": "F1", "button": True, "here": True})
    mgr.send_key("d")
    spot_tab._release_reader_after_window()
    assert spot_tab._written[-1] == {"cmd": "done"}
    assert {"cmd": "resume"} not in spot_tab._written


def test_patch_by_patch_no_hold_from_an_engine_that_cannot(spot_tab):
    """A strip-only engine (4.3.10's first build) is not asked to hold at
    the patch menu: there a hold would be dropped anyway."""
    spot_tab._manager._engine_holds_here_patch = False
    _read_the_last_patch(spot_tab)
    assert {"cmd": "hold"} not in spot_tab._written


def test_the_session_start_says_whether_the_engine_can_hold_at_a_patch(tab):
    mgr = tab._manager
    _feed(mgr, {"event": "session_start", "chart": "", "strips": STRIPS,
                "hold_here": True, "hold_here_patch": True})
    assert mgr._engine_holds_here_patch is True
    _feed(mgr, {"event": "session_start", "chart": "", "strips": STRIPS,
                "hold_here": True})
    assert mgr._engine_holds_here_patch is False

"""Item 74, P1 and P2: every ending with the arm out offers the homing, and only an answer that
says so leaves the arm out.

On a real table: End measurement on the failed row's page, End measurement again on the question
about the last step, Discard: the session was closed without the homing being offered; the arm
stayed out, the table in its aiming mode, and the next START moved the arm 24 cm after a countdown.
Every way of ending is walked here from every page that asks something with the arm out.
"""
from __future__ import annotations

import pytest

from tests.i1io_table.test_4350_dual_m1_m2_per_row import STRIP, SPOT  # noqa: F401
from tests.i1io_table.test_dual_table import dual_setup, long_sheet
from tests.i1io_table.test_job_safety import moves
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (fixture)
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W

pytestmark = pytest.mark.timeout(180)

PRESSES = {"end": lambda w: w._on_end_pressed(), "x": lambda w: w._on_close_pressed(),
           "esc": lambda w: w.reject(), "quit": lambda w: w.request_quit()}
#: the page the walk stops on -> (chartread arguments, the faults, guided pages needed)
PAGES = {
    "row_failed_strip": (["-v", "-c", "1", "chart"], {"scan": {"not_ready": True}}),
    "row_failed": (["-v", "-c", "1", "-p", "chart"], {"read_loc": {"0-1": "implausible"}}),
    "dual": (["-v", "-c", "1", "chart"], {"scan": {"uv_not_ready": True}}),
    "dual spot": (["-v", "-c", "1", "-p", "chart"], {"no_write_at": range(2, 60)}),
}


def _open(qtbot, monkeypatch, tmp_path, settings, page, guided=True):  # noqa: F811
    args, faults = PAGES[page]
    if page.startswith("dual"):
        orig = W.TableMeasureWindow.__init__

        def init(self, *a, **k):
            k.setdefault("dual", dual_setup("M1"))
            orig(self, *a, **k)
        monkeypatch.setattr(W.TableMeasureWindow, "__init__", init)
    kw = {"asking": False} if guided is None else {"guided": guided}
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, sheet=long_sheet(), args=args,
        sim=WindowSim(faults=faults), **kw)
    asked = p.drive_until(("row_failed_strip", "row_failed"))
    assert asked in ("row_failed_strip", "row_failed")
    return win, sim, run, p, saved, finished


def _press(win, p, how):
    PRESSES[how](win)
    p.idle()


HOMING = ("home_at_end", "home_offered")


def _to_the_ending(win, p, presses):
    """Press until the readings' question, or the homing's when nothing was read."""
    for how in (*presses, presses[-1]):
        if win.pages_shown[-1] in ("end_of_session", *HOMING):
            break
        _press(win, p, how)
    assert p.page() in ("end_of_session", *HOMING), win.pages_shown[-6:]


def _arm_out(sim):
    j = sim.jobs[-1]
    return not j.at_rest()


def _homing_offered(win, sim, p):
    assert _arm_out(sim), "the walk must end with the arm out"
    assert p.page() in ("home_at_end", "home_offered"), (p.page(), win.pages_shown[-6:])
    assert sim.jobs[-1].phase == "open"


WALKS = [(a, b) for a in PRESSES for b in PRESSES if a != "esc" or b != "esc"]


@pytest.mark.parametrize("answer", ["Save and stop", "Discard and stop"])
@pytest.mark.parametrize("first,second", WALKS)
def test_two_presses_and_the_ending_offer_the_homing(
        qtbot, monkeypatch, tmp_path, settings, first, second, answer):  # noqa: F811
    win, sim, run, p, saved, finished = _open(qtbot, monkeypatch, tmp_path, settings,
                                              "row_failed")
    n = len(sim.sim.received)
    _to_the_ending(win, p, (first, second))
    assert p.page() == "end_of_session"
    p.press(answer)
    _homing_offered(win, sim, p)
    # nothing that moves was sent by any of it
    assert not [ln for ln in sim.sim.received[n:] if ln.startswith((";m", ";i"))]


@pytest.mark.parametrize("guided", [True, False, None])
@pytest.mark.parametrize("page", list(PAGES))
@pytest.mark.parametrize("how", list(PRESSES))
def test_every_kind_of_row_and_every_press_offer_the_homing(
        qtbot, monkeypatch, tmp_path, settings, page, guided, how):  # noqa: F811
    win, sim, run, p, saved, finished = _open(qtbot, monkeypatch, tmp_path, settings, page,
                                              guided)
    if not _arm_out(sim):
        pytest.skip("nothing moved on this walk")
    _to_the_ending(win, p, (how, how))
    if p.page() == "end_of_session":
        p.press("Discard and stop")
    _homing_offered(win, sim, p)
    # and it goes home from there
    if p.page() == "home_at_end":
        p.press("Bring the arm home, my hands are away")
        assert sim.jobs[-1].at_rest() and sim.sim.violations == []


@pytest.mark.parametrize("how", ["end", "x", "esc"])
def test_on_the_homing_page_every_press_is_not_now(
        qtbot, monkeypatch, tmp_path, settings, how):  # noqa: F811
    win, sim, run, p, saved, finished = _open(qtbot, monkeypatch, tmp_path, settings,
                                              "row_failed")
    _to_the_ending(win, p, ("end", "end"))
    p.press("Discard and stop")
    assert p.page() == "home_at_end"
    n = len(sim.sim.received)
    _press(win, p, how)
    assert p.page() == "home_not_now", win.pages_shown[-4:]
    job = sim.jobs[-1]
    assert job.phase == "open" and not win._closed_job and sim.sim.received[n:] == []
    assert win._closed_by_window is False if hasattr(win, "_closed_by_window") else True
    p.press("Bring the arm home, my hands are away")
    assert job.at_rest() and sim.sim.violations == []


def test_the_quit_on_the_homing_page_stays_there(qtbot, monkeypatch, tmp_path,
                                                 settings):  # noqa: F811
    win, sim, run, p, saved, finished = _open(qtbot, monkeypatch, tmp_path, settings,
                                              "row_failed")
    _to_the_ending(win, p, ("quit", "quit"))
    p.press("Discard and stop")
    _homing_offered(win, sim, p)
    assert win.request_quit() is False
    assert p.page() == "home_at_end" and finished == []


def test_a_quit_while_the_save_runs_still_offers_the_homing(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    win, sim, run, p, saved, finished = _open(qtbot, monkeypatch, tmp_path, settings, "row_failed")
    _to_the_ending(win, p, ("end", "end"))
    job = sim.jobs[-1]
    real = job.save

    def slow(*a, **k):
        import time
        time.sleep(0.4)
        return real(*a, **k)
    monkeypatch.setattr(job, "save", slow)
    b = next(x for x in win._buttons if "Save" in x.text() or "Discard" in x.text())
    b.click()
    if win._busy:
        assert win.request_quit() is False
    p.idle()
    _homing_offered(win, sim, p)


def test_an_answered_report_still_goes_to_the_ending(qtbot, monkeypatch, tmp_path,
                                                     settings):  # noqa: F811
    """The wish kept through the report is still fulfilled by its answer (fix round 10)."""
    win, sim, run, p, saved, finished = _open(qtbot, monkeypatch, tmp_path, settings, "row_failed")
    _press(win, p, "end")
    assert p.page() == "report_after_step"
    p.press("As described, my hands are away")
    assert p.page() == "end_of_session"
    p.press("Discard and stop")
    _homing_offered(win, sim, p)

"""4.3.52 fix round, S-1 and S-2 of the independent safety review: the countdown.

S-1: in the pop-up presentation (the look a measurement with the guidance off uses) the
countdown was only a thin strip under the chart preview, and silent, while the person stands at
the table. Now it opens as the table's own pop-up page, large, with ONE button, Stop, and plays
"Instrument error" as it opens (W-1; through the person's sound settings: POPUP_SOUND goes to
the tab's _cue_window, which is play_window). It asks nothing, and it is closed before the arm
moves: the job tells the countdown's end one slice before the first line.
S-2: the first page's instructions (only the sheet on the table, the arm's height for the paper)
are on the countdown page, where they cost no click."""
from __future__ import annotations

import pytest

from core.i18n import tr
from tests.i1io_table.test_4352_guidance_off import UNGUIDED_ANSWERS, _unguided_job
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (the fixture)
from ui import i1io_table_window as W
from workflow import measurement_messages as M
from workflow.i1io.table import job as J

CHECK = ("Please check: only your sheet lies on the table, and the arm's height is set for this "
         "paper.")


def _quiet_unguided(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    guided=False)
    p.script.update(UNGUIDED_ANSWERS)
    assert win._popups, "the guidance off uses the pop-up presentation"
    return win, sim, p


def test_s1_the_countdown_is_a_large_pop_up_with_stop_and_a_sound(qtbot, monkeypatch, tmp_path,
                                                                  settings):
    win, sim, p = _quiet_unguided(qtbot, monkeypatch, tmp_path, settings)
    cues, notices = [], []
    win.cue.connect(cues.append)
    win.notice.connect(notices.append)
    win._relay_progress({"event": "countdown", "left": 3, "seconds": 3.0, "step": "align"})
    pop = win.popup()
    assert win.popup_open() and win._page_id == "countdown"
    title, body = M.M_I1IO_DRIVE_COUNTDOWN.render(n=3)
    assert win._title.text() == title and win._text.text() == body
    assert "font-size" in win._title.styleSheet()                 # large
    # ONE button: Stop. No answer, no End measurement (it would be ignored while the job runs)
    assert win._buttons == []
    assert pop.stop_btn.isVisibleTo(pop) and not pop.end_btn.isVisibleTo(pop)
    assert cues == ["INSTRUMENT_ERROR"]                          # W-1: as it opens
    assert notices and notices[-1] == body.split("\n\n")[0]      # the strip too
    # the next seconds: the same page, the number changes, no second sound
    win._relay_progress({"event": "countdown", "left": 2, "seconds": 3.0, "step": "align"})
    assert win._text.text() == M.M_I1IO_DRIVE_COUNTDOWN.render(n=2)[1]
    assert cues == ["INSTRUMENT_ERROR"]
    assert win.job is not None and not win.job.stop_pressed
    pop.stop_btn.click()
    assert win.job.stop_pressed                                  # the window's own Stop
    # its end closes it
    win._relay_progress({"event": "countdown_end", "stopped": False})
    assert not win.popup_open() and win._page_id == "working"
    assert win._title.styleSheet() == ""


def test_s1_the_sound_is_a_real_sound_and_goes_through_the_sound_settings():
    import inspect

    import core.sound as snd
    from ui.tabs import tab_measure
    assert getattr(snd, W.POPUP_SOUND["countdown"])                  # W-4
    # the quiet mode connects the pop-ups' cue to the tab's _cue_window, which is play_window:
    # the master switch ("Play sounds during measurement") and a sound set to Off hold
    assert "win.cue.connect(self._cue_window)" in inspect.getsource(tab_measure)
    assert "play_window" in inspect.getsource(tab_measure.TabMeasure._cue_window)


def test_s1_the_countdown_end_is_told_before_the_arm_moves(tmp_path):
    """The job tells the end of each countdown before any line after it: the pop-up is closed
    before the arm moves (condition 3)."""
    job, sim, person = _unguided_job(tmp_path)
    events = []
    job.on_progress = lambda ev: events.append((ev.get("event"), len(sim.received),
                                                job._table.t.now() if job._table else 0.0))
    assert person.drive(job.open()).ok and person.drive(job.calibrate()).ok
    r = person.drive(job.align())
    assert r.ok
    starts = [ev for ev in events if ev[0] == "countdown"]
    ends = [ev for ev in events if ev[0] == "countdown_end"]
    assert starts and ends
    (_e, n0, t0), (_e2, n1, t1) = starts[0], ends[0]
    assert n1 == n0, events[:8]                       # no line between its start and its end
    # told one slice BEFORE the countdown is over (the window closes the pop-up meanwhile)
    assert t1 <= t0 + J.UNGUIDED_COUNTDOWN_S - J.COUNTDOWN_SLICE_S / 2, (t0, t1)
    assert t1 >= t0 + J.UNGUIDED_COUNTDOWN_S - 2 * J.COUNTDOWN_SLICE_S, (t0, t1)
    assert J.HANDS_OFF_BREACHES == []


def test_s2_the_countdown_page_carries_the_first_pages_instructions():
    for n in (1, 3):
        body = M.M_I1IO_DRIVE_COUNTDOWN.render(n=n)[1]
        assert tr(CHECK) in body


@pytest.mark.parametrize("lang", ["de", "ru", "uk"])
def test_s2_the_instructions_are_translated(lang):
    import json
    from pathlib import Path
    cat = json.loads((Path(__file__).resolve().parents[2] / "data" / "i18n" /
                      f"{lang}.json").read_text(encoding="utf-8"))
    assert M.M_I1IO_DRIVE_COUNTDOWN.body in cat and M.M_I1IO_DRIVE_COUNTDOWN.body_one in cat
    word = {"de": "Höhe des Arms", "ru": "рычага", "uk": "важеля"}[lang]
    assert word in cat[M.M_I1IO_DRIVE_COUNTDOWN.body].split("\n\n")[1]

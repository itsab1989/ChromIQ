"""4.3.51 (re-review S1, S2): the notice M-I1IO-DRIVE-I1PROFILER-LIMIT ("i1Profiler 3.8.7 and
newer no longer work with the i1iO 2 ...") belongs to a page because a part of it says so
(``needs_old_i1profiler`` on the message, ``_old_i1p`` on a text of the window), never because
the translated text happens to contain "3.8.6".

* the flagged messages are pinned: dropping one fails;
* every table message that sends the person to i1Profiler 3.8.6 or older is flagged, except
  the ones named here with their reason (M-I1IO-DRIVE-NOT-I1IO2 is for a table that is NOT an
  i1iO 2, so "3.8.7 and newer no longer work with the i1iO 2 ... only 3.8.6 or older can do what
  this page describes" may be false there);
* in the table window, in every language, a flagged page shows the notice once and an
  unflagged page never does;
* a real page that gets the notice only by the flag (the table still in its aiming mode at a
  START) shows it: dropping the window's addition fails.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from core import i18n
from core.i18n import tr
from tests.i1io_table.test_4350_not_now_keeps_the_way_home import _LeftOutSim
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from ui import i1io_table_window as W
from workflow import measurement_messages as M

I18N = Path(__file__).resolve().parents[2] / "data" / "i18n"
LANGS = ["en"] + sorted(p.stem for p in I18N.glob("*.json"))

FLAGGED = {
    "M-I1IO-DRIVE-STOPPED", "M-I1IO-DRIVE-STOPPED-END-FIRST", "M-I1IO-DRIVE-AFTER-PROBLEM-OUT",
    "M-I1IO-DRIVE-SWITCH-OFF", "M-I1IO-DRIVE-LINK-LOST", "M-I1IO-DRIVE-LINK-LOST-SWITCH-OFF",
    "M-I1IO-DRIVE-COLD", "M-I1IO-DRIVE-COLD-WAY-OUT", "M-I1IO-DRIVE-FREE-LEFT",
    "M-I1IO-DRIVE-LEFT-OUT", "M-I1IO-DRIVE-STILL-AIMING", "M-I1IO-DRIVE-HOME-AFTER-STOP",
    "M-I1IO-DRIVE-ARM-OUT-AT-START", "M-I1IO-DRIVE-ARM-OUT-AT-START-AREA", "M-I1IO-DRIVE-START-UP", "M-I1IO-DRIVE-USB-MISSING",
    "M-I1IO-DRIVE-USB-NOT-ON-THIS-SYSTEM", "M-I1IO-DRIVE-TABLE-DRIVER",
    "M-I1IO-DRIVE-TABLE-DRIVER-FILE",
}
#: table messages that name i1Profiler 3.8.6 and are NOT flagged, with the reason
NOT_FLAGGED = {
    "M-I1IO-DRIVE-NOT-I1IO2": "the table here is not an i1iO 2: the notice may be false",
    "M-I1IO-DRIVE-CONSENT": "states the limit itself",
    "M-I1IO-DRIVE-ARM-WAY-OUT": "states the limit itself",
    "M-I1IO-DRIVE-I1PROFILER-LIMIT": "is the notice",
}


def _table_messages():
    return [m for m in M.CATALOGUE.values() if m.id.startswith("M-I1IO-DRIVE-")]


def _filled(msg):
    names = set()
    for t in (msg.title, msg.body, msg.body_one, msg.body_two, msg.title_one):
        names |= set(re.findall(r"\{(\w+)\}", t or ""))
    kw = {n: "X" for n in names}
    if msg.count_key:
        kw[msg.count_key] = 3
    return msg.render(**kw)


def test_the_flagged_messages_are_pinned():
    flagged = {m.id for m in _table_messages() if m.needs_old_i1profiler}
    assert flagged == FLAGGED
    for mid in FLAGGED:
        body = M.CATALOGUE[mid].body
        assert "3.8.6 or older" in body and "3.8.7" not in body, mid


def test_every_table_message_naming_old_i1profiler_is_flagged_or_named_here():
    for m in _table_messages():
        if "3.8.6" in m.body and not m.needs_old_i1profiler:
            assert m.id in NOT_FLAGGED, m.id
    assert not M.M_I1IO_DRIVE_NOT_I1IO2.needs_old_i1profiler


def test_the_window_texts_naming_old_i1profiler_are_flagged():
    i18n.set_language("en")
    assert M.needs_i1profiler_limit(W.table_state_text("123456"))
    assert M.needs_i1profiler_limit(W.table_state_text(""))
    _t, body = M.M_I1IO_DRIVE_NOT_I1IO2.render()
    assert not M.needs_i1profiler_limit(body)


@pytest.mark.parametrize("code", LANGS)
def test_in_the_window_a_flagged_page_says_the_limit_once_and_no_other_page_does(
        qtbot, monkeypatch, tmp_path, settings, code):  # noqa: F811
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings)
    i18n.set_language(code)
    try:
        notice = M.M_I1IO_DRIVE_I1PROFILER_LIMIT.render()[1]
        bad = []
        for msg in _table_messages():
            if msg.id == M.M_I1IO_DRIVE_I1PROFILER_LIMIT.id:
                continue
            title, body = _filled(msg)
            win._show("probe", title, body, [(tr("Close"), win._close_job)])
            n = win._text.text().count(notice)
            want = 1 if msg.needs_old_i1profiler else 0
            if n != want:
                bad.append((msg.id, n))
        assert not bad, (code, bad)
    finally:
        i18n.set_language("en")


@pytest.mark.parametrize("code", ["en", "de"])
def test_the_still_aiming_page_gets_the_notice_by_its_flag(
        qtbot, monkeypatch, tmp_path, settings, code):  # noqa: F811
    """The re-review's case: this page names 3.8.6 and not 3.8.7, so only the window's
    addition gives it the notice."""
    i18n.set_language(code)
    try:
        sim = _LeftOutSim()
        win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                        sim=sim, asking=False)
        assert p.drive_until("ready_to_open") == "ready_to_open"
        win._tick_widgets[1].setChecked(True)
        p.press("The arm is out")
        assert p.drive_until(("stopped", "refused", "done")) == "stopped"
        title, _b = M.M_I1IO_DRIVE_STILL_AIMING.render(log="x")
        assert win._title.text() == title
        text = win._text.text()
        assert text.count(M.M_I1IO_DRIVE_I1PROFILER_LIMIT.render()[1]) == 1
        assert sim.sim.violations == []
    finally:
        i18n.set_language("en")

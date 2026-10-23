"""The pause between pages: the manager and the Measure tab (jctay, forum
149802; Basti 2026-10-23: an option in Preferences ▸ Measurement, and a review
moment, also after the last strip of the chart).

The engine half is tests/test_page_pause_engine.py. Here:

* the manager asks the engine to hold after a strip only when the option is
  on and the engine can (``hold_after`` at the strip menu), passes the
  engine's ``held`` and the release on, and lets a press through while held;
* `page_pause_plan` says when the hold is a pause: the next strip to read is
  on another page, or this was the last strip of the chart (or completed it);
* the tab shows the panel (never a window), Continue goes to the next page's
  strip, the instrument's button continues after the debounce and never
  before, Return and Space are Continue, a re-read of a strip of the page
  comes back to the pause, and the option is off by default.

Every test here fails on the code before this change: none of it existed.
"""
from __future__ import annotations

import json
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings, Qt                # noqa: E402
from PyQt6.QtWidgets import QApplication              # noqa: E402

from core.argyll_runner import ArgyllRunner           # noqa: E402
from core.settings import AppSettings                 # noqa: E402
from workflow import measurement_messages as M        # noqa: E402

#: Two pages: A-C on page 1, D-F on page 2.
STRIPS = [{"strip": s, "sheet": 1 if s in "ABC" else 2, "read": False,
           "verifiable": True} for s in "ABCDEF"]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


@pytest.fixture
def tab(qapp, tmp_path, monkeypatch):
    from ui.tabs.tab_measure import TabMeasure
    s = _settings(tmp_path)
    t = TabMeasure(ArgyllRunner(s), s)
    mgr = t._manager
    written = []
    monkeypatch.setattr(mgr._runner, "write_stdin",
                        lambda text: written.append(json.loads(text)))
    mgr._engine_active = True
    mgr._page_pause_on = True
    mgr._engine_holds = True
    mgr._spot_mode = False
    mgr._guided_state = "disabled"
    mgr._session_strips = [dict(x) for x in STRIPS]
    mgr._loc_strip = {f"{s}{i}": s for s in "ABCDEF" for i in (1, 2)}
    mgr._unread_locs = set(mgr._loc_strip)
    mgr._padding_locs = set()
    mgr._chart_was_complete = False
    mgr._is_resume = False
    mgr._read_something = True
    t._session_live = True
    t._written = written
    yield t
    t._session_live = False


def _read(mgr, *strips):
    for s in strips:
        mgr._unread_locs -= {f"{s}1", f"{s}2"}


def _feed(mgr, ev):
    mgr._handle_engine_line(json.dumps(ev), lambda _line: None)


def _settle(ms=60):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.005)


def _hold(tab, strip, button=True):
    mgr = tab._manager
    _feed(mgr, {"event": "held", "strip": strip, "button": button})
    _settle()


# ---------------------------------------------------------------------------
# the plan: when is the hold a pause?
# ---------------------------------------------------------------------------
def test_the_last_strip_of_a_page_is_a_page_turn(tab):
    mgr = tab._manager
    _read(mgr, "A", "B", "C")
    plan = mgr.page_pause_plan("C")
    assert plan == {"kind": "page", "page": 1, "next_page": 2, "pages": 2,
                    "strip": "C", "target": "D"}


def test_a_strip_in_the_middle_of_a_page_is_no_pause(tab):
    mgr = tab._manager
    _read(mgr, "A", "B")
    assert mgr.page_pause_plan("B") is None


def test_the_last_strip_of_the_chart_is_the_end(tab):
    mgr = tab._manager
    _read(mgr, *"ABCDEF")
    plan = mgr.page_pause_plan("F")
    assert plan["kind"] == "end" and plan["page"] == 2


def test_the_read_that_completes_the_chart_is_the_end_too(tab):
    """Strip B was skipped and is read last: that read completes the chart."""
    mgr = tab._manager
    _read(mgr, *"ABCDEF")
    assert mgr.page_pause_plan("B")["kind"] == "end"


def test_back_to_a_skipped_strip_on_the_same_page_is_no_pause(tab):
    mgr = tab._manager
    _read(mgr, "A", "C", "D", "E", "F")    # B skipped; C is the page's last
    # the reader goes back to B, on page 1: no page turn
    assert mgr.page_pause_plan("C") is None


def test_a_single_page_chart_pauses_only_at_its_end(tab):
    mgr = tab._manager
    for st in mgr._session_strips:
        st["sheet"] = 1
    _read(mgr, "A", "B", "C")
    assert mgr.page_pause_plan("C") is None
    _read(mgr, *"DEF")
    assert mgr.page_pause_plan("F")["kind"] == "end"


def test_no_pause_in_front_of_the_unread_question(tab):
    """Re-reading strip A of page 1 while D (page 2) is the next unread one:
    "Continue to next / Jump to unread" is asked, and its answer decides."""
    mgr = tab._manager
    _read(mgr, "A", "B", "C")
    mgr._unread_policy = None
    assert mgr.page_pause_plan("A") is None
    mgr._unread_policy = "unread"
    assert mgr.page_pause_plan("A")["target"] == "D"
    mgr._unread_policy = "next"
    assert mgr.page_pause_plan("A") is None          # on to B, same page


# ---------------------------------------------------------------------------
# the manager and the engine
# ---------------------------------------------------------------------------
def test_the_hold_is_asked_for_at_the_strip_menu_only_when_switched_on(tab):
    mgr = tab._manager
    _feed(mgr, {"event": "strip_ready", "strip": "A", "read": False,
                "all_done": False})
    assert {"cmd": "hold_after", "strip": "A"} in tab._written
    tab._written.clear()
    mgr._page_pause_on = False
    _feed(mgr, {"event": "strip_ready", "strip": "B", "read": False,
                "all_done": False})
    assert not [c for c in tab._written if c.get("cmd") == "hold_after"]


@pytest.mark.parametrize("why", ["engine_cannot", "spot", "guided"])
def test_never_where_it_does_not_apply(tab, why):
    mgr = tab._manager
    if why == "engine_cannot":
        mgr._engine_holds = False
    elif why == "spot":
        mgr._spot_mode = True
    else:
        mgr._guided_state = "waiting"
    mgr._ask_hold_after("A")
    assert not tab._written


def test_the_session_says_whether_the_engine_can_hold(tab):
    mgr = tab._manager
    mgr._engine_holds = False
    mgr._build_read_map = lambda *_a: None
    mgr._learn_measured_strips = lambda *_a: None
    _feed(mgr, {"event": "session_start", "chart": "", "strips": STRIPS,
                "hold_after": True})
    assert mgr._engine_holds is True


def test_held_and_released_are_passed_on_and_a_press_gets_through(tab):
    mgr = tab._manager
    got = []
    mgr.engine_held.connect(lambda s, b: got.append(("held", s, b)))
    mgr.engine_released.connect(lambda: got.append(("released",)))
    presses = []
    mgr.instrument_button.connect(lambda: presses.append(1))
    tab._session_live = False             # the tab stays out of it here
    _feed(mgr, {"event": "switch"})
    assert presses == []
    _feed(mgr, {"event": "held", "strip": "C", "button": True})
    assert mgr.held_strip == {"strip": "C", "button": True}
    _feed(mgr, {"event": "switch"})
    assert presses == [1]
    _feed(mgr, {"event": "strip_ready", "strip": "D", "read": False,
                "all_done": False})
    assert mgr.held_strip is None
    assert got[:2] == [("held", "C", True), ("released",)]


def test_resume_is_written_only_while_held(tab):
    mgr = tab._manager
    mgr.resume_after_hold()
    assert not tab._written
    mgr._engine_held = {"strip": "C", "button": False}
    mgr.resume_after_hold()
    assert tab._written == [{"cmd": "resume"}]


# ---------------------------------------------------------------------------
# the tab
# ---------------------------------------------------------------------------
def test_a_page_turn_shows_the_panel_and_no_window(tab):
    _read(tab._manager, "A", "B", "C")
    _hold(tab, "C")
    assert tab._page_pause_visible()
    assert QApplication.activeModalWidget() is None
    title = tab._page_pause_title.text()
    assert title == M.M_PAGE_PAUSE.render(
        page=1, pages=2, next_page=2, target="D", reread="x",
        **{"continue": "y"})[0]
    body = tab._page_pause_body.text()
    assert "strip D" in body and "page 2" in body
    # the button paragraph: the engine said the button can continue
    assert M.M_PAGE_PAUSE_BUTTON.render(
        **{"continue": "Continue with page 2"})[1] in body
    assert tab._page_pause_continue_btn.text() == "Continue with page 2"
    assert tab._page_pause_reread_btn.text() == "Re-read strip C"
    # the engine still holds: nothing was sent
    assert not tab._written


def test_without_a_button_the_text_does_not_mention_one(tab):
    _read(tab._manager, "A", "B", "C")
    _hold(tab, "C", button=False)
    body = tab._page_pause_body.text()
    assert "button on your" not in body


def test_continue_goes_to_the_first_strip_of_the_next_page(tab):
    _read(tab._manager, "A", "B", "C")
    _hold(tab, "C")
    tab._page_pause_continue_btn.click()
    assert tab._written == [{"cmd": "goto", "strip": "D"}]
    assert not tab._page_pause_visible()


def test_a_hold_that_is_not_a_pause_is_let_go_at_once(tab):
    _read(tab._manager, "A", "B")
    _hold(tab, "B")
    assert not tab._page_pause_visible()
    assert tab._written == [{"cmd": "resume"}]


def test_the_pause_waits_for_a_question_about_the_strip(tab, monkeypatch):
    _read(tab._manager, "A", "B", "C")
    asking = {"on": True}
    monkeypatch.setattr(tab, "_a_question_is_open", lambda: asking["on"])
    _hold(tab, "C")
    assert not tab._page_pause_visible() and not tab._written
    asking["on"] = False
    _settle(600)
    assert tab._page_pause_visible()


def test_the_button_continues_after_the_debounce_and_not_before(tab):
    mgr = tab._manager
    _read(mgr, "A", "B", "C")
    _hold(tab, "C")
    tab._page_pause["shown"] = time.monotonic()           # just appeared
    _feed(mgr, {"event": "switch"})
    assert tab._page_pause_visible() and not tab._written
    tab._page_pause["shown"] = time.monotonic() - 1.0
    _feed(mgr, {"event": "switch"})
    assert tab._written == [{"cmd": "goto", "strip": "D"}]


def test_a_press_while_held_without_a_pause_is_dropped(tab, monkeypatch):
    """Held, a question still open: the press neither continues nor reaches
    the Strip Read Failed window."""
    mgr = tab._manager
    monkeypatch.setattr(tab, "_a_question_is_open", lambda: True)
    _read(mgr, "A", "B", "C")
    _hold(tab, "C")
    _feed(mgr, {"event": "switch"})
    assert not tab._written


def test_return_and_space_are_continue_in_the_pause(tab):
    from PyQt6.QtGui import QKeyEvent
    from PyQt6.QtCore import QEvent
    _read(tab._manager, "A", "B", "C")
    _hold(tab, "C")
    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space,
                   Qt.KeyboardModifier.NoModifier, " ")
    assert tab.eventFilter(tab, ev) is True
    assert tab._written == [{"cmd": "goto", "strip": "D"}]


def test_a_reread_of_the_page_comes_back_to_the_pause(tab):
    mgr = tab._manager
    _read(mgr, "A", "B", "C")
    _hold(tab, "C")
    # click "Re-read strip C", the engine goes there
    tab._page_pause_reread_btn.click()
    assert tab._written[-1] == {"cmd": "goto", "strip": "C"}
    _feed(mgr, {"event": "strip_ready", "strip": "C", "read": True,
                "all_done": False})
    _settle()
    assert not tab._page_pause_visible()
    tab._written.clear()
    # ...read it again: the pause is back, with the same next page
    _hold(tab, "C")
    assert tab._page_pause_visible()
    tab._page_pause_continue_btn.click()
    assert tab._written == [{"cmd": "goto", "strip": "D"}]


def test_a_reread_from_the_middle_of_the_page_comes_back_too(tab):
    """Strip A read again from the pause: "Continue to next / Jump to
    unread" would otherwise decide, and no pause would come back."""
    mgr = tab._manager
    _read(mgr, "A", "B", "C")
    _hold(tab, "C")
    mgr._engine_held = {"strip": "C", "button": True}
    _feed(mgr, {"event": "strip_ready", "strip": "A", "read": True,
                "all_done": False})          # the user clicked strip A
    _settle()
    tab._written.clear()
    _hold(tab, "A")
    assert tab._page_pause_visible()
    assert tab._page_pause["plan"]["target"] == "D"


def test_the_end_of_the_chart_continues_with_resume(tab):
    mgr = tab._manager
    _read(mgr, *"ABCDEF")
    _hold(tab, "F")
    assert tab._page_pause_visible()
    assert tab._page_pause_title.text() == M.M_PAGE_PAUSE_END.title
    assert tab._page_pause_continue_btn.text() == "Continue"
    # two pages: the arrows sentence is there
    assert M.M_PAGE_PAUSE_OTHER_PAGES.render(pages=2)[1] in \
        tab._page_pause_body.text()
    tab._page_pause_continue_btn.click()
    assert tab._written == [{"cmd": "resume"}]


def test_the_page_lists_what_is_worth_a_second_look(tab):
    from workflow.patch_flags import FLAG_RED

    class V:
        flag = FLAG_RED
    mgr = tab._manager
    _read(mgr, "A", "B", "C")

    class J:
        _verdicts = {"B1": V(), "B2": V(), "E1": V()}
    tab._patch_flag_judge = J()
    tab._slip_kept_strips = {"A"}
    _hold(tab, "C")
    found = tab._page_pause_found.text()
    assert "Worth a second look on page 1" in found
    assert "Strip B: 2 patches with a red outline (B1, B2)" in found
    assert "Strip A: ChromIQ asked whether it was read out of step" in found
    assert "E1" not in found                       # page 2
    # Re-read offers the first strip worth a look
    assert tab._page_pause_reread_btn.text() == "Re-read strip A"


def test_nothing_marked_says_so(tab):
    _read(tab._manager, "A", "B", "C")
    _hold(tab, "C")
    assert tab._page_pause_found.text() == M._PAUSE_NOTHING.format(page=1)


def test_the_session_end_takes_the_pause_away(tab):
    _read(tab._manager, "A", "B", "C")
    _hold(tab, "C")
    tab._end_page_pause()
    assert not tab._page_pause_visible()


# ---------------------------------------------------------------------------
# the option
# ---------------------------------------------------------------------------
def test_the_option_is_off_by_default(tmp_path):
    from core.settings import DEFAULTS
    assert DEFAULTS["measure_page_pause"] is False


def test_the_option_reaches_the_reader():
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure)
    assert ('p.page_pause = bool(self._settings.get("measure_page_pause", '
            'False))') in src


def test_preferences_has_the_option_with_its_help(qapp, tmp_path):
    from ui.dialogs.settings_dialog import SettingsDialog, page_pause_help
    s = _settings(tmp_path)
    dlg = SettingsDialog(s, None)
    try:
        cb = dlg._page_pause_cb
        assert cb.text() == "Pause after each page so I can check it"
        assert cb.isChecked() is False
        cb.setChecked(True)
        dlg._save_and_close()
        assert s.get("measure_page_pause") is True
    finally:
        dlg.deleteLater()
    help_ = page_pause_help()
    for needle in ("after the last strip of each page",
                   "after the very last strip of the chart",
                   "never starts reading a strip",
                   "Patch-by-patch reading", "**Default:** off."):
        assert needle in help_
    assert "—" not in help_


def test_a_reread_from_the_end_pause_holds_the_finished_window_back(tab):
    """Found on screen: Re-read from the pause after the last strip let the
    engine say "all done" again, and "All Strips Read" opened over the strip
    being re-read. It waits for the pause's Continue now."""
    mgr = tab._manager
    _read(mgr, *"ABCDEF")
    _hold(tab, "F")
    tab._page_pause_reread_btn.click()
    _feed(mgr, {"event": "strip_ready", "strip": "F", "read": True,
                "all_done": True})
    _settle()
    shown = []
    tab._show_all_stripes_done = lambda: shown.append(1)
    tab._show_patches_left_pending = lambda: shown.append(2)
    tab._on_all_stripes_done()
    _settle(200)
    assert not shown and not tab._all_done_shown
    _hold(tab, "F")
    assert tab._page_pause_visible()
    tab._page_pause_continue_btn.click()
    assert tab._written[-1] == {"cmd": "resume"}
    tab._on_all_stripes_done()
    assert tab._all_done_shown


# ---------------------------------------------------------------------------
# the note (Basti, 2026-10-23): over the column for a while, or nothing at all
# ---------------------------------------------------------------------------
def test_with_the_note_off_the_pause_shows_nothing_but_still_waits(tab):
    tab._settings.set("measure_page_pause_note", False)
    _read(tab._manager, "A", "B", "C")
    _hold(tab, "C")
    assert tab._page_pause_active()
    assert not tab._page_pause_visible()
    assert not tab._written                    # the engine still holds
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QKeyEvent
    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return,
                   Qt.KeyboardModifier.NoModifier, "\r")
    assert tab.eventFilter(tab, ev) is True
    assert tab._written == [{"cmd": "goto", "strip": "D"}]


def test_with_the_note_off_the_button_still_continues(tab):
    tab._settings.set("measure_page_pause_note", False)
    mgr = tab._manager
    _read(mgr, "A", "B", "C")
    _hold(tab, "C")
    tab._page_pause["shown"] = time.monotonic() - 1.0
    _feed(mgr, {"event": "switch"})
    assert tab._written == [{"cmd": "goto", "strip": "D"}]


def test_the_note_goes_after_its_time_and_the_pause_stays(tab):
    _read(tab._manager, "A", "B", "C")
    _hold(tab, "C")
    assert tab._page_pause_visible()
    assert tab._page_pause_timer.isActive()
    ms = tab._page_pause_timer.interval()
    assert tab.PAGE_PAUSE_NOTE_MIN_MS <= ms <= tab.PAGE_PAUSE_NOTE_MAX_MS
    tab._page_pause_timer.timeout.emit()
    _settle(400)                                  # the fade out
    assert not tab._page_pause_visible() and tab._page_pause_active()
    assert not tab._written


def test_a_click_elsewhere_takes_the_note_away(tab):
    from PyQt6.QtCore import QEvent, QPointF
    from PyQt6.QtGui import QMouseEvent
    _read(tab._manager, "A", "B", "C")
    _hold(tab, "C")
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5),
                     QPointF(5, 5), Qt.MouseButton.LeftButton,
                     Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    tab.eventFilter(tab._left_panel, ev)
    _settle(400)
    assert not tab._page_pause_visible() and tab._page_pause_active()


def test_the_note_fades_in_and_out(tab):
    """The legend chip's fast fade (ui.fade.Fade, shared with it)."""
    _read(tab._manager, "A", "B", "C")
    tab._manager._engine_held = None
    _feed(tab._manager, {"event": "held", "strip": "C", "button": True})
    QApplication.processEvents()
    QApplication.processEvents()
    assert tab._page_pause_visible()
    start = tab._page_pause_effect.opacity()
    assert start < 1.0                            # not instant
    _settle(400)
    assert tab._page_pause_effect.opacity() == pytest.approx(1.0)
    tab._hide_page_pause_note()
    # a fade, not a switch: the animation is running the moment it is asked
    # (polling for an in-between value flaked on a loaded gate, where a whole
    # 110 ms can pass between two event-loop turns)
    assert tab._page_pause_fade.running()
    assert tab._page_pause_visible()
    _settle(400)
    assert tab._page_pause_effect.opacity() == pytest.approx(0.0)
    assert not tab._page_pause_visible()


def test_the_note_lies_over_the_preview_in_no_layout(tab):
    """Over the chart preview and in no layout, so nothing moves under it;
    the legend chip's see-through look."""
    assert tab._page_pause_panel.parentWidget() is tab._preview
    lay = tab._preview.layout()
    widgets = [lay.itemAt(i).widget() for i in range(lay.count())] \
        if lay is not None else []
    assert tab._page_pause_panel not in widgets
    from ui.pause_note import PauseNote
    assert isinstance(tab._page_pause_panel, PauseNote)


def test_the_note_option_is_on_by_default_and_greyed_without_the_pause(
        qapp, tmp_path):
    from core.settings import DEFAULTS
    from ui.dialogs.settings_dialog import SettingsDialog, page_pause_note_help
    assert DEFAULTS["measure_page_pause_note"] is True
    s = _settings(tmp_path)
    dlg = SettingsDialog(s, None)
    try:
        note = dlg._page_pause_note_cb
        assert note.text() == "Show a note when it pauses"
        assert note.isChecked() and not note.isEnabled()
        dlg._page_pause_cb.setChecked(True)
        assert note.isEnabled()
        note.setChecked(False)
        dlg._page_pause_cb.setChecked(False)
        assert not note.isEnabled() and not note.isChecked()   # keeps it
        dlg._save_and_close()
        assert s.get("measure_page_pause_note") is False
    finally:
        dlg.deleteLater()
    help_ = page_pause_note_help()
    for needle in ("waits silently at the end of each page",
                   "between 8 and 30 seconds", "**Default:** on.",
                   "see-through"):
        assert needle in help_
    assert "—" not in help_


def test_the_legend_chip_makes_way_while_the_note_is_up(tab):
    _read(tab._manager, "A", "B", "C")
    _hold(tab, "C")
    assert tab._preview.legend_suppressed()
    tab._hide_page_pause_note()
    _settle(400)
    assert not tab._preview.legend_suppressed()


def test_the_end_of_the_session_gives_the_chip_back(tab):
    _read(tab._manager, "A", "B", "C")
    _hold(tab, "C")
    tab._end_page_pause()
    _settle(400)
    assert not tab._preview.legend_suppressed()


def test_with_the_note_off_the_chip_is_never_touched(tab):
    tab._settings.set("measure_page_pause_note", False)
    _read(tab._manager, "A", "B", "C")
    _hold(tab, "C")
    assert not tab._preview.legend_suppressed()


def test_the_note_stays_long_enough_to_read_it(tab):
    """Basti, 2026-10-23: at least 6-8 s, scaled to the text."""
    assert tab._page_pause_note_ms({"title": "x", "body": "", "found": []}) \
        == tab.PAGE_PAUSE_NOTE_MIN_MS == 8000
    assert tab._page_pause_note_ms({"title": "w " * 1000, "body": "",
                                    "found": []}) == 30000
    _read(tab._manager, "A", "B", "C")
    _hold(tab, "C")
    words = 0
    for w in (tab._page_pause_title, tab._page_pause_body, tab._page_pause_found):
        import re
        words += len(re.sub("<[^>]+>", " ", w.text()).split())
    assert tab._page_pause_timer.interval() >= min(30000, words / 4 * 1000) - 1500


def test_the_note_comes_at_every_page_end_and_at_the_end(tab):
    """Three pages: after page 1, after page 2 and after the last strip."""
    mgr = tab._manager
    mgr._session_strips = [{"strip": s, "sheet": 1 + "ABCDEFGHI".index(s) // 3,
                            "read": False, "verifiable": True}
                           for s in "ABCDEFGHI"]
    mgr._loc_strip = {f"{s}{i}": s for s in "ABCDEFGHI" for i in (1, 2)}
    mgr._unread_locs = set(mgr._loc_strip)
    seen = []
    for page_end in ("C", "F", "I"):
        first = "ABCDEFGHI".index(page_end) - 2
        _read(mgr, *"ABCDEFGHI"[first:first + 3])
        _hold(tab, page_end)
        assert tab._page_pause_visible(), page_end
        seen.append(tab._page_pause["plan"]["kind"])
        tab._page_pause_continue_btn.click()
        mgr._engine_held = None
        _feed(mgr, {"event": "strip_ready", "strip": "x", "read": False,
                    "all_done": False})
        _settle(300)
    assert seen == ["page", "page", "end"]


def test_the_two_buttons_share_one_height(tab):
    """Basti, 2026-10-23: "the left button does not have the same height as
    the one on the right"."""
    _read(tab._manager, "A", "B", "C")
    _hold(tab, "C")
    tab._page_pause_panel.resize(560, 320)
    QApplication.processEvents()
    a = tab._page_pause_reread_btn.geometry()
    b = tab._page_pause_continue_btn.geometry()
    assert a.height() == b.height() and a.y() == b.y()
    assert "padding" not in tab._page_pause_reread_btn.styleSheet()


def test_stop_in_the_question_ends_without_a_pause(tab, monkeypatch):
    """Basti, 2026-10-23: Stop in a question about the last strip ends as it
    does today, and no pause comes after it."""
    _read(tab._manager, "A", "B", "C")
    asking = {"on": True}
    monkeypatch.setattr(tab, "_a_question_is_open", lambda: asking["on"])
    _hold(tab, "C")
    assert not tab._page_pause_active()
    tab._session_live = False          # Stop ended the measurement
    asking["on"] = False
    _settle(700)
    assert not tab._page_pause_active() and not tab._page_pause_visible()


def test_a_reread_answer_leaves_the_hold_and_no_pause_follows(tab, monkeypatch):
    """Re-measure in the question: the engine is sent to the strip again (it
    leaves the hold), so the pause waits for that strip's new reading."""
    mgr = tab._manager
    _read(mgr, "A", "B", "C")
    asking = {"on": True}
    monkeypatch.setattr(tab, "_a_question_is_open", lambda: asking["on"])
    _hold(tab, "C")
    _feed(mgr, {"event": "strip_ready", "strip": "C", "read": True,
                "all_done": False})              # Re-measure: back to C
    asking["on"] = False
    _settle(700)
    assert not tab._page_pause_active()
    _hold(tab, "C")                              # read again, accepted
    assert tab._page_pause_visible()


def test_one_press_is_retry_in_strip_read_failed_and_nothing_else(tab):
    """The misread prompt holds the engine at its own prompt, not in the
    pause: a press there is the Strip Read Failed window's, never Continue."""
    mgr = tab._manager
    assert mgr.held_strip is None
    assert tab._page_pause_takes_button() is False   # left to the window

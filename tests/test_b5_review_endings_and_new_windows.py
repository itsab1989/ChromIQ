"""4.3.5 beta 5 review: two gaps in what beta 5 changed.

* "Discard and stop" reached from a failure window's Give Up (six windows go
  through ``_give_up_or_save``) sent Esc to the reader but never told the
  session's verdict that the user had discarded. ChromIQ's engine may already
  have written the session's readings into the .ti3, so that route kept them,
  while the same button reached through Stop put the previous measurement
  back (``MeasurementSession.finish(discarded=True)``).
* The two messages beta 5 opened as windows (M-ENGINE-FELL-BACK and
  M-ALL-STRIPS-PATCHES-LEFT) came from a timer and opened whatever was on
  screen, so they could land on top of another question ("Continue to next /
  Jump to unread", "Was a strip read twice?"). They wait for it now.
"""
from __future__ import annotations

from types import SimpleNamespace

import ui.tabs.tab_measure as tm
from ui.tabs.tab_measure import TabMeasure


def _fake(**kw):
    ns = SimpleNamespace(END_FAILURE_WINDOW=TabMeasure.END_FAILURE_WINDOW,
                         END_SAVE=TabMeasure.END_SAVE,
                         _discard_chosen=False, _ended_by_discard=False)
    ns.__dict__.update(kw)
    return ns


def test_give_up_then_discard_is_the_same_discard_as_stop():
    me = _fake(_confirm_end_of_session=lambda how: "discard")
    assert TabMeasure._give_up_or_save(me) == "\x1b"
    assert me._discard_chosen and me._ended_by_discard


def test_give_up_then_save_or_carry_on_is_no_discard():
    for answer, key in (("save", TabMeasure.END_SAVE), (None, "\r")):
        me = _fake(_confirm_end_of_session=lambda how, a=answer: a)
        assert TabMeasure._give_up_or_save(me) == key
        assert not me._discard_chosen and not me._ended_by_discard


class _Timer:
    calls: list = []

    @staticmethod
    def singleShot(ms, slot):        # noqa: N802 (Qt's name)
        _Timer.calls.append((ms, slot))


def _window_fake(question_open: bool, shown: list):
    return _fake(_runner=SimpleNamespace(is_running=True), _session_live=True,
                 _a_question_is_open=lambda: question_open,
                 _patches_left_n=3, _fell_back_reason="no instrument",
                 _show_patches_left=lambda n: shown.append(("left", n)),
                 _show_engine_fell_back=lambda r: shown.append(("fell", r)),
                 _show_patches_left_pending=object(),
                 _show_engine_fell_back_pending=object())


def test_the_new_windows_wait_for_an_open_question(monkeypatch):
    monkeypatch.setattr(tm, "QTimer", _Timer)
    _Timer.calls = []
    shown: list = []
    me = _window_fake(True, shown)
    TabMeasure._show_patches_left_pending(me)
    TabMeasure._show_engine_fell_back_pending(me)
    assert shown == [], "opened on top of another question"
    assert [slot for _ms, slot in _Timer.calls] == [
        me._show_patches_left_pending, me._show_engine_fell_back_pending]


def test_the_new_windows_open_when_nothing_else_asks(monkeypatch):
    monkeypatch.setattr(tm, "QTimer", _Timer)
    _Timer.calls = []
    shown: list = []
    me = _window_fake(False, shown)
    TabMeasure._show_patches_left_pending(me)
    TabMeasure._show_engine_fell_back_pending(me)
    assert shown == [("left", 3), ("fell", "no instrument")]
    assert _Timer.calls == []

"""The Measure tab takes a key only while a reader really waits for it
(2026-11-14).

The app-wide key filter used to ask only whether a session was MARKED live.
`_session_live` goes up at Start, before the reader is launched, and comes
down in `_on_measure_done`, after it has ended, so around the reader there
were moments when every key in the app was eaten and sent to no process ("a
test once kept the keyboard after its read"). Now the reader's process must
be running too. A person measuring sees no change: a waiting reader gets the
same keys.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    t = TabMeasure(ArgyllRunner(s), s)
    sent = []
    t._manager.send_key = sent.append
    t._arm_key_watchdog = lambda: None
    t._sent = sent
    t._session_live = True
    yield t
    t._session_live = False
    t.deleteLater()


def _key(k, text=""):
    return QKeyEvent(QEvent.Type.KeyPress, k, Qt.KeyboardModifier.NoModifier,
                     text)


def test_a_live_flag_with_no_reader_takes_no_key(tab, qapp):
    assert not tab._runner.is_running
    for k, t in ((Qt.Key.Key_Space, " "), (Qt.Key.Key_Return, "\r"),
                 (Qt.Key.Key_A, "a"), (Qt.Key.Key_Escape, "\x1b")):
        assert tab.eventFilter(tab, _key(k, t)) is False, (
            "a key was eaten with no reader behind it")
    assert tab._sent == []


def test_a_running_reader_gets_its_keys_as_before(tab, monkeypatch):
    monkeypatch.setattr(type(tab._runner), "is_running",
                        property(lambda _self: True))
    assert tab.eventFilter(tab, _key(Qt.Key.Key_Space, " ")) is True
    assert tab.eventFilter(tab, _key(Qt.Key.Key_Return, "\r")) is True
    assert tab._sent == [" ", "\r"]


def test_no_session_still_takes_the_filter_away(tab, qapp, monkeypatch):
    monkeypatch.setattr(type(tab._runner), "is_running",
                        property(lambda _self: True))
    tab._session_live = False
    assert tab.eventFilter(tab, _key(Qt.Key.Key_Space, " ")) is False
    assert tab._sent == []

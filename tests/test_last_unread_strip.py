"""#131 (Knut, 2026-07-26/27): "Skip Stripe" on the only unread stripe skips
nothing.

ArgyllCMS's "next unread" search wraps around, so with nothing else unread it
returns to the very stripe that just failed — the button promises something it
cannot do. When that is the situation it becomes "Finish Without This Strip"
and saves what has been read instead.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                   # noqa: E402
from PyQt6.QtWidgets import QApplication             # noqa: E402

from core.argyll_runner import ArgyllRunner          # noqa: E402
from core.settings import AppSettings                # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    from ui.tabs.tab_measure import TabMeasure
    return TabMeasure(ArgyllRunner(s), s)


def _engine_on(tab, monkeypatch, on=True):
    monkeypatch.setattr(type(tab._manager), "engine_active",
                        property(lambda self: on))


def test_it_is_the_last_unread_when_every_other_strip_is_read(tab, monkeypatch):
    _engine_on(tab, monkeypatch)
    tab._engine_read = {"A": True, "B": True, "C": False}
    tab._current_strip_letter = "C"
    assert tab._is_last_unread_strip() is True


def test_it_is_not_the_last_unread_while_others_remain(tab, monkeypatch):
    _engine_on(tab, monkeypatch)
    tab._engine_read = {"A": True, "B": False, "C": False}
    tab._current_strip_letter = "C"
    assert tab._is_last_unread_strip() is False


def test_another_unread_strip_that_is_not_this_one_does_not_count(tab,
                                                                  monkeypatch):
    """There is somewhere to skip TO, so Skip keeps its normal meaning."""
    _engine_on(tab, monkeypatch)
    tab._engine_read = {"A": False, "B": True, "C": False}
    tab._current_strip_letter = "C"
    assert tab._is_last_unread_strip() is False


def test_nothing_is_claimed_without_the_engine(tab, monkeypatch):
    """The separate chartread gives no dependable read map, and putting the
    wrong button on screen would be worse than leaving it alone."""
    _engine_on(tab, monkeypatch, on=False)
    tab._engine_read = {"A": True, "C": False}
    tab._current_strip_letter = "C"
    assert tab._is_last_unread_strip() is False


def test_nothing_is_claimed_without_a_read_map(tab, monkeypatch):
    _engine_on(tab, monkeypatch)
    tab._engine_read = {}
    tab._current_strip_letter = "C"
    assert tab._is_last_unread_strip() is False


def test_the_window_offers_the_honest_button_and_saves(tab, monkeypatch):
    """End to end through the real dialog: the label changes AND the action
    becomes save-partial rather than a jump that would go nowhere."""
    _engine_on(tab, monkeypatch)
    tab._engine_read = {"A": True, "B": False}
    tab._current_strip_letter = "B"
    saved = {"n": 0}
    monkeypatch.setattr(tab._manager, "send_save_partial_and_quit",
                        lambda: saved.__setitem__("n", saved["n"] + 1))
    monkeypatch.setattr(tab._manager, "send_key", lambda *_a: None)
    monkeypatch.setattr(tab, "_arm_key_watchdog", lambda: None)
    monkeypatch.setattr(tab, "_on_strip_error_sound", lambda *_a: None)

    from PyQt6.QtWidgets import QDialog, QPushButton
    seen = {}

    def press_finish(dlg):
        labels = [b.text() for b in dlg.findChildren(QPushButton)]
        seen["labels"] = labels
        for b in dlg.findChildren(QPushButton):
            if "Finish Without" in b.text():
                b.click()
                return 1
        raise AssertionError(f"no Finish button among {labels}")
    monkeypatch.setattr(QDialog, "exec", press_finish)

    tab._on_strip_error("Not enough patches")

    assert not any("Skip Stripe" in x for x in seen["labels"]), seen["labels"]
    assert saved["n"] == 1, "it must save what was read and end"

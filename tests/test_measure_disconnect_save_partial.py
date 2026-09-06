"""Instrument disconnect during the Save-Partial-&-Quit chain must not kill
chartread — the readings live only in its memory until 'd' writes the .ti3.
Outside that chain the disconnect handler still aborts as before."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


class _Settings:
    def __init__(self):
        self._d = {"appearance": "dark"}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


def _make_tab():
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings()
    return TabMeasure(ArgyllRunner(s), s)


def test_disconnect_during_save_partial_does_not_abort(monkeypatch):
    tab = _make_tab()
    aborted = []
    monkeypatch.setattr(tab._manager, "abort", lambda: aborted.append(True))

    tab._manager._save_partial_state = "wait_strip_menu"
    tab._on_instrument_disconnected()

    assert not aborted
    assert not tab._instrument_disconnected
    # The tag and the sentence, both as the log now prints them: the
    # severity was `[WARN]` here and `[WARNING]` two lines below it in
    # the same widget, and the em dash that joined the two clauses went
    # with the re-key.
    text = tab._log.toPlainText()
    assert "[WARNING] Instrument connection lost." in text
    assert "Still trying to save the partial measurement" in text


def test_disconnect_outside_save_partial_still_aborts(monkeypatch):
    tab = _make_tab()
    aborted = []
    monkeypatch.setattr(tab._manager, "abort", lambda: aborted.append(True))

    tab._on_instrument_disconnected()

    assert aborted == [True]
    assert tab._instrument_disconnected

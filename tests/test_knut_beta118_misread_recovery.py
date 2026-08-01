"""#130 item 3 (Knut, 2026-08-01): recovering from a misread in Read single
patches.

    *"when I simulate a Read failure (misread) … the window shows 'Misread -
    reposition and take the reading again'. If I try to press instrument button
    nothing happens. If I click Take Reading, then the message changes to
    'Ready'. The misread text is a little lacking in information, as it gives
    the impression that pressing take reading will try again. This is not what
    happens, only after pressing take reading button is it ready for
    measurement."*

What spotread actually does after a bad reading::

    Spot read failed due to misread (Reading is inconsistent)
    Hit Esc or Q to give up, any other key to retry:

That prompt is a *keyboard* prompt — the instrument's own button is not read
there, which is why pressing it did nothing. And one click of Take reading was
spent leaving the prompt rather than measuring, so the user lost a reading and
was told nothing about why.

His fix, followed here: Take reading sends a carriage return, pauses long
enough for the status line to be seen changing to Ready, then takes the reading
— and goes back to its ordinary behaviour afterwards. Both status texts are
rewritten to name the control that actually works in each state.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication                     # noqa: E402

from ui.dialogs.spot_read_dialog import SpotReadDialog       # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FakeManager:
    """Records what would reach spotread's stdin, in order."""

    def __init__(self):
        self.sent: list[str] = []

    def take_reading(self):
        self.sent.append("READ")

    def send_key(self, key="\r"):
        self.sent.append(key)


class _FakeButton:
    def __init__(self):
        self.enabled = True

    def setEnabled(self, on):
        self.enabled = bool(on)

    def isEnabled(self):
        return self.enabled


def _dlg(misread=False):
    d = SpotReadDialog.__new__(SpotReadDialog)
    d._manager = _FakeManager()
    d._read_btn = _FakeButton()
    d._misread = misread
    d._status_texts = []
    d._set_status = d._status_texts.append
    return d


# ---- the ordinary case is untouched --------------------------------------
def test_a_normal_click_just_reads(qapp):
    d = _dlg(misread=False)
    d._on_take_reading()
    assert d._manager.sent == ["READ"]


# ---- the misread case ----------------------------------------------------
def test_a_misread_click_clears_first_then_reads(qapp):
    """One click, both steps — the CR that leaves the retry prompt, then the
    reading. Before this, the click was consumed by the prompt."""
    d = _dlg(misread=True)
    d._on_take_reading()
    assert d._manager.sent == ["\r"], "the CR must go first, on its own"

    # The reading follows after the pause; drive the timer rather than waiting.
    qapp.processEvents()
    from PyQt6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(SpotReadDialog._MISREAD_CLEAR_PAUSE_MS + 150, loop.quit)
    loop.exec()
    assert d._manager.sent == ["\r", "READ"]


def test_the_button_is_disabled_between_the_two_keys(qapp):
    """Otherwise an impatient second click queues a third keypress and takes
    two readings from one intended measurement."""
    d = _dlg(misread=True)
    d._on_take_reading()
    assert d._read_btn.isEnabled() is False


def test_the_state_clears_so_the_button_goes_back_to_normal(qapp):
    """Knut: *"After the status goes back to ready, the Take Reading button
    must also go back to regular function."*"""
    d = _dlg(misread=True)
    d._on_take_reading()
    from PyQt6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(SpotReadDialog._MISREAD_CLEAR_PAUSE_MS + 150, loop.quit)
    loop.exec()
    assert d._misread is False
    assert d._read_btn.isEnabled() is True

    d._manager.sent.clear()
    d._on_take_reading()
    assert d._manager.sent == ["READ"], "a later click must not send a CR again"


def test_the_ready_prompt_ends_the_misread_state(qapp):
    """spotread returning to its menu is the real evidence the error is over —
    a reading taken with the instrument's button also gets there, without any
    click for a timer to hang off."""
    d = _dlg(misread=True)
    d._on_ready()
    assert d._misread is False
    assert d._read_btn.isEnabled() is True


def test_the_pause_is_long_enough_to_be_seen(qapp):
    """Knut asked for ~0.3 s precisely so the change to Ready is visible. Much
    shorter and the two steps collapse into one on screen; much longer and the
    tool feels broken."""
    assert 250 <= SpotReadDialog._MISREAD_CLEAR_PAUSE_MS <= 600


# ---- the texts name the control that works -------------------------------
def test_the_misread_text_says_the_instrument_button_will_not_work(qapp):
    d = _dlg()
    d._on_misread()
    text = " ".join(d._status_texts)
    assert "Take reading" in text
    assert "instrument" in text.lower()
    assert "discarded" in text.lower(), \
        "the user needs to know the reading was thrown away, not kept"


def test_the_misread_state_leaves_the_button_usable(qapp):
    """It is the only control that can clear the error, so disabling it would
    strand the session."""
    d = _dlg()
    d._read_btn.setEnabled(False)
    d._on_misread()
    assert d._misread is True
    assert d._read_btn.isEnabled() is True


def test_the_ready_text_names_both_ways_of_reading(qapp):
    """Knut: *"the 'Ready ….' message is inaccurate, as using instrument button
    is also possible."*"""
    d = _dlg()
    d._on_ready()
    text = " ".join(d._status_texts)
    assert "Take reading" in text
    assert "button on the instrument" in text


def test_the_help_card_explains_a_misread(qapp):
    """A user who hits this mid-session should not have to find the issue
    tracker to learn what happened."""
    from ui.dialogs.spot_read_dialog import _HELP
    assert "inconsistent" in _HELP.lower()
    assert "Take reading" in _HELP

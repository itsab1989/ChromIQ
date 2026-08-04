"""#130 (Knut, 2026-08-01): ChromIQ sent stray keys to the instrument.

His patch-by-patch log ends with a bare ``c``, and a tab character two minutes
later:

    2026-08-01 18:05:50  send_key 'c'  → pty OK
    2026-08-01 18:07:50  send_key '\\t' → pty OK

    "the stray c was part of the log window. No keys were pressed. only the
     sequence I told you, so the code generated these extra key strokes. That
     is the bug. Search the code for these occurrences."

He is right, and my first answer — that these were his own keystrokes being
forwarded — was wrong in the way that mattered. They were his **shortcuts**.

While a measurement waits for a key, the Measure tab installs an event filter
on the whole application and forwards ``event.text()`` for anything it does not
recognise. For ⌘C that text is the bare letter ``"c"``. So copying the log
(which is exactly what he does before pasting it into an issue) sent a ``c`` to
the reader — and because the filter consumed the event, the copy did not even
happen. Tab, pressed to move focus, went the same way.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QEvent, Qt                       # noqa: E402
from PyQt6.QtGui import QKeyEvent                         # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Mgr:
    def __init__(self):
        self.sent: list[str] = []

    def send_key(self, key):
        self.sent.append(key)


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
    t._manager = _Mgr()
    t._arm_key_watchdog = lambda: None
    # These tests are about a reader that is WAITING FOR A KEY, which is the
    # only state in which the app-wide filter forwards anything. Since
    # beta.130 the filter says so itself: with no session live it removes
    # itself rather than swallowing keys the rest of the app needs.
    t._session_live = True
    return t


def _key(k, text="", mods=Qt.KeyboardModifier.NoModifier):
    return QKeyEvent(QEvent.Type.KeyPress, k, mods, text)


# ---- his case ------------------------------------------------------------
@pytest.mark.parametrize("mod,name", [
    (Qt.KeyboardModifier.MetaModifier, "Cmd"),
    (Qt.KeyboardModifier.ControlModifier, "Ctrl"),
    (Qt.KeyboardModifier.AltModifier, "Alt"),
])
def test_a_shortcut_never_reaches_the_instrument(tab, mod, name):
    """⌘C is a copy, not a reading command."""
    handled = tab.eventFilter(tab, _key(Qt.Key.Key_C, "c", mod))
    assert tab._manager.sent == [], f"{name}+C was sent to the reader"
    assert handled is False, \
        f"{name}+C must reach the application, or copy stops working"


def test_tab_is_left_for_focus(tab):
    handled = tab.eventFilter(tab, _key(Qt.Key.Key_Tab, "\t"))
    assert tab._manager.sent == []
    assert handled is False


def test_shift_tab_too(tab):
    handled = tab.eventFilter(tab, _key(Qt.Key.Key_Backtab, "",
                                        Qt.KeyboardModifier.ShiftModifier))
    assert tab._manager.sent == []
    assert handled is False


# ---- the keys that ARE for the instrument still work ---------------------
def test_return_still_reads(tab):
    assert tab.eventFilter(tab, _key(Qt.Key.Key_Return, "\r")) is True
    assert tab._manager.sent == ["\r"]


def test_space_still_reads(tab):
    tab.eventFilter(tab, _key(Qt.Key.Key_Space, " "))
    assert tab._manager.sent == [" "]


def test_escape_still_gives_up(tab):
    tab.eventFilter(tab, _key(Qt.Key.Key_Escape, "\x1b"))
    assert tab._manager.sent == ["\x1b"]


def test_the_arrows_still_navigate(tab):
    tab.eventFilter(tab, _key(Qt.Key.Key_Left, ""))
    tab.eventFilter(tab, _key(Qt.Key.Key_Right, ""))
    assert tab._manager.sent == ["\x1b[D", "\x1b[C"]


def test_a_plain_letter_still_reaches_chartread(tab):
    """chartread's own menu keys — f, b, n, d, k — must still get through."""
    for letter in "fbndk":
        tab.eventFilter(tab, _key(getattr(Qt.Key, f"Key_{letter.upper()}"),
                                  letter))
    assert tab._manager.sent == list("fbndk")


def test_shift_alone_does_not_block_a_letter(tab):
    """Shift is not a command modifier — 'F' is a real chartread key."""
    tab.eventFilter(tab, _key(Qt.Key.Key_F, "F",
                              Qt.KeyboardModifier.ShiftModifier))
    assert tab._manager.sent == ["F"]


# ---- and it lets go when there is nothing to forward to ------------------
def test_the_filter_removes_itself_when_no_session_is_live(tab, qapp):
    """A filter installed on the whole application must not outlive the reader
    it forwards to.

    Every ending removes it, but the recovery windows re-install it as they
    close — so a session that ended inside one could leave it behind, and from
    then on an arrow key anywhere in ChromIQ was eaten and logged as "send_key
    LEFT: no active process". A keyboard-navigation test lost its arrow keys to
    a Measure tab left over from an earlier test in the same process; a user
    would lose them to the tab they had just measured in.
    """
    tab._session_live = False
    QApplication.instance().installEventFilter(tab)
    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier)

    assert tab.eventFilter(tab, ev) is False, "the key must reach the app"
    assert tab._manager.sent == [], "nothing may be sent with no reader running"

    # …and it really has taken itself off the application.
    tab._manager.sent.clear()
    assert tab.eventFilter(tab, ev) is False

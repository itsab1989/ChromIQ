"""#159: an instrument that vanishes mid-chart said so only in the log.

The owner hit this himself on 2026-08-28 — he unplugged the CR30 mid-session,
the app said nothing at all, and then froze for three minutes when he tried to
stop. The freeze and the detection were fixed then. WHERE it was said was not:
M-CR30-INSTRUMENT-GONE went to the log under the §M rule that unapproved
wording speaks through the log until it is approved, so the user got the shared
ending window with no idea why it had appeared.

He ruled on it directly, 2026-08-30:

    *"i don't know what m-cr30-instrument-gone is for but if this is an
     important message this should be in a pop up windows with benefitial
     options for this case"*

It is important, and the beneficial options are real: plug it back in and carry
on, or stop and keep everything already read. Nothing is lost either way — the
helper writes the measurement file after every patch.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                       # noqa: E402
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget      # noqa: E402

from ui.tabs.tab_measure import TabMeasure                          # noqa: E402


@pytest.fixture(autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


class _Box:
    """The window, with the close button as a first-class outcome."""

    from PyQt6.QtWidgets import QMessageBox as _real
    Icon = _real.Icon
    ButtonRole = _real.ButtonRole
    choose: "str | None" = "Carry on measuring"
    shown: list = []

    def __init__(self, parent=None):
        self._buttons: dict = {}
        self._clicked = None
        self.text = self.informative = ""

    def __getattr__(self, name):
        return lambda *a, **k: None

    def setText(self, t):
        self.text = t

    def setInformativeText(self, t):
        self.informative = t

    def addButton(self, text, role):
        b = QPushButton(text)
        self._buttons[text] = b
        return b

    def exec(self):
        type(self).shown.append(self)
        want = type(self).choose
        self._clicked = self._buttons.get(want) if want else None
        if want is not None and self._clicked is None:
            raise AssertionError(
                f"no {want!r} button; offered {sorted(self._buttons)}")

    def clickedButton(self):
        return self._clicked


class _Log:
    def __init__(self):
        self.lines: list[str] = []

    def appendPlainText(self, t):
        self.lines.append(t)

    def ensureCursorVisible(self):
        pass


class _Bridge:
    def __init__(self, rearms=True):
        self._rearms = rearms
        self.rearmed = 0

    def rearm(self):
        self.rearmed += 1
        return self._rearms


class _Tab(QWidget):
    _on_cr30_device_lost = TabMeasure._on_cr30_device_lost
    END_FAILURE_WINDOW = TabMeasure.END_FAILURE_WINDOW

    def __init__(self, bridge=None):
        super().__init__()
        self._log = _Log()
        self._cr30_bridge = bridge
        self.ended: list = []
        self.flashed: list = []

    def _flash_status(self, text, duration_ms=0):
        self.flashed.append(text)

    def _sound_instrument_fault_once(self):
        pass

    def _confirm_end_of_session(self, which):
        self.ended.append(which)
        return "give_up"

    def _end_session(self, choice):
        self.ended.append(("end", choice))


@pytest.fixture
def window(monkeypatch):
    import PyQt6.QtWidgets as W
    import ui.widgets as widgets
    monkeypatch.setattr(W, "QMessageBox", _Box)
    monkeypatch.setattr(widgets, "fit_message_box_buttons", lambda box: None)
    _Box.choose = "Carry on measuring"
    _Box.shown = []
    return _Box


REASON = "the instrument stopped answering"


def test_it_opens_a_window_and_does_not_only_log(window):
    tab = _Tab(_Bridge())
    tab._on_cr30_device_lost("B7", REASON)
    assert window.shown, (
        "a vanished instrument was announced only in the log, where it is "
        "found by scrolling")


def test_the_window_says_which_patch_and_that_nothing_is_lost(window):
    tab = _Tab(_Bridge())
    tab._on_cr30_device_lost("B7", REASON)
    said = window.shown[0].text + " " + window.shown[0].informative
    assert "B7" in said, "it does not say where the measurement stopped"
    assert "lost" in said.lower() or "saved" in said.lower(), (
        "it does not tell the user their measurements are safe, which is the "
        "first thing anyone wants to know")
    assert REASON in said, "the underlying failure was dropped"


def test_carrying_on_re_arms_instead_of_ending(window):
    bridge = _Bridge()
    tab = _Tab(bridge)
    tab._on_cr30_device_lost("B7", REASON)
    assert bridge.rearmed == 1, "nothing is listening after 'carry on'"
    assert not any(isinstance(e, tuple) for e in tab.ended), (
        "carrying on ended the session anyway")


def test_stopping_goes_through_the_one_shared_ending(window):
    """measurement_exit_strategy.md §1: every ending route goes through
    `_confirm_end_of_session`, so there is no second exit."""
    window.choose = "Stop the measurement"
    tab = _Tab(_Bridge())
    tab._on_cr30_device_lost("B7", REASON)
    assert tab.ended and tab.ended[0] == TabMeasure.END_FAILURE_WINDOW
    assert any(isinstance(e, tuple) and e[0] == "end" for e in tab.ended)


def test_closing_the_window_does_not_end_the_session(window):
    """Dismissing a window is a withdrawal, never a consent — and ending the
    session is the consequential act here, so a close takes the option that
    changes nothing. Same rule as the black calibration window."""
    window.choose = None                     # red traffic light / X / Esc
    bridge = _Bridge()
    tab = _Tab(bridge)

    tab._on_cr30_device_lost("B7", REASON)

    assert any(isinstance(e, tuple) and e[0] == "end" for e in tab.ended), (
        "closing the window neither ended nor continued — the session would "
        "be left with nothing listening and nothing on screen")


def test_it_survives_having_no_bridge_at_all(window):
    """The bridge can already be gone when this arrives; it must not raise on
    top of an instrument failure."""
    tab = _Tab(None)
    tab._on_cr30_device_lost("B7", REASON)      # must not raise


def test_the_message_no_longer_only_tells_the_user_to_start_again(window):
    """The text used to say "start the measurement again with Refine / resume
    ticked" as the ONLY way forward, which contradicted the app: it offers to
    carry on from the patch you were on."""
    from workflow import measurement_messages as M
    _, body = M.M_CR30_INSTRUMENT_GONE.render(loc="B7", reason=REASON)
    assert "Carry on measuring" in body, (
        "the text does not name the button that carries on")
    i, j = body.index("Carry on measuring"), body.index("Refine / resume")
    assert i < j, (
        "restarting is offered before carrying on, which is the wrong order: "
        "carrying on is what the user wants and what the app now does")

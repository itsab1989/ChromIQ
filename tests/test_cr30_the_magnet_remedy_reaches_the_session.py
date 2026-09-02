"""#159: "Recalibrate now" led into a dead session.

The magnet window is the remedy for the owner's own incident — a chart on a
MacBook, the laptop's magnets reaching through the sheet, the instrument taking
a white calibration from the patch he meant to measure. The window stops the
session and offers to put it right.

It could not. The remedy called the calibration, and the calibration's FIRST act
was to drop the bridge and build a new one — so:

* the instrument was closed and reopened in the middle of the recovery;
* the outstanding patch, the retry counts and the stopped flag went with the old
  bridge;
* `resume_after_magnet()` then ran against a bridge that had never been stopped,
  where its first line — `if not self._stopped: return True` — reports success
  without arming anything.

The operator was told "Carrying on. Read the highlighted patch again." with
nothing listening for the press.

⚠ WHY THE EXISTING TESTS PASSED. Every one of them resumes the SAME bridge
object it stopped, which is the one thing the tab did not do. The tab path had
no test at all. So these drive the real `TabMeasure` methods — unbound, over a
stand-in for the widget — rather than reading their source: an
`inspect.getsource` test of this flow would have passed against the dead end
just as happily.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                       # noqa: E402

from ui.tabs.tab_measure import TabMeasure                          # noqa: E402
from workflow.cr30.measurement import MAGNET_MESSAGE, MagnetGated   # noqa: E402
from tests.test_cr30_measure_bridge import Harness                  # noqa: E402


class _Button:
    def __init__(self, enabled=True):
        self._on = enabled

    def isEnabled(self):
        return self._on

    def setEnabled(self, on):
        self._on = on


class _Log:
    def __init__(self):
        self.lines: list[str] = []

    def appendPlainText(self, text):
        self.lines.append(text)

    def ensureCursorVisible(self):
        pass


class _Tab:
    """A stand-in widget carrying the REAL methods under test."""

    _on_cr30_magnet = TabMeasure._on_cr30_magnet
    _run_cr30_calibration = TabMeasure._run_cr30_calibration
    _calibrate_and_confirm = TabMeasure._calibrate_and_confirm
    _open_cr30_bridge = TabMeasure._open_cr30_bridge
    _close_cr30_bridge = TabMeasure._close_cr30_bridge
    _end_after_magnet = TabMeasure._end_after_magnet
    END_FAILURE_WINDOW = TabMeasure.END_FAILURE_WINDOW

    #: What the ending window returns, in order. None means "Keep measuring".
    endings: list = []

    def __init__(self, bridge):
        self._cr30_bridge = bridge
        # No reader, so the calibration returns as soon as it has decided what
        # to do with the bridge — which is the whole of what this file is
        # about. That the calibration itself runs is proved separately, in
        # tests/test_cr30_calibration_actually_runs.py.
        self._cr30_reader = None
        self._log = _Log()
        self._start_btn = _Button()
        self._stop_btn = _Button()
        self.closes = 0
        self.ended: list = []

    def _sound_instrument_fault_once(self):
        pass

    def _confirm_end_of_session(self, which):
        self.ended.append(which)
        return self.endings.pop(0) if self.endings else "give_up"

    def _end_session(self, choice):
        self.ended.append(("end", choice))


class _StubBox:
    """Stands in for the magnet window, and clicks one of its own buttons."""

    from PyQt6.QtWidgets import QMessageBox as _real
    Icon = _real.Icon
    ButtonRole = _real.ButtonRole
    choose = "Recalibrate now"
    seen: list = []

    def __init__(self, parent=None):
        self._buttons: list = []
        self._clicked = None

    def __getattr__(self, name):          # setText, setIcon, setDefaultButton…
        return lambda *a, **k: None

    def addButton(self, text, role):
        b = _Button()
        b.text = text
        self._buttons.append(b)
        return b

    def exec(self):
        type(self).seen.append([b.text for b in self._buttons])
        for b in self._buttons:
            if b.text == type(self).choose:
                self._clicked = b
                return
        raise AssertionError(
            f"no {type(self).choose!r} button; the window offered "
            f"{[b.text for b in self._buttons]}")

    def clickedButton(self):
        return self._clicked


@pytest.fixture
def stubbed(monkeypatch):
    """The window, stubbed. Everything below it is the real code."""
    import PyQt6.QtWidgets as W
    import ui.widgets as widgets
    _StubBox.seen = []
    monkeypatch.setattr(W, "QMessageBox", _StubBox)
    monkeypatch.setattr(widgets, "fit_message_box_buttons", lambda box: None)
    return _StubBox


def _stopped_by_a_magnet():
    """A real bridge, stopped the way the instrument really stops it.

    ⚠ ANY TEST THAT RESUMES THIS BRIDGE MUST CALL `h.settle()` BEFORE IT ENDS.
    Resuming starts a real reader thread; ending the test with it still running
    leaves Qt collecting objects out from under it, and the worker SEGFAULTS —
    intermittently, and never when the file is run alone, which is the worst
    way for it to fail. Seen repeatedly on 2026-08-30 under `-n auto`.
    """
    h = Harness()
    h.raise_with = MagnetGated(MAGNET_MESSAGE)
    h.ready("A1")
    assert h.bridge._stopped is True and h.bridge._awaiting_loc == "A1"
    h.raise_with = None                       # the user recalibrates
    return h


def test_the_remedy_keeps_the_session_it_is_rescuing(stubbed):
    """The bridge IS the stopped session. Replacing it discards the recovery."""
    h = _stopped_by_a_magnet()
    tab = _Tab(h.bridge)
    was = tab._cr30_bridge

    tab._on_cr30_magnet("A1", MAGNET_MESSAGE)

    assert tab._cr30_bridge is was, (
        "the remedy built a new bridge; the outstanding patch and the stopped "
        "flag went with the old one")
    h.settle()          # the resume started a reader thread; let it finish


def test_the_remedy_actually_re_arms_the_patch(stubbed):
    """The assertion the dead end could not have made.

    `resume_after_magnet` returns True on a bridge that was never stopped
    without arming anything, so 'it returned True' proves nothing on its own —
    what matters is that a read is running for the patch the operator is
    looking at.
    """
    h = _stopped_by_a_magnet()
    before = len(h.read_calls)
    tab = _Tab(h.bridge)

    tab._on_cr30_magnet("A1", MAGNET_MESSAGE)

    assert h.bridge._stopped is False, "the session is still stopped"
    assert h.bridge.armed_for("A1"), (
        "the highlighted patch is not the one being read")
    h.settle()                      # let the reader thread actually run
    assert len(h.read_calls) > before, (
        "nothing is listening for the press the operator was just asked for")
    assert h.sent, "the resumed read never produced a value for the chart"


def test_the_operator_is_only_told_it_carried_on_when_it_did(stubbed):
    h = _stopped_by_a_magnet()
    tab = _Tab(h.bridge)
    tab._on_cr30_magnet("A1", MAGNET_MESSAGE)
    said = "\n".join(tab._log.lines)
    assert "Carrying on" in said
    assert h.bridge.armed_for("A1"), (
        "the app promised the session had carried on while nothing listened")
    h.settle()


def test_the_instrument_is_not_closed_mid_recovery(stubbed):
    """`reader.close()` disconnects it — over Bluetooth, a full disconnect of a
    peripheral that takes one connection at a time, in the middle of putting
    the reference right."""
    h = _stopped_by_a_magnet()
    tab = _Tab(h.bridge)
    stops = []
    h.bridge.stop = lambda *a, **k: stops.append(1)

    tab._on_cr30_magnet("A1", MAGNET_MESSAGE)

    assert stops == [], "the bridge was stopped by its own remedy"
    h.settle()


def test_stopping_from_the_window_still_ends_the_session(stubbed):
    """The other button must keep working — the fix must not make the magnet
    window a one-way door."""
    stubbed.choose = "Stop the measurement"
    try:
        h = _stopped_by_a_magnet()
        tab = _Tab(h.bridge)
        tab._on_cr30_magnet("A1", MAGNET_MESSAGE)
        assert any(isinstance(e, tuple) and e[0] == "end" for e in tab.ended), (
            "'Stop the measurement' did not end the session")
        assert h.bridge._stopped is True, "the session was resumed anyway"
        h.settle()
    finally:
        stubbed.choose = "Recalibrate now"


def test_keep_measuring_does_not_leave_a_stopped_session_on_screen(stubbed):
    """THE OTHER DOOR INTO THE SAME DEAD END.

    "Stop the measurement" leads to the shared ending window, and that window
    always offers "Keep measuring" — which returns None, and `_end_session`
    treats None as "carry on" by doing nothing at all. So the session stayed
    stopped, with nothing armed and nothing on screen: exactly the fault the
    magnet remedy exists to remove, reached by the other route.

    Resuming would be wrong — the white reference is still overwritten. So the
    remedy comes back instead, and the user recalibrates or really ends it.
    """
    stubbed.choose = "Stop the measurement"
    _Tab.endings = [None, "give_up"]        # keep measuring, then really stop
    try:
        h = _stopped_by_a_magnet()
        tab = _Tab(h.bridge)
        tab._on_cr30_magnet("A1", MAGNET_MESSAGE)

        assert len(stubbed.seen) == 2, (
            "the remedy was not offered again after 'Keep measuring'; the "
            f"window was shown {len(stubbed.seen)} time(s)")
        assert any("still stopped" in l for l in tab._log.lines), (
            "nothing told the user why they cannot measure")
        h.settle()
    finally:
        stubbed.choose = "Recalibrate now"
        _Tab.endings = []


def test_cancelling_the_calibration_is_not_an_ending_by_itself(stubbed):
    """Cancel at the calibration window, then "Keep measuring": the remedy must
    come back rather than the session dying quietly."""
    _Tab.endings = [None, "give_up"]
    try:
        h = _stopped_by_a_magnet()
        tab = _Tab(h.bridge)
        # No reader, so the calibration returns True; force the cancel path.
        tab._run_cr30_calibration = lambda **kw: False
        tab._on_cr30_magnet("A1", MAGNET_MESSAGE)
        assert len(stubbed.seen) == 2, (
            "cancelling the calibration ended the session without asking")
        h.settle()
    finally:
        _Tab.endings = []


def test_a_start_still_lets_go_of_an_older_bridge():
    """The other caller must keep its opposite behaviour: a Start must NOT
    inherit a previous run's bridge. One flag serves both, so both are asserted
    here — otherwise fixing the magnet quietly breaks Start."""
    h = _stopped_by_a_magnet()
    tab = _Tab(h.bridge)
    closed = []
    tab._close_cr30_bridge = lambda: closed.append(1)

    TabMeasure._calibrate_and_confirm(tab, keep_bridge=False)

    assert closed == [1], "a Start inherited the previous session's bridge"


def test_the_remedy_does_not_let_go_of_it():
    h = _stopped_by_a_magnet()
    tab = _Tab(h.bridge)
    closed = []
    tab._close_cr30_bridge = lambda: closed.append(1)

    TabMeasure._calibrate_and_confirm(tab, keep_bridge=True)

    assert closed == [], "the remedy dropped the session it was rescuing"


def test_resuming_a_bridge_that_was_never_stopped_is_not_success():
    """The one line both dead ends grew from.

    `resume_after_magnet` used to answer True whenever the bridge was not
    stopped — which is exactly the state a REBUILT bridge is in. The tab took
    that as "carrying on" and said so to the user, over a session with no
    reader in it. "Not stopped" is not the same as "reading".
    """
    from workflow.cr30.measure_bridge import Cr30MeasureBridge
    h = Harness()
    fresh = h.bridge                      # never stopped, nothing outstanding
    assert fresh._stopped is False
    assert fresh.resume_after_magnet() is False, (
        "a bridge with nothing outstanding reported that it had resumed")
    h.settle()


def test_a_real_resume_still_reports_success():
    """The other direction, so the fix cannot be 'always return False'."""
    h = _stopped_by_a_magnet()
    assert h.bridge.resume_after_magnet() is True
    assert h.bridge.armed_for("A1")
    h.settle()          # ⚠ see _stopped_by_a_magnet: resuming starts a thread



def test_every_test_here_that_resumes_also_settles():
    """SELF-POLICING, because the failure is an intermittent SEGFAULT.

    Resuming starts a real reader thread. A test that ends while it runs lets
    Qt collect objects out from under it and the xdist worker dies — never when
    the file runs alone, which is the worst way for a fault to present. It was
    tolerated for hours before being tracked down, and then reappeared two
    screens below the warning that documents it.

    So the rule is enforced rather than remembered. It is deliberately
    over-broad: a test that only LOOKS like it resumes still has to settle,
    because deciding case by case is how the hole got reopened.
    """
    import pathlib
    src = pathlib.Path(__file__).read_text(encoding="utf-8")
    offenders = []
    for block in src.split("\ndef test_")[1:]:
        name = block.split("(")[0]
        if name == "every_test_here_that_resumes_also_settles":
            continue
        touches = ("resume_after_magnet" in block or "_on_cr30_magnet" in block
                   or "bridge.rearm(" in block)
        if touches and "h.settle()" not in block:
            offenders.append(name)
    assert not offenders, (
        "these resume a bridge without settling its reader thread, which "
        f"segfaults an xdist worker at random: {offenders}")

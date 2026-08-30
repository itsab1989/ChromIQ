"""#159: a refused reading was announced only in the log.

The owner, 2026-08-30, with a screenshot of it as grey text under the buttons:

    *"a message like this would be better in a pop up so the user is aware of
    it instead of ruining a whole measurement session when this is unnoticed"*

He has the cost exactly right. The failure itself is cheap — one button press,
and the bridge arms the patch again by itself. NOT NOTICING is what ruins the
session: the instrument sits waiting, the operator believes they have already
pressed it, and nothing moves.

M-CR30-READ-FAILED (§M-PROPOSED).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                     # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget                 # noqa: E402

from ui.tabs.tab_measure import TabMeasure                        # noqa: E402


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


class _Log:
    def __init__(self):
        self.lines: list[str] = []

    def appendPlainText(self, t):
        self.lines.append(t)

    def ensureCursorVisible(self):
        pass


class _Tab(QWidget):
    _on_cr30_read_failed = TabMeasure._on_cr30_read_failed
    _show_cr30_read_failed_window = TabMeasure._show_cr30_read_failed_window
    _close_cr30_read_failed_window = TabMeasure._close_cr30_read_failed_window
    _close_measurement_windows = TabMeasure._close_measurement_windows
    _forget_measure_window = TabMeasure._forget_measure_window

    def __init__(self):
        super().__init__()
        self._log = _Log()
        self._live_measure_windows: list = []
        self.flashed: list = []

    def _flash_status(self, text, duration_ms=0):
        self.flashed.append(text)


REASON = "the instrument did not return a complete reading"


def test_a_failed_reading_opens_a_window(app):
    tab = _Tab()
    tab._on_cr30_read_failed("A3", REASON)
    try:
        assert tab._live_measure_windows, (
            "the refusal was announced only in the log — the place he did not "
            "see it")
        assert tab._live_measure_windows[0].isVisible()
    finally:
        tab._close_measurement_windows()


def test_the_window_names_the_patch_and_says_what_to_do(app):
    tab = _Tab()
    tab._on_cr30_read_failed("A3", REASON)
    try:
        dlg = tab._live_measure_windows[0]
        from PyQt6.QtWidgets import QLabel
        said = " ".join(l.text() for l in dlg.findChildren(QLabel))
        assert "A3" in said, "the window does not say which patch"
        assert "press the button" in said.lower(), (
            "the window does not say what to do about it")
        assert REASON in said, "the instrument's own words were dropped"
    finally:
        tab._close_measurement_windows()


def test_it_is_modeless_so_the_remedy_is_reachable(app):
    """The remedy is to press the instrument's button. A modal window would
    stand between the user and the only thing that fixes it."""
    tab = _Tab()
    tab._on_cr30_read_failed("A3", REASON)
    try:
        assert not tab._live_measure_windows[0].isModal(), (
            "a modal window blocks the retry it is asking for")
    finally:
        tab._close_measurement_windows()


def test_the_log_still_says_it_too(app):
    """The window is added, not substituted: the log is the record somebody
    reads back afterwards."""
    tab = _Tab()
    tab._on_cr30_read_failed("A3", REASON)
    try:
        assert any("A3" in l for l in tab._log.lines)
    finally:
        tab._close_measurement_windows()


def test_one_window_per_patch_not_one_per_refusal(app):
    """A flaky link refuses the same patch up to five times. Five windows for
    one stuck patch is a worse interface than none."""
    tab = _Tab()
    for _ in range(5):
        tab._on_cr30_read_failed("A3", REASON)
    try:
        assert len(tab._live_measure_windows) == 1, (
            f"{len(tab._live_measure_windows)} windows for one patch")
        assert len(tab._log.lines) == 5, (
            "the log must still record every refusal")
    finally:
        tab._close_measurement_windows()


def test_a_different_patch_gets_its_own_window(app):
    tab = _Tab()
    tab._on_cr30_read_failed("A3", REASON)
    first = tab._live_measure_windows[0]
    tab._on_cr30_read_failed("A4", REASON)
    try:
        assert not first.isVisible(), "the window for A3 is still up on A4"
        assert len(tab._live_measure_windows) == 1
    finally:
        tab._close_measurement_windows()


def test_it_closes_itself_when_the_chart_moves_on(app):
    """The whole promise the text makes: "This window will close by itself when
    the reading comes through." The chart advancing IS that."""
    tab = _Tab()
    tab._on_cr30_read_failed("A3", REASON)
    dlg = tab._live_measure_windows[0]
    assert dlg.isVisible()

    tab._close_cr30_read_failed_window()     # what _on_patch_ready calls
    app.processEvents()

    assert not dlg.isVisible(), "the window outstayed the problem"


def test_closing_it_by_hand_does_not_silence_the_next_one(app):
    """The 'already asked about this patch' flag must not outlive the window —
    otherwise a user who closes it never hears about that patch again."""
    tab = _Tab()
    tab._on_cr30_read_failed("A3", REASON)
    tab._live_measure_windows[0].accept()          # the user closes it
    app.processEvents()

    tab._on_cr30_read_failed("A3", REASON)
    try:
        assert tab._live_measure_windows, (
            "the second refusal of A3 was silent")
    finally:
        tab._close_measurement_windows()


def test_the_ending_takes_the_window_with_it(app):
    """Knut, beta.139: when the measurement ends, everything relating to it
    ends."""
    tab = _Tab()
    tab._on_cr30_read_failed("A3", REASON)
    dlg = tab._live_measure_windows[0]
    tab._close_measurement_windows()
    app.processEvents()
    assert not dlg.isVisible()


def test_the_instrument_words_never_say_s_in_brackets():
    """The screenshot that prompted all this also showed "1 candidate(s)".
    The project writes singular and plural out."""
    from workflow.cr30.device import MeasurementError
    import inspect
    import workflow.cr30.device as device
    import workflow.cr30.usb_measure as usb
    for mod in (device, usb):
        src = inspect.getsource(mod)
        for bad in ('candidate(s)', 'reading(s)', 'chunk(s)', 'patch(es)'):
            assert bad not in src.replace('"(s)"', ''), (
                f"{mod.__name__} still ships {bad!r}")

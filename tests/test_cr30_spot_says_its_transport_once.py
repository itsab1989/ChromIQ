"""The spot window says "Connected to your CR30 over ..." ONCE per connection.

Beta 17 review of afa1aaf81: Tools > Read single patches printed the line
twice in a row. The shared calibration (ui/cr30_calibration.py) writes it as
its last note, and `Cr30SpotManager.start` wrote it again on the next line.

RUN, NOT READ: the real `SpotReadDialog._start_cr30_session`, the real shared
calibration and the real `Cr30SpotManager` with its read loop. Faked: the
reader (no instrument may be opened), the calibration command, and the modal
windows.

Still said when it is news: a session whose calibration did not say it, and a
reconnect, which is a new connection.
"""
from __future__ import annotations

import os
import threading
import time
import types

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox            # noqa: E402

from core.argyll_runner import ArgyllRunner                      # noqa: E402
from core.settings import AppSettings                            # noqa: E402

NOTE = "Connected to your CR30 over"


class _FakeDev:
    def __init__(self, kind):
        self.kind = kind
        self.learned_tile = None
        self._t = types.SimpleNamespace(address="AA:BB:CC", port="/dev/fake")

    def close(self):
        pass


class _FakeReader:
    """The DeviceReader surface the spot session uses; opens nothing."""

    def __init__(self, kind):
        self._dev = _FakeDev(kind)
        self._kind_again = kind
        self.guard_is_armed = True
        self.button_timeout_s = 30.0
        self._cancel = threading.Event()

    @property
    def open_transport(self):
        return self._dev.kind

    def calibrate(self, black=False):
        return None

    def open_now(self):
        if self._dev is None:           # a reconnect opens it afresh
            self._dev = _FakeDev(self._kind_again)

    def drop_stale_presses(self):
        return 0

    def arm_trigger(self, token):
        pass

    def disarm_trigger(self):
        pass

    def cancel(self):
        self._cancel.set()

    def close(self):
        self._cancel.set()

    def __call__(self, generation=None):
        from workflow.cr30.measurement import MeasurementError
        self._cancel.wait(0.05)
        raise MeasurementError("no button press within 30 s")


def _answer_modals(monkeypatch):
    def _exec(self):
        buttons = self.buttons()
        if buttons:
            buttons[0].click()          # "Calibrate now" / "Reconnect" / OK
        return 0
    monkeypatch.setattr(QMessageBox, "exec", _exec, raising=False)


def _dialog(monkeypatch, kind, *, calibrate=True):
    from ui.dialogs.spot_read_dialog import SpotReadDialog

    QApplication.instance() or QApplication([])
    s = AppSettings()
    dlg = SpotReadDialog(ArgyllRunner(s), s)
    reader = _FakeReader(kind)

    def _open():
        dlg._cr30_reader = reader

    def _close():
        dlg._cr30_reader = None

    monkeypatch.setattr(dlg, "_open_cr30_bridge", _open)
    monkeypatch.setattr(dlg, "_close_cr30_bridge", _close)
    monkeypatch.setattr(dlg, "_offer_cr30_tile_learning", lambda r: None)
    monkeypatch.setattr(dlg, "_show_cr30_measuring_window", lambda: None)
    if not calibrate:
        def _no_calibration(*, keep_bridge=False):
            _open()
            return True
        monkeypatch.setattr(dlg, "_run_cr30_calibration", _no_calibration)
    _answer_modals(monkeypatch)
    return dlg


def _wait(predicate, seconds=5.0):
    app = QApplication.instance()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    return False


def _notes(dlg):
    return [ln for ln in dlg._log.toPlainText().splitlines() if NOTE in ln]


def _ready(dlg):
    return dlg._cr30 is not None and dlg._read_btn.isEnabled()


def _end(dlg):
    if dlg._cr30 is not None:
        dlg._end_cr30_session()
    dlg._unsaved = False
    dlg.deleteLater()


@pytest.mark.parametrize("kind, words", [("ble", "over Bluetooth"),
                                         ("usb", "over the USB cable")])
def test_the_connection_is_named_once_after_the_calibration(
        monkeypatch, kind, words):
    dlg = _dialog(monkeypatch, kind)
    try:
        dlg._start_cr30_session()
        assert _wait(lambda: _ready(dlg)), "the window never said Ready"
        notes = _notes(dlg)
        assert len(notes) == 1, (
            "the spot window's log names the connection "
            f"{len(notes)} times, expected once:\n" + dlg._log.toPlainText())
        assert words in notes[0]
    finally:
        _end(dlg)


def test_without_the_calibrations_note_the_session_still_names_it(
        monkeypatch):
    dlg = _dialog(monkeypatch, "ble", calibrate=False)
    try:
        dlg._start_cr30_session()
        assert _wait(lambda: _ready(dlg)), "the window never said Ready"
        assert len(_notes(dlg)) == 1, dlg._log.toPlainText()
    finally:
        _end(dlg)


def test_a_reconnect_names_the_new_connection(monkeypatch):
    dlg = _dialog(monkeypatch, "ble")
    try:
        dlg._start_cr30_session()
        assert _wait(lambda: _ready(dlg)), "the window never said Ready"
        # As after a real loss: the reader has let go of its dead handle,
        # and the instrument comes back over the other transport.
        reader = dlg._cr30_reader
        reader._dev = None
        reader._kind_again = "usb"
        dlg._cr30.reconnect()
        assert _wait(lambda: len(_notes(dlg)) == 2 and _ready(dlg)), (
            "a reconnect did not say which way it connected:\n"
            + dlg._log.toPlainText())
        assert "USB cable" in _notes(dlg)[1]
    finally:
        _end(dlg)


def test_a_second_session_in_the_same_window_names_it_once_again(
        monkeypatch):
    """The flag is per Start: Stop, Start again, and the line appears once
    more (a new connection), not zero times and not twice."""
    dlg = _dialog(monkeypatch, "ble")
    try:
        dlg._start_cr30_session()
        assert _wait(lambda: _ready(dlg))
        dlg._end_cr30_session()
        dlg._start_cr30_session()          # clears the log, calibrates again
        assert _wait(lambda: _ready(dlg))
        assert len(_notes(dlg)) == 1, dlg._log.toPlainText()
    finally:
        _end(dlg)

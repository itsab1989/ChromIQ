"""d8ceaca8: the Measure tab now says which way it connected. Does it, really?

RUN, NOT READ. Three tests covering this same calibration flow once passed
through a TypeError that made every CR30 measurement impossible, because all
three read `inspect.getsource` instead of calling the method
(`measure_bridge.DeviceReader.calibrate`'s own docstring says so). So these
drive the real `_run_cr30_calibration` on a real `TabMeasure` and read the real
log pane. Only three things are faked, and none of them is the code under test:

* the DEVICE — a stub with a `kind`, because the constraint for this whole
  round is that no CR30 and no serial or Bluetooth device may be touched;
* the CALIBRATION COMMAND — a no-op, for the same reason;
* the two MODAL windows — answered from the test, because a modal in a suite
  waits for ever.
"""
from __future__ import annotations

import os
import types

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox            # noqa: E402

from core.argyll_runner import ArgyllRunner                      # noqa: E402
from core.settings import AppSettings                            # noqa: E402
from ui.tabs.tab_measure import TabMeasure                       # noqa: E402


@pytest.fixture
def tab():
    QApplication.instance() or QApplication([])
    s = AppSettings()
    return TabMeasure(ArgyllRunner(s), s)


class _FakeDev:
    """Only what the transport note and the calibration path read."""
    def __init__(self, kind):
        self.kind = kind
        self.learned_tile = None
        self._t = types.SimpleNamespace(address="AA:BB:CC", port="/dev/fake")

    def calibrate(self, black=False):
        return None

    def close(self):
        return None


class _FakeReader:
    """The real DeviceReader's surface, minus anything that opens hardware."""
    def __init__(self, kind):
        self._dev = _FakeDev(kind)
        self.guard_is_armed = True

    def calibrate(self, black=False):
        return None

    def close(self):
        return None


def _answer_modals(monkeypatch, accept=True):
    """Click the accepting button on every QMessageBox this flow opens.

    Patched on the CLASS and restored by monkeypatch, because a hand-rolled
    save/restore of `QMessageBox.exec` does NOT restore it — that leak is a
    documented cross-test fault in this suite (b30b0ad8).
    """
    def _exec(self):
        buttons = self.buttons()
        if not buttons:
            return QMessageBox.StandardButton.Ok
        wanted = buttons[0] if accept else buttons[-1]
        self.setResult(0)
        # `clickedButton()` reads the button the box recorded, so press it.
        self.buttonClicked.emit(wanted)
        for b in buttons:
            if b is wanted:
                b.click()
                break
        return 0
    monkeypatch.setattr(QMessageBox, "exec", _exec, raising=False)


def _run_calibration(tab, monkeypatch, kind):
    """Drive the REAL method with only the device faked. Returns the log text."""
    reader = _FakeReader(kind)
    # The bridge is what the method reaches for; give it the fake reader and
    # stop it standing up a real one (which would open an instrument).
    monkeypatch.setattr(tab, "_open_cr30_bridge", lambda: None)
    monkeypatch.setattr(tab, "_close_cr30_bridge", lambda: None)
    monkeypatch.setattr(tab, "_offer_cr30_tile_learning", lambda r: None)
    tab._cr30_reader = reader
    tab._cr30_bridge = object()
    _answer_modals(monkeypatch, accept=True)
    tab._log.clear()
    tab._run_cr30_calibration()
    return tab._log.toPlainText()


# ---------------------------------------------------------------------------
# 1. The note appears, and it names the transport it was actually given.
# ---------------------------------------------------------------------------

def test_it_names_the_cable_when_the_cable_was_used(tab, monkeypatch):
    text = _run_calibration(tab, monkeypatch, "usb")
    assert "USB cable" in text, (
        "the session log does not say the instrument was reached over USB:\n"
        + text)
    assert "Bluetooth" not in text.split("USB cable")[0], (
        "it named Bluetooth on a cable session")


def test_it_names_bluetooth_when_bluetooth_was_used(tab, monkeypatch):
    text = _run_calibration(tab, monkeypatch, "ble")
    assert "over Bluetooth" in text, (
        "the session log does not say the instrument was reached over "
        "Bluetooth:\n" + text)
    assert "USB cable" not in text, "it named the cable on a Bluetooth session"


def test_a_remembered_address_still_names_bluetooth(tab, monkeypatch):
    """The fast path skips discovery but still builds `CR30(t, "ble")`, so
    `kind` is unchanged. Pinned because the whole repair feature routes users
    onto that path, and it is the one that would silently lose the note."""
    reader = _FakeReader("ble")
    reader._dev._t.address = "REMEMBERED-ADDRESS"
    monkeypatch.setattr(tab, "_open_cr30_bridge", lambda: None)
    monkeypatch.setattr(tab, "_close_cr30_bridge", lambda: None)
    monkeypatch.setattr(tab, "_offer_cr30_tile_learning", lambda r: None)
    tab._cr30_reader = reader
    tab._cr30_bridge = object()
    _answer_modals(monkeypatch, accept=True)
    tab._log.clear()
    tab._run_cr30_calibration()
    assert "over Bluetooth" in tab._log.toPlainText()


def test_an_unknown_kind_says_nothing_rather_than_guessing(tab, monkeypatch):
    """`kind` is "" only if the device never opened. Naming a transport then
    would be an invention, and this note's entire value is that it is not."""
    text = _run_calibration(tab, monkeypatch, "")
    assert "USB cable" not in text and "over Bluetooth" not in text


# ---------------------------------------------------------------------------
# 2. THE GAP. Manual + "Skip initial calibration" never reaches this method.
# ---------------------------------------------------------------------------

def test_skipping_the_calibration_leaves_the_transport_unnamed():
    """⚠ A REAL HOLE, pinned so it is a decision and not a surprise.

    `_on_start` guards the whole calibration on
    `params.external_values and not params.disable_initial_cal`, and the note
    lives INSIDE it. So a Manual user who ticks "Skip initial calibration (-N)"
    is told nothing about the transport — and that user is disproportionately
    the one debugging a connection, because skipping is what you do on the
    second and third attempt.

    Guided is unaffected: `disable_initial_cal` is hard-coded False there.
    """
    import inspect
    start = inspect.getsource(TabMeasure._on_start)
    guard = next(l for l in start.splitlines()
                 if "if params.external_values" in l)
    assert "not params.disable_initial_cal" in guard

    body = inspect.getsource(TabMeasure._calibrate_and_confirm)
    assert "Connected to your CR30 over" in body, (
        "the transport note has moved; re-check whether it is still gated by "
        "the skip-calibration guard")
    assert "Connected to your CR30 over" not in start, (
        "GOOD NEWS, DELETE THIS TEST: the note now also runs on the path that "
        "skips the calibration, so the gap this pins is closed")

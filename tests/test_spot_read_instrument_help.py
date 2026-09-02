"""Read single patches: which reader "Detect automatically" picks, and the
drawn instrument in the windows that ask for a physical move.

Both come from the same session on real hardware, 2026-09-02. He tried the tool
with a CR30 paired over Bluetooth and with a ColorMunki, and reported:

    *"automatically detecting the cr30 via blutooth did not seem to work …
    however i noticed it did not use the nice graphics to help the user during
    calibration (calibration position and measurement position). those things
    are probably true for the cr30 as well."*

His log shows what automatic actually did: it ran `spotread -v -c 1`, i.e. it
took the ArgyllCMS path, and spotread offered him
``1 = '/dev/cu.Bluetooth-Incoming-Port'`` — macOS's own incoming serial port.
ArgyllCMS cannot drive a CR30 at all, so that route could only ever end in
"no instrument detected".
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402

from core.argyll_runner import ArgyllRunner       # noqa: E402
from core.settings import AppSettings             # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def dialog(qapp, tmp_path):
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    dlg = SpotReadDialog(ArgyllRunner(s), s, None)
    yield dlg
    dlg.deleteLater()


# ----------------------------------------------------------------------
# Detect automatically
# ----------------------------------------------------------------------
def test_a_bluetooth_cr30_can_never_be_a_usb_candidate():
    """The reason automatic could not see it, stated where it cannot rot.

    `discovery.candidates()` filters on the CH340 bridge's VID:PID, and a
    Bluetooth CR30 is not a USB serial port at all — it has neither.
    """
    from workflow.cr30.discovery import Candidate
    bluetooth_ish = Candidate("/dev/cu.CR30-BLE", None, None, "CR30")
    assert not bluetooth_ish.is_ch34x


def test_automatic_picks_the_cr30_when_this_mac_has_used_one_over_bluetooth(
        dialog, monkeypatch):
    import ui.dialogs.spot_read_dialog as mod
    monkeypatch.setattr(mod, "cr30_is_probably_attached", lambda: False)
    monkeypatch.setattr(mod, "cr30_is_remembered_over_bluetooth", lambda: True)
    dialog._instrument.setCurrentIndex(0)          # Detect automatically
    assert dialog._chosen_reader() == "cr30"


def test_automatic_still_picks_the_cr30_on_usb(dialog, monkeypatch):
    import ui.dialogs.spot_read_dialog as mod
    monkeypatch.setattr(mod, "cr30_is_probably_attached", lambda: True)
    monkeypatch.setattr(mod, "cr30_is_remembered_over_bluetooth", lambda: False)
    dialog._instrument.setCurrentIndex(0)
    assert dialog._chosen_reader() == "cr30"


def test_automatic_falls_back_to_argyll_with_no_cr30_evidence(dialog,
                                                              monkeypatch):
    """A ColorMunki owner must not be handed ChromIQ's CR30 reader."""
    import ui.dialogs.spot_read_dialog as mod
    monkeypatch.setattr(mod, "cr30_is_probably_attached", lambda: False)
    monkeypatch.setattr(mod, "cr30_is_remembered_over_bluetooth", lambda: False)
    dialog._instrument.setCurrentIndex(0)
    assert dialog._chosen_reader() == "argyll"


def test_the_bluetooth_hint_reads_one_remembered_setting_and_nothing_else():
    """No scan, no open, no write. A 15 s Bluetooth scan (measured on his own
    Mac) is not something to spend before a dropdown can answer, and the
    remembered address is only written after `identify()` has come back with
    the model string."""
    from ui.dialogs.spot_read_dialog import cr30_is_remembered_over_bluetooth
    src = inspect.getsource(cr30_is_remembered_over_bluetooth)
    assert "_remembered_address" in src
    for forbidden in ("scan", "discover", "connect(", "open("):
        assert forbidden not in src.split('"""')[-1], forbidden


def test_picking_the_cr30_by_hand_is_honoured(dialog):
    """The more important half: he can also choose it explicitly, and that
    path uses `DeviceReader`, which tries USB and Bluetooth."""
    dialog._instrument.setCurrentIndex(2)          # CR30 (ChnSpec)
    assert dialog._chosen_reader() == "cr30"

    from workflow.cr30.measure_bridge import DeviceReader
    sig = inspect.signature(DeviceReader.__init__)
    assert sig.parameters["transport"].default == "auto", (
        "the explicit CR30 choice must still try both transports")
    src = inspect.getsource(DeviceReader)
    assert "_open_ble" in src and "_open_usb" in src


# ----------------------------------------------------------------------
# The drawn instrument
# ----------------------------------------------------------------------
def _pixmap_labels(widget) -> list:
    return [w for w in widget.findChildren(QLabel)
            if w.pixmap() is not None and not w.pixmap().isNull()]


WINDOWS = [
    ("_on_calibration_prompt", "calibrate"),
    ("_on_calibration_position_wrong", "calibrate"),
    ("_on_calibration_finished", "measure"),
    ("_on_sensor_wrong_position", "measure"),
]


@pytest.mark.parametrize("method,position", WINDOWS)
def test_every_positioning_window_draws_the_colormunki_dial(
        dialog, monkeypatch, method, position):
    """He has these in the Measure tab and had none of them here."""
    dialog._detected_instrument = "ColorMunki"
    seen = {}

    from ui import dial_pictogram
    real = dial_pictogram.dial

    def spy(pos, widget=None, size=260):
        seen["position"] = pos
        return real(pos, widget, size)

    monkeypatch.setattr(dial_pictogram, "dial", spy)
    monkeypatch.setattr("PyQt6.QtWidgets.QDialog.exec", lambda self: 0)
    monkeypatch.setattr("PyQt6.QtWidgets.QMessageBox.exec", lambda self: 0)
    getattr(dialog, method)()
    assert seen.get("position") == position, (
        f"{method} must show the wheel turned to the {position} mark")


@pytest.mark.parametrize("method,_position", WINDOWS)
@pytest.mark.parametrize("reported", ["i1Pro", "", "SpectroScan"])
def test_no_dial_for_an_instrument_that_has_no_dial(
        dialog, monkeypatch, method, _position, reported):
    """The drawing is a ColorMunki's wheel. An i1Pro has none, and offering a
    picture of somebody else's device is worse than words alone — the same
    rule `ui/dial_pictogram.py` and the Measure tab already keep."""
    dialog._detected_instrument = reported
    from ui import dial_pictogram
    called = []
    monkeypatch.setattr(dial_pictogram, "dial",
                        lambda *a, **k: called.append(a) or None)
    monkeypatch.setattr("PyQt6.QtWidgets.QDialog.exec", lambda self: 0)
    monkeypatch.setattr("PyQt6.QtWidgets.QMessageBox.exec", lambda self: 0)
    getattr(dialog, method)()
    assert called == [], f"{method} drew a dial for {reported!r}"


def test_the_buttons_do_not_move_into_the_text_column(dialog, monkeypatch):
    """The picture takes a column and the text takes the column beside it —
    but the buttons belong to the dialog, not to the text. Putting them in the
    column shrinks them to the text's width, which is what the Measure tab's
    `_outer` exists to prevent."""
    from PyQt6.QtWidgets import QDialog, QDialogButtonBox

    dialog._detected_instrument = "ColorMunki"
    grabbed = {}

    def capture(self):
        grabbed["dlg"] = self
        return 0

    monkeypatch.setattr(QDialog, "exec", capture)
    dialog._on_calibration_prompt()
    dlg = grabbed["dlg"]
    box = dlg.findChild(QDialogButtonBox)
    assert box is not None
    # the button box's parent layout is the dialog's own, not the text column
    assert dlg.layout().indexOf(box) >= 0, (
        "the buttons were put in the text column beside the picture")

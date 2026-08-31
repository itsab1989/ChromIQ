"""Report 55: does the transport note actually appear on screen, and read well?

DRIVES THE REAL APP. It builds the real MainWindow, takes its real Measure tab,
and calls the real `_run_cr30_calibration()`. Only three things are faked, and
none of them is the code being judged:

* the DEVICE — a stub with a `kind`. No CR30, no serial port, no Bluetooth
  connection is touched; that is the standing constraint for this whole round.
* the CALIBRATION COMMAND — a no-op, for the same reason.
* the MODAL WINDOWS — answered by a timer that clicks their accepting button.
  A driver that blocks on a modal gets clicked by a human, and every result
  after that point is human-assisted rather than proof.

Writes PNGs of the Measure tab's session log for both transports.

    python scripts/drive_55_transport_note.py <out-dir>
"""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/drive55")
OUT.mkdir(parents=True, exist_ok=True)

# SANDBOX BEFORE ANYTHING IMPORTS SETTINGS. An on-screen driver writes to the
# user's REAL preferences and preset folder otherwise; one leak once broke every
# project lookup on this machine.
SANDBOX = OUT / "sandbox"
(SANDBOX / "presets").mkdir(parents=True, exist_ok=True)
(SANDBOX / "output").mkdir(parents=True, exist_ok=True)
os.environ["CHROMIQ_PRESETS_DIR"] = str(SANDBOX / "presets")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QTimer                                  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox            # noqa: E402

from core.argyll_runner import ArgyllRunner                      # noqa: E402
from core.settings import AppSettings                            # noqa: E402
from ui.main_window import MainWindow                            # noqa: E402


class _FakeDev:
    def __init__(self, kind):
        self.kind = kind
        self.learned_tile = None
        self._t = types.SimpleNamespace(address="AA:BB:CC:DD:EE:FF",
                                        port="/dev/cu.usbserial-10")

    def calibrate(self, black=False):
        return None

    def close(self):
        return None


class _FakeReader:
    def __init__(self, kind, armed=True):
        self._dev = _FakeDev(kind)
        # False makes the tile-learning offer actually appear, which appends
        # MORE lines after the transport note — the same way the note used to
        # be pushed off the bottom by the calibration note.
        self.guard_is_armed = armed
        self.MAX_LEARNING_PRESSES = 3

    def learn_tile(self, **kw):
        return {"learned": False, "provenance": "", "presses": 0}

    def calibrate(self, black=False):
        return None

    def close(self):
        return None


def _click_modals(app):
    """Answer any modal that appears, and NEVER leave one waiting."""
    def tick():
        w = app.activeModalWidget()
        if isinstance(w, QMessageBox):
            buttons = w.buttons()
            if buttons:
                buttons[0].click()          # the accepting button
    t = QTimer()
    t.timeout.connect(tick)
    t.start(120)
    return t


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    settings = AppSettings()
    settings.set("custom_output_path", str(SANDBOX / "output"))
    # The log pane's height is a user setting, and it decides whether the note
    # can be SEEN at all. Driven at both the shipped default and whatever this
    # machine is actually set to, because they differ.
    lines = int(os.environ.get("DRIVE55_LOG_LINES", "0"))
    if lines:
        settings.set("log_visible_lines", lines)

    win = MainWindow(settings)
    if lines:
        # What the settings dialog itself does after changing the value, or the
        # panes keep the height they were polished with.
        from ui.widgets import refresh_log_panes_from_settings
        refresh_log_panes_from_settings()
    w, h = (int(x) for x in os.environ.get("DRIVE55_SIZE", "1280x900").split("x"))
    win.resize(w, h)
    win.show()
    app.processEvents()

    tab = None
    for i in range(win._tabs.count() if hasattr(win, "_tabs") else 0):
        w = win._tabs.widget(i)
        if type(w).__name__ == "TabMeasure":
            tab = w
            win._tabs.setCurrentIndex(i)
            break
    if tab is None:
        from ui.tabs.tab_measure import TabMeasure
        for w in win.findChildren(TabMeasure):
            tab = w
            break
    if tab is None:
        print("FAILED: no Measure tab found")
        return 2
    app.processEvents()

    # The panes settle on a tab change; do what the app does rather than
    # trusting the geometry of a window that has only just been shown.
    from ui.widgets import refit_log_panes
    for _ in range(3):
        app.processEvents()
        refit_log_panes()
        app.processEvents()

    keeper = _click_modals(app)
    tab._open_cr30_bridge = lambda: None
    tab._close_cr30_bridge = lambda: None
    # NOT stubbed any more: `_offer_cr30_tile_learning` appends up to six lines
    # AFTER the transport note, so stubbing it would hide the very regression
    # this run exists to look for.
    armed = os.environ.get("DRIVE55_GUARD_ARMED", "1") != "0"

    for kind, label in (("usb", "cable"), ("ble", "bluetooth")):
        tab._cr30_reader = _FakeReader(kind, armed=armed)
        tab._cr30_bridge = object()
        tab._log.clear()
        app.processEvents()
        tab._run_cr30_calibration()
        for _ in range(20):
            app.processEvents()
        png = OUT / f"measure-log-{label}-{os.environ.get("DRIVE55_LOG_LINES","asset")}-{os.environ.get("DRIVE55_SIZE","1280x900")}-armed{os.environ.get("DRIVE55_GUARD_ARMED","1")}.png"
        tab._log.grab().save(str(png))
        win.grab().save(str(OUT / f"window-{label}-{os.environ.get("DRIVE55_LOG_LINES","asset")}-{os.environ.get("DRIVE55_SIZE","1280x900")}-armed{os.environ.get("DRIVE55_GUARD_ARMED","1")}.png"))
        print(f"--- {kind} ---")
        print(tab._log.toPlainText())
        print(f"[saved {png}]")

    keeper.stop()
    # NEVER leave a modal waiting: close anything still up before quitting.
    while app.activeModalWidget() is not None:
        app.activeModalWidget().close()
        app.processEvents()
    win.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

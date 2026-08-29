"""#159 (report 17, F3): the first press after clicking a patch was always lost.

The owner, on USB and on Bluetooth both: *"initial press then said the reading
appeared while chromiq was not waiting for it. second button press took the
reading."* It cost him a press every single time he corrected a patch.

The read for the patch he was LEAVING is still blocked waiting for a button. His
next press satisfies THAT read, which then finds the prompt has moved on and is
discarded as stale. So navigating away has to let go of the old read.

Abandoning is not cancelling. `DeviceReader._cancel` means "this reader is
finished" and is never cleared; using it here would make every later patch fail
instantly — the dead session this whole line of work exists to remove.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.cr30.measure_bridge import DeviceReader              # noqa: E402
from tests.test_cr30_measure_bridge import Harness                 # noqa: E402


def test_abandoning_leaves_the_reader_usable():
    """The distinction the fix turns on."""
    r = DeviceReader()
    assert r._cancelled() is False
    r.abandon_current()
    assert r._cancelled() is False, (
        "abandoning one read ended the whole reader — every later patch would "
        "fail the instant it started")


def test_abandoning_changes_the_token_the_read_watches():
    r = DeviceReader()
    before = r._generation
    assert r.abandon_current() != before


class _AbandonableReader:
    """A reader shaped like the real one: it blocks, and it can be let go of
    without being ended. A plain callable cannot show this — the whole fix is
    the difference between abandoning one read and ending the reader."""

    def __init__(self):
        import threading
        self._generation = 0
        self.gate = threading.Event()
        self.calls = 0

    def abandon_current(self):
        self._generation += 1
        return self._generation

    def __call__(self, generation=None):
        self.calls += 1
        self.gate.wait(5)
        if generation is not None and generation != self._generation:
            raise RuntimeError("cancelled while waiting for the button")
        return (10.0, 20.0, 30.0)


def test_navigating_away_lets_go_of_the_read_in_flight():
    from workflow.cr30.measure_bridge import Cr30MeasureBridge

    reader = _AbandonableReader()
    sent: list = []
    bridge = Cr30MeasureBridge(sent.append, reader)
    bridge.on_patch_ready({"loc": "A19", "read": False, "all_done": False})
    assert bridge._reading_loc == "A19"
    gen_before = reader._generation

    bridge.note_goto("A5")

    assert bridge._reading_loc is None, (
        "the read for the patch being left is still armed, and will eat the "
        "user's next press")
    assert reader._generation != gen_before, (
        "the read in flight was never abandoned, so the operator's next press "
        "still satisfies it and is then thrown away as stale")

    reader.gate.set()                      # let the worker finish and be reaped
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QCoreApplication
    app = QApplication.instance() or QCoreApplication.instance()
    for _ in range(400):
        app.processEvents()
        if not bridge._threads:
            break
    assert sent == [], "a value from the abandoned read was sent anyway"


def test_an_abandoned_read_is_not_reported_and_does_not_re_arm():
    """Otherwise every click flashes "could not be read — press the button
    again" and burns one of the patch's retries."""
    h = Harness()
    seen: list = []
    h.bridge.read_failed.connect(lambda loc, msg: seen.append((loc, msg)))
    before = len(h.read_calls)

    h.bridge._on_read_failed("A19", "cancelled while waiting", "ReadAbandoned")

    assert seen == [], f"told the user about a read we chose to drop: {seen}"
    assert len(h.read_calls) == before, "it re-armed a patch the user left"
    assert "A19" not in h.bridge._retries

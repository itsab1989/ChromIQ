"""A "Take reading" press made before the read is listening must not vanish.

THE FAULT. `DeviceReader._reading_in_flight` becomes True inside `__call__`,
after the reader's lock is taken and after the transport is opened. Both hosts
make the control that asks for a reading live BEFORE that:

* `Cr30SpotManager.start()` emits `ready_to_read`, which is what enables the
  spot window's "Take reading" button, and only then does the reader thread get
  scheduled;
* `Cr30MeasureBridge._start_read` sets `_reading_loc` -- which is exactly what
  the Measure tab's key filter asks (`armed_for`) before it will accept Space
  at all -- before it starts the worker thread.

`request_trigger()` used to refuse for the whole of that gap and keep nothing.
The press did nothing and said nothing. On the Measure tab it did worse than
nothing: the tab does not ask `trigger_allowed()` first, so the refusal came
back as M-CR30-TRIGGER-NOT-ARMED about an instrument whose tile IS learned.

WHY THESE TESTS CAN SEE IT AND THE OLD ONES COULD NOT.
`tests/test_cr30_spot_read.py::test_take_reading_asks_the_instrument_instead_of_waiting`
passes six times out of six on its own and fails inside a parallel gate,
because the gap is only as wide as the scheduler makes it. Here the gap is held
open with the reader's OWN lock -- the one `calibrate`, `learn_tile`,
`read_zero`, `trigger_and_read` and `close` all take -- so the press lands
inside it every single time, on an idle machine, with no timing assumption at
all. Nothing about the code under test is stubbed to arrange it.

AND THE OLD RULE STILL HOLDS. A request must never be spent by a read it was
not made for: that is what fired the instrument at whatever it was resting on
and put a plausible wrong colour into a `.ti3` in silence
(`test_cr30_review43_stale_trigger.py`, `test_cr30_trigger_request_dies_with_its_read.py`).
The last two tests here are the other side of the same fix -- a press held for
one patch is thrown away the moment a different one is armed, and a press with
nothing armed at all is still refused outright.
"""
import os
import pathlib
import sys
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication                       # noqa: E402

from core import instrument_lease                              # noqa: E402
from core.settings import AppSettings                          # noqa: E402
from workflow.cr30.measure_bridge import (Cr30MeasureBridge,   # noqa: E402
                                          DeviceReader)
from workflow.cr30.measurement import Measurement              # noqa: E402
from workflow.cr30.measurement import MeasurementError         # noqa: E402
from workflow.cr30_spot_manager import NO_PRESS_MARKER         # noqa: E402
from ui.dialogs.spot_read_dialog import SpotReadDialog         # noqa: E402

WL = list(range(400, 701, 10))

#: How long the reader's lock is held, i.e. how long the reader thread is kept
#: short of its wait. Long enough that no scheduler can close the gap by luck,
#: short enough to be free in a gate.
HOLD_S = 0.4


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _a_free_instrument():
    """Nobody holds the instrument before or after. The claim is process-wide,
    so a test that left one standing would refuse the next test's session and
    the failure would land on an innocent file."""
    instrument_lease.release(instrument_lease.holder_object())
    yield
    instrument_lease.release(instrument_lease.holder_object())


@pytest.fixture(autouse=True)
def _the_remembered_instrument_is_put_back():
    """Choosing the CR30 in the window WRITES it to the settings, and the next
    window built anywhere in the process opens on it.

    Found the hard way: this file alone made
    `test_cr30_spot_read.py::test_automatic_is_the_default_and_it_means_argyllcms`
    fail, in a different file, with nothing wrong in either. `--dist loadfile`
    keeps a file on one worker but not on a process of its own, so a leak like
    this lands on whichever file happens to run next. `is_stored` is what makes
    "it was never there" restorable at all -- `get` cannot tell that from a key
    set to today's default.
    """
    settings = AppSettings()
    key = "spot_read_instrument"
    stored = settings.is_stored(key)
    before = settings.get(key) if stored else None
    yield
    if stored:
        settings.set(key, before)
    else:
        settings.unset(key)


class FakeDevice:
    """A CR30 that answers only when its button is pressed, or when the host
    asks for a reading. The same shape as `tests/test_cr30_spot_read.py`'s,
    including the full `read_next_measurement` signature."""

    def __init__(self, kind="usb", refuse_first=False):
        self.kind = kind
        self._pending = None
        self.reads = 0
        self.learned_tile = [1.0] * 31     # this unit's magnet guard is armed
        self.triggered = 0
        self.closed = False
        self.on_dropped = None
        #: Refuse the FIRST read outright, before the trigger request is even
        #: looked at. That is an ordinary refusal -- a reading rejected as a
        #: bit-identical repeat, a cap left on -- and the bridge answers it by
        #: re-arming the same patch.
        self._refuse_first = refuse_first
        self.refusals = 0

    def press(self, level=50.0):
        self._pending = Measurement(WL, [float(level)] * 31)

    def read_next_measurement(self, *, timeout=180.0, cancelled=None,
                              poll=0.01, for_learning=False,
                              trigger_wanted=None):
        if self._refuse_first:
            self._refuse_first = False
            self.refusals += 1
            raise MeasurementError("that reading was refused")
        end = time.monotonic() + timeout
        while self._pending is None:
            if trigger_wanted is not None and trigger_wanted():
                self.triggered += 1
                self.press()
                continue
            if cancelled is not None and cancelled():
                raise MeasurementError("cancelled while waiting for the "
                                       "instrument's button")
            if time.monotonic() > end:
                raise MeasurementError(f"{NO_PRESS_MARKER} {timeout:.0f} s.")
            time.sleep(0.002)
        m, self._pending = self._pending, None
        self.reads += 1
        return m

    def calibrate(self, black=False):
        pass

    def read_measurement(self, *a, **kw):
        return Measurement(WL, [0.0] * 31)

    def close(self):
        self.closed = True


class _Runner:
    """Only the ArgyllCMS process is faked; nothing on the CR30 path uses it."""

    def __init__(self):
        self.calls, self.keys, self.is_running = [], [], False

    def run(self, tool, args, cwd, on_line=None, on_finish=None,
            use_pty=False):
        self.calls.append((tool, list(args), use_pty))
        self.is_running = True

    def write_stdin(self, key):
        self.keys.append(key)

    def abort(self):
        self.is_running = False

    def forget_run_callbacks(self):
        pass


class _Dialog(SpotReadDialog):
    """The real window, with only the two modal calibration windows replaced.

    `_dev` is planted OPEN and with this unit's tile learned, because that is
    the state a real session starts in: `ui/cr30_calibration.py` opens and
    calibrates the instrument before the session begins.
    """

    def __init__(self, *a, device=None, **kw):
        self._device = device
        self.busy_windows = []
        self.trigger_windows = 0
        super().__init__(*a, **kw)

    def _run_cr30_calibration(self, *, keep_bridge=False):
        self._open_cr30_bridge()
        if self._cr30_reader is not None and self._device is not None:
            self._cr30_reader._dev = self._device
        return True

    def _show_instrument_busy(self, where):
        self.busy_windows.append(where)

    def _on_cr30_trigger_not_armed(self):
        self.trigger_windows += 1


def _wait(qapp, cond, seconds=8.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.002)
    return bool(cond())


class _HoldsTheLock:
    """Keeps the reader thread short of its wait, using the reader's own lock.

    Not a stand-in for something imaginary: every other DeviceReader entry
    point takes this lock, and while it is held `__call__` is stuck on it with
    `_reading_in_flight` still False -- which is precisely the state a slow
    scheduler produces, and the state the press has to survive.
    """

    def __init__(self, reader, seconds=HOLD_S):
        self._lock, self._seconds = reader._lock, seconds
        self._done = threading.Event()
        self._thread = None

    def __enter__(self):
        def _hold():
            with self._lock:
                self._done.wait(self._seconds)

        self._thread = threading.Thread(target=_hold, daemon=True)
        self._thread.start()
        # Let it actually take the lock before the caller starts a read.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and self._lock.acquire(blocking=False):
            self._lock.release()
            time.sleep(0.002)
        return self

    def __exit__(self, *exc):
        self._done.set()
        self._thread.join(5.0)
        return False


# ---------------------------------------------------------------------------
# 1. The spot window: the press the owner makes the instant "Ready" appears
# ---------------------------------------------------------------------------
def test_the_spot_window_keeps_a_press_made_before_the_read_opens(qapp):
    """Click "Take reading" the moment the button goes live, with the reader
    still short of its wait. The reading must arrive."""
    device = FakeDevice()
    dlg = _Dialog(_Runner(), AppSettings(), device=device)
    dlg._instrument.setCurrentIndex(2)          # the CR30 entry
    # The reader exists from here, so the gap can be held open around Start.
    dlg._open_cr30_bridge()
    dlg._cr30_reader._dev = device
    try:
        with _HoldsTheLock(dlg._cr30_reader):
            dlg._on_start_stop()
            assert _wait(qapp, lambda: dlg._read_btn.isEnabled(), 5.0), \
                "the window never offered Take reading"
            assert dlg._cr30_reader._reading_in_flight is False, (
                "the reader reached its wait anyway, so this run never "
                "entered the window under test — the harness is broken")
            dlg._on_take_reading()
        assert _wait(qapp, lambda: len(dlg._readings) == 1), (
            "the press made while the button said it was live produced no "
            "reading at all — it was dropped in silence, which is what the "
            "owner sees as a dead instrument")
        assert device.triggered == 1, (
            f"the instrument was fired {device.triggered} times for one press")
        assert dlg.trigger_windows == 0, (
            "the press was answered with M-CR30-TRIGGER-NOT-ARMED about an "
            "instrument whose tile is learned")
    finally:
        if dlg._cr30 is not None:
            dlg._cr30.quit()
            dlg._cr30.detach()
        dlg._release_instrument()


# ---------------------------------------------------------------------------
# 2. The Measure tab: Space, in the same gap, on the shared bridge
# ---------------------------------------------------------------------------
def test_the_measure_tab_keeps_a_press_made_before_the_read_opens(qapp):
    """`armed_for` is what the tab's key filter gates Space on, and
    `_start_read` sets it before the worker thread exists. Every fact the tab
    reads to choose its branch is asserted here, because the wrong branch put a
    false sentence on screen rather than merely losing the key."""
    device = FakeDevice()
    reader = DeviceReader()
    reader._dev = device
    reader.button_timeout_s = 5.0
    sent: list = []
    bridge = Cr30MeasureBridge(sent.append, reader)
    try:
        with _HoldsTheLock(reader):
            bridge.on_patch_ready({"loc": "A1"})
            qapp.processEvents()
            assert bridge.armed_for("A1"), (
                "the bridge is not armed, so the tab would not have accepted "
                "the key at all — the harness is broken")
            assert reader.trigger_allowed(), (
                "this unit's tile is not learned, so the refusal under test "
                "would be the correct one")
            assert reader._reading_in_flight is False, (
                "the read opened anyway; this run never entered the window")
            assert reader.request_trigger() is True, (
                "Space was refused while the patch was armed — the tab then "
                "shows M-CR30-TRIGGER-NOT-ARMED, which is untrue here, and "
                "the keystroke is gone")
        assert _wait(qapp, lambda: device.triggered == 1, 6.0), (
            "the accepted request never reached the instrument")
        assert _wait(qapp, lambda: sent and sent[-1].get("cmd") == "value"), (
            "the reading never went back to the helper")
    finally:
        bridge.stop()
        reader.close()
        qapp.processEvents()


# ---------------------------------------------------------------------------
# 3. …and the reason the old code refused is still honoured
# ---------------------------------------------------------------------------
def test_a_press_held_for_one_patch_is_thrown_away_when_another_is_armed(qapp):
    """THE HAZARD THE REFUSAL EXISTED FOR, and it must stay impossible.

    A request kept past the read it was made for used to be spent by the next
    patch's read on its first iteration — firing the instrument at whatever it
    was resting on, with nobody having pressed anything, and sending the
    plausible reading back as that patch's colour in silence.

    Holding a press is now safe only because it is held FOR something: arming a
    different patch discards it. Here the press is made for A1, A1 is
    abandoned, A2 is armed, and A2 must wait for the operator.
    """
    device = FakeDevice()
    reader = DeviceReader()
    reader._dev = device
    reader.button_timeout_s = 0.3
    sent: list = []
    bridge = Cr30MeasureBridge(sent.append, reader)
    try:
        with _HoldsTheLock(reader, seconds=0.6):
            bridge.on_patch_ready({"loc": "A1"})
            qapp.processEvents()
            assert reader.request_trigger() is True, "the press for A1 was refused"
            # The user clicks a different patch. The read for A1 is given up
            # and the prompt moves on; nothing was pressed for A2.
            bridge.note_goto("A2")
            bridge.on_patch_ready({"loc": "A2"})
            qapp.processEvents()
            assert reader._trigger_requested is False, (
                "the press made for A1 is still standing while A2 is armed — "
                "A2's read will fire the instrument at whatever it is sitting "
                "on and record the answer as A2's colour")
        # And prove it behaviourally, not only by the flag: A2's read must end
        # in the honest button-press timeout with the instrument untouched.
        assert _wait(qapp, lambda: device.triggered > 0 or not bridge.armed_for("A2"),
                     6.0)
        assert device.triggered == 0, (
            "the stale press fired the instrument for a patch nobody asked to "
            "read")
    finally:
        bridge.stop()
        reader.close()
        qapp.processEvents()


def test_arming_a_second_patch_over_a_live_one_discards_the_press(qapp):
    """THE SAME HAZARD BY THE ONE ROUTE THAT DOES NOT PASS THROUGH A DISARM.

    Every ordinary way a patch stops being read -- a reading, a failure, a
    navigation -- clears `_reading_loc` first, and clearing it disarms. But the
    helper can prompt for a NEW patch while the old read is still running: the
    already-read branch of `on_patch_ready` sends `next_unread`, and the answer
    is a `spot_ready` for a different loc which goes straight to `_start_read`
    and arms over the top of a live one. That is the arm-to-arm transition, and
    `arm_trigger`'s token comparison is the only thing standing in it.

    Without this test that comparison can be deleted and every other test here
    still passes -- which is exactly what the mutation run found.
    """
    device = FakeDevice()
    reader = DeviceReader()
    reader._dev = device
    reader.button_timeout_s = 0.3
    sent: list = []
    bridge = Cr30MeasureBridge(sent.append, reader)
    try:
        with _HoldsTheLock(reader, seconds=0.6):
            bridge.on_patch_ready({"loc": "A1"})
            qapp.processEvents()
            assert reader.request_trigger() is True, "the press for A1 was refused"
            # A prompt for a different patch, with A1's read still standing.
            bridge.on_patch_ready({"loc": "A2"})
            qapp.processEvents()
            assert bridge.armed_for("A2"), (
                "the second prompt did not re-arm, so this run never made the "
                "arm-to-arm transition — the harness is broken")
            assert reader._trigger_requested is False, (
                "the press made for A1 survived into A2's read; A2 will fire "
                "the instrument at whatever it is sitting on and the answer "
                "goes into the .ti3 as A2's colour")
        assert _wait(qapp, lambda: device.triggered > 0, 3.0) is False, (
            "the stale press fired the instrument for a patch nobody asked to "
            "read")
    finally:
        bridge.stop()
        reader.close()
        qapp.processEvents()


def test_a_refused_read_does_not_hand_its_press_to_the_retry(qapp):
    """A press is spent by the read it was made for, ONCE, even when that read
    ends in a refusal.

    The bridge answers an ordinary refusal by re-arming the SAME patch, so the
    arm token does not change and `arm_trigger` has nothing to discard. If the
    press survived, the retry would fire the instrument the instant it opened
    with nobody having pressed anything for it -- which is how a plausible
    wrong colour went into a `.ti3` in silence, and the reason the operator
    must be the one who says "again". Clearing it is `_reading_loc`'s disarm,
    and this is the only test that can see that line.
    """
    device = FakeDevice(refuse_first=True)
    reader = DeviceReader()
    reader._dev = device
    reader.button_timeout_s = 0.4
    sent: list = []
    bridge = Cr30MeasureBridge(sent.append, reader)
    try:
        with _HoldsTheLock(reader, seconds=0.3):
            bridge.on_patch_ready({"loc": "A1"})
            qapp.processEvents()
            assert reader.request_trigger() is True, "the press for A1 was refused"
        assert _wait(qapp, lambda: device.refusals == 1, 5.0), (
            "the first read never ran, so nothing was refused — the harness "
            "is broken")
        assert _wait(qapp, lambda: bridge.armed_for("A1"), 5.0), (
            "the bridge did not re-arm the patch after the refusal")
        # Let the retry live out its whole wait.
        _wait(qapp, lambda: False, 1.0)
        assert device.triggered == 0, (
            "the press made for the read that was refused was handed to the "
            "retry, which fired the instrument at whatever it was sitting on "
            "without the operator asking again")
    finally:
        bridge.stop()
        reader.close()
        qapp.processEvents()


def test_a_press_with_nothing_armed_at_all_is_still_refused():
    """An idle reader keeps nothing. No session, no patch, no read: there is
    nothing for a press to belong to, so it is refused outright rather than
    stored for whatever comes next."""
    device = FakeDevice()
    reader = DeviceReader()
    reader._dev = device                 # an opened session, as __call__ leaves it
    assert reader.trigger_armed is False
    assert reader.request_trigger() is False, (
        "a trigger was accepted with nothing armed and no read waiting")
    assert reader._trigger_requested is False, (
        "the refused request was stored anyway")


def test_ending_a_session_discards_a_press_nothing_will_collect():
    """Stop, close, or a reader that is finished: whatever was pending dies
    with it. Otherwise a press made at the end of one session would be waiting
    for the first read of the next."""
    device = FakeDevice()
    reader = DeviceReader()
    reader._dev = device
    reader.arm_trigger("A1")
    assert reader.request_trigger() is True
    reader.cancel()
    assert reader.trigger_armed is False, "cancel left the reader armed"
    assert reader._trigger_requested is False, (
        "a press survived the end of the session and is waiting for the next "
        "read to spend it")

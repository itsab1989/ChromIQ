"""Tools ▸ "Read single patches" reads a CR30 — and nothing else changed.

Two halves, and the second is the one the owner asked for by name:

> *"i want this now and in the same way as other instruments are handled. also
> supporting the cr30 should not affect the other supported instruments so i
> should be able to still use my colormunki for example"*

**No protocol is re-implemented here.** The real `DeviceReader`, the real
`Cr30SpotManager` and the real `SpotReadDialog` are driven; the only fake is the
DEVICE — the thing that needs hardware — and it is the same fake shape
`tests/test_cr30_waits_for_the_button.py` already uses. A stub that stood in for
the reader instead would be testing itself, which has shipped green here twice.
"""
import os
import pathlib
import sys
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication                      # noqa: E402

from core import instrument_lease                             # noqa: E402
from core.settings import AppSettings                         # noqa: E402
from workflow.cr30.measure_bridge import DeviceReader         # noqa: E402
from workflow.cr30.measurement import (MagnetGated,           # noqa: E402
                                       Measurement, MeasurementError)
from workflow.cr30_spot_manager import (Cr30SpotManager,      # noqa: E402
                                        NO_PRESS_MARKER)
from ui.dialogs.spot_read_dialog import SpotReadDialog        # noqa: E402
from workflow.spot_read_manager import SpotReadManager        # noqa: E402

WL = list(range(400, 701, 10))


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _a_free_instrument():
    """Every test starts with nobody holding the instrument, and leaves it so.

    The claim is process-wide by design — that is the whole point of it — so a
    test that left one standing would refuse the next test's session and the
    failure would land on an innocent file.
    """
    instrument_lease.release(instrument_lease.holder_object())
    yield
    instrument_lease.release(instrument_lease.holder_object())


class FakeDevice:
    """A CR30 that answers only when its button is pressed.

    Same shape as the fake in `test_cr30_waits_for_the_button.py`, including the
    full `read_next_measurement` signature: a stub that accepts fewer arguments
    than the real device reports the CALLER broken the moment the real one grows
    a parameter.
    """

    def __init__(self, kind="usb"):
        self.kind = kind
        self._pending = None
        self.reads = 0
        self.calibrations = []
        self.learned_tile = None
        self.triggered = 0
        self.closed = False

    # -- the operator ---------------------------------------------------
    def press(self, level):
        self._pending = Measurement(WL, [float(level)] * 31)

    # -- the device -----------------------------------------------------
    def read_next_measurement(self, *, timeout=180.0, cancelled=None, poll=0.01,
                              for_learning=False, trigger_wanted=None):
        end = time.monotonic() + timeout
        while self._pending is None:
            if trigger_wanted is not None and trigger_wanted():
                self.triggered += 1
                self.press(50)
                continue
            if cancelled is not None and cancelled():
                raise MeasurementError("cancelled while waiting for the "
                                       "instrument's button")
            if time.monotonic() > end:
                raise MeasurementError(
                    f"{NO_PRESS_MARKER} {timeout:.0f} s.")
            time.sleep(0.002)
        m, self._pending = self._pending, None
        self.reads += 1
        return m

    def calibrate(self, black=False):
        self.calibrates = True
        self.calibrations.append(black)

    def read_measurement(self, *a, **kw):
        return Measurement(WL, [0.0] * 31)

    def close(self):
        self.closed = True


def _reader_on(device) -> DeviceReader:
    """A REAL DeviceReader already holding a fake device.

    `_dev` is set rather than mocked open: everything above the transport — the
    lock, the generation token, the trigger flag, the guards — is the real
    thing, which is what these tests are about.
    """
    reader = DeviceReader()
    reader._dev = device
    return reader


class _Runner:
    """Only the PROCESS is faked; SpotReadManager itself is real."""

    def __init__(self):
        self.calls = []
        self.keys = []
        self.is_running = False

    def run(self, tool, args, cwd, on_line=None, on_finish=None, use_pty=False):
        self.calls.append((tool, list(args), use_pty))
        self.is_running = True

    def write_stdin(self, key):
        self.keys.append(key)

    def abort(self):
        self.is_running = False

    def forget_run_callbacks(self):
        pass


class _Dialog(SpotReadDialog):
    """The real window, with the two things a test cannot answer replaced.

    The calibration windows are modal and are covered by their own tests
    (`test_cr30_calibrates_before_measuring.py` and friends, which now exercise
    the SHARED code both hosts use). Overriding them in a subclass leaves every
    other line of the window real.
    """

    def __init__(self, *a, device=None, calibrates=True, **kw):
        self._device = device
        self._calibrates = calibrates
        self.busy_windows = []
        self.trigger_windows = 0
        super().__init__(*a, **kw)

    def _run_cr30_calibration(self, *, keep_bridge=False):
        self._open_cr30_bridge()
        if self._cr30_reader is not None and self._device is not None:
            self._cr30_reader._dev = self._device
        return self._calibrates

    def _show_instrument_busy(self, where):
        self.busy_windows.append(where)

    def _on_cr30_trigger_not_armed(self):
        self.trigger_windows += 1


def _dialog(qapp, **kw):
    return _Dialog(_Runner(), AppSettings(), **kw)


def _spotread_calls(dlg):
    """What the ArgyllCMS manager actually asked the runner to start."""
    return dlg._manager._runner.calls


# ---------------------------------------------------------------------------
# 1. The instrument is CHOSEN, the way this app chooses instruments
# ---------------------------------------------------------------------------
def test_the_window_names_its_instruments_in_a_list(qapp):
    """Create Chart names its instruments and the CR30 is already a peer in
    that list. This window used to name none, because ArgyllCMS spotread
    cannot be told which device to open. Now there are two readers."""
    dlg = _dialog(qapp)
    labels = [dlg._instrument.itemText(i)
              for i in range(dlg._instrument.count())]
    assert len(labels) == 3
    assert any("CR30" in t for t in labels), labels


def test_automatic_is_the_default_and_it_means_argyllcms(qapp, monkeypatch):
    """THE CR30 IS NEVER THE DEFAULT. With nothing remembered — which is every
    machine that has never seen a CR30 — automatic is the path that has always
    run."""
    monkeypatch.setattr("ui.dialogs.spot_read_dialog.cr30_is_probably_attached",
                        lambda: False)
    dlg = _dialog(qapp)
    assert dlg._instrument.currentIndex() == 0
    assert dlg._chosen_reader() == "argyll"


def test_automatic_finds_a_cr30_this_machine_has_already_used(qapp,
                                                              monkeypatch):
    monkeypatch.setattr("ui.dialogs.spot_read_dialog.cr30_is_probably_attached",
                        lambda: True)
    dlg = _dialog(qapp)
    assert dlg._chosen_reader() == "cr30"


def test_the_usb_look_opens_nothing_and_believes_no_stranger(monkeypatch):
    """A CH340 bridge is an Arduino as often as it is a CR30, so a bare
    VID:PID match must NOT be read as an instrument — that would hand a
    ColorMunki owner a broken tool by default."""
    from ui.dialogs import spot_read_dialog as mod
    from workflow.cr30.discovery import Candidate

    stranger = Candidate("/dev/cu.usbserial-99", 0x1A86, 0x7523, "CH554_CDC")
    monkeypatch.setattr("workflow.cr30.discovery.candidates",
                        lambda **kw: [stranger])
    monkeypatch.setattr(DeviceReader, "_remembered", staticmethod(lambda k: None))
    assert mod.cr30_is_probably_attached() is False

    monkeypatch.setattr(DeviceReader, "_remembered",
                        staticmethod(lambda k: "/dev/cu.usbserial-99"))
    assert mod.cr30_is_probably_attached() is True


def test_the_cr30_cannot_be_asked_for_a_display_reading(qapp):
    """Mode and Skip-calibration are ArgyllCMS's, both of them. A CR30 is
    reflective only and calibrates its own way, so offering them would be
    offering settings that go nowhere."""
    dlg = _dialog(qapp)
    dlg._instrument.setCurrentIndex(2)          # CR30
    assert not dlg._mode.isEnabled()
    assert not dlg._skip_cal.isEnabled()
    dlg._instrument.setCurrentIndex(1)          # any ArgyllCMS instrument
    assert dlg._mode.isEnabled()
    assert dlg._skip_cal.isEnabled()


def test_neither_combo_can_be_squeezed_below_its_own_words(qapp):
    """FOUND ON SCREEN, NOT IN A TEST — and it hit the ArgyllCMS window.

    The controls row grew by one control, and a QHBoxLayout answers that by
    taking the space out of whatever will give it. Mode gave, and rendered
    "Reflective (materia" — clipped, with no ellipsis to say so, and only while
    DISABLED, which is precisely when a session is running.
    """
    dlg = _dialog(qapp)
    for combo in (dlg._instrument, dlg._mode):
        fm = combo.fontMetrics()
        widest = max(fm.horizontalAdvance(combo.itemText(i))
                     for i in range(combo.count()))
        assert combo.minimumWidth() > widest, (
            f"{[combo.itemText(i) for i in range(combo.count())]} needs "
            f"{widest} px and the control may shrink to "
            f"{combo.minimumWidth()}")


# ---------------------------------------------------------------------------
# 2. The ArgyllCMS path is untouched
# ---------------------------------------------------------------------------
def test_a_colormunki_session_still_starts_spotread(qapp, monkeypatch):
    monkeypatch.setattr("ui.dialogs.spot_read_dialog.cr30_is_probably_attached",
                        lambda: False)
    dlg = _dialog(qapp)
    dlg._on_start_stop()
    assert _spotread_calls(dlg) == [("spotread", ["-v", "-c", "1"], True)]
    assert dlg._cr30 is None, "an ArgyllCMS session built ChromIQ's own reader"


def test_the_argyll_path_claims_nothing(qapp, monkeypatch):
    """Two ArgyllCMS sessions already exclude each other through the process
    guard. Making that path take the claim as well would change the behaviour
    of the one path that must not move."""
    monkeypatch.setattr("ui.dialogs.spot_read_dialog.cr30_is_probably_attached",
                        lambda: False)
    dlg = _dialog(qapp)
    dlg._on_start_stop()
    assert instrument_lease.holder() is None


def test_choosing_the_cr30_never_starts_spotread(qapp):
    dlg = _dialog(qapp, device=FakeDevice())
    dlg._instrument.setCurrentIndex(2)
    dlg._on_start_stop()
    try:
        assert _spotread_calls(dlg) == [], "ArgyllCMS was started for a CR30"
        assert dlg._cr30 is not None
    finally:
        dlg._release_instrument()


# ---------------------------------------------------------------------------
# 3. A reading, end to end, through the real reader
# ---------------------------------------------------------------------------
def _wait(qapp, predicate, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_a_button_press_puts_a_reading_in_the_table(qapp):
    device = FakeDevice()
    dlg = _dialog(qapp, device=device)
    dlg._instrument.setCurrentIndex(2)
    dlg._on_start_stop()
    try:
        assert _wait(qapp, lambda: device.reads == 0 or True, 0.2)
        device.press(40.0)               # the operator presses the instrument
        assert _wait(qapp, lambda: len(dlg._readings) == 1), \
            "the reading never reached the window"
        r = dlg._readings[0]
        assert r.lab[0] > 0, r.lab
        assert r.hex.startswith("#")
        assert dlg._table.rowCount() == 1
    finally:
        dlg._release_instrument()


def test_take_reading_asks_the_instrument_instead_of_waiting(qapp):
    """The host trigger — the same one the Measure tab binds to the space bar,
    and measurably steadier than pressing the instrument's own button."""
    device = FakeDevice()
    device.learned_tile = [1.0] * 31          # this unit's guard is armed
    dlg = _dialog(qapp, device=device)
    dlg._instrument.setCurrentIndex(2)
    dlg._on_start_stop()
    try:
        assert _wait(qapp, lambda: dlg._read_btn.isEnabled())
        dlg._on_take_reading()
        assert _wait(qapp, lambda: len(dlg._readings) == 1), \
            "the host trigger produced no reading"
        assert device.triggered == 1
    finally:
        dlg._release_instrument()


def test_a_reading_is_refused_when_the_magnet_guard_is_not_armed(qapp):
    """A reading ChromIQ asks for cannot report the magnet gate, so without
    this unit's learned tile there is nothing to replace the flag with.
    M-CR30-TRIGGER-NOT-ARMED, exactly as in the Measure tab."""
    device = FakeDevice()                      # learned_tile stays None
    dlg = _dialog(qapp, device=device)
    dlg._instrument.setCurrentIndex(2)
    dlg._on_start_stop()
    try:
        assert _wait(qapp, lambda: dlg._read_btn.isEnabled())
        dlg._on_take_reading()
        assert dlg.trigger_windows == 1, "the refusal was silent"
        assert device.triggered == 0
    finally:
        dlg._release_instrument()


def test_an_expired_wait_is_not_reported_as_a_failure():
    """The loop re-arms silently when nobody pressed anything. A spot session
    has no chart to walk, so an expiry is not news — but a REFUSAL is, and the
    two arrive as the same exception type."""
    import inspect
    from workflow.cr30 import device as device_mod
    src = inspect.getsource(device_mod)
    assert NO_PRESS_MARKER in src, (
        "the sentence the spot loop matches to tell an expiry from a refusal "
        "has been reworded; every expiry now reports itself as an error")


def test_the_two_managers_present_the_same_surface():
    """The window must not learn a second vocabulary. Whatever it consumes from
    the ArgyllCMS manager, the CR30 one answers to."""
    for name in ("reading_ready", "ready_to_read", "instrument_detected",
                 "calibration_prompt", "calibration_finished",
                 "calibration_position_wrong", "misread",
                 "sensor_wrong_position", "no_instrument", "device_busy",
                 "instrument_disconnected", "coms_init_failed",
                 "inst_init_failed", "session_ended",
                 "start", "take_reading", "send_key", "quit", "abort",
                 "detach", "is_running"):
        assert hasattr(SpotReadManager, name), name
        assert hasattr(Cr30SpotManager, name), \
            f"the CR30 manager has no {name}; the window would have to branch"


# ---------------------------------------------------------------------------
# 4. Two windows, one instrument — the hazard, in both orders
# ---------------------------------------------------------------------------
def test_measure_first_then_the_spot_window(qapp):
    """A Measure session holds the instrument; the spot window refuses.

    `ArgyllRunner.is_running` cannot answer this: ChromIQ's own reader is not a
    process. What the second window would otherwise get is a plausible colour
    belonging to the first one's patch.
    """
    holder = DeviceReader()
    assert instrument_lease.acquire(holder, instrument_lease.MEASURE_TAB)
    dlg = _dialog(qapp, device=FakeDevice())
    dlg._instrument.setCurrentIndex(2)
    dlg._on_start_stop()
    try:
        assert dlg.busy_windows == [instrument_lease.MEASURE_TAB], \
            "the spot window opened the instrument out from under a measurement"
        assert dlg._cr30 is None
        assert dlg._cr30_reader is None
    finally:
        dlg._release_instrument()
        instrument_lease.release(holder)


def test_the_spot_window_first_then_measure(qapp, monkeypatch):
    """…and the other way round, which is the order nothing in the app could
    see before: the spot window opens no process at all."""
    dlg = _dialog(qapp, device=FakeDevice())
    dlg._instrument.setCurrentIndex(2)
    dlg._on_start_stop()
    try:
        assert instrument_lease.holder() == instrument_lease.SPOT_TOOL

        from ui.tabs.tab_measure import TabMeasure

        class _Tab(TabMeasure):
            windows = []

            def _chart_is_cr30(self):
                return True

            def _instrument_busy_window(self, where):
                _Tab.windows.append(where)

        from core.argyll_runner import ArgyllRunner
        settings = AppSettings()
        tab = _Tab(ArgyllRunner(settings), settings)
        assert tab._blocked_by_the_instrument_being_in_use() is True
        assert _Tab.windows == [instrument_lease.SPOT_TOOL]
    finally:
        dlg._release_instrument()


def test_a_colormunki_chart_is_not_blocked_by_a_cr30_spot_session(qapp):
    """Two different instruments doing two different jobs. Refusing this would
    be the CR30 affecting an instrument that already worked."""
    holder = DeviceReader()
    instrument_lease.acquire(holder, instrument_lease.SPOT_TOOL)
    try:
        from ui.tabs.tab_measure import TabMeasure
        from core.argyll_runner import ArgyllRunner

        class _Tab(TabMeasure):
            def _chart_is_cr30(self):
                return False

            def _instrument_busy_window(self, where):
                raise AssertionError("a ColorMunki chart was refused")

        settings = AppSettings()
        tab = _Tab(ArgyllRunner(settings), settings)
        assert tab._blocked_by_the_instrument_being_in_use() is False
    finally:
        instrument_lease.release(holder)


def test_closing_the_window_lets_the_instrument_go(qapp):
    device = FakeDevice()
    dlg = _dialog(qapp, device=device)
    dlg._instrument.setCurrentIndex(2)
    dlg._on_start_stop()
    assert instrument_lease.holder() == instrument_lease.SPOT_TOOL
    dlg._release_instrument()
    assert instrument_lease.holder() is None, \
        "the window closed still holding the instrument"
    assert device.closed, "the instrument was never let go of"


def test_a_claim_whose_window_is_gone_frees_itself():
    """A leaked claim would refuse every later measurement for the life of the
    app, which is worse than the fault it prevents and unclearable without a
    restart. The holder is a weak reference for exactly that reason."""
    owner = DeviceReader()
    instrument_lease.acquire(owner, instrument_lease.SPOT_TOOL)
    assert instrument_lease.holder() == instrument_lease.SPOT_TOOL
    del owner
    import gc
    gc.collect()
    assert instrument_lease.holder() is None


def test_a_window_holding_the_instrument_is_never_told_it_is_busy():
    """The Measure tab's calibration opens a reader, closes it and opens
    another inside one Start. It must not refuse itself on the way."""
    mine = DeviceReader()
    instrument_lease.acquire(mine, instrument_lease.MEASURE_TAB)
    assert instrument_lease.held_by_other(mine) is None
    instrument_lease.release(mine)
    second = DeviceReader()
    assert instrument_lease.acquire(second, instrument_lease.MEASURE_TAB)
    instrument_lease.release(second)


def test_a_second_window_of_the_SAME_kind_is_still_refused():
    """Two Read-single-patches windows carry the same name, so the question is
    asked of the reader and never of the name. A name comparison would wave the
    second one straight through to the instrument the first is holding."""
    first = DeviceReader()
    instrument_lease.acquire(first, instrument_lease.SPOT_TOOL)
    # A window that has not opened a reader yet — which is every window at the
    # moment it asks.
    assert instrument_lease.held_by_other(None) == instrument_lease.SPOT_TOOL
    instrument_lease.release(first)


# ---------------------------------------------------------------------------
# 5. The magnet, which is not an ordinary refusal
# ---------------------------------------------------------------------------
def test_a_magnet_stops_the_session_rather_than_asking_for_another_press(qapp):
    """The instrument has already performed a white calibration against
    whatever was under the aperture, so every later reading would be wrong by a
    factor nothing downstream can see."""
    stopped = {"n": 0}

    class _Gated(FakeDevice):
        def read_next_measurement(self, **kw):
            raise MagnetGated("a magnet at the aperture")

    mgr = Cr30SpotManager()
    mgr.reader = _reader_on(_Gated())
    seen = []
    mgr.magnet_gated.connect(seen.append)
    mgr.session_ended.connect(lambda _c: stopped.__setitem__("n",
                                                             stopped["n"] + 1))
    mgr.start(None, lambda _t: None)
    assert _wait(qapp, lambda: bool(seen))
    assert not mgr.is_running, "the session carried on after a magnet"
    mgr.quit()

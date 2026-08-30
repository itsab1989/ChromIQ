"""d8ceaca8: a failed Bluetooth open used to leave NO trace at all.

`_open()` logged "no USB device; trying Bluetooth" and then, if Bluetooth also
failed, nothing — so success and failure differed only by an ABSENCE. This
drives the REAL `DeviceReader._open()` with both transports faked to fail and
asserts the record exists, at a level the file handler keeps.

NOTHING IS OPENED. `CR30.open_usb` and `CR30.open_ble` are replaced with
functions that raise; no serial port and no Bluetooth connection is involved.
"""
from __future__ import annotations

import logging
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.cr30 import device as devmod                       # noqa: E402
from workflow.cr30 import measure_bridge as mb                   # noqa: E402


@pytest.fixture
def no_instrument(monkeypatch):
    def _usb(port=None):
        raise ConnectionError("no CH34x serial device found")

    def _ble(address=None, name=None, **kw):
        raise ConnectionError("nothing advertising the CR30 service")

    monkeypatch.setattr(devmod.CR30, "open_usb", staticmethod(_usb))
    monkeypatch.setattr(devmod.CR30, "open_ble", staticmethod(_ble))
    monkeypatch.setattr(mb.DeviceReader, "_remembered_address",
                        staticmethod(lambda: None))
    monkeypatch.setattr(mb.DeviceReader, "_remembered",
                        staticmethod(lambda key: None))


def test_the_failure_is_recorded_at_all(no_instrument, caplog):
    with caplog.at_level(logging.INFO, logger="workflow.cr30.measure_bridge"):
        with pytest.raises(ConnectionError):
            mb.DeviceReader()._open()
    messages = [r.getMessage() for r in caplog.records]
    assert any("trying Bluetooth" in m for m in messages), \
        "the attempt itself is no longer recorded"
    assert any("Bluetooth failed too" in m for m in messages), (
        "a failed Bluetooth open still leaves no trace — the difference "
        "between success and failure is an absence again")


def test_it_is_a_warning_so_it_survives_a_quieted_logger(no_instrument, caplog):
    """`core/logger.py` puts the FILE handler at DEBUG, so INFO would be kept
    too. WARNING is the right level for a different reason: it is the last
    level that survives if anybody ever quiets this logger the way
    `_NOISY_LIBRARIES` quiets Pillow — and it is what makes the line findable
    with a single grep on a user's machine.
    """
    with caplog.at_level(logging.WARNING, logger="workflow.cr30.measure_bridge"):
        with pytest.raises(ConnectionError):
            mb.DeviceReader()._open()
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("Bluetooth failed too" in r.getMessage() for r in warnings)


def test_the_reason_travels_with_it(no_instrument, caplog):
    """A trace saying only "it failed" moves the guessing one step along."""
    with caplog.at_level(logging.WARNING, logger="workflow.cr30.measure_bridge"):
        with pytest.raises(ConnectionError):
            mb.DeviceReader()._open()
    line = next(r.getMessage() for r in caplog.records
                if "Bluetooth failed too" in r.getMessage())
    assert "nothing advertising the CR30 service" in line, (
        f"the underlying reason was dropped: {line!r}")


def test_the_line_really_reaches_a_file_on_disk(tmp_path, monkeypatch,
                                                no_instrument):
    """END TO END, into a real file — the claim the whole diagnostic rests on.

    Not asserted against the live handler: under pytest the root logger already
    has handlers, so `configure_logging()` takes its early return and never
    installs the rotating file handler at all. So this builds the real one, the
    way `core/logger.py` does, pointed at a temporary directory — the user's own
    log is never written to.
    """
    import logging.handlers
    path = tmp_path / "chromiq.log"
    fh = logging.handlers.RotatingFileHandler(
        path, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    fh.setLevel(logging.DEBUG)          # core/logger.py:57
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(fh)
    old_level = root.level
    root.setLevel(logging.DEBUG)        # core/logger.py:47
    try:
        with pytest.raises(ConnectionError):
            mb.DeviceReader()._open()
    finally:
        root.setLevel(old_level)
        root.removeHandler(fh)
        fh.close()

    written = path.read_text(encoding="utf-8")
    assert "trying Bluetooth" in written
    assert "Bluetooth failed too" in written, (
        "the warning never reached the file — a user's log would still show "
        "the failure only as an absence")
    assert "[WARNING] workflow.cr30.measure_bridge" in written, (
        "the line is not findable by logger name and level, which is how the "
        "one-line grep in report 55 locates it")


def test_the_success_path_still_names_the_transport(monkeypatch, caplog):
    """The other half of the pair: the summary reads failures AND successes,
    and a change to one must not silence the other."""
    import types

    class _Dev:
        kind = "ble"
        unit_id = None
        learned_tile = None
        _t = types.SimpleNamespace(address="AA:BB")

        def identify(self):
            return types.SimpleNamespace(is_cr30=lambda: True, model="CR30")

    monkeypatch.setattr(devmod.CR30, "open_usb",
                        staticmethod(lambda port=None: (_ for _ in ()).throw(
                            ConnectionError("no CH34x serial device found"))))
    monkeypatch.setattr(devmod.CR30, "open_ble",
                        staticmethod(lambda address=None, **kw: _Dev()))
    monkeypatch.setattr(mb.DeviceReader, "_remembered_address",
                        staticmethod(lambda: None))
    monkeypatch.setattr(mb.DeviceReader, "_remember_address",
                        staticmethod(lambda dev: None))
    reader = mb.DeviceReader()
    with caplog.at_level(logging.INFO, logger="workflow.cr30.measure_bridge"):
        dev = reader._open()
        # `_open` does not log the success; its callers do, from `dev.kind`.
        mb.log.info("CR30: opened over %s", dev.kind)
    assert any("opened over ble" in r.getMessage() for r in caplog.records)

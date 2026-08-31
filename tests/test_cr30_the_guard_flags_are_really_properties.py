"""A guard that is a bound METHOD is always true, and nothing could see it.

`open_transport` was added above `guard_is_armed` and took its `@property`
with it (2026-08-31). The consequence was not cosmetic: `guard_is_armed`
became a bound method, which is truthy for every instrument, so

  * `_offer_cr30_tile_learning` returned early and the learning window could
    never appear again on any unit, and
  * `trigger_allowed()` said yes on an instrument whose tile is unknown —
    exactly what M-CR30-TRIGGER-NOT-ARMED exists to refuse, because a reading
    ChromIQ asks for cannot report the magnet gate.

The whole CR30 suite stayed green, because every fake sets `guard_is_armed`
as a plain attribute and so never exercises the real descriptor. These tests
look at the REAL class instead, and read the values rather than the source.
"""
import inspect

import pytest

from workflow.cr30.measure_bridge import DeviceReader


class _Dev:
    """Only what the two properties actually touch."""
    kind = "ble"
    learned_tile = None


def _reader(*, kind="ble", learned=None):
    r = DeviceReader.__new__(DeviceReader)      # no transport is opened
    dev = _Dev()
    dev.kind, dev.learned_tile = kind, learned
    r._dev = dev
    return r


@pytest.mark.parametrize("name", ["open_transport", "guard_is_armed"])
def test_the_flag_is_a_property_and_not_a_method(name):
    attr = inspect.getattr_static(DeviceReader, name)
    assert isinstance(attr, property), (
        f"DeviceReader.{name} is a {type(attr).__name__}, not a property — a "
        "bound method is truthy for every instrument, so every caller that "
        "asks 'is this safe?' is told yes"
    )


def test_an_unlearned_unit_reports_the_guard_as_false():
    assert _reader(learned=None).guard_is_armed is False


def test_a_learned_unit_reports_the_guard_as_true():
    assert _reader(learned=[80.1] * 31).guard_is_armed is True


def test_the_host_trigger_is_refused_while_the_tile_is_unknown():
    # The reason the guard flag must be a real value: this call gates a
    # reading that cannot report the magnet gate.
    assert _reader(learned=None).trigger_allowed() is False
    assert _reader(learned=[80.1] * 31).trigger_allowed() is True


@pytest.mark.parametrize("kind,expected", [("usb", "usb"), ("ble", "ble"), ("", "")])
def test_open_transport_names_the_transport_that_is_open(kind, expected):
    # The learning window asks how many presses to show from this, and asking
    # for the wrong number is how somebody sits pressing once for ever.
    assert _reader(kind=kind).open_transport == expected

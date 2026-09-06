"""#159: WinUSB on the CR30 would not install a driver — it would remove one.

The CR30 does not speak USB directly. It sits behind a CH340 USB-to-serial
bridge and ChromIQ reaches it as a COM port through pyserial. Giving that bridge
the WinUSB driver destroys the COM port: the instrument disappears from ChromIQ
and from every other serial application until somebody rolls the driver back by
hand in Device Manager.

Nothing in the app does this today — 1a86:7523 is not in `KNOWN_COLORIMETERS`.
Two things make it worth guarding anyway, and the second is live right now:

* the dialog's "Reinstall" path runs `install_winusb` over EVERY detected
  device, so one wrong table entry would brick a CR30 while its owner was
  repairing a different instrument entirely;
* the Zadig guidance tells the user, in their own words, to find their
  instrument and give it WinUSB. A CR30 owner with driver trouble who follows
  that on the CH340 row does the damage themselves, with no code change at all.

⚠ 1a86:7523 is the generic CH340 and lives in millions of unrelated devices.
Its presence never means a CR30 is attached, which is why none of this may
auto-install anything.
"""
from __future__ import annotations

import inspect

import pytest

import core.usb_driver_installer as inst


CR30_BRIDGE = ("1a86", "7523")


def test_the_serial_bridge_is_not_a_colorimeter():
    """It must never be in the table the installer walks."""
    assert CR30_BRIDGE not in inst.KNOWN_COLORIMETERS, (
        "the CR30's USB-serial bridge is listed as a colorimeter; the "
        "Reinstall path would give it WinUSB and remove its COM port")


def test_the_two_tables_never_overlap():
    """The guarantee is structural: a device is one class or the other."""
    both = set(inst.KNOWN_COLORIMETERS) & set(inst.VENDOR_SERIAL_DEVICES)
    assert not both, f"listed as both a colorimeter and a serial device: {both}"


def test_it_is_recognised_as_a_serial_device():
    assert inst.is_vendor_serial(*CR30_BRIDGE)
    assert inst.is_vendor_serial("1A86", "7523"), "case must not matter"
    assert not inst.is_vendor_serial("0971", "2000"), "an i1 Pro is not serial"


def test_install_winusb_refuses_it_even_when_asked_directly():
    """The belt-and-braces guard, and the one that still holds if someone edits
    the table by mistake.

    ⚠ ON A NON-WINDOWS HOST THIS PASSES FOR THE WRONG REASON: wdi-simple is not
    there, so the function returns False whether or not the guard exists.
    Proved by removing the guard — this test stayed green and only the ordering
    test below went red. Do not delete that one thinking this covers it.
    """
    dev = inst.UsbDevice(vid="1a86", pid="7523", name="USB-SERIAL CH340",
                         has_winusb=False)
    assert inst.install_winusb(dev) is False


def test_the_refusal_comes_before_anything_is_launched(monkeypatch):
    """Proved rather than assumed: if it refused only after finding the
    installer, the guard would be inert wherever wdi-simple exists."""
    called = []
    monkeypatch.setattr(inst, "_wdi_simple_path",
                        lambda: called.append(1) or pytest.fail(
                            "it went looking for the installer before "
                            "refusing a serial device"))
    dev = inst.UsbDevice(vid="1a86", pid="7523", name="USB-SERIAL CH340",
                         has_winusb=False)
    assert inst.install_winusb(dev) is False
    assert called == []


def test_every_zadig_instruction_warns_about_the_serial_device():
    """The hazard a user can reach today with no code change.

    Each place the app steers someone to Zadig says "find your colorimeter and
    choose WinUSB". On a machine with a CR30 attached, that sentence applied to
    the CH340 row is the damage. Every one of them must carry the warning.

    THIS USED TO COUNT PHRASES IN THE SOURCE, and that is why it is being
    rewritten rather than deleted. The three outcomes each carried their own
    copy of the warning paragraph; factoring the copies into one `tr()` key —
    so a translator writes it once and the three windows cannot drift apart —
    dropped the source count from three to one and turned this test red, on a
    change that made the guarantee *stronger*. A test that fails when the thing
    it protects improves is measuring the wrong thing.

    So it now asks the question of the rendered text: every branch of the two
    message functions that mentions Zadig must also carry the CR30 warning. That
    holds however the string is assembled, and it is what the user actually
    reads.
    """
    from ui.dialogs.settings_dialog import (usb_installer_text,
                                            usb_install_outcome)
    from types import SimpleNamespace

    def dev(has_winusb):
        return SimpleNamespace(name="GretagMacbeth i1 Pro / i1 Pro 2",
                               has_winusb=has_winusb)

    rendered = []
    for wdi in (True, False):
        for devices in ([], [dev(True)], [dev(False)], [dev(True), dev(False)]):
            rendered.append(usb_installer_text(devices, wdi_available=wdi)[0])
    for status in ("launched", "download_page", "failed", None):
        rendered.append(usb_install_outcome(
            wdi_available=False, ran_ok=False, still_unbound_names=[],
            zadig_status=status, driver_was_missing=True)[0])
    for ran_ok in (True, False):
        for unbound in ([], ["GretagMacbeth i1 Pro / i1 Pro 2"]):
            rendered.append(usb_install_outcome(
                wdi_available=True, ran_ok=ran_ok,
                still_unbound_names=unbound, zadig_status=None,
                driver_was_missing=True)[0])

    steers = [t for t in rendered
              if "List All Devices" in t
              or "Select your colorimeter, choose WinUSB" in t]
    assert steers, "no branch steers the user to Zadig any more — has the "                    "wording moved somewhere this test cannot see?"
    unwarned = [t for t in steers if "If you own a CR30" not in t]
    assert not unwarned, (
        f"{len(unwarned)} of {len(steers)} Zadig instructions do not warn "
        f"about the CR30's serial bridge: {unwarned}")


def test_the_driver_dialog_does_not_ship_s_in_brackets():
    """The project writes singular and plural out. Basti flagged it in the
    measurement log; the same pattern was in this dialog."""
    from ui.dialogs import settings_dialog
    src = inspect.getsource(settings_dialog)
    for bad in ("device(s)", "colorimeter(s)", "instrument(s)", "driver(s)"):
        assert bad not in src, f"the driver dialog still ships {bad!r}"

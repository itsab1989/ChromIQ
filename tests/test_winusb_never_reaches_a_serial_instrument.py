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
    choose <driver>". On a machine with a CR30 attached, that sentence applied
    to the CH340 row is the damage. Every one of them must carry the warning.

    THIS USED TO COUNT PHRASES IN THE SOURCE, and that is why it is being
    rewritten rather than deleted. The three outcomes each carried their own
    copy of the warning paragraph; factoring the copies into one `tr()` key —
    so a translator writes it once and the three windows cannot drift apart —
    dropped the source count from three to one and turned this test red, on a
    change that made the guarantee *stronger*. A test that fails when the thing
    it protects improves is measuring the wrong thing.

    So it asks the question of the rendered text instead. That holds however
    the string is assembled, and it is what the user actually reads.

    …AND THEN IT ASKED THE RENDERED TEXT THE WRONG QUESTION, WHICH IS WORSE.
    It selected the branches to check by looking for two PHRASES —
    `List All Devices` and `Select your colorimeter, choose WinUSB`. Two
    branches of `usb_install_outcome` steer a user into Zadig without either
    phrase: the one that says the automatic install failed, and the one that
    says the driver did not bind. Both return `offer_zadig=True`, so the button
    beside them launches Zadig, and neither was ever inside `steers`. A CR30
    owner routed through either got a live Zadig and no warning — and the test
    was green throughout, because it had never looked.

    It also would have gone quietly *blinder* on the change that brought this
    to light: renaming WinUSB to libusb-win32 in the "Zadig is open" branch
    deletes the second phrase, dropping that branch out of coverage with no
    test turning red. A guard that stops guarding without failing is the one
    kind of test worth less than none.

    So the selector is now the same fact the app acts on: **a branch that
    OFFERS Zadig, or names it, must carry the warning.** `usb_install_outcome`
    returns that fact as its second element; nothing has to be spelled the
    right way for this test to see it.
    """
    from ui.dialogs.settings_dialog import (usb_installer_text,
                                            usb_install_outcome)
    from types import SimpleNamespace

    def dev(has_winusb):
        return SimpleNamespace(name="GretagMacbeth i1 Pro / i1 Pro 2",
                               has_winusb=has_winusb)

    # Every branch that tells the user which row to pick in Zadig, named one at
    # a time. A list of names cannot shrink by accident the way a phrase match
    # can — a branch leaves it only by being deleted from the app.
    steers = {
        "the numbered Zadig steps":
            usb_installer_text([dev(False)], wdi_available=False)[0],
        "Zadig has just been launched":
            usb_install_outcome(
                wdi_available=False, ran_ok=False, still_unbound_names=[],
                zadig_status="launched", driver_was_missing=True)[0],
        "Zadig must be downloaded first":
            usb_install_outcome(
                wdi_available=False, ran_ok=False, still_unbound_names=[],
                zadig_status="download_page", driver_was_missing=True)[0],
        # THE TWO THAT USED TO HIDE. Neither carries `List All Devices` nor the
        # old "choose WinUSB" phrase, so neither was ever inside the old
        # selector — and both return `offer_zadig=True`, so the button beside
        # them launches Zadig. A CR30 owner reached either one and got a live
        # Zadig with no warning at all, with this test green.
        "the automatic install failed or was cancelled":
            usb_install_outcome(
                wdi_available=True, ran_ok=False, still_unbound_names=[],
                zadig_status=None, driver_was_missing=True)[0],
        "the installer finished but the driver did not bind":
            usb_install_outcome(
                wdi_available=True, ran_ok=True,
                still_unbound_names=["GretagMacbeth i1 Pro / i1 Pro 2"],
                zadig_status=None, driver_was_missing=True)[0],
        "Zadig could not be opened at all":
            usb_install_outcome(
                wdi_available=False, ran_ok=False, still_unbound_names=[],
                zadig_status="failed", driver_was_missing=True)[0],
    }
    unwarned = sorted(why for why, text in steers.items()
                      if "If you own a CR30" not in text)
    assert not unwarned, (
        f"{len(unwarned)} of {len(steers)} Zadig instructions do not warn "
        f"about the CR30's serial bridge: {unwarned}")

    # AND THE LIST ABOVE MUST STILL BE THE WHOLE LIST. Everything that offers
    # Zadig, or names it, has to be either in `steers` or in the short list of
    # branches that hand over no instruction — so a NEW Zadig steer cannot be
    # added to the app without one of these two lists being updated.
    #
    # "The driver is already installed… click Open Zadig" names Zadig but tells
    # nobody which row to pick; the instruction arrives one window later, in
    # "Zadig has just been launched", which is in `steers`. "Could not open
    # Zadig or its download page" gives an address and sends nobody to a
    # dropdown.
    # ONE EXCLUSION LEFT, AND IT SHRANK BECAUSE A REVIEW ARGUED IT DOWN.
    # "Could not open Zadig or its download page" used to be excluded on the
    # grounds that it gives an address rather than an instruction. It gives
    # Zadig's DOWNLOAD PAGE and tells the user to go there — the same journey
    # as the `download_page` branch, which has always carried the warning, with
    # the only difference being whether ChromIQ managed to open the browser.
    # It carries the warning now, and is swept like the rest.
    #
    # What remains is the branch that opens Zadig and instructs nothing: the
    # instruction arrives one window later, in "Zadig has just been launched",
    # which is in `steers` above. This file runs in English only, so an English
    # phrase is safe here in a way it is not in the twelve-language sibling.
    instructs_nobody = ("to run the installer again",)
    everything: "list[tuple[str, bool]]" = []
    for wdi in (True, False):
        for devices in ([], [dev(True)], [dev(False)], [dev(True), dev(False)]):
            everything.append(
                (usb_installer_text(devices, wdi_available=wdi)[0], False))
    for status in ("launched", "download_page", "failed", None):
        everything.append(usb_install_outcome(
            wdi_available=False, ran_ok=False, still_unbound_names=[],
            zadig_status=status, driver_was_missing=True))
    for ran_ok in (True, False):
        for unbound in ([], ["GretagMacbeth i1 Pro / i1 Pro 2"]):
            everything.append(usb_install_outcome(
                wdi_available=True, ran_ok=ran_ok,
                still_unbound_names=unbound, zadig_status=None,
                driver_was_missing=True))
    unaccounted = [
        t for t, offers in everything
        if (offers or "Zadig" in t)
        and "If you own a CR30" not in t
        and not any(p in t for p in instructs_nobody)
    ]
    assert not unaccounted, (
        f"{len(unaccounted)} branch(es) put the user in front of Zadig, carry "
        f"no CR30 warning, and are not one of the two that instruct nobody: "
        f"{unaccounted}")


def test_the_driver_dialog_does_not_ship_s_in_brackets():
    """The project writes singular and plural out. Basti flagged it in the
    measurement log; the same pattern was in this dialog."""
    from ui.dialogs import settings_dialog
    src = inspect.getsource(settings_dialog)
    for bad in ("device(s)", "colorimeter(s)", "instrument(s)", "driver(s)"):
        assert bad not in src, f"the driver dialog still ships {bad!r}"

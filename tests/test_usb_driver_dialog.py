"""The driver helper's words, pinned.

`SettingsDialog._show_usb_installer` is a `while True:` around `dlg.exec()`, so
it cannot be driven from a test — CLAUDE.md warns that a modal `.exec()` makes
the whole suite look like it has hung. Until now the only thing guarding what it
says was `tests/test_winusb_never_reaches_a_serial_instrument.py`, which counts
phrases in the *source text* and so cannot tell you what a user would read.

`ui.dialogs.settings_dialog.usb_installer_text` and `usb_install_outcome` are
that message-building lifted out into pure functions. This file asserts their
output character for character.

**These are characterisation tests.** They are not aspirational: they say "this
is what shipped". When the wording changes on purpose, the diff to this file is
the review artefact for the change. When it changes by accident, this file is
what notices.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ui.dialogs import settings_dialog as sd


def dev(name: str, has_winusb: bool):
    """The two attributes the text functions read off a `UsbDevice`."""
    return SimpleNamespace(name=name, has_winusb=has_winusb)


I1PRO = "GretagMacbeth i1 Pro / i1 Pro 2"
SPYDER = "Datacolor SpyderX"


# ---------------------------------------------------------------------------
# The first window
# ---------------------------------------------------------------------------

def test_nothing_attached_asks_for_a_cable_and_offers_no_primary_button():
    msg, btn = sd.usb_installer_text([], wdi_available=True)
    assert msg == (
        "<b>No colorimeter detected.</b><br><br>"
        "Make sure your device is plugged in via USB, "
        "then click <b>Refresh</b>."
    )
    assert btn is None, "there is nothing to install for, so no primary button"


def test_nothing_attached_says_the_same_without_wdi_simple():
    assert (sd.usb_installer_text([], wdi_available=False)
            == sd.usb_installer_text([], wdi_available=True))


def test_one_device_without_a_driver_and_wdi_simple_present():
    msg, btn = sd.usb_installer_text([dev(I1PRO, False)], wdi_available=True)
    assert msg == (
        "<b>Connected colorimeter:</b><br>"
        f"&nbsp;&nbsp;• {I1PRO} — <i>driver not installed</i>"
        "<br><br>"
        "Click <b>Install Driver</b> to install the Microsoft WinUSB driver "
        "automatically. A Windows security prompt will appear — click Yes to "
        "continue.<br><br>"
        "<i>No test-signing mode required. Works on x64 and ARM64.</i>"
    )
    assert btn == "Install Driver"


def test_one_device_without_a_driver_and_no_wdi_simple_falls_back_to_zadig():
    msg, btn = sd.usb_installer_text([dev(I1PRO, False)], wdi_available=False)
    assert msg == (
        "<b>Connected colorimeter:</b><br>"
        f"&nbsp;&nbsp;• {I1PRO} — <i>driver not installed</i>"
        "<br><br>"
        "Click <b>Open Zadig</b> and ChromIQ will launch <b>Zadig</b>, a free "
        "USB driver tool. In Zadig:<br>"
        "&nbsp;&nbsp;1. Click <b>Options → List All Devices</b><br>"
        "&nbsp;&nbsp;2. Find your colorimeter in the dropdown<br>"
        "&nbsp;&nbsp;3. Select <b>WinUSB</b> as the driver and click "
        "<b>Install Driver</b>"
        "<br><br><b>If you own a CR30:</b> do not pick the USB-serial "
        "device (CH340) in Zadig. That instrument is reached "
        "through its COM port, and giving it WinUSB would stop "
        "ChromIQ finding it at all."
    )
    assert btn == "Open Zadig"


def test_one_device_that_already_works_offers_a_repair_not_an_install():
    msg, btn = sd.usb_installer_text([dev(I1PRO, True)], wdi_available=True)
    assert msg == (
        "<b>Connected colorimeter:</b><br>"
        f"&nbsp;&nbsp;• {I1PRO} — <i>WinUSB ✓</i>"
        "<br><br>"
        "The driver is already installed for the device above. "
        "If ChromIQ or Argyll still can't open your instrument, click "
        "<b>Reinstall Driver</b> to run the installer again."
    )
    assert btn == "Reinstall Driver"


def test_two_working_devices_switch_every_word_to_the_plural():
    msg, btn = sd.usb_installer_text(
        [dev(I1PRO, True), dev(SPYDER, True)], wdi_available=True)
    assert msg == (
        "<b>Connected colorimeters:</b><br>"
        f"&nbsp;&nbsp;• {I1PRO} — <i>WinUSB ✓</i><br>"
        f"&nbsp;&nbsp;• {SPYDER} — <i>WinUSB ✓</i>"
        "<br><br>"
        "The driver is already installed for the devices above. "
        "If ChromIQ or Argyll still can't open your instrument, click "
        "<b>Reinstall Driver</b> to run the installer again."
    )
    assert btn == "Reinstall Driver"


def test_a_mixed_pair_is_treated_as_needing_an_install():
    """One working, one not: the header pluralises, the action does not soften."""
    msg, btn = sd.usb_installer_text(
        [dev(I1PRO, True), dev(SPYDER, False)], wdi_available=True)
    assert msg.startswith("<b>Connected colorimeters:</b><br>")
    assert f"• {I1PRO} — <i>WinUSB ✓</i>" in msg
    assert f"• {SPYDER} — <i>driver not installed</i>" in msg
    assert "Click <b>Install Driver</b>" in msg
    assert "already installed" not in msg
    assert btn == "Install Driver"


def test_a_working_device_without_wdi_simple_still_says_open_zadig():
    _msg, btn = sd.usb_installer_text([dev(I1PRO, True)], wdi_available=False)
    assert btn == "Open Zadig"


@pytest.mark.parametrize("wdi", [True, False])
@pytest.mark.parametrize("has_driver", [True, False])
def test_no_bracketed_plurals_reach_the_screen(wdi, has_driver):
    """The source is already checked for `device(s)`; check the output too."""
    msg, _btn = sd.usb_installer_text(
        [dev(I1PRO, has_driver), dev(SPYDER, has_driver)], wdi_available=wdi)
    for bad in ("device(s)", "colorimeter(s)", "instrument(s)", "driver(s)"):
        assert bad not in msg


# ---------------------------------------------------------------------------
# The outcome window
# ---------------------------------------------------------------------------

def test_a_clean_install_says_so_and_offers_nothing_further():
    text, offer_zadig = sd.usb_install_outcome(
        wdi_available=True, ran_ok=True, still_unbound_names=[],
        zadig_status=None)
    assert text == "WinUSB driver installed successfully."
    assert offer_zadig is False


def test_a_failed_or_cancelled_install_offers_zadig():
    text, offer_zadig = sd.usb_install_outcome(
        wdi_available=True, ran_ok=False, still_unbound_names=[],
        zadig_status=None)
    assert text == (
        "Automatic installation failed or was cancelled.<br>"
        "Click <b>Try Zadig</b> to install it manually using the guided tool."
    )
    assert offer_zadig is True


def test_the_cancelled_wording_wins_even_when_something_is_still_unbound():
    """`ran_ok` False is checked before the unbound list — pinned so the
    ordering cannot be swapped by accident."""
    text, _ = sd.usb_install_outcome(
        wdi_available=True, ran_ok=False, still_unbound_names=[I1PRO],
        zadig_status=None)
    assert text.startswith("Automatic installation failed or was cancelled.")


def test_installed_but_not_bound_names_the_instrument():
    text, offer_zadig = sd.usb_install_outcome(
        wdi_available=True, ran_ok=True, still_unbound_names=[I1PRO],
        zadig_status=None)
    assert text == (
        "Windows reported the install finished, but the driver still "
        f"isn't bound to {I1PRO}. This often happens when the device "
        "was previously plugged into a different USB port.<br><br>"
        "Click <b>Try Zadig</b> to install it reliably: pick your "
        "instrument in Zadig, choose <b>WinUSB</b> (or libusb-win32), "
        "then click <b>Replace Driver</b>. Unplugging and replugging the "
        "instrument first can also help."
    )
    assert offer_zadig is True


def test_installed_but_not_bound_lists_several_instruments_comma_separated():
    text, _ = sd.usb_install_outcome(
        wdi_available=True, ran_ok=True,
        still_unbound_names=[I1PRO, SPYDER], zadig_status=None)
    assert f"isn't bound to {I1PRO}, {SPYDER}." in text


def test_zadig_launched_repeats_the_cr30_warning():
    text, offer_zadig = sd.usb_install_outcome(
        wdi_available=False, ran_ok=False, still_unbound_names=[],
        zadig_status="launched")
    assert text == (
        "Zadig is open. Select your colorimeter, choose WinUSB, "
        "then click Install Driver."
        "<br><br><b>If you own a CR30:</b> do not pick the USB-serial "
        "device (CH340) in Zadig. That instrument is reached "
        "through its COM port, and giving it WinUSB would stop "
        "ChromIQ finding it at all."
    )
    assert offer_zadig is False


def test_the_zadig_download_page_repeats_the_cr30_warning_too():
    text, offer_zadig = sd.usb_install_outcome(
        wdi_available=False, ran_ok=False, still_unbound_names=[],
        zadig_status="download_page")
    assert text == (
        "Zadig isn't bundled with this build, so its download page "
        "has been opened in your browser.<br>"
        "Download and run <b>Zadig</b>, then: Options → List All Devices → "
        "select your colorimeter → choose WinUSB → Install Driver."
        "<br><br><b>If you own a CR30:</b> do not pick the USB-serial "
        "device (CH340) in Zadig. That instrument is reached "
        "through its COM port, and giving it WinUSB would stop "
        "ChromIQ finding it at all."
    )
    assert offer_zadig is False


def test_zadig_failing_entirely_falls_back_to_the_website():
    text, offer_zadig = sd.usb_install_outcome(
        wdi_available=False, ran_ok=False, still_unbound_names=[],
        zadig_status="failed")
    assert text == (
        "Could not open Zadig or its download page. Visit "
        "<b>https://zadig.akeo.ie</b> manually, or try running ChromIQ "
        "as Administrator."
    )
    assert offer_zadig is False


def test_an_unknown_zadig_status_lands_on_the_website_fallback():
    """Defensive: `launch_zadig()` returns one of three strings today, and a
    fourth must not produce an empty window."""
    text, _ = sd.usb_install_outcome(
        wdi_available=False, ran_ok=False, still_unbound_names=[],
        zadig_status="something-new")
    assert text.startswith("Could not open Zadig or its download page.")


def test_every_zadig_steer_in_the_outcomes_carries_the_cr30_warning():
    """The invariant `test_winusb_never_reaches_a_serial_instrument` asserts
    over the source, asserted here over the rendered text instead."""
    for status in ("launched", "download_page"):
        text, _ = sd.usb_install_outcome(
            wdi_available=False, ran_ok=False, still_unbound_names=[],
            zadig_status=status)
        assert "If you own a CR30" in text


# ---------------------------------------------------------------------------
# They really are pure
# ---------------------------------------------------------------------------

def test_the_text_functions_need_no_qt_and_no_windows(monkeypatch):
    """They are importable and callable with `sys.platform` lying, because they
    touch neither `ctypes` nor a widget. That is what makes them testable in
    the everyday tier on any host."""
    import sys
    monkeypatch.setattr(sys, "platform", "linux")
    assert sd.usb_installer_text([dev(I1PRO, False)], wdi_available=True)[1] == (
        "Install Driver")
    assert sd.usb_install_outcome(
        wdi_available=True, ran_ok=True, still_unbound_names=[],
        zadig_status=None)[1] is False


# ---------------------------------------------------------------------------
# The ghost devices
# ---------------------------------------------------------------------------
#
# Measured on the ARM64 machine, 2026-09-04, with no colorimeter attached at
# all: `enumerate_connected()` returned `X-Rite i1 Studio`, because it reads
# HKLM\SYSTEM\CurrentControlSet\Enum\USB, which remembers every USB device the
# machine has ever seen. The window then said "Connected colorimeter: X-Rite i1
# Studio" about hardware that was not in the building.

PRESENT_LIST = [
    r"USB\ROOT_HUB30\5&32007b01&0&0",
    r"USB\VID_0765&PID_6008\7&2a0c73b9&0&0002",
    r"USB\VID_1A86&PID_7523\7&3b74c78&0&1",
    r"USB\VID_0E0F&PID_000B&MI_00\7&2a0c73b9&0&0000",
]


@pytest.mark.parametrize("instance_id, expected", [
    (r"USB\VID_1A86&PID_7523\7&3b74c78&0&1", ("1a86", "7523")),
    (r"USB\VID_0765&PID_6008\7&2a0c73b9&0&0002", ("0765", "6008")),
    # a composite child carries a third token and must still resolve
    (r"USB\VID_0E0F&PID_000B&MI_00\7&2a0c73b9&0&0000", ("0e0f", "000b")),
    # hubs have no VID at all
    (r"USB\ROOT_HUB30\5&32007b01&0&0", None),
    (r"USB\ROOT_HUB20\4&2ec99baf&0", None),
    # malformed input must not raise
    ("", None),
    ("USB", None),
    (r"USB\NOT_A_DEVICE", None),
    (r"USB\VID_1A86\7&3b74c78&0&1", None),      # VID without PID
])
def test_the_ids_are_read_out_of_a_pnp_instance_id(instance_id, expected):
    assert sd.usb_ids_in_instance(instance_id) == expected


def test_the_ids_come_back_lower_case_whatever_case_windows_used():
    """`enumerate_connected` lower-cases what it reads, so the two sides of the
    comparison have to agree — Windows writes these IDs upper-case."""
    assert sd.usb_ids_in_instance(
        r"usb\vid_1a86&pid_7523\7&3b74c78&0&1") == ("1a86", "7523")


def _ghost():
    """A device Windows remembers and no longer has."""
    return SimpleNamespace(vid="0765", pid="6008", name="X-Rite i1 Studio",
                           has_winusb=True)


def _real():
    return SimpleNamespace(vid="0971", pid="2000", name=I1PRO, has_winusb=False)


def test_a_remembered_device_that_is_not_attached_is_dropped():
    present = {("0971", "2000")}
    assert sd.attached_only([_ghost(), _real()], present) == [_real()]


def test_an_attached_device_survives_the_filter():
    present = {("0765", "6008")}
    kept = sd.attached_only([_ghost()], present)
    assert [d.name for d in kept] == ["X-Rite i1 Studio"]


def test_the_filter_is_case_insensitive_on_both_sides():
    dev_upper = SimpleNamespace(vid="0765", pid="6008", name="x", has_winusb=True)
    assert sd.attached_only([dev_upper], {("0765", "6008")}) == [dev_upper]


def test_nothing_present_means_nothing_reported():
    assert sd.attached_only([_ghost(), _real()], set()) == []


def test_when_windows_cannot_be_asked_everything_is_shown():
    """The failure direction is chosen deliberately: a ghost is a lie the user
    can see and ignore, a filtered-out real instrument is a feature that
    silently refuses to help. Only the first is survivable."""
    devices = [_ghost(), _real()]
    assert sd.attached_only(devices, None) == devices


def test_the_filter_returns_a_new_list_and_does_not_mutate_the_input():
    devices = [_ghost(), _real()]
    out = sd.attached_only(devices, None)
    assert out is not devices
    assert len(devices) == 2


def test_present_usb_ids_says_it_cannot_ask_off_windows(monkeypatch):
    monkeypatch.setattr(sd, "_sys", SimpleNamespace(platform="linux"))
    assert sd.present_usb_ids() is None


def test_present_usb_ids_survives_a_missing_cfgmgr32(monkeypatch):
    """A ctypes failure must not take the Preferences window down with it."""
    import ctypes

    def boom(*_a, **_kw):
        raise OSError("cfgmgr32 is not here")

    monkeypatch.setattr(sd, "_sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(ctypes, "WinDLL", boom, raising=False)
    assert sd.present_usb_ids() is None


def test_the_whole_chain_turns_a_ghost_into_no_colorimeter_detected():
    """The bug, end to end, in the words the user reads."""
    remembered = [_ghost()]
    present = {("1a86", "7523")}       # only the serial bridge is attached
    msg, btn = sd.usb_installer_text(
        sd.attached_only(remembered, present), wdi_available=True)
    assert msg.startswith("<b>No colorimeter detected.</b>")
    assert "i1 Studio" not in msg
    assert btn is None

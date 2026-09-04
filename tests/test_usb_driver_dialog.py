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

from pathlib import Path
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
        "then click <b>Check again</b>."
    )
    assert btn is None, "there is nothing to install for, so no primary button"


def test_the_only_button_the_first_section_names_is_one_that_exists():
    """The button used to be called Refresh. It is called Check again now, and
    a message pointing at a button that is not on the screen is worse than no
    message at all."""
    msg, _btn = sd.usb_installer_text([], wdi_available=True)
    assert "Refresh" not in msg
    assert "Check again" in msg


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


# ---------------------------------------------------------------------------
# The COM-port section (the CR30's kind of driver)
# ---------------------------------------------------------------------------

def bridge(port=None):
    """A `core.ch34x_driver.DeviceState` as far as the text functions care."""
    return SimpleNamespace(instance_id=r"USB\VID_1A86&PID_7523\7&x&0&1",
                           vid="1a86", pid="7523", port=port)


def _serial(states, **kw):
    return sd.serial_section_text(states, **kw)


# --- the promise that must never break -------------------------------------

@pytest.mark.parametrize("states, kw", [
    ([], {}),
    ([bridge()], {}),
    ([bridge("COM5")], {}),
    ([bridge("COM5"), bridge()], {}),
    ([bridge("COM3"), bridge("COM5")], {}),
    ([], {"offer_anyway": True}),
    ([bridge("COM5")], {"offer_anyway": True}),
])
def test_no_state_ever_claims_a_cr30_was_detected(states, kw):
    """1a86:7523 is a generic bridge sitting inside millions of Arduinos.
    Windows can say a bridge is attached; it can never say what is on the far
    end of it. The word "detected" next to "CR30" would be a lie in every one
    of these states."""
    msg, _p, _s = _serial(states, **kw)
    lowered = msg.lower()
    for lie in ("cr30 detected", "cr30 is connected", "cr30 is attached",
                "found your cr30", "cr30 found"):
        assert lie not in lowered, f"the section claims to have found a CR30: {lie!r}"


@pytest.mark.parametrize("states, kw", [
    ([], {}), ([bridge()], {}), ([bridge("COM5")], {}),
    ([bridge("COM5"), bridge()], {}), ([], {"offer_anyway": True}),
])
def test_the_section_never_ships_a_bracketed_plural(states, kw):
    msg, _p, _s = _serial(states, **kw)
    for bad in ("device(s)", "colorimeter(s)", "instrument(s)", "driver(s)",
                "bridge(s)", "port(s)"):
        assert bad not in msg


@pytest.mark.parametrize("states, kw", [
    ([], {}), ([bridge()], {}), ([bridge("COM5")], {}),
    ([bridge("COM5"), bridge()], {}), ([], {"offer_anyway": True}),
])
def test_there_is_always_a_way_in(states, kw):
    """Basti's Q3: always reachable, never auto-triggered. A driverless CH340
    reports "no problem" to Windows and an instrument too broken to enumerate
    reports nothing at all, so a section that only spoke when it had something
    to say would be silent for exactly the person who needs it."""
    _msg, primary, secondary = _serial(states, **kw)
    assert primary or secondary, "the section offered no route at all"


# --- nothing attached -------------------------------------------------------

def test_nothing_attached_says_so_and_offers_the_not_listed_route():
    msg, primary, secondary = _serial([])
    assert msg.startswith(
        "<b>ChromIQ cannot see a USB-to-serial bridge on this computer at the "
        "moment.</b>")
    assert primary is None, "nothing is attached, so nothing is offered yet"
    assert secondary == "My instrument is not listed…"
    assert "cable" in msg and "socket" in msg


def test_nothing_attached_explains_what_the_bridge_is_for():
    msg, _p, _s = _serial([])
    assert "turn the USB cable into a COM port" in msg
    assert "no port appears" in msg


# --- attached and working ---------------------------------------------------

def test_a_working_bridge_is_offered_nothing():
    """Decision 3, in as many words: never offer anything for a device that
    already works. There is nothing to fix and an install could only break it."""
    msg, primary, secondary = _serial([bridge("COM5")])
    assert primary is None
    assert secondary == "My instrument is not listed…"
    assert msg.startswith(
        "<b>A USB-to-serial bridge is connected, and Windows already has a "
        "working driver for it.</b> It has been given COM5, and there is "
        "nothing for ChromIQ to install.")


def test_two_working_bridges_use_the_plural_and_name_both_ports():
    msg, primary, _s = _serial([bridge("COM7"), bridge("COM3")])
    assert primary is None
    assert msg.startswith(
        "<b>Several USB-to-serial bridges are connected, and Windows already "
        "has a working driver for every one of them.</b> They have been given "
        "COM3, COM7,")
    assert "COM3, COM7" in msg, "ports are sorted so the sentence is stable"


def test_a_working_bridge_still_says_chromiq_cannot_identify_it():
    msg, _p, _s = _serial([bridge("COM5")])
    assert "ChromIQ cannot tell you that this is your CR30" in msg


# --- attached with no driver: the state the feature exists for --------------

def test_a_driverless_bridge_gets_the_offer_and_both_buttons():
    msg, primary, secondary = _serial([bridge()])
    assert msg.startswith(
        "<b>A USB-to-serial bridge is connected, and Windows has no working "
        "driver for it.</b>")
    assert primary == "Get the driver…"
    assert secondary == "I already have the folder…"


def test_the_driverless_wording_says_what_the_consequence_is():
    msg, _p, _s = _serial([bridge()])
    assert "No COM port has appeared for it" in msg
    assert "nothing on this computer can talk to it" in msg
    assert "The CR30 is reached through a bridge of exactly this kind" in msg


def test_the_offer_promises_the_checks_and_the_permission_prompt():
    msg, _p, _s = _serial([bridge()])
    assert "check what arrived" in msg
    assert "permission prompt" in msg
    assert "nothing is removed" in msg


def test_one_broken_bridge_beside_a_working_one_still_offers_the_install():
    """A user with an Arduino on COM3 and a dead CR30 must not be told
    everything is fine because *something* has a port."""
    msg, primary, _s = _serial([bridge("COM3"), bridge()])
    assert primary == "Get the driver…"
    assert "has no working driver for it" in msg


# --- "my instrument is not listed" -----------------------------------------

def test_the_not_listed_route_offers_without_claiming_to_have_found_anything():
    msg, primary, secondary = _serial([], offer_anyway=True)
    assert primary == "Get the driver…"
    assert secondary == "I already have the folder…"
    assert msg.startswith(
        "<b>You told ChromIQ your instrument is not in the list above.</b>")
    assert "A USB-to-serial bridge is connected" not in msg


def test_the_not_listed_route_works_even_when_a_bridge_is_present_and_fine():
    """The exposed case: an Arduino holds COM3, the CR30 does not enumerate at
    all, so the automatic reading says "everything is fine" and is useless."""
    _msg, primary, _s = _serial([bridge("COM3")], offer_anyway=True)
    assert primary == "Get the driver…"


# ---------------------------------------------------------------------------
# The announcement that comes before the Windows permission prompt
# ---------------------------------------------------------------------------

def test_the_uac_prompt_is_announced_before_it_appears():
    text = sd.serial_install_intro_text(r"C:\x\drivers\2026", "ARM64")
    assert "Windows will ask your permission at step 4" in text
    assert "blue border" in text
    assert "comes from Windows itself, not from ChromIQ" in text
    assert "Choosing No stops the installation there with nothing changed" in text


def test_the_announcement_names_the_folder_and_the_processor():
    text = sd.serial_install_intro_text(r"C:\x\drivers\2026", "ARM64")
    assert r"C:\x\drivers\2026" in text
    assert "(ARM64)" in text


def test_the_announcement_admits_the_download_cannot_be_pinned():
    """Decision 9: no checksum, no versioned link, HTTP 200 for an error. The
    UI may promise "we checked what arrived" and never "we know what we asked
    for"."""
    text = sd.serial_install_intro_text("f", "ARM64")
    assert "no checksum and no fixed link to a particular version" in text
    assert "a check on what did arrive, never a guarantee of what was asked for" in text


def test_the_announcement_promises_nothing_is_removed():
    text = sd.serial_install_intro_text("f", "ARM64")
    assert "nothing here removes or replaces a driver" in text


def test_the_announcement_says_the_port_is_checked_afterwards():
    text = sd.serial_install_intro_text("f", "ARM64")
    assert "a driver can install perfectly and still not attach itself" in text


# ---------------------------------------------------------------------------
# The outcomes
# ---------------------------------------------------------------------------

ALL_STAGES = ["bound", "not_bound", "install_failed", "cancelled",
              "package_rejected", "download_failed"]


@pytest.mark.parametrize("stage", ALL_STAGES)
def test_no_outcome_ever_mentions_roll_back_driver(stage):
    """Decision 10, and required change 18. *Roll Back Driver* is greyed out
    unless the device already had a working driver once — and the person
    reading any of these is by definition the person whose instrument never
    had one. Sending them to a greyed-out button is worse than saying nothing.
    """
    text, _ = sd.serial_outcome_text(stage=stage, detail="d", folder="f",
                                     ports="COM5")
    lowered = text.lower()
    assert "roll back" not in lowered
    assert "rollback" not in lowered


@pytest.mark.parametrize("stage", ALL_STAGES)
def test_no_outcome_ships_a_bracketed_plural(stage):
    text, _ = sd.serial_outcome_text(stage=stage, detail="d", folder="f",
                                     ports="COM5")
    for bad in ("device(s)", "driver(s)", "instrument(s)", "port(s)"):
        assert bad not in text


@pytest.mark.parametrize("stage", ["not_bound", "install_failed", "cancelled",
                                   "package_rejected", "download_failed"])
def test_every_failure_says_nothing_was_changed(stage):
    """Non-negotiable 1: ChromIQ never removes or overwrites a driver, and the
    user must be told that, because "the install failed" otherwise reads as
    "my computer is now in an unknown state"."""
    text, _ = sd.serial_outcome_text(stage=stage, detail="d", folder="f")
    lowered = text.lower()
    assert ("nothing" in lowered
            and ("changed" in lowered or "removed" in lowered
                 or "installed" in lowered))


def test_success_names_the_port_and_explains_why_that_is_the_test():
    text, offer = sd.serial_outcome_text(stage="bound", ports="COM5")
    assert text.startswith(
        "<b>It worked.</b> Windows installed the driver, and a COM port has "
        "appeared for the adapter: COM5.")
    assert "does not take the installer's word for it" in text
    assert "Measure tab" in text
    assert offer is False


def test_the_hard_case_says_plainly_what_was_tried():
    """Decision 10: everything right, still not bound. Say what was done, and
    offer routes that are not greyed out."""
    text, offer = sd.serial_outcome_text(stage="not_bound", detail="ignored",
                                         folder=r"C:\pkg")
    assert text.startswith(
        "<b>Everything ChromIQ could check passed, and there is still no COM "
        "port.</b>")
    assert "downloaded and unpacked" in text
    assert "signature was verified" in text
    assert "reported the installation as finished" in text
    # the three routes that are actually available to this user
    assert "Unplug the instrument" in text
    assert "Device Manager" in text
    assert r"C:\pkg" in text
    assert "a cable that carries power but not data" in text
    assert offer is False


def test_the_hard_case_ends_by_saying_there_is_nothing_to_undo():
    text, _ = sd.serial_outcome_text(stage="not_bound", folder="f")
    assert text.endswith(
        "Nothing has been removed or replaced, so there is nothing to undo. "
        "Whatever your computer had before, it still has.")


def test_a_cancelled_install_is_not_treated_as_a_failure():
    text, offer = sd.serial_outcome_text(stage="cancelled", folder=r"C:\pkg")
    assert text.startswith(
        "<b>The installation was stopped at the Windows permission prompt.</b>")
    assert "exactly what choosing No there is supposed to do" in text
    assert r"C:\pkg" in text
    assert "Device Manager" not in text, (
        "someone who deliberately said No does not need a wall of recovery advice")
    assert offer is False


def test_a_failed_install_carries_the_reason_and_the_manual_route():
    text, offer = sd.serial_outcome_text(
        stage="install_failed",
        detail="Windows refused the change.", folder=r"C:\pkg")
    assert "Windows refused the change." in text
    assert "Device Manager" in text
    assert "Browse my computer for drivers" in text
    assert r"C:\pkg" in text
    assert offer is False


def test_a_rejected_package_explains_why_the_refusal_is_the_point():
    text, offer = sd.serial_outcome_text(
        stage="package_rejected",
        detail="It declares NT, NTamd64 — not this computer's ARM64.",
        folder=r"C:\pkg")
    assert "It declares NT, NTamd64" in text
    assert "installs without a single complaint and then simply never works" in text
    assert "ARM-based computers only appears in the newer releases" in text
    assert offer is True, "the user must be able to point at a different folder"


def test_a_failed_download_offers_the_do_it_yourself_route():
    text, offer = sd.serial_outcome_text(
        stage="download_failed", detail="The connection timed out.")
    assert "The connection timed out." in text
    assert "company network that inspects encrypted traffic" in text
    assert sd.WCH_PACKAGE_PAGE in text
    assert offer is True


def test_the_do_it_yourself_route_points_at_the_zip_and_warns_off_the_exe():
    """The .EXE installs 3.5.2019.1, which has no ARM64 support — it is the
    installer that left this project's own machine driverless."""
    text, _ = sd.serial_outcome_text(stage="download_failed", detail="d")
    assert "the ZIP, not the .EXE installer" in text
    assert "cannot work on ARM-based computers" in text


def test_the_download_page_is_the_zip_page():
    assert sd.WCH_PACKAGE_PAGE.endswith("CH341SER_ZIP.html")


def test_an_unknown_stage_falls_back_to_the_download_wording():
    text, _ = sd.serial_outcome_text(stage="something-new", detail="d")
    assert text.startswith("<b>ChromIQ could not get a usable driver package.</b>")


# ---------------------------------------------------------------------------
# The manual route, on its own
# ---------------------------------------------------------------------------

def test_the_manual_route_names_every_click_by_the_words_on_screen():
    text = sd.serial_manual_route_text(r"C:\pkg\WIN 1X")
    for label in ("Device Manager", "Update driver",
                  "Browse my computer for drivers", "Ports (COM &amp; LPT)",
                  "Other devices"):
        assert label in text
    assert r"C:\pkg\WIN 1X" in text


def test_the_manual_route_never_says_roll_back_driver():
    text = sd.serial_manual_route_text("f")
    assert "roll back" not in text.lower()


# ---------------------------------------------------------------------------
# Where the download lands
# ---------------------------------------------------------------------------

def test_the_staging_folder_is_under_the_apps_own_name(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\x\AppData\Local")
    root = sd.driver_staging_root()
    assert root.parts[-2:] == ("ChromIQ", "drivers")


def test_the_staging_folder_falls_back_to_the_home_directory(monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert sd.driver_staging_root().parts[-2:] == ("ChromIQ", "drivers")


# ---------------------------------------------------------------------------
# The one place this file reaches into the other agent's module
# ---------------------------------------------------------------------------

def test_cancelled_is_recognised_from_the_sentence_core_actually_writes():
    """`core.ch34x_driver.install()` returns `(bool, str)` with no
    machine-readable code, so the dialog has to recognise "the user said No"
    from the prose. That is fragile by construction — this test is the tripwire
    that goes red the day the sentence is reworded, instead of the user quietly
    getting a wall of recovery advice for a button they pressed on purpose."""
    ch34x = pytest.importorskip("core.ch34x_driver")
    outcomes = getattr(ch34x, "_PNPUTIL_OUTCOMES", None)
    if outcomes is None or 1223 not in outcomes:
        pytest.skip("core.ch34x_driver does not expose the exit-code table")
    _ok, sentence = outcomes[1223]
    assert sd._install_was_cancelled(sentence), (
        "core reworded its cancelled message; ui/dialogs/settings_dialog.py's "
        f"_CANCELLED_PREFIX no longer matches it: {sentence!r}")


def test_a_genuine_failure_is_not_mistaken_for_a_cancellation():
    assert not sd._install_was_cancelled("Windows refused the change.")
    assert not sd._install_was_cancelled("")


# ---------------------------------------------------------------------------
# Not while a measurement is running (Basti's Q11)
# ---------------------------------------------------------------------------
#
# Only the driver helper is blocked. Preferences itself stays open during a
# measurement, which `ui/main_window.py:1150-1155` calls deliberate policy, and
# nothing here overturns it — the driver helper is singled out because it is the
# one window in Preferences that can END a measurement.

class _Holder:
    """The lease keeps its owner by weak reference, and `SimpleNamespace` does
    not support one — so the stand-in for a window needs to be a real class."""


def test_nothing_running_means_nothing_is_blocked():
    from core import instrument_lease
    assert instrument_lease.holder() is None, "a previous test leaked a claim"
    assert sd.measurement_in_progress() is None


def test_the_lease_is_the_signal_not_the_process_state():
    """`core/instrument_lease.py` exists precisely because
    `ArgyllRunner.is_running` answers from PROCESS state, and a CR30 session
    driven through `DeviceReader` spawns no process at all. Tools > Read single
    patches takes the lease and starts nothing — so the lease is the only signal
    that sees it."""
    from core import instrument_lease

    owner = _Holder()          # a stand-in for the window holding it
    assert instrument_lease.acquire(owner, instrument_lease.SPOT_TOOL)
    try:
        where = sd.measurement_in_progress()
        assert where is not None
        assert where == instrument_lease.where_label(instrument_lease.SPOT_TOOL)
    finally:
        instrument_lease.release(owner)
    assert sd.measurement_in_progress() is None


def test_the_measure_tab_holding_the_lease_is_named_too():
    from core import instrument_lease

    owner = _Holder()
    assert instrument_lease.acquire(owner, instrument_lease.MEASURE_TAB)
    try:
        assert sd.measurement_in_progress() == instrument_lease.where_label(
            instrument_lease.MEASURE_TAB)
    finally:
        instrument_lease.release(owner)


def test_the_main_windows_own_measuring_flag_is_read_through_the_parent_chain():
    """The ArgyllCMS instruments do not take the lease — that is deliberate, and
    documented in `core/instrument_lease.py`. `_measuring` on the main window is
    what covers a chartread session, and the dialog reaches it by walking up
    from itself."""
    from core import instrument_lease

    class FakeWindow:
        _measuring = True

        def parent(self):
            return None

    class FakeDialog:
        def __init__(self, win):
            self._win = win

        def parent(self):
            return self._win

    win = FakeWindow()
    assert sd.measurement_in_progress(FakeDialog(win)) == (
        instrument_lease.where_label(instrument_lease.MEASURE_TAB))
    win._measuring = False
    assert sd.measurement_in_progress(FakeDialog(win)) is None


def test_a_parent_chain_that_loops_does_not_hang_the_app():
    """A guard must never be the thing that breaks. A cycle in the parent chain
    would be a Qt bug, but an infinite loop inside Preferences would be ours."""
    class Loop:
        def parent(self):
            return self

    assert sd.measurement_in_progress(Loop()) is None


def test_a_broken_lease_module_does_not_take_preferences_down(monkeypatch):
    from core import instrument_lease

    def boom():
        raise RuntimeError("the lease exploded")

    monkeypatch.setattr(instrument_lease, "holder", boom)
    assert sd.measurement_in_progress() is None


def test_the_refusal_explains_the_consequence_not_just_the_rule():
    text = sd.measurement_block_text("the Measure tab")
    assert text.startswith("<b>Not while a measurement is running.</b>")
    assert "the Measure tab" in text
    assert "restarts the connection Windows holds to the instrument" in text
    assert "the patches measured so far would be lost" in text


def test_the_refusal_says_how_to_get_past_it():
    text = sd.measurement_block_text("the Measure tab")
    assert "Let the measurement finish, or stop it" in text


def test_the_refusal_says_the_rest_of_preferences_is_untouched():
    """Because it is. Widening the block to all of Preferences would overturn a
    policy `ui/main_window.py:1150-1155` calls deliberate, and this PR does not
    do that."""
    text = sd.measurement_block_text("the Measure tab")
    assert "Everything else in Preferences stays available" in text


def test_the_refusal_ships_no_bracketed_plural():
    text = sd.measurement_block_text("the Measure tab")
    for bad in ("device(s)", "driver(s)", "instrument(s)", "patch(es)"):
        assert bad not in text


def test_the_guard_is_the_first_thing_the_driver_helper_does():
    """Proved from the source rather than assumed: if the refusal came after
    the device enumeration, a measurement could be interrupted by the very act
    of opening the window."""
    import inspect
    src = inspect.getsource(sd.SettingsDialog._show_usb_installer)
    guard = src.index("measurement_in_progress")
    enumerate_call = src.index("enumerate_connected(")
    assert guard < enumerate_call, (
        "the driver helper touches the hardware before it checks whether a "
        "measurement is running")


# ---------------------------------------------------------------------------
# "ChromIQ cannot tell what CPU this is"
# ---------------------------------------------------------------------------
#
# `core.ch34x_driver.machine_arch()` returns "" for 32-bit x86, for an
# architecture it does not recognise, and off Windows, and "" means REFUSE, not
# "guess". On 32-bit the correct INF section really is the bare `NT` one that
# the package gate rejects everywhere else, so there is no honest answer and no
# safe install to offer. That is a state with a cause, not an error.

def test_the_unknown_processor_state_refuses_and_says_why():
    text = sd.serial_unknown_arch_text()
    assert text.startswith(
        "<b>ChromIQ cannot tell what kind of processor this computer has, so "
        "it is not going to install a driver here.</b>")
    assert "A driver package has to match the processor" in text
    assert "installing a driver nobody has checked" in text


def test_the_unknown_processor_state_still_offers_a_way_through():
    """Refusing is right; leaving the user with nothing is not."""
    text = sd.serial_unknown_arch_text()
    assert sd.WCH_PACKAGE_PAGE in text
    assert "the ZIP, not the .EXE installer" in text
    assert "Device Manager" in text
    assert "Browse my computer for drivers" in text


def test_the_unknown_processor_state_never_mentions_roll_back_driver():
    assert "roll back" not in sd.serial_unknown_arch_text().lower()


def test_the_unknown_processor_state_ships_no_bracketed_plural():
    text = sd.serial_unknown_arch_text()
    for bad in ("device(s)", "driver(s)", "instrument(s)", "port(s)"):
        assert bad not in text


def test_the_arch_helper_reports_an_empty_string_rather_than_guessing(monkeypatch):
    """Pinned because the tempting bug is to substitute a friendly placeholder
    for "", which would turn a refusal into an install against an unknown CPU."""
    import inspect
    src = inspect.getsource(sd.SettingsDialog._serial_machine_arch)
    assert "machine_arch() or \"\"" in src
    assert 'tr("unknown")' not in src


def test_both_serial_entry_points_check_the_processor_first():
    """Proved from the source: an install must not begin — not even a download
    — on a machine whose CPU ChromIQ could not identify."""
    import inspect
    for method in (sd.SettingsDialog._serial_get_driver,
                   sd.SettingsDialog._serial_from_folder):
        src = inspect.getsource(method)
        assert "serial_unknown_arch_text" in src, (
            f"{method.__name__} does not handle an unknown processor")


# ---------------------------------------------------------------------------
# Never accuse the user's download of being malicious
# ---------------------------------------------------------------------------
#
# Two measured facts make a confident "this file has been tampered with"
# indefensible: the documented WTD_SAFER_FLAG breaks driver verification on a
# genuinely WHQL-signed catalogue, and WCH's catalogue is SHA-1, so a SHA-256
# check fails in a way indistinguishable from tampering. Both are handled in
# core — but if a verification ever does fail, the honest line is that ChromIQ
# could not confirm the package is genuine, not that somebody attacked you.

@pytest.mark.parametrize("stage", ALL_STAGES)
def test_no_outcome_accuses_the_user_of_a_tampered_download(stage):
    text, _ = sd.serial_outcome_text(stage=stage, detail="", folder="f",
                                     ports="COM5")
    lowered = text.lower()
    for accusation in ("tampered", "tamper", "malicious", "malware", "virus",
                       "has been altered", "attack"):
        assert accusation not in lowered, (
            f"the {stage} window accuses the user's download: {accusation!r}")


def test_the_section_and_the_announcement_do_not_accuse_either():
    texts = [sd.serial_section_text([bridge()])[0],
             sd.serial_section_text([])[0],
             sd.serial_install_intro_text("f", "ARM64"),
             sd.serial_unknown_arch_text(),
             sd.serial_manual_route_text("f")]
    for text in texts:
        lowered = text.lower()
        for accusation in ("tampered", "malicious", "malware", "virus"):
            assert accusation not in lowered


# ---------------------------------------------------------------------------
# The button that opens all of this
# ---------------------------------------------------------------------------

def test_the_button_no_longer_promises_an_install():
    """It opens a window that covers two unrelated kinds of driver and can
    report that nothing needs installing at all. "Install USB Driver…" was
    wrong twice over: about what it does, and about whether it will do it."""
    import inspect
    src = inspect.getsource(sd.SettingsDialog._build_ui)
    assert 'tr("Instrument drivers…")' in src
    # the old label may still be named in a comment explaining the change;
    # what must not survive is a tr() call carrying it to the screen.
    assert 'tr("Install USB Driver' not in src


def test_the_rename_reached_every_catalogue():
    """The gate this commit had to satisfy. `test_catalog_is_complete` and
    `test_catalog_has_no_stale_keys` are parametrised over twelve catalogues,
    so a renamed key has to move in all twelve at once or twenty-four tests go
    red. Pinned here as well, because the failure mode when it is missed is a
    button that silently reverts to English in eleven languages."""
    import json
    from pathlib import Path
    root = Path(sd.__file__).resolve().parent.parent.parent / "data" / "i18n"
    codes = sorted(p.stem for p in root.glob("*.json"))
    assert len(codes) == 12, codes
    for code in codes:
        cat = json.loads(root.joinpath(f"{code}.json").read_text(encoding="utf-8"))
        assert "Instrument drivers…" in cat, f"[{code}] the button lost its key"
        assert cat["Instrument drivers…"] != "Instrument drivers…", (
            f"[{code}] the button is still English")
        assert "Install USB Driver…" not in cat, (
            f"[{code}] the old key was left behind and is now stale")


# ---------------------------------------------------------------------------
# A message that names a button must get the name FROM the button
# ---------------------------------------------------------------------------
#
# THE FAULT THIS PREVENTS, in the words of the screenshot it was found in: the
# window's title and buttons were translated and one paragraph was not, so a
# German user read "then click Check again" under a button labelled ERNEUT
# PRÜFEN and went looking for a control that is not on the screen.
#
# Wrapping the paragraph in tr() is only half a fix. If the button's name stays
# an English literal INSIDE the translated sentence, the sentence and the button
# are two independent keys, and the next person to translate them — or to rename
# the button — separates them again. The paragraph must interpolate the button's
# own label, so that there is only one string to get right.
#
# These tests ask the question in every language ChromIQ ships, of the rendered
# output rather than of the source, so the invariant holds however it is spelled.

ALL_CODES = [p.stem for p in
             (Path(sd.__file__).resolve().parent.parent.parent
              / "data" / "i18n").glob("*.json")]


@pytest.fixture
def in_language():
    """Render in one language, and always come back to English.

    The characterisation tests above assert English character for character, so
    a language left set here would fail them in whatever order pytest happens to
    run. The reset is in a fixture, not at the end of each test, because a
    failing assertion would skip it.
    """
    from core import i18n

    def _set(code):
        i18n.set_language(code)
        return code
    yield _set
    i18n.set_language("en")


@pytest.mark.parametrize("code", ALL_CODES)
def test_the_no_device_message_names_the_button_that_is_really_there(
        code, in_language):
    """`Check again` is built with tr(), so in German the button reads ERNEUT
    PRÜFEN. The sentence pointing at it has to say the same thing."""
    in_language(code)
    msg, _btn = sd.usb_installer_text([], wdi_available=True)
    assert sd._label_check_again() in msg, (
        f"[{code}] the message does not name the button as it is labelled")


@pytest.mark.parametrize("code", ALL_CODES)
def test_the_install_message_names_the_install_button(code, in_language):
    in_language(code)
    msg, btn = sd.usb_installer_text([dev(I1PRO, False)], wdi_available=True)
    assert btn in msg, f"[{code}] {btn!r} is not named in its own message"


@pytest.mark.parametrize("code", ALL_CODES)
def test_the_zadig_message_names_the_zadig_button(code, in_language):
    in_language(code)
    msg, btn = sd.usb_installer_text([dev(I1PRO, False)], wdi_available=False)
    assert btn in msg, f"[{code}] {btn!r} is not named in its own message"


@pytest.mark.parametrize("code", ALL_CODES)
@pytest.mark.parametrize("wdi", [True, False])
def test_the_already_installed_message_names_whichever_button_it_gets(
        code, wdi, in_language):
    in_language(code)
    msg, btn = sd.usb_installer_text([dev(I1PRO, True)], wdi_available=wdi)
    assert btn in msg, f"[{code}] wdi={wdi}: {btn!r} is not named in its message"


@pytest.mark.parametrize("code", ALL_CODES)
def test_the_outcomes_that_offer_zadig_name_the_zadig_button(code, in_language):
    """`Try Zadig` is the label `_show_usb_installer` passes to
    `_driver_notice`, so it is what the user sees on the button."""
    in_language(code)
    for ran_ok, unbound in ((False, []), (True, [I1PRO])):
        text, offer = sd.usb_install_outcome(
            wdi_available=True, ran_ok=ran_ok,
            still_unbound_names=unbound, zadig_status=None)
        assert offer is True
        assert sd._label_try_zadig() in text, (
            f"[{code}] the outcome offers a button it does not name")


def test_the_labels_come_from_tr_and_not_from_a_literal():
    """The mechanism, pinned from the source. Every one of these is a single
    tr() call, which is what makes interpolating them worth anything: a label
    assembled some other way could drift from the catalogue."""
    import inspect
    for fn in (sd._label_check_again, sd._label_install_driver,
               sd._label_reinstall_driver, sd._label_open_zadig,
               sd._label_try_zadig):
        src = inspect.getsource(fn)
        assert src.count("tr(") == 1, f"{fn.__name__} is not one tr() call"
        assert "return tr(" in src


def test_no_message_hard_codes_a_button_name_in_english():
    """The source-level half of the invariant.

    Interpolation is the fix; this is the tripwire for someone adding a new
    sentence the easy way. Every message built by these two functions must
    reach a button's name through `{button}` / `{check_again}`, never by
    spelling it out.
    """
    import inspect
    OURS = ("Check again", "Reinstall Driver", "Open Zadig", "Try Zadig")
    for fn in (sd.usb_installer_text, sd.usb_install_outcome):
        src = inspect.getsource(fn)
        # drop comments: they discuss the labels by name, on purpose
        body = "\n".join(l for l in src.split("\n")
                         if not l.strip().startswith("#"))
        for label in OURS:
            assert f"<b>{label}</b>" not in body, (
                f"{fn.__name__} spells out {label!r} instead of interpolating "
                "the button's own tr() label")


# ---------------------------------------------------------------------------
# The names that must NOT be translated
# ---------------------------------------------------------------------------
#
# The mirror image of the rule above, and it bites in the opposite direction.
# Zadig ships one user interface and it is English. Translating "Options → List
# All Devices" into German would send the user hunting through a menu that does
# not contain those words — the same fault as naming a button that is not there,
# arrived at from the other side.
#
# Windows is different: it IS translated, so "click Yes" belongs inside the key
# for the translator to render as "Ja". That is why this list is Zadig's
# controls only, and not every foreign word in the window.

ZADIG_CONTROLS = ("Options → List All Devices", "Install Driver",
                  "Replace Driver", "WinUSB", "libusb-win32")


@pytest.mark.parametrize("code", ALL_CODES)
def test_zadigs_own_controls_are_never_translated(code, in_language):
    """Zadig's menu items must survive verbatim into every language."""
    in_language(code)
    steps, _btn = sd.usb_installer_text([dev(I1PRO, False)], wdi_available=False)
    for control in ("Options → List All Devices", "WinUSB", "Install Driver"):
        assert control in steps, (
            f"[{code}] Zadig's {control!r} was translated — the user will look "
            "for it in Zadig's English interface and not find it")

    launched, _ = sd.usb_install_outcome(
        wdi_available=False, ran_ok=False, still_unbound_names=[],
        zadig_status="launched")
    assert "WinUSB" in launched and "Install Driver" in launched

    unbound, _ = sd.usb_install_outcome(
        wdi_available=True, ran_ok=True, still_unbound_names=[I1PRO],
        zadig_status=None)
    for control in ("WinUSB", "libusb-win32", "Replace Driver"):
        assert control in unbound, f"[{code}] Zadig's {control!r} was translated"


@pytest.mark.parametrize("code", ALL_CODES)
def test_the_zadig_address_survives_every_language(code, in_language):
    """A URL a translator retypes is a URL that can acquire a typo in one
    language only, so it is interpolated rather than left inside the key."""
    in_language(code)
    text, _ = sd.usb_install_outcome(
        wdi_available=False, ran_ok=False, still_unbound_names=[],
        zadig_status="failed")
    assert sd.ZADIG_SITE in text
    assert sd.ZADIG_SITE == "https://zadig.akeo.ie"


# ---------------------------------------------------------------------------
# The English fault that was hiding underneath the German one
# ---------------------------------------------------------------------------

def test_a_working_device_without_wdi_simple_names_open_zadig_not_reinstall():
    """FIXED HERE. The "already installed" paragraph said "click <b>Reinstall
    Driver</b>" in both branches, but without wdi-simple the button built
    underneath it is `Open Zadig`. So this window has been naming a
    non-existent button in ENGLISH, on every build without the bundled
    installer, since long before the German section existed —
    `test_a_working_device_without_wdi_simple_still_says_open_zadig` asserted
    the button and never read the sentence.

    Interpolating the label fixes it for the same reason it fixes the German
    one: there is now only one name, and the button owns it.
    """
    msg, btn = sd.usb_installer_text([dev(I1PRO, True)], wdi_available=False)
    assert btn == "Open Zadig"
    assert "<b>Open Zadig</b>" in msg
    assert "Reinstall Driver" not in msg, (
        "the message still names the button from the other branch")


def test_the_whole_window_is_one_language_or_the_other(in_language):
    """The defect, stated as one assertion.

    Round 1 translated this window's titles, its second section and its buttons
    and left the WinUSB body in English, which reads worse than leaving all of
    it English: German, English, German, German looks broken rather than
    untranslated. Every string the window builds must move together.
    """
    in_language("de")
    msg, _btn = sd.usb_installer_text([], wdi_available=True)
    assert "No colorimeter detected" not in msg
    assert "Make sure your device is plugged in" not in msg
    assert "Kein Farbmessgerät gefunden" in msg

    listed, _btn = sd.usb_installer_text([dev(I1PRO, False)], wdi_available=True)
    assert "Connected colorimeter" not in listed
    assert "driver not installed" not in listed

    ok, _ = sd.usb_install_outcome(wdi_available=True, ran_ok=True,
                                   still_unbound_names=[], zadig_status=None)
    assert "installed successfully" not in ok


# ---------------------------------------------------------------------------
# The same rule, over the COM-port half
# ---------------------------------------------------------------------------
#
# Four sentences in this half spelled a button out in English too, and one of
# them was worse than the WinUSB cases: `<b>My instrument is not listed</b>` was
# a SECOND catalogue key, differing from the button's own
# `My instrument is not listed…` by the trailing ellipsis. Two keys for one
# control is drift waiting to happen — a translator sees them in different
# places, months apart, and has no way to know they must agree.

@pytest.mark.parametrize("code", ALL_CODES)
def test_the_working_bridge_names_the_not_listed_button(code, in_language):
    in_language(code)
    text, primary, secondary = sd.serial_section_text([bridge("COM5")])
    assert primary is None, "a bridge that works must not be offered an install"
    assert secondary == sd._label_not_listed()
    assert sd._in_prose(secondary) in text, (
        f"[{code}] the message does not name its button")


@pytest.mark.parametrize("code", ALL_CODES)
def test_the_no_bridge_message_names_the_not_listed_button(code, in_language):
    in_language(code)
    text, _primary, secondary = sd.serial_section_text([])
    assert sd._in_prose(secondary) in text, (
        f"[{code}] the message does not name its button")


@pytest.mark.parametrize("code", ALL_CODES)
def test_the_failed_install_advice_names_the_check_again_button(
        code, in_language):
    in_language(code)
    text, _ = sd.serial_outcome_text(stage="not_bound", folder="F")
    assert sd._label_check_again() in text, (
        f"[{code}] step 1 tells the user to press something that is not there")


@pytest.mark.parametrize("code", ALL_CODES)
def test_the_download_failure_names_the_folder_button(code, in_language):
    in_language(code)
    text, _ = sd.serial_outcome_text(stage="download_failed", detail="x")
    assert sd._in_prose(sd._label_have_folder()) in text, (
        f"[{code}] the do-it-yourself route names a button that is not there")


def test_there_is_only_one_key_per_button():
    """`My instrument is not listed` and `My instrument is not listed…` were
    two keys for one control. Pinned so a near-duplicate cannot come back."""
    import json
    root = Path(sd.__file__).resolve().parent.parent.parent / "data" / "i18n"
    for code in ALL_CODES:
        cat = json.loads(root.joinpath(f"{code}.json").read_text(encoding="utf-8"))
        assert "My instrument is not listed" not in cat, (
            f"[{code}] the ellipsis-less near-duplicate is back")


def test_no_serial_message_hard_codes_a_button_name_in_english():
    """The tripwire, over this half of the window."""
    import inspect
    OURS = ("Check again", "Get the driver…", "I already have the folder…",
            "My instrument is not listed…", "My instrument is not listed")
    for fn in (sd.serial_section_text, sd.serial_outcome_text,
               sd.serial_install_intro_text, sd.serial_manual_route_text,
               sd.serial_unknown_arch_text, sd.measurement_block_text):
        src = inspect.getsource(fn)
        body = "\n".join(l for l in src.split("\n")
                         if not l.strip().startswith("#"))
        flat = body.replace('"\n', "").replace('"', "")
        for label in OURS:
            assert f"<b>{label}</b>" not in flat, (
                f"{fn.__name__} spells out {label!r} instead of interpolating "
                "the button's own tr() label")


def test_a_button_name_in_prose_does_not_collide_with_the_full_stop(in_language):
    """The cosmetic half of the fix, and it only showed up on screen.

    Interpolating the label put the button's trailing ellipsis into the middle
    of a sentence, so the German window read "…in der Liste….". The ellipsis is
    punctuation on the control, not part of its name.
    """
    for code in ALL_CODES + ["en"]:
        in_language(code)
        for states in ([], [bridge("COM5")]):
            text, _p, _s = sd.serial_section_text(states)
            assert "…." not in text, f"[{code}] ellipsis collides with full stop"
        failed, _ = sd.serial_outcome_text(stage="download_failed", detail="x")
        assert "…." not in failed, f"[{code}] ellipsis collides with full stop"


def test_stripping_the_ellipsis_leaves_the_name_alone():
    assert sd._in_prose("My instrument is not listed…") ==         "My instrument is not listed"
    assert sd._in_prose("Check again") == "Check again"
    assert sd._in_prose("I already have the folder…") ==         "I already have the folder"

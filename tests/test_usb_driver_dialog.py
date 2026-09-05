"""The driver helper's words, pinned.

`SettingsDialog._show_usb_installer` is a `while True:` around `dlg.exec()`.
Until now the only thing guarding what it says was
`tests/test_winusb_never_reaches_a_serial_instrument.py`, which counts phrases in
the *source text* and so cannot tell you what a user would read.

**THIS FILE USED TO SAY THE WINDOW "CANNOT BE DRIVEN FROM A TEST". THAT WAS
FALSE, AND IT COST THREE BLOCKERS.** What is true is that calling `exec()` and
then doing nothing hangs the suite, which is the warning CLAUDE.md actually
gives. A modal is driven from *inside* its own event loop: arm a QTimer before
the call, and `QApplication.activeModalWidget()` hands back the live dialog. See
"DRIVING THE REAL DIALOG" at the end of this file — a verifier did it in under an
hour and found that this window was frequently not being shown at all, while
every string it could produce was pinned here in twelve languages.

Both halves are needed and neither substitutes for the other: the pure-function
tests say what the words are, the driving tests say that anyone sees them.

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

#: `reboot`, `cannot_tell` and `nothing_applied` are the three windows the 3010
#: fix added. They are in this list because every rule below is a rule about
#: every outcome window, and a stage that is not in it is a stage nothing
#: checks — which is how the contradiction window survived a green suite.
ALL_STAGES = ["bound", "reboot", "not_bound", "cannot_tell", "nothing_applied",
              "install_failed", "cancelled", "package_rejected",
              "download_failed"]


@pytest.mark.parametrize("stage", ALL_STAGES)
def test_no_outcome_ever_sends_the_user_to_roll_back_driver(stage):
    """Decision 10, and required change 18. *Roll Back Driver* is greyed out
    unless the device already had a working driver once — and the person
    reading any of these is by definition the person whose instrument never
    had one. Sending them to a greyed-out button is worse than saying nothing.

    **THIS USED TO BAN THE PHRASE AND IT WAS BANNING THE WRONG THING.** The
    `not_bound` window has always ended by warning the user OFF Roll Back —
    "it is greyed out for a device that never had a driver to roll back to" —
    and it passed because that sentence arrived through `detail`, from
    `core.ch34x_driver.verify_bound`, which this test stubs out with `"d"`. So
    the ban only ever covered the template, the sentence it was written to
    prevent was never in the template, and moving core's words into the UI
    (where they can be translated) made a green test go red without anything a
    user reads having changed. The rule is about STEERING, so that is what it
    now says: name the dead end if you like, but only to say it is one.
    """
    text, _ = sd.serial_outcome_text(stage=stage, detail="d", folder="f",
                                     ports="COM5")
    lowered = text.lower()
    if "roll back" in lowered or "rollback" in lowered:
        assert "will not help" in lowered, (
            "the %s window names Roll Back Driver without saying it is a dead "
            "end" % stage)


@pytest.mark.parametrize("stage", ALL_STAGES)
def test_no_outcome_ships_a_bracketed_plural(stage):
    text, _ = sd.serial_outcome_text(stage=stage, detail="d", folder="f",
                                     ports="COM5")
    for bad in ("device(s)", "driver(s)", "instrument(s)", "port(s)"):
        assert bad not in text


@pytest.mark.parametrize("stage", ["not_bound", "cannot_tell",
                                   "nothing_applied", "install_failed",
                                   "cancelled", "package_rejected",
                                   "download_failed"])
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
    """...and by naming the dead end, which is the last thing this user needs
    told before they go looking for one.

    Both sentences shipped; the second arrived through `detail` from
    `core.ch34x_driver.verify_bound` and is now part of the window, where it
    can be translated. See `test_no_outcome_ever_sends_the_user_to_roll_back_driver`.
    """
    text, _ = sd.serial_outcome_text(stage="not_bound", folder="f")
    assert ("Nothing has been removed or replaced, so there is nothing to "
            "undo. Whatever your computer had before, it still has." in text)
    assert text.endswith(
        "Device Manager's <b>Roll Back Driver</b> will not help here — it is "
        "greyed out for a device that never had a driver to roll back to.")


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
# The boundary: core says WHAT happened, this file says it in words
# ---------------------------------------------------------------------------
#
# This is where the two halves of the feature meet, and it used to meet on
# PROSE. `install()` returned `(bool, str)` and the dialog told "the user
# pressed No at the Windows permission prompt" from "the install failed" by
# comparing the first words of core's English against `_CANCELLED_PREFIX`. The
# tests that used to sit here were the tripwire for that: they asserted core
# still WROTE the sentence the dialog was matching on. Translating core would
# have broken the match — and translating core is the whole of defect 2.
#
# So the contract is now data, and these tests assert the data.


def test_the_prose_string_match_is_gone():
    """`_CANCELLED_PREFIX` / `_install_was_cancelled` must not come back.

    Not a source-text assertion for its own sake: while either of these exists,
    somebody can route a window on English again, and the routing tests below
    would still pass because they exercise the outcomes those helpers *agree*
    with today.
    """
    assert not hasattr(sd, "_CANCELLED_PREFIX")
    assert not hasattr(sd, "_install_was_cancelled")


def test_the_exit_code_table_is_outcomes_and_not_sentences():
    """Every `pnputil` code the feature knows maps to (Outcome, Reason)."""
    ch = pytest.importorskip("core.ch34x_driver")
    table = ch._PNPUTIL_OUTCOMES
    for code, pair in table.items():
        outcome, reason = pair
        assert isinstance(outcome, ch.Outcome), code
        assert isinstance(reason, ch.Reason), code
    assert table[1223] == (ch.Outcome.USER_CANCELLED,
                           ch.Reason.CANCELLED_AT_PROMPT)
    assert table[5] == (ch.Outcome.ACCESS_DENIED, ch.Reason.NO_PERMISSION)


def test_3010_is_its_own_outcome_and_is_not_a_success():
    """THE 3010 FAULT, at its root.

    `describe_exit_code(3010)` used to return `(True, "…needs a restart…")`.
    The `True` sent the flow on to `verify_bound`, which cannot find a COM port
    for a driver that is staged and not yet live — so the restart sentence was
    printed under the heading "Everything ChromIQ could check passed, and there
    is still no COM port". `REBOOT_REQUIRED` is deliberately falsy so that
    nothing can treat it as success by accident again.
    """
    ch = pytest.importorskip("core.ch34x_driver")
    got = ch.describe_exit_code(3010)
    assert got.outcome is ch.Outcome.REBOOT_REQUIRED
    assert got.reason is ch.Reason.REBOOT_TO_FINISH
    assert got.ok is False and bool(got) is False
    assert got.code == 3010


def test_every_reason_either_has_a_sentence_or_a_window_of_its_own():
    """A `Reason` nobody can render is a `Reason` that shows an empty paragraph.

    Core owns the vocabulary and this file owns the words, so the mapping has to
    be TOTAL in both directions: a member added to core with nothing to say
    fails here, and a name left behind in `_REASONS_WITH_THEIR_OWN_WINDOW`
    after core drops it fails here too.
    """
    ch = pytest.importorskip("core.ch34x_driver")
    own_window = set(sd._REASONS_WITH_THEIR_OWN_WINDOW)
    assert own_window <= {r.name for r in ch.Reason}, (
        "these names are not Reasons any more: %r"
        % sorted(own_window - {r.name for r in ch.Reason}))
    silent = []
    for reason in ch.Reason:
        said = sd.serial_reason_text(
            ch.DriverResult(ch.Outcome.FAILED, reason, code=1, name="COM7",
                            count=2, detail="because", path=Path("F")))
        if reason.name in own_window:
            assert said == "", (
                "%s has a window of its own AND a sentence — one of them is "
                "said twice" % reason.name)
        elif not said:
            silent.append(reason.name)
    assert silent == [], "these reasons can reach a window with nothing to say: %r" % silent


def test_no_reason_sentence_leaves_a_placeholder_unfilled():
    """`{code}` on screen is the failure mode of interpolating by hand."""
    ch = pytest.importorskip("core.ch34x_driver")
    for reason in ch.Reason:
        said = sd.serial_reason_text(
            ch.DriverResult(ch.Outcome.FAILED, reason, code=87, name="COM7",
                            count=300, detail="disk full", path=Path("F")))
        assert "{" not in said and "}" not in said, (reason.name, said)


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


# ===========================================================================
# DRIVING THE REAL DIALOG
# ===========================================================================
#
# THE HEADER OF THIS FILE USED TO SAY THE WINDOW "CANNOT BE DRIVEN FROM A TEST",
# AND THAT CLAIM COST THREE BLOCKERS.
#
# It is true that calling `_show_usb_installer()` from a test and then doing
# nothing hangs the suite: `dlg.exec()` spins its own event loop and waits for a
# human. What does not follow is "so do not test it". A modal can be driven from
# inside its own loop — arm a QTimer BEFORE the call, and when the loop starts
# the timer fires, `QApplication.activeModalWidget()` hands back the live
# dialog, and its real buttons can be clicked.
#
# That is all it takes, and it is what the pure-function tests above could never
# do. They pin every string this window can produce, character for character, in
# twelve languages — while the window itself was not being shown at all:
#
#   * `return bool(extra_label) and dlg.exec() == ...` short-circuits, so every
#     notice without a second button was built, laid out, tinted and dropped.
#     The measurement guard refused with nothing on screen.
#   * `box.accepted` fires for `StandardButton.Ok` too, so OK on the consent
#     window started an elevated driver install.
#   * The WinUSB outcome window, an unconditional `outcome_dlg.exec()` on
#     master, stopped appearing on any build without a bundled wdi-simple —
#     taking `_cr30_zadig_warning()` with it, the warning this branch
#     consolidated on purpose.
#
# Every test below fails against the code as it was shipped.

_TICK_MS = 5
_MAX_TICKS = 400          # ~2 s, then force everything shut: a stuck modal must
                          # fail the test, never hang the suite.


def _plain(widget) -> str:
    """Everything a user can read on this dialog, markup stripped."""
    import re
    from PyQt6.QtWidgets import QLabel
    return "\n".join(re.sub(r"<[^>]+>", "", lbl.text())
                     for lbl in widget.findChildren(QLabel))


def _button(widget, text: str):
    """The button whose visible label is *text*, or None."""
    from PyQt6.QtWidgets import QAbstractButton
    for b in widget.findChildren(QAbstractButton):
        if b.text().replace("&", "") == text:
            return b
    return None


def _ok_button(widget):
    from PyQt6.QtWidgets import QDialogButtonBox
    for box in widget.findChildren(QDialogButtonBox):
        btn = box.button(QDialogButtonBox.StandardButton.Ok)
        if btn is not None:
            return btn
    return None


class ModalDriver:
    """Act on each modal dialog as it appears, from inside its own event loop.

    *steps* are called in order, one per NEW modal window; anything that appears
    after they run out is dismissed. `self.seen` records what was on screen each
    time, so a test can assert about a window that has already closed — and an
    empty `seen` is itself the proof that nothing was ever shown.
    """

    def __init__(self, *steps):
        from PyQt6.QtCore import QTimer
        self._steps = list(steps)
        self._handled: set = set()
        self.seen: list = []
        self.ticks = 0
        self.timed_out = False
        self._timer = QTimer()
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._tick)

    def __enter__(self):
        self._timer.start()
        return self

    def __exit__(self, *exc):
        self._timer.stop()
        if exc[0] is None:
            # THIS ASSERT IS THE POINT OF THE FLAG, and for one release it did
            # not exist. `timed_out` was recorded and never read by any of the
            # 33 driving tests, so deleting `dlg.accept()` from the affirmative
            # button's handler left all 310 GREEN: the window never closed, the
            # driver force-`reject()`ed it after 400 ticks, and the test then
            # asserted on the flag the handler had already set. What the user
            # got was a window that would not go away and, once they pressed OK
            # or Esc to be rid of it, the elevated install they had just asked
            # the suite to prove could not happen that way. A harness that can
            # see a stuck modal and does not look is worse than no harness: it
            # reads as coverage.
            assert not self.timed_out, (
                "a modal window never closed — the driver had to force it shut "
                "after %d ticks; seen: %r" % (self.ticks, [t for t, _ in self.seen]))
        return False

    def _tick(self) -> None:
        from PyQt6.QtWidgets import QApplication
        self.ticks += 1
        if self.ticks > _MAX_TICKS:
            self.timed_out = True
            w = QApplication.activeModalWidget()
            while w is not None:
                w.reject()
                nxt = QApplication.activeModalWidget()
                if nxt is w:
                    break
                w = nxt
            self._timer.stop()
            return
        w = QApplication.activeModalWidget()
        if w is None or id(w) in self._handled:
            return
        self._handled.add(id(w))
        self.seen.append((w.windowTitle(), _plain(w)))
        if self._steps:
            self._steps.pop(0)(w)
        else:
            w.reject()

    @property
    def modal_count(self) -> int:
        return len(self.seen)

    def text_of(self, n: int) -> str:
        return self.seen[n][1]


@pytest.fixture(scope="module")
def qapp_for_driving():
    from PyQt6.QtWidgets import QApplication
    # tests/conftest.py pins one QApplication per worker. Never build a second
    # one and never tear this down: destroying a QApplication sip-deletes every
    # remaining QObject in the process (CLAUDE.md).
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialog(qapp_for_driving):
    """A real SettingsDialog on settings that are never written back."""
    from core.settings import DEFAULTS
    from ui.dialogs.settings_dialog import SettingsDialog

    class _Fake:
        def __init__(self):
            self._s = dict(DEFAULTS)

        def get(self, k, d=None):
            return self._s.get(k, d)

        def set(self, k, v):
            self._s[k] = v

        def migrate(self):
            pass

        def reset_to_defaults(self):
            pass

    dlg = SettingsDialog(_Fake())
    yield dlg
    dlg.deleteLater()


@pytest.fixture
def on_windows(monkeypatch):
    """`_show_usb_installer` returns immediately off win32.

    Its only use of `_sys` is `_sys.platform` (six times, nothing else), so a
    namespace carrying that one attribute is a complete stand-in — and these
    tests then run on every platform instead of skipping on the two where CI
    actually lives.
    """
    from types import SimpleNamespace
    monkeypatch.setattr(sd, "_sys", SimpleNamespace(platform="win32"))


def _fixed_hardware(monkeypatch, devices, wdi: bool):
    """Point the window at a known device list and wdi-simple state."""
    import core.resource_path as rp
    import core.usb_driver_installer as inst
    monkeypatch.setattr(inst, "enumerate_connected", lambda: list(devices))
    monkeypatch.setattr(inst, "unbound_targets", lambda t: [])
    monkeypatch.setattr(inst, "install_winusb", lambda d: True)
    monkeypatch.setattr(sd, "present_usb_ids", lambda: None)
    monkeypatch.setattr(sd.SettingsDialog, "_serial_states", lambda self: [])

    class _P:
        def exists(self):
            return wdi

    monkeypatch.setattr(rp, "resource_path", lambda p: _P())


# --- the window appears at all ---------------------------------------------

def test_a_notice_with_no_extra_button_is_actually_shown(dialog):
    """BLOCKER 1, pinned.

    `return bool(extra_label) and dlg.exec() == ...` never reached `exec()` when
    there was no extra button, so this window did not exist for the user. When
    it is not shown no modal is ever active, so the driver never fires and
    `seen` stays empty.
    """
    with ModalDriver(lambda w: _ok_button(w).click()) as drv:
        took = dialog._driver_notice("Instrument drivers", "<b>Something.</b>")
    assert drv.modal_count == 1, "no modal window was ever shown"
    assert took is False
    assert "Something." in drv.text_of(0)


def test_a_notice_with_an_extra_button_is_shown_too(dialog):
    with ModalDriver(lambda w: _ok_button(w).click()) as drv:
        dialog._driver_notice("T", "<b>Body.</b>", "Do the thing")
    assert drv.modal_count == 1
    assert "Body." in drv.text_of(0)


@pytest.mark.parametrize("extra", [None, "Do the thing"])
def test_the_notice_is_genuinely_modal(dialog, extra):
    """`activeModalWidget()` is what proves an event loop was entered, rather
    than a widget having been built and thrown away."""
    seen = {}

    def _look(w):
        from PyQt6.QtWidgets import QApplication
        seen["active"] = QApplication.activeModalWidget()
        seen["visible"] = w.isVisible()
        _ok_button(w).click()

    with ModalDriver(_look):
        dialog._driver_notice("T", "Body", extra)
    assert seen.get("active") is not None
    assert seen.get("visible") is True


# --- OK means dismiss, never "yes, install" --------------------------------

def test_ok_dismisses_and_does_not_take_the_action(dialog):
    """BLOCKER 2, pinned.

    On the before-UAC consent window the two buttons were `Download and
    install` and `OK`, and both started the install. The only decline was Esc.
    """
    with ModalDriver(lambda w: _ok_button(w).click()) as drv:
        took = dialog._driver_notice("T", "Body", "Download and install")
    assert drv.modal_count == 1
    assert took is False, "OK started the action it was there to decline"


def test_the_extra_button_takes_the_action(dialog):
    with ModalDriver(lambda w: _button(w, "Download and install").click()):
        took = dialog._driver_notice("T", "Body", "Download and install")
    assert took is True


def test_escape_dismisses(dialog):
    def _esc(w):
        w.reject()          # what Esc is wired to on a QDialog

    with ModalDriver(_esc):
        took = dialog._driver_notice("T", "Body", "Download and install")
    assert took is False


def test_closing_the_window_dismisses(dialog):
    with ModalDriver(lambda w: w.close()):
        took = dialog._driver_notice("T", "Body", "Download and install")
    assert took is False


def test_the_affirmative_button_is_the_tinted_one(dialog):
    """The action must not be the button that merely closes the window."""
    names = {}

    def _look(w):
        names["extra"] = _button(w, "Download and install").objectName()
        names["ok"] = _ok_button(w).objectName()
        _ok_button(w).click()

    with ModalDriver(_look):
        dialog._driver_notice("T", "Body", "Download and install")
    assert names["extra"] == "primary"
    assert names["ok"] != "primary"


# --- the measurement guard, this branch's headline safety feature -----------

def test_the_measurement_guard_actually_puts_its_refusal_on_screen(
        dialog, on_windows, monkeypatch):
    """BLOCKER 1 where it costs the most: the guard fired, `_driver_notice` was
    called, and nothing appeared. A silent refusal is the exact failure the
    guard was written to prevent."""
    monkeypatch.setattr(sd, "measurement_in_progress",
                        lambda parent=None: "the Measure tab")
    with ModalDriver(lambda w: _ok_button(w).click()) as drv:
        dialog._show_usb_installer()
    assert drv.modal_count == 1, "the guard refused without showing anything"
    assert "Not while a measurement is running" in drv.text_of(0)
    assert "the Measure tab" in drv.text_of(0)


def test_the_guard_shows_its_refusal_instead_of_the_driver_window(
        dialog, on_windows, monkeypatch):
    monkeypatch.setattr(sd, "measurement_in_progress",
                        lambda parent=None: "the Measure tab")
    with ModalDriver(lambda w: _ok_button(w).click()) as drv:
        dialog._show_usb_installer()
    assert drv.modal_count == 1
    assert "USB-to-serial bridge" not in drv.text_of(0)


# --- the WinUSB outcome window, and the CR30 warning it carries -------------

def test_the_winusb_outcome_window_appears_when_zadig_was_launched(
        dialog, on_windows, monkeypatch):
    """BLOCKER 3, pinned.

    `assets/wdi_simple.exe` is not in this repo, so this is the DEFAULT path.
    On master the outcome dialog was an unconditional `outcome_dlg.exec()`.
    """
    import core.usb_driver_installer as inst
    _fixed_hardware(monkeypatch, [dev(I1PRO, False)], wdi=False)
    monkeypatch.setattr(inst, "launch_zadig", lambda: "launched")
    with ModalDriver(lambda w: _button(w, "Open Zadig").click(),
                     lambda w: _ok_button(w).click()) as drv:
        dialog._show_usb_installer()
    assert drv.modal_count == 2, (
        "the install ran and its outcome window never appeared")
    assert "Zadig is open" in drv.text_of(1)


def test_the_cr30_warning_reaches_the_screen_after_zadig_is_launched(
        dialog, on_windows, monkeypatch):
    """The warning this branch consolidated into one key was being shown to
    nobody on the default build, while the test guarding it stayed green
    because it asserts on the string the function returns."""
    import core.usb_driver_installer as inst
    _fixed_hardware(monkeypatch, [dev(I1PRO, False)], wdi=False)
    monkeypatch.setattr(inst, "launch_zadig", lambda: "launched")
    with ModalDriver(lambda w: _button(w, "Open Zadig").click(),
                     lambda w: _ok_button(w).click()) as drv:
        dialog._show_usb_installer()
    assert drv.modal_count == 2
    assert "If you own a CR30" in drv.text_of(1)
    assert "do not pick the USB-serial" in drv.text_of(1)


def test_the_download_page_outcome_is_shown_and_warns_too(
        dialog, on_windows, monkeypatch):
    import core.usb_driver_installer as inst
    _fixed_hardware(monkeypatch, [dev(I1PRO, False)], wdi=False)
    monkeypatch.setattr(inst, "launch_zadig", lambda: "download_page")
    with ModalDriver(lambda w: _button(w, "Open Zadig").click(),
                     lambda w: _ok_button(w).click()) as drv:
        dialog._show_usb_installer()
    assert drv.modal_count == 2
    assert "If you own a CR30" in drv.text_of(1)


def test_the_zadig_failure_outcome_is_shown(dialog, on_windows, monkeypatch):
    import core.usb_driver_installer as inst
    _fixed_hardware(monkeypatch, [dev(I1PRO, False)], wdi=False)
    monkeypatch.setattr(inst, "launch_zadig", lambda: "failed")
    with ModalDriver(lambda w: _button(w, "Open Zadig").click(),
                     lambda w: _ok_button(w).click()) as drv:
        dialog._show_usb_installer()
    assert drv.modal_count == 2
    assert "zadig.akeo.ie" in drv.text_of(1)


def test_ok_on_the_outcome_window_does_not_launch_zadig(
        dialog, on_windows, monkeypatch):
    """On master `Try Zadig` had its own handler and OK merely closed. The
    branch made OK launch Zadig too."""
    import core.usb_driver_installer as inst
    _fixed_hardware(monkeypatch, [dev(I1PRO, True)], wdi=True)
    monkeypatch.setattr(inst, "unbound_targets", lambda t: list(t))
    launches = []
    monkeypatch.setattr(inst, "launch_zadig",
                        lambda: (launches.append(1), "launched")[1])
    with ModalDriver(lambda w: _button(w, "Reinstall Driver").click(),
                     lambda w: _ok_button(w).click()) as drv:
        dialog._show_usb_installer()
    assert drv.modal_count == 2
    assert launches == [], "OK launched Zadig"


def test_try_zadig_on_the_outcome_window_does_launch_zadig(
        dialog, on_windows, monkeypatch):
    import core.usb_driver_installer as inst
    _fixed_hardware(monkeypatch, [dev(I1PRO, True)], wdi=True)
    monkeypatch.setattr(inst, "unbound_targets", lambda t: list(t))
    launches = []
    monkeypatch.setattr(inst, "launch_zadig",
                        lambda: (launches.append(1), "launched")[1])
    with ModalDriver(lambda w: _button(w, "Reinstall Driver").click(),
                     lambda w: _button(w, "Try Zadig").click()) as drv:
        dialog._show_usb_installer()
    assert drv.modal_count == 2
    assert launches == [1]


# --- the driver window itself ----------------------------------------------

def test_the_driver_window_appears(dialog, on_windows, monkeypatch):
    _fixed_hardware(monkeypatch, [], wdi=False)
    with ModalDriver(lambda w: _button(w, "Close").click()) as drv:
        dialog._show_usb_installer()
    assert drv.modal_count == 1
    assert "No colorimeter detected" in drv.text_of(0)


def test_long_prose_scrolls_instead_of_being_cut_off(dialog):
    """The window wanted 934 px; a 1080p laptop at 150% has about 672. Past its
    height a word-wrapped QLabel is truncated with no scrollbar and no sign that
    anything is missing, so the paragraph justifying the install button was
    simply gone."""
    from PyQt6.QtWidgets import QScrollArea
    found = {}

    def _look(w):
        # Read the properties HERE, not after the call: once `exec()` returns
        # the dialog is gone and the wrappers raise "C/C++ object has been
        # deleted". Anything a test wants to assert about a live widget has to
        # be taken while the window is on screen.
        areas = w.findChildren(QScrollArea)
        found["count"] = len(areas)
        found["resizable"] = [a.widgetResizable() for a in areas]
        _ok_button(w).click()

    with ModalDriver(_look):
        dialog._driver_notice("T", "<br><br>".join(["A long paragraph."] * 60))
    assert found["count"], "no scroll area — long text is silently truncated"
    assert found["resizable"][0] is True


def test_the_driver_window_scrolls_too(dialog, on_windows, monkeypatch):
    from PyQt6.QtWidgets import QScrollArea
    _fixed_hardware(monkeypatch, [], wdi=False)
    found = {}

    def _look(w):
        found["count"] = len(w.findChildren(QScrollArea))
        _button(w, "Close").click()

    with ModalDriver(_look) as drv:
        dialog._show_usb_installer()
    assert drv.modal_count == 1
    assert found["count"], "the driver window cannot scroll"


def test_the_buttons_stay_outside_the_scroll_area(dialog, on_windows,
                                                  monkeypatch):
    """Check again / Close must never scroll out of reach."""
    from PyQt6.QtWidgets import QScrollArea
    _fixed_hardware(monkeypatch, [], wdi=False)
    found = {}

    def _look(w):
        area = w.findChildren(QScrollArea)[0]
        close = _button(w, "Close")
        found["inside"] = area.isAncestorOf(close)
        close.click()

    with ModalDriver(_look):
        dialog._show_usb_installer()
    assert found["inside"] is False


# --- what core learned is not thrown away ----------------------------------

def test_the_not_bound_window_repeats_what_core_actually_found():
    """`detail` was accepted and dropped, so exit 3010's "Windows accepted the
    driver and needs a restart to finish switching it on" was replaced by three
    pieces of advice, none of which is "restart"."""
    restart = ("Windows accepted the driver and needs a restart to finish "
               "switching it on.")
    text, _ = sd.serial_outcome_text(stage="not_bound", detail=restart,
                                     folder="F")
    assert restart in text


def test_the_not_bound_window_is_unchanged_when_core_says_nothing():
    text, _ = sd.serial_outcome_text(stage="not_bound", detail="", folder="F")
    assert "Everything ChromIQ could check passed" in text
    assert "<br><br><br>" not in text


# ---------------------------------------------------------------------------
# The window has to FIT, and its own buttons have to be on it
# ---------------------------------------------------------------------------
#
# The scroll area added to stop text being truncated became the truncation.
# `QScrollArea::sizeHint()` is the inner widget's hint `boundedTo(36h, 24h)`
# with `h = fontMetrics().height()`, so it reports the same height whatever it
# holds — and `_fit_to_screen` pinned that with `resize()`. Measured on the
# owner's machine, German, the worst natural case: **620 x 480 on a 1032 px
# screen**, 774 px of content, 390 px hidden, `Treiber holen…` — the button the
# whole window exists to offer — 303 px BELOW THE BOTTOM EDGE, with nothing on
# screen to say it was there. It was photographed into the committed evidence
# gallery and nobody noticed.
#
# What made that survivable for a whole release is that the only assertions
# about the fix were "a QScrollArea exists" and "widgetResizable() is True".
# Three separate mutations left all 310 tests green:
#
#   M6  vertical scrollbar policy -> ScrollBarAlwaysOff  (silent truncation, again)
#   M7  delete both `_fit_to_screen` calls               (the screen cap does nothing)
#   M8  `area.setMaximumHeight(40)` on the scroll area   (two lines above a green button)
#
# The tests below are written against the RELATION rather than against pixel
# counts, so they say the same thing on a 4K desktop and on a CI worker with an
# 800 px offscreen screen:
#
#     window height == min(what the content wants, 90 % of the screen)
#
# and, when the cap is what bit, everything is still reachable by scrolling.


def _geometry_of(w):
    """Everything these tests need, read while the window is still alive."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QPushButton, QScrollArea
    area = w.findChildren(QScrollArea)[0]
    vbar, hbar = area.verticalScrollBar(), area.horizontalScrollBar()
    inner = area.widget()
    off = []
    for b in w.findChildren(QPushButton):
        if not b.isVisible():
            continue
        bottom = b.mapTo(w, b.rect().bottomRight()).y()
        if bottom > w.height():
            off.append(b.text().replace("&", ""))
    return {
        "height": w.height(),
        "cap": w.maximumHeight(),
        "viewport_h": area.viewport().height(),
        "viewport_w": area.viewport().width(),
        "inner_h": inner.height(),
        # How tall the content really is at the width it really got — which is
        # not `inner_h`, because `setWidgetResizable(True)` stretches the inner
        # widget to fill the viewport. The difference is wasted window.
        "inner_needed_h": (inner.heightForWidth(area.viewport().width())
                           if inner.hasHeightForWidth() else inner.height()),
        "inner_minhint_w": inner.minimumSizeHint().width(),
        "assumed_w": getattr(area, "_assumed_width", None),
        "hidden": vbar.maximum(),
        "vbar_visible": vbar.isVisible(),
        "hbar_max": hbar.maximum(),
        "hbar_visible": hbar.isVisible(),
        "hbar_policy_is_always_off": (area.horizontalScrollBarPolicy()
                                     == Qt.ScrollBarPolicy.ScrollBarAlwaysOff),
        "buttons_below_the_bottom_edge": off,
        "screen_h": (w.screen().availableGeometry().height()
                     if w.screen() is not None else 0),
    }


def _worst_case_hardware(monkeypatch):
    """A colorimeter with no WinUSB driver AND a driverless CH34x bridge.

    Both halves populated is the tallest the window ever gets, and it is the
    case the shipped build cut in half.
    """
    from types import SimpleNamespace
    _fixed_hardware(monkeypatch, [dev(I1PRO, False)], wdi=False)
    bridge = SimpleNamespace(instance_id=r"USB\VID_1A86&PID_7523\X",
                             vid="1a86", pid="7523", port=None,
                             status=None)
    monkeypatch.setattr(sd.SettingsDialog, "_serial_states",
                        lambda self: [bridge])


def test_the_driver_window_opens_at_the_height_its_content_wants(
        dialog, on_windows, monkeypatch):
    """M6/M7/M8, and the shipped 620 x 480.

    `chrome` is everything that is not the scroll area's viewport — the
    margins, the spacing and the button row — so `chrome + inner_h` is the
    height the window would need to show everything. Anything that shrinks the
    viewport without shrinking the window (the `boundedTo` clamp, a
    `setMaximumHeight` on the area) breaks the equality; deleting the screen cap
    breaks it too, because then `cap` is `QWIDGETSIZE_MAX` and the window is
    still 480.
    """
    _worst_case_hardware(monkeypatch)
    found = {}

    def _look(w):
        found.update(_geometry_of(w))
        _button(w, "Close").click()

    with ModalDriver(_look) as drv:
        dialog._show_usb_installer()
    assert drv.modal_count == 1
    chrome = found["height"] - found["viewport_h"]
    wanted = chrome + found["inner_h"]
    assert abs(found["height"] - min(wanted, found["cap"])) <= 2, (
        "the window opened %d px tall for %d px of content on a %d px cap"
        % (found["height"], wanted, found["cap"]))


def test_the_driver_window_shows_every_button_it_offers(
        dialog, on_windows, monkeypatch):
    """`Get the driver…` and `I already have the folder…` start ON the window.

    Shipped, they started 303 px past the bottom edge on a screen with 448 px
    of headroom going spare, and the paragraph that names them ended 249 px
    past it. The user could not see the action the window exists to offer.
    """
    _worst_case_hardware(monkeypatch)
    found = {}

    def _look(w):
        from PyQt6.QtWidgets import QPushButton
        found.update(_geometry_of(w))
        found["labels"] = [b.text().replace("&", "")
                           for b in w.findChildren(QPushButton) if b.isVisible()]
        _button(w, "Close").click()

    with ModalDriver(_look):
        dialog._show_usb_installer()
    assert "Get the driver…" in found["labels"]
    assert "I already have the folder…" in found["labels"]
    # A button may only start below the bottom edge when the SCREEN is what
    # ran out — never when the window merely decided to be short. Shipped:
    # height 480, cap 928, two buttons below the edge. On a CI worker with an
    # 800 px offscreen screen the worst case genuinely does not fit, the window
    # is at the cap, and scrolling is then the correct answer; the assertion
    # stays honest either way instead of being skipped.
    assert (found["buttons_below_the_bottom_edge"] == []
            or found["height"] == found["cap"]), (
        "%r start below the bottom edge of a %d px window that could have been "
        "%d px" % (found["buttons_below_the_bottom_edge"],
                   found["height"], found["cap"]))


def test_a_notice_taller_than_the_screen_scrolls_and_stops_at_the_screen(
        dialog):
    """M6 and M8 again, from the other end: when the cap DOES bite.

    Everything below the fold must still be reachable, and the window must stop
    at the screen rather than at whatever the scroll area felt like reporting.
    """
    found = {}

    def _look(w):
        found.update(_geometry_of(w))
        _ok_button(w).click()

    with ModalDriver(_look):
        dialog._driver_notice("T", "<br><br>".join(["A long paragraph."] * 300))
    assert found["hidden"] > 0, "300 paragraphs fitted on the screen?"
    assert found["vbar_visible"], (
        "text is below the fold and there is no scrollbar to reach it")
    assert found["viewport_h"] + found["hidden"] == found["inner_h"], (
        "the scrollbar does not reach the end of the content")
    assert found["height"] == found["cap"], (
        "the window stopped %d px short of the screen cap %d"
        % (found["height"], found["cap"]))


def test_a_notice_that_fits_the_screen_hides_none_of_itself(dialog):
    """The same relation for `_driver_notice`, which is the NARROW window.

    A notice is 560 px wide where the helper is 620, and a word-wrapped
    paragraph is TALLER when it is narrower — so a height worked out at the
    wrong width is short here even when it is right there. Not hypothetical:
    `QScrollArea::sizeHint()` answers at its own placeholder width
    (36 * fontMetrics().height()), which is wider than this window’s viewport,
    and taking that answer leaves the last paragraph below the fold on a screen
    with room to spare. `_fit_to_screen` settles the width first and tells the
    area what it will get; this test is what says so.
    """
    found = {}

    def _look(w):
        found.update(_geometry_of(w))
        _ok_button(w).click()

    with ModalDriver(_look):
        dialog._driver_notice(
            "T", sd.serial_install_intro_text(
                r"C:\Users\x\AppData\Local\ChromIQ\drivers\2026-09-05_01-42-17", "ARM64"))
    chrome = found["height"] - found["viewport_h"]
    assert abs(found["height"]
               - min(chrome + found["inner_h"], found["cap"])) <= 2
    assert found["hidden"] == 0 or found["height"] == found["cap"], (
        "%d px of the consent text is below the fold in a %d px window that "
        "could have been %d px"
        % (found["hidden"], found["height"], found["cap"]))
    # ...and it is not needlessly TALL either, which is the other half of
    # "the height its content wants". A height worked out at the wrong width
    # errs in whichever direction that width was wrong: too narrow an estimate
    # opens a window with a band of empty space under the last paragraph, too
    # wide an estimate leaves the last paragraph below the fold. One line of
    # slack is expected and deliberate — the vertical scrollbar's width is
    # reserved in the estimate so that a marginal fit cannot come out short.
    slack = found["viewport_h"] - found["inner_needed_h"]
    assert slack <= 40, (
        "%d px of empty space under the text — the height was worked out at "
        "the wrong width" % slack)
    # And the mechanism, said directly, because the symptom above is only a
    # few lines of slack and a threshold that could tell 14 px from 30 px would
    # be a threshold that breaks on the next font: the area is TOLD the width
    # it is about to have, and that width is the one it gets.
    assert found["assumed_w"] == found["viewport_w"], (
        "the scroll area worked its height out for %s px and was given %d"
        % (found["assumed_w"], found["viewport_w"]))


def test_the_screen_cap_is_the_only_thing_that_shortens_a_notice(dialog):
    """M7: deleting `_fit_to_screen` leaves `maximumHeight` at QWIDGETSIZE_MAX."""
    found = {}

    def _look(w):
        found.update(_geometry_of(w))
        _ok_button(w).click()

    with ModalDriver(_look):
        dialog._driver_notice("T", "<br><br>".join(["A long paragraph."] * 300))
    assert 320 <= found["cap"] <= int(found["screen_h"] * 0.9) + 1, (
        "maximumHeight is %d on a %d px screen — _fit_to_screen did not run"
        % (found["cap"], found["screen_h"]))


def test_a_long_folder_path_does_not_clip_the_window(dialog):
    """The same fault on the other axis, and it shipped too.

    `setWidgetResizable(True)` sizes the inner label to at least its minimum
    size hint, and a word-wrapped QLabel cannot break inside an unbroken run —
    so one 80-character folder path widened the label past the viewport and
    CHOPPED EVERY LINE IN THE WINDOW at the right edge. Measured
    `hbar_max = 99`, `hbar_visible = False`: no scrollbar, no ellipsis, nothing
    to say a word was missing. The path the user picks is not ChromIQ's to keep
    short — `Downloads\\CH341SER_LINUX_WINDOWS_ARM64_2026_09_05\\DRIVER` is an
    ordinary one.
    """
    long_path = (r"C:\Users\sebastian.sandberg\Downloads"
                 r"\CH341SER_LINUX_WINDOWS_ARM64_2026_09_05\DRIVER\CH341SER")
    text, _ = sd.serial_outcome_text(stage="install_failed",
                                     detail="Windows refused the change.",
                                     folder=long_path)
    assert long_path in text, "the fixture no longer puts the path on screen"
    found = {}

    def _look(w):
        found.update(_geometry_of(w))
        _ok_button(w).click()

    with ModalDriver(_look):
        dialog._driver_notice("T", text)
    assert not (found["hbar_max"] > 0 and not found["hbar_visible"]), (
        "%d px of the window is off the right edge with no scrollbar"
        % found["hbar_max"])
    assert found["inner_minhint_w"] <= found["viewport_w"], (
        "the path still cannot be broken: it needs %d px in a %d px viewport"
        % (found["inner_minhint_w"], found["viewport_w"]))
    assert found["hbar_policy_is_always_off"] is False, (
        "the break opportunity handles the paths we can foresee; the scrollbar "
        "is what handles the ones we cannot, and forcing it off is how this "
        "shipped")


def test_the_path_break_opportunity_is_invisible():
    """Nothing is added that a user could see, select or paste wrongly."""
    out = sd._let_paths_wrap(r"C:\Users\x\CH341SER")
    assert out.replace("\u200b", "") == r"C:\Users\x\CH341SER"
    assert out.count("\u200b") == 3
    assert sd._let_paths_wrap("no separators here") == "no separators here"


# ---------------------------------------------------------------------------
# Enter must not install
# ---------------------------------------------------------------------------
#
# OK, Esc and the title-bar X were all made to decline. Enter was not, and Enter
# is the key people press to make a window go away: `QDialogButtonBox` promotes
# its first AcceptRole button to the dialog's default, and the affirmative one
# is added first, so `Return` on the before-UAC consent window DOWNLOADED AND
# INSTALLED AN ELEVATED DRIVER. Measured true in all six theme/language runs of
# the one window that exists for informed consent, and no test covered it.


def _press(w, key):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    QTest.keyClick(w, getattr(Qt.Key, key))


@pytest.mark.parametrize("key", ["Key_Return", "Key_Enter"])
def test_enter_dismisses_and_does_not_take_the_action(dialog, key):
    with ModalDriver(lambda w: _press(w, key)) as drv:
        took = dialog._driver_notice("T", "Body", "Download and install")
    assert drv.modal_count == 1
    assert took is False, "Enter started an elevated driver install"


def test_the_dismissing_button_is_the_default_one(dialog):
    """Belt as well as braces: the behaviour above, said as a property.

    Qt's promotion is by construction order and not by role, so every button
    has to lose `autoDefault` before the safe one gets it back — otherwise the
    next button added to this window silently becomes what Enter presses.
    """
    found = {}

    def _look(w):
        found["extra"] = _button(w, "Download and install").isDefault()
        found["ok"] = _ok_button(w).isDefault()
        _ok_button(w).click()

    with ModalDriver(_look):
        dialog._driver_notice("T", "Body", "Download and install")
    assert found["ok"] is True
    assert found["extra"] is False


def test_enter_on_the_driver_window_closes_it_and_installs_nothing(
        dialog, on_windows, monkeypatch):
    """Same mechanism on the helper window, where Enter pressed `Open Zadig`."""
    import core.usb_driver_installer as inst
    _fixed_hardware(monkeypatch, [dev(I1PRO, False)], wdi=False)
    launches = []
    monkeypatch.setattr(inst, "launch_zadig",
                        lambda: (launches.append(1), "launched")[1])
    found = {}

    def _look(w):
        found["zadig_default"] = _button(w, "Open Zadig").isDefault()
        found["close_default"] = _button(w, "Close").isDefault()
        _press(w, "Key_Return")

    with ModalDriver(_look) as drv:
        dialog._show_usb_installer()
    assert drv.modal_count == 1, "Enter opened a second window"
    assert launches == [], "Enter started the WinUSB install"
    assert found["zadig_default"] is False
    assert found["close_default"] is True


# ---------------------------------------------------------------------------
# The serial half's five outcome windows: that anyone SEES them
# ---------------------------------------------------------------------------
#
# The guard and the WinUSB outcome each have a driving test, so deleting their
# `_driver_notice` call goes red. The serial half's outcomes had none: deleting
# the call at the end of `_serial_check_and_install` killed BOTH "it worked" and
# "still no COM port" with 317 tests green, and deleting the one in the
# install-failure branch killed BOTH "the install failed" and "you cancelled at
# the permission prompt", also green. Their text is pinned character for
# character above; that anybody ever sees it was not.
#
# `install` is never the real one here — every test in this section replaces it,
# so nothing can elevate, and a call with an unexpected argument fails loudly
# rather than reaching pnputil.


def _result(outcome_name, reason_name, **kw):
    """A real `DriverResult` — the type the dialog is coded against."""
    import core.ch34x_driver as ch
    return ch.DriverResult(getattr(ch.Outcome, outcome_name),
                           getattr(ch.Reason, reason_name), **kw)


def _fake_core(monkeypatch, *, inspect_ok=True,
               install_result=("OK", "DRIVER_ACCEPTED"),
               bound=("OK", "PORT_APPEARED"), ports=("COM7",)):
    """Point `_serial_check_and_install` at a scripted core, never the real one.

    `install_result` and `bound` are `(Outcome name, Reason name)` pairs, or a
    ready-made `DriverResult`. THEY ARE NOT PROSE ANY MORE, and that is the
    point of the change these tests cover: the dialog picks its window from the
    outcome, so a test that wants a particular window has to name one.
    """
    from pathlib import Path
    from types import SimpleNamespace
    import core.ch34x_driver as ch

    def _as_result(spec, **extra):
        if isinstance(spec, ch.DriverResult):
            return spec
        return _result(spec[0], spec[1], **extra)

    calls = {"installed": []}

    def _inspect(folder):
        return SimpleNamespace(
            ok=inspect_ok,
            inf_path=Path(folder) / "CH341SER.INF" if inspect_ok else None,
            reason="" if inspect_ok else "the INF is for other hardware.",
            arch_section="NTARM64", service_binary="CH341SER.SYS")

    def _install(inf_path):
        calls["installed"].append(str(inf_path))
        return _as_result(install_result)

    monkeypatch.setattr(ch, "inspect_package", _inspect)
    monkeypatch.setattr(ch, "install", _install)
    monkeypatch.setattr(
        ch, "verify_bound",
        lambda before: _as_result(bound, name=", ".join(ports)))
    monkeypatch.setattr(ch, "devices", lambda: [
        SimpleNamespace(instance_id="ID%d" % i, vid="1a86", pid="7523",
                        port=p, status=None)
        for i, p in enumerate(ports)])
    return calls


def _unbound_before():
    from types import SimpleNamespace
    return [SimpleNamespace(instance_id="ID0", vid="1a86", pid="7523",
                            port=None, status=None)]


def test_the_it_worked_window_reaches_the_screen(dialog, monkeypatch, tmp_path):
    calls = _fake_core(monkeypatch, bound=("OK", "PORT_APPEARED"))
    with ModalDriver(lambda w: _ok_button(w).click()) as drv:
        dialog._serial_check_and_install(tmp_path, _unbound_before())
    assert calls["installed"], "nothing was installed, so this proves nothing"
    assert drv.modal_count == 1, (
        "the driver was installed and the user was told nothing")
    assert "It worked." in drv.text_of(0)
    assert "COM7" in drv.text_of(0)


def test_the_still_no_com_port_window_reaches_the_screen(
        dialog, monkeypatch, tmp_path):
    """pnputil said 0, the checks all passed, and Windows has still not
    attached the driver. The hard case this whole feature exists for."""
    _fake_core(monkeypatch, install_result=("OK", "DRIVER_ACCEPTED"),
               bound=("FAILED", "STILL_NO_PORT"))
    with ModalDriver(lambda w: _ok_button(w).click()) as drv:
        dialog._serial_check_and_install(tmp_path, _unbound_before())
    assert drv.timed_out is False
    assert drv.modal_count == 1, (
        "the install left no COM port and the user was told nothing")
    said = drv.text_of(0)
    assert "there is still no COM port" in said
    assert "Unplug the instrument" in said
    # AND IT NO LONGER CARRIES A SENTENCE THAT CONTRADICTS ITS OWN HEADING.
    # 3010's "needs a restart to finish switching it on" used to be printed
    # here, under "Everything ChromIQ could check passed".
    assert "restart to finish" not in said


def test_the_install_failed_window_reaches_the_screen(
        dialog, monkeypatch, tmp_path):
    _fake_core(monkeypatch, install_result=("FAILED", "PACKAGE_INVALID"))
    with ModalDriver(lambda w: _ok_button(w).click()) as drv:
        dialog._serial_check_and_install(tmp_path, _unbound_before())
    assert drv.timed_out is False
    assert drv.modal_count == 1, (
        "an elevated install failed and the user was told nothing")
    said = drv.text_of(0)
    assert "Windows did not install the package." in said
    assert "rejected the driver package as invalid" in said, (
        "what core actually found was dropped on the way to the screen")


def test_the_you_cancelled_window_reaches_the_screen(
        dialog, monkeypatch, tmp_path):
    """Cancelling the UAC prompt is indistinguishable from a failure unless the
    window says so, and this is the one outcome with no screenshot in the
    evidence pack — all the more reason for a test."""
    _fake_core(monkeypatch,
               install_result=("USER_CANCELLED", "CANCELLED_AT_PROMPT"))
    with ModalDriver(lambda w: _ok_button(w).click()) as drv:
        dialog._serial_check_and_install(tmp_path, _unbound_before())
    assert drv.timed_out is False
    assert drv.modal_count == 1
    assert "stopped at the Windows permission prompt" in drv.text_of(0)
    assert "Windows did not install the package." not in drv.text_of(0)


def test_the_package_rejected_window_reaches_the_screen(
        dialog, monkeypatch, tmp_path):
    calls = _fake_core(monkeypatch, inspect_ok=False)
    with ModalDriver(lambda w: _ok_button(w).click()) as drv:
        dialog._serial_check_and_install(tmp_path, _unbound_before())
    assert calls["installed"] == [], "a rejected package was installed anyway"
    assert drv.modal_count == 1
    assert "will not install that package" in drv.text_of(0)


# ---------------------------------------------------------------------------
# The folder route announces the permission prompt before it appears
# ---------------------------------------------------------------------------
#
# `My instrument is not listed…` -> `I already have the folder…` -> a folder
# picker -> `pnputil`. Two clicks to an elevated install, and Windows' own UAC
# prompt was the first the user heard of it — against the rule the download
# route states four screens up in its own comment: "an unexpected security
# prompt is the one people cancel … so say what is coming, and say what ChromIQ
# cannot promise, while there is still nothing to undo."


@pytest.fixture
def folder_route(monkeypatch, tmp_path):
    """`_serial_from_folder` with a chosen folder and the install stubbed out."""
    import ui.widgets as w
    monkeypatch.setattr(sd.SettingsDialog, "_serial_machine_arch",
                        lambda self: "ARM64")
    monkeypatch.setattr(sd.SettingsDialog, "_serial_states", lambda self: [])
    monkeypatch.setattr(w, "open_dir_dialog",
                        lambda *a, **k: str(tmp_path / "CH341SER"))
    reached = []
    monkeypatch.setattr(
        sd.SettingsDialog, "_serial_check_and_install",
        lambda self, folder, before: reached.append(str(folder)))
    return reached


def test_the_folder_route_announces_the_prompt_before_anything_elevates(
        dialog, folder_route):
    with ModalDriver(lambda w: _button(w, "Check and install").click()) as drv:
        dialog._serial_from_folder()
    assert drv.modal_count == 1, (
        "the folder route reached an elevated install with no announcement")
    said = drv.text_of(0)
    assert "Here is exactly what is about to happen" in said
    assert "Windows will ask your permission" in said
    assert "cannot promise" in said
    assert folder_route, "consent was given and nothing happened"


def test_the_folder_route_does_not_promise_a_download_it_never_makes(
        dialog, folder_route):
    """It is not the download route's text with a word changed: on this route
    ChromIQ did not fetch the files and says so."""
    with ModalDriver(lambda w: _ok_button(w).click()) as drv:
        dialog._serial_from_folder()
    said = drv.text_of(0)
    assert "downloads the driver package" not in said
    assert "encrypted connection" not in said
    assert "These files are yours" in said


@pytest.mark.parametrize("dismiss", ["ok", "escape", "enter"])
def test_declining_the_folder_consent_installs_nothing(
        dialog, folder_route, dismiss):
    def _act(w):
        if dismiss == "ok":
            _ok_button(w).click()
        elif dismiss == "escape":
            w.reject()
        else:
            _press(w, "Key_Return")

    with ModalDriver(_act) as drv:
        dialog._serial_from_folder()
    assert drv.modal_count == 1
    assert folder_route == [], "%s went ahead with the install" % dismiss


def test_the_folder_route_still_refuses_an_unknown_processor(
        dialog, folder_route, monkeypatch):
    """The arch check has to stay in front of everything, consent included."""
    monkeypatch.setattr(sd.SettingsDialog, "_serial_machine_arch",
                        lambda self: "")
    with ModalDriver(lambda w: _ok_button(w).click()) as drv:
        dialog._serial_from_folder()
    assert drv.modal_count == 1
    assert "kind of processor" in drv.text_of(0)
    assert folder_route == []


# ---------------------------------------------------------------------------
# ONE OUTCOME, ONE WINDOW — and 3010 gets its own
# ---------------------------------------------------------------------------
#
# **THE WINDOW THAT CONTRADICTED ITSELF.** `pnputil` exit 3010 means "the driver
# is accepted; restart to finish switching it on". Core used to answer that as
# `(True, "…needs a restart…")`, so the flow read the `True` and went on to
# `verify_bound` — which cannot find a COM port for a driver that is staged and
# not yet live — and printed core's restart sentence UNDERNEATH the heading
# *"Everything ChromIQ could check passed, and there is still no COM port."*
# Two incompatible statements in one window, on the one code that means the
# install actually worked.
#
# The tests below drive the real dialog for every outcome the install can end
# in and read what is on the screen. They are the reason `install()` returning a
# `DriverResult` is worth the churn: each of them fails against the shipped
# code, and each of them names a window rather than a sentence.


def _serial_window(dialog, monkeypatch, tmp_path, **core):
    """Run one install through the real dialog and hand back what was on screen."""
    _fake_core(monkeypatch, **core)
    with ModalDriver(lambda w: _ok_button(w).click()) as drv:
        dialog._serial_check_and_install(tmp_path, _unbound_before())
    assert drv.timed_out is False, "a window would not close"
    assert drv.modal_count == 1, "an install ended and the user was told nothing"
    return drv.text_of(0)


def test_3010_says_restart_and_not_that_nothing_worked(
        dialog, monkeypatch, tmp_path):
    """DEFECT 1, on screen.

    `verify_bound` is deliberately still consulted and deliberately still finds
    nothing — that is exactly the state 3010 leaves the machine in — and the
    window must nonetheless be about restarting.
    """
    said = _serial_window(
        dialog, monkeypatch, tmp_path,
        install_result=("REBOOT_REQUIRED", "REBOOT_TO_FINISH"),
        bound=("FAILED", "STILL_NO_PORT"))
    assert "needs a restart to finish switching it on" in said
    assert "Restart the computer" in said
    assert "Everything ChromIQ could check passed" not in said, (
        "the 3010 window still leads with the heading that contradicts it")
    assert "there is still no COM port" not in said
    assert "Windows did not install the package" not in said


def test_3010_that_did_bind_anyway_still_says_it_worked(
        dialog, monkeypatch, tmp_path):
    """A restart is not always needed for the port to appear. When one HAS
    appeared, saying "restart to finish" would be the same fault the other way
    round — so the COM port still decides."""
    said = _serial_window(
        dialog, monkeypatch, tmp_path,
        install_result=("REBOOT_REQUIRED", "REBOOT_TO_FINISH"),
        bound=("OK", "PORT_APPEARED"), ports=("COM7",))
    assert "It worked." in said
    assert "COM7" in said
    assert "Restart the computer" not in said


def test_a_refused_elevation_is_not_reported_as_a_cancellation(
        dialog, monkeypatch, tmp_path):
    """`ConsentPromptBehaviorUser = 0` is an ordinary managed-desktop setting:
    Windows fails the elevation with NO prompt at all. Telling that user "you
    said No at the permission prompt" describes a prompt they never saw."""
    said = _serial_window(
        dialog, monkeypatch, tmp_path,
        install_result=("ACCESS_DENIED", "ELEVATION_REFUSED"))
    assert "Windows did not install the package." in said
    assert "refused to ask for your permission" in said
    assert "stopped at the Windows permission prompt" not in said


def test_no_permission_lands_on_the_failure_window_with_its_own_reason(
        dialog, monkeypatch, tmp_path):
    said = _serial_window(dialog, monkeypatch, tmp_path,
                          install_result=("ACCESS_DENIED", "NO_PERMISSION"))
    assert "Windows did not install the package." in said
    assert "this account may not install drivers" in said


def test_259_says_windows_took_it_and_found_nothing_to_use_it_on(
        dialog, monkeypatch, tmp_path):
    """`pnputil` 259 added the package and matched no device. "Windows did not
    install the package" would be untrue, and "there is still no COM port"
    would be the 3010 mistake wearing a different exit code."""
    said = _serial_window(dialog, monkeypatch, tmp_path,
                          install_result=("NO_OP", "NOTHING_TO_APPLY"))
    assert "did not attach it to anything" in said
    assert "found no device to use it on" in said
    assert "Everything ChromIQ could check passed" not in said
    assert "Windows did not install the package." not in said


def test_an_adapter_unplugged_mid_flow_is_not_reported_as_a_failure(
        dialog, monkeypatch, tmp_path):
    """`verify_bound` says NO_OP, not FAILED: nothing could be judged. The
    "everything passed and there is still no COM port" window would be a third
    self-contradiction — the adapter was not there to be given one."""
    said = _serial_window(dialog, monkeypatch, tmp_path,
                          install_result=("OK", "DRIVER_ACCEPTED"),
                          bound=("NO_OP", "UNPLUGGED_MID_FLOW"))
    assert "cannot tell you whether that worked" in said
    assert "unplugged while ChromIQ was working" in said
    assert "Everything ChromIQ could check passed" not in said


def test_nothing_was_unbound_to_begin_with_says_so(
        dialog, monkeypatch, tmp_path):
    said = _serial_window(dialog, monkeypatch, tmp_path,
                          install_result=("OK", "DRIVER_ACCEPTED"),
                          bound=("NO_OP", "NOTHING_TO_CHECK"), ports=("COM5",))
    assert "cannot tell you whether that worked" in said
    assert "COM5" in said
    assert "Everything ChromIQ could check passed" not in said


@pytest.mark.parametrize("outcome,reason,heading", [
    ("REBOOT_REQUIRED", "REBOOT_TO_FINISH", "restart"),
    ("USER_CANCELLED", "CANCELLED_AT_PROMPT", "permission prompt"),
    ("ACCESS_DENIED", "NO_PERMISSION", "did not install"),
    ("NO_OP", "NOTHING_TO_APPLY", "did not attach"),
    ("FAILED", "PACKAGE_UNREADABLE", "did not install"),
])
def test_every_install_outcome_reaches_a_window_of_its_own(
        dialog, monkeypatch, tmp_path, outcome, reason, heading):
    """Five outcomes, five windows, and none of them silent. The parametrisation
    is the point: adding an `Outcome` that falls through the routing shows up
    here as an empty window rather than as a user's confusion."""
    said = _serial_window(dialog, monkeypatch, tmp_path,
                          install_result=(outcome, reason),
                          bound=("FAILED", "STILL_NO_PORT"))
    assert heading in said


# ---------------------------------------------------------------------------
# ...and every word of it is in the reader's language
# ---------------------------------------------------------------------------
#
# **DEFECT 2.** Core's sentences were composed in English in a module with no
# `tr()` in it, and the dialog printed them verbatim — so the German window read
# five paragraphs of German and then *"Windows refused the change. This normally
# means the account does not have permission to install drivers…"*. There was no
# key to translate it under; the sentence did not exist in any catalogue.


@pytest.mark.parametrize("outcome,reason", [
    ("REBOOT_REQUIRED", "REBOOT_TO_FINISH"),
    ("ACCESS_DENIED", "NO_PERMISSION"),
    ("ACCESS_DENIED", "ELEVATION_REFUSED"),
    ("NO_OP", "NOTHING_TO_APPLY"),
    ("FAILED", "PACKAGE_INVALID"),
    ("FAILED", "UNKNOWN_EXIT"),
])
def test_the_german_outcome_window_has_no_english_left_in_it(
        dialog, monkeypatch, tmp_path, in_language, outcome, reason):
    in_language("de")
    said = _serial_window(dialog, monkeypatch, tmp_path,
                          install_result=(outcome, reason),
                          bound=("FAILED", "STILL_NO_PORT"))
    for english in ("Windows refused the change",
                    "Windows accepted the driver",
                    "needs a restart to finish switching it on",
                    "Nothing was changed",
                    "rejected the driver package as invalid",
                    "found no device to use it on",
                    "refused to ask for your permission",
                    "stopped with an error"):
        assert english not in said, (
            f"{reason}: core's English is still on the German window: "
            f"{english!r}")
    assert "Windows" in said or "ChromIQ" in said, (
        "the window rendered empty, which would pass the assertions above for "
        "the wrong reason")


def test_the_german_3010_window_is_german_all_the_way_down(
        dialog, monkeypatch, tmp_path, in_language):
    """The headline window of this fix, in the language it was found broken in."""
    in_language("de")
    said = _serial_window(
        dialog, monkeypatch, tmp_path,
        install_result=("REBOOT_REQUIRED", "REBOOT_TO_FINISH"),
        bound=("FAILED", "STILL_NO_PORT"))
    assert "Neustart" in said, "the 3010 window is not translated"
    assert "restart" not in said.lower().replace("neustart", "")
    assert "COM-Anschluss" in said or "COM-Port" in said


@pytest.mark.parametrize("code", ALL_CODES)
def test_every_reason_sentence_is_translated_in_every_language(
        code, in_language):
    """A reason with no catalogue entry falls back to English silently — which
    is the defect, one sentence at a time, in whichever language nobody checked.
    """
    ch = pytest.importorskip("core.ch34x_driver")
    if code == "en":
        return
    in_language(code)
    english = {}
    from core import i18n
    i18n.set_language("en")
    for reason in ch.Reason:
        english[reason] = sd.serial_reason_text(
            ch.DriverResult(ch.Outcome.FAILED, reason))
    in_language(code)
    untranslated = [
        r.name for r in ch.Reason
        if english[r] and sd.serial_reason_text(
            ch.DriverResult(ch.Outcome.FAILED, r)) == english[r]]
    assert untranslated == [], (
        f"[{code}] these reason sentences are still English: {untranslated}")


# ---------------------------------------------------------------------------
# The measurement guard, in German, for BOTH holders
# ---------------------------------------------------------------------------
#
# **THE GERMAN SENTENCE WAS RE-WORDED FOR ONE HOLDER AND BROKEN FOR THE OTHER.**
# `f7a565ad` changed the guard from "Dein Instrument wird gerade gelesen, von
# {where} aus." to "…wird gerade aus {where} gelesen.", and its write-up claimed
# the new form "works for the spot-read holder too". It does not. There are two
# holders (`core/instrument_lease.py`), and the German labels are already
# case-inflected to fit the preposition:
#
#     MEASURE_TAB  -> "dem Tab „Messen“"                      ✔ "aus dem Tab …"
#     SPOT_TOOL    -> "Werkzeuge ▸ Einzelne Felder messen"    ✘ "aus Werkzeuge ▸ …"
#
# `tests/test_i18n.py` cannot see it — the placeholder is present and the key is
# translated — and nothing rendered the `SPOT_TOOL` branch, so a wrong sentence
# had no way of being noticed except by somebody reading it. These tests render
# it.
#
# The first fix was the LABEL — a dative noun phrase, which fits both of the
# German sentences that interpolate it. **AND IT DOES NOT GENERALISE, which the
# review found by rendering the same sentence in the other eleven languages:**
#
#     it   "da la scheda Misura"            must contract to "dalla scheda"
#     pt   "a partir de o separador Medir"  must contract to "a partir do"
#     pl   "z karcie Pomiar"                needs the genitive "z karty"
#     ru   "из вкладке «Измерение»"         needs the genitive "из вкладки"
#
# You cannot inflect one label to fit two prepositions in two sentences in a
# language with cases. So `measurement_block_text` no longer interpolates
# anything: it picks a WHOLE SENTENCE per holder, and each language writes its
# own preposition, article and case. The tests below are the German ones plus
# the four that were wrong, and they render rather than read.
#
# `M_INSTRUMENT_BUSY` still glues "in {where}" and still has the same fault. It
# is a §M message, its wording is not ours to change, and it is not this
# branch's — it is reported, not fixed here.


def test_the_spot_tool_label_names_the_route_that_really_opens_it():
    """The claim in the label, checked against the code that opens the window.

    `Tools ▸ Read single patches` has to be a route a user can walk: the
    masthead's Tools button (`ui/main_window.py`) opens `ui.tools_popup`, whose
    first group is `Measurements`, and its `spot_read` row is what reaches
    `open_tool_dialog("spot_read")` -> `SpotReadDialog`.
    """
    from core import instrument_lease as lease
    from ui.tools_popup import _ENTRIES, _GROUPS

    assert lease.SPOT_TOOL.startswith("Tools ▸ ")
    assert "spot_read" in {e.key for e in _ENTRIES}, (
        "the label names a Tools entry the Tools popup does not have")
    holder = [header for header, entries in _GROUPS
              if any(e.key == "spot_read" for e in entries)]
    assert holder, "spot_read is not in any group"
    assert holder[0] == _GROUPS[0][0], (
        "the entry moved out of the popup's first group; the label may need "
        "to name the group it is in now")


@pytest.mark.parametrize("holder", ["MEASURE_TAB", "SPOT_TOOL"])
def test_the_german_guard_reads_as_a_sentence_for_either_holder(
        in_language, holder):
    from core import instrument_lease as lease
    in_language("de")
    said = sd.measurement_block_text(getattr(lease, holder))
    where = lease.where_label(getattr(lease, holder))
    assert f"aus {where} gelesen" in said, (
        f"the German guard does not read as a sentence for {holder}: {said!r}")
    assert "aus Werkzeuge ▸" not in said, (
        "the bare menu path is back in the middle of the sentence")


def test_the_german_guard_window_names_the_spot_tool_grammatically(
        dialog, on_windows, monkeypatch, in_language):
    """The defect where it is actually read: on the screen, in German.

    The guard is this branch's headline safety feature — installing a driver
    restarts the device stack and takes an open COM handle with it — so the one
    window it ever shows has to be a sentence.
    """
    from core import instrument_lease as lease
    in_language("de")
    monkeypatch.setattr(sd, "measurement_in_progress",
                        lambda parent=None: lease.SPOT_TOOL)
    with ModalDriver(lambda w: _ok_button(w).click()) as drv:
        dialog._show_usb_installer()
    assert drv.timed_out is False
    assert drv.modal_count == 1, "the guard refused without showing anything"
    said = drv.text_of(0)
    assert "aus dem Fenster „Werkzeuge ▸ Einzelne Felder messen“ gelesen" in said
    assert "aus Werkzeuge ▸" not in said
    assert "USB-to-serial bridge" not in said


# --- the four languages the label trick could not reach ---------------------
#
# Each entry is (code, holder, the fragment that MUST be there, the glued form
# that must NOT). The wrong forms are the ones the shipped catalogues really
# produced before this change — copied from the rendering, not imagined.
_GRAMMAR = [
    ("it", "MEASURE_TAB", "dalla scheda Misura", "da la scheda"),
    ("it", "SPOT_TOOL", "dalla finestra Strumenti ▸", "da la "),
    ("pt", "MEASURE_TAB", "a partir do separador Medir", "a partir de o "),
    ("pt", "SPOT_TOOL", "a partir da janela Ferramentas ▸", "a partir de a "),
    ("pl", "MEASURE_TAB", "z karty Pomiar", "z karcie"),
    ("pl", "SPOT_TOOL", "z okna Narzędzia ▸", "z Narzędzia ▸"),
    ("ru", "MEASURE_TAB", "из вкладки «Измерение»",
     "из вкладке"),
    ("ru", "SPOT_TOOL", "из окна «Инструменты",
     "из Инструменты"),
]


@pytest.mark.parametrize("code,holder,must,must_not", _GRAMMAR)
def test_the_guard_is_a_sentence_in_the_four_that_inflect(
        in_language, code, holder, must, must_not):
    """Rendered, not read. This is the only thing that could have caught it.

    `tests/test_i18n.py` sees a present, translated key whose placeholder
    matches; `scripts/i18n_extract.py` sees nothing at all, because the broken
    sentence exists nowhere as a literal — it was assembled at run time. So the
    check has to be the rendering itself.
    """
    from core import instrument_lease as lease
    in_language(code)
    said = sd.measurement_block_text(getattr(lease, holder))
    assert must in said, f"[{code}/{holder}] expected {must!r} in:\n{said}"
    assert must_not not in said, (
        f"[{code}/{holder}] the glued preposition is back: {must_not!r}")


@pytest.mark.parametrize("code", ALL_CODES)
def test_the_guard_never_formats_a_label_into_a_sentence_again(code,
                                                               in_language):
    """The structural rule, in every language ChromIQ ships.

    Whatever the wording becomes, no holder's sentence may be built by dropping
    `where_label()` into a slot — that is the shape that cannot be made correct
    in a language with cases, and it is the shape that shipped.
    """
    import inspect
    from core import instrument_lease as lease
    in_language(code)
    for holder in (lease.MEASURE_TAB, lease.SPOT_TOOL, "something else"):
        said = sd.measurement_block_text(holder)
        assert "{" not in said and "}" not in said, (code, holder, said)
    src = inspect.getsource(sd.measurement_block_text) + \
        inspect.getsource(sd._read_right_now_sentence)
    assert "where_label" not in src, (
        "measurement_block_text is interpolating the holder's LABEL again; the "
        "whole sentence has to be the translatable unit")
    assert ".format(" not in src, (
        "a sentence in this guard is being assembled from parts again")


def test_the_guard_is_handed_an_identifier_not_a_label():
    """`measurement_in_progress` answers with the lease's identifier.

    English hides this completely — `where_label(SPOT_TOOL)` returns the
    identifier itself — so the assertion is made in German, where the two are
    different strings.
    """
    from core import i18n
    from core import instrument_lease as lease

    owner = _Holder()
    assert lease.acquire(owner, lease.SPOT_TOOL)
    try:
        i18n.set_language("de")
        got = sd.measurement_in_progress()
        assert got == lease.SPOT_TOOL, (
            f"expected the identifier, got {got!r} — a translated label cannot "
            "be handed to a sentence that has to inflect around it")
        assert got != lease.where_label(lease.SPOT_TOOL)
    finally:
        i18n.set_language("en")
        lease.release(owner)


# ---------------------------------------------------------------------------
# The reboot window must not name a button that is not on it
# ---------------------------------------------------------------------------
#
# Caught on the REAL window, in German, before it shipped. The first draft read
# "…come back to THIS window and use Erneut prüfen" — and this window has one
# button, which says OK. `Check again` lives on the driver helper behind it,
# which is reached by opening `Instrument drivers…` in Preferences. Naming a
# control that is not on the screen is exactly the fault `3c3ba01b` fixed on the
# WinUSB half ("half of this window was German … and it named a button that was
# not there"), and it nearly shipped again on this one.


def test_the_reboot_window_does_not_point_at_a_button_on_itself():
    text, _ = sd.serial_outcome_text(stage="reboot", folder="f")
    assert "this window" not in text.lower(), (
        "the reboot window sends the user to a button it does not have")


@pytest.mark.parametrize("code", ALL_CODES)
def test_the_reboot_window_names_both_controls_it_points_at(code, in_language):
    """Both names come from the buttons' own keys, so they cannot drift from
    the controls in any of the twelve languages."""
    from core.i18n import tr
    in_language(code)
    text, _ = sd.serial_outcome_text(stage="reboot", folder="f")
    assert sd._in_prose(sd._label_check_again()) in text, (
        f"[{code}] the reboot window does not name the Check again button")
    assert sd._in_prose(tr("Instrument drivers…")) in text, (
        f"[{code}] the reboot window does not name the control that reopens "
        f"the driver helper")


# ===========================================================================
# THE GEOMETRY TESTS WERE ALL WRITTEN IN ENGLISH, AND THE DEFECT IS GERMAN
# ===========================================================================
#
# `d5d49696` ("the consent window came out 14px short whenever the text nearly
# filled it") is the reserve of the vertical scrollbar's width inside
# `ContentHeightScrollArea._content_height`. Every test above that could notice
# it renders in ENGLISH — and English is not the case that fails.
#
# Measured, on the real windows, with that one reserve removed and nothing else
# changed:
#
#   window                    shipped              without the reserve
#   "Before ChromIQ starts"   607 x 496, 0 hidden  607 x 496, 0 hidden   (en)
#   "Bevor ChromIQ beginnt"   608 x 528, 0 hidden  608 x 512, 16 HIDDEN  (de)
#   "Instrument drivers"      624 x 774, 0 hidden  624 x 774, 0 hidden   (en)
#   "Instrumententreiber"     624 x 838, 0 hidden  624 x 822, 16 HIDDEN  (de)
#
# 513 tests stayed green through that. German prose is ~8 % longer, so it is
# German that lands on the marginal line where 18 px of width costs a line of
# height — the exact case the reserve exists for. So these two tests are the
# English ones again, in the language the fault actually occurs in.

_LONGEST_LANGUAGES = ["en", "de"]


@pytest.fixture
def on_a_tall_screen(monkeypatch):
    """Ask the geometry question on a screen with room, whatever the host has.

    THE SCREEN IS NOT A CONSTANT AND THESE ASSERTIONS ARE ABOUT HEIGHT. The
    offscreen platform reports 800 x 800, so the cap is 720 and the German
    helper window — which wants 838 — is AT the cap: `hidden == 0 or
    height == cap` then passes without ever asking the question, and the M6
    mutation that this test exists to kill goes green. (This is also why the
    Windows gate has a flaky 704-vs-718 geometry failure: the same assertion,
    the same cap, a different font.) A screen tall enough that the cap cannot
    bite makes the answer the same on every host.
    """
    from PyQt6.QtCore import QRect
    real = sd.SettingsDialog._fit_to_screen

    class _TallScreen:
        def availableGeometry(self):
            return QRect(0, 0, 1920, 2000)

    def _fit(self, dlg):
        dlg.screen = lambda: _TallScreen()
        return real(self, dlg)

    monkeypatch.setattr(sd.SettingsDialog, "_fit_to_screen", _fit)


@pytest.mark.parametrize("code", _LONGEST_LANGUAGES)
def test_the_consent_window_hides_none_of_itself_in_german_too(
        dialog, on_a_tall_screen, in_language, code):
    """`_driver_notice` at the width it really gets, in the longest language."""
    in_language(code)
    found = {}

    def _look(w):
        found.update(_geometry_of(w))
        _ok_button(w).click()

    with ModalDriver(_look):
        dialog._driver_notice(
            "T", sd.serial_install_intro_text(
                r"C:\Users\x\AppData\Local\ChromIQ\drivers\2026-09-05_01-42-17",
                "ARM64"))
    assert found["height"] < found["cap"], (
        "[%s] the window is at the screen cap (%d px), so the question this "
        "test asks was never put — see `on_a_tall_screen`"
        % (code, found["cap"]))
    assert found["hidden"] == 0, (
        "[%s] %d px of the consent text is below the fold in a %d px window "
        "that could have been %d px"
        % (code, found["hidden"], found["height"], found["cap"]))


@pytest.mark.parametrize("code", _LONGEST_LANGUAGES)
def test_the_driver_helper_hides_none_of_itself_in_german_too(
        dialog, on_windows, on_a_tall_screen, monkeypatch, in_language, code):
    """The same relation for the helper window, whose German is 64 px taller."""
    in_language(code)
    _worst_case_hardware(monkeypatch)
    found = {}

    def _look(w):
        found.update(_geometry_of(w))
        _button(w, sd._label_check_again()).click()

    with ModalDriver(_look):
        dialog._show_usb_installer()
    assert found["height"] < found["cap"], (
        "[%s] the window is at the screen cap (%d px), so the question this "
        "test asks was never put — see `on_a_tall_screen`"
        % (code, found["cap"]))
    assert found["hidden"] == 0, (
        "[%s] %d px of the helper window is below the fold in a %d px window "
        "that could have been %d px"
        % (code, found["hidden"], found["height"], found["cap"]))


# ---------------------------------------------------------------------------
# A WINDOWS FEATURE MUST STAY ON WINDOWS
# ---------------------------------------------------------------------------
#
# Both guards below survived a deliberate mutation against all 24 test files
# that touch `settings_dialog` — 983 tests, all green with the Preferences
# button built on every platform and with `_show_usb_installer`'s own
# early-return deleted. Nothing in the suite could see a Windows-only window
# arriving on macOS and Linux, where `pnputil` does not exist and every
# sentence in it is untrue.
#
# They cannot be written with the `on_windows` fixture, which is what every
# other driving test uses: that fixture pins `_sys.platform` TO win32, and
# these two are about what happens when it is not.

def test_the_preferences_button_is_built_on_windows_and_nowhere_else():
    from types import SimpleNamespace
    import inspect
    src = inspect.getsource(sd.SettingsDialog._build_ui)
    guard = 'if _sys.platform == "win32":'
    assert guard in src, (
        "the Preferences driver button lost its platform guard — it would "
        "appear on macOS and Linux, where there is no pnputil to run")
    # ...and the guard is the one the button is inside, not some other line.
    after = src.split(guard, 1)[1].split("\n        if ", 1)[0]
    assert 'tr("Instrument drivers…")' in after, (
        "the driver button is no longer inside the win32 guard")


def test_the_driver_helper_shows_nothing_when_the_platform_is_not_windows(
        dialog, monkeypatch):
    """Belt as well as braces: the method refuses even if it is called."""
    from types import SimpleNamespace
    monkeypatch.setattr(sd, "_sys", SimpleNamespace(platform="darwin"))
    with ModalDriver() as drv:
        dialog._show_usb_installer()
    assert drv.modal_count == 0, (
        "the Windows driver helper opened on %r: %r"
        % ("darwin", [t for t, _ in drv.seen]))



# ===========================================================================
# THE BUTTON THAT DECLINES MUST NOT SAY "OK"
# ===========================================================================
#
# On the consent window "Before ChromIQ starts" the green button reads
# `Download and install` and the other one read **OK** — and OK is the DECLINE
# (`ok.clicked.connect(dlg.reject)`, deliberately, because `box.accepted` fires
# for OK too and that is how OK once started an elevated driver install). The
# behaviour is right and mutation-tested; the WORD was the fault, on the one
# window in this app whose entire purpose is informed consent. Somebody skimming
# clicks OK meaning "yes" and gets the opposite of what they intended.
#
# `Not now` is already the app's own word for this — `ui/cr30_calibration.py`
# builds a button with that exact label for declining an offered action — so
# these tests also pin that the two stay ONE key, and that a window with nothing
# to decline goes on saying OK, which is what a notice's button should say.

ALL_LANGUAGES = ["en"] + sorted(ALL_CODES)

#: The dark stylesheet's button font (`ui/styles.py`). Menlo is monospaced and
#: much wider than Inter, so Dark is the appearance where a button row runs out
#: of window — and it is applied to the DIALOG here, never to the application:
#: `qapp.setStyleSheet()` re-polishes every widget the suite has alive and costs
#: half a minute of gate time (CLAUDE.md).
_DARK_BUTTON_FONT = 'QPushButton { font-family: "Menlo"; }'


def _dismiss_button(widget):
    """The dismissing button, whatever it now says on it."""
    from PyQt6.QtWidgets import QDialogButtonBox
    for box in widget.findChildren(QDialogButtonBox):
        btn = box.button(QDialogButtonBox.StandardButton.Ok)
        if btn is not None:
            return btn
    return None


def _button_row(widget):
    """The dialog's button box, and how each visible button fits."""
    from PyQt6.QtWidgets import QDialogButtonBox
    boxes = widget.findChildren(QDialogButtonBox)
    assert boxes, "the window has no button box"
    box = boxes[-1]
    out = []
    for b in box.buttons():
        if not b.isVisible():
            continue
        out.append({
            "text": b.text().replace("&", ""),
            "width": b.width(),
            "wants": b.sizeHint().width(),
            "right": b.mapTo(widget, b.rect().topRight()).x(),
        })
    return box, out


def _consent_window(dialog, look):
    """Drive the REAL consent window — `_driver_notice` with an offer on it."""
    from core.i18n import tr
    with ModalDriver(look) as drv:
        took = dialog._driver_notice(
            tr("Before ChromIQ starts"),
            sd.serial_install_intro_text(
                r"C:\Users\x\AppData\Local\ChromIQ\drivers\2026-09-05_01-42-17",
                "ARM64"),
            tr("Download and install"))
    assert drv.timed_out is False
    return took


def test_the_consent_window_does_not_call_its_decline_button_ok(
        dialog, in_language):
    in_language("en")
    seen = {}

    def _look(w):
        btn = _dismiss_button(w)
        seen["label"] = btn.text().replace("&", "")
        seen["labels"] = [b["text"] for b in _button_row(w)[1]]
        btn.click()

    took = _consent_window(dialog, _look)
    assert took is False, "the dismissing button must decline, not accept"
    assert seen["label"] != "OK", (
        "the button that DECLINES an elevated driver install still says OK")
    assert seen["label"] == sd._label_not_now()
    assert seen["labels"] == ["Download and install", "Not now"], seen["labels"]


def test_the_decline_button_is_still_the_one_enter_presses(dialog, in_language):
    """Relabelling must not have moved the default off the safe button.

    `f7a565ad` found `Return` — the key most people press to get rid of a
    window — DOWNLOADING AND INSTALLING AN ELEVATED DRIVER, because Qt promotes
    a button box's first AcceptRole button. The new label keeps the button's
    role and its identity, and this is the assertion that says so.
    """
    in_language("en")
    seen = {}

    def _look(w):
        btn = _dismiss_button(w)
        seen["default"] = btn.isDefault()
        seen["others"] = [b.text().replace("&", "")
                          for b in w.findChildren(type(btn))
                          if b is not btn and b.isDefault()]
        btn.click()

    _consent_window(dialog, _look)
    assert seen["default"] is True, "the safe button is no longer the default"
    assert seen["others"] == [], seen["others"]


def test_a_notice_with_nothing_to_decline_still_says_ok(dialog, in_language):
    """The other half. A window that asks nothing is acknowledged, not declined,
    and OK is exactly the right word for that."""
    from core.i18n import tr
    in_language("en")
    seen = {}

    def _look(w):
        seen["labels"] = [b["text"] for b in _button_row(w)[1]]
        _dismiss_button(w).click()

    with ModalDriver(_look) as drv:
        dialog._driver_notice(tr("Instrument drivers"),
                              sd.serial_unknown_arch_text())
    assert drv.timed_out is False
    assert seen["labels"] == ["OK"], seen["labels"]


def test_the_decline_label_is_the_apps_own_word_for_declining():
    """One key, not two. `Not now` is already a button in the CR30 calibration
    window for the same meaning, and a near-duplicate key is exactly how twelve
    translations get lost at once — see
    `test_there_is_only_one_key_per_button` above.
    """
    import inspect
    import json
    import ui.cr30_calibration as cal
    assert 'tr("Not now")' in inspect.getsource(cal), (
        "the CR30 window no longer uses this label; check the two have not "
        "drifted into two keys")
    root = Path(sd.__file__).resolve().parent.parent.parent / "data" / "i18n"
    for code in ALL_CODES:
        cat = json.loads(root.joinpath(f"{code}.json").read_text(
            encoding="utf-8"))
        assert "Not now" in cat, f"[{code}] the decline label is not a key"
        for near in ("Not now…", "not now", "Not Now"):
            assert near not in cat, f"[{code}] near-duplicate key {near!r}"


@pytest.mark.parametrize("code", ALL_LANGUAGES)
def test_the_consent_buttons_fit_the_row_in_every_language(
        dialog, on_a_tall_screen, in_language, code):
    """The button row, measured, in all thirteen — and in the wider font.

    THE PRECONDITION IS THE POINT, and it is BB's finding: `_fit_to_screen` caps
    the window at 0.9 of the screen, the offscreen platform reports 800 x 800,
    and the German window sits AT that cap — where a geometry assertion passes
    without ever asking the question. `on_a_tall_screen` lifts the cap out of
    the way and `height < cap` is asserted FIRST.
    """
    in_language(code)
    found = {}

    def _look(w):
        found["geom"] = _geometry_of(w)
        box, row = _button_row(w)
        found["row"] = row
        found["win_w"] = w.width()
        # The dark appearance's button font, on this dialog only. It is the
        # widest this row ever gets.
        w.setStyleSheet(_DARK_BUTTON_FONT)
        box.layout().invalidate()
        box.layout().activate()
        found["dark_box_needs"] = box.sizeHint().width()
        found["dark_row"] = [
            {"text": b.text().replace("&", ""),
             "wants": b.sizeHint().width()} for b in box.buttons()]
        w.setStyleSheet("")
        _dismiss_button(w).click()

    _consent_window(dialog, _look)

    g, row = found["geom"], found["row"]
    assert g["height"] < g["cap"], (
        "[%s] the window is at the screen cap (%d px), so this test asked "
        "nothing — see `on_a_tall_screen`" % (code, g["cap"]))
    assert len(row) == 2, (code, row)
    for b in row:
        assert b["width"] >= b["wants"], (
            "[%s] %r is %d px wide and wants %d — the label is clipped"
            % (code, b["text"], b["width"], b["wants"]))
        assert 0 < b["right"] <= found["win_w"], (
            "[%s] %r ends %d px outside a %d px window"
            % (code, b["text"], b["right"], found["win_w"]))
    assert g["hbar_max"] == 0 and not g["hbar_visible"], (
        "[%s] the consent window scrolls sideways" % code)
    assert g["buttons_below_the_bottom_edge"] == [], (
        "[%s] %r" % (code, g["buttons_below_the_bottom_edge"]))
    assert found["dark_box_needs"] <= found["win_w"], (
        "[%s] in the dark appearance's font the button row wants %d px in a "
        "%d px window: %r"
        % (code, found["dark_box_needs"], found["win_w"], found["dark_row"]))

"""ArgyllCMS can reach a USB instrument through ONE Windows driver: libusb-win32.

Measured, three ways, on Argyll 3.5.0's own binaries:

* `spotread.exe` contains the string `\\\\.\\libusb0-%04d` and no other device
  path. It imports **no** `WinUsb_*` symbol, and it does not import
  `libusb0.dll` either — its DLL imports are ADVAPI32, GDI32, KERNEL32,
  SETUPAPI, USER32, hid and ntdll — so it opens that kernel device object with
  `CreateFile` itself and a user-mode compatibility shim cannot stand in for the
  driver. `\\\\.\\libusb0-NNNN` is created by libusb-win32's `libusb0.sys`.
* `usb/ArgyllCMS.inf`, which ships with Argyll, binds
  `AddService = libusb0, 0x00000002, libusb0_add_service` with
  `ServiceBinary = %12%\\libusb0.sys`, for all 28 devices it lists.
* Argyll's changelog dates the switch at V1.5.0 (2013): *"No longer using
  libusb for USB access, using native USB access instead. MSWin uses the
  libusb-win32 kernel driver."* The two WinUSB lines in that changelog are from
  V1.2.0 and V1.3.3 (2010-2011) and describe the forked libusb-1.0 back end
  V1.5.0 discarded.

Two consequences lived on master together and compounded each other:

1. `enumerate_connected()` treated `("winusb", "libusb0")` as driven, so a
   WinUSB-bound instrument reported **"driver installed ✓"** while Argyll
   printed `** No ports found **` — a closed loop with no way out from inside
   the app, the same shape as the ghost-instance bug.
2. **ChromIQ's own Zadig instructions told the user to choose WinUSB**, in four
   places. The app walked its users into the state it then could not detect.

This file guards both halves. Every test here fails if either comes back.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import core.usb_driver_installer as udi
from ui.dialogs import settings_dialog as sd


I1PRO = "GretagMacbeth i1 Pro / i1 Pro 2"

ALL_CODES = [p.stem for p in
             (Path(sd.__file__).resolve().parent.parent.parent
              / "data" / "i18n").glob("*.json")]


@pytest.fixture
def in_language():
    """Render in one language, and always come back to English.

    The reset is in a fixture, not at the end of each test, because a failing
    assertion would skip it and leave every later English pin in the worker
    reading German.
    """
    from core import i18n

    def _set(code):
        i18n.set_language(code)
        return code
    yield _set
    i18n.set_language("en")


def _entry(service: str):
    """One registry entry for the i1 Studio, bound to *service*."""
    return [("VID_0765&PID_6008", [("7&3b74c78&0&1", service)])]


_PRESENT = {r"USB\VID_0765&PID_6008\7&3B74C78&0&1"}


# ---------------------------------------------------------------------------
# HALF 1 — what counts as driven
# ---------------------------------------------------------------------------

def test_libusb0_is_the_only_service_that_counts_as_driven():
    """The pin. `ARGYLL_USB_SERVICE` is one name, not a set of them.

    It was `("winusb", "libusb0")`. Widening it again — to a tuple, a set, a
    second `or` clause — is the regression, and it is invisible in a diff that
    only adds a word.
    """
    assert udi.ARGYLL_USB_SERVICE == "libusb0"
    assert isinstance(udi.ARGYLL_USB_SERVICE, str), (
        "the acceptance test is one service name; a collection here is how the "
        "WinUSB bug is written back in")


def test_a_winusb_bound_instrument_is_not_driven():
    """THE BUG, PINNED. Argyll prints `** No ports found **` for this device;
    ChromIQ used to print `driver installed ✓` about the same one."""
    got = udi.attached_devices(_entry("WinUSB"), _PRESENT)
    assert [d.has_winusb for d in got] == [False], (
        "a WinUSB-bound instrument was reported as driven. ArgyllCMS cannot "
        "open it: spotread carries no WinUsb_* symbol and opens "
        r"\\.\libusb0-NNNN, which only libusb-win32's libusb0.sys creates")


def test_a_libusb0_bound_instrument_is_driven():
    """The other direction, so the fix cannot be "always False"."""
    got = udi.attached_devices(_entry("libusb0"), _PRESENT)
    assert [d.has_winusb for d in got] == [True]


def test_libusbk_is_not_driven_either():
    """Zadig offers libusbK and users pick it.

    libusbK ships a user-mode `libusb0.dll` compatibility shim, which makes it
    look interchangeable. It is not relevant here: Argyll does not link that
    DLL — measured, `spotread.exe` imports no `libusb0.dll` — it calls
    `CreateFile` on the kernel object name itself. Whether `libusbK.sys`
    creates `\\.\\libusb0-NNNN` is not something this project has measured, and
    Argyll's own INF installs `libusb0` and nothing else. Accepting libusbK
    would mean asserting an untested compatibility claim in order to *withhold*
    help from a user whose instrument may well be dark.
    """
    got = udi.attached_devices(_entry("libusbK"), _PRESENT)
    assert [d.has_winusb for d in got] == [False]


@pytest.mark.parametrize("service", ["", "usbccgp", "usbser", "WUDFRd",
                                     "CH341SER_M64"])
def test_no_other_service_is_mistaken_for_a_driver(service):
    got = udi.attached_devices(_entry(service), _PRESENT)
    assert [d.has_winusb for d in got] == [False]


def test_the_service_comparison_stays_case_insensitive():
    """Windows writes what it likes; the registry returns it verbatim."""
    for spelling in ("libusb0", "LIBUSB0", "LibUsb0"):
        got = udi.attached_devices(_entry(spelling), _PRESENT)
        assert [d.has_winusb for d in got] == [True], spelling


# ---------------------------------------------------------------------------
# HALF 2 — what the app tells the user to choose in Zadig
# ---------------------------------------------------------------------------
#
# Rendered text, not source: the question is what a user reads. Every branch of
# the two message functions is walked, in every language ChromIQ ships, and any
# branch that talks about Zadig must not name WinUSB — because in Zadig, WinUSB
# is a row in a dropdown the user is being told to pick from.


def _every_rendered_branch():
    """(text, offers_zadig) for every branch of both message functions."""
    def dev(has_winusb):
        return SimpleNamespace(name=I1PRO, has_winusb=has_winusb)

    out: "list[tuple[str, bool]]" = []
    for wdi in (True, False):
        for devices in ([], [dev(True)], [dev(False)], [dev(True), dev(False)]):
            out.append((sd.usb_installer_text(devices, wdi_available=wdi)[0],
                        False))
    for status in ("launched", "download_page", "failed", None):
        out.append(sd.usb_install_outcome(
            wdi_available=False, ran_ok=False, still_unbound_names=[],
            zadig_status=status, driver_was_missing=True,
            target_names=[I1PRO]))
    for ran_ok in (True, False):
        for unbound in ([], [I1PRO]):
            for missing in (True, False):
                out.append(sd.usb_install_outcome(
                    wdi_available=True, ran_ok=ran_ok,
                    still_unbound_names=unbound, zadig_status=None,
                    driver_was_missing=missing, target_names=[I1PRO]))
    return out


@pytest.mark.parametrize("code", ALL_CODES)
def test_no_zadig_instruction_tells_the_user_to_choose_winusb(code,
                                                              in_language):
    """FOUR PLACES SAID WinUSB, AND FOLLOWING ANY OF THEM BROKE THE INSTRUMENT.

    Zadig's driver box is a dropdown. Naming WinUSB in a sentence whose verb is
    "choose" is an instruction to bind the one driver ArgyllCMS cannot read
    through — and ChromIQ then told the user the driver was installed.
    """
    in_language(code)
    offenders = [t for t, _ in _every_rendered_branch()
                 if "Zadig" in t and "WinUSB" in t]
    assert not offenders, (
        f"[{code}] {len(offenders)} Zadig instruction(s) still name WinUSB as "
        f"a driver to pick: {offenders}")


def _branches_that_put_a_user_in_front_of_zadigs_dropdown():
    """The five, named one at a time rather than matched by phrase.

    A phrase-matched selector is what let two of these hide for months — see
    `tests/test_winusb_never_reaches_a_serial_instrument.py`. Naming them means
    a branch can only leave this list by being deleted from the app.

    Deliberately NOT here: "The driver is already installed… click Open Zadig
    to run the installer again", which opens Zadig but instructs nothing — the
    instruction arrives one window later, in the `launched` branch, which is in
    this list; and "Could not open Zadig or its download page", which gives an
    address and sends nobody to a dropdown.
    """
    undriven = SimpleNamespace(name=I1PRO, has_winusb=False)
    return {
        "the numbered Zadig steps":
            sd.usb_installer_text([undriven], wdi_available=False)[0],
        "Zadig has just been launched":
            sd.usb_install_outcome(
                wdi_available=False, ran_ok=False, still_unbound_names=[],
                zadig_status="launched", driver_was_missing=True,
                target_names=[I1PRO])[0],
        "Zadig must be downloaded first":
            sd.usb_install_outcome(
                wdi_available=False, ran_ok=False, still_unbound_names=[],
                zadig_status="download_page", driver_was_missing=True,
                target_names=[I1PRO])[0],
        "the automatic install failed or was cancelled":
            sd.usb_install_outcome(
                wdi_available=True, ran_ok=False, still_unbound_names=[],
                zadig_status=None, driver_was_missing=True,
                target_names=[I1PRO])[0],
        "the installer finished but the driver did not bind":
            sd.usb_install_outcome(
                wdi_available=True, ran_ok=True, still_unbound_names=[I1PRO],
                zadig_status=None, driver_was_missing=True,
                target_names=[I1PRO])[0],
    }


@pytest.mark.parametrize("code", ALL_CODES)
def test_every_zadig_instruction_names_libusb_win32(code, in_language):
    """The other half: it is not enough to stop saying WinUSB.

    A user standing in front of Zadig's dropdown has to be told which row to
    pick, or they take Zadig's default — which is WinUSB, which is the fault.
    """
    in_language(code)
    silent = [why for why, text
              in _branches_that_put_a_user_in_front_of_zadigs_dropdown().items()
              if "libusb-win32" not in text]
    assert not silent, (
        f"[{code}] {len(silent)} branch(es) send the user to Zadig without "
        f"naming the driver to pick, so they will take Zadig's default "
        f"(WinUSB): {silent}")


def test_the_english_zadig_steps_name_libusb_win32_verbatim():
    """Character for character, in the language the keys are written in."""
    steps, _ = sd.usb_installer_text(
        [SimpleNamespace(name=I1PRO, has_winusb=False)], wdi_available=False)
    assert "3. Select <b>libusb-win32</b> as the driver and click " \
           "<b>Install Driver</b>" in steps


def test_the_cr30_warning_no_longer_names_a_single_driver():
    """It used to say "giving it WinUSB would stop ChromIQ finding it".

    Once step 3 says "choose libusb-win32", a warning phrased against WinUSB
    reads as permission to give the CH340 libusb-win32 — which destroys COM7
    exactly as thoroughly. The warning names the ROW, not a driver.
    """
    warning = sd._cr30_zadig_warning()
    assert "CH340" in warning
    for driver in ("WinUSB", "libusb-win32", "libusbK"):
        assert driver not in warning, (
            f"the CR30 warning names {driver!r}; a user told to pick a "
            "different driver will read that as permission")

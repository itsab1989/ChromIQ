"""Tests for launch_zadig()'s bundled-vs-download-page fallback.

Regression guard for the forum #148275 driver dialog: when the bundled
zadig.exe isn't present (e.g. running from source rather than a CI build),
launch_zadig() must open the Zadig download page instead of silently failing,
so the Settings dialog can tell the user what happened.
"""
from __future__ import annotations

import inspect
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.usb_driver_installer as udi


def _stub_resource_path(monkeypatch, target: Path) -> None:
    monkeypatch.setattr(udi, "resource_path", lambda rel: target)


def test_launch_zadig_runs_bundled_exe(monkeypatch, tmp_path: Path) -> None:
    zadig = tmp_path / "zadig.exe"
    zadig.write_bytes(b"MZ")  # non-empty -> treated as a real binary
    _stub_resource_path(monkeypatch, zadig)

    launched: list[list[str]] = []
    monkeypatch.setattr(
        subprocess, "Popen",
        lambda args, **kw: launched.append(args) or object(),
    )
    # If the bundled exe runs, we must NOT also open a browser.
    import webbrowser

    def _no_browser(url):
        raise AssertionError("browser opened despite bundled zadig.exe")

    monkeypatch.setattr(webbrowser, "open", _no_browser)

    assert udi.launch_zadig() == "launched"
    assert launched and launched[0][0] == str(zadig)


def test_launch_zadig_opens_download_page_when_missing(monkeypatch, tmp_path: Path) -> None:
    _stub_resource_path(monkeypatch, tmp_path / "does_not_exist.exe")

    opened: list[str] = []
    import webbrowser
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url) or True)

    assert udi.launch_zadig() == "download_page"
    assert opened == [udi.ZADIG_URL]


def test_launch_zadig_treats_empty_exe_as_missing(monkeypatch, tmp_path: Path) -> None:
    empty = tmp_path / "zadig.exe"
    empty.write_bytes(b"")  # 0-byte placeholder -> not a usable binary
    _stub_resource_path(monkeypatch, empty)

    import webbrowser
    monkeypatch.setattr(webbrowser, "open", lambda url: True)

    assert udi.launch_zadig() == "download_page"


def test_launch_zadig_failed_when_browser_unavailable(monkeypatch, tmp_path: Path) -> None:
    _stub_resource_path(monkeypatch, tmp_path / "nope.exe")

    import webbrowser
    monkeypatch.setattr(webbrowser, "open", lambda url: False)

    assert udi.launch_zadig() == "failed"


def test_i1pro_family_known(monkeypatch) -> None:
    """i1 Pro family must be in the allowlist so the driver dialog detects it.

    Regression guard for the forum #148275 report ("i1Pro / i1Pro2 not
    recognized"). Per ArgyllCMS 3.5.0 usb/ArgyllCMS.inf the i1 Pro and i1 Pro 2
    share GretagMacbeth 0971:2000, and the i1 Pro 3 / 3+ use X-Rite 0765:6009.
    Keys are lower-case hex to match enumerate_connected()'s registry reads.
    """
    assert ("0971", "2000") in udi.KNOWN_COLORIMETERS
    assert ("0765", "6009") in udi.KNOWN_COLORIMETERS
    # All keys are lower-case hex (the lookup would silently miss otherwise).
    for vid, pid in udi.KNOWN_COLORIMETERS:
        assert vid == vid.lower() and pid == pid.lower(), (vid, pid)


def test_i1pro_2000_matches_registry_combo() -> None:
    """The 0971:2000 key matches what enumerate_connected() parses from a
    'VID_0971&PID_2000' registry combo (the form Windows stores)."""
    combo = "VID_0971&PID_2000"
    parts = combo.upper().split("&")
    vid = parts[0].replace("VID_", "").lower()
    pid = parts[1].replace("PID_", "").lower()
    assert udi.KNOWN_COLORIMETERS.get((vid, pid)) == "GretagMacbeth i1 Pro / i1 Pro 2"


# Devices Argyll 3.5.0's usb/ArgyllCMS.inf actively binds the libusb driver to.
_EXPECTED_PRESENT = {
    ("0971", "2000"),  # i1 Pro / i1 Pro 2
    ("0971", "2007"),  # ColorMunki Photo/Design
    ("0765", "6009"),  # i1 Pro 3 / 3+
    ("0765", "6008"),  # i1 Studio
    ("0765", "6003"),  # ColorMunki Smile
    ("0765", "d094"),  # DTP94
    ("085c", "0100"),  # Spyder 1
    ("085c", "0a0a"),  # SpyderX2
    ("085c", "0a0b"),  # Spyder 2024
    ("04db", "005b"),  # HCFR V3.1
    ("2457", "4000"),  # Image Engineering EX1
}

# Deliberately excluded: inf-commented (5020/600a), HID-only colorimeters that
# must NOT get WinUSB (d0c0/d065/d095), and the prior table's wrong PIDs.
_EXPECTED_ABSENT = {
    ("0765", "5020"),  # Eye-One Display 3 — commented out in the inf
    ("0765", "600a"),  # D123 — commented out in the inf
    ("0765", "d0c0"),  # i1 Studio native HID — Argyll binds 6008 instead
    ("0765", "d065"),  # i1 Display Pro (HID) — must stay on HID, not WinUSB
    ("0765", "d095"),  # ColorMunki Display (HID)
    ("085c", "0c00"),  # prior table's wrong SpyderX2 PID (real is 0a0a)
    ("085c", "0b00"),  # prior table's invented "SpyderX Pro"
}


def test_table_matches_argyll_inf_inclusions() -> None:
    for key in _EXPECTED_PRESENT:
        assert key in udi.KNOWN_COLORIMETERS, f"{key} missing from allowlist"


def test_table_excludes_hid_and_commented_devices() -> None:
    for key in _EXPECTED_ABSENT:
        assert key not in udi.KNOWN_COLORIMETERS, f"{key} should not be in allowlist"


def _dev(vid: str, pid: str, has_winusb: bool) -> udi.UsbDevice:
    return udi.UsbDevice(vid=vid, pid=pid, name=f"{vid}:{pid}", has_winusb=has_winusb)


def test_unbound_targets_flags_device_that_did_not_bind(monkeypatch) -> None:
    """After install, a target still reporting no driver must be flagged.

    Reproduces the i1Studio case: wdi-simple exits 0 but the device (0765:6008)
    is still driverless, so the dialog must treat it as a failure and offer Zadig.
    """
    target = _dev("0765", "6008", has_winusb=False)
    # Re-enumeration still shows it without a WinUSB/libusb0 driver.
    monkeypatch.setattr(udi, "enumerate_connected", lambda: [_dev("0765", "6008", False)])
    assert udi.unbound_targets([target]) == [_dev("0765", "6008", False)]


def test_unbound_targets_empty_when_bind_succeeded(monkeypatch) -> None:
    target = _dev("0765", "6008", has_winusb=False)
    # Re-enumeration now shows the driver bound.
    monkeypatch.setattr(udi, "enumerate_connected", lambda: [_dev("0765", "6008", True)])
    assert udi.unbound_targets([target]) == []


def test_unbound_targets_only_considers_requested_devices(monkeypatch) -> None:
    target = _dev("0765", "6008", has_winusb=False)
    # An unrelated driverless device must not be reported as a failed target.
    monkeypatch.setattr(
        udi, "enumerate_connected",
        lambda: [_dev("0765", "6008", True), _dev("085c", "0a00", False)],
    )
    assert udi.unbound_targets([target]) == []


# ---------------------------------------------------------------------------
# The ghost devices
# ---------------------------------------------------------------------------
#
# `enumerate_connected()` reads HKLM\SYSTEM\CurrentControlSet\Enum\USB, which
# remembers every USB device this machine has ever seen and every port each was
# plugged into. Measured on the ARM64 box 2026-09-04 with no colorimeter
# attached at all, it returned `X-Rite i1 Studio`.
#
# The first fix filtered that in the Preferences dialog. `unbound_targets()` —
# the OTHER caller, and the post-install verification whose entire job is to
# answer "did the driver actually bind?" — went on reading ghosts. It is now
# filtered once, here, at instance granularity, and these tests live beside the
# code that does it rather than beside one of its callers.

I1STUDIO = ("0765", "6008")


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
def test_the_ids_are_read_out_of_a_pnp_instance_id(instance_id, expected) -> None:
    assert udi.usb_ids_in_instance(instance_id) == expected


def test_the_ids_come_back_lower_case_whatever_case_windows_used() -> None:
    """The registry side is lower-cased, so the two sides of the comparison have
    to agree — Windows writes these IDs upper-case."""
    assert udi.usb_ids_in_instance(
        r"usb\vid_1a86&pid_7523\7&3b74c78&0&1") == ("1a86", "7523")


def test_present_usb_instance_ids_says_it_cannot_ask_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(udi, "sys", SimpleNamespace(platform="linux"))
    assert udi.present_usb_instance_ids() is None


def test_present_usb_instance_ids_survives_a_missing_cfgmgr32(monkeypatch) -> None:
    """A ctypes failure must not take the Preferences window down with it."""
    def boom(*_a, **_kw):
        raise OSError("cfgmgr32 is not here")

    monkeypatch.setattr(udi, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(udi.ctypes, "WinDLL", boom, raising=False)
    assert udi.present_usb_instance_ids() is None


def test_present_usb_ids_is_derived_from_the_instance_list(monkeypatch) -> None:
    """One cfgmgr32 call in this project's USB code, not two that can disagree."""
    monkeypatch.setattr(udi, "present_usb_instance_ids", lambda: {
        r"USB\VID_0765&PID_6008\7&3B74C78&0&1",
        r"USB\VID_0E0F&PID_000B&MI_00\7&2A0C73B9&0&0000",
        r"USB\ROOT_HUB30\5&32007B01&0&0",          # no VID: dropped
    })
    assert udi.present_usb_ids() == {("0765", "6008"), ("0e0f", "000b")}


def test_present_usb_ids_passes_could_not_ask_straight_through(monkeypatch) -> None:
    monkeypatch.setattr(udi, "present_usb_instance_ids", lambda: None)
    assert udi.present_usb_ids() is None


# --- GUARD 1: a device the registry remembers and the machine no longer has --

def _entry(vid: str, pid: str, *instances):
    """One `Enum\\USB` combo key, as `_registry_usb_entries()` hands it over."""
    return (f"VID_{vid.upper()}&PID_{pid.upper()}", list(instances))


def _present(vid: str, pid: str, instance: str) -> str:
    return (f"USB\\VID_{vid}&PID_{pid}\\{instance}").upper()


def test_a_remembered_device_that_is_not_attached_is_dropped() -> None:
    entries = [
        _entry("0765", "6008", ("7&3b74c78&0&1", "libusb0")),   # ghost
        _entry("0971", "2000", ("7&2a0c73b9&0&2", "")),         # attached
    ]
    present = {_present("0971", "2000", "7&2a0c73b9&0&2")}
    assert [(d.vid, d.pid) for d in udi.attached_devices(entries, present)] == [
        ("0971", "2000")]


def test_an_attached_device_survives_the_filter() -> None:
    entries = [_entry("0765", "6008", ("7&3b74c78&0&1", "libusb0"))]
    present = {_present("0765", "6008", "7&3b74c78&0&1")}
    kept = udi.attached_devices(entries, present)
    assert [d.name for d in kept] == ["X-Rite i1 Studio"]


def test_nothing_present_means_nothing_reported() -> None:
    entries = [_entry("0765", "6008", ("7&3b74c78&0&1", "libusb0"))]
    assert udi.attached_devices(entries, set()) == []


def test_when_windows_cannot_be_asked_everything_is_shown() -> None:
    """The failure direction is chosen deliberately: a ghost is a lie the user
    can see and ignore, a filtered-out real instrument is a feature that
    silently refuses to help. Only the first is survivable."""
    entries = [
        _entry("0765", "6008", ("7&3b74c78&0&1", "libusb0")),
        _entry("0971", "2000", ("7&2a0c73b9&0&2", "")),
    ]
    assert [(d.vid, d.pid) for d in udi.attached_devices(entries, None)] == [
        ("0765", "6008"), ("0971", "2000")]


def test_the_comparison_is_case_insensitive_on_both_sides() -> None:
    """Windows writes instance IDs upper-case; the registry key names come back
    in whatever case they were created with."""
    entries = [("vid_0765&pid_6008", [("7&3b74c78&0&1", "WinUSB")])]
    present = {r"USB\VID_0765&PID_6008\7&3B74C78&0&1"}
    got = udi.attached_devices(entries, present)
    assert [(d.vid, d.pid, d.has_winusb) for d in got] == [("0765", "6008", True)]


def test_devices_that_are_not_known_colorimeters_are_still_ignored() -> None:
    """Presence is a second filter, not a replacement for the allowlist."""
    entries = [_entry("1a86", "7523", ("7&3b74c78&0&1", "CH341SER_A64"))]
    present = {_present("1a86", "7523", "7&3b74c78&0&1")}
    assert udi.attached_devices(entries, present) == []


# --- GUARD 2: a remembered INSTANCE of a device that IS attached -------------
#
# This is the one that fools the verification. The i1 Studio on this machine
# really does hold two instance keys — two USB ports it has been plugged into —
# and only one of them is present. `has_winusb` used to be OR-ed over both.

def test_a_ghost_instance_does_not_lend_its_driver_to_a_live_one() -> None:
    """Replug into another port: the new node is driverless, the old one still
    says libusb0. If the stale one counts, wdi-simple's "exit 0" is confirmed by
    a device that never bound and the user is told an install succeeded."""
    entries = [_entry(
        "0765", "6008",
        ("7&3b74c78&0&2", "libusb0"),      # ghost: the old port
        ("7&3b74c78&0&1", ""),             # live: no driver bound
    )]
    present = {_present("0765", "6008", "7&3b74c78&0&1")}
    got = udi.attached_devices(entries, present)
    assert [d.has_winusb for d in got] == [False], (
        "a ghost instance's stale Service was counted as the live device's driver")


def test_the_live_instance_is_believed_when_it_does_have_the_driver() -> None:
    entries = [_entry(
        "0765", "6008",
        ("7&3b74c78&0&2", ""),             # ghost: the old port, driverless
        ("7&3b74c78&0&1", "libusb0"),      # live: bound
    )]
    present = {_present("0765", "6008", "7&3b74c78&0&1")}
    assert [d.has_winusb for d in udi.attached_devices(entries, present)] == [True]


def test_a_present_device_whose_instances_do_not_match_is_kept() -> None:
    """cfgmgr32 says this vid:pid is here; only the node is unrecognised. Keeping
    it costs a possibly-stale driver flag, dropping it hides a real instrument —
    and the second is the unsurvivable direction."""
    entries = [_entry("0765", "6008", ("some&unexpected&form", "libusb0"))]
    present = {_present("0765", "6008", "7&3b74c78&0&1")}
    got = udi.attached_devices(entries, present)
    assert [(d.vid, d.pid, d.has_winusb) for d in got] == [("0765", "6008", True)]


def test_composite_children_collapse_to_one_device() -> None:
    entries = [
        ("VID_0765&PID_6008&MI_00", [("7&3b74c78&0&0000", "libusb0")]),
        ("VID_0765&PID_6008", [("7&3b74c78&0&1", "libusb0")]),
    ]
    present = {r"USB\VID_0765&PID_6008&MI_00\7&3B74C78&0&0000",
               r"USB\VID_0765&PID_6008\7&3B74C78&0&1"}
    assert len(udi.attached_devices(entries, present)) == 1


# --- and the whole point: the ghost never reaches the verification -----------

def _win32_registry(monkeypatch, entries, present) -> None:
    monkeypatch.setattr(udi, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(udi, "_registry_usb_entries", lambda: entries)
    monkeypatch.setattr(udi, "present_usb_instance_ids", lambda: present)


def test_a_ghost_never_reaches_unbound_targets(monkeypatch) -> None:
    """THE BUG. `unbound_targets()` is the post-install verification — it must
    not report "the driver did not bind" about hardware that is not attached."""
    ghost = _dev("0765", "6008", has_winusb=False)
    _win32_registry(
        monkeypatch,
        [_entry("0765", "6008", ("7&3b74c78&0&1", ""))],
        set(),                                   # nothing is attached
    )
    assert udi.enumerate_connected() == []
    assert udi.unbound_targets([ghost]) == []


def test_a_genuinely_present_device_still_reaches_unbound_targets(monkeypatch) -> None:
    """The other half of the guard: the filter must not swallow a real failure."""
    target = _dev("0765", "6008", has_winusb=False)
    _win32_registry(
        monkeypatch,
        [_entry("0765", "6008", ("7&3b74c78&0&1", ""))],
        {_present("0765", "6008", "7&3b74c78&0&1")},
    )
    assert [(d.vid, d.pid) for d in udi.unbound_targets([target])] == [("0765", "6008")]


def test_a_ghost_instance_cannot_confirm_an_install_that_did_not_happen(
        monkeypatch) -> None:
    """The false-SUCCESS direction, end to end: the live node is driverless, the
    ghost node still says libusb0, and `unbound_targets()` must still say the
    install did not bind."""
    target = _dev("0765", "6008", has_winusb=False)
    _win32_registry(
        monkeypatch,
        [_entry("0765", "6008",
                ("7&3b74c78&0&2", "libusb0"),    # ghost
                ("7&3b74c78&0&1", ""))],         # live, unbound
        {_present("0765", "6008", "7&3b74c78&0&1")},
    )
    assert [(d.vid, d.pid) for d in udi.unbound_targets([target])] == [("0765", "6008")]


def test_enumerate_connected_is_empty_off_windows(monkeypatch) -> None:
    """The registry and cfgmgr32 do not exist there; importing must still work."""
    monkeypatch.setattr(udi, "sys", SimpleNamespace(platform="darwin"))
    assert udi.enumerate_connected() == []


def test_presence_uses_the_cfgmgr32_present_filter() -> None:
    """The constant's VALUE is the guard, and no stubbed test can reach it.

    Every test above hands `attached_devices()` a presence set directly, so a
    zero in either flag would leave them all green while the real call went back
    to returning phantoms alongside the live device. Asserted from the source,
    the same way `tests/test_ch34x_driver.py` pins the serial half.
    """
    module = inspect.getsource(udi)
    assert "_CM_GETIDLIST_FILTER_PRESENT = 0x00000100" in module
    assert "_CM_GETIDLIST_FILTER_ENUMERATOR = 0x00000001" in module

    fn = inspect.getsource(udi.present_usb_instance_ids)
    assert "_CM_GETIDLIST_FILTER_ENUMERATOR | _CM_GETIDLIST_FILTER_PRESENT" in fn
    assert "CM_Get_Device_ID_ListW" in fn


def test_the_registry_read_does_no_filtering_of_its_own() -> None:
    """One filter, in one place. `_registry_usb_entries()` reports what is
    REMEMBERED; if it started deciding what is present there would be two
    answers to the same question and they could drift apart."""
    src = inspect.getsource(udi._registry_usb_entries)
    for forbidden in ("present", "PRESENT", "cfgmgr"):
        assert forbidden not in src.split('"""')[2], (
            f"{forbidden} appears in the registry read; presence is "
            "attached_devices()'s job")

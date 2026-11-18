"""Review WIN2 of the i1iO table's Windows driver help (2026-11-18): the fixes, pinned.

* F-M1: a USB hub whose chip carries an instrument maker's vendor id (WCH 1A86:8091 in very many
  cheap hubs and docks, Microchip 04D8, or X-Rite's own 0971) is a hub, not "another measuring
  instrument": the cfgmgr32 list marks it from the registry (a hub driver's service, or a
  hub-class compatible id), as the libusb route (bDeviceClass 9) and macOS always did.
* F-M2: on Windows, a table that is not connected gets "ChromIQ did not find the table", not an
  install offer that leads into a window listing no table.
* F-S1: the x64 build on a Windows for ARM computer is refused BEFORE the READY_TO_OPEN question,
  whatever the drivers' states.
* N1 / plant F7a: cfgmgr32's return codes are honoured (a faked cfgmgr32, so this runs off
  Windows too), and a list that grew between the two calls is asked for again.

No hardware, no registry, no driver: every Windows path runs with the platform and the Windows
libraries faked.
"""
from __future__ import annotations

import ctypes
from types import SimpleNamespace

import pytest

import core.usb_driver_installer as udi
from tests.i1io_table import job_harness as H
from workflow.i1io.table import job as J
from workflow.i1io.table import usb_system as us

PRO_ID = "USB\\VID_0971&PID_2000\\6&1A2B3C&0&1"
TABLE_ID = "USB\\VID_0971&PID_2004\\6&777&0&2"
WCH_HUB = "USB\\VID_1A86&PID_8091\\5&ABC&0&3"
MICROCHIP_HUB = "USB\\VID_04D8&PID_0B10\\5&DEF&0&4"
XRITE_HUB = "USB\\VID_0971&PID_5555\\5&123&0&5"


# ---- F-M1: hubs ------------------------------------------------------------------------------

@pytest.mark.parametrize("hub", [WCH_HUB, MICROCHIP_HUB, XRITE_HUB])
def test_a_hub_with_an_instrument_vendor_id_is_not_another_instrument(hub):
    devices = us.list_devices("windows", instance_ids={PRO_ID, TABLE_ID, hub}, hub_ids={hub})
    assert us.instrument_check(devices).state == "ok"
    assert [d["hub"] for d in devices if d["vid"] != 0x0971 or d["pid"] not in (0x2000, 0x2004)] \
        == [True]


def test_the_hub_flag_is_matched_whatever_the_case():
    devices = us.list_devices("windows", instance_ids={PRO_ID, TABLE_ID, WCH_HUB},
                              hub_ids={WCH_HUB.lower()})
    assert us.instrument_check(devices).state == "ok"


def test_without_a_hub_flag_nothing_is_marked_a_hub_as_before():
    """The registry could not be read: no hub is marked (the old behaviour), and a real second
    instrument is still counted."""
    devices = us.list_devices("windows", instance_ids={PRO_ID, TABLE_ID, WCH_HUB}, hub_ids=None)
    assert us.instrument_check(devices).state == "other_instrument"
    devices = us.list_devices("windows", instance_ids={PRO_ID, TABLE_ID,
                                                       "USB\\VID_0765&PID_6008\\5&1&0&5"},
                              hub_ids={WCH_HUB})
    assert us.instrument_check(devices).state == "other_instrument"


def test_the_windows_route_asks_the_registry_which_instances_are_hubs(monkeypatch):
    monkeypatch.setattr(udi, "present_usb_instance_ids", lambda: {PRO_ID, TABLE_ID, WCH_HUB})
    monkeypatch.setattr(udi, "usb_hub_instance_ids", lambda: {WCH_HUB})
    assert us.instrument_now("win32").state == "ok"
    monkeypatch.setattr(udi, "usb_hub_instance_ids", lambda: None)
    assert us.instrument_now("win32").state == "other_instrument"

    def boom():
        raise OSError("registry")
    monkeypatch.setattr(udi, "usb_hub_instance_ids", boom)
    assert us.instrument_now("win32").state == "other_instrument"     # cannot tell = not a hub


def test_a_wch_hub_on_a_windows_pc_does_not_refuse_start(monkeypatch):
    """The whole Windows route, from cfgmgr32's list and the registry (both faked) to the
    instrument check: the review's `wch_hub` case, i1Pro 2 + table + a 1A86:8091 hub."""
    monkeypatch.setattr(udi, "present_usb_instance_ids", lambda: {PRO_ID, TABLE_ID, WCH_HUB})
    monkeypatch.setitem(__import__("sys").modules, "winreg", _FakeWinreg({
        "VID_1A86&PID_8091": {"5&abc&0&3": {"Service": "USBHUB3",
                                            "CompatibleIDs": ["USB\\Class_09"]}},
        "VID_0971&PID_2000": {"6&1a2b3c&0&1": {"Service": "libusb0"}},
        "VID_0971&PID_2004": {"6&777&0&2": {"Service": "libusb0"}}}))
    monkeypatch.setattr(udi, "sys", SimpleNamespace(platform="win32"))
    assert us.instrument_now("win32").state == "ok"


@pytest.mark.parametrize("service,compat,hub", [
    ("usbhub", None, True),
    ("USBHUB3", None, True),
    ("UsbHub3", [], True),
    (" usbhub ", None, True),
    ("iusb3hub", None, True),
    ("", ["USB\\Class_09&SubClass_00&Prot_02", "USB\\Class_09&SubClass_00", "USB\\Class_09"],
     True),
    ("vendorhub", ["USB\\CLASS_09"], True),                 # any hub driver, by its class
    ("libusb0", ["USB\\Class_ff&SubClass_00", "USB\\Class_ff"], False),
    ("WinUSB", None, False),
    ("usbccgp", ["USB\\DevClass_00&SubClass_00", "USB\\COMPOSITE"], False),
    ("", None, False),
    (None, None, False),
])
def test_a_hub_entry_is_named_by_its_service_or_its_class(service, compat, hub):
    assert udi.is_hub_entry(service, compat) is hub


class _FakeWinreg:
    """`winreg` as far as `usb_hub_instance_ids` uses it: Enum\\USB with values per instance."""
    HKEY_LOCAL_MACHINE = "HKLM"

    def __init__(self, tree):
        self.tree = tree        # {combo: {instance: {value: data}}}

    def OpenKey(self, base, sub):
        if base == "HKLM":
            return ("root",)
        if base == ("root",):
            if sub not in self.tree:
                raise OSError(sub)
            return ("combo", sub)
        if base[0] == "combo":
            return ("inst", base[1], sub)
        raise OSError(sub)

    def EnumKey(self, key, i):
        names = (list(self.tree) if key == ("root",) else list(self.tree[key[1]]))
        if i >= len(names):
            raise OSError(i)
        return names[i]

    def QueryValueEx(self, key, name):
        values = self.tree[key[1]][key[2]]
        if name not in values:
            raise OSError(name)
        return values[name], 7


def test_the_registry_walk_names_the_hubs(monkeypatch):
    fake = _FakeWinreg({
        "VID_1A86&PID_8091": {"5&abc&0&3": {"Service": "USBHUB3",
                                            "CompatibleIDs": ["USB\\Class_09&SubClass_00"]}},
        "VID_04D8&PID_0B10": {"5&def&0&4": {"CompatibleIDs": ["USB\\Class_09"]}},
        "VID_0971&PID_2000": {"6&1a2b3c&0&1": {"Service": "libusb0"}},
        "VID_0971&PID_2004": {"6&777&0&2": {}},
    })
    monkeypatch.setitem(__import__("sys").modules, "winreg", fake)
    monkeypatch.setattr(udi, "sys", SimpleNamespace(platform="win32"))
    assert udi.usb_hub_instance_ids() == {WCH_HUB, MICROCHIP_HUB}


def test_the_hub_walk_says_cannot_tell_off_windows_or_without_the_registry(monkeypatch):
    monkeypatch.setattr(udi, "sys", SimpleNamespace(platform="darwin"))
    assert udi.usb_hub_instance_ids() is None

    class _NoKey(_FakeWinreg):
        def OpenKey(self, base, sub):
            raise OSError("no Enum\\USB")
    monkeypatch.setitem(__import__("sys").modules, "winreg", _NoKey({}))
    monkeypatch.setattr(udi, "sys", SimpleNamespace(platform="win32"))
    assert udi.usb_hub_instance_ids() is None


# ---- F-M2: no table attached -----------------------------------------------------------------

def _pf(table, detail=None, pro="libusb0", arm64=False):
    return us.Preflight("windows", {}, us.Check("ok"), us.Check("cannot_tell"), None,
                        us.Check(table, detail or {}), us.Check(pro), arm64)


@pytest.mark.parametrize("detail", [{"seen": False, "present": False},
                                    {"seen": True, "present": False}])
def test_a_table_that_is_not_connected_gets_the_table_not_found_message(detail):
    opened = []
    job, sim, _t = H.make_job(preflight=_pf("none", detail))
    job._open_transport = lambda: opened.append(1)
    person = H.Person(job, sim)
    r = person.drive(job.open())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "usb_open_refused")
    assert r.detail["message_id"] == "M-I1IO-DRIVE-TABLE-NOT-FOUND"
    assert person.asked == [] and opened == [] and sim.received == []


def test_the_window_words_it_as_the_table_not_found():
    from workflow import measurement_messages as M
    assert M.I1IO_DRIVE_USB_MESSAGE["M-I1IO-DRIVE-TABLE-NOT-FOUND"] \
        is M.M_I1IO_DRIVE_TABLE_NOT_FOUND


def test_a_connected_table_without_the_driver_is_still_offered_the_install():
    job, sim, _t = H.make_job(preflight=_pf("none", {"seen": True, "present": True}))
    r = H.Person(job, sim).drive(job.open())
    assert r.reason == "driver_not_installed_for_table"


def test_the_table_state_reads_not_connected_from_the_registry_and_cfgmgr32():
    entries = [("VID_0971&PID_2004", [("6&777&0&2", "")])]
    assert udi.table_driver_state([], set()) == ("none", {"seen": False, "present": False})
    assert udi.table_driver_state(entries, set()) == ("none", {"seen": True, "present": False})
    assert udi.table_driver_state(entries, {TABLE_ID})[0] == "none"
    assert udi.table_driver_state(entries, {TABLE_ID})[1].get("present") is not False


def test_a_present_table_whose_instance_did_not_match_is_never_called_not_connected():
    """Review WIN2, N8: cfgmgr32 lists the table's vid:pid, but under an instance id the registry
    keys do not rebuild; presence is not in doubt (as in `attached_devices`)."""
    entries = [("VID_0971&PID_2004", [("6&777&0&2", "libusb0")])]
    other = "USB\\VID_0971&PID_2004\\7&999&0&9"
    assert udi.table_driver_state(entries, {other}) == ("libusb0", {"service": "libusb0"})
    state, detail = udi.table_driver_state([("VID_0971&PID_2004", [("6&777&0&2", "")])],
                                           {other})
    assert state == "none" and detail.get("present") is not False


# ---- F-S1: the x64 build on an ARM PC, refused before the first question ---------------------

@pytest.mark.parametrize("table,pro", [("libusb0", "libusb0"), ("none", "libusb0"),
                                       ("libusb0", "none"), ("vendor_driver", "none"),
                                       ("cannot_tell", "cannot_tell")])
def test_the_x64_build_on_an_arm_pc_is_refused_before_ready_to_open(table, pro):
    opened = []
    job, sim, _t = H.make_job(preflight=_pf(table, pro=pro, arm64=True))
    job._open_transport = lambda: opened.append(1)
    person = H.Person(job, sim)
    r = person.drive(job.open())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "usb_open_refused")
    assert r.detail["message_id"] == "M-I1IO-DRIVE-USB-NOT-ON-THIS-SYSTEM"
    assert not any(a[1] == J.Confirm.READY_TO_OPEN for a in person.asked)
    assert opened == [] and sim.received == []


def test_the_x64_on_arm_refusal_does_not_reach_macos_or_linux():
    for system in ("macos", "linux"):
        pf = us.Preflight(system, {}, us.Check("ok"), us.Check("cannot_tell"), None,
                          us.Check("not_applicable"), us.Check("not_applicable"), True)
        job, sim, _t = H.make_job(preflight=pf)
        assert H.Person(job, sim).drive(job.open()).ok


# ---- N1 / plant F7a: cfgmgr32's return codes, with a faked cfgmgr32 -------------------------

class _FakeCfgmgr32:
    """`CM_Get_Device_ID_List_SizeW` / `CM_Get_Device_ID_ListW` as Windows answers them: the
    size in characters of a double-NUL-terminated list, then the list."""

    def __init__(self, ids, size_codes=(0,), list_codes=(0,), grow_after_size=0):
        self.ids = list(ids)
        self.size_codes, self.list_codes = list(size_codes), list(list_codes)
        self.size_calls = self.list_calls = 0
        self.grow_after_size = grow_after_size

    def _text(self):
        return "".join(i + "\0" for i in self.ids) + "\0"

    def CM_Get_Device_ID_List_SizeW(self, size_ref, enumerator, flags):
        code = self.size_codes[min(self.size_calls, len(self.size_codes) - 1)]
        self.size_calls += 1
        size_ref._obj.value = len(self._text())
        if self.grow_after_size:
            self.grow_after_size -= 1
            self.ids.append("USB\\VID_046D&PID_C52B\\5&9&0&%d" % self.size_calls)
        return code

    def CM_Get_Device_ID_ListW(self, enumerator, buf, size, flags):
        code = self.list_codes[min(self.list_calls, len(self.list_codes) - 1)]
        self.list_calls += 1
        text = self._text()
        if len(text) > size.value:
            return 0x1A                                   # CR_BUFFER_SMALL
        if code == 0:
            buf[:len(text)] = text
        return code


def _with_cfgmgr32(monkeypatch, fake):
    monkeypatch.setattr(udi, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(udi.ctypes, "WinDLL", lambda name: fake, raising=False)


def test_the_faked_cfgmgr32_gives_the_present_list(monkeypatch):
    _with_cfgmgr32(monkeypatch, _FakeCfgmgr32([PRO_ID.lower(), TABLE_ID]))
    assert udi.present_usb_instance_ids() == {PRO_ID, TABLE_ID}


@pytest.mark.parametrize("size_codes,list_codes", [
    ((0x13,), (0,)),          # CR_FAILURE on the size call
    ((0,), (0x13,)),          # CR_FAILURE on the list call
    ((0,), (0x05,)),          # CR_INVALID_POINTER (any other code)
    ((0,), (0x1A,)),          # CR_BUFFER_SMALL every time: gives up, does not loop for ever
])
def test_a_cfgmgr32_failure_is_cannot_tell_not_a_list(monkeypatch, size_codes, list_codes):
    """Plant F7a of review WIN2 (the return code ignored) survived every test, because the
    ctypes path never ran off Windows. With a faked cfgmgr32 it runs here."""
    fake = _FakeCfgmgr32([PRO_ID, TABLE_ID], size_codes, list_codes)
    _with_cfgmgr32(monkeypatch, fake)
    assert udi.present_usb_instance_ids() is None
    assert fake.list_calls <= 3


def test_a_device_plugged_in_between_the_two_calls_is_asked_again(monkeypatch):
    """N1: a device arriving between the size call and the list call makes the list longer
    than the buffer (CR_BUFFER_SMALL); the list is asked for again, not given up on."""
    fake = _FakeCfgmgr32([PRO_ID, TABLE_ID], grow_after_size=1)
    _with_cfgmgr32(monkeypatch, fake)
    got = udi.present_usb_instance_ids()
    assert got is not None and {PRO_ID, TABLE_ID} <= got and len(got) == 3
    assert fake.size_calls == 2 and fake.list_calls == 2


def test_the_fake_speaks_ctypes_like_windows():
    """The fake reads the size through `byref(...)._obj` and writes into a real unicode buffer,
    as the real call does; a guard that the test above exercises the module's own ctypes."""
    size = ctypes.c_ulong(0)
    fake = _FakeCfgmgr32(["A"])
    assert fake.CM_Get_Device_ID_List_SizeW(ctypes.byref(size), None, None) == 0
    assert size.value == 3
    buf = ctypes.create_unicode_buffer(size.value)
    assert fake.CM_Get_Device_ID_ListW(None, buf, size, None) == 0
    assert buf[:size.value] == "A\0\0"


# ---- N4 / N5: the self-test's docstring and two old drivers -----------------------------------

def test_the_selftest_docstring_says_what_usb_get_version_opens():
    """N4: libusb-win32's usb_get_version opens the first libusb0 device object it finds; the
    docstring may not say that nothing is opened."""
    import core.usb_library as ul
    doc = " ".join(ul.libusb0_selftest_field.__doc__.split())
    assert "no device is listed or opened" not in doc
    assert "libusb0-NNNN" in doc and "GET_VERSION" in doc and "CHROMIQ_SELFTEST=1" in doc


@pytest.mark.parametrize("script", ["scripts/drive_a10_libusb_only.py",
                                    "scripts/drive_a11_certificate_text.py"])
def test_the_old_drivers_fake_the_list_as_the_window_now_calls_it(script):
    """N5: with the Beta on, the window calls `enumerate_connected(include_table=True)`; a fake
    that takes no arguments raises TypeError there."""
    import ast
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / script).read_text(encoding="utf-8")
    fakes = [node.value for node in ast.walk(ast.parse(src))
             if isinstance(node, ast.Assign) and isinstance(node.value, ast.Lambda)
             and any(isinstance(t, ast.Attribute) and t.attr == "enumerate_connected"
                     for t in node.targets)]
    assert fakes
    for fake in fakes:
        assert fake.args.kwarg is not None, script


# ---- F-S2 / F-S3: the texts say what is not tried, and Windows 10/11's extra step -------------

def test_the_x64_on_arm_message_says_what_nobody_has_tried():
    """F-S3: neither the ARM64 build's table install nor its opening has been tried; the text
    may not state either as fact, and says so in the way the way back does."""
    from workflow import measurement_messages as M
    msg = M.M_I1IO_DRIVE_USB_NOT_ON_THIS_SYSTEM
    assert not msg.approved and msg.id in M.PROPOSED
    _t, body = msg.render()
    flat = " ".join(body.split())
    assert "ChromIQ has not yet tried either version with a table on an ARM computer" in flat
    assert "It reaches the table through the same driver" not in flat
    assert "can install that driver for the table" not in flat
    assert "—" not in body


def test_the_way_back_names_the_browse_step_without_claiming_it():
    """F-S2 (not verified on a real Windows): Windows 10 and 11 may ask "Browse my computer for
    drivers" before the pick-from-a-list choice; the text is right whether or not it asks, and
    says the step is not the guide's."""
    from ui.dialogs import settings_dialog as sd
    window = sd.usb_table_text([udi.TableUsbDevice("0971", "2004", "X-Rite i1iO 2 table", False)],
                               button="Install Driver for the Table")
    flat = " ".join(window.split())
    assert ("If Windows asks how you want to search for drivers before it offers the choice to "
            "pick from a list, choose “Browse my computer for drivers” first") in flat
    assert "that step is not in the guide" in flat
    assert flat.index("Browse my computer") > flat.index("let me pick from a list")

"""Build step 6: the table is opened ONLY through ChromIQ's own USB route, on every system, and
the per-system instrument / holder / driver checks (recorded answers; no device, no hardware).

macOS / Linux: the bundled libusb-1.0 (core.usb_library.backend). Windows (owner's ruling of
2026-11-17): libusb-win32's driver, installed for the table only on the person's explicit choice,
through pyusb's libusb0 backend with the driver package's own libusb0.dll by full path. The
Windows route is UNTESTED ON REAL WINDOWS HARDWARE; these tests pin its logic only."""
from __future__ import annotations

import sys
import types

import pytest

import core.usb_library as ul
from tests.i1io_table import job_harness as H
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl
from workflow.i1io.table import usb_system as us


# ---- a fake table device: the recorded descriptors, records every call ---------------------

class _Ep:
    def __init__(self, addr):
        self.bEndpointAddress, self.bmAttributes, self.wMaxPacketSize = addr, 2, 64


class _Intf:
    bInterfaceClass = bInterfaceSubClass = bInterfaceProtocol = 0xFF

    def endpoints(self):
        return [_Ep(0x02), _Ep(0x81)]


class FakeDev:
    idVendor, idProduct, bcdDevice, bDeviceClass = 0x0971, 0x2004, 0x0400, 0

    def __init__(self, fail_at=None, exc=None):
        self.calls, self.writes = [], []
        self.fail_at, self.exc = fail_at, exc

    def __getitem__(self, i):
        return [_Intf()]

    def _maybe(self, what):
        self.calls.append(what)
        if what == self.fail_at:
            raise self.exc

    def get_active_configuration(self):
        self._maybe("get_active_configuration")

    def set_configuration(self):
        self._maybe("set_configuration")

    def ctrl_transfer(self, *a):
        self._maybe("ctrl_transfer")

    def write(self, ep, data, timeout):
        self.writes.append(bytes(data))
        return len(data)


class FakeUtil:
    def __init__(self, dev):
        self.dev = dev

    def claim_interface(self, dev, i):
        dev._maybe("claim_interface")

    def release_interface(self, dev, i):
        dev.calls.append("release")

    def dispose_resources(self, dev):
        dev.calls.append("dispose")


def _patch_usb(monkeypatch, devs, find_exc=None):
    import usb.core
    import usb.util
    seen = {}

    def find(find_all=False, idVendor=None, idProduct=None, backend=None, **kw):
        seen["backend"] = backend
        if find_exc is not None:
            raise find_exc
        return iter(devs)
    monkeypatch.setattr(usb.core, "find", find)
    util = FakeUtil(devs[0] if devs else None)
    for name in ("claim_interface", "release_interface", "dispose_resources"):
        monkeypatch.setattr(usb.util, name, getattr(util, name))
    return seen


BUNDLED = object()


@pytest.fixture
def bundled(monkeypatch):
    """core.usb_library as it is (the bundled library must load) but with the backend call
    recorded: the only route to a backend."""
    calls = []
    real = ul.backend

    def backend():
        calls.append("bundled")
        return BUNDLED
    monkeypatch.setattr(ul, "backend", backend)
    return calls


# (1)
def test_the_drive_never_reaches_pyusbs_default_search(monkeypatch, bundled):
    import ctypes.util

    import usb.backend.libusb1 as l1
    asked = []

    def get_backend(find_library=None):
        asked.append(find_library)
        raise AssertionError("pyusb's own search must never run")
    monkeypatch.setattr(l1, "get_backend", get_backend)
    monkeypatch.setattr(ctypes.util, "find_library",
                        lambda name: (_ for _ in ()).throw(AssertionError("system search")))
    dev = FakeDev()
    seen = _patch_usb(monkeypatch, [dev])
    t = tbl.open_table("darwin")
    assert isinstance(t, tbl.FtdiUsb) and seen["backend"] is BUNDLED
    assert bundled == ["bundled"] and asked == []
    assert dev.writes == []                       # nothing sent: only the FTDI set-up
    assert dev.calls.count("ctrl_transfer") == 5


# (2)
def test_homebrews_libusb_is_never_loaded(monkeypatch):
    """The tester's Homebrew paths and its default-search helper are gone from the app's module,
    and the backend ChromIQ asks for is built on the bundled file only."""
    assert not hasattr(tbl, "LIBUSB_PATHS") and not hasattr(tbl, "libusb_backend")
    src = (tbl.__file__ and open(tbl.__file__, encoding="utf-8").read())
    assert "/opt/homebrew" not in src and "/usr/local/lib" not in src
    import usb.backend.libusb1 as l1
    got = []
    monkeypatch.setattr(l1, "get_backend", lambda find_library=None: got.append(
        find_library("usb-1.0")) or "be")
    monkeypatch.setattr(ul, "library_path", lambda: ul.Path("/bundled/libusb-1.0.dylib"))
    monkeypatch.setattr(ul, "bundled_on_this_platform", lambda: True)
    assert ul.backend() == "be" and got == ["/bundled/libusb-1.0.dylib"]


# (3)
@pytest.mark.parametrize("system", ["darwin", "linux", "win32"])
def test_open_table_runs_on_every_system(monkeypatch, bundled, system):
    import core.usb_driver_installer as inst
    assert not hasattr(tbl, "NOT_A_MAC")
    monkeypatch.setattr(inst, "table_driver_state_now", lambda: ("libusb0", {}))
    monkeypatch.setattr(ul, "table_backend", lambda s=None, dll_path=None: ul.TableBackend(
        BUNDLED, "libusb0" if s == "win32" else "libusb1"))
    dev = FakeDev()
    _patch_usb(monkeypatch, [dev])
    t = tbl.open_table(system)
    assert isinstance(t, tbl.FtdiUsb)
    assert t.backend_kind == ("libusb0" if system == "win32" else "libusb1")


def _usb_error(code, errno=None):
    import usb.core
    return usb.core.USBError("x", code, errno)


# (4)
@pytest.mark.parametrize("where", ["find", "claim_interface", "set_configuration",
                                   "ctrl_transfer"])
@pytest.mark.parametrize("system,kind,code", [
    ("darwin", "libusb1", -3), ("darwin", "libusb1", -4), ("darwin", "libusb1", -5),
    ("darwin", "libusb1", -6), ("darwin", "libusb1", -12), ("darwin", "libusb1", -99),
    ("linux", "libusb1", -3), ("linux", "libusb1", -6), ("linux", "libusb1", -4),
    ("win32", "libusb0", -13), ("win32", "libusb0", -16), ("win32", "libusb0", -19),
    ("win32", "libusb0", -2), ("win32", "libusb0", -22)])
def test_every_open_failure_is_said(monkeypatch, bundled, where, system, kind, code):
    import core.usb_driver_installer as inst
    monkeypatch.setattr(inst, "table_driver_state_now", lambda: ("libusb0", {}))
    monkeypatch.setattr(ul, "table_backend", lambda s=None, dll_path=None: ul.TableBackend(
        BUNDLED, kind))
    exc = _usb_error(code)
    if where == "find":
        dev = FakeDev()
        _patch_usb(monkeypatch, [dev], find_exc=exc)
    else:
        dev = FakeDev(fail_at=where, exc=exc)
        if where == "set_configuration":
            dev.fail_at = "get_active_configuration"
            dev.exc = _usb_error(code)
            dev.exc.args = ("Configuration not set",)
            dev.exc.strerror = "Configuration not set"
            orig = dev._maybe

            def maybe(what, orig=orig):
                if what == "set_configuration":
                    raise _usb_error(code)
                if what == "get_active_configuration":
                    import usb.core
                    raise usb.core.USBError("Configuration not set", None)
                orig(what)
            dev._maybe = maybe
        _patch_usb(monkeypatch, [dev])
    with pytest.raises(tbl.NotAvailable) as e:
        tbl.open_table(system)
    want = ul.open_failure(_usb_error(code), system, kind)
    assert e.value.message_id == want and want.startswith("M-I1IO-DRIVE-")
    assert dev.writes == []
    if where != "find":
        assert "dispose" in dev.calls             # closed again, nothing kept open


def test_the_libusb0_codes_are_named_like_libusb1s():
    assert ul.open_failure(_usb_error(-13), "win32", "libusb0") == \
        "M-I1IO-DRIVE-USB-WINDOWS-DRIVER"
    assert ul.open_failure(_usb_error(-16), "win32", "libusb0") == "M-I1IO-DRIVE-BUSY"
    assert ul.open_failure(_usb_error(-19), "win32", "libusb0") == "M-I1IO-DRIVE-USB-GONE"
    assert ul.open_failure(_usb_error(-22), "win32", "libusb0") == "M-I1IO-DRIVE-USB-UNEXPECTED"
    # the same number means something else in libusb-1.0: the backend kind decides
    assert ul.open_failure(_usb_error(-4), "win32", "libusb1") == "M-I1IO-DRIVE-USB-GONE"
    assert ul.open_failure(_usb_error(-4), "win32", "libusb0") == "M-I1IO-DRIVE-USB-UNEXPECTED"


def test_a_libusb0_read_timeout_is_a_timeout_not_a_lost_link():
    import usb.core
    dev = FakeDev()
    t = tbl.FtdiUsb(dev, usb.core, FakeUtil(dev), timeout_codes=ul.LIBUSB0_TIMEOUT_CODES)

    def read(ep, n, timeout):
        raise usb.core.USBError("timeout", -116)
    dev.read = read
    assert t.read(0.1) == b""
    t1 = tbl.FtdiUsb(dev, usb.core, FakeUtil(dev))          # libusb1: -116 is not a timeout
    with pytest.raises(tbl.TransportError):
        t1.read(0.1)


def test_windows_opens_only_with_libusb_win32_bound(monkeypatch, bundled):
    import core.usb_driver_installer as inst
    for state in ("none", "vendor_driver", "cannot_tell"):
        monkeypatch.setattr(inst, "table_driver_state_now", lambda s=state: (s, {}))
        dev = FakeDev()
        _patch_usb(monkeypatch, [dev])
        with pytest.raises(tbl.NotAvailable) as e:
            tbl.open_table("win32")
        assert e.value.message_id == "M-I1IO-DRIVE-TABLE-DRIVER-NOT-INSTALLED"
        assert e.value.problem == f"table driver {state}"     # decided by the driver state
        assert dev.calls == [] and bundled == []


def test_the_windows_backend_is_libusb_win32s_own_dll_by_full_path(monkeypatch, tmp_path):
    import usb.backend.libusb0 as l0
    got = []
    monkeypatch.setattr(l0, "get_backend", lambda find_library=None: got.append(
        find_library("libusb0")) or "be0")
    monkeypatch.setattr(ul, "bundled_on_this_platform", lambda: True)
    dll = tmp_path / "libusb0.dll"
    tb = ul.table_backend("win32", dll_path=dll)
    assert (tb.backend, tb.kind) == ("be0", "libusb0") and got == [str(dll)]
    monkeypatch.setattr(ul, "libusb0_dll_path", lambda: None)
    assert ul.table_backend("win32").problem == "no-libusb0-dll"
    monkeypatch.setattr(ul, "bundled_on_this_platform", lambda: False)
    assert ul.table_backend("win32").problem == "not-bundled"


# (5) the per-system checks, from recorded answers ----------------------------------------------

def _d(v, p, hub=False):
    return {"vid": v, "pid": p, "place": None, "hub": hub, "interfaces": 0}


@pytest.mark.parametrize("devices,state", [
    (None, "cannot_tell"),
    ([_d(0x0971, 0x2004)], "no_instrument"),
    ([_d(0x0971, 0x2004), _d(0x0971, 0x2000)], "ok"),
    ([_d(0x0971, 0x2004), _d(0x0971, 0x2000), _d(0x0971, 0x2000)], "several_instruments"),
    ([_d(0x0971, 0x2004), _d(0x0971, 0x2000), _d(0x0765, 0x6009)], "other_instrument"),
    ([_d(0x0971, 0x2004), _d(0x0971, 0x2000), _d(0x05AC, 0x1234)], "ok"),
])
def test_the_instrument_check(devices, state):
    assert us.instrument_check(devices).state == state


def test_pyusb_enumeration_keeps_ids_only():
    class D:
        def __init__(self, v, p, c=0):
            self.idVendor, self.idProduct, self.bDeviceClass = v, p, c
            self.serial_number = "SECRET123"
    devs = us.list_devices("linux", pyusb_find=lambda: [D(0x0971, 0x2000), D(0x0971, 0x2004),
                                                        D(0x1d6b, 0x0002, 9)])
    assert devs == [_d(0x0971, 0x2000), _d(0x0971, 0x2004), _d(0x1d6b, 0x0002, True)]
    assert "SECRET" not in repr(devs)
    assert us.list_devices("windows", pyusb_find=lambda: (_ for _ in ()).throw(OSError())) is None
    assert us.list_devices("windows") is None            # no backend: cannot tell, not a guess
    assert us.list_devices("other") is None


def test_macos_lists_device_entries_only():
    roots = [{"IOObjectClass": "IOUSBHostDevice", "idVendor": 0x0971, "idProduct": 0x2000,
              "locationID": 1, "IORegistryEntryChildren": [
                  {"IOObjectClass": "IOUSBHostInterface", "bInterfaceNumber": 0,
                   "idVendor": 0x0971, "idProduct": 0x2000}]},
             {"IOObjectClass": "IOUSBHostDevice", "idVendor": 0x0971, "idProduct": 0x2004,
              "locationID": 2}]
    assert us.instrument_check(us.list_devices("macos", ioreg_roots=roots)).state == "ok"


def _sysfs(tmp_path, driver=None, holder=False, unreadable=False):
    sysfs, proc = tmp_path / "sys", tmp_path / "proc"
    dev = sysfs / "1-2"
    dev.mkdir(parents=True)
    (dev / "idVendor").write_text("0971\n", encoding="utf-8")
    (dev / "idProduct").write_text("2004\n", encoding="utf-8")
    (dev / "busnum").write_text("1\n", encoding="utf-8")
    (dev / "devnum").write_text("7\n", encoding="utf-8")
    intf = sysfs / "1-2:1.0"
    intf.mkdir()
    if driver:
        target = tmp_path / "drivers" / driver
        target.mkdir(parents=True)
        (intf / "driver").symlink_to(target)
    other = sysfs / "1-3"
    other.mkdir()
    (other / "idVendor").write_text("0971\n", encoding="utf-8")
    (other / "idProduct").write_text("2000\n", encoding="utf-8")
    p = proc / "4242"
    (p / "fd").mkdir(parents=True)
    (p / "comm").write_text("i1Profiler\n", encoding="utf-8")
    if holder:
        (p / "fd" / "5").symlink_to("/dev/bus/usb/001/007")
    if unreadable:
        (proc / "4243").mkdir()          # no fd folder: not readable as this user
    return str(sysfs), str(proc)


def test_linux_names_a_kernel_driver_and_the_programs_holding_the_table(tmp_path):
    s, p = _sysfs(tmp_path / "a", driver="ftdi_sio")
    c = us.holders_linux(s, p)
    assert c.state == "kernel_driver_bound" and c.detail["kernel_drivers"] == ["ftdi_sio"]
    s, p = _sysfs(tmp_path / "b", holder=True)
    c = us.holders_linux(s, p)
    assert c.state == "held" and c.detail["programs"] == ["i1Profiler"]
    s, p = _sysfs(tmp_path / "c")
    assert us.holders_linux(s, p).state == "nobody_listed"
    s, p = _sysfs(tmp_path / "d", unreadable=True)
    assert us.holders_linux(s, p).state == "cannot_tell"        # never a guess
    assert us.holders_linux(str(tmp_path / "none"), p).state == "cannot_tell"


def test_windows_cannot_tell_who_holds_the_table():
    c = us.holders_check("windows")
    assert c.state == "cannot_tell"


def test_macos_holders_from_ioreg_entries():
    assert us.holders_macos([]).state == "nobody_listed"
    c = us.holders_macos(["exclusive owner: i1Profiler (pid 77)", "connected: this program "
                                                                  "(pid 1)"])
    assert c.state == "held" and c.detail["programs"] == [{"how": "exclusive owner",
                                                           "program": "i1Profiler"}]
    assert us.holders_macos(["(macOS's list could not be read)"]).state == "cannot_tell"


def test_i1profiler_is_looked_for_per_system():
    class R:
        def __init__(self, out, rc=0):
            self.stdout, self.returncode = out, rc
    assert us.i1profiler_running("macos", run=lambda a: R("123\n" if a[1] == "-x" else "")) \
        is True
    assert us.i1profiler_running("macos", run=lambda a: R("")) is False
    assert us.i1profiler_running("macos", run=lambda a: None) is None
    assert us.i1profiler_running("windows", run=lambda a: R('"i1Profiler.exe","1234"')) is True
    assert us.i1profiler_running("windows", run=lambda a: R("INFO: No tasks")) is False
    assert us.i1profiler_running("windows", run=lambda a: R("", 1)) is None
    assert us.i1profiler_running("linux") is None


@pytest.mark.parametrize("state", ["none", "vendor_driver", "cannot_tell"])
def test_the_job_names_a_table_without_the_driver_on_windows(state):
    pf = us.Preflight("windows", {}, us.Check("ok"), us.Check("cannot_tell"), None,
                      us.Check(state))
    job, sim, _t = H.make_job(preflight=pf)
    r = job.open()
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "driver_not_installed_for_table")
    assert r.detail["driver_state"] == state and sim.received == []


def test_the_job_says_driver_installed_on_windows():
    pf = us.Preflight("windows", {}, us.Check("ok"), us.Check("cannot_tell"), None,
                      us.Check("libusb0"))
    job, sim, _t = H.make_job(preflight=pf)
    r = job.open()
    assert r.ok and r.detail["table_driver"] == "driver_installed"


@pytest.mark.parametrize("field,state,reason", [
    ("instrument", "no_instrument", "instrument_no_instrument"),
    ("instrument", "several_instruments", "instrument_several_instruments"),
    ("instrument", "other_instrument", "instrument_other_instrument"),
    ("instrument", "cannot_tell", "instrument_cannot_tell"),
    ("holders", "held", "table_held_by_another_program"),
    ("holders", "kernel_driver_bound", "table_held_by_a_kernel_driver"),
])
def test_anything_but_one_i1pro_and_a_free_table_is_refused_before_anything_is_sent(
        field, state, reason):
    pf = H.OK_PREFLIGHT
    pf = us.Preflight(pf.system, pf.usb, us.Check(state) if field == "instrument"
                      else pf.instrument, us.Check(state) if field == "holders" else pf.holders,
                      pf.i1profiler)
    opened = []
    job, sim, t = H.make_job(preflight=pf)
    job._open_transport = lambda: opened.append(1)
    r = job.open()
    assert (r.kind, r.reason) == (J.Kind.REFUSED, reason)
    assert opened == [] and sim.received == []


def test_a_holder_list_that_cannot_tell_does_not_refuse():
    pf = us.Preflight("linux", {}, us.Check("ok"), us.Check("cannot_tell"), None)
    job, sim, _t = H.make_job(preflight=pf)
    assert job.open().ok


def test_i1profiler_running_is_refused_before_opening():
    pf = us.Preflight("macos", {}, us.Check("ok"), us.Check("nobody_listed"), True)
    job, sim, _t = H.make_job(preflight=pf)
    r = job.open()
    assert r.reason == "i1profiler_running" and sim.received == []


@pytest.mark.parametrize("model", [("i1iO 3", "i1Pro 2"), ("i1iO 2", "i1Pro 3"),
                                   (None, None), ("i1iO", "i1Pro 2")])
def test_only_a_chart_for_an_i1io_2_with_an_i1pro_2_is_driven(model):
    sheet = H.demo_sheet()
    sheet["table_model"], sheet["head_model"] = model
    opened = []
    job, sim, _t = H.make_job(sheet=sheet)
    job._preflight = lambda: opened.append("preflight")
    r = job.open()
    assert r.reason == "chart_not_for_i1io2_with_i1pro2" and opened == [] and \
        sim.received == []


@pytest.mark.parametrize("message_id", ["M-I1IO-DRIVE-USB-MISSING", "M-I1IO-DRIVE-BUSY",
                                        "M-I1IO-DRIVE-TABLE-NOT-FOUND", "M-I1IO-DRIVE-NOT-I1IO2"])
def test_a_refused_usb_opening_is_a_named_refusal(message_id):
    job, sim, _t = H.make_job()

    def refuse():
        raise tbl.NotAvailable(message_id, problem="x")
    job._open_transport = refuse
    r = job.open()
    assert (r.kind, r.reason, r.detail["message_id"]) == (J.Kind.REFUSED, "usb_open_refused",
                                                          message_id)
    assert job.d is None and sim.received == []


def test_the_descriptor_check_refuses_another_device_before_anything():
    dev = FakeDev()
    dev.bcdDevice = 0x0600
    with pytest.raises(tbl.NotAvailable) as e:
        tbl.check_descriptors(dev)
    assert e.value.message_id == "M-I1IO-DRIVE-NOT-I1IO2" and dev.calls == []


if sys.platform == "darwin":
    def test_the_real_macos_lists_can_be_read_here():
        """On this Mac: ioreg answers (read only); no table needed."""
        assert us.list_devices("macos") is not None
        assert us.holders_check("macos").state in ("nobody_listed", "held", "cannot_tell")

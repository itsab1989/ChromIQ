"""THE i1iO TABLE DRIVE'S USB LIBRARY SHIPS, LOADS, AND TOUCHES NO DEVICE (build step 5).

`core/usb_library.py`: pyusb plus the libusb-1.0 of the `libusb-package` wheel, bundled by all
three PyInstaller specs, found by path (never the system's), loaded by the start-up self-test
without `libusb_init` and without listing or opening any device. Nothing else in the app uses it
yet. A minimal frozen build with the same bundling lines found and loaded the library from the
bundle (2026-11-17, desk proof); the full apps are proved by each release build's self-test.
"""
from __future__ import annotations

import ast
import hashlib
import shutil
import sys
from pathlib import Path

import pytest

from core import usb_library as U

ROOT = Path(__file__).resolve().parent.parent
SPECS = ("ChromIQ.spec", "ChromIQWin.spec", "ChromIQLinux.spec")
LICENCES = {
    "pyusb-LICENSE": "03e39fdcee9c18f2f9d0c3500a993ddeac050695eb81070ea41347587c76a7fe",
    "libusb-package-LICENSE": "a6cba85bc92e0cff7a450b1d873c0eaa2e9fc96bf472df0247a26bec77bf3ff9",
    "libusb-COPYING": "5df07007198989c622f5d41de8d703e7bef3d0e79d62e24332ee739a452af62a",
    "libusb-AUTHORS": "27fd82b016838197d5276ba98d2187ed5a1ad0e171767322f356f0a9f6395941",
    "importlib_resources-LICENSE":
        "e2f7bb0557e7a381499f15baa7c1d776d83d6616599179d71d3109b8e39f7b25",
}


def test_the_library_loads_here_and_says_its_version():
    if not U.bundled_on_this_platform():
        pytest.skip("Windows on ARM64: nothing bundled on purpose")
    st = U.status()
    assert st.ok, st
    assert st.pyusb == "1.2.1"
    assert st.libusb.startswith("1.0.")
    assert st.selftest_field() == f"usb=pyusb-1.2.1/libusb-{st.libusb}"
    assert Path(st.path).name == U.LIBRARY_NAME


def test_the_status_touches_no_device(monkeypatch):
    """No libusb_init, no enumeration: pyusb's backend and find are never asked."""
    if not U.bundled_on_this_platform():
        pytest.skip("Windows on ARM64")
    import usb.backend.libusb1
    import usb.core

    def refuse(*_a, **_k):
        raise AssertionError("the self-test path asked pyusb for a backend or a device")

    monkeypatch.setattr(usb.backend.libusb1, "get_backend", refuse)
    monkeypatch.setattr(usb.core, "find", refuse)
    assert U.status().ok
    src = (ROOT / "core" / "usb_library.py").read_text(encoding="utf-8")
    body = src.split("def status()", 1)[1].split("\ndef ", 1)[0]
    assert "get_backend" not in body and "find(" not in body and "libusb_init" not in body


def test_the_system_library_is_never_used(monkeypatch):
    # not installed where nothing is bundled (Windows on ARM64, review A2-a)
    libusb_package = pytest.importorskip("libusb_package")
    monkeypatch.setattr(libusb_package, "get_library_path", lambda: None)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert U.library_path() is None
    st = U.status()
    assert not st.ok and st.problem in ("no-libusb", "not-bundled")


def test_the_frozen_app_finds_the_library_in_its_package_folder(tmp_path, monkeypatch):
    if not U.bundled_on_this_platform():
        pytest.skip("Windows on ARM64")
    import libusb_package
    real = libusb_package.get_library_path()
    monkeypatch.setattr(libusb_package, "get_library_path", lambda: None)
    (tmp_path / "libusb_package").mkdir()
    shutil.copy2(real, tmp_path / "libusb_package" / U.LIBRARY_NAME)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert U.library_path() == tmp_path / "libusb_package" / U.LIBRARY_NAME
    assert U.status().ok


def test_a_library_that_does_not_load_is_said_as_such(tmp_path, monkeypatch):
    bad = tmp_path / U.LIBRARY_NAME
    bad.write_bytes(b"not a library")
    monkeypatch.setattr(U, "library_path", lambda: bad)
    monkeypatch.setattr(U, "bundled_on_this_platform", lambda: True)
    st = U.status()
    assert not st.ok and st.problem == "libusb-does-not-load"
    assert U.MESSAGE_FOR_PROBLEM[st.problem] == "M-I1IO-DRIVE-USB-MISSING"


def test_windows_on_arm64_has_none_on_purpose(monkeypatch):
    monkeypatch.setattr(U.sys, "platform", "win32")
    monkeypatch.setattr(U.platform, "machine", lambda: "ARM64")
    assert U.bundled_on_this_platform() is False
    st = U.status()
    assert st.problem == "not-bundled" and st.selftest_field() == "usb=not-bundled"
    assert U.backend() is None
    assert U.MESSAGE_FOR_PROBLEM["not-bundled"] == "M-I1IO-DRIVE-USB-NOT-ON-THIS-SYSTEM"


class _USBError(Exception):
    def __init__(self, code=None, errno=None):
        super().__init__("x")
        self.backend_error_code = code
        self.errno = errno


class NoBackendError(Exception):
    pass


@pytest.mark.parametrize("exc,system,msg", [
    (_USBError(-3), "linux", "M-I1IO-DRIVE-USB-LINUX-PERMISSION"),
    (_USBError(-3), "win32", "M-I1IO-DRIVE-USB-WINDOWS-DRIVER"),
    (_USBError(-3), "darwin", "M-I1IO-DRIVE-BUSY"),
    (_USBError(-12), "win32", "M-I1IO-DRIVE-USB-WINDOWS-DRIVER"),
    (_USBError(-12), "darwin", "M-I1IO-DRIVE-USB-UNEXPECTED"),
    (_USBError(-6), "linux", "M-I1IO-DRIVE-USB-LINUX-KERNEL-DRIVER"),
    (_USBError(-6), "darwin", "M-I1IO-DRIVE-BUSY"),
    (_USBError(-4), "darwin", "M-I1IO-DRIVE-USB-GONE"),
    (_USBError(-5), "win32", "M-I1IO-DRIVE-USB-GONE"),
    (_USBError(None, errno=13), "linux", "M-I1IO-DRIVE-USB-LINUX-PERMISSION"),
    (_USBError(-99), "linux", "M-I1IO-DRIVE-USB-UNEXPECTED"),
    (OSError("odd"), "darwin", "M-I1IO-DRIVE-USB-UNEXPECTED"),
    (NoBackendError(), "linux", "M-I1IO-DRIVE-USB-MISSING"),
])
def test_every_open_failure_gets_its_own_message(exc, system, msg):
    assert U.open_failure(exc, system) == msg


def test_the_diagnostics_hold_no_path_with_a_user_name():
    d = U.diagnostics()
    assert set(d) == {"platform", "machine", "pyusb", "libusb", "problem", "library"}
    assert "/" not in d["library"] and "\\" not in d["library"]


@pytest.mark.parametrize("spec", SPECS)
def test_every_spec_bundles_it_with_its_licences(spec):
    src = (ROOT / spec).read_text(encoding="utf-8")
    assert "collect_dynamic_libs('libusb_package')" in src
    assert "*_usb_binaries" in src and "*_usb_licences" in src and "*_USB_HIDDENIMPORTS" in src
    for name in ("'core.usb_library'", "'usb.backend.libusb1'", "'libusb_package'",
                 "'importlib_resources'"):
        assert name in src, (spec, name)
    for f in LICENCES:
        assert f"'{f}'" in src, (spec, f)
    assert "'importlib_resources-LICENSE'" in src and "'README.md'" in src


def test_the_licence_texts_are_the_packages_own():
    for name, sha in LICENCES.items():
        data = (ROOT / "vendor" / "usb" / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == sha, name
    assert b"GNU LESSER GENERAL PUBLIC LICENSE" in (ROOT / "vendor/usb/libusb-COPYING").read_bytes()
    assert (ROOT / "vendor/usb/importlib_resources-LICENSE").read_text(
        encoding="utf-8").lstrip().startswith("Apache License")
    notices = (ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    assert "## USB access for the i1iO table" in notices
    # no source distribution exists on PyPI (review A1-a): the source is the GitHub tag
    readme = (ROOT / "vendor/usb/README.md").read_text(encoding="utf-8")
    for text in (" ".join(notices.split()), " ".join(readme.split())):
        assert "source distribution" not in text
        assert "https://github.com/pyocd/libusb-package/tree/v1.0.30.1" in text
    from ui.licences import NOTICE_SECTIONS
    assert "USB access for the i1iO table" in NOTICE_SECTIONS


def test_the_requirements_pin_it_and_leave_windows_arm64_out():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "\npyusb==1.2.1\n" in req
    assert ('importlib_resources==7.1.0 ; sys_platform != "win32" or '
            'platform_machine != "ARM64"') in req
    assert ('libusb-package==1.0.30.1 ; sys_platform != "win32" or '
            'platform_machine != "ARM64"') in req


def test_the_release_builds_make_it_universal_and_prove_it_loads():
    mac = (ROOT / ".github/workflows/build-release.yml").read_text(encoding="utf-8")
    assert "lipo_pkg libusb-package       libusb_package    py3-none" in mac
    linux = (ROOT / ".github/workflows/build-linux.yml").read_text(encoding="utf-8")
    step = linux.index("Start the built app's self-test")
    assert step < linux.index("Package as tar.gz")
    assert "CHROMIQ_SELFTEST=1 QT_QPA_PLATFORM=offscreen timeout 300 ./dist/ChromIQ/ChromIQ" in linux
    # Qt's widgets need libGL on the runner, as tests.yml installs it (review A2-b)
    apt = linux[:linux.index("Install Python dependencies")]
    assert "            libgl1 \\\n" in apt and "            libxkbcommon0 \\\n" in apt


def test_only_the_selftest_uses_it_yet():
    users = []
    for base in ("core", "ui", "workflow", "scripts"):
        for f in (ROOT / base).rglob("*.py"):
            if f.name == "usb_library.py" and f.parent.name == "core":
                continue
            tree = ast.parse(f.read_text(encoding="utf-8"), str(f))
            for n in ast.walk(tree):
                mods = ([a.name for a in n.names] if isinstance(n, ast.Import) else
                        [n.module or ""] if isinstance(n, ast.ImportFrom) else [])
                if any(m == "core.usb_library" or m == "usb" or m.startswith("usb.")
                       for m in mods):
                    users.append(f.relative_to(ROOT).as_posix())
    # build step 6: the table package opens the table and lists devices through it (still
    # reached by nothing in the app: tests/test_i1io_table_not_reached_by_the_app.py)
    assert sorted(set(users)) == ["core/selftest.py", "workflow/i1io/table/session_table.py",
                                  "workflow/i1io/table/usb_system.py"]


def test_the_windows_driver_installer_never_targets_the_table_without_the_explicit_choice():
    """The owner's ruling of 2026-11-17: on Windows the table (0971:2004) is reached like an
    ArgyllCMS instrument, through libusb-win32, which ChromIQ's installer may bind to it ONLY on
    the person's explicit table choice: never automatically, never as part of an instrument's
    installation (while it has that driver, i1Profiler cannot use the table)."""
    from core import usb_driver_installer as inst
    # not among the instruments the driver window walks and offers
    for table in (inst.KNOWN_COLORIMETERS, inst.VENDOR_SERIAL_DEVICES):
        assert ("0971", "2004") not in {(v.lower(), p.lower()) for v, p in table}
    assert set(inst.TABLE_DEVICE) == {("0971", "2004")}
    # the registry holding the table (with any driver) never makes it an offered instrument
    entries = [("VID_0971&PID_2004", [("6&abc&0&1", "")]),
               ("VID_0971&PID_2000", [("6&def&0&2", "")])]
    found = inst.attached_devices(entries, None)
    assert [(d.vid, d.pid) for d in found] == [("0971", "2000")]
    # installing for the table: refused unless the device came from the explicit choice
    plain = inst.UsbDevice("0971", "2004", "X-Rite i1iO 2 table", False)
    assert inst.install_winusb(plain) is inst.InstallAttempt.REFUSED
    with pytest.raises(ValueError):
        inst.ExplicitTableChoice("yes")
    with pytest.raises(ValueError):
        inst.table_device_for("install the libusb-win32 driver for my i1iO table")
    dev = inst.table_device_for(inst.ExplicitTableChoice(inst.TABLE_CHOICE_WORDS))
    assert (dev.vid, dev.pid) == ("0971", "2004") and isinstance(dev, inst.TableUsbDevice)
    got = inst.install_winusb(dev)
    assert got is not inst.InstallAttempt.REFUSED      # NOT_WINDOWS here, the install on Windows
    # nothing else in ChromIQ builds the choice: only the module itself names it
    users = [f for base in ("core", "ui", "workflow", "scripts")
             for f in (ROOT / base).rglob("*.py")
             if "ExplicitTableChoice(" in f.read_text(encoding="utf-8")
             and f.name != "usb_driver_installer.py"]
    assert users == []


@pytest.mark.parametrize("entries,present,want", [
    (None, None, "cannot_tell"),
    ([], None, "none"),
    ([("VID_0971&PID_2004", [("6&a&0&1", "")])], None, "none"),
    ([("VID_0971&PID_2004", [("6&a&0&1", "libusb0")])], None, "libusb0"),
    ([("VID_0971&PID_2004", [("6&a&0&1", "FTDIBUS")])], None, "vendor_driver"),
    ([("VID_0971&PID_2004", [("6&a&0&1", "XRiteDevice")])], None, "vendor_driver"),
    ([("VID_0971&PID_2004", [("6&a&0&1", "libusb0"), ("6&b&0&2", "FTDIBUS")])],
     {"USB\\VID_0971&PID_2004\\6&B&0&2"}, "vendor_driver"),       # the live one decides
    ([("VID_0971&PID_2004", [("6&a&0&1", "FTDIBUS"), ("6&b&0&2", "libusb0")])],
     {"USB\\VID_0971&PID_2004\\6&B&0&2"}, "libusb0"),
    ([("VID_0971&PID_2004", [("6&a&0&1", "libusb0")])], set(), "none"),   # remembered, gone
    ([("VID_0971&PID_2004", [("6&a&0&1", "winusb")])], None, "vendor_driver"),  # not libusb0
])
def test_the_tables_driver_state_is_read_from_the_registry(entries, present, want):
    from core import usb_driver_installer as inst
    state, detail = inst.table_driver_state(entries, present)
    assert state == want
    assert "6&" not in repr(detail)        # never an instance key (it can hold a serial)
